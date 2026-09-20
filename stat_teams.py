import urllib.request, json, time

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
base = "https://e7stats.qyzlgame.com"

def post(nick_no, season=""):
    q = f"nick_no={nick_no}&world_code=world_zlong1&lang=zh-CN&season_code={season}"
    h = {"User-Agent": UA, "Referer": base + "/", "Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(base + "/gameApi/getBattleList", data=q.encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def get_users():
    req = urllib.request.Request("https://media.zlongame.com/media/pictures/qy/e7/actv/2023/Epic7_Stats/json/epic7_user_world_cn.json?_=1", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))["users"]

users = get_users()
hit = []
for u in users[:300]:
    try:
        j = post(u["nick_no"])
        bl = (j.get("result_body") or {}).get("battle_list")
        if bl:
            hit.append((u["nick_no"], u["nick_nm"], bl))
            if len(hit) >= 6: break
    except Exception as e:
        pass
    time.sleep(0.05)

print(f"找到 {len(hit)} 个有战绩玩家\n")
total_battles = 0
nonempty_team = 0
nonempty_hero = 0
nonempty_pb = 0
first_season = None
for nick_no, nm, bl in hit:
    b0 = bl[0]
    if first_season is None:
        first_season = (b0.get("season_code"), b0.get("season_name"))
    # 统计该玩家前 10 场
    for b in bl[:10]:
        total_battles += 1
        try:
            tb = json.loads("{" + b["teamBettleInfo"] + "}")
            if tb.get("my_team"): nonempty_team += 1
        except Exception:
            pass
        md = b.get("my_deck") or {}
        if md.get("hero_list"): nonempty_hero += 1
        pb = b.get("prebanList")
        if pb:
            try:
                if json.loads("{" + pb + "}").get("preban_list"): nonempty_pb += 1
            except Exception: pass
    print(f"{nm} ({nick_no}): {len(bl)} 场 | 首场 season={b0.get('season_code')} season_name={b0.get('season_name')}")

print(f"\n=== 前 {total_battles} 场统计 ===")
print(f"my_team 非空: {nonempty_team}/{total_battles}")
print(f"my_deck.hero_list 非空: {nonempty_hero}/{total_battles}")
print(f"prebanList 非空: {nonempty_pb}/{total_battles}")

# 用真实 season_code 重试第一个玩家
if first_season and first_season[0]:
    sc = first_season[0]
    print(f"\n用真实 season_code={sc} 重试 {hit[0][1]}...")
    j2 = post(hit[0][0], sc)
    bl2 = (j2.get("result_body") or {}).get("battle_list") or []
    ne = 0
    for b in bl2[:10]:
        try:
            if json.loads("{" + b["teamBettleInfo"] + "}").get("my_team"): ne += 1
        except Exception: pass
    print(f"  带 season_code 后: {len(bl2)} 场, my_team 非空 {ne}/{min(10,len(bl2))}")
