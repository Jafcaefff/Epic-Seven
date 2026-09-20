"""下载第七史诗英雄头像到本地（本地缓存，避免运行时依赖外部 CDN）。

用法（在你自己的机器上跑）：
    python fetch_images.py --test           # 只测 1 张，秒出结论（排障先跑这个）
    python fetch_images.py                  # 下载全部英雄图标
    python fetch_images.py --workers 16     # 提高并发
    python fetch_images.py --suffix _l      # 横条立绘（_s 图标 / _su 横条右 / _l 横条左）

图片来源（2026-09-18 实测可用，按英雄 code 命名，无需别名映射）：
    https://cdn.jsdelivr.net/gh/CeciliaBot/E7Assets-Temp@main/assets/face/<code>_s.png

为什么换源：旧网文档说的 assets.epicsevendb.com 已不可达 —— 该站已 301 迁到
epic7db.com，旧 assets 子域的 nginx 不认识这个主机名，TLS 握手直接报
TLSV1_UNRECOGNIZED_NAME（换域名/跳过证书/不发 SNI 都救不了）。
epic7db.com 的图片改用「英文名 slug」（/images/heroes/perfumer-byblis.webp），
和我们的数字 code 对不上；而 CeciliaBot/E7Assets-Temp 仓库保留了官方原始资源、仍按
code 命名，经 jsDelivr 加速，国内可直接访问。

输出目录：static/img/heroes/<code>.png
前端加载顺序：本地 /img/heroes/<code>.png → CDN → 属性色 SVG 占位
"""
import argparse
import concurrent.futures as futures
import os
import sqlite3
import sys
import time
import urllib.request
import urllib.error

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "img", "heroes")
IMG_BASE = "https://cdn.jsdelivr.net/gh/CeciliaBot/E7Assets-Temp@main/assets/face/"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://epicsevendb.com/",
}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

TIMEOUT = 8          # 单次请求超时(秒)——原为 25，失败时太难熬
RETRIES = 2          # 重试次数（不含首次）——原为 3
MAX_FAILLOG = 30


def load_codes():
    """从 heroes 表取全部英雄 code（含中文名，便于报错定位）。"""
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT code, name FROM heroes ORDER BY code").fetchall()
    conn.close()
    return rows


def fetch_one(item):
    code, name = item
    suffix = fetch_one.suffix
    dst = os.path.join(OUT, code + ".png")
    # 已存在且非空且是真 PNG → 跳过（断点续传）
    if os.path.isfile(dst) and os.path.getsize(dst) > 0:
        with open(dst, "rb") as f:
            if f.read(8) == PNG_MAGIC:
                return (code, name, "skip", "")
    url = IMG_BASE + code + suffix + ".png"
    last_err = ""
    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read()
            if not data.startswith(PNG_MAGIC):
                last_err = f"非PNG(len={len(data)})"
                time.sleep(0.3)
                continue
            tmp = dst + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dst)
            return (code, name, "ok", len(data))
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code in (400, 403, 404):
                break
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(0.4 * (attempt + 1))
    return (code, name, "fail", last_err)


def fmt_line(done, total, t0, cur, counts):
    el = time.time() - t0
    pct = done * 100.0 / total if total else 0
    rate = counts["ok"] / el if el > 0 else 0
    return (f"\r  [{el:5.1f}s] {done:3d}/{total} ({pct:5.1f}%) "
            f"新增={counts['ok']:3d} 已有={counts['skip']:3d} 失败={counts['fail']:3d} "
            f"{rate:5.1f}张/秒  当前:{cur:<14}")


def run(heroes, workers, quiet=False):
    counts = {"ok": 0, "skip": 0, "fail": 0}
    failures = []
    done = 0
    t0 = time.time()
    sys.stdout.write("\r  启动下载线程... " + " " * 40)
    sys.stdout.flush()
    with futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fetch_one, h): h for h in heroes}
        for fut in futures.as_completed(futs):        # 谁先完就先出反馈（不再按提交顺序阻塞）
            code, name, status, info = fut.result()
            done += 1
            counts[status] += 1
            if status == "fail":
                failures.append((code, name, info))
                if len(failures) <= 5:                # 立刻暴露前几条失败，别让用户干等
                    print(f"\n    ✗ {code} {name or ''} -> {info}")
            elif status == "ok" and not quiet and done <= 3:
                print(f"\n    ✓ 首批到达 {code} {name or ''} （{info}B）——网络正常")
            if not quiet:
                cur = f"{code} {name or ''}"
                sys.stdout.write(fmt_line(done, len(heroes), t0, cur, counts))
                sys.stdout.flush()
    print("\r" + " " * 120 + "\r", end="")  # 清行
    return counts, failures, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--suffix", default="_s", choices=["_s", "_su", "_l"])
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个（调试用）")
    ap.add_argument("--test", action="store_true", help="只测 1 张图并立即给出诊断")
    a = ap.parse_args()
    fetch_one.suffix = a.suffix

    os.makedirs(OUT, exist_ok=True)

    # ---- 快速自检模式：1 张图定生死 ----
    if a.test:
        print("=== 单图自检 ===")
        print(f"目标: {IMG_BASE}c2124{a.suffix}.png")
        t0 = time.time()
        code, name, status, info = fetch_one(("c2124", "自检英雄"))
        dt = time.time() - t0
        if status in ("ok", "skip"):
            size = os.path.getsize(os.path.join(OUT, "c2124.png"))
            print(f"  ✓ 成功 ({status}) {size}B 用时 {dt:.2f}s")
            print("  → 网络可达该 CDN，直接跑 `python fetch_images.py` 下载全部。")
        else:
            print(f"  ✗ 失败 用时 {dt:.2f}s  原因: {info}")
            print("\n  排查：")
            print("   1. 浏览器打开 https://assets.epicsevendb.com/_source/face/c2124_s.png 看能否显示")
            print("   2. 若本机有代理/加速器，先临时关掉，或在 CMD 执行：")
            print("      set HTTP_PROXY= && set HTTPS_PROXY=")
            print("      再重跑本脚本")
            print("   3. 仍不行则是网络屏蔽该域名，需要换网络/VPN")
        return

    heroes = load_codes()
    if a.limit:
        heroes = heroes[: a.limit]
    if not heroes:
        print("heroes 表为空，请先运行 importer.py 导入静态数据")
        sys.exit(1)

    print(f"英雄总数: {len(heroes)}  并发: {a.workers}  变体: {a.suffix}")
    print(f"输出目录: {OUT}")
    print(f"超时 {TIMEOUT}s / 重试 {RETRIES} 次，Ctrl+C 可随时中断（已下载的会保留）")
    print("-" * 70)

    counts, failures, dt = run(heroes, a.workers)

    print(f"完成 用时 {dt:.1f}s：新增 {counts['ok']} / 已存在 {counts['skip']} / 失败 {counts['fail']}")
    if failures:
        print(f"\n失败明细（前 {min(MAX_FAILLOG, len(failures))} 条）：")
        for c, n, i in failures[:MAX_FAILLOG]:
            print(f"  {c:8} {n or '':12} {i}")
        print("\n若几乎全部失败 → 跑 `python fetch_images.py --test` 看单图诊断。")
        print("注意：此 CDN 在某些网络/代理下不可达；如果只是少量失败，多为该英雄无此变体图。")
    else:
        print("全部头像就绪。前端会优先加载本地图片，离线可用。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已中断。已下载的头像保留在目录中，重跑自动跳过。")
