const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
function fixture(){
 const calls=[];let focused=false;
 const dialog={showModal(){},close(){},querySelector(){return {focus(){focused=true;}};}};
 const context={window:{},document:{documentElement:{lang:'en'}},navigator:{language:'en'},fetch:async(url,options)=>{calls.push({url,...options});return {ok:true,json:async()=>({revision:12,outgoing:[]})};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),context);
 const app=context.window.messagerApp();app.currentBot={id:'source'};app.botUseAccess={revision:10};app.$refs={accessDialog:dialog};app.$nextTick=f=>f();app.loadBotUseAccess=async()=>{};
 return {app,calls,focused:()=>focused};
}
test('review and cancel never revoke access, and Cancel receives focus',async()=>{
 const {app,calls,focused}=fixture();app.reviewRemoveBotUse({id:'target',name:'Target'});
 assert.equal(app.accessRemoval.name,'Target');assert(focused());assert.equal(calls.length,0);
 app.closeAccessDialog();await app.removeBotUse();assert.equal(calls.length,0);
});
test('confirmation uses the reviewed target and revision despite polling',async()=>{
 const {app,calls}=fixture();app.reviewRemoveBotUse({id:'target',name:'Target'});app.botUseAccess={revision:11};
 await app.removeBotUse();assert.equal(calls.length,1);assert.equal(calls[0].method,'DELETE');
 assert(calls[0].url.endsWith('/bots/source/bot-access/targets/target'));
 assert.equal(JSON.parse(calls[0].body).revision,10);assert.equal(app.accessDialogMode,'');
});
test('switching Bot or an in-flight removal blocks submission',async()=>{
 const {app,calls}=fixture();app.reviewRemoveBotUse({id:'target',name:'Target'});
 app.botUseBusy=true;await app.removeBotUse();app.botUseBusy=false;app.currentBot={id:'other'};await app.removeBotUse();
 assert.equal(calls.length,0);
});

test('restoring research defaults reviews changes and saves only the reviewed App grants',async()=>{
 const calls=[];
 const defaults={templates:[{id:'research',role:{en:'Default research role'},app_ids:['search','reader','unavailable']}]};
 const context={window:{},document:{documentElement:{lang:'en'}},navigator:{language:'en'},fetch:async(url,options)=>{
  calls.push({url,...options});return {ok:true,json:async()=>url.endsWith('/options')?defaults:{revision:7,items:[]}};
 }};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),context);
 const app=context.window.messagerApp();
 app.currentBot={id:'research-copy',template_id:'research'};app.botEditDuty='My role';
 app.$refs={accessDialog:{showModal(){},close(){}}};app.$nextTick=f=>f();
 app.accessLoaded=true;app.accessRevision=5;app.accessReviewHash='reviewed-catalog';
 app.botAccess=[
  {app_id:'search',name:'Search',available:true,selected:true,enabled:true},
  {app_id:'reader',name:'Reader',available:true,selected:false,enabled:false},
  {app_id:'unavailable',name:'Unavailable',available:false,selected:false,enabled:false},
  {app_id:'other',name:'Other',available:true,selected:true,enabled:true},
 ];
 await app.restoreTemplateRole();
 assert.equal(app.botEditDuty,'Default research role');
 assert(!calls.some(c=>c.method==='PUT'||c.method==='PATCH'));
 await app.reviewRestoreTemplateAccess();
 assert.equal(app.accessDialogMode,'restore-template');
 assert.deepEqual(JSON.parse(JSON.stringify(app.accessRemoval.changes)),[
  {id:'reader',name:'Reader',enabled:true},{id:'other',name:'Other',enabled:false},
 ]);
 assert(!calls.some(c=>c.method==='PUT'));
 app.accessRevision=6;
 await app.restoreTemplateAccess();
 const update=calls.find(c=>c.method==='PUT');
 assert(update.url.endsWith('/bots/research-copy/app-access'));
 assert.deepEqual(JSON.parse(update.body),{
  revision:5,review_hash:'reviewed-catalog',apps:[{app_id:'search',enabled:true},{app_id:'reader',enabled:true}],
 });
});
