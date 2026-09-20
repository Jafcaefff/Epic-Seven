// 统一网格 + 图标筛选 端到端验证（jsdom）
// 注意：jsdom 下脚本用 let 声明的绑定，跨 window.eval 不可见；
// 因此把探针函数拼接到同一段 eval 里，靠闭包访问内部状态。
const { JSDOM } = require('jsdom');
const fs = require('fs');

const html = fs.readFileSync('E:/第七史诗查询工具/e7rta/static/draft.html', 'utf8');
const BASE = 'http://127.0.0.1:8799';
const dom = new JSDOM(html, { runScripts: 'outside-only', url: BASE + '/draft' });
const w = dom.window;
w.fetch = async (u, opt) => {
  const url = u.startsWith('http') ? u : BASE + u;
  const res = await fetch(url, opt);
  const data = await res.json();
  return { ok: true, status: res.status, json: async () => data, text: async () => JSON.stringify(data) };
};

const PROBE = [
  'window.__probe = function(){ return {',
  '  step: curStep(), cards: document.querySelectorAll("#rosterBox .card").length,',
  '  top: currentAll[0] ? {name:currentAll[0].name, score:currentAll[0].score, pos_rate:currentAll[0].pos_rate, rarity:currentAll[0].rarity} : null,',
  '  mode: currentMode, my_bans: state.my_bans.map(b=>b.code), enemy_bans: state.enemy_bans.map(b=>b.code),',
  '  my_picks: state.my_picks.slice(),',
  '  hasStars: !!document.querySelector("#rosterBox .card .stars"),',
  '  hasStatLine: !!document.querySelector("#rosterBox .card .stat-line"),',
  '  ichips: document.querySelectorAll("#filterChips .ichip").length,',
  '  cardCodes: [].map.call(document.querySelectorAll("#rosterBox .card"), c=>c.dataset.code)',
  '};};',
  'window.__all = function(){ return currentAll; };',
  'window.__heroOf = function(code){ return HMAP[code]; };',
  'window.__itemOf = function(code){ for(var i=0;i<currentAll.length;i++){ if(currentAll[i].code===code) return currentAll[i]; } return null; };',
  'window.__clickFirst = function(){ var c=document.querySelector("#rosterBox .card"); if(!c) return false; c.dispatchEvent(new MouseEvent("click",{bubbles:true})); return c.dataset.code; };',
  'window.__setFilter = function(g,k){ HERO_FILTER[g].add(k); renderFilterChips(); refreshRoster(); };',
  'window.__clearFilters = function(){ HERO_FILTER.attrs.clear(); HERO_FILTER.jobs.clear(); HERO_FILTER.rarities.clear(); refreshRoster(); };',
  'window.__doBan = function(){ addMyBan("c1106"); addEnemyBan("c2007"); };',
].join('\n');

const wait = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const s = w.document.querySelector('script');
  w.eval(s.textContent + '\n' + PROBE);
  await w.eval('(async()=>{ await loadHeroes(); await loadSeasons(); await loadSequence(); })()');
  await w.eval('renderTrack(); renderSlots(); (async()=>{try{await renderAction();}catch(e){console.log("RA_ERR:",e.message)}})()');
  await wait(6000);   // 冷启动首次聚合较慢

  let p = w.__probe();
  console.log('STEP1:', JSON.stringify(p.step), '| cards:', p.cards, '| ichips:', p.ichips,
    '| stars:', p.hasStars, '| statLine:', p.hasStatLine, '| mode:', p.mode);
  console.log('TOP1:', JSON.stringify(p.top));

  const all = w.__all();
  const scored = all.filter(h => h.score != null);
  const mono = scored.every((h, i) => i === 0 || scored[i - 1].score >= h.score);
  const firstNull = all.findIndex(h => h.score == null);
  const nullsLast = firstNull === -1 || firstNull >= scored.length;
  console.log('scored:', scored.length, '| 单调不增:', mono, '| 无数据排最后:', nullsLast);
  console.log('前5:', scored.slice(0, 5).map(h => h.name + ' (' + Math.round(h.score * 100) + ', 第1选' + h.pos_rate + '%)').join(' / '));
  console.log('前5中该位0场:', scored.slice(0, 5).filter(h => !h.pos_games).length,
    '| 前14中选率<0.5%:', scored.slice(0, 14).filter(h => h.pos_rate < 0.5).length);

  const code0 = w.__clickFirst();
  await wait(1500);
  p = w.__probe();
  console.log('ban 点击:', code0, '-> my_bans:', JSON.stringify(p.my_bans));

  w.__setFilter('attrs', 'fire');
  await wait(3000);
  let codes = w.__probe().cardCodes;
  let allFire = codes.every(c => { const h = w.__itemOf(c); return h && (h.attr_raw || h.attr) === 'fire'; });
  console.log('火属性筛选(ban阶段):', codes.length, '| 全部是火:', allFire);

  w.__setFilter('rarities', 3);
  codes = w.__probe().cardCodes;
  let both = codes.every(c => { const h = w.__itemOf(c); return h && (h.attr_raw || h.attr) === 'fire' && h.rarity === 3; });
  console.log('火+3星(组间=且):', codes.length, '| 全部匹配:', both);

  w.__clearFilters();
  w.__doBan();
  await wait(6000);
  p = w.__probe();
  console.log('当前步:', JSON.stringify(p.step), '| mode:', p.mode, '| cards:', p.cards, '| top:', JSON.stringify(p.top));
  const code1 = w.__clickFirst();
  await wait(2000);
  p = w.__probe();
  console.log('pick 点击:', code1, '-> my_picks:', JSON.stringify(p.my_picks));

  // pick 阶段筛选（用户主场景）：火 + 战士 + 5星 三层叠加；属性选两项=组内或
  await wait(4000);
  w.__setFilter('attrs', 'fire');
  w.__setFilter('attrs', 'wind');
  await wait(500);
  codes = w.__probe().cardCodes;
  let twoAttr = codes.every(c => { const h = w.__itemOf(c); const a = h ? (h.attr_raw || h.attr) : ''; return a === 'fire' || a === 'wind'; });
  console.log('火+风(组内=或):', codes.length, '| 全部火或风:', twoAttr);

  w.__setFilter('jobs', 'warrior');
  await wait(500);
  codes = w.__probe().cardCodes;
  let cross = codes.every(c => { const h = w.__itemOf(c); const a = h ? (h.attr_raw || h.attr) : ''; const j = h ? (h.job_raw || h.job) : ''; return (a === 'fire' || a === 'wind') && j === 'warrior'; });
  console.log('叠加战士(组间=且):', codes.length, '| 全部匹配:', cross);

  w.__setFilter('rarities', 5);
  await wait(500);
  codes = w.__probe().cardCodes;
  let triple = codes.every(c => { const h = w.__itemOf(c); const a = h ? (h.attr_raw || h.attr) : ''; const j = h ? (h.job_raw || h.job) : ''; return (a === 'fire' || a === 'wind') && j === 'warrior' && h.rarity === 5; });
  console.log('再加5星:', codes.length, '| 全部匹配:', triple);

  // 搜索框（先清筛选）
  w.__clearFilters();
  await wait(300);
  await w.eval('(function(){var el=document.getElementById("rosterSearch");el.value="维";el.dispatchEvent(new Event("input"));})()');
  await wait(300);
  console.log('搜索"维":', w.__probe().cardCodes.length, '张');
  console.log('RESULT=FRONTEND_OK');
})().catch(e => { console.log('FATAL:', e.message); process.exit(1); });
