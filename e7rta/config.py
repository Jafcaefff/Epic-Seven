"""第七史诗 RTA 数据层配置与 API 封装。

所有 API 均为 POST + form-urlencoded + Referer 头。
原项目用 query string 传参会被 SPA 壳兜底成 HTML，必须用 body。
"""
import urllib.request
import urllib.parse
import json
import time

API_BASE = "https://e7stats.qyzlgame.com/gameApi/"
STATIC_BASE = "https://media.zlongame.com/media/pictures/qy/e7/actv/2023/Epic7_Stats/json/"
WORLD_CODE = "world_zlong1"
LANG = "zh-CN"
REFERER = "https://e7stats.qyzlgame.com/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 只抓阵容完整的赛季：ss17(2025夏) 及以后（见研究报告第 4 节规律）
MIN_SEASON = "ss17"

# 抓取限流（秒）。保守值，避免触发风控。
REQUEST_INTERVAL = 0.6
RETRY = 3
RETRY_BACKOFF = 2.0


def _post(endpoint: str, params: dict, timeout: int = 30):
    """POST form 数据到 e7stats gameApi，返回解析后的 JSON。"""
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        API_BASE + endpoint,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": REFERER,
            "User-Agent": UA,
        },
        method="POST",
    )
    last_err = None
    for _ in range(RETRY):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(RETRY_BACKOFF)
    raise RuntimeError(f"{endpoint} failed after {RETRY} retries: {last_err}")


def get_battle_list(nick_no, season_code=None):
    p = {"nick_no": nick_no, "world_code": WORLD_CODE, "lang": LANG}
    if season_code:
        p["season_code"] = season_code
    return _post("getBattleList", p)


def get_battle_detail(nick_no, battle_seq, season_code):
    p = {
        "nick_no": nick_no,
        "battle_seq": battle_seq,
        "world_code": WORLD_CODE,
        "lang": LANG,
        "season_code": season_code,
    }
    return _post("getBattleDetail", p)


def get_season_list():
    return _post("getSeasonList", {"world_code": WORLD_CODE, "lang": LANG})


def get_user_info(nick_no):
    return _post("getUserInfo", {"nick_no": nick_no, "world_code": WORLD_CODE, "lang": LANG})


def fetch_static_json(filename: str):
    """下载静态 CDN 上的 JSON（玩家/英雄/装备映射）。"""
    url = STATIC_BASE + filename
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": REFERER})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))
