"""进程内 HTTP 验证：在同一进程起 server，用 urllib 直接请求，绕开沙箱跨进程网络问题。"""
import threading, urllib.request, json, time
import server as S

httpd = S.ThreadingHTTPServer(("127.0.0.1", 8799), S.Handler)
t = threading.Thread(target=httpd.serve_forever, daemon=True)
t.start()
time.sleep(0.5)

def req(method, path, data=None):
    url = "http://127.0.0.1:8799" + path
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(url, data=body, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            raw = resp.read()
            return resp.status, len(raw), raw[:200]
    except Exception as e:
        return "ERR", str(e), ""

print("sequence:", req("GET", "/api/draft/sequence?hand=first&preban=1")[0], "len", req("GET","/api/draft/sequence?hand=first&preban=1")[1])
st, ln, head = req("POST", "/api/draft/suggest", {"hand":"first","my_picks":["c2124"],"enemy_picks":["c2038"],"my_bans":[{"code":"c2007","pre":True}],"enemy_bans":[],"phase":"pick","season":None})
print("suggest status:", st, "len:", ln, "head:", head)
st, ln, head = req("GET", "/draft")
print("draft.html status:", st, "len:", ln)
st, ln, head = req("GET", "/api/seasons")
print("seasons status:", st, "len:", ln)

# 连续 5 次请求看是否稳定
print("\n--- 连续 5 次 sequence 请求 ---")
for i in range(5):
    st, ln, _ = req("GET", "/api/draft/sequence?hand=second")
    print(f"  #{i+1}: {st} len={ln}")

httpd.shutdown()
print("\nDONE")
