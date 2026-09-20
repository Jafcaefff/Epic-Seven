"""抓 epic7rtastats /meta 渲染后真实 DOM，提取 4 张榜 + pick-order 榜。
英雄名用本地的 epic7_en_names.json 映射（从 /heroes 列表页提取的 c-code ↔ 英文名）。

输出: data/meta_snapshot.json
"""
import subprocess, time, re, json, os
from datetime import datetime, timezone, timedelta

META_URL = 'https://www.epic7rtastats.com/meta'
BASE = os.path.dirname(__file__)
OUT = os.path.join(BASE, 'data', 'meta_snapshot.json')
EN_MAP_FILE = os.path.join(BASE, 'data', 'epic7_en_names.json')

CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

def dump_dom(url, vt_budget=15):
    args = [CHROME, '--headless=new', '--disable-gpu', '--no-sandbox',
            f'--virtual-time-budget={vt_budget*1000}', '--dump-dom', url,
            f'--user-data-dir=C:/Users/Administrator/AppData/Local/Temp/cs_meta_{int(time.time()*1000)}']
    p = subprocess.run(args, capture_output=True, text=True, timeout=vt_budget+30)
    return p.stdout

def parse_pct(s):
    if s is None: return None
    m = re.search(r'(\d+\.\d+)', str(s))
    return float(m.group(1)) if m else None

def parse_int(s):
    m = re.search(r'(\d{1,3}(?:,\d{3})*)', s)
    return int(m.group(1).replace(',', '')) if m else None

def load_en_map():
    if os.path.exists(EN_MAP_FILE):
        with open(EN_MAP_FILE, encoding='utf-8') as f:
            arr = json.load(f)
        return {code: name for code, name in arr}
    return {}

def main():
    print(f'Rendering {META_URL} ...')
    dom = dump_dom(META_URL)
    en_map = load_en_map()
    print(f'  loaded {len(en_map)} en-name mappings')

    # 赛季
    season_m = re.search(r'Current Meta For <strong>([^<]+)</strong>', dom)
    season = season_m.group(1) if season_m else 'Unknown'
    updated_m = re.search(r'Last Updated: <strong>([^<]+)</strong>', dom)
    updated = updated_m.group(1).strip() if updated_m else None

    # 段提取：每个 marker 是一个 <div class="...bg-zinc-800..."> 容器
    # 段间的边界：用 marker 字符串定位
    def section_html(marker, end_markers):
        i = dom.find(marker)
        if i < 0: return ''
        end_pos = len(dom)
        for em in end_markers:
            j = dom.find(em, i + len(marker))
            if j > 0 and j < end_pos:
                end_pos = j
        return dom[i:end_pos]

    # 4 张榜
    sections = {
        'most_picked':       ('Most Picked', ['Highest Win Rate', 'Most Pre-Banned']),
        'highest_winrate':   ('Highest Win Rate', ['Most Pre-Banned', 'Most Post-Banned']),
        'most_pre_banned':   ('Most Pre-Banned', ['Most Post-Banned']),
        'most_post_banned':  ('Most Post-Banned', ['Most Picked By Pick Order']),
    }

    snapshot = {k: [] for k in sections}
    snapshot['pick_order'] = {}

    # 第1名是特殊大图（有 alt），第2-20名是列表项（也有 alt）
    # 每个条目: img alt="Name" + 数字串 + games 数字
    for key, (marker, ends) in sections.items():
        seg = section_html(marker, ends)
        # 提取所有 (alt, code) 配对 + 该条目后到下一个 alt 之间的数字
        # 方法：找每个 alt 配对后的数字/games
        # 实际：<img alt="X" ... cXXXX_s>...<b>90.88<!-- -->%</b>... 63,129 games
        items = list(re.finditer(r'alt=\"([A-Z][a-zA-Z &\-\'\.]{2,30})\"[^<]{0,800}?c(\d{4})_s', seg))
        for idx, m in enumerate(items[:20], start=1):
            name = m.group(1)
            code = 'c' + m.group(2)   # 全局统一 c-code 格式，对齐 data.db heroes.code
            # 数字从 m.end() 到下一个 alt 或段尾
            seg_end = items[idx].start() if idx < len(items) else len(seg)
            body = seg[m.end():seg_end]
            rates = re.findall(r'(\d+\.\d+)(?:<!-- -->)?%', body)
            games = parse_int(body)
            entry = {'rank': idx, 'name': name, 'code': code}
            if key == 'most_pre_banned':
                entry['preban_rate'] = parse_pct(rates[0]) if rates else None
                if len(rates) >= 2: entry['pick_rate'] = parse_pct(rates[1])
            elif key == 'most_post_banned':
                entry['postban_rate'] = parse_pct(rates[0]) if rates else None
                if len(rates) >= 2: entry['pick_rate'] = parse_pct(rates[1])
            else:
                entry['pick_rate'] = parse_pct(rates[0]) if rates else None
                if len(rates) >= 2: entry['win_rate'] = parse_pct(rates[1])
            entry['games'] = games
            snapshot[key].append(entry)

    # Pick Order 段（4 个子榜：First Pick / Second Pick / Pick 1 / Pick 4+5）
    po_seg = section_html('Most Picked By Pick Order', [])
    po_keys = ['First Pick', 'Second Pick', 'Pick 1', 'Pick 4+5']
    pos = {}
    for k in po_keys:
        i = po_seg.find(k)
        if i < 0: continue
        rest = po_seg[i + len(k):]
        next_pos = []
        for kk in po_keys:
            if kk != k:
                j = rest.find(kk)
                if j > 0: next_pos.append(j)
        end = min(next_pos) if next_pos else len(rest)
        pos[k] = rest[:end]

    for k, seg in pos.items():
        items = list(re.finditer(r'alt=\"([A-Z][a-zA-Z &\-\'\.]{2,30})\"[^<]{0,800}?c(\d{4})_s', seg))
        ent = []
        for idx, m in enumerate(items[:10], start=1):
            name = m.group(1)
            code = 'c' + m.group(2)
            seg_end = items[idx].start() if idx < len(items) else len(seg)
            body = seg[m.end():seg_end]
            rates = re.findall(r'(\d+\.\d+)(?:<!-- -->)?%', body)
            games = parse_int(body)
            ent.append({
                'rank': idx, 'name': name, 'code': code,
                'pick_rate': parse_pct(rates[0]) if rates else None,
                'win_rate': parse_pct(rates[1]) if len(rates) >= 2 else None,
                'games': games,
            })
        snapshot['pick_order'][k.replace(' ', '_').lower()] = ent

    snapshot['season'] = season
    snapshot['last_updated'] = updated
    snapshot['captured_at'] = datetime.now(timezone(timedelta(hours=8))).isoformat()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    print(f'Wrote {OUT}')
    print(f'  season={season}')
    for k in sections:
        print(f'  {k}: {len(snapshot[k])} 条')
    print(f'  pick_order: { {k: len(v) for k,v in snapshot["pick_order"].items()} }')
    print('  前 5 preban:')
    for e in snapshot['most_pre_banned'][:5]:
        print(f'    #{e["rank"]:2} {e["name"]:30} preban={e["preban_rate"]}%  code={e["code"]}')

if __name__ == '__main__':
    main()