import urllib.request, json, re

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
# 1) 查 archive.org 是否有快照
avail_url = "http://archive.org/wayback/available?url=e7stats.qyzlgame.com"
try:
    req = urllib.request.Request(avail_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    print("wayback available:", json.dumps(data, ensure_ascii=False)[:500])
    snap = data.get("archived_snapshots", {}).get("closest", {})
    if snap.get("available"):
        print("closest snapshot:", snap.get("url"))
except Exception as e:
    print("wayback available failed:", e)

# 2) 直接试一个已知时间戳的 bundle.js（2024年某次）
candidates = [
    "https://web.archive.org/web/2024/https://e7stats.qyzlgame.com/next/actv/2024/Epic7_Stats/assets/js/bundle.js",
    "https://web.archive.org/web/2024id_/https://e7stats.qyzlgame.com/next/actv/2024/Epic7_Stats/assets/js/bundle.js",
]
for url in candidates:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read()
        print(f"\n{url}\n  status ok bytes={len(body)}")
        txt = body.decode("utf-8", "replace")
        paths = set(re.findall(r'/gameApi/[A-Za-z0-9_]+', txt))
        print("  gameApi paths found:", sorted(paths))
        # 找 chunk 引用
        chunks = set(re.findall(r'/_next/static/chunks/[A-Za-z0-9_./-]+\.js', txt))
        print("  next chunks:", list(chunks)[:20])
    except Exception as e:
        print(f"\n{url}\n  failed: {type(e).__name__}: {e}")
