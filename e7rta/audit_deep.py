#!/usr/bin/env python3
"""
策略深度审查：BP 中途联动、matchup 动态、选位常用度按位次生效
"""
import sys, json, urllib.request
sys.path.insert(0, 'E:/第七史诗查询工具/e7rta')

BASE = 'http://127.0.0.1:8799'


def post(p, b, t=30):
    req = urllib.request.Request(BASE+p, data=json.dumps(b).encode(),
                                  headers={'Content-Type':'application/json'})
    return json.load(urllib.request.urlopen(req, timeout=t))


def h(t): print(f'\n--- {t} ---')


# 1. 我方 1 选 + 敌方 1 选时推荐是否真正互动
h('1. 早期联动: 我方选好 c1168 (利纳柯) 后，敌1选不同英雄 推荐是否变')
base = {'hand':'first','side':'me','my_picks':['c1168'],'enemy_picks':[],
        'my_bans':[],'enemy_bans':[],'phase':'pick','season':None}
r0 = post('/api/draft/suggest', base)
print(f'  敌0人 top3: {[x["name"] for x in r0["my_picks"][:3]]}')
for en in ['c5154', 'c1106', 'c1401', 'c1183']:
    body = {**base, 'enemy_picks': [en]}
    r = post('/api/draft/suggest', body)
    top3 = [(x['name'], round(x['score'],3)) for x in r['my_picks'][:3]]
    print(f'  敌1选 {en}: {top3}')


# 2. 选位常用度乘数在每个位次（1-5 选）是否生效
h('2. 选位常用度按位次生效')
for n_my in range(0, 5):
    body = {'hand':'first','side':'me',
            'my_picks':['c2124','c1183','c5154','c6005'][:n_my],
            'enemy_picks':[],'my_bans':[],'enemy_bans':[],
            'phase':'pick','season':None}
    r = post('/api/draft/suggest', body)
    slot = min(n_my+1, 5)
    # 看 top5 中 pos_games<30 的数量（说明该位几乎不出）
    pos0 = sum(1 for x in r['my_picks'][:10] if x.get('pos_games', 0) < 30)
    print(f'  第 {slot} 选: top1={r["my_picks"][0]["name"]} pos_games={r["my_picks"][0]["pos_games"]} '
          f'pos_rate={r["my_picks"][0]["pos_rate"]}% | top10中0选位={pos0}/10')


# 3. matchup 是否随我方选人动态变化
h('3. matchup 动态变化 (我方依次加英雄)')
en_team = ['c5154', 'c2124', 'c1183', 'c6005', 'c1106']
my_teams = [
    [],
    ['c1168'],  # 利纳柯 counter 调香师
    ['c1168', 'c2185'],  # + 里安娜 counter 亚露嘉
    ['c1168', 'c2185', 'c6005'],  # + 天秤之主
    ['c1168', 'c2185', 'c6005', 'c1401'],  # + 冷门（弱）
    ['c1168', 'c2185', 'c6005', 'c1401', 'c1402'],  # 全弱
]
print('  敌:', [x['name'] for x in map(lambda c: {'name':'', 'code':c}, en_team)])  # 简化输出
for my in my_teams:
    body = {'hand':'first','side':'me','my_picks':my,'enemy_picks':en_team,
            'my_bans':[],'enemy_bans':[],'phase':'pick','season':None}
    r = post('/api/draft/suggest', body)
    m = r['matchup']
    print(f'  我 {len(my)} 人 ({my}) vs 敌 5 人: my_wr={m["my_wr"]}% advantage={m["advantage"]}')


# 4. 对手全是无效 code 时 matchup 不应该乱出数字
h('4. 无效 code 容错')
body = {'hand':'first','side':'me','my_picks':['c2124','c1183'],
        'enemy_picks':['c9999','c8888'],'my_bans':[],'enemy_bans':[],
        'phase':'pick','season':None}
r = post('/api/draft/suggest', body)
print(f'  敌全无效: my_wr={r["matchup"]["my_wr"]}% advantage={r["matchup"]["advantage"]} cov={r["matchup"].get("coverage")}')


# 5. 我方部分阵容 + 敌方阵容数据不完整
h('5. 数据稀疏的阵容')
body = {'hand':'first','side':'me','my_picks':['c1401','c1402','c1403'],
        'enemy_picks':['c1404','c1405'],'my_bans':[],'enemy_bans':[],
        'phase':'pick','season':None}
r = post('/api/draft/suggest', body)
m = r['matchup']
print(f'  全冷门 vs 全冷门: my_wr={m["my_wr"]}% advantage={m["advantage"]} cov={m.get("coverage")} sample_pairs={m.get("sample_pairs")}')