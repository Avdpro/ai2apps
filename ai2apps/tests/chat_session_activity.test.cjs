const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');
function setup(){
 const stored=new Map(),timers=[];
 const context={window:{t:k=>k,addEventListener(){},removeEventListener(){}},document:{visibilityState:'hidden',hasFocus:()=>false,addEventListener(){},removeEventListener(){}},console,
  localStorage:{getItem:k=>stored.get(k)||null,setItem:(k,v)=>stored.set(k,v)},setTimeout:f=>{timers.push(f);return timers.length;},clearTimeout(){},Date};
 vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/chat_session_activity.js','utf8'),context);
 const methods=vm.runInContext('({'+html.slice(html.indexOf('            sessionListRuns(chatId)'),html.indexOf('            isChatStreaming(chatId'))+'})',context);
 return {context,stored,api:context.window.AI2AppsChatSessionActivity,app:{...methods,chatHistory:[{id:'s'}],currentChatId:'other',agentRuns:{},sessionListRunSnapshots:[],sessionListSeen:{},sessionListActivityReady:false,chatHistoryStorageKey:()=> 'owner:one',isLegacyChatStreaming:()=>false}};
}
const run=(status='running',extra={})=>({id:'r',session_id:'s',status,revision:1,created_at:'2026-10-27T00:00:00Z',updated_at:'2026-10-27T00:00:01Z',...extra});
test('busy, waiting authorization/parameters/capability and unread completion have distinct priority',()=>{
 const {api}=setup();assert.equal(api.state([run()],false,''),'busy');
 for(const status of ['waiting_input','waiting_capability','interrupted'])assert.equal(api.state([run(status)],true,''),'attention');
 assert.equal(api.state([run('running',{interactions:[{status:'pending'}]})],true,''),'attention');
 assert.equal(api.state([run('completed')],false,''),'unread');
 assert.equal(api.state([run('completed')],false,'r:completed'),'idle');
 assert.equal(api.state([run('cancelled')],false,''),'idle');
 assert.equal(api.state([],true,''),'busy');
});
test('pending child provider interaction surfaces on its parent Session; historical interrupted runs do not mask a newer reply',()=>{
 const {api}=setup();
 const child=run('waiting_input',{id:'child',parent_run_id:'r',root_run_id:'r'});
 assert.equal(api.state([run(),child],false,''),'attention');
 assert.equal(api.state([run('completed'),child],false,''),'unread');
 assert.equal(api.state([run('interrupted',{id:'old',created_at:'2026-10-26'}),run('completed')],false,''),'unread');
});
test('newer durable revisions beat stale in-memory runs and all provider names remain generic',()=>{
 const {api}=setup();
 assert.equal(api.state(api.merge([run('waiting_input',{revision:3})],[run('running',{revision:2,agent_key:'arbitrary.provider'})]),true,''),'attention');
});
test('polling is read-only, unread persists on reload and only viewing the corresponding Session clears it',async()=>{
 const {app,context,stored}=setup();const requests=[];
 app.agentPlatformFetch=async path=>{requests.push(path);return {items:[run()]};};
 await app.refreshSessionListActivity();assert.equal(app.sessionListActivityState('s'),'busy');
 app.agentPlatformFetch=async path=>{requests.push(path);return {items:[run('completed',{revision:2})]};};
 await app.refreshSessionListActivity();assert.equal(app.sessionListActivityState('s'),'unread');
 assert.ok(requests.every(path=>path.startsWith('/agent-runs?')));
 const saved=JSON.parse(stored.get('owner:one:activity-v1'));assert.notEqual(saved.seen.s,'r:completed');
 const reload=setup();reload.app.sessionListSeen=saved.seen;reload.app.sessionListRunSnapshots=[run('completed')];reload.app.sessionListActivityReady=true;
 assert.equal(reload.app.sessionListActivityState('s'),'unread');
 reload.app.markSessionListViewed('s');assert.equal(reload.app.sessionListActivityState('s'),'idle');
 reload.app.sessionListRunSnapshots=[run('waiting_input',{revision:3})];reload.app.markSessionListViewed('s');
 assert.equal(reload.app.sessionListActivityState('s'),'attention');
 context.document.visibilityState='visible';context.document.hasFocus=()=>true;app.currentChatId='other';
 await app.refreshSessionListActivity();assert.equal(app.sessionListActivityState('s'),'unread');
 app.currentChatId='s';await app.refreshSessionListActivity();assert.equal(app.sessionListActivityState('s'),'idle');
});
test('first adoption does not badge historical archive; work finishing after boot stays unread',async()=>{
 const {app}=setup();app._sessionListFirstInstall=true;app._sessionListActivityBootAt=Date.parse('2026-10-27T00:00:03Z');
 app.agentPlatformFetch=async()=>({items:[run('completed',{finished_at:'2026-10-27T00:00:02Z'})]});
 await app.refreshSessionListActivity();assert.equal(app.sessionListActivityState('s'),'idle');
 app.agentPlatformFetch=async()=>({items:[run('completed',{id:'new',created_at:'2026-10-27T00:00:04Z',finished_at:'2026-10-27T00:00:05Z'})]});
 await app.refreshSessionListActivity();assert.equal(app.sessionListActivityState('s'),'unread');
});
test('template exposes accessible indicators and reduced-motion support without widening the row',()=>{
 assert.match(html,/class="chat-session-state"[^>]+:aria-label=/);
 assert.match(html,/prefers-reduced-motion: reduce/);
 assert.match(html,/chat-session-state \{ width: 16px/);
});
test('status caches contain no prompts/results, and unloaded answers cannot be marked read',()=>{
 const {app,api}=setup();
 const snapshot=api.summary(run('completed',{input:{prompt:'private'},output:{message_id:'answer',content:'private'},interactions:[{status:'pending',prompt:'private'}]}));
 assert.equal(JSON.stringify(snapshot).includes('private'),false);
 app.sessionListRunSnapshots=[snapshot];app.getChatSession=()=>({messages:[]});
 app.markSessionListViewed('s');assert.equal(app.sessionListSeen.s,undefined);
 app.getChatSession=()=>({messages:[{id:'answer'}]});app.markSessionListViewed('s');assert.equal(app.sessionListSeen.s,'r:completed');
});
