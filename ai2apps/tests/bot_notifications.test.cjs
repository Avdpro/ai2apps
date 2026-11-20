const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
function setup(handler){
 const calls=[],badges=[],window={parent:{postMessage:(value,origin)=>badges.push([value,origin])}};
 const location={origin:'http://local.test',search:'',hash:''};
 const context={window,location,URLSearchParams,setTimeout(){},clearTimeout(){},document:{documentElement:{lang:'en'}},navigator:{language:'en'},async fetch(url,options){calls.push({url,options});const value=await handler(url,options);return {ok:value.ok!==false,status:value.status||200,async json(){return value.body;}};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),context);
 return {app:window.messagerApp(),calls,badges,location};
}
test('local Inbox contributes actual counters and uses existing Shell badge protocol',async()=>{
 const t=setup(async()=>({body:{items:[{id:'bn_one',bot_id:'owned',read_at:null},{id:'bn_read',bot_id:'owned',read_at:'2026-11-03'}],unread_count:1,has_more:false}}));
 t.app.unreadCount=2;await t.app.loadLocalNotices();
 assert.equal(t.app.inboxUnread,3);assert.equal(t.app.sidebarUnread({id:'owned'}),1);assert.equal(t.app.sidebarBadge({id:'owned'}),'1');
 assert.equal(t.badges[0][0].type,'ai2apps.shell.set-badge');assert.equal(t.badges[0][0].targetAppId,'ai2apps.messager');assert.equal(t.badges[0][0].badge,'3');assert.equal(t.badges[0][1],'http://local.test');
});
test('opening a notice uses reauthorized server target and never submits an approval',async()=>{
 const t=setup(async url=>({body:url.endsWith('/open')?{bot_id:'owned',todo_run_id:'original-run',task:{id:'original-task',title:'Owned task',status:'waiting_input'}}:{items:[],unread_count:0,has_more:false}}));
 const selected=[];t.app.loadBots=async()=>{t.app.bots=[{id:'owned',name:'Owned'}];};t.app.openBot=async b=>{selected.push(b.id);t.app.currentBot=b;};
 await t.app.openBotNotice('bn_owned');assert.deepEqual(selected,['owned']);assert.equal(t.app.focusedTask.id,'original-task');assert.equal(t.app.tab,'bots');
 assert.equal(t.calls[0].url,'/v1/platform/messager/notices/bn_owned/open');assert.equal(t.calls[0].options.method,'POST');
 assert.ok(t.calls.every(c=>!c.url.includes('/respond')&&!c.url.includes('/approve')&&!c.url.includes('/run')));
});
test('route carries only notice reference; stale or unauthorized target does not navigate',async()=>{
 const t=setup(async()=>({ok:false,status:404,body:{detail:'Original request unavailable'}}));
 t.app.currentBot={id:'current'};t.location.hash='#notification-route=bot-notice&notification-resource=bn_stale&bot_id=foreign';
 await t.app.openNotificationRoute();assert.equal(t.app.currentBot.id,'current');assert.equal(t.app.notice,'Original request unavailable');assert.equal(t.calls.length,1);
 assert.equal(t.calls[0].url,'/v1/platform/messager/notices/bn_stale/open');
});
