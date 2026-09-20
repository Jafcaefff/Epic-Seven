"""第七史诗 RTA 战绩数据看板（零依赖）。

后端：Python 标准库 http.server（从 SQLite 实时读聚合数据）。
前端：原生 HTML/CSS/JS + SVG 图表，无外部 CDN，离线可用。
数据源：e7rta/data.db（battles / battle_picks / battle_bans / heroes）。

启动：  python web.py
访问：  http://localhost:8787
支持赛季筛选：http://localhost:8787/api/stats?season=ss20
"""
import json
import os
import sqlite3
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "data.db")
PORT = 8787
MIN_WR = 15  # 胜率统计最小样本量


# ----------------------------------------------------------------------------
# 聚合逻辑（复用 analyze.py 的口径，结构化输出给前端）
# ----------------------------------------------------------------------------
def _q(cur, sql, params=()):
    return cur.execute(sql, params).fetchall()


def build_stats(season=None):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    hero_name = dict(_q(cur, "SELECT code, name FROM heroes"))

    w = ""
    p = []
    if season:
        w = "WHERE b.season_code=?"
        p = [season]

    total_b = _q(cur, f"SELECT COUNT(*) FROM battles b {w}", p)[0][0]
    if total_b == 0:
        conn.close()
        return {"empty": True}

    base_my = (
        "FROM battle_picks bp JOIN battles b ON bp.battle_seq=b.battle_seq "
        f"WHERE bp.side='my' {w}"
    )
    base_ban = (
        "FROM battle_bans bb JOIN battles b ON bb.battle_seq=b.battle_seq "
        f"WHERE bb.side='my' {w}"
    )

    total_picks = _q(cur, f"SELECT COUNT(*) {base_my}", p)[0][0]
    total_bans = _q(cur, f"SELECT COUNT(*) {base_ban}", p)[0][0]
    n_players = _q(cur, f"SELECT COUNT(DISTINCT nick_no) FROM battles b {w}", p)[0][0]
    n_team = _q(cur, f"SELECT COUNT(*) FROM battles b WHERE my_team IS NOT NULL AND my_team!='[]' {w}", p)[0][0]
    overall_wr = _q(cur, f"SELECT AVG(is_win) FROM battles b {w}", p)[0][0] or 0

    # 出场 Top
    pick = Counter(c for (c,) in _q(cur, f"SELECT bp.hero_code {base_my}", p))
    pick_top = [
        {"code": c, "name": hero_name.get(c, c), "count": n, "rate": round(100 * n / total_picks, 1)}
        for c, n in pick.most_common(20)
    ]

    # ban Top
    ban = Counter(c for (c,) in _q(cur, f"SELECT bb.hero_code {base_ban}", p))
    ban_top = [
        {"code": c, "name": hero_name.get(c, c), "count": n, "rate": round(100 * n / total_bans, 1)}
        for c, n in ban.most_common(20)
    ]

    # 胜率（样本>=MIN_WR）
    play = Counter()
    win = Counter()
    for code, iw in _q(cur, f"SELECT bp.hero_code, b.is_win {base_my}", p):
        play[code] += 1
        if iw:
            win[code] += 1
    wr = [
        {"code": c, "name": hero_name.get(c, c), "wins": win[c], "plays": play[c],
         "rate": round(100 * win[c] / play[c], 1)}
        for c in play if play[c] >= MIN_WR
    ]
    wr.sort(key=lambda x: x["rate"], reverse=True)
    wr = wr[:20]

    # 属性 / 职业分布
    attr = Counter(a for (a,) in _q(cur, f"SELECT bp.attribute_cd {base_my}", p))
    job = Counter(j for (j,) in _q(cur, f"SELECT bp.job_cd {base_my}", p))
    attribute = [
        {"attr": a or "未知", "count": n, "rate": round(100 * n / total_picks, 1)}
        for a, n in attr.most_common()
    ]
    job = [
        {"job": j or "未知", "count": n, "rate": round(100 * n / total_picks, 1)}
        for j, n in job.most_common()
    ]

    # pick 顺序分布
    po = Counter(o for (o,) in _q(cur, f"SELECT bp.pick_order {base_my}", p))
    pick_order = [
        {"order": o, "count": po[o], "rate": round(100 * po[o] / total_picks, 1)}
        for o in sorted(po)
    ]

    # 赛季分布（始终全量，便于看数据来源）
    season_dist = [
        {"season": s, "count": c}
        for s, c in _q(cur, "SELECT season_code, COUNT(*) FROM battles GROUP BY season_code ORDER BY season_code")
    ]
    season_options = [
        {"code": s, "name": n}
        for s, n in _q(cur, "SELECT DISTINCT season_code, season_name FROM battles WHERE season_code IS NOT NULL ORDER BY season_code")
    ]

    conn.close()
    return {
        "empty": False,
        "overview": {
            "battles": total_b,
            "picks": total_picks,
            "bans": total_bans,
            "players": n_players,
            "team_rate": round(100 * n_team / total_b, 1) if total_b else 0,
            "win_rate": round(100 * overall_wr, 1),
        },
        "season_options": season_options,
        "pick_top": pick_top,
        "ban_top": ban_top,
        "winrate_top": wr,
        "attribute": attribute,
        "job": job,
        "pick_order": pick_order,
        "season_dist": season_dist,
    }


# ----------------------------------------------------------------------------
# 前端页面（内嵌，离线可用）
# ----------------------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>第七史诗 RTA 战绩分析看板</title>
<style>
  :root{--bg:#f5f6f8;--card:#fff;--ink:#1f2330;--muted:#6b7280;--line:#e5e7eb;
        --blue:#3b82f6;--red:#ef4444;--green:#22c55e;--amber:#f59e0b;--purple:#8b5cf6;}
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);padding:20px}
  h1{font-size:22px;margin-bottom:4px}
  .sub{color:var(--muted);font-size:13px;margin-bottom:16px}
  .bar-top{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:18px}
  select{padding:8px 12px;border:1px solid var(--line);border-radius:8px;font-size:14px;background:#fff}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:22px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
  .card .v{font-size:24px;font-weight:700}
  .card .l{color:var(--muted);font-size:12px;margin-top:4px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:18px}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
  .panel h2{font-size:15px;margin-bottom:12px}
  .row{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:13px}
  .row .name{width:120px;flex:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .row .track{flex:1;background:#eef0f4;border-radius:6px;height:18px;position:relative;overflow:hidden}
  .row .fill{height:100%;background:var(--blue);border-radius:6px}
  .row .val{width:64px;flex:none;text-align:right;color:var(--muted)}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
  th{color:var(--muted);font-weight:600}
  .pie{display:flex;align-items:center;gap:16px}
  .pie .chart{width:160px;height:160px;border-radius:50%;flex:none}
  .legend{font-size:12px;line-height:1.7}
  .legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:middle}
  .wr-hi{color:var(--green);font-weight:600}
  .wr-mid{color:var(--amber)}
  .wr-lo{color:var(--red)}
  .empty{padding:40px;text-align:center;color:var(--muted)}
</style>
</head>
<body>
  <h1>第七史诗 RTA 战绩分析看板</h1>
  <div class="sub">数据源：e7stats 紫龙公开接口 · 仅统计 ss17(2025夏) 及以后阵容完整赛季</div>
  <div class="bar-top">
    <div class="cards" id="cards"></div>
    <select id="season"><option value="">全部赛季</option></select>
  </div>
  <div class="grid" id="grid"></div>

<script>
const COLORS=["#3b82f6","#ef4444","#22c55e","#f59e0b","#8b5cf6","#06b6d4","#ec4899","#84cc16"];
const fmt=n=>n>=10000?(n/10000).toFixed(1)+"万":n.toLocaleString();

function barRows(items, getLabel, getVal, getPct, color){
  const max=Math.max(...items.map(getVal),1);
  return items.map(it=>{
    const v=getVal(it), pct=Math.round(100*v/max);
    const label=getLabel(it), val=getPct?getPct(it):fmt(v);
    return `<div class="row"><div class="name" title="${label}">${label}</div>
      <div class="track"><div class="fill" style="width:${pct}%;background:${color}"></div></div>
      <div class="val">${val}</div></div>`;
  }).join("");
}

function pie(items){
  const total=items.reduce((s,i)=>s+i.count,0)||1;
  let acc=0, stops=[];
  items.forEach((it,i)=>{
    const start=acc/total*360, end=(acc+it.count)/total*360;
    stops.push(`${COLORS[i%COLORS.length]} ${start}deg ${end}deg`);
    acc+=it.count;
  });
  const legend=items.map((it,i)=>
    `<div><i style="background:${COLORS[i%COLORS.length]}"></i>${it.attr||it.job||it.season} ${it.rate}%</div>`
  ).join("");
  return `<div class="pie"><div class="chart" style="background:conic-gradient(${stops.join(",")})"></div>
    <div class="legend">${legend}</div></div>`;
}

function wrClass(r){return r>=58?"wr-hi":r>=50?"wr-mid":"wr-lo";}

function render(d){
  if(d.empty){document.getElementById("grid").innerHTML='<div class="empty">暂无数据，请先运行抓取脚本。</div>';return;}
  const o=d.overview;
  document.getElementById("cards").innerHTML=[
    ["对局数",fmt(o.battles)],["我方出场",fmt(o.picks)],["我方 ban",fmt(o.bans)],
    ["覆盖玩家",fmt(o.players)],["阵容完整率",o.team_rate+"%"],["整体胜率",o.win_rate+"%"]
  ].map(([l,v])=>`<div class="card"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");

  const sel=document.getElementById("season");
  if(!sel.dataset.filled){
    d.season_options.forEach(s=>{const op=document.createElement("option");op.value=s.code;op.textContent=s.code+(s.name?" · "+s.name:"");sel.appendChild(op);});
    sel.dataset.filled="1";
  }

  const panels=[];
  panels.push(`<div class="panel"><h2>英雄出场 Top 20</h2>${barRows(d.pick_top,i=>i.name,i=>i.count,null,"#3b82f6")}</div>`);
  panels.push(`<div class="panel"><h2>英雄被 ban Top 20</h2>${barRows(d.ban_top,i=>i.name,i=>i.count,null,"#ef4444")}</div>`);
  panels.push(`<div class="panel"><h2>属性分布（我方出场）</h2>${pie(d.attribute)}</div>`);
  panels.push(`<div class="panel"><h2>职业分布（我方出场）</h2>${pie(d.job)}</div>`);

  let wr=`<table><tr><th>英雄</th><th>胜率</th><th>场次</th></tr>`;
  d.winrate_top.forEach(i=>{wr+=`<tr><td>${i.name}</td><td class="${wrClass(i.rate)}">${i.rate}%</td><td>${i.plays}</td></tr>`;});
  wr+="</table>";
  panels.push(`<div class="panel"><h2>英雄胜率 Top 20（样本≥15场）</h2>${wr}</div>`);

  let sd=`<table><tr><th>赛季</th><th>对局数</th></tr>`;
  d.season_dist.forEach(s=>{sd+=`<tr><td>${s.season}</td><td>${fmt(s.count)}</td></tr>`;});
  sd+="</table>";
  panels.push(`<div class="panel"><h2>赛季分布</h2>${sd}</div>`);

  panels.push(`<div class="panel"><h2>先手/pick 顺序分布</h2>${barRows(d.pick_order,i=>"第"+(i.order+1)+"手",i=>i.count,null,"#8b5cf6")}</div>`);

  document.getElementById("grid").innerHTML=panels.join("");
}

async function load(season){
  const r=await fetch("/api/stats"+(season?"?season="+season:""));
  const d=await r.json();
  render(d);
}

document.getElementById("season").addEventListener("change",e=>load(e.target.value));
load("");
</script>
</body>
</html>"""


# ----------------------------------------------------------------------------
# HTTP 服务
# ----------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            self._send(HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif u.path == "/api/stats":
            season = parse_qs(u.query).get("season", [None])[0]
            try:
                data = build_stats(season)
            except Exception as e:  # noqa: BLE001
                data = {"error": str(e)}
            self._send(json.dumps(data, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
        else:
            self._send(b"404", "text/plain; charset=utf-8", 404)

    def _send(self, body, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main():
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"RTA 看板已启动: http://localhost:{PORT}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
