"""第七史诗 RTA BP 模拟器 — 有状态选人/ban 推荐引擎。

核心能力：
- rta_steps(hand, preban_count): 生成真实对局顺序
    先手/后手 → pre-ban(各1,大师+2) → pick 1-2-2-2-2-1 → post-ban(各1,第3选保护)
- suggest(state): 根据当前盘面（双方已选/已ban、当前阶段）给出
    - my_picks: 我方该选谁（克制敌方当前阵容 + 自身强度 + 与我方配合）
    - my_bans:  我方该 ban 谁（对当前盘面威胁最大 + 版本强势）
    - enemy_picks: 模拟对手很可能选的（用于"对手选人"自动模拟）

真实 RTA 规则（已核实，来源 hideoutgacha + 国服 wiki）：
- 抛硬币定先手/后手
- Pre-ban：双方各 ban 1（大师及以上 ban 2），整场不可用
- Pick 顺序 1-2-2-2-2-1：先手先选 1，后手选 2，交替，各 5 人
- Post-ban：10 人全选完后双方各 ban 对手 1 名，各自第 3 选(pick_order=3)受保护 → 4v4
注意：e7stats 不记录先后手，模拟器由用户选定先手/后手后严格按真实顺序走。
"""
import sqlite3
import json
import os
import sys
import time
import pickle
import itertools
from collections import Counter, defaultdict
from pathlib import Path

import analytics as A

DB = A.DB


def _pair_default():
    """named function 让 defaultdict 可 pickle（lambda 不可 pickle）。"""
    return [0, 0]

_META_PREBAN = None
_META_PREBAN_MAX = 90.88   # 归一化上限（meta preban 榜首值）

_POS_CACHE = {}   # season -> {"by": {(order,code):[wins,games]}, "tot": {order: games}}
_AGG_CACHE = {}    # season -> {"n_total", "hero_games", "hero_wins", "enemy_games", "enemy_wins", "pair", "syn"}
_LINEUP_CACHE = {} # season -> {"n", "win", "my": {code: bitmask}, "en": {code: bitmask}}
_LINEUP_CACHE = {}  # season -> {"n":场数, "win":胜局掩码, "my":{code:掩码}, "en":{code:掩码}}

# 分层对位估计参数
LINEUP_MIN_GAMES = 25    # 阵容级样本门槛：某子集不足 25 场就降一级（全员→…→2人核心）
LINEUP_PRIOR_K = 60.0    # 阵容级估计的先验强度：权重 w = g/(g+60)，60 场时与单体估计各占一半

import pickle as _pickle
_PICKLE_DIR = Path(os.environ.get("E7RTA_CACHE", "E:/第七史诗查询工具/e7rta/.cache"))
_PICKLE_DIR.mkdir(exist_ok=True)


def _pickle_load(key):
    p = _PICKLE_DIR / f"{key}.pkl"
    if p.exists() and (time.time() - p.stat().st_mtime) < 86400 * 7:  # 7天有效
        try:
            with open(p, "rb") as f:
                return _pickle.load(f)
        except Exception:
            return None
    return None


def _pickle_save(key, obj):
    try:
        with open(_PICKLE_DIR / f"{key}.pkl", "wb") as f:
            _pickle.dump(obj, f, protocol=_pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass


def _lineup_index(season):
    """对局位掩码索引：每场对局占 1 个 bit。

    my[code] = 我方含该英雄的对局掩码；en[code] = 敌方含该英雄的掩码；win = 我方获胜的掩码。
    于是「某几个敌方英雄同时在场 且 我方含候选英雄」的样本数 = popcount(掩码AND)，
    胜率 = popcount(掩码AND & win) / 样本数 —— 一次位运算即得阵容级对位胜率，
    393 个候选 × 31 个子集也只要毫秒级（实测建索引 1.3s，之后缓存复用）。
    按 season 缓存 + 磁盘 pickle 持久化（7 天有效，重启秒启）。"""
    cache_key = f"lineup_{season}"
    pkl = _pickle_load(cache_key)
    if pkl:
        _LINEUP_CACHE[season] = pkl
        return pkl
    if season in _LINEUP_CACHE:
        return _LINEUP_CACHE[season]
    conn = sqlite3.connect(DB)
    if season and A._valid_season(season):
        rows = conn.execute(
            "SELECT battle_seq, is_win FROM battles WHERE season_code=?", (season,)).fetchall()
    else:
        rows = conn.execute("SELECT battle_seq, is_win FROM battles").fetchall()
    idx = {seq: i for i, (seq, _) in enumerate(rows)}
    win = 0
    for seq, w in rows:
        if w == 1:
            win |= 1 << idx[seq]
    my, en = {}, {}
    for seq, side, code in conn.execute(
            "SELECT battle_seq, side, hero_code FROM battle_picks"):
        i = idx.get(seq)
        if i is None:
            continue
        d = my if side == "my" else en
        d[code] = d.get(code, 0) | (1 << i)
    conn.close()
    out = {"n": len(rows), "win": win, "my": my, "en": en}
    _LINEUP_CACHE[season] = out
    _pickle_save(cache_key, out)
    return out


def _lineup_matchup(cand, foe_picks, idx, side="me", min_games=LINEUP_MIN_GAMES):
    """阵容级对位：候选英雄 vs 敌方已选全员（或最大可行子集）的历史胜率。

    side='me'：cand 在我方、foe_picks 是敌方已选；side='enemy' 反之（敌方视角胜=我方败）。
    样本随人数指数衰减，故从「全员同时在场」起逐级降规模（k → k-1 → … → 2 人核心），
    每级取样本量最大的子集，达到 min_games 即采用。
    返回 None 表示连 2 人核心都不足门槛 → 调用方降级到单体对位。"""
    if not foe_picks:
        return None
    cand_mask = (idx["my"] if side == "me" else idx["en"]).get(cand, 0)
    if not cand_mask:
        return None
    foe_map = idx["en"] if side == "me" else idx["my"]
    win_mask = idx["win"]
    if side == "enemy":
        win_mask = ((1 << idx["n"]) - 1) ^ idx["win"]   # 敌方视角的「胜」= 我方败
    codes = [c for c in foe_picks if foe_map.get(c)]
    if not codes:
        return None
    for k in range(min(len(codes), 5), 1, -1):
        best = None
        for sub in itertools.combinations(codes, k):
            m = cand_mask
            for c in sub:
                m &= foe_map[c]
                if not m:
                    break
            g = m.bit_count()
            if best is None or g > best[0]:
                best = (g, sub, m)
        if best and best[0] >= min_games:
            g, sub, m = best
            w = (m & win_mask).bit_count()
            return {"size": k, "games": g, "wins": w, "wr": w / g,
                    "heroes": list(sub)}
    return None


def _pair_estimate(cand, foe_picks, pair, MU, K, side="me"):
    """单体对位（降级层）：候选英雄对每个敌方英雄的历史胜率，按样本量加权平均。
    side='enemy' 时 pair 键序反转（pair[(my,enemy)] 记的是我方视角胜场）。"""
    vals = []
    for e in foe_picks:
        w, g = pair[(cand, e)] if side == "me" else pair[(e, cand)]
        if g <= 0:
            continue
        wr = _shrunk(w, g, MU, K)
        if side == "enemy":
            wr = 1 - wr
        vals.append((wr, g))
    if not vals:
        return None
    tot = sum(g for _, g in vals)
    return sum(wr * g for wr, g in vals) / tot, tot


def _counter_estimate(cand, foe_picks, pair, MU, K, idx, side="me"):
    """分层对位估计（阵容级优先，样本不足自动降级）：
      ① 阵容级：候选 vs 敌方已选全员/最大子集（样本门槛 25 场）
      ② 单体对位：候选 vs 每个敌方英雄，按样本加权
      ③ 都没有 → None，调用方退回「自身强度 + 该选位胜率」兜底
    有阵容级样本时按 w = g/(g+60) 与单体估计混合，避免子集规模跳变时排序突变。
    返回 (胜率, 来源 'lineup'/'pair'/'none', lineup 明细 dict 或 None)。"""
    if not foe_picks:
        return None, "none", None
    pe = _pair_estimate(cand, foe_picks, pair, MU, K, side)
    ln = _lineup_matchup(cand, foe_picks, idx, side)
    if ln is None:
        return (pe[0] if pe else None), ("pair" if pe else "none"), None
    if pe is None:
        return ln["wr"], "lineup", ln
    w = ln["games"] / (ln["games"] + LINEUP_PRIOR_K)
    return (1 - w) * pe[0] + w * ln["wr"], "lineup", ln


def _pos_stats(season):
    """按选位（pick_order 1-5）聚合我方英雄数据：
    by[(order, code)] = [wins, games]；tot[order] = 该选位总出场人次。
    用于计算「第 N 选率」与「该选位胜率」。按 season 缓存。"""
    if season in _POS_CACHE:
        return _POS_CACHE[season]
    conn = sqlite3.connect(DB)
    if season and A._valid_season(season):
        rows = conn.execute(
            "SELECT bp.pick_order, bp.hero_code, SUM(b.is_win), COUNT(*) "
            "FROM battle_picks bp JOIN battles b ON bp.battle_seq=b.battle_seq "
            "WHERE bp.side='my' AND b.season_code=? GROUP BY bp.pick_order, bp.hero_code",
            (season,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT bp.pick_order, bp.hero_code, SUM(b.is_win), COUNT(*) "
            "FROM battle_picks bp JOIN battles b ON bp.battle_seq=b.battle_seq "
            "WHERE bp.side='my' GROUP BY bp.pick_order, bp.hero_code").fetchall()
    conn.close()
    by, tot = {}, {}
    for order, code, w, g in rows:
        by[(order, code)] = [int(w or 0), int(g)]
        tot[order] = tot.get(order, 0) + int(g)
    out = {"by": by, "tot": tot}
    _POS_CACHE[season] = out
    return out


def _load_meta_preban():
    """从 data/meta_snapshot.json 读取职业选手 pre-ban 率 → {code: preban_rate}。
    文件不存在时返空 dict。建议在 server 启动后调用一次预热。"""
    global _META_PREBAN
    if _META_PREBAN is not None:
        return _META_PREBAN
    _META_PREBAN = {}
    fp = os.path.join(os.path.dirname(__file__), "data", "meta_snapshot.json")
    if not os.path.exists(fp):
        return _META_PREBAN
    try:
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        for e in d.get("most_pre_banned", []) or []:
            c = e.get("code")
            if c and e.get("preban_rate") is not None:
                _META_PREBAN[c] = e["preban_rate"]
    except Exception:
        _META_PREBAN = {}
    return _META_PREBAN


def _meta_preban_norm(code):
    """归一化 meta preban 到 0-1（除以最高值）。无数据返 0。"""
    r = _load_meta_preban().get(code)
    if not r:
        return 0.0
    return min(r / _META_PREBAN_MAX, 1.0)


def _shrunk(w, g, mu, k):
    """经验贝叶斯收缩：小样本胜率向全局先验 mu 拉，k = 先验强度(等效场次数)。
    例：16 场 93.8% 在 k=40、mu=0.496 下 → 约 62%，避免噪声英雄霸榜。"""
    if g <= 0:
        return mu
    return (w + k * mu) / (g + k)


def _score_bans(agg, MU, K, n_total, side, alliad_picks, foe_picks, phase, taken,
                lidx=None, limit=14):
    """返回 ban 推荐：side='me' 为我方该 ban 谁；side='enemy' 为敌方该 ban 谁。
    alliad_picks = 该方已选英雄；foe_picks = 对方已选英雄；lidx = 阵容级位掩码索引。
    评分：50% 对位威胁 + 30% 职业选手共识 + 20% 热门度。
    limit=None 时不截断且保留 _sort（供全量排序列表 all 使用）。"""
    hg, hw = agg["hero_games"], agg["hero_wins"]
    eg, ew = agg["enemy_games"], agg["enemy_wins"]
    pair = agg["pair"]
    # 目标池与基础胜率聚合：我方 ban 目标是敌方英雄(eg/ew)，敌方 ban 目标是我方英雄(hg/hw)
    tgt_games = eg if side == "me" else hg
    tgt_wins = ew if side == "me" else hw
    # postban：只能 ban 对方已选（第3选 index2 受保护）
    postban_targets = None
    if phase == "postban" and foe_picks:
        postban_targets = [foe_picks[i] for i in range(len(foe_picks)) if i != 2]
    if postban_targets is not None:
        cand = postban_targets
    else:
        cand = [c for c in tgt_games if tgt_games[c] >= 20]
    recs = []
    for c in cand:
        if postban_targets is None and c in taken:
            continue
        g = tgt_games.get(c, 0)
        # postban 目标即使场次很少也必须可评估（它是唯一合法目标池）
        if g < 5 and postban_targets is None:
            continue
        base_loss = 1 - _shrunk(tgt_wins[c], g, MU, K)
        board_loss = base_loss
        if alliad_picks and lidx is not None:
            # 分层对位：ban 候选视角下，ally_picks 就是它的「对手阵容」；
            # side='me' 表示被评估的 c 是敌方英雄（我方要 ban 它）
            est, _src, _ln = _counter_estimate(
                c, alliad_picks, pair, MU, K, lidx, "enemy" if side == "me" else "me")
            if est is not None:
                board_loss = 1 - est
        pick_rate = g / n_total
        meta_pb = _meta_preban_norm(c)
        meta_pct = _load_meta_preban().get(c)
        ban_score = 0.5 * board_loss + 0.3 * meta_pb + 0.2 * min(pick_rate * 5, 1.0)
        rec = _meta_of(c)
        who = "敌方" if side == "me" else "我方"
        reasons = [f"{who}带此英雄时{'我方' if side == 'me' else '敌方'}胜率仅 {round(100 * (1 - board_loss))}%"]
        if pick_rate >= 0.05:
            reasons.append(f"版本热门（出场率 {round(100 * pick_rate)}%）")
        if meta_pct and meta_pct >= 10:
            reasons.append(f"🔥 职业选手 pre-ban 率 {meta_pct:.1f}%（Champion+ 数据）")
        rec.update({
            "threat_win_rate": round(100 * (1 - board_loss), 1),
            "pick_rate": round(100 * pick_rate, 1),
            "meta_preban": meta_pct,
            "ban_score": round(ban_score, 1) if limit is not None else ban_score,
            "_sort": ban_score,
            "games": g,
            "reasons": reasons,
        })
        recs.append(rec)
    recs.sort(key=lambda x: x["_sort"], reverse=True)
    if limit is not None:
        recs = recs[:limit]
        for r in recs:
            r["ban_score"] = round(r["ban_score"], 3)
            r.pop("_sort", None)
    return recs


def rta_steps(hand="first", preban_count=1):
    """返回 BP 流程的步骤列表。hand='first' 表示我方先手。"""
    first = "me" if hand == "first" else "enemy"
    other = "enemy" if first == "me" else "me"
    steps = []
    for _ in range(preban_count):
        steps.append({"phase": "preban", "side": first, "count": 1})
        steps.append({"phase": "preban", "side": other, "count": 1})
    # pick 顺序 1-2-2-2-2-1（按 first/other 交替）
    counts = [(first, 1), (other, 2), (first, 2), (other, 2), (first, 2), (other, 1)]
    for i, (side, cnt) in enumerate(counts, 1):
        steps.append({"phase": "pick", "side": side, "count": cnt, "round": i})
    steps.append({"phase": "postban", "side": first, "count": 1})
    steps.append({"phase": "postban", "side": other, "count": 1})
    return steps


# ---------------------------------------------------------------------------
# 数据预聚合
# ---------------------------------------------------------------------------
def _aggregate(season):
    """聚合全场对局 → 英雄级 / 对位 / 配合统计。

    性能优化（vs 原版）：
    1. 用 collections.Counter 替代 defaultdict(lambda: [0,0])（C 实现，~2x）
    2. pair 循环并入英雄级循环（避免 2 次 set 展开）
    3. 按 season 缓存 + 磁盘 pickle 持久化（7 天有效，重启秒启）
    """
    cache_key = f"agg_{season}"
    pkl = _pickle_load(cache_key)
    if pkl:
        _AGG_CACHE[season] = pkl
        return pkl
    if season in _AGG_CACHE:
        return _AGG_CACHE[season]
    battles = A.load_battles(season)
    n_total = len(battles) or 1
    hero_games = Counter()
    hero_wins = Counter()
    enemy_games = Counter()
    enemy_wins = Counter()
    pair = defaultdict(_pair_default)
    syn = defaultdict(_pair_default)
    for my, en, win in battles:
        # 英雄级 + 对位
        for c in my:
            hero_games[c] += 1
            if win:
                hero_wins[c] += 1
            for e in en:
                key = pair[(c, e)]
                key[1] += 1
                if win:
                    key[0] += 1
        for e in en:
            enemy_games[e] += 1
            if win:
                enemy_wins[e] += 1
        # 我方内配合（5×4/2 = 10 对）
        ml = list(my)
        for i in range(len(ml)):
            ci = ml[i]
            for j in range(i + 1, len(ml)):
                key = syn[(ci, ml[j])]
                key[1] += 1
                if win:
                    key[0] += 1
    out = {
        "n_total": n_total,
        "hero_games": hero_games, "hero_wins": hero_wins,
        "enemy_games": enemy_games, "enemy_wins": enemy_wins,
        "pair": pair, "syn": syn,
    }
    _AGG_CACHE[season] = out
    _pickle_save(cache_key, out)
    return out


_META = None


def hero_meta():
    """code -> {name, attr, attr_raw, job, rarity}。

    星数(rarity)/属性/职业以官方静态数据为准（A.hero_static，373 个全有），
    battle_picks 仅作离线兜底；修复了此前 37 个英雄缺属性/职业的问题。"""
    global _META
    if _META is None:
        conn = sqlite3.connect(DB)
        name = {r[0]: r[1] for r in conn.execute("SELECT code, name FROM heroes")}
        attr = {}
        job = {}
        for code, a, j in conn.execute(
                "SELECT DISTINCT hero_code, attribute_cd, job_cd FROM battle_picks"):
            attr.setdefault(code, a)
            job.setdefault(code, j)
        conn.close()
        st = A.hero_static()
        _META = {}
        for code in set(name) | set(attr) | set(st):
            s = st.get(code) or {}
            a = s.get("attribute_cd") or attr.get(code) or ""
            j = s.get("job_cd") or job.get(code) or ""
            _META[code] = {
                "name": name.get(code, code),
                "attr": A.attr_cn(a) if a else "",
                "attr_raw": a,  # 英文（fire/wind/ice/...）用于克制计算
                "job": A.job_cn(j) if j else "",
                "job_raw": j,   # 英文（warrior/knight/...）前端筛选用
                "rarity": s.get("rarity") or 0,  # 天然星数 3/4/5
            }
    return _META


_META_OF_CACHE = {}  # code -> {...} —— _meta_of 返回值会被外部 .update() 污染，每次复制一份


def _meta_of(code):
    """返回 code 的元数据 dict。注意：调用方会用 .update() 改写返回对象，所以必须返回新 dict。"""
    return dict(_META_OF_CACHE.get(code) or _build_meta(code))


def _build_meta(code):
    m = hero_meta().get(code, {})
    out = {
        "code": code,
        "name": m.get("name", code),
        "attr": m.get("attr", ""),
        "attr_raw": m.get("attr_raw", ""),
        "job": m.get("job", ""),
        "job_raw": m.get("job_raw", ""),
        "rarity": m.get("rarity", 0),
    }
    _META_OF_CACHE[code] = out
    return out


# ---------------------------------------------------------------------------
# 推荐引擎
# ---------------------------------------------------------------------------
def suggest(state):
    """state: {hand, side, my_picks[], enemy_picks[], my_bans[], enemy_bans[], phase, season}

    返回新增 all：当前回合（side + phase）的全英雄排序列表——推荐度从高到低，
    前端只渲染这一个网格，不再割裂「推荐」和「全部英雄」两个区域。
    有对局数据的英雄带完整选位/胜率数据；无数据的 score=null 排最后。"""
    my_picks = list(state.get("my_picks") or [])
    enemy_picks = list(state.get("enemy_picks") or [])
    my_bans = list(state.get("my_bans") or [])
    enemy_bans = list(state.get("enemy_bans") or [])
    season = state.get("season")
    phase = state.get("phase")
    side = state.get("side") or "me"
    agg = _aggregate(season)
    hg, hw = agg["hero_games"], agg["hero_wins"]
    eg, ew = agg["enemy_games"], agg["enemy_wins"]
    pair, syn = agg["pair"], agg["syn"]
    n_total = agg["n_total"]

    # 经验贝叶斯先验：全局平均自身胜率 + 先验强度 K（等效场次数）
    hw_total = sum(hw.values())
    hg_total = sum(hg.values())
    MU = (hw_total / hg_total) if hg_total else 0.5
    K = 40.0

    # my_bans / enemy_bans 可能是 [{code,pre}] 字典或纯 code 字符串，统一抽 code
    my_ban_codes = {b["code"] if isinstance(b, dict) else b for b in my_bans}
    enemy_ban_codes = {b["code"] if isinstance(b, dict) else b for b in enemy_bans}
    taken = set(my_picks) | set(enemy_picks) | my_ban_codes | enemy_ban_codes

    # ---- 我方选人评分（全英雄；选位常用度作为乘数而非加项）----
    pos = _pos_stats(season)
    lidx = _lineup_index(season)   # 阵容级对位位掩码索引（缓存复用）
    slot = min(len(my_picks) + 1, 5)   # 我方第几选（对应数据里 pick_order 1-5）
    slot_tot = pos["tot"].get(slot, 0)

    def _usage_mult(pg, slot_rate):
        """选位常用度乘数：第 slot 选率 ≥2.5% 记满分(1.0)，线性衰减；
        该位从未出场(pg=0) → 0.40。修复「第1选率 0% 也被顶上推荐位」的问题——
        一个从不在 1 选位置出场的英雄，无论多强都不该排进 1 选推荐前列。"""
        if not pg:
            return 0.40
        u = min(slot_rate / 0.025, 1.0)
        return 0.55 + 0.45 * u

    pick_all = []
    for c in hero_meta():
        if c in taken:
            continue
        g = hg.get(c, 0)
        rec = _meta_of(c)
        pw, pg = pos["by"].get((slot, c), (0, 0))
        slot_rate = (pg / slot_tot) if slot_tot else 0.0
        if g == 0:
            # 完全无对局数据：不评分，排最后（前端显示「暂无数据」）
            rec.update({"score": None, "_sort": None, "games": 0,
                        "self_win_rate": None, "counter_score": None, "synergy": None,
                        "pos_order": slot, "pos_rate": 0.0, "pos_games": 0,
                        "pos_wr": None, "reasons": [], "vs_list": [],
                        "counter_src": "none", "lineup": None,
                        "counters_weak": "", "counters_strong": ""})
            pick_all.append(rec)
            continue
        self_wr = _shrunk(hw[c], g, MU, K)
        counter = self_wr
        vs_list = []   # 对敌方每个已选英雄的历史对位明细（供前端展示"针对谁"）
        lineup = None  # 阵容级对位明细（全员/最大子集）
        counter_src = "none"
        if enemy_picks:
            for e in enemy_picks:
                ew_, eg_ = pair[(c, e)]
                if eg_ > 0:
                    vs_list.append({
                        "code": e,
                        "name": _meta_of(e)["name"],
                        "wr": round(100 * _shrunk(ew_, eg_, MU, K), 1),
                        "games": eg_,
                    })
            # 分层：阵容级（全员/最大子集）优先，样本不足自动降级到单体对位
            est, counter_src, ln = _counter_estimate(c, enemy_picks, pair, MU, K, lidx, "me")
            if est is not None:
                counter = est
            if ln:
                lineup = {"size": ln["size"], "games": ln["games"],
                          "wr": round(100 * ln["wr"], 1),
                          "heroes": [{"code": x, "name": _meta_of(x)["name"]}
                                     for x in ln["heroes"]]}
        synergy = self_wr
        if my_picks:
            ss = [_shrunk(syn[(c, p)][0], syn[(c, p)][1], MU, K)
                  for p in my_picks if syn[(c, p)][1] > 0]
            if ss:
                synergy = sum(ss) / len(ss)
        slot_wr = _shrunk(pw, pg, MU, 60) if pg else MU
        # 评分 = 基础分（对位克制 40% + 自身强度 25% + 配合 10% + 该位胜率 25%）
        #        × 选位常用度乘数（0.40~1.0）
        # 无敌方已选时 counter==self_wr，权重拆分无影响；有敌方已选时克制占主导。
        base = 0.40 * counter + 0.25 * self_wr + 0.10 * synergy + 0.25 * slot_wr
        score = base * _usage_mult(pg, slot_rate)
        reasons = []
        if enemy_picks and counter_src == "lineup":
            reasons.append(f"阵容级对位：对阵敌方 {lineup['size']} 人核心胜率 "
                           f"{lineup['wr']}%（{lineup['games']} 场）")
        elif enemy_picks and counter_src == "pair":
            reasons.append(f"单体对位（阵容级样本不足，已降级）：对位胜率 {round(100 * counter)}%")
        elif enemy_picks and abs(counter - self_wr) > 0.02:
            reasons.append(f"克制敌方当前阵容（对位胜率 {round(100 * counter)}%）")
        reasons.append(f"自身强度 {round(100 * self_wr)}%")
        if my_picks and abs(synergy - self_wr) > 0.02:
            reasons.append(f"与我方配合（同队胜率 {round(100 * synergy)}%）")
        if not pg:
            reasons.append(f"⚠ 第 {slot} 选位几乎不用（历史 {round(100 * slot_rate, 1) if slot_rate else 0}%），慎选")
        vs_list.sort(key=lambda v: v["wr"], reverse=True)
        rec.update({
            "self_win_rate": round(100 * self_wr, 1),
            "counter_score": round(100 * counter, 1),
            "counter_src": counter_src,   # lineup / pair / none（前端标注数据来源）
            "lineup": lineup,             # 阵容级明细 {size, games, wr, heroes[]}
            "synergy": round(100 * synergy, 1),
            "pos_order": slot,
            "pos_rate": round(100 * slot_rate, 1),     # 第 slot 选率（该位出场占比）
            "pos_games": pg,
            "pos_wr": round(100 * slot_wr, 1) if pg else None,
            "score": score,            # 完整精度，下面排序用
            "_sort": score,            # 排序键（避免四舍五入后大批量并列退化为随机）
            "games": g,
            "reasons": reasons,
            "vs_list": vs_list,        # 针对敌方已选的逐个对位（胜率降序）
        })
        weak_cn, strong_cn = _counter_for(rec.get("attr_raw", ""))
        rec["counters_weak"] = weak_cn    # 我方克它
        rec["counters_strong"] = strong_cn  # 它克我方
        pick_all.append(rec)

    pick_all.sort(key=lambda r: (r["_sort"] is None, -(r["_sort"] or 0)))
    all_picks = []
    for r in pick_all:
        r["score"] = round(r["score"], 3) if r["score"] is not None else None
        r.pop("_sort", None)
        all_picks.append(r)
    # 顶部推荐（my_picks 供预测/模拟用）：只保留该选位确有出场数据的英雄（pg≥30）
    my_rec = [r for r in all_picks if r["pos_games"] >= 30 and r["score"] is not None][:14]

    # ---- 我方 / 敌方 ban 推荐（对称复用同一套评分）----
    ban_rec = _score_bans(agg, MU, K, n_total, "me", my_picks, enemy_picks, phase, taken, lidx)
    enemy_ban_rec = _score_bans(agg, MU, K, n_total, "enemy", enemy_picks, my_picks, phase, taken, lidx)

    # ---- 模拟对手选人评分（全英雄，供 enemy_picks 与敌方回合 all 列表）----
    slot_en = min(len(enemy_picks) + 1, 5)
    slot_en_tot = pos["tot"].get(slot_en, 0)
    enemy_all = []
    for c in hero_meta():
        if c in taken:
            continue
        g = hg.get(c, 0)
        rec = _meta_of(c)
        pw, pg = pos["by"].get((slot_en, c), (0, 0))
        slot_rate = (pg / slot_en_tot) if slot_en_tot else 0.0
        if g == 0:
            rec.update({"score": None, "_sort": None, "games": 0,
                        "self_win_rate": None, "vs_me_score": None,
                        "pos_order": slot_en, "pos_rate": 0.0, "pos_games": 0,
                        "pos_wr": None})
            enemy_all.append(rec)
            continue
        self_wr = _shrunk(hw[c], g, MU, K)
        # 对手想 counter 我方当前阵容（counter 越高 = 我方越难受）
        # 同样走分层：阵容级（vs 我方已选全员/最大子集）优先，样本不足降级到单体对位
        counter = self_wr
        counter_src = "none"
        lineup = None
        if my_picks:
            est, counter_src, ln = _counter_estimate(c, my_picks, pair, MU, K, lidx, "enemy")
            if est is not None:
                counter = est
            if ln:
                lineup = {"size": ln["size"], "games": ln["games"],
                          "wr": round(100 * ln["wr"], 1),
                          "heroes": [{"code": x, "name": _meta_of(x)["name"]}
                                     for x in ln["heroes"]]}
        slot_wr = _shrunk(pw, pg, MU, 60) if pg else MU
        base_e = 0.40 * counter + 0.30 * self_wr + 0.30 * slot_wr
        escore = base_e * _usage_mult(pg, slot_rate)
        rec.update({
            "self_win_rate": round(100 * self_wr, 1),
            "vs_me_score": round(100 * counter, 1),
            "counter_src": counter_src,
            "lineup": lineup,          # 敌方视角：该英雄 vs 我方已选阵容的阵容级胜率
            "pos_order": slot_en,
            "pos_rate": round(100 * slot_rate, 1),
            "pos_games": pg,
            "pos_wr": round(100 * slot_wr, 1) if pg else None,
            "score": escore,
            "_sort": escore,
            "games": g,
        })
        enemy_all.append(rec)
    enemy_all.sort(key=lambda r: (r["_sort"] is None, -(r["_sort"] or 0)))
    all_enemy_picks = []
    for r in enemy_all:
        r["score"] = round(r["score"], 3) if r["score"] is not None else None
        r.pop("_sort", None)
        all_enemy_picks.append(r)
    enemy_rec = [r for r in all_enemy_picks if r["pos_games"] >= 30 and r["score"] is not None][:14]

    # ---- 我方 / 敌方 ban 推荐（对称复用同一套评分）----
    ban_rec = _score_bans(agg, MU, K, n_total, "me", my_picks, enemy_picks, phase, taken, lidx)
    enemy_ban_rec = _score_bans(agg, MU, K, n_total, "enemy", enemy_picks, my_picks, phase, taken, lidx)

    # ---- 全量排序列表：按当前回合 side+phase 选一种，前端统一渲染 ----
    if is_ban_phase(phase):
        if side == "enemy":
            scored = _score_bans(agg, MU, K, n_total, "enemy", enemy_picks, my_picks,
                                 phase, taken, lidx, limit=None)
        else:
            scored = _score_bans(agg, MU, K, n_total, "me", my_picks, enemy_picks,
                                 phase, taken, lidx, limit=None)
        if phase == "postban":
            # 终 ban 只能 ban 对方已选：只列合法目标（受保护第 3 选由前端禁用提示）
            all_list = scored
        else:
            scored_map = {r["code"] for r in scored}
            all_list = []
            for r in scored:
                r["ban_score"] = round(r["ban_score"], 3)
                r.pop("_sort", None)
                all_list.append(r)
            for c in hero_meta():
                if c in taken or c in scored_map:
                    continue
                r = _meta_of(c)
                r.update({"score": None, "ban_score": None, "games": 0,
                          "threat_win_rate": None, "pick_rate": None,
                          "meta_preban": _load_meta_preban().get(c), "reasons": []})
                all_list.append(r)
    else:
        all_list = all_picks if side == "me" else all_enemy_picks

    return {"my_picks": my_rec, "my_bans": ban_rec,
            "enemy_picks": enemy_rec, "enemy_bans": enemy_ban_rec,
            "all": all_list, "all_mode": "ban" if is_ban_phase(phase) else "pick",
            "slot": slot if side == "me" else slot_en,
            "matchup": _matchup_predict(my_picks, enemy_picks, agg, n_total),
            "attr_overview": _attr_overview(my_picks, enemy_picks)}


def is_ban_phase(phase):
    """ban 阶段判断（后端 STEPS 的 phase 值是 preban/postban，不是 ban）。"""
    return phase in ("preban", "postban")


def _attr_of(code):
    """code → 内部属性英文（fire/wind/ice/light/dark），用于克制计算。"""
    m = hero_meta().get(code, {})
    raw = m.get("attr_raw") or ""
    return raw


def _counter_for(rec_attr):
    """返回 rec_attr 被谁克 / 克谁（中文）。"""
    from analytics import ATTR_COUNTER
    rev = {v: k for k, v in ATTR_COUNTER.items()}
    weak = rev.get(rec_attr, "")  # 克它的属性
    strong = ATTR_COUNTER.get(rec_attr, "")  # 它克的属性
    cn = {"fire": "火", "wind": "风", "ice": "冰", "light": "光", "dark": "暗"}
    return cn.get(weak, ""), cn.get(strong, "")


def _matchup_predict(my_picks, enemy_picks, agg, n_total):
    """4v4 整体胜率预估：每个我方英雄 vs 敌方阵容的平均胜率，再取均值。
    返回 {my_wr, enemy_wr, advantage, sample_info}（百分比，浮点）。

    注：BP 走到一半时（如我2 敌3）也能计算——此时基于已选阵容的局部胜率预估，
    通过 pair 单体对位（经验贝叶斯收缩 K=40）而非位掩码阵容级——后者样本不足。
    满员 4v4 时退化为传统对位平均。
    """
    if not my_picks or not enemy_picks:
        return {"my_wr": None, "enemy_wr": None, "advantage": 0,
        "coverage": "无阵容数据"}
    # 过滤无效 code（MuMu OCR 偶尔识别错的 code）——双方都至少要有 1 个有效 code
    valid_codes = set(agg["hero_games"].keys())
    my_valid = [c for c in my_picks if c in valid_codes]
    en_valid = [c for c in enemy_picks if c in valid_codes]
    if not my_valid or not en_valid:
        return {"my_wr": None, "enemy_wr": None, "advantage": 0,
        "coverage": "对手阵容无效"}

    pair = agg["pair"]
    hg, hw = agg["hero_games"], agg["hero_wins"]
    hw_total = sum(hw.values()); hg_total = sum(hg.values())
    MU = (hw_total / hg_total) if hg_total else 0.5
    K = 40.0

    # 整体 MU 是 base rate，先用 pair 单体对位加权（任何人数都能算）
    per_my = []
    sample_pairs = 0
    for m in my_valid:
        wrs = []
        for e in en_valid:
            w, g = pair.get((m, e), (0, 0))
            if g > 0:
                # 用 _shrunk 让小样本对位不至于被噪声支配
                wrs.append(_shrunk(w, g, MU, K))
                sample_pairs += 1
        if wrs:
            per_my.append(sum(wrs) / len(wrs))
        else:
            # 我方该英雄在数据库中无任何对位数据，用全局平均
            g = hg.get(m, 0)
            if g > 0:
                per_my.append(_shrunk(hw[m], g, MU, K))

    if not per_my:
        return {"my_wr": None, "enemy_wr": None, "advantage": 0,
        "coverage": "无样本"}
    my_wr = sum(per_my) / len(per_my)
    enemy_wr = 1 - my_wr

    # 阵容覆盖度：满员 4v4 = 16 对, 走完一半 = 6 对, 走完前 1 选 = 1 对
    full_pairs = len(my_picks) * len(enemy_picks)
    coverage = "完整" if full_pairs >= 16 else ("部分" if full_pairs >= 6 else "预估")

    return {
        "my_wr": round(my_wr * 100, 1),
        "enemy_wr": round(enemy_wr * 100, 1),
        "advantage": round((my_wr - enemy_wr) * 100, 1),
        "coverage": coverage,
        "sample_pairs": sample_pairs,
    }


def _attr_overview(my_picks, enemy_picks):
    """属性克制总览：双方属性分布 + 我方被克数 / 克敌方数。
    返回 {my_attr, en_attr, my_counted_by_enemy, en_counted_by_me}。
    my_counted_by_enemy = 我方被敌方克制属性数（越高越劣势）。"""
    from collections import Counter
    rev = {v: k for k, v in A.ATTR_COUNTER.items()}  # 反向：weak 属性
    meta = hero_meta()
    def dist(codes):
        c = Counter()
        for code in codes:
            a = meta.get(code, {}).get("attr_raw", "")
            if a: c[a] += 1
        return dict(c)
    my_attr = dist(my_picks)
    en_attr = dist(enemy_picks)
    # 我方阵营里"被敌方克"的英雄数
    my_counted_by_enemy = 0
    for mc in my_picks:
        ma = meta.get(mc, {}).get("attr_raw", "")
        for ea, n in en_attr.items():
            if rev.get(ea) == ma and n > 0:  # ea 克 ma
                my_counted_by_enemy += n
                break
    # 敌方阵营里"被我方克"的英雄数
    en_counted_by_me = 0
    for ec in enemy_picks:
        ea = meta.get(ec, {}).get("attr_raw", "")
        for ma, n in my_attr.items():
            if rev.get(ma) == ea and n > 0:
                en_counted_by_me += n
                break
    return {
        "my_attr": {A.attr_cn(k): v for k, v in my_attr.items()},
        "en_attr": {A.attr_cn(k): v for k, v in en_attr.items()},
        "my_counted_by_enemy": my_counted_by_enemy,
        "en_counted_by_me": en_counted_by_me,
    }
def quick_recommend(enemy_picks, top=20, season=None):
    """极简 BP 推荐：只输入敌方阵容 → top 个我方推荐英雄。

    专为 MuMu 模拟器截图识别后实时调用设计 —— 不参与 BP 步进、不需要知道我方已选。
    内部复用 suggest() 的全量评分（分层对位估计 + 选位匹配），输出字段精简到 MuMu 直接渲染所需。

    Args:
        enemy_picks: 敌方已选英雄 code 列表（最多 5 个）
        top: 返回前 N 个推荐（默认 20，上限 100）
        season: 赛季 code（None = 全部）

    Returns:
        {
            "recommendations": [按推荐度降序],
            "meta": {
                "input_enemy_picks": [...],
                "lineup_subsets_used": [2,3,...],   # 阵容级命中用了哪些子集规模
                "scored_candidates": 393,          # 总候选数
                "lineup_hit_candidates": 28,       # 阵容级命中数
                "lineup_hit_top": {wr, games}      # 命中样本的最大子集（仅命中时存在）
            }
        }
    """
    # clamp top 到合法范围（防 top=-1 时 Python 切片 [:−1] 返回全集去尾）
    top = max(0, min(int(top or 0), 100))
    state = {
        "hand": "first", "side": "me",
        "my_picks": [], "my_bans": [],
        "enemy_picks": list(enemy_picks or []),
        "enemy_bans": [],
        "phase": "pick", "season": season,
    }
    d = suggest(state)
    all_picks = d.get("all", [])

    keys = ("code", "name", "attr", "attr_raw", "job", "rarity",
            "score", "self_win_rate", "counter_score", "synergy",
            "counter_src", "lineup", "vs_list",
            "pos_order", "pos_rate", "pos_games", "pos_wr",
            "games", "reasons", "counters_weak", "counters_strong")
    recs = [{k: r.get(k) for k in keys} for r in all_picks[:top]]

    lineup_subsets = sorted({(r.get("lineup") or {}).get("size")
                             for r in all_picks if r.get("counter_src") == "lineup"})
    lineup_hits = sum(1 for r in all_picks if r.get("counter_src") == "lineup")
    # 取样本量最大的子集作为头部推荐依据
    best = None
    for r in all_picks:
        if r.get("counter_src") == "lineup" and r.get("lineup"):
            g = r["lineup"]["games"]
            if best is None or g > best["games"]:
                best = r["lineup"]

    return {
        "recommendations": recs,
        "meta": {
            "input_enemy_picks": state["enemy_picks"],
            "lineup_subsets_used": lineup_subsets,
            "scored_candidates": len(all_picks),
            "lineup_hit_candidates": lineup_hits,
            "lineup_hit_top": best,  # 头部命中样本最大的子集
        }
    }
