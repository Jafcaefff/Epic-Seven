import urllib.request, json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
base = "https://e7stats.qyzlgame.com"

def fetch(url, data=None, headers=None):
    h = {"User-Agent": UA, "Referer": base + "/", "Content-Type": "application/x-www-form-urlencoded"}
    if headers: h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

q = "nick_no=1100111328105&world_code=world_zlong1&lang=zh-CN&season_code="
j = fetch(base + "/gameApi/getBattleList", q.encode())
bl = j["result_body"]["battle_list"]
b0 = bl[0]

def show(label, obj, depth=0):
    if isinstance(obj, dict):
        print(f"{label}: dict keys={list(obj.keys())}")
    elif isinstance(obj, list):
        print(f"{label}: list len={len(obj)}")
        if obj:
            show(f"  {label}[0]", obj[0], depth+1)
    else:
        s = str(obj)
        print(f"{label}: {s[:120]}")

print("=== my_deck ==="); show("my_deck", b0.get("my_deck"))
print("\n=== enemy_deck ==="); show("enemy_deck", b0.get("enemy_deck"))
print("\n=== teamBettleInfo (top) ==="); show("teamBettleInfo", b0.get("teamBettleInfo"))
print("\n=== prebanList ==="); show("prebanList", b0.get("prebanList"))
print("=== prebanListEnemy ==="); show("prebanListEnemy", b0.get("prebanListEnemy"))

# 深入 teamBettleInfo[0]
tb = b0.get("teamBettleInfo")
if isinstance(tb, list) and tb:
    print("\n=== teamBettleInfo[0] full ===")
    print(json.dumps(tb[0], ensure_ascii=False)[:600])
    # 找英雄 code / first_pick / ban 字段
    keys = set()
    def collect(o):
        if isinstance(o, dict):
            keys.update(o.keys())
            for v in o.values(): collect(v)
        elif isinstance(o, list):
            for v in o: collect(v)
    collect(tb[0])
    print("teamBettleInfo[0] keys:", sorted(keys))

# 英雄映射验证
s, ct, b = urllib.request.urlopen(
    "https://media.zlongame.com/media/pictures/qy/e7/actv/2023/Epic7_Stats/json/epic7_hero.json?_=1", timeout=20).read()
heroes = json.loads(b.decode("utf-8"))["zh-CN"]
hmap = {h["code"]: h["name"] for h in heroes}
# 从 prebanList 取一个 code 验证
pb = b0.get("prebanList") or []
print("\nprebanList codes:", pb, "-> names:", [hmap.get(c, "??") for c in pb if c])
