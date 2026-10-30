const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');
const methods=source.slice(source.indexOf('    async deleteChat('),source.indexOf('    // Thinking/Reasoning tag processing'));
function fixture(){
 const alerts=[],calls=[];
 const state=vm.runInNewContext('({'+methods+'})',{confirm:()=>true,alert:s=>alerts.push(s),window:{t:k=>k},clearTimeout,console:{error(){},warn(){}}});
 Object.assign(state,{backendChatReady:true,chatHistory:[{id:'ses_test',backendRevision:1}],currentChatId:'other',
 backendChatSyncTimers:{},backendChatSyncPromises:{},chatSessions:{ses_test:{messages:['stale']}},streamSessions:{},
 getStreamSession:()=>null,saveChatHistory(){},flushBackendChatSync:async()=>{throw Error('Deletion must not upload stale content');}});
 let revision=5,deleted=false;
 state.platformChatFetch=async(path,options={})=>{calls.push([path,options.method||'GET']);
  if(options.method==='DELETE'){assert.equal(path,`/threads/ses_test?expected_revision=${revision}`);deleted=true;return {};}
  if(path==='')return {collection_revision:9};
  assert.equal(path,'/threads/ses_test');return {revision};};
 return {state,alerts,calls,setRevision:n=>revision=n,isDeleted:()=>deleted};
}
test('delete reads current durable revision without uploading stale Agent content',async()=>{
 const f=fixture();assert.equal(await f.state.deleteChat('ses_test'),true);assert.equal(f.isDeleted(),true);
 assert.equal(f.state.chatHistory.length,0);assert.equal(f.state.chatSessions.ses_test,undefined);
 assert.deepEqual(f.calls.map(c=>c[1]),['GET','DELETE','GET']);assert.equal(f.alerts.length,0);
});
test('in-flight content synchronization settles before revision read',async()=>{
 const f=fixture();let release;f.state.backendChatSyncPromises.ses_test=new Promise(r=>release=r);
 const pending=f.state.deleteChat('ses_test');assert.equal(f.calls.length,0);
 f.setRevision(8);release();await pending;assert.equal(f.isDeleted(),true);
});
test('a collection refresh failure does not resurrect a successfully deleted row',async()=>{
 const f=fixture(),fetch=f.state.platformChatFetch;f.state.platformChatFetch=(p,o)=>p===''?Promise.reject(Error('offline')):fetch(p,o);
 assert.equal(await f.state.deleteChat('ses_test'),true);assert.equal(f.state.chatHistory.length,0);assert.equal(f.alerts.length,0);
});
test('concurrent delete conflict and connection failures remain visible and retain local data',async()=>{
 for(const status of [409,403,503]){const f=fixture(),fetch=f.state.platformChatFetch;
 f.state.platformChatFetch=(p,o)=>o?.method==='DELETE'?Promise.reject(Object.assign(Error('rejected'),{status})):fetch(p,o);
 assert.equal(await f.state.deleteChat('ses_test'),false);assert.equal(f.state.chatHistory.length,1);
 assert.equal(f.alerts[0],status===409?'chat.delete_conflict':'chat.delete_failed');}
});
test('clear all stops on failure and does not erase undeleted local history',async()=>{
 const f=fixture();f.state.stopAllStreams=()=>{};f.state.platformChatFetch=async()=>{throw Error('offline');};
 await f.state.clearAllHistory();assert.equal(f.state.chatHistory.length,1);assert.ok(f.state.chatSessions.ses_test);
});
test('delete messages exist in every supported locale',()=>{
 for(const lang of ['zh','zh-TW','en','de','es','fr','ja','ko','pt-BR','ru']){
 const values=JSON.parse(fs.readFileSync(__dirname+'/../web/i18n/'+lang+'.json'));
 assert.ok(values['chat.delete_failed']);assert.ok(values['chat.delete_conflict']);}
});
