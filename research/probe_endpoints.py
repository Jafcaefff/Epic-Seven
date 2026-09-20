import urllib.request, json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
BASE = "https://e7stats.qyzlgame.com"
cands = ["getBattleList","getBattleDetail","getBattleInfo","getHeroStats","getHeroData","getHeroInfo",
         "getHeroRank","getHeroWinRate","getRankList","getWorldRankList","getRank","getWorldRank",
         "getTopRank","getSeasonList","getSeasonInfo","getSeason","getUserRank","getUserInfo",
         "getUserData","getWorldUser","getWorldRankList","getServerList","getGameData","getServerData",
         "getStatsData","getUserStats","getArenaData","getRtaData","getWorldStats","getWorldInfo"]

def post(path, params):
    url = BASE + "/gameApi/" + path
    q = "&".join(f"{k}={v}" for k, v in params.items())
    h = {"User-Agent": UA, "Referer": BASE + "/", "Content-Type": "application/x-www-form-urlencoded"}
    req = urllib.request.Request(url, data=q.encode(), headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.headers.get("Content-Type"), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type"), e.read()

params = {"nick_no": "1100111328105", "world_code": "world_zlong1", "lang": "zh-CN", "season_code": ""}
print("=== gameApi 候选端点探测 ===")
for c in cands:
    s, ct, b = post(c, params)
    txt = b.decode("utf-8", "replace")
    is_json = txt.strip().startswith(("{", "["))
    print(f"{c:18s} {s} ct={ct} json={is_json} len={len(b)} head={txt[:100].replace(chr(10),' ')}")
