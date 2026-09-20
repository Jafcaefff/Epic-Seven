// 端到端验证（jsdom）：分层对位估计（阵容级优先 → 单体降级）
// 用法：node verify_lineup.js （服务需已在 8799 运行）
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
const wait = ms => new Promise(r => setTimeout(r, ms));
const PROBE = `
window.__probe = function(){ return {
  step: curStep(), cards: document.querySelectorAll('#rosterBox .card').length, mode: currentMode,
  my_picks: state.my_picks.slice(), enemy_picks: state.enemy_picks.slice(),
  srcTop: currentAll.slice(0,6).map(function(h){ return h.name+':'+h.counter_src; }),
  lineupTop: currentAll.slice(0,3).map(function(h){ return h.lineup ? (h.lineup.size+'人 '+h.lineup.wr+'% '+h.lineup.games+'场') : null; }),
  lineupChips: document.querySelectorAll('#rosterBox .card .vs-chip.lineup').length,
  pairChips: document.querySelectorAll('#rosterBox .card .vs-chip.best').length,
  firstCard: (document.querySelector('#rosterBox .card')||{textContent:''}).textContent.replace(/\\s+/g,' ').slice(0,110)
};};
window.__useSecondHand = async function(){ state.hand='second'; await loadSequence(); };
window.__prebans = function(){ addEnemyBan('c2007'); addMyBan('c1106'); };
window.__enemyPick = function(code){ addEnemyPick(code); };
window.__myPickTop2 = function(){ var l=currentAll.filter(function(h){return h.score!=null;}).slice(0,2); addMyPick(l[0].code); addMyPick(l[1].code); };
`;
(async () => {
  w.eval(w.document.querySelector('script').textContent + PROBE);
  await w.eval('(async()=>{ await loadHeroes(); await loadSeasons(); })()');
  await w.__useSecondHand();
  await w.eval('renderTrack(); renderSlots(); (async()=>{try{await renderAction();}catch(e){console.log("RA_ERR:",e.message)}})()');
  await wait(8000);
  // 走完两个 preban
  w.__prebans(); await wait(8000);
  // 敌方 1 选 → 我方 2 选 → 敌方 2 选（此时敌方 2 人，阵容级应生效）
  w.__enemyPick('c5154'); await wait(8000);
  let p = w.__probe();
  console.log('敌1人 → step:', JSON.stringify(p.step), '| src:', p.srcTop.join(' / '));
  w.__myPickTop2(); await wait(8000);
  // 敌方第 3 轮要选 2 人，逐个补齐直到轮到我方
  w.__enemyPick('c1183'); await wait(7000);
  let st = w.__probe().step;
  if (st && st.side === 'enemy') { w.__enemyPick('c6005'); await wait(8000); }
  st = w.__probe().step;
  console.log('补齐后 step:', JSON.stringify(st));
  p = w.__probe();
  console.log('敌2人后 step:', JSON.stringify(p.step), '| enemy:', JSON.stringify(p.enemy_picks), '| my:', JSON.stringify(p.my_picks));
  console.log('前6来源:', p.srcTop.join(' / '));
  console.log('前3阵容级:', JSON.stringify(p.lineupTop));
  console.log('DOM 阵容级chip数:', p.lineupChips, '| 降级chip数:', p.pairChips);
  console.log('首卡文本:', p.firstCard);
  const ok = p.lineupChips > 0 && p.srcTop.some(s => s.includes('lineup'));
  console.log(ok ? 'RESULT=LINEUP_OK' : 'RESULT=CHECK_FAIL');
})().catch(e => { console.log('FATAL:', e.message); process.exit(1); });
