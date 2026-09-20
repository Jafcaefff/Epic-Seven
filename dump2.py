import urllib.request, json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
base = "https://e7stats.qyzlgame.com"

def post(url, data, headers=None):
    h = {"User-Agent": UA, "Referer": base + "/", "Content-Type": "application/x-www-form-urlencoded"}
    if headers: h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

q = "nick_no=1100111328105&world_code=world_zlong1&lang=zh-CN&season_code="
b0 = post(base + "/gameApi/getBattleList", q.encode())["result_body"]["battle_list"][0]

# 解析字符串化 JSON
def parse_str(s):
    return json.loads("{" + s + "}")

tb = parse_str(b0["teamBettleInfo"])
tbe = parse_str(b0["teamBettleInfoenemy"])
pb = parse_str(b0["prebanList"])
pbe = parse_str(b0["prebanListEnemy"])

print("teamBettleInfo keys:", list(tb.keys()), "| my_team len:", len(tb.get("my_team", [])))
print("teamBettleInfoenemy keys:", list(tbe.keys()), "| enemy_team len:", len(tbe.get("enemy_team", [])))
print("prebanList keys:", list(pb.keys()), "->", pb)
print("prebanListEnemy keys:", list(pbe.keys()), "->", pbe)

mt = tb.get("my_team", [])
if mt:
    print("\n=== my_team[0] full ===")
    print(json.dumps(mt[0], ensure_ascii=False)[:500])
    keys = set()
    def collect(o):
        if isinstance(o, dict):
            keys.update(o.keys()); 
            for v in o.values(): collect(v)
        elif isinstance(o, list):
            for v in o: collect(v)
    for x in mt: collect(x)
    print("union keys across my_team:", sorted(keys))

# 英雄映射
h = json.loads(urllib.request.urlopen("https://media.zlongame.com/media/pictures/qy/e7/actv/2023/Epic7_Stats/json/epic7_hero.json?_=1", timeout=20).read().decode("utf-8"))
hmap = {x["code"]: x["name"] for x in h["zh-CN"]}
# 取 my_team[0] 里可能的英雄 code 字段
def find_codes(o):
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            if k.lower() in ("hero_code", "code", "herocode") and v:
                out.append((k, v, hmap.get(v, "??")))
            else:
                out += find_codes(v)
    elif isinstance(o, list):
        for v in o: out += find_codes(v)
    return out
print("\nhero codes in my_team[0]:", find_codes(mt[0])[:6])
print("preban names:", [hmap.get(c, "??") for c in (pb.get('preban_list') or []) if c])
