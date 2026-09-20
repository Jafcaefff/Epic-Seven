"""SQLite 数据库 schema 与基础操作。

表设计：
- players / heroes / equips / seasons：维度表（来自静态 JSON + getSeasonList）
- battles：对局主表（保留原始阵容 JSON，便于回查）
- battle_picks / battle_bans：范式化出场与 ban 位，便于聚合分析
- crawl_progress：断点续传记录（已抓玩家 + 状态）
"""
import sqlite3
import os

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    nick_no   INTEGER PRIMARY KEY,
    nick_nm   TEXT,
    rank      INTEGER,
    code      TEXT
);

CREATE TABLE IF NOT EXISTS heroes (
    code TEXT PRIMARY KEY,
    name TEXT
);

CREATE TABLE IF NOT EXISTS equips (
    code TEXT PRIMARY KEY,
    name TEXT
);

CREATE TABLE IF NOT EXISTS seasons (
    season_code  TEXT PRIMARY KEY,
    season_name TEXT,
    start_date   TEXT,
    end_date     TEXT,
    is_now       INTEGER
);

CREATE TABLE IF NOT EXISTS battles (
    battle_seq     TEXT PRIMARY KEY,
    nick_no        INTEGER,
    season_code    TEXT,
    season_name    TEXT,
    is_win         INTEGER,
    turn           INTEGER,
    battle_time    INTEGER,
    battle_day     TEXT,
    my_team        TEXT,
    enemy_team     TEXT,
    preban_list    TEXT,
    preban_enemy   TEXT,
    raw_team       TEXT,
    raw_preban     TEXT,
    raw_enemy_team TEXT,
    raw_enemy_preban TEXT,
    fetched_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_battles_nick   ON battles(nick_no);
CREATE INDEX IF NOT EXISTS idx_battles_season ON battles(season_code);

CREATE TABLE IF NOT EXISTS battle_picks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    battle_seq   TEXT,
    side         TEXT,            -- 'my' / 'enemy'
    hero_code    TEXT,
    pick_order   INTEGER,
    position     INTEGER,
    artifact     TEXT,
    job_cd       TEXT,
    attribute_cd TEXT,
    grade        TEXT,
    awaken_grade TEXT,
    attack_damage  REAL,
    receive_damage REAL,
    recovery       REAL,
    mvp_point     REAL,
    kill_count    INTEGER,
    level         INTEGER,
    is_mvp        INTEGER,
    respawn       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_picks_hero   ON battle_picks(hero_code);
CREATE INDEX IF NOT EXISTS idx_picks_battle ON battle_picks(battle_seq);

CREATE TABLE IF NOT EXISTS battle_bans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    battle_seq  TEXT,
    side        TEXT,            -- 'my' / 'enemy'
    hero_code   TEXT,
    ban_index   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_bans_hero   ON battle_bans(hero_code);
CREATE INDEX IF NOT EXISTS idx_bans_battle ON battle_bans(battle_seq);

CREATE TABLE IF NOT EXISTS crawl_progress (
    nick_no     INTEGER PRIMARY KEY,
    status      TEXT,            -- 'done' / 'empty' / 'error'
    battles     INTEGER,
    error       TEXT,
    fetched_at  TEXT
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.executescript(SCHEMA)
    # 兼容旧库：crawl_progress 增加 season 列，按赛季独立记录进度
    try:
        conn.execute("ALTER TABLE crawl_progress ADD COLUMN season TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # 列已存在
    return conn


def upsert_battle(conn, b: dict):
    """写入一场对局 + 范式化 picks/bans。b 为已解析的字段字典。"""
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR REPLACE INTO battles
        (battle_seq, nick_no, season_code, season_name, is_win, turn, battle_time,
         battle_day, my_team, enemy_team, preban_list, preban_enemy, raw_team, raw_preban,
         raw_enemy_team, raw_enemy_preban, fetched_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            b["battle_seq"], b["nick_no"], b["season_code"], b["season_name"],
            b["is_win"], b["turn"], b["battle_time"], b["battle_day"],
            b["my_team"], b["enemy_team"], b["preban_list"], b["preban_enemy"],
            b["raw_team"], b["raw_preban"], b["raw_enemy_team"], b["raw_enemy_preban"],
            b["fetched_at"],
        ),
    )
    seq = b["battle_seq"]
    # 去重：先清旧 picks/bans，避免重复抓取叠加
    cur.execute("DELETE FROM battle_picks WHERE battle_seq=?", (seq,))
    cur.execute("DELETE FROM battle_bans WHERE battle_seq=?", (seq,))
    # 范式化 my/enemy 阵容
    for side, team in (("my", b["my_team_parsed"]), ("enemy", b["enemy_team_parsed"])):
        for h in team:
            cur.execute(
                """
                INSERT INTO battle_picks
                (battle_seq, side, hero_code, pick_order, position, artifact, job_cd,
                 attribute_cd, grade, awaken_grade, attack_damage, receive_damage,
                 recovery, mvp_point, kill_count, level, is_mvp, respawn)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    seq, side, h.get("hero_code"), h.get("pick_order"), h.get("position"),
                    h.get("artifact"), h.get("job_cd"), h.get("attribute_cd"),
                    h.get("grade"), h.get("awaken_grade"),
                    _f(h.get("attack_damage")), _f(h.get("receive_damage")),
                    _f(h.get("recovery")), _f(h.get("mvp_point")),
                    _i(h.get("kill_count")), _i(h.get("level")),
                    _i(h.get("mvp")), _i(h.get("respawn")),
                ),
            )
    # 范式化 ban 位
    for side, bans in (("my", b["preban_parsed"]), ("enemy", b["preban_enemy_parsed"])):
        for i, code in enumerate(bans):
            if code:
                cur.execute(
                    "INSERT INTO battle_bans (battle_seq, side, hero_code, ban_index) VALUES (?,?,?,?)",
                    (seq, side, code, i),
                )


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
