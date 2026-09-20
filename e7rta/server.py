"""第七史诗 RTA 数据中心 — 后端服务（零依赖，标准库）。

端口 8799。提供 REST API + 静态前端（static/index.html）。
"""
import json
import os
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import analytics as A
import draft as D

_META_CACHE = {"ts": 0, "data": None}
META_TTL = 3600   # 1 小时缓存
def _meta_snapshot():
    import time as _t
    now = _t.time()
    if _META_CACHE["data"] and now - _META_CACHE["ts"] < META_TTL:
        return _META_CACHE["data"]
    fp = os.path.join(os.path.dirname(__file__), "data", "meta_snapshot.json")
    if not os.path.exists(fp):
        return {"error": "no meta snapshot yet, run fetch_meta.py"}
    with open(fp, encoding="utf-8") as f:
        d = json.load(f)
    _META_CACHE["data"] = d
    _META_CACHE["ts"] = now
    return d

DB = "E:/第七史诗查询工具/e7rta/data.db"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
PORT = 8799


def get_seasons():
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT season_code, COUNT(*) FROM battles GROUP BY season_code ORDER BY season_code"
    ).fetchall()
    conn.close()
    return [{"code": r[0], "count": r[1]} for r in rows]


def _json_body(handler):
    length = int(handler.headers.get("Content-Length", 0) or 0)
    if length == 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8", "ignore")
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _send(handler, obj, status=200):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def _q(self):
        return parse_qs(urlparse(self.path).query)

    def do_GET(self):
        path = urlparse(self.path).path
        q = self._q()
        season = q.get("season", [None])[0]

        if path in ("/", "/index.html"):
            self._serve_static("index.html")
            return
        if path in ("/draft", "/draft.html"):
            self._serve_static("draft.html")
            return

        if path == "/api/seasons":
            return _send(self, get_seasons())
        if path == "/api/overview":
            return _send(self, A.overview(season))
        if path == "/api/heroes":
            return _send(self, A.hero_catalog())
        if path == "/api/hero-stats":
            return _send(self, A.hero_stats(season))
        if path == "/api/matchup":
            hero = q.get("hero", [None])[0]
            if not hero:
                return _send(self, {"error": "missing hero"}, 400)
            return _send(self, A.matchup(hero, season))
        if path == "/api/pickorder":
            return _send(self, A.pick_order_stats(season))
        if path == "/api/recent":
            limit = int(q.get("limit", [30])[0])
            return _send(self, A.recent_matches(limit, season))
        if path == "/api/match":
            seq = q.get("seq", [None])[0]
            if not seq:
                return _send(self, {"error": "missing seq"}, 400)
            return _send(self, A.match_detail(seq) or {"error": "not found"}, 404 if not A.match_detail(seq) else 200)
        if path == "/api/draft/sequence":
            hand = q.get("hand", ["first"])[0]
            preban = int(q.get("preban", [1])[0])
            return _send(self, {"steps": D.rta_steps(hand, preban)})
        if path == "/api/meta":
            return _send(self, _meta_snapshot())
        # 静态文件兜底（css/js/png 等）
        rel = path.lstrip("/")
        fp = os.path.join(STATIC_DIR, rel)
        if os.path.isfile(fp):
            self._serve_file(fp)
            return
        return _send(self, {"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = _json_body(self)
        if path == "/api/recommend":
            my = body.get("my_picks", [])
            enemy_pick = body.get("enemy_picks", [])
            enemy_ban = body.get("enemy_bans", [])
            season = body.get("season")
            return _send(self, A.recommend(my, enemy_pick, enemy_ban, season))
        if path == "/api/draft/suggest":
            return _send(self, D.suggest(body))
        if path == "/api/draft/quick":
            # MuMu 极简接口：只输入敌方阵容 -> 推荐列表（不参与 BP 步进）
            enemy = body.get("enemy_picks", [])
            top = int(body.get("top", 20))
            season = body.get("season")
            return _send(self, D.quick_recommend(enemy, top, season))
        return _send(self, {"error": "not found"}, 404)

    def _serve_static(self, name):
        fp = os.path.join(STATIC_DIR, name)
        self._serve_file(fp)

    _CT = {
        ".html": "text/html; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
    }

    def _serve_file(self, fp):
        if not os.path.isfile(fp):
            self.send_error(404)
            return
        ext = os.path.splitext(fp)[1].lower()
        ctype = self._CT.get(ext, "application/octet-stream")
        with open(fp, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # 静默日志
        pass


def main():
    os.makedirs(STATIC_DIR, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"RTA 数据中心已启动: http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
