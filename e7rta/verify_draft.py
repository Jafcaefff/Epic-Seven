"""draft.py 修复后端到端验证（不依赖 HTTP）。"""
import draft as D
from pprint import pprint

# 1) 基础序列（先手 / 后手 / 大师+）
print("=== rta_steps(first, preban=1) ===")
for s in D.rta_steps("first", 1):
    print(" ", s)
print("\n=== rta_steps(second, preban=2) ===")
for s in D.rta_steps("second", 2):
    print(" ", s)

# 2) 关键 bug：ban 以 {code,pre} 字典传入时，必须被排除出推荐
print("\n=== 验证 ban 字典被排除（之前 bug：taken 用 set(my_bans) 字典集合导致未排除）===")
ep = ["c2038", "c1127", "c2007"]  # 敌方已选
# 我方已选一个，且把 c2124、c1127 列为 ban（字典形式）
state = {
    "hand": "first",
    "my_picks": ["c2124"],
    "enemy_picks": ep,
    "my_bans": [{"code": "c1127", "pre": True}],   # 已被我方 ban
    "enemy_bans": [{"code": "c2007", "pre": False}],
    "phase": "pick",
    "season": None,
}
r = D.suggest(state)
my_codes = [x["code"] for x in r["my_picks"]]
print("  我方推荐前 6:", my_codes[:6])
assert "c1127" not in my_codes, "FAILED: 已ban英雄 c1127 仍出现在推荐"
assert "c2007" not in my_codes, "FAILED: 已ban英雄 c2007 仍出现在推荐"
assert "c2124" not in my_codes, "FAILED: 已选英雄 c2124 仍出现在推荐"
print("  PASS: 已ban/已选英雄均被排除")

# 3) postban 阶段：ban 推荐只能来自敌方已选，且排除第3选(index 2)
print("\n=== postban 我方 ban 推荐（只能 ban 敌方已选, 排除 index2）===")
enemy_real = ["c2007", "c1183", "c5154", "c2185", "c2124"]  # 真实高登场码, index2=c5154 受保护
state2 = {
    "hand": "first",
    "my_picks": ["c6005", "c2076", "c1168", "c1183", "c2007"],
    "enemy_picks": enemy_real,
    "my_bans": [], "enemy_bans": [],
    "phase": "postban", "season": None,
}
r2 = D.suggest(state2)
ban_codes = [x["code"] for x in r2["my_bans"]]
print("  ban 推荐:", ban_codes[:6])
assert "c5154" not in ban_codes, "FAILED: 第3选 c5154 受保护仍被推荐 ban"
assert all(c in state2["enemy_picks"] for c in ban_codes), "FAILED: 出现非敌方已选英雄"
print("  PASS: 仅敌方已选, 第3选受保护正确")

# 4) hand=second 全流程不崩溃（之前 RemoteDisconnected）
print("\n=== hand=second 全流程逐步 suggest（含 ban 字典）===")
steps = D.rta_steps("second", 1)
my_picks, enemy_picks, my_bans, enemy_bans = [], [], [], []
for st in steps:
    phase = st["phase"]
    side = st["side"]
    state = {
        "hand": "second",
        "my_picks": my_picks, "enemy_picks": enemy_picks,
        "my_bans": my_bans, "enemy_bans": enemy_bans,
        "phase": phase, "season": None,
    }
    rr = D.suggest(state)
    if side == "me" and phase == "postban":
        # 模拟我方 ban 敌方一名（非第3选）
        cand = [c for c in enemy_picks if enemy_picks.index(c) != 2][:1]
        for c in cand:
            my_bans.append({"code": c, "pre": False})
    if side == "enemy" and phase == "postban":
        cand = [c for c in my_picks if my_picks.index(c) != 2][:1]
        for c in cand:
            enemy_bans.append({"code": c, "pre": False})
    print(f"  {side:5} {phase:7} -> my_rec={len(rr['my_picks'])} ban_rec={len(rr['my_bans'])} enemy_rec={len(rr['enemy_picks'])}")
print("  PASS: hand=second 全流程无异常")

print("\nALL TESTS PASSED")
