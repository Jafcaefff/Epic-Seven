import urllib.request, json, sys

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"

def fetch(url, data=None, headers=None):
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read()
            return r.status, r.headers.get("Content-Type"), body
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()
    except Exception as e:
        return None, f"ERR: {type(e).__name__}: {e}", b""

base = "https://media.zlongame.com"
ts = "1726660000000"
tests = {
    "1_user_world_json": f"{base}/media/pictures/qy/e7/actv/2023/Epic7_Stats/json/epic7_user_world_cn.json?_={ts}",
    "2_hero_json": f"{base}/media/pictures/qy/e7/actv/2023/Epic7_Stats/json/epic7_hero.json?_={ts}",
}

for name, url in tests.items():
    status, ctype, body = fetch(url)
    print(f"=== {name} ===")
    print("URL:", url)
    print("Status:", status, "| Content-Type:", ctype)
    txt = body.decode("utf-8", "replace")
    print("Bytes:", len(body))
    try:
        j = json.loads(txt)
        print("JSON keys:", list(j.keys()) if isinstance(j, dict) else type(j))
        if isinstance(j, dict):
            if "users" in j:
                print("users len:", len(j["users"]))
            if "zh-CN" in j:
                print("zh-CN len:", len(j["zh-CN"]))
    except Exception as e:
        print("JSON parse failed:", e)
        print("head:", txt[:300])
    print()

# POST getBattleList (try with a guessed nick_no / empty)
post_url = "https://e7stats.qyzlgame.com/gameApi/getBattleList"
from urllib.parse import urlencode
params = urlencode({"nick_no": "1000001", "world_code": "world_zlong1", "lang": "zh-CN", "season_code": ""})
status, ctype, body = fetch(post_url + "?" + params)
print("=== 3_getBattleList (POST) ===")
print("URL:", post_url + "?" + params)
print("Status:", status, "| Content-Type:", ctype)
print("Bytes:", len(body))
txt = body.decode("utf-8", "replace")
try:
    j = json.loads(txt)
    print("JSON keys:", list(j.keys()) if isinstance(j, dict) else type(j))
except Exception as e:
    print("JSON parse failed:", e)
    print("head:", txt[:500])
