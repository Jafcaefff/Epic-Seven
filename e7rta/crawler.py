"""对局批量抓取：遍历玩家 × 目标赛季，调 getBattleList，解析阵容/ban 位并落库。"""
import json
import re
import time
from datetime import datetime, timezone

import config
import db


def _now():
    return datetime.now(timezone.utc).isoformat()


def _wrap_load(raw, key):
    """紫龙后端 bug：teamBettleInfo/prebanList 字段是缺外层花括号的片段
    （如 '"my_team":[...]'），需包裹成对象再解析。兼容正常 JSON / 对象两种情况。"""
    if raw is None:
        return []
    if isinstance(raw, str):
        s = raw.strip()
        if not s.startswith("{"):
            s = "{" + s + "}"
        try:
            return json.loads(s).get(key, []) or []
        except (json.JSONDecodeError, AttributeError):
            return []
    if isinstance(raw, dict):
        return raw.get(key, []) or []
    return []


def _parse_team(raw):
    """返回 my_team 列表（我方/敌方字段内 key 均为 my_team）。"""
    return _wrap_load(raw, "my_team")


def _parse_preban(raw):
    return _wrap_load(raw, "preban_list")


def _battle_list(resp):
    rb = resp.get("result_body") if isinstance(resp, dict) else None
    if isinstance(rb, dict) and isinstance(rb.get("battle_list"), list):
        return rb["battle_list"]

    def f(d):
        if isinstance(d, dict):
            for k, v in d.items():
                if k == "battle_list" and isinstance(v, list):
                    return v
                r = f(v)
                if r is not None:
                    return r
        return None

    return f(resp) or []


def crawl_player(conn, nick_no, season=None):
    """抓取单个玩家对局并落库。
    season=None -> 本地过滤 ss17+（每玩家 API 封顶 100 场，跨赛季混合）；
    season='pvp_rta_ssXX' -> API 精准返回该赛季，落库即该赛季（DB 最小）。
    每玩家仅 1 次 API 调用。返回落库对局数。"""
    min_n = int(config.MIN_SEASON[2:])  # 'ss17' -> 17
    try:
        resp = config.get_battle_list(nick_no, season)
    except Exception:  # noqa: BLE001
        return 0
    bl = _battle_list(resp)
    if not bl:
        return 0
    total = 0
    for b in bl:
        sc = b.get("season_code") or ""
        if season:
            # 精准赛季：API 已过滤，仍校验一致性
            if sc != season:
                continue
        else:
            m = re.search(r"ss(\d+)", sc)
            if not m or int(m.group(1)) < min_n:
                continue
        seq = str(b.get("battle_seq"))
        if not seq:
            continue
        my_team_raw = b.get("teamBettleInfo")
        enemy_team_raw = b.get("teamBettleInfoenemy")
        preban_raw = b.get("prebanList")
        preban_enemy_raw = b.get("prebanListEnemy")
        my_team = _parse_team(my_team_raw)
        enemy_team = _parse_team(enemy_team_raw)
        preban = _parse_preban(preban_raw)
        preban_enemy = _parse_preban(preban_enemy_raw)
        rec = {
            "battle_seq": seq,
            "nick_no": int(nick_no),
            "season_code": b.get("season_code"),
            "season_name": b.get("season_name"),
            "is_win": 1 if db._i(b.get("iswin")) == 2 else 0,  # 紫龙: 2=胜 1=负
            "turn": db._i(b.get("turn")),
            "battle_time": db._i(b.get("battle_time")),
            "battle_day": b.get("battle_day"),
            "my_team": json.dumps(my_team, ensure_ascii=False),
            "enemy_team": json.dumps(enemy_team, ensure_ascii=False),
            "preban_list": json.dumps(preban, ensure_ascii=False),
            "preban_enemy": json.dumps(preban_enemy, ensure_ascii=False),
                "raw_team": my_team_raw if isinstance(my_team_raw, str) else json.dumps(my_team_raw, ensure_ascii=False),
                "raw_preban": preban_raw if isinstance(preban_raw, str) else json.dumps(preban_raw, ensure_ascii=False),
                "raw_enemy_team": enemy_team_raw if isinstance(enemy_team_raw, str) else json.dumps(enemy_team_raw, ensure_ascii=False),
                "raw_enemy_preban": preban_enemy_raw if isinstance(preban_enemy_raw, str) else json.dumps(preban_enemy_raw, ensure_ascii=False),
            "my_team_parsed": my_team,
            "enemy_team_parsed": enemy_team,
            "preban_parsed": preban,
            "preban_enemy_parsed": preban_enemy,
            "fetched_at": _now(),
        }
        db.upsert_battle(conn, rec)
        total += 1
    conn.commit()
    time.sleep(config.REQUEST_INTERVAL)
    return total
