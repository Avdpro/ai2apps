const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const base=path.join(__dirname,'../../packages/ai2apps-frozen-time/web');
function fixture(){
 const elements=Object.fromEntries(['startup','startup-zh','startup-en','startup-retry','app-ui'].map(id=>[id,{hidden:['app-ui','startup-retry'].includes(id),textContent:'',classList:{add(value){this.value=value}},setAttribute(key,value){this[key]=value}}]));
 const events={},timers=new Map();let serial=0,reloaded=0,view=0;
 elements.startup.appendChild=child=>elements[child.id]=child;
 const ctx={document:{createElement:()=>({style:{},textContent:''}),getElementById:id=>elements[id],addEventListener:(name,fn)=>events[name]=fn},window:{addEventListener:(name,fn)=>events[name]=fn,dispatchEvent:()=>view++},location:{reload:()=>reloaded++},Event:class{},setTimeout:fn=>{timers.set(++serial,fn);return serial},clearTimeout:id=>timers.delete(id)};
 vm.runInNewContext(fs.readFileSync(path.join(base,'frozen-time-startup.js'),'utf8'),ctx);
 events.DOMContentLoaded();return {elements,events,timers,api:ctx.window.frozenStartup,get reloaded(){return reloaded},get view(){return view}};
}
test('UI is hidden in source and revealed only after translated draft and model initialization',()=>{
 const html=fs.readFileSync(path.join(base,'frozen-time.html'),'utf8'),js=fs.readFileSync(path.join(base,'frozen-time.js'),'utf8');
 assert.ok(html.includes('<main id="app-ui" hidden>'));
 assert.ok(html.indexOf('frozen-time-startup.js')<html.indexOf('<body>'));
 assert.ok(js.includes("await models();state();window.frozenStartup.ready()"));
 const f=fixture();assert.equal(f.elements['app-ui'].hidden,true);f.api.stage('models');assert.equal(f.elements['startup-zh'].textContent,'正在检查模型…');
 f.api.ready();assert.equal(f.elements['app-ui'].hidden,false);assert.equal(f.elements.startup.hidden,true);assert.equal(f.timers.size,0);assert.equal(f.view,1);
});
test('startup failure displays actual stage and error safely as text',()=>{
 const f=fixture();f.api.stage('restoring');f.api.fail(new Error('HTTP 403 <script>'));
 assert.match(f.elements['startup-detail'].textContent,/恢复设置/);
 assert.match(f.elements['startup-detail'].textContent,/HTTP 403 <script>/);
 assert.equal(f.elements['app-ui'].hidden,true);
});
test('connection timeout and script errors retain hidden UI and allow retry',()=>{
 for(const failure of ['timeout','error']){
  const f=fixture();if(failure==='timeout')[...f.timers.values()][0]();else f.events.error();
  assert.equal(f.elements['app-ui'].hidden,true);assert.equal(f.elements['startup-retry'].hidden,false);assert.equal(f.elements.startup['aria-busy'],'false');
  f.elements['startup-retry'].onclick();assert.equal(f.reloaded,1);
 }
});
