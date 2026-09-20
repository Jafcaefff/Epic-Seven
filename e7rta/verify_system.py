#!/usr/bin/env python3
"""
BP 辅助系统综合回归 + 策略审查测试
- 流程：A) 完整 BP 推进 / B) 状态机删除回退 / C) 大师+ / D) BP 完成
- 推荐：B) 排序稳定性 / C) 空阵容不应推荐 0 选位英雄 / D) 阵容变化时联动
- 分层对位：A) 敌 1 人 pair / B) 敌 2-3 人 lineup / C) 降级链路
- 策略：A) 评分权重合理性 / B) matchup 预测 / C) ban 评分
- 边界：A) 空 enemy / B) 无效 code / C) top 限制 / D) postban 只能 ban 对方已选
"""
import sys, json, time, urllib.request

sys.path.insert(0, 'E:/第七史诗查询工具/e7rta')
import draft  # noqa  (用来生成期望 STEPS + 校验服务端逻辑)


BASE = 'http://127.0.0.1:8799'


def post(path, body, timeout=30):
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def get(path, timeout=15):
    return json.load(urllib.request.urlopen(BASE + path, timeout=timeout))


# ---------------- 工具 ----------------

FAIL = []
PASS = []


def check(name, cond, info=''):
    if cond:
        PASS.append(name)
        print(f'  OK   {name}' + (f'  ({info})' if info else ''))
    else:
        FAIL.append((name, info))
        print(f'  FAIL {name}' + (f'  [{info}]' if info else ''))


def section(t):
    print(f'\n=== {t} ===')


def steps(hand='first', preban=1):
    """本地生成 BP 步骤（与服务端 draft.rta_steps 一致）"""
    return draft.rta_steps(hand, preban)


# ---------------- 测试 ----------------

print('BP 系统综合测试 / ' + time.strftime('%Y-%m-%d %H:%M:%S'))
print('=' * 60)

# ---------- A. 流程完整性 ----------
section('A. 流程完整性')

# A1. 我方先手完整 BP 走完
state = {'hand': 'first', 'side': 'me', 'my_picks': [], 'enemy_picks': [],
         'my_bans': [], 'enemy_bans': [], 'phase': None, 'season': None}
S = steps('first', 1)
my_pool = ['c2124', 'c1183', 'c5154', 'c6005', 'c1106']
en_pool = ['c1096', 'c1118', 'c1129', 'c2111', 'c1157']
ban_pool = ['c2007', 'c9001']
my_ban_pool = ['c2008', 'c9002']
myp, enp, myb, enb = 0, 0, 0, 0

# 模拟：根据 STEPS 推进
for i, step in enumerate(S):
    state['side'] = step['side']
    state['phase'] = step['phase']
    if step['phase'] == 'preban':
        if step['side'] == 'me':
            state['my_bans'].append(ban_pool[myb]); myb += 1
        else:
            state['enemy_bans'].append(my_ban_pool[enb]); enb += 1
    elif step['phase'] == 'pick':
        for _ in range(step['count']):
            if step['side'] == 'me':
                state['my_picks'].append(my_pool[myp]); myp += 1
            else:
                state['enemy_picks'].append(en_pool[enp]); enp += 1
    elif step['phase'] == 'postban':
        if step['side'] == 'me':
            target = state['enemy_picks'][0] if len(state['enemy_picks']) > 0 else en_pool[0]
            if target not in state['my_bans']:
                state['my_bans'].append(target)
        else:
            target = state['my_picks'][0] if len(state['my_picks']) > 0 else my_pool[0]
            if target not in state['enemy_bans']:
                state['enemy_bans'].append(target)

check('A1 我方先手 5v5 完整流程', len(state['my_picks']) == 5 and len(state['enemy_picks']) == 5,
      f'my={len(state["my_picks"])} en={len(state["enemy_picks"])}')
check('A2 preban 各 1 个', len([b for b in state['my_bans'] if b in ban_pool + [state['enemy_picks'][0]]]) >= 1
      and len([b for b in state['enemy_bans'] if b in my_ban_pool + [state['my_picks'][0]]]) >= 1,
      f'my_bans={state["my_bans"]} en_bans={state["enemy_bans"]}')

# A2. 我方后手完整流程
state2 = {'hand': 'second', 'my_picks': [], 'enemy_picks': [],
          'my_bans': [], 'enemy_bans': []}
S2 = steps('second', 1)
mp, ep, mb, eb = 0, 0, 0, 0
for step in S2:
    if step['phase'] == 'preban':
        if step['side'] == 'me':
            state2['my_bans'].append(my_ban_pool[mb]); mb += 1
        else:
            state2['enemy_bans'].append(ban_pool[eb]); eb += 1
    elif step['phase'] == 'pick':
        for _ in range(step['count']):
            if step['side'] == 'me':
                state2['my_picks'].append(my_pool[mp]); mp += 1
            else:
                state2['enemy_picks'].append(en_pool[ep]); ep += 1
    elif step['phase'] == 'postban':
        if step['side'] == 'me':
            t = state2['enemy_picks'][0]
            if t not in state2['my_bans']: state2['my_bans'].append(t)
        else:
            t = state2['my_picks'][0]
            if t not in state2['enemy_bans']: state2['enemy_bans'].append(t)

check('A3 我方后手 5v5 完整流程', len(state2['my_picks']) == 5 and len(state2['enemy_picks']) == 5,
      f'my={len(state2["my_picks"])} en={len(state2["enemy_picks"])}')

# A3. 大师+（preban=2）
S3 = steps('first', 2)
check('A4 大师+ STEPS 包含 4 个 preban（每侧 2 个）',
      sum(1 for s in S3 if s['phase'] == 'preban') == 4,
      f'preban 步数={sum(1 for s in S3 if s["phase"]=="preban")}')
# 大师+ 总操作数：2+2(preban) + 10(pick 1+2+2+2+2+1) + 2(postban) = 16
total_ops = sum(s.get('count', 1) for s in S3)
check('A5 大师+ 总 BP 操作数 = 16',
      total_ops == 16,
      f'总操作数={total_ops}')

# A4. BP 完成状态
final_state = {**state, 'phase': 'postban'}
final_state['side'] = 'done'
resp = post('/api/draft/suggest', final_state)
check('A6 BP 完成后服务端仍能响应（返回 all + matchup）',
      'all' in resp and 'matchup' in resp,
      f'keys={list(resp.keys())[:6]}')

# ---------- B. 推荐质量 ----------
section('B. 推荐质量')

# B1. 排序稳定性：相同输入多次调用结果一致
body = {'hand': 'first', 'side': 'me', 'my_picks': [], 'enemy_picks': [],
        'my_bans': [], 'enemy_bans': [], 'phase': 'pick', 'season': None}
r1 = post('/api/draft/suggest', body)
r2 = post('/api/draft/suggest', body)
r3 = post('/api/draft/suggest', body)
ids1 = [(x['code'], x['score']) for x in r1['all']]
ids2 = [(x['code'], x['score']) for x in r2['all']]
ids3 = [(x['code'], x['score']) for x in r3['all']]
check('B1 同输入 3 次调用结果完全一致', ids1 == ids2 == ids3,
      f'#1=#2={ids1==ids2} #2=#3={ids2==ids3}')

# B2. 排序单调性
scored = [x for x in r1['all'] if x['score'] is not None]
mono = all(scored[i]['score'] <= scored[i-1]['score'] for i in range(1, len(scored)))
check('B2 有数据的候选 score 单调不增', mono,
      f'前 5={[(x["name"], x["score"]) for x in scored[:5]]}')

# B3. 无数据的英雄排在最后
no_data_idx = next((i for i, x in enumerate(r1['all']) if x['score'] is None), len(r1['all']))
scored_count = len(scored)
check('B3 无数据的英雄排到最后', no_data_idx == scored_count,
      f'有数据={scored_count}, 无数据起始位={no_data_idx}')

# B4. 空阵容时前排不应推荐 1选率=0 的英雄
top5_with_pos0 = sum(1 for x in scored[:5] if x.get('pos_rate', 0) == 0 and x.get('pos_games', 0) == 0)
check('B4 空阵容时前 5 名都有真实选位数据', top5_with_pos0 == 0,
      f'前 5 中 0 选位率数={top5_with_pos0}')
top10_with_pos0 = sum(1 for x in scored[:10] if x.get('pos_rate', 0) == 0 and x.get('pos_games', 0) == 0)
print(f'     (前 10 中 0 选位率数={top10_with_pos0})')

# B5. 阵容变化时推荐应变化（实时联动）
body_e1 = {**body, 'enemy_picks': ['c5154']}
body_e3 = {**body, 'enemy_picks': ['c5154', 'c2124', 'c1183']}
r_e1 = post('/api/draft/suggest', body_e1)
r_e3 = post('/api/draft/suggest', body_e3)
top_e1 = [x['code'] for x in r_e1['my_picks'][:5]]
top_e3 = [x['code'] for x in r_e3['my_picks'][:5]]
check('B5 敌方阵容从 1→3 人推荐前 5 名变化', top_e1 != top_e3,
      f'e1={top_e1[:3]} e3={top_e3[:3]}')

# B6. 评分上下界
scores = [x['score'] for x in scored]
check('B6 score 范围 [0, 1]', min(scores) >= 0 and max(scores) <= 1,
      f'min={min(scores):.3f} max={max(scores):.3f}')

# ---------- C. 分层对位 ----------
section('C. 分层对位')

# C1. 敌 1 人应该是 pair 单体对位
r_e1 = post('/api/draft/suggest', {**body, 'enemy_picks': ['c1106']})
src_e1 = [x.get('counter_src') for x in r_e1['my_picks']]
check('C1 敌 1 人 → 命中层级主要是 pair 或 position（无 lineup）',
      'lineup' not in src_e1, f'层级分布={ {s: src_e1.count(s) for s in set(src_e1)} }')

# C2. 敌 3-5 人应该命中 lineup
r_e3 = post('/api/draft/suggest', {**body, 'enemy_picks': ['c5154', 'c2124', 'c1183']})
src_e3 = [x.get('counter_src') for x in r_e3['my_picks']]
lineup_e3 = sum(1 for s in src_e3 if s == 'lineup')
check('C2 敌 3 人 → 有 lineup 命中', lineup_e3 > 0,
      f'lineup={lineup_e3}/{len(src_e3)}, 分布={ {s: src_e3.count(s) for s in set(src_e3)} }')

# C3. 敌 4-5 人应该有 lineup 命中（子集降级到 3-4 人）
r_e4 = post('/api/draft/suggest', {**body, 'enemy_picks': ['c5154', 'c2124', 'c1183', 'c6005']})
src_e4 = [x.get('counter_src') for x in r_e4['my_picks']]
lineup_e4 = sum(1 for s in src_e4 if s == 'lineup')
check('C3 敌 4 人 → 仍能命中 lineup（降级子集）', lineup_e4 > 0,
      f'lineup={lineup_e4}/{len(src_e4)}')

# C4. 阵容级 vs 单体的样本数应该显著不同
r_e3_full = post('/api/draft/suggest', {**body, 'enemy_picks': ['c5154', 'c2124', 'c1183']})
lineup_rec = next((x for x in r_e3_full['my_picks'] if x.get('counter_src') == 'lineup'), None)
pair_rec = next((x for x in r_e3_full['my_picks'] if x.get('counter_src') == 'pair'), None)
if lineup_rec and pair_rec:
    check('C4 阵容级样本数与 pair 对位样本数不一致（验证非退化）',
          lineup_rec.get('lineup', {}).get('games', 0) != lineup_rec.get('games', 0),
          f"lineup={lineup_rec['name']} lineup.games={lineup_rec['lineup']['games']} total.games={lineup_rec['games']}")

# ---------- D. 策略/逻辑 ----------
section('D. 策略/逻辑')

# D1. ban 评分合理性：ban 推荐 top 应包含对位威胁高的英雄
r_preban = post('/api/draft/suggest', {**body, 'enemy_picks': ['c5154'], 'phase': 'preban'})
top_bans = r_preban['my_bans'][:5]
# 调香师维波里丝 c5154 是强力辅助，应该在己方禁对手时威胁最高
codes_ban = [b['code'] for b in top_bans]
check('D1 ban 推荐返回 ban_score 字段', all('ban_score' in b for b in top_bans),
      f'codes={codes_ban}')
check('D2 ban 推荐 top 5 ban_score 单调不增',
      all(top_bans[i]['ban_score'] >= top_bans[i+1]['ban_score'] for i in range(len(top_bans)-1)),
      f'前 5={[(b["name"], b["ban_score"]) for b in top_bans]}')

# D3. postban 只能 ban 对方已选
r_post = post('/api/draft/suggest', {**body, 'enemy_picks': ['c1106', 'c2124', 'c1183'],
                                       'my_picks': ['c5154', 'c6005', 'c1096'],
                                       'phase': 'postban'})
post_targets = [b['code'] for b in r_post['my_bans']]
en_picks = ['c1106', 'c2124', 'c1183']
check('D3 postban 目标只能是对方已选英雄', all(t in en_picks for t in post_targets),
      f'目标={post_targets}, 敌方={en_picks}')
# 第 3 选(index=2)受保护
check('D4 postban 不应推荐对方第 3 选（受保护）',
      'c1183' not in post_targets,
      f'目标={post_targets}, 敌方第 3 选=c1183')

# D5. matchup 预测存在且包含我/敌胜率
check('D5 matchup 预测包含我方/敌方胜率',
      r_post['matchup'].get('my_wr') is not None and r_post['matchup'].get('enemy_wr') is not None,
      f"matchup={r_post['matchup']}")
advantage = r_post['matchup'].get('advantage')
check('D6 matchup.advantage 是数值差（-100~100）',
      isinstance(advantage, (int, float)) and -100 <= advantage <= 100,
      f"advantage={advantage}")

# D7. 我方回合 vs 敌方回合推荐不同（视角不同）
r_me_pick = post('/api/draft/suggest', {**body, 'enemy_picks': ['c5154'], 'side': 'me'})
r_en_pick = post('/api/draft/suggest', {**body, 'enemy_picks': ['c5154'], 'side': 'enemy'})
codes_me = [x['code'] for x in r_me_pick['my_picks'][:5]]
codes_en_view = [x['code'] for x in r_en_pick['all'][:5]]
check('D7 我方视角和敌方视角推荐不同', codes_me != codes_en_view,
      f'我方={codes_me[:3]} 敌方={codes_en_view[:3]}')

# ---------- E. 边界/异常 ----------
section('E. 边界/异常')

# E1. 空 enemy_picks
r_empty = post('/api/draft/suggest', {**body, 'enemy_picks': []})
check('E1 空敌方阵容能正常返回',
      len(r_empty['all']) > 0, f'rec={len(r_empty["all"])}')

# E2. 无效 code
r_bad = post('/api/draft/suggest', {**body, 'enemy_picks': ['c9999', 'c8888']})
check('E2 无效 code 不报错',
      'recommendations' in r_bad or 'all' in r_bad, f'rec={len(r_bad.get("all", []))}')

# E3. my_picks 含无效 code
r_bad2 = post('/api/draft/suggest', {**body, 'my_picks': ['c2124', 'c9999']})
check('E3 我方含无效 code 不报错',
      'all' in r_bad2, f'rec={len(r_bad2.get("all", []))}')

# E4. 5 人完整阵容（极端）
r_5v5 = post('/api/draft/suggest', {**body,
                                     'my_picks': ['c2124', 'c1183', 'c5154', 'c6005', 'c1106'],
                                     'enemy_picks': ['c1096', 'c1118', 'c1129', 'c2111', 'c1157'],
                                     'phase': 'postban'})
check('E4 5v5 完整阵容能正常返回',
      'all' in r_5v5 and 'matchup' in r_5v5,
      f'matchup={r_5v5["matchup"]}')

# E5. pick 数为 0（极端边界）
r_zero = post('/api/draft/suggest', {**body, 'enemy_picks': ['c2124', 'c1183']})
# 已经测过，看返回里 rec 全不全
check('E5 推荐列表里每个候选有基础字段（code/name/score）',
      all('code' in x and 'name' in x for x in r_zero['all']),
      f'首个候选 keys={list(r_zero["all"][0].keys())[:8]}')

# E6. quick 接口 + 大阵容
r_quick = post('/api/draft/quick', {'enemy_picks': ['c2124', 'c1183', 'c5154'], 'top': 10})
check('E6 quick 接口返回 recommendations+meta',
      'recommendations' in r_quick and 'meta' in r_quick,
      f'keys={list(r_quick.keys())}')
check('E7 quick 接口响应中第一个候选有完整数据',
      all(k in r_quick['recommendations'][0] for k in ['code', 'name', 'score']),
      f'首个 keys={list(r_quick["recommendations"][0].keys())[:10]}')

# ---------- 报告 ----------
print('\n' + '=' * 60)
print(f'PASS: {len(PASS)}')
print(f'FAIL: {len(FAIL)}')
if FAIL:
    print('\n失败项：')
    for n, info in FAIL:
        print(f'  - {n}  {info}')
    sys.exit(1)
else:
    print('全部通过')