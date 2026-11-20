const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function setup(){let id=0;const timers=new Map(),calls=[],actions=[];const window={removeEventListener(){},AI2AppsBotConversation:{invalidate(){}}};
 const ctx={window,document:{documentElement:{lang:'en'}},navigator:{language:'en'},setTimeout:(fn,ms)=>{timers.set(++id,{fn,ms});return id},clearTimeout:key=>timers.delete(key),clearInterval(){},fetch:async url=>{calls.push(url);return {ok:true,json:async()=>({items:[]})}}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),ctx);const app=window.messagerApp();app.$nextTick=fn=>{fn?.();return Promise.resolve()};app.$refs={botCreateForm:{scrollIntoView(){actions.push('show-create')}},botNameInput:{focus(){actions.push('focus-name')}},botArchiveList:{scrollIntoView(){actions.push('show-archive')}}};return {app,timers,calls,actions};}
test('notices expire after a fixed six seconds; repeated polling errors do not extend the visible timer',()=>{
 const t=setup();t.app.fail(Error('Synthetic failure'));const timer=[...t.timers.values()][0];assert.equal(timer.ms,6000);t.app.fail(Error('Synthetic failure'));assert.equal(t.timers.size,1);assert.equal([...t.timers.values()][0],timer);timer.fn();assert.equal(t.app.notice,'');assert.equal(t.timers.size,0);
});
test('manual dismiss and teardown cancel timers; old callbacks cannot dismiss a new notice',()=>{
 const t=setup();t.app.fail(Error('old'));const old=[...t.timers.values()][0];t.app.success('new');old.fn();assert.equal(t.app.notice,'new');assert.equal(t.app.noticeTone,'success');t.app.dismissNotice();assert.equal(t.app.notice,'');assert.equal(t.timers.size,0);t.app.fail(Error('last'));t.app.destroy();assert.equal(t.timers.size,0);
});
test('archive index remains lazy alongside the independent creation surface',async()=>{
 const t=setup();t.app.sidebarWidth=88;t.app.expandSidebar=()=>t.app.sidebarWidth=260;
 await t.app.toggleArchivedBots();assert.equal(t.app.showArchivedBots,true);assert.equal(t.calls.length,1);assert.match(t.calls[0],/\/bots-archive$/);await t.app.toggleArchivedBots();assert.equal(t.app.showArchivedBots,false);assert.equal(t.calls.length,1);
});
