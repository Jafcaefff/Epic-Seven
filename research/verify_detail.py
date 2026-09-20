import urllib.request, json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
BASE = "https://e7stats.qyzlgame.com"

def post(path, params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    h = {"User-Agent": UA, "Referer": BASE + "/", "Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(BASE + "/gameApi/" + path, data=q.encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def parse_str(s):
    return json.loads("{" + s + "}")

# 取一个有阵容的玩家（彩之风 ss20）的 battle_seq
bl = post("getBattleList", {"nick_no": "1100116050698", "world_code": "world_zlong1", "lang": "zh-CN", "season_code": "pvp_rta_ss20"})["result_body"]["battle_list"]
target = None
for b in bl:
    try:
        if parse_str(b["teamBettleInfo"]).get("my_team"):
            target = b["battle_seq"]; break
    except Exception: pass
print("选中的 battle_seq:", target)

d = post("getBattleDetail", {"nick_no": "1100116050698", "world_code": "world_zlong1", "lang": "zh-CN", "season_code": "pvp_rta_ss20", "battle_seq": target})["result_body"]
print("getBattleDetail keys:", list(d.keys()))

print("\n=== energy_gauge (前3) ===")
print(json.dumps(d.get("energy_gauge")[:3], ensure_ascii=False, indent=1))

print("\n=== turn_list 类型/长度 ===")
tl = d.get("turn_list")
print("type:", type(tl), "len:", len(tl) if isinstance(tl, list) else "n/a")
if isinstance(tl, list) and tl:
    print("turn_list[0]:", json.dumps(tl[0], ensure_ascii=False)[:800])
    # 收集 turn_list 元素字段
    keys = set()
    def collect(o):
        if isinstance(o, dict):
            keys.update(o.keys())
            for v in o.values(): collect(v)
        elif isinstance(o, list):
            for v in o: collect(v)
    for x in tl: collect(x)
    print("turn_list 元素字段:", sorted(keys))

print("\n=== teamBettleInfo my_team[0] ===")
tb = parse_str(d["teamBettleInfo"]).get("my_team", [])
print(json.dumps(tb[0] if tb else {}, ensure_ascii=False, indent=1)[:500])
