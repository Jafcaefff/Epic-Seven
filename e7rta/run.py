"""主入口：导入静态数据 → 遍历玩家抓取 ss17+ 对局 → 落库 → 打印统计。

用法：
  python run.py small [limit]   小规模验证（默认 80 玩家，断点续传）
  python run.py full            全量（遍历所有未抓玩家）
"""
import sys
from datetime import datetime, timezone

import config
import db
from importer import import_static, import_seasons
from crawler import crawl_player

DB = "E:/第七史诗查询工具/e7rta/data.db"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "small"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else (80 if mode == "small" else 0)
    conn = db.connect(DB)

    print("[1/3] 导入静态数据...")
    n_u, n_h, n_e = import_static(conn)
    print(f"      玩家 {n_u} / 英雄 {n_h} / 装备 {n_e}")
    seasons = import_seasons(conn)
    print(f"      目标赛季(>=ss17): {seasons}")

    cur = conn.cursor()
    if limit and limit > 0:
        cur.execute(
            """SELECT p.nick_no FROM players p
               WHERE p.nick_no NOT IN (SELECT nick_no FROM crawl_progress)
               ORDER BY p.rowid LIMIT ?""",
            (limit,),
        )
    else:
        cur.execute(
            """SELECT p.nick_no FROM players p
               WHERE p.nick_no NOT IN (SELECT nick_no FROM crawl_progress)"""
        )
    todos = [r[0] for r in cur.fetchall()]
    print(f"\n[2/3] 待抓玩家: {len(todos)}")

    done = empty = err = 0
    for i, no in enumerate(todos, 1):
        n = None
        status = "error"
        errmsg = None
        try:
            n = crawl_player(conn, no)
            status = "done" if n and n > 0 else "empty"
        except Exception as e:  # noqa: BLE001
            errmsg = str(e)[:200]
        conn.execute(
            "INSERT OR REPLACE INTO crawl_progress (nick_no, status, battles, error, fetched_at) VALUES (?,?,?,?,?)",
            (no, status, n or 0, errmsg, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        if status == "done":
            done += 1
        elif status == "empty":
            empty += 1
        else:
            err += 1
        if i % 10 == 0 or i == len(todos):
            print(f"      [{i}/{len(todos)}] done={done} empty={empty} err={err}")

    print("\n[3/3] 抓取统计")
    cur.execute("SELECT COUNT(*) FROM battles")
    nb = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM battle_picks")
    np_ = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM battle_bans")
    nbans = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM battles WHERE my_team IS NOT NULL AND my_team != '[]'")
    n_with_team = cur.fetchone()[0]
    print(f"  对局总数: {nb}")
    if nb:
        print(f"  有阵容的对局: {n_with_team} ({100*n_with_team/nb:.1f}%)")
    print(f"  出场记录: {np_} / ban 记录: {nbans}")
    cur.execute("SELECT season_code, COUNT(*) FROM battles GROUP BY season_code ORDER BY season_code")
    for sc, c in cur.fetchall():
        print(f"    {sc}: {c}")
    conn.close()


if __name__ == "__main__":
    main()
