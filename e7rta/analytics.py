"""第七史诗 RTA 深度分析层。

提供：
- overview          总览 KPI + 属性/职业分布
- hero_stats       英雄榜（出场/ban/胜率）
- matchup          英雄克制关系（我方含A且敌方含B的胜率）
- pick_order_stats 选人位置(1-5)差异分析
- recommend        选人辅助（给定已选→推荐 counter + 该 ban）
- recent_matches / match_detail  对阵视图数据
- hero_catalog     英雄字典（前端搜索）

数据来源：e7rta/data.db（battles / battle_picks / battle_bans / heroes）
注意：e7stats 不记录先后手(first/second)，故"先后手差异"以 pick_order(1-5) 位置呈现。
"""
import sqlite3
import json
import os
import re
from collections import defaultdict, Counter

DB = "E:/第七史诗查询工具/e7rta/data.db"

ATTR_CN = {"fire": "火", "ice": "水", "wind": "风", "light": "光", "dark": "暗"}
JOB_CN = {
    "warrior": "战士", "knight": "骑士", "assassin": "刺客", "mage": "法师",
    "ranger": "游侠", "manauser": "术师", "material": "辅助",
}
# 属性克制：火>风>水>火（三角），光<->暗互克
ATTR_COUNTER = {"fire": "wind", "wind": "ice", "ice": "fire", "light": "dark", "dark": "light"}

_HEROES = None


def _conn():
    return sqlite3.connect(DB)


_HERO_STATIC = None


def hero_static():
    """官方静态英雄数据 {code: {rarity:int, attribute_cd, job_cd}}（373 个全有）。

    来源：紫龙 media.zlongame.com 的 epic7_hero.json（grade=天然星数 3/4/5，
    attribute_cd=fire/ice/wind/light/dark，job_cd=官方 6 职业）。
    本地缓存 data/hero_static.json；缓存存在则离线可用。"""
    global _HERO_STATIC
    if _HERO_STATIC is not None:
        return _HERO_STATIC
    fp = os.path.join(os.path.dirname(__file__), "data", "hero_static.json")
    if os.path.exists(fp):
        try:
            with open(fp, encoding="utf-8") as f:
                _HERO_STATIC = json.load(f)
            return _HERO_STATIC
        except Exception:
            pass
    out = {}
    try:
        import config
        d = config.fetch_static_json("epic7_hero.json")["zh-CN"]
        for h in d:
            out[h["code"]] = {
                "rarity": int(h.get("grade") or 0),
                "attribute_cd": h.get("attribute_cd") or "",
                "job_cd": h.get("job_cd") or "",
            }
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
    except Exception:
        out = {}
    _HERO_STATIC = out
    return out


def hero_map():
    global _HEROES
    if _HEROES is None:
        conn = _conn()
        _HEROES = {r[0]: r[1] for r in conn.execute("SELECT code, name FROM heroes")}
        conn.close()
    return _HEROES


def hname(code):
    return hero_map().get(code, code)


def attr_cn(c):
    return ATTR_CN.get(str(c), str(c))


def job_cn(c):
    return JOB_CN.get(str(c), str(c))


def _valid_season(s):
    return bool(re.match(r"^pvp_rta_ss\d+[a-z]?$", s or ""))


def _j(s):
    try:
        return json.loads(s) if s else []
    except Exception:
        return []


def _team(raw):
    try:
        arr = json.loads(raw)
    except Exception:
        arr = []
    arr = sorted(arr, key=lambda x: x.get("pick_order") or 99)
    return [{
        "code": x.get("hero_code"),
        "name": hname(x.get("hero_code")),
        "attr": attr_cn(x.get("attribute_cd")),
        "job": job_cn(x.get("job_cd")),
        "pick_order": x.get("pick_order"),
        "position": x.get("position"),
        "mvp": bool(x.get("mvp")),
        "attack": x.get("attack_damage"),
        "receive": x.get("receive_damage"),
        "artifact": x.get("artifact"),
    } for x in arr]


def load_battles(season=None):
    """返回 [(my_set, enemy_set, win), ...]，win=我方是否胜(0/1)。

    优化：直接从 battle_picks 表读取（已清洗过的 hero_code），
    避免 373k 场 × 2 次 json.loads() 的开销（之前要 20s）。
    """
    conn = _conn()
    if season and _valid_season(season):
        rows = conn.execute("""
            SELECT b.battle_seq, bp.side, bp.hero_code, b.is_win
            FROM battles b JOIN battle_picks bp ON b.battle_seq=bp.battle_seq
            WHERE b.season_code=?
        """, (season,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT b.battle_seq, bp.side, bp.hero_code, b.is_win
            FROM battles b JOIN battle_picks bp ON b.battle_seq=bp.battle_seq
        """).fetchall()
    conn.close()

    # 一次性 group by battle_seq
    out_map = {}
    for seq, side, code, win in rows:
        if seq not in out_map:
            out_map[seq] = (set(), set(), int(win or 0))
        if side == 'my':
            out_map[seq][0].add(code)
        elif side == 'enemy':
            out_map[seq][1].add(code)
    # 转 frozenset 以便 hash
    return [(frozenset(m), frozenset(e), w) for m, e, w in out_map.values()]


# ---------------------------------------------------------------------------
# 总览
# ---------------------------------------------------------------------------
def overview(season=None):
    conn = _conn()
    wc = "WHERE b.season_code=?" if (season and _valid_season(season)) else ""
    wv = (season,) if wc else ()
    total = conn.execute(f"SELECT COUNT(*) FROM battles {wc}", wv).fetchone()[0]
    wins = conn.execute(f"SELECT COUNT(*) FROM battles WHERE is_win=1 {wc}", wv).fetchone()[0]
    win_rate = round(100 * wins / total, 1) if total else 0

    picks = Counter(c for (c,) in conn.execute(
        f"SELECT bp.hero_code FROM battle_picks bp JOIN battles b ON bp.battle_seq=b.battle_seq "
        f"WHERE bp.side='my' {wc}", wv))
    bans = Counter(c for (c,) in conn.execute(
        f"SELECT bb.hero_code FROM battle_bans bb JOIN battles b ON bb.battle_seq=b.battle_seq "
        f"WHERE bb.side='my' {wc}", wv))

    attr = Counter(a for (a,) in conn.execute(
        f"SELECT bp.attribute_cd FROM battle_picks bp JOIN battles b ON bp.battle_seq=b.battle_seq "
        f"WHERE bp.side='my' {wc}", wv))
    job = Counter(j for (j,) in conn.execute(
        f"SELECT bp.job_cd FROM battle_picks bp JOIN battles b ON bp.battle_seq=b.battle_seq "
        f"WHERE bp.side='my' {wc}", wv))
    conn.close()

    total_pick = sum(picks.values()) or 1
    return {
        "total_battles": total,
        "win_rate": win_rate,
        "total_picks": total_pick,
        "total_bans": sum(bans.values()),
        "top_pick": [{"code": c, "name": hname(c), "n": n} for c, n in picks.most_common(6)],
        "top_ban": [{"code": c, "name": hname(c), "n": n} for c, n in bans.most_common(6)],
        "attr_dist": [{"name": attr_cn(a), "n": n} for a, n in attr.most_common()],
        "job_dist": [{"name": job_cn(j), "n": n} for j, n in job.most_common()],
    }


# ---------------------------------------------------------------------------
# 英雄榜
# ---------------------------------------------------------------------------
def hero_stats(season=None, min_games=15):
    conn = _conn()
    wc = " AND b.season_code=?" if (season and _valid_season(season)) else ""
    wv = (season,) if wc else ()
    rows = conn.execute(
        f"SELECT bp.hero_code, b.is_win FROM battle_picks bp "
        f"JOIN battles b ON bp.battle_seq=b.battle_seq WHERE bp.side='my' {wc}", wv).fetchall()
    picks = Counter()
    wins = Counter()
    for code, win in rows:
        picks[code] += 1
        if win:
            wins[code] += 1
    bans = Counter()
    for code, n in conn.execute(
        f"SELECT bb.hero_code, COUNT(*) FROM battle_bans bb "
        f"JOIN battles b ON bb.battle_seq=b.battle_seq WHERE bb.side='my' {wc} "
        f"GROUP BY bb.hero_code", wv).fetchall():
        bans[code] = n
    conn.close()
    total = sum(picks.values()) or 1
    total_ban = sum(bans.values()) or 1
    out = []
    for code in picks:
        g = picks[code]
        if g < min_games:
            continue
        out.append({
            "code": code, "name": hname(code),
            "picks": g, "wins": wins[code],
            "win_rate": round(100 * wins[code] / g, 1),
            "pick_rate": round(100 * g / total, 2),
            "ban_rate": round(100 * bans.get(code, 0) / total_ban, 2),
            "bans": bans.get(code, 0),
        })
    out.sort(key=lambda x: x["pick_rate"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# 克制关系
# ---------------------------------------------------------------------------
def matchup(hero_code, season=None, min_games=15):
    battles = load_battles(season)
    base = [b for b in battles if hero_code in b[0]]
    if not base:
        return {"base_win_rate": None, "games": 0, "counters": [], "countered_by": []}
    base_wins = sum(b[2] for b in base)
    base_wr = base_wins / len(base)
    stats = defaultdict(lambda: [0, 0])  # enemy_code -> [wins, games]
    for my, en, win in base:
        for e in en:
            stats[e][1] += 1
            if win:
                stats[e][0] += 1
    counters, countered = [], []
    for e, (w, g) in stats.items():
        if g < min_games:
            continue
        wr = w / g
        delta = wr - base_wr
        rec = {"code": e, "name": hname(e),
               "win_rate": round(100 * wr, 1), "games": g,
               "delta": round(100 * delta, 1)}
        (counters if delta >= 0 else countered).append(rec)
    counters.sort(key=lambda x: x["delta"], reverse=True)
    countered.sort(key=lambda x: x["delta"])
    return {
        "base_win_rate": round(100 * base_wr, 1),
        "games": len(base),
        "counters": counters[:15],
        "countered_by": countered[:15],
    }


# ---------------------------------------------------------------------------
# 选人位置差异（pick_order 1-5）
# ---------------------------------------------------------------------------
def pick_order_stats(season=None):
    conn = _conn()
    wc = " AND b.season_code=?" if (season and _valid_season(season)) else ""
    wv = (season,) if wc else ()
    rows = conn.execute(
        f"SELECT bp.pick_order, bp.attribute_cd, bp.job_cd, b.is_win, bp.hero_code "
        f"FROM battle_picks bp JOIN battles b ON bp.battle_seq=b.battle_seq "
        f"WHERE bp.side='my' {wc}", wv).fetchall()
    conn.close()
    res = {}
    for po, attr, job, win, code in rows:
        d = res.setdefault(po, {"count": 0, "wins": 0, "attrs": Counter(), "jobs": Counter(), "heroes": Counter()})
        d["count"] += 1
        if win:
            d["wins"] += 1
        d["attrs"][attr] += 1
        d["jobs"][job] += 1
        d["heroes"][code] += 1
    out = []
    for po in sorted(res):
        d = res[po]
        out.append({
            "pick_order": po,
            "count": d["count"],
            "win_rate": round(100 * d["wins"] / d["count"], 1),
            "top_attrs": [{"name": attr_cn(a), "n": n} for a, n in d["attrs"].most_common(5)],
            "top_jobs": [{"name": job_cn(j), "n": n} for j, n in d["jobs"].most_common(5)],
            "top_heroes": [{"code": c, "name": hname(c), "n": n} for c, n in d["heroes"].most_common(5)],
        })
    return out


# ---------------------------------------------------------------------------
# 选人辅助
# ---------------------------------------------------------------------------
def recommend(my_picks, enemy_picks=None, enemy_bans=None, season=None, top_n=12):
    battles = load_battles(season)
    enemy_picks = set(enemy_picks or [])
    enemy_bans = set(enemy_bans or [])
    n_total = len(battles) or 1

    hero_games = Counter()
    hero_wins = Counter()
    enemy_games = Counter()   # 敌方含 e 时（我方胜率视角）
    enemy_wins = Counter()
    pair = defaultdict(lambda: [0, 0])  # (my_c, enemy_e) -> [wins, games]
    for my, en, win in battles:
        for c in my:
            hero_games[c] += 1
            if win:
                hero_wins[c] += 1
        for e in en:
            enemy_games[e] += 1
            if win:
                enemy_wins[e] += 1
        for c in my:
            for e in en:
                pair[(c, e)][1] += 1
                if win:
                    pair[(c, e)][0] += 1

    # 推荐 pick：候选 = 出场过且不在已选/已ban
    candidates = set(hero_games) - set(my_picks) - enemy_bans
    picks = []
    for c in candidates:
        g = hero_games[c]
        if g < 15:
            continue
        self_wr = hero_wins[c] / g
        if enemy_picks:
            scores = []
            for e in enemy_picks:
                w_, g_ = pair.get((c, e), (0, 0))
                if g_ > 0:
                    scores.append(w_ / g_)
            counter = sum(scores) / len(scores) if scores else self_wr
        else:
            counter = self_wr
        score = 0.45 * self_wr + 0.55 * counter
        picks.append({
            "code": c, "name": hname(c),
            "self_win_rate": round(100 * self_wr, 1),
            "counter_score": round(100 * counter, 1),
            "games": g, "score": round(score, 1),
        })
    picks.sort(key=lambda x: x["score"], reverse=True)
    picks = picks[:top_n]

    # 推荐 ban：敌方含 c 时我方胜率越低 + 出场越高 → 越该 ban
    bans = []
    for c in enemy_games:
        if c in enemy_bans or c in enemy_picks or c in my_picks:
            continue
        g = enemy_games[c]
        if g < 20:
            continue
        threat_wr = enemy_wins[c] / g
        pick_rate = g / n_total * 100
        ban_score = (100 - 100 * threat_wr) * 0.6 + pick_rate * 0.4
        bans.append({
            "code": c, "name": hname(c),
            "threat_win_rate": round(100 * threat_wr, 1),
            "games": g, "ban_score": round(ban_score, 1),
        })
    bans.sort(key=lambda x: x["ban_score"], reverse=True)
    bans = bans[:top_n]

    return {"picks": picks, "bans": bans}


# ---------------------------------------------------------------------------
# 对阵视图
# ---------------------------------------------------------------------------
def recent_matches(limit=30, season=None):
    conn = _conn()
    if season and _valid_season(season):
        rows = conn.execute(
            "SELECT battle_seq, is_win, season_code, my_team, enemy_team, preban_list, "
            "preban_enemy, turn, battle_time FROM battles WHERE season_code=? "
            "ORDER BY rowid DESC LIMIT ?", (season, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT battle_seq, is_win, season_code, my_team, enemy_team, preban_list, "
            "preban_enemy, turn, battle_time FROM battles ORDER BY rowid DESC LIMIT ?",
            (limit,)).fetchall()
    conn.close()
    out = []
    for seq, win, sc, my, en, pb, pbe, turn, bt in rows:
        out.append({
            "seq": seq, "is_win": bool(win), "season": sc, "turn": turn, "time": bt,
            "my": _team(my), "enemy": _team(en),
            "my_ban": _j(pb), "enemy_ban": _j(pbe),
        })
    return out


def match_detail(seq):
    conn = _conn()
    row = conn.execute(
        "SELECT is_win, season_code, my_team, enemy_team, preban_list, preban_enemy, "
        "turn, battle_time FROM battles WHERE battle_seq=?", (seq,)).fetchone()
    conn.close()
    if not row:
        return None
    win, sc, my, en, pb, pbe, turn, bt = row
    return {
        "seq": seq, "is_win": bool(win), "season": sc, "turn": turn, "time": bt,
        "my": _team(my), "enemy": _team(en),
        "my_ban": _j(pb), "enemy_ban": _j(pbe),
    }


# ---------------------------------------------------------------------------
# 英雄字典（前端搜索）
# ---------------------------------------------------------------------------
def hero_catalog():
    """返回完整英雄字典（全部 373 个），供前端搜索/筛选。

    星数(rarity)/属性/职业以官方 epic7_hero.json（hero_static）为准——
    373 个全部有值；battle_picks 仅作离线兜底（无官方缓存时）。
    """
    conn = _conn()
    static = hero_static()
    bp = {}
    for code, a, j in conn.execute(
            "SELECT hero_code, attribute_cd, job_cd FROM battle_picks"):
        cur = bp.get(code)
        if cur is None:
            bp[code] = [a, j]
        else:
            if not cur[0] and a:
                cur[0] = a
            if not cur[1] and j:
                cur[1] = j
    rows = conn.execute("SELECT code, name FROM heroes").fetchall()
    conn.close()
    out = []
    seen = set()
    for code, name in rows:
        if code in seen:
            continue
        seen.add(code)
        st = static.get(code) or {}
        a = st.get("attribute_cd") or bp.get(code, [None, None])[0] or ""
        j = st.get("job_cd") or bp.get(code, [None, None])[1] or ""
        out.append({
            "code": code,
            "name": name or code,
            "attr": attr_cn(a) if a else "",
            "attr_raw": a,
            "job": job_cn(j) if j else "",
            "job_raw": j,
            "rarity": st.get("rarity") or 0,
        })
    out.sort(key=lambda x: x["name"])
    return out


if __name__ == "__main__":
    import pprint
    print("=== overview ===")
    pprint.pprint(overview())
    print("\n=== pick_order_stats ===")
    pprint.pprint(pick_order_stats())
    print("\n=== matchup(组长亚露嘉 c2124) ===")
    pprint.pprint(matchup("c2124"))
    print("\n=== recommend(['c2124']) ===")
    pprint.pprint(recommend(["c2124"]))
