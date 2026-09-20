#!/usr/bin/env python3
"""
策略审查：BP 系统的推荐是否真的有意义
- 真首抢王：1选榜是否都是当前版本强势
- ban 推荐：preban 是否能 ban 出版本强势
- 联动态势：阵容逐渐增加时推荐应该明显变化
- matchup：对称阵容应接近 0，强 vs 弱应该 ±20+
- 视角差异：我方 vs 敌方 推荐差异是否合理
- 评分权重：克制权重应该主导（敌 1 选强力辅助时克制英雄顶到第 1）
"""
import sys, json, urllib.request

sys.path.insert(0, 'E:/第七史诗查询工具/e7rta')

BASE = 'http://127.0.0.1:8799'


def post(path, body, timeout=30):
    req = urllib.request.Request(BASE + path,
                                 data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def header(t):
    print(f'\n--- {t} ---')


# ---------------- 1. 真首抢王 ----------------
header('1. 真首抢王 (1选榜 top 10)')
r = post('/api/draft/suggest', {'hand': 'first', 'side': 'me',
                                 'my_picks': [], 'enemy_picks': [],
                                 'my_bans': [], 'enemy_bans': [],
                                 'phase': 'pick', 'season': None})
print('1选 top 10:')
for i, x in enumerate(r['my_picks'][:10]):
    lu = f"阵容{x['counter_score']}%" if x.get('counter_src') == 'lineup' else f"自身{x['self_win_rate']}%"
    print(f'  {i+1:2d}. {x["name"]:8s} score={x["score"]:.3f} ({lu}) 1选率={x["pos_rate"]}% 第1选场次={x["pos_games"]} 自身强度={x["self_win_rate"]}%')

# ss21 当前版本强势英雄（常识）
known_strong = ['组长亚露嘉', '艾丝黛', '利纳柯', '里安娜路西艾拉', '天秤之主',
                '调香师维波里丝', '诺托斯', '黎洁特', '执行官维德瑞']
top10_names = {x['name'] for x in r['my_picks'][:10]}
hit = sum(1 for n in known_strong if n in top10_names)
print(f'\n版本强势命中: {hit}/{len(top10_names)} ({top10_names & set(known_strong)})')


# ---------------- 2. preban 推荐 ----------------
header('2. preban 推荐 top 10')
r = post('/api/draft/suggest', {'hand': 'first', 'side': 'me',
                                 'my_picks': [], 'enemy_picks': [],
                                 'my_bans': [], 'enemy_bans': [],
                                 'phase': 'preban', 'season': None})
print('preban top 10:')
for i, b in enumerate(r['my_bans'][:10]):
    print(f'  {i+1:2d}. {b["name"]:8s} ban_score={b["ban_score"]:.3f} '
          f'威胁WR={b["threat_win_rate"]}% 出场率={b["pick_rate"]}% '
          f'meta_preban={b.get("meta_preban")}%')

ban_top_names = {b['name'] for b in r['my_bans'][:10]}
ban_hit = sum(1 for n in known_strong if n in ban_top_names)
print(f'\n版本强势被 ban: {ban_hit}/{len(ban_top_names)} (推荐合理)')


# ---------------- 3. 联动态势 ----------------
header('3. 阵容逐渐增加时推荐变化')
last_top5 = None
changes = []
for n_en in range(0, 6):
    en = ['c2124', 'c1183', 'c5154', 'c6005', 'c1106'][:n_en]
    r = post('/api/draft/suggest', {'hand': 'first', 'side': 'me',
                                     'my_picks': [], 'enemy_picks': en,
                                     'my_bans': [], 'enemy_bans': [],
                                     'phase': 'pick', 'season': None})
    top5 = [x['code'] for x in r['my_picks'][:5]]
    if last_top5 is not None:
        diff = sum(1 for c in top5 if c not in last_top5)
        changes.append((n_en, diff))
    print(f'  敌 {n_en} 人: top5 = {[r["my_picks"][i]["name"] for i in range(5)]}')
    last_top5 = top5

print(f'\n阵容增加时前 5 名变化次数: {changes}')
print(f'平均每次新增人数带来 {sum(c for _, c in changes)/len(changes):.1f} 位变化')


# ---------------- 4. matchup 预测 ----------------
header('4. matchup 终局胜率')
scenarios = [
    ('空阵容', [], []),
    ('强 vs 弱', ['c2124', 'c1183', 'c5154', 'c6005', 'c1106'], ['c9991', 'c9992', 'c9993', 'c9994', 'c9995']),  # 弱队用无效 code
    ('版本强 vs 冷门', ['c2124', 'c1183', 'c5154', 'c6005', 'c1106'], ['c1401', 'c1402', 'c1403', 'c1404', 'c1405']),
    ('版本强 vs 版本强', ['c2124', 'c1183', 'c5154', 'c6005', 'c1106'], ['c2185', 'c2181', 'c2186', 'c6005', 'c5154']),
]
for name, my, en in scenarios:
    r = post('/api/draft/suggest', {'hand': 'first', 'side': 'me',
                                     'my_picks': my, 'enemy_picks': en,
                                     'my_bans': [], 'enemy_bans': [],
                                     'phase': 'pick', 'season': None})
    m = r['matchup']
    print(f'  {name}: my_wr={m["my_wr"]}% en_wr={m["enemy_wr"]}% advantage={m["advantage"]:+.1f}')


# ---------------- 5. 视角差异 ----------------
header('5. 我方视角 vs 敌方视角（敌方有 1 选时）')
en = ['c5154']
r_me = post('/api/draft/suggest', {'hand': 'first', 'side': 'me',
                                     'my_picks': [], 'enemy_picks': en,
                                     'my_bans': [], 'enemy_bans': [],
                                     'phase': 'pick', 'season': None})
r_en = post('/api/draft/suggest', {'hand': 'first', 'side': 'enemy',
                                     'my_picks': [], 'enemy_picks': en,
                                     'my_bans': [], 'enemy_bans': [],
                                     'phase': 'pick', 'season': None})

print(f'我方 top5: {[x["name"] for x in r_me["my_picks"][:5]]}')
print(f'敌方 top5: {[x["name"] for x in r_en["all"][:5]]}')
diff_codes = set(x['code'] for x in r_me['my_picks'][:5]) ^ set(x['code'] for x in r_en['all'][:5])
print(f'两视角 top5 中不一致英雄: {diff_codes}')


# ---------------- 6. 评分权重合理性 ----------------
header('6. 评分权重验证（克制权重应主导）')
en = ['c5154']  # 调香师维波里丝
r = post('/api/draft/suggest', {'hand': 'first', 'side': 'me',
                                 'my_picks': [], 'enemy_picks': en,
                                 'my_bans': [], 'enemy_bans': [],
                                 'phase': 'pick', 'season': None})
# 利纳柯(c1168) 对位 c5154 应该 top
top1 = r['my_picks'][0]
print(f'  敌 1 选 c5154 时 top1: {top1["name"]} score={top1["score"]:.3f} counter_score={top1["counter_score"]}% self_wr={top1["self_win_rate"]}%')
print(f'  判断: counter_score > self_wr → {"是(克制主导)" if top1["counter_score"] > top1["self_win_rate"] else "否"}')

# 换成克 制 弱 阵容（挑个数据少的）
en_weak = ['c1401']  # 冷门
r = post('/api/draft/suggest', {'hand': 'first', 'side': 'me',
                                 'my_picks': [], 'enemy_picks': en_weak,
                                 'my_bans': [], 'enemy_bans': [],
                                 'phase': 'pick', 'season': None})
print(f'  敌 1 选 c1401 (冷门) 时 top1: {r["my_picks"][0]["name"]} src={r["my_picks"][0].get("counter_src")}')

# ---------------- 7. 终局胜率（双方都强 vs 我方降权） ----------------
header('7. 我方阵容被 ban/pick 削弱时胜率下降')
# 我方用真强势阵容 vs 敌方 0 人
r_full = post('/api/draft/suggest', {'hand': 'first', 'side': 'me',
                                      'my_picks': ['c2124', 'c1183', 'c5154', 'c6005', 'c1106'],
                                      'enemy_picks': [],
                                      'my_bans': [], 'enemy_bans': [],
                                      'phase': 'pick', 'season': None})
print(f'  满阵容 vs 0人: my_wr={r_full["matchup"]["my_wr"]}%')

# 我方只留 1 个 3 星（低星 = 弱）
r_weak = post('/api/draft/suggest', {'hand': 'first', 'side': 'me',
                                      'my_picks': ['c1401', 'c1402', 'c1403', 'c1404', 'c1405'],
                                      'enemy_picks': [],
                                      'my_bans': [], 'enemy_bans': [],
                                      'phase': 'pick', 'season': None})
print(f'  冷门 5 人 vs 0人: my_wr={r_weak["matchup"]["my_wr"]}% (应该更低)')

# ---------------- 8. 选位常用度乘数 ----------------
header('8. 选位常用度乘数（1选率0 不该顶进前排）')
# 选 3 选 (len(my_picks)=2, slot=3)，看 top1 的 pos_rate
my = ['c2124', 'c1183']
r = post('/api/draft/suggest', {'hand': 'first', 'side': 'me',
                                 'my_picks': my, 'enemy_picks': [],
                                 'my_bans': [], 'enemy_bans': [],
                                 'phase': 'pick', 'season': None})
top1 = r['my_picks'][0]
print(f'  第 3 选 top1: {top1["name"]} score={top1["score"]:.3f} pos_rate={top1["pos_rate"]}% pos_games={top1["pos_games"]}')
print(f'  判断: pos_games 应该 > 100 且 pos_rate > 2% → {"是" if top1["pos_games"] > 100 and top1["pos_rate"] > 2 else "否"}')

# top10 中 0 选位率数
zero_pos = sum(1 for x in r['my_picks'][:10] if x.get('pos_games', 0) == 0)
print(f'  top10 中 0 选位率的英雄: {zero_pos}')