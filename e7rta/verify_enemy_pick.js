// 端到端验证（jsdom）：精简卡片 + 敌方 1 选后我方推荐联动
// 用法：node verify_enemy_pick.js （服务需已在 8799 运行）
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
  step: curStep(), cards: document.querySelectorAll('#rosterBox .card').length,
  mode: currentMode,
  my_picks: state.my_picks.slice(), enemy_picks: state.enemy_picks.slice(),
  topNames: currentAll.slice(0,6).map(function(h){return h.name;}),
  topVs: currentAll.slice(0,3).map(function(h){return (h.vs_list||[]).map(function(v){return v.name+' '+v.wr+'%';});}),
  noTags: !document.querySelector('#rosterBox .card .tags'),
  noStars: !document.querySelector('#rosterBox .card .stars'),
  hasVsChip: !!document.querySelector('#rosterBox .card .vs-chip'),
  firstCardTxt: (document.querySelector('#rosterBox .card')||{textContent:''}).textContent.slice(0,120)
};};
window.__enemyFirstPick = function(){ addEnemyPick('c5154'); };
window.__useSecondHand = async function(){ state.hand='second'; await loadSequence(); };
window.__enemyPrebanAndMyPreban = function(){ addEnemyBan('c2007'); addMyBan('c1106'); };
`;
(async () => {
  w.eval(w.document.querySelector('script').textContent + PROBE);
  await w.eval('(async()=>{ await loadHeroes(); await loadSeasons(); })()');
  // 我方后手：敌方先 1 选
  await w.__useSecondHand();
  await w.eval('renderTrack(); renderSlots(); (async()=>{try{await renderAction();}catch(e){console.log("RA_ERR:",e.message)}})()');
  await wait(6000);
  let p = w.__probe();
  console.log('初始步:', JSON.stringify(p.step), '| cards:', p.cards, '| mode:', p.mode);
  console.log('精简卡片: 无tags行 =', p.noTags, ', 无星数 =', p.noStars);
  // 走完两个 preban → 到敌方 1 选
  w.eval('void 0');
  await new Promise(r => setTimeout(r, 100));
  w.__enemyPrebanAndMyPreban();
  await wait(6000);
  p = w.__probe();
  console.log('两 ban 后步:', JSON.stringify(p.step));
  // 敌方 1 选 c5154 调香师维波里丝
  w.__enemyFirstPick();
  await wait(6000);
  p = w.__probe();
  console.log('敌方 1 选后步:', JSON.stringify(p.step), '| enemy_picks:', JSON.stringify(p.enemy_picks));
  console.log('我方推荐 top6:', p.topNames.join(' / '));
  console.log('前3的 vs 数据:', JSON.stringify(p.topVs));
  console.log('卡片显示 vs-chip:', p.hasVsChip);
  console.log('首卡文本:', p.firstCardTxt);
  const okOrder = p.topNames[0] === '利纳柯';
  console.log('利纳柯 升到第1(对位63%):', okOrder);
  console.log(okOrder && p.hasVsChip && p.noTags ? 'RESULT=ENEMY_PICK_OK' : 'RESULT=CHECK_FAIL');
})().catch(e => { console.log('FATAL:', e.message); process.exit(1); });
