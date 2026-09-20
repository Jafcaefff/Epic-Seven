"""静态数据导入：玩家 / 英雄 / 装备 / 赛季。"""
import re
import config


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def import_static(conn):
    """从 CDN JSON 导入玩家、英雄、装备映射。返回 (玩家数, 英雄数, 装备数)。"""
    users = config.fetch_static_json("epic7_user_world_cn.json")["users"]
    conn.executemany(
        "INSERT OR IGNORE INTO players (nick_no, nick_nm, rank, code) VALUES (?,?,?,?)",
        [(int(u["nick_no"]), u.get("nick_nm"), _i(u.get("rank")), u.get("code")) for u in users],
    )
    conn.commit()

    heroes = config.fetch_static_json("epic7_hero.json")["zh-CN"]
    conn.executemany(
        "INSERT OR IGNORE INTO heroes (code, name) VALUES (?,?)",
        [(h["code"], h.get("name")) for h in heroes],
    )
    conn.commit()

    equips = config.fetch_static_json("epic7_equip.json")["zh-CN"]
    conn.executemany(
        "INSERT OR IGNORE INTO equips (code, name) VALUES (?,?)",
        [(e["code"], e.get("name")) for e in equips],
    )
    conn.commit()
    return len(users), len(heroes), len(equips)


def _find_seasons(d):
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, list) and v and isinstance(v[0], dict) and "season_code" in v[0]:
                return v
            r = _find_seasons(v)
            if r:
                return r
    return None


def import_seasons(conn):
    """从 getSeasonList 导入赛季表，返回目标赛季列表（ss17 及以后）。"""
    sl = config.get_season_list()
    seasons = _find_seasons(sl) or []
    conn.executemany(
        "INSERT OR REPLACE INTO seasons (season_code, season_name, start_date, end_date, is_now) VALUES (?,?,?,?,?)",
        [
            (s["season_code"], s.get("name"), s.get("startDate"), s.get("endDate"), s.get("is_now_season", 0))
            for s in seasons
        ],
    )
    conn.commit()
    target = []
    for s in seasons:
        m = re.search(r"ss(\d+)", s["season_code"])
        if m and int(m.group(1)) >= 17:
            target.append(s["season_code"])
    return sorted(target)
