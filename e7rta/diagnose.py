"""一次性诊断：确认 season / battle / hero / equip 的真实结构。"""
import sys, json
sys.path.insert(0, r"E:/第七史诗查询工具/e7rta")
import config


def find_list(d):
    if isinstance(d, dict):
        for k, v in d.items():
            if k == "battle_list" and isinstance(v, list):
                return v
            r = find_list(v)
            if r is not None:
                return r
    return None


def find_seasons(d):
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, list) and v and isinstance(v[0], dict) and (
                "season_code" in v[0] or "season_name" in v[0]
            ):
                return v
            r = find_seasons(v)
            if r:
                return r
    return None


print("=== getSeasonList ===")
sl = config.get_season_list()
print("top keys:", list(sl.keys()) if isinstance(sl, dict) else type(sl))
seasons = find_seasons(sl) or []
print("seasons found:", len(seasons))
for s in seasons:
    print("  ", s)
print("last:", seasons[-1] if seasons else None)

print("\n=== players sample ===")
users = config.fetch_static_json("epic7_user_world_cn.json")["users"]
print("users:", len(users), "sample:", users[0])

test_no = None
for u in users[:80]:
    try:
        r = config.get_battle_list(u["nick_no"])
        bl = find_list(r)
        if bl:
            test_no = u["nick_no"]
            print("found battles for", test_no, "unfiltered len", len(bl))
            break
    except Exception:
        pass
print("test_no:", test_no)

if test_no is not None:
    r = config.get_battle_list(test_no)
    bl = find_list(r)
    b = bl[0]
    print("battle keys:", list(b.keys()))
    print("season_code:", b.get("season_code"), "name:", b.get("season_name"))
    sc = b["season_code"]
    r2 = config.get_battle_list(test_no, sc)
    bl2 = find_list(r2)
    print("filtered by", sc, "-> len", len(bl2) if bl2 else 0)
    dist = {}
    for x in bl:
        dist[x.get("season_code")] = dist.get(x.get("season_code"), 0) + 1
    print("season dist (unfiltered top):", dict(list(dist.items())[:8]))

print("\n=== hero structure ===")
heroes = config.fetch_static_json("epic7_hero.json")["zh-CN"]
print("type:", type(heroes), "len:", len(heroes) if hasattr(heroes, "__len__") else "?")
print("sample:", heroes[:2] if isinstance(heroes, list) else list(heroes.items())[:2])

print("\n=== equip structure ===")
equips = config.fetch_static_json("epic7_equip.json")["zh-CN"]
print("type:", type(equips), "len:", len(equips) if hasattr(equips, "__len__") else "?")
print("sample:", equips[:3] if isinstance(equips, list) else list(equips.items())[:3])
