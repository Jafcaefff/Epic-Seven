// BP 状态机回归：验证「选完还缺人」修复 —— 每步必须真正填满 count 才推进
const { JSDOM } = require('jsdom');
const fs = require('fs');
const html = fs.readFileSync('E:/第七史诗查询工具/e7rta/static/draft.html', 'utf8');
const dom = new JSDOM(html, { runScripts: 'outside-only', url: 'http://127.0.0.1:8799/draft' });
const w = dom.window;
// 全部 mock 掉网络（本测试只验证前端状态机）
w.fetch = async (u) => {
  const url = String(u);
  let data = {};
  if (url.includes('/api/heroes')) data = [];
  else if (url.includes('/api/seasons')) data = [];
  else if (url.includes('/api/draft/sequence')) data = { steps: [] };
  else if (url.includes('/api/meta')) data = {};
  else if (url.includes('/api/draft/suggest')) data = { my_picks: [], enemy_picks: [], my_bans: [], all: [], matchup: null, attr_overview: null };
  return { ok: true, status: 200, json: async () => data, text: async () => JSON.stringify(data) };
};
const wait = ms => new Promise(r => setTimeout(r, ms));
const PROBE = `
window.__t = {};
window.__setup = function(hand, preban){ state.hand=hand; state.preban=preban;
  state.my_picks=[]; state.enemy_picks=[]; state.my_bans=[]; state.enemy_bans=[]; state.stepIndex=0; };
// 前端 STEPS 来自后端 /api/draft/sequence（已 mock 掉），这里按同一规则本地生成
window.__mkSteps = function(hand, preban){
  var first = hand==='first' ? 'me' : 'enemy', other = first==='me'?'enemy':'me';
  var steps=[];
  for(var i=0;i<preban;i++){ steps.push({phase:'preban',side:first,count:1}); steps.push({phase:'preban',side:other,count:1}); }
  var counts=[[first,1],[other,2],[first,2],[other,2],[first,2],[other,1]];
  counts.forEach(function(c,i){ steps.push({phase:'pick',side:c[0],count:c[1],round:i+1}); });
  steps.push({phase:'postban',side:first,count:1});
  steps.push({phase:'postban',side:other,count:1});
  STEPS=steps;
};
window.__seq = function(){ return STEPS.map(function(s,i){ return i+':'+s.phase+'/'+s.side+'/'+s.count; }); };
window.__step = function(){ var s=curStep(); return s? (s.phase+'/'+s.side+'/'+s.count) : 'DONE'; };
window.__act = function(myPick, enPick, myPre, enPre, myPost, enPost){
  var s=curStep(); if(!s) return 'DONE';
  if(s.phase==='pick') return s.side==='me' ? addMyPick(myPick) : addEnemyPick(enPick);
  if(s.phase==='preban') return s.side==='me' ? addMyBan(myPre) : addEnemyBan(enPre);
  if(s.phase==='postban') return s.side==='me' ? addMyBan(myPost) : addEnemyBan(enPost);
};
window.__state = function(){ return { my: state.my_picks.slice(), en: state.enemy_picks.slice(),
  myB: state.my_bans.map(function(b){return b.code+(b.pre?'P':'');}),
  enB: state.enemy_bans.map(function(b){return b.code+(b.pre?'P':'');}), idx: state.stepIndex };};
`;
// 模拟队列
const MY_PICKS = ['c1168', 'c2124', 'c1096', 'c2128', 'c1118'];
const EN_PICKS = ['c5154', 'c1183', 'c6005', 'c1129', 'c1157'];
const MY_PRE = ['c1106', 'c2008'];
const EN_PRE = ['c2007', 'c1159'];

function runFlow(label, hand, preban) {
  return new Promise(resolve => {
    w.__setup(hand, preban);
    w.__seq();  // 由 loadSequence 的 fetch mock 拿不到真步骤 → 手工注入
    w.__mkSteps(hand, preban);
    let mi = 0, ei = 0, mpi = 0, epi = 0;
    let clicks = 0;
    const timer = setInterval(() => {
      const st = w.__step();
      if (st === 'DONE' || clicks > 40) {
        clearInterval(timer);
        const s = w.__state();
        const ok = s.my.length === 5 && s.en.length === 5;
        console.log(label, '| 我:', s.my.length, '敌:', s.en.length, '| idx:', s.idx,
          '| 我ban:', s.myB.join(','), '| 敌ban:', s.enB.join(','), '|', ok ? 'OK' : '*** FAIL ***');
        resolve(ok);
        return;
      }
      // 按当前步决定喂什么
      const stepRaw = st.split('/');
      const phase = stepRaw[0], side = stepRaw[1];
      let args = [null, null, null, null, null, null];
      if (phase === 'pick') { if (side === 'me') args[0] = MY_PICKS[mi++]; else args[1] = EN_PICKS[ei++]; }
      if (phase === 'preban') { if (side === 'me') args[2] = MY_PRE[mpi++]; else args[3] = EN_PRE[epi++]; }
      if (phase === 'postban') {
        if (side === 'me') { const s2 = w.__state(); args[4] = s2.en.find(c => !s2.myB.includes(c)) || s2.en[0]; }
        else { const s2 = w.__state(); args[5] = s2.my.find(c => !s2.enB.includes(c)) || s2.my[0]; }
      }
      w.__act(...args);
      clicks++;
    }, 30);
  });
}
(async () => {
  w.eval(w.document.querySelector('script').textContent + PROBE);
  await wait(200);
  const r1 = await runFlow('①我方先手 preban1', 'first', 1);
  const r2 = await runFlow('②我方后手 preban1', 'second', 1);
  const r3 = await runFlow('③我方先手 preban2(大师+)', 'first', 2);
  // ④ 删除回退（同步跑）：填满 → 删我方第 2 选 → 应回到我方选人步 → 补选后再次走完
  const r4 = (() => {
    // 通用同步填满器
    const fillAll = (myFn, enFn, myPreFn, enPreFn) => {
      let n = 0;
      while (w.__step() !== 'DONE' && n++ < 40) {
        const p = w.__step().split('/'), ph = p[0], sd = p[1];
        const s2 = w.__state();
        const args = [null, null, null, null, null, null];
        if (ph === 'pick') { if (sd === 'me') args[0] = myFn(s2); else args[1] = enFn(s2); }
        if (ph === 'preban') { if (sd === 'me') args[2] = myPreFn(s2); else args[3] = enPreFn(s2); }
        if (ph === 'postban') {
          if (sd === 'me') args[4] = s2.en.find(c => !s2.myB.includes(c)) || s2.en[0];
          else args[5] = s2.my.find(c => !s2.enB.includes(c)) || s2.my[0];
        }
        w.__act(...args);
      }
      const s = w.__state();
      return s.my.length === 5 && s.en.length === 5;
    };
    w.__setup('first', 1);
    w.__mkSteps('first', 1);
    let mi = 0, ei = 0, mpi = 0, epi = 0;
    const okFilled = fillAll(
      () => MY_PICKS[mi++], () => EN_PICKS[ei++],
      () => MY_PRE[mpi++], () => EN_PRE[epi++]);
    // 删除我方第 2 选（它在第 2 个我方选人步里）
    w.eval('removePick("me", 1)');
    const after = w.__step();
    const sAfter = w.__state();
    const rewound = after.startsWith('pick/me');
    console.log('④删除回退: 完成 →', after, '| 我:', sAfter.my.length, '敌:', sAfter.en.length,
      rewound ? 'OK(回到我方选人步)' : '*** FAIL ***');
    // 补选（换新英雄），应再次走完
    mi = 0; ei = 0; mpi = 0; epi = 0;
    const okRefill = fillAll(
      () => 'x' + (100 + mi++) + 'c', () => 'y' + (100 + ei++) + 'c',
      () => 'z' + (100 + mpi++) + 'c', () => 'w' + (100 + epi++) + 'c');
    const sEnd = w.__state();
    console.log('④补选后: 我:', sEnd.my.length, '敌:', sEnd.en.length, okRefill ? 'OK' : '*** FAIL ***');
    return okFilled && rewound && okRefill;
  })();
  console.log((r1 && r2 && r3 && r4) ? 'RESULT=BP_FLOW_OK' : 'RESULT=BP_FLOW_FAIL');
  process.exit(0);
})().catch(e => { console.log('FATAL:', e.message); process.exit(1); });
