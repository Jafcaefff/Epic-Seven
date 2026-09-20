import urllib.request, re, os

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
BASE = "https://e7stats.qyzlgame.com"

def get(url, headers=None):
    h = {"User-Agent": UA}
    if headers: h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.headers.get("Content-Type"), r.read()

# 首页拿到 bundle 路径
s, ct, html = get(BASE + "/")
html = html.decode("utf-8", "replace")
scripts = re.findall(r'src="([^"]+\.js[^"]*)"', html)
print("scripts:", scripts)

bundle_url = None
for sc in scripts:
    if "bundle" in sc:
        bundle_url = BASE + sc if sc.startswith("/") else BASE + "/" + sc
print("bundle_url:", bundle_url)

s, ct, bundle = get(bundle_url)
print("bundle status:", s, "bytes:", len(bundle))
out = os.path.join(os.path.dirname(__file__), "bundle.js")
with open(out, "wb") as f:
    f.write(bundle)
print("saved ->", out)

# 提取所有 /gameApi/ 路径
text = bundle.decode("utf-8", "replace")
paths = re.findall(r'/gameApi/[A-Za-z0-9_/?=&.-]+', text)
# 也抓被拼接的形式： "/gameApi/" 前缀
paths2 = re.findall(r'"/gameApi/[^"]*"', text)
allp = set(paths) | set(p.replace('"','') for p in paths2)
print("\n=== gameApi 端点（去重，含占位符）===")
for p in sorted(allp):
    print(" ", p)

# 统计每个端点出现次数
from collections import Counter
cnt = Counter(re.findall(r'/gameApi/[A-Za-z0-9_]+', text))
print("\n=== 端点出现频次 ===")
for k, v in cnt.most_common():
    print(f"  {k}: {v}")
