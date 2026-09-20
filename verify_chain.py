import urllib.request, re, json, time

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
base = "https://e7stats.qyzlgame.com"

def fetch(url, data=None, headers=None, method=None):
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers: h.update(headers)
    m = method or ("POST" if data is not None else "GET")
    req = urllib.request.Request(url, data=data, headers=h, method=m)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.headers.get("Content-Type"), r.read()

# 1) 取真实用户
s, ct, b = fetch("https://media.zlongame.com/media/pictures/qy/e7/actv/2023/Epic7_Stats/json/epic7_user_world_cn.json?_=1")
users = json.loads(b.decode("utf-8"))["users"]
print("users:", len(users), "| first sample:", users[0])

# 2) 取英雄表
s, ct, b = fetch("https://media.zlongame.com/media/pictures/qy/e7/actv/2023/Epic7_Stats/json/epic7_hero.json?_=1")
heroes = json.loads(b.decode("utf-8"))["zh-CN"]
hero_map = {h["code"]: h["name"] for h in heroes}
print("heroes:", len(hero_map))

# 3) 用前几个真实 nick_no 探测 battle_list，直到拿到非空
found = None
for u in users[:50]:
    nick_no = str(u.get("nick_no"))
    nick_nm = u.get("nick_nm")
    q = f"nick_no={nick_no}&world_code=world_zlong1&lang=zh-CN&season_code="
    s, ct, b = fetch(base + "/gameApi/getBattleList", data=q.encode(),
                     headers={"Referer": base + "/", "Content-Type": "application/x-www-form-urlencoded"})
    j = json.loads(b.decode("utf-8"))
    bl = (j.get("result_body") or {}).get("battle_list")
    if bl:
        found = (nick_no, nick_nm, bl)
        print(f"HIT {nick_nm} ({nick_no}) battle_list len={len(bl)}")
        break
    time.sleep(0.1)

if not found:
    print("前50个用户均无战绩，未能拿到非空 battle_list（接口链路 OK，只是这些号没数据）")
else:
    nick_no, nick_nm, bl = found
    b0 = bl[0]
    print("\n=== 第一条 battle 字段（验证代码解析兼容性）===")
    print("顶层 keys:", list(b0.keys()))
    print("battle_seq:", b0.get("battle_seq"), "| battle_day:", b0.get("battle_day"),
          "| iswin:", b0.get("iswin"), "| turn:", b0.get("turn"), "| battle_time:", b0.get("battle_time"))
    md = b0.get("my_deck", {})
    ed = b0.get("enemy_deck", {})
    print("my_deck.hero_list len:", len(md.get("hero_list", [])), "| my preban_list:", md.get("preban_list"))
    print("enemy_deck.hero_list len:", len(ed.get("hero_list", [])), "| enemy preban_list:", ed.get("preban_list"))
    # 验证英雄 code 能否在 hero_map 命中
    h = md.get("hero_list", [{}])[0]
    print("my hero[0]:", h, "-> name:", hero_map.get(h.get("hero_code"), "NOT FOUND"))
    print("\n结论：接口存活 + 数据结构与原代码解析逻辑一致，仅需修正调用方式（POST body + Referer）。")
