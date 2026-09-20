import urllib.request, json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
BASE = "https://e7stats.qyzlgame.com"

def post(path, params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    h = {"User-Agent": UA, "Referer": BASE + "/", "Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(BASE + "/gameApi/" + path, data=q.encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

# 1) 赛季列表
print("=== getSeasonList ===")
sl = post("getSeasonList", {"lang": "zh-CN"})["result_body"]
print(f"赛季数: {len(sl)}")
for s in sl[:40]:
    print(f"  {s.get('season_code')} | {s.get('season_name')} | {s.get('startDate')} ~ {s.get('endDate')} | grade={s.get('grade_code')}")

# 2) 用户信息
print("\n=== getUserInfo ===")
ui = post("getUserInfo", {"nick_no": "1100111328105", "world_code": "world_zlong1", "lang": "zh-CN"})["result_body"]
print(json.dumps(ui, ensure_ascii=False, indent=1)[:1500])

# 3) getBattleDetail
print("\n=== getBattleDetail 尝试 ===")
bl = post("getBattleList", {"nick_no": "1100111328105", "world_code": "world_zlong1", "lang": "zh-CN", "season_code": ""})["result_body"]["battle_list"]
b0 = bl[0]
print("用 battle_seq=", b0["battle_seq"])
for extra in [{}, {"nick_no": "1100111328105"}]:
    params = {"battle_seq": b0["battle_seq"], "world_code": "world_zlong1", "lang": "zh-CN", "season_code": ""}
    params.update(extra)
    try:
        d = post("getBattleDetail", params)["result_body"]
        print(f"  附加参数{extra} -> keys={list(d.keys()) if isinstance(d, dict) else type(d)}")
        if isinstance(d, dict):
            print("   ", json.dumps(d, ensure_ascii=False)[:600])
    except Exception as e:
        print("  err:", e)
