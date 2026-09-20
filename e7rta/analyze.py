"""分析层 demo：基于已落库数据跑 RTA 榜单。

用法：python analyze.py
数据来源：e7rta/data.db（battles / battle_picks / battle_bans / heroes）
"""
import sqlite3
from collections import Counter, defaultdict

DB = "E:/第七史诗查询工具/e7rta/data.db"


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    hero_name = dict(cur.execute("SELECT code, name FROM heroes").fetchall())
    total_battles = cur.execute("SELECT COUNT(*) FROM battles").fetchone()[0]
    total_my = cur.execute("SELECT COUNT(*) FROM battle_picks WHERE side='my'").fetchone()[0]
    total_ban = cur.execute("SELECT COUNT(*) FROM battle_bans WHERE side='my'").fetchone()[0]
    print(f"数据集：{total_battles} 场对局 / {total_my} 条我方出场 / {total_ban} 条我方 ban\n")

    def top(title, counter, denom, min_n=0):
        print(f"=== {title} ===")
        for i, (code, cnt) in enumerate(counter.most_common(12), 1):
            if cnt < min_n:
                continue
            name = hero_name.get(code, code)
            print(f"  {i:2d}. {name}({code})  {cnt}  ({100*cnt/denom:.1f}%)")
        print()

    # 出场率
    pick = Counter(c for (c,) in cur.execute("SELECT hero_code FROM battle_picks WHERE side='my'"))
    top("英雄出场次数 (我方)", pick, total_my)
    # ban率
    ban = Counter(c for (c,) in cur.execute("SELECT hero_code FROM battle_bans WHERE side='my'"))
    top("英雄被 ban 次数 (我方)", ban, total_ban)

    # 胜率（样本>=15）
    play = Counter(); win = Counter()
    for code, iswin in cur.execute(
        "SELECT bp.hero_code, b.is_win FROM battle_picks bp JOIN battles b ON bp.battle_seq=b.battle_seq WHERE bp.side='my'"
    ):
        play[code] += 1
        if iswin:
            win[code] += 1
    wr = [(c, win[c], play[c]) for c in play if play[c] >= 15]
    wr.sort(key=lambda x: x[1]/x[2], reverse=True)
    print("=== 英雄胜率 Top 12 (样本>=15 场) ===")
    for i, (c, w, p) in enumerate(wr[:12], 1):
        print(f"  {i:2d}. {hero_name.get(c,c)}({c})  {100*w/p:.1f}%  ({w}/{p})")
    print()

    # 属性 / 职业
    attr = Counter(a for (a,) in cur.execute("SELECT attribute_cd FROM battle_picks WHERE side='my'"))
    job = Counter(j for (j,) in cur.execute("SELECT job_cd FROM battle_picks WHERE side='my'"))
    print("=== 属性分布 (我方出场) ===")
    for a, c in attr.most_common():
        print(f"  {a}: {c} ({100*c/total_my:.1f}%)")
    print("\n=== 职业分布 (我方出场) ===")
    for j, c in job.most_common():
        print(f"  {j}: {c} ({100*c/total_my:.1f}%)")
    print()

    # pick 顺序（先手率）
    po = Counter(p for (p,) in cur.execute("SELECT pick_order FROM battle_picks WHERE side='my'"))
    print("=== pick 顺序分布 (我方) ===")
    for p in sorted(po):
        print(f"  pick {p}: {po[p]} ({100*po[p]/total_my:.1f}%)")

    conn.close()


if __name__ == "__main__":
    main()
