import urllib.request, json, time

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
BASE = "https://e7stats.qyzlgame.com"

def post(nick_no, season=""):
    q = f"nick_no={nick_no}&world_code=world_zlong1&lang=zh-CN&season_code={season}"
    h = {"User-Agent": UA, "Referer": BASE + "/", "Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(BASE + "/gameApi/getBattleList", data=q.encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))

def get_users():
    req = urllib.request.Request("https://media.zlongame.com/media/pictures/qy/e7/actv/2023/Epic7_Stats/json/epic7_user_world_cn.json?_=1", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))["users"]

def parse_str(s):
    return json.loads("{" + s + "}")

users = get_users()
hit = []
for u in users[:400]:
    try:
        j = post(u["nick_no"])
        bl = (j.get("result_body") or {}).get("battle_list")
        if bl:
            hit.append((u["nick_no"], u["nick_nm"], bl))
            if len(hit) >= 8: break
    except Exception:
        pass
    time.sleep(0.05)

print(f"找到 {len(hit)} 个有战绩玩家\n")
# 各赛季阵容完整度 + dump my_team 结构
sample_dumped = False
for nick_no, nm, bl in hit:
    b0 = bl[0]
    season = b0.get("season_code")
    nonempty = 0
    pb_nonempty = 0
    for b in bl:
        try:
            if parse_str(b["teamBettleInfo"]).get("my_team"): nonempty += 1
        except Exception: pass
        pb = b.get("prebanList")
        if pb:
            try:
                if parse_str(pb).get("preban_list"): pb_nonempty += 1
            except Exception: pass
        if not sample_dumped and nonempty > 0:
            # dump 第一场有阵容的对局
            for b in bl:
                try:
                    tb = parse_str(b["teamBettleInfo"])["my_team"]
                    if tb:
                        print(f"\n=== 样例（{nm}, season={season}）my_team[0] ===")
                        print(json.dumps(tb[0], ensure_ascii=False)[:400])
                        keys = set()
                        def collect(o):
                            if isinstance(o, dict):
                                keys.update(o.keys())
                                for v in o.values(): collect(v)
                            elif isinstance(o, list):
                                for v in o: collect(v)
                        for x in tb: collect(x)
                        print("my_team 元素字段:", sorted(keys))
                        # enemy
                        tbe = parse_str(b["teamBettleInfoenemy"]).get("my_team", [])
                        if tbe:
                            print("enemy my_team[0]:", json.dumps(tbe[0], ensure_ascii=False)[:400])
                        print("prebanList:", parse_str(b["prebanList"]))
                        print("prebanListEnemy:", parse_str(b["prebanListEnemy"]))
                        sample_dumped = True
                        break
                except Exception: pass
    print(f"{nm} ({nick_no}): {len(bl)}场 | season={season} | my_team非空 {nonempty}/{len(bl)} | preban非空 {pb_nonempty}/{len(bl)}")
