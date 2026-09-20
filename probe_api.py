import urllib.request, re, json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"

def fetch(url, data=None, headers=None, method=None):
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers: h.update(headers)
    m = method or ("POST" if data is not None else "GET")
    req = urllib.request.Request(url, data=data, headers=h, method=m)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()
    except Exception as e:
        return None, f"ERR:{e}", b""

base = "https://e7stats.qyzlgame.com"

# 1) 首页 HTML，提取 script 与 api 线索
status, ctype, body = fetch(base + "/")
html = body.decode("utf-8", "replace")
print("Home status:", status, ctype, "bytes:", len(body))
scripts = re.findall(r'src="([^"]+\.js[^"]*)"', html)
scripts = [s for s in scripts if not s.startswith("http")]
print("Scripts found:", scripts[:10])
api_hits = re.findall(r'[/\"\']([^\"\']*api[^\"\']*)[\"\']', html, re.I)
print("api-like in HTML:", list(dict.fromkeys(api_hits))[:20])

# 2) 探测 gameApi 的几种姿势
def probe(label, url, data=None, headers=None, method=None):
    s, ct, b = fetch(url, data, headers, method)
    t = b.decode("utf-8", "replace")
    head = t[:160].replace("\n", " ")
    print(f"[{label}] {s} {ct} bytes={len(b)} | {head}")

q = "nick_no=1000001&world_code=world_zlong1&lang=zh-CN&season_code="
probe("query+referer", base + "/gameApi/getBattleList?" + q, headers={"Referer": base + "/"})
probe("body+referer", base + "/gameApi/getBattleList", data=q.encode(),
      headers={"Referer": base + "/", "Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest"})
probe("GET query", base + "/gameApi/getBattleList?" + q, method="GET")

# 3) 下载首个 JS 挖真实接口
if scripts:
    js_url = base + "/" + scripts[0].lstrip("/")
    s, ct, b = fetch(js_url)
    js = b.decode("utf-8", "replace")
    print(f"\nJS {scripts[0]} status={s} bytes={len(b)}")
    for kw in ["gameApi", "getBattleList", "world_code", "nick_no", "api/"]:
        for m in re.finditer(re.escape(kw), js):
            i = max(0, m.start()-60); j = min(len(js), m.end()+60)
            print(f"  {kw} -> ...{js[i:j]}...")
            break
