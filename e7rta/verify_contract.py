"""用前端真实 payload 形状验证后端（my_bans/enemy_bans 为纯 code 字符串数组）。"""
import json, threading, time, urllib.request
import server as S

httpd = S.ThreadingHTTPServer(("127.0.0.1", 8799), S.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
time.sleep(0.5)

def post(payload):
    r = urllib.request.Request("http://127.0.0.1:8799/api/draft/suggest",
        data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except Exception as e:
        return "ERR", str(e)

# 前端真实 payload：my_bans/enemy_bans = 纯字符串数组
p1 = {"hand":"first","season":None,"phase":"pick",
      "my_picks":["c2124"],"enemy_picks":["c2038"],
      "my_bans":["c2007"],"enemy_bans":["c1183"]}
st, d = post(p1)
codes = [x["code"] for x in d["my_picks"]]
print("pick 阶段 my_picks 推荐前8:", codes[:8])
assert st == 200, f"HTTP {st}"
assert "c2007" not in codes, "FAIL: 已ban c2007 未被排除"
assert "c1183" not in codes, "FAIL: 已ban c1183 未被排除"
assert "c2124" not in codes, "FAIL: 已选 c2124 未被排除"
assert "c2038" not in codes, "FAIL: 已选敌方 c2038 未被排除"
print("  PASS: 纯字符串 ban 数组正确排除")

# postban：敌方已选真实英雄, 第3选 c5154 受保护
p2 = {"hand":"first","season":None,"phase":"postban",
      "my_picks":["c6005","c2076","c1168","c1183","c2007"],
      "enemy_picks":["c2007","c1183","c5154","c2185","c2124"],
      "my_bans":[],"enemy_bans":[]}
st, d = post(p2)
ban = [x["code"] for x in d["my_bans"]]
print("postban ban 推荐:", ban)
assert st == 200
assert "c5154" not in ban, "FAIL: 第3选未受保护"
assert all(c in p2["enemy_picks"] for c in ban), "FAIL: 出现非敌方已选英雄"
print("  PASS: postban 仅敌方已选且第3选受保护")

# preban 阶段（全局威胁兜底）
p3 = {"hand":"first","season":None,"phase":"preban",
      "my_picks":[],"enemy_picks":[],"my_bans":[],"enemy_bans":[]}
st, d = post(p3)
print("preban ban 推荐前5:", [(x["name"], x["ban_score"]) for x in d["my_bans"][:5]])
assert st == 200 and len(d["my_bans"]) > 0
print("  PASS: preban 全局兜底正常")

httpd.shutdown()
print("\nALL FRONTEND-PAYLOAD TESTS PASSED")
