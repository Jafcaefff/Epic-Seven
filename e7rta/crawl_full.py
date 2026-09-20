"""全量并发抓取（后台常驻），支持按赛季精准抓取。

复用 crawler.crawl_player，用线程池并发遍历所有未抓玩家。
- season 指定时用 API 精准返回该赛季（落库最小）；否则本地过滤 ss17+。
- 断点续传：crawl_progress 按 (nick_no, season) 维度跳过已抓玩家。
- SQLite WAL 模式支持多连接读写。

用法：
  python crawl_full.py [workers] [season] [limit]
    workers  并发线程数（默认 6，建议 4~8）
    season   赛季代码，如 pvp_rta_ss21；留空=ss17+ 全量
    limit    本次最多抓取玩家数（默认 0=全量；调试可用 5000）

示例：
  python crawl_full.py 6 pvp_rta_ss21        # 全量抓最新赛季 ss21（DB 最小）
  python crawl_full.py 6 "" 5000             # 先抓 5000 玩家观察全量
"""
import sys
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import config
import db
from importer import import_static, import_seasons
from crawler import crawl_player

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "data.db")


def work(nick_no, season):
    """单玩家抓取（独立连接，线程安全）。返回 (no, status, battles, error)。"""
    conn = db.connect(DB)
    try:
        n = crawl_player(conn, nick_no, season)
        status = "done" if n and n > 0 else "empty"
        err = None
    except Exception as e:  # noqa: BLE001
        n = 0
        status = "error"
        err = str(e)[:200]
    finally:
        conn.close()
    return nick_no, status, n or 0, err


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    season = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    # 初始化数据库 + 静态数据（幂等）
    conn = db.connect(DB)
    import_static(conn)
    import_seasons(conn)
    cur = conn.cursor()
    sk = season or ""
    if limit and limit > 0:
        cur.execute(
            """SELECT p.nick_no FROM players p
               WHERE p.nick_no NOT IN (SELECT nick_no FROM crawl_progress WHERE season=?)
               ORDER BY p.rowid LIMIT ?""",
            (sk, limit),
        )
    else:
        cur.execute(
            """SELECT p.nick_no FROM players p
               WHERE p.nick_no NOT IN (SELECT nick_no FROM crawl_progress WHERE season=?)""",
            (sk,),
        )
    todos = [r[0] for r in cur.fetchall()]
    conn.close()

    print(f"待抓玩家: {len(todos)} | 并发: {workers} | 赛季: {season or 'ss17+(全部)'} | 限流: {config.REQUEST_INTERVAL}s/请求")
    done = empty = err = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, no, season) for no in todos]
        for i, f in enumerate(futs, 1):
            no, status, n, e = f.result()
            c2 = db.connect(DB)
            c2.execute(
                "INSERT OR REPLACE INTO crawl_progress (nick_no, season, status, battles, error, fetched_at) VALUES (?,?,?,?,?,?)",
                (no, season or "", status, n, e, datetime.now(timezone.utc).isoformat()),
            )
            c2.commit()
            c2.close()
            if status == "done":
                done += 1
            elif status == "empty":
                empty += 1
            else:
                err += 1
            if i % 100 == 0 or i == len(todos):
                print(f"  [{i}/{len(todos)}] done={done} empty={empty} err={err}")


if __name__ == "__main__":
    main()
