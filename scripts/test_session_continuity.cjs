const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
function boot(file, store = new Map(), clock = {now: 100000000}, cfg = {}) {
  const events = {}, timers = new Map(); let seq = 0, signs = 0;
  const document = {documentElement: {dataset:{}}, hidden:false, querySelector:()=>null, getElementById:()=>null, querySelectorAll:()=>[], addEventListener:(n,fn)=>{events['doc:'+n]=fn;}, dispatchEvent:()=>{}};
  const window = {IAEMLOOP_AUTH_CONFIG:{...cfg}, location:{origin:'https://example.test',pathname:'/privado/test.html',search:'?month=10',hash:'#table',replace:()=>{},assign:()=>{}}, addEventListener:(n,fn)=>{events[n]=fn;}, setTimeout:(fn,ms)=>{timers.set(++seq,{fn,ms});return seq;},clearTimeout:(id)=>timers.delete(id),__iaemloopSupabase:{auth:{signOut:async()=>{signs++;}}}};
  const localStorage = {getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k)};
  const ctx={window,document,localStorage,Date:{now:()=>clock.now},CustomEvent:class{},URL,URLSearchParams,console};
  vm.runInNewContext(fs.readFileSync(path.join(root,file),'utf8'),ctx);
  return {window,events,timers,store,clock,signs:()=>signs};
}
(async()=>{
 for (const file of ['js/iaemloop-auth.js','js/v2/auth.js']) {
  let s = boot(file); assert.equal(s.window.IAEMLOOPAuth.idleLimitMs(),43200000,`${file}: default must be 12 hours`);
  s = boot(file,new Map([['iaemloop:last_activity_at','99999000']]),{now:100000000});
  s.events.click(); const first=[...s.timers.values()][0]; assert.ok(first);
  s.store.set('iaemloop:last_activity_at','100000500'); s.clock.now=100000501;
  first.fn(); await Promise.resolve(); assert.equal(s.signs(),0,`${file}: stale timer must reread other-tab activity`);
  s.clock.now=143200501; [...s.timers.values()].at(-1).fn(); await Promise.resolve(); assert.equal(s.signs(),1,`${file}: actual idle expiry must sign out`);
  s=boot(file,new Map([['iaemloop:last_activity_at','99999000']]),{now:100000000});s.events.click();s.clock.now+=1000;s.events.pagehide();assert.equal(s.store.get('iaemloop:last_activity_at'),'100001000');
 }
 // Exercise the public bridge with metadata-only fixtures; no real auth tokens.
 const shell = fs.readFileSync(path.join(root,'js/v2/shell.js'),'utf8');
 function publicVisit(last, token = true) {
   const state = new Map(); if (last !== null) state.set('iaemloop:last_activity_at',String(last));
   if (token) state.set('iaemloop-auth-token','test-marker-not-a-real-token');
   const handlers = {};
   const document = {body:{classList:{contains:()=>false}},querySelectorAll:()=>[]};
   const window = {location:{pathname:'/v2/index.html'},addEventListener:(name,fn)=>{handlers[name]=fn;},matchMedia:()=>({matches:true})};
   vm.runInNewContext(shell,{document,window,Date:{now:()=>100000000},localStorage:{getItem:k=>state.get(k)??null,setItem:(k,v)=>state.set(k,v)}});
   return state;
 }
 assert.equal(publicVisit(99999000).get('iaemloop:last_activity_at'),'100000000');
 assert.equal(publicVisit(1).get('iaemloop:last_activity_at'),'1','public navigation cannot revive expired session');
 assert.equal(publicVisit(null).has('iaemloop:last_activity_at'),false,'public navigation cannot invent signed-in activity');
 assert.equal(publicVisit(99999000,false).get('iaemloop:last_activity_at'),'99999000');
 const source=fs.readFileSync(path.join(root,'js/iaemloop-auth-config.js'),'utf8');assert.match(source,/sessionIdleMinutes:\s*720/);
 function checkAuthCache(dir) {
   for (const entry of fs.readdirSync(dir,{withFileTypes:true})) {
     if (entry.name === '.git') continue;
     const full = path.join(dir,entry.name);
     if (entry.isDirectory()) checkAuthCache(full);
     else if (entry.name.endsWith('.html')) {
       const text = fs.readFileSync(full,'utf8');
       for (const match of text.matchAll(/<script[^>]+src=["']([^"']+)/g)) {
         if (/\/(?:iaemloop-auth(?:-config)?|v2\/auth)\.js(?:\?|$)/.test(match[1])) {
           assert.ok(match[1].includes('?v=20261016-session2'),`stale auth cache: ${full} ${match[1]}`);
         }
       }
     }
   }
 }
 checkAuthCache(root);
 console.log('SESSION_CONTINUITY_OK defaults=12h stale_timer=protected pagehide=flushed legacy_and_v2=2 auth_cache_inventory=all');
})().catch(e=>{console.error(e);process.exitCode=1;});
