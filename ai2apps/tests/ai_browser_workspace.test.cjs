const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const translations=JSON.parse(fs.readFileSync(__dirname+'/../web/i18n/zh.json','utf8'));
const t=key=>translations[key]||key;
const source=fs.readFileSync(__dirname+'/../web/static/js/ai_browser.js','utf8');
function setup(){const context={crypto:{randomUUID:()=> 'worker-1234567890'},window:{t,},document:{getElementById:()=>({classList:{toggle(){}}})},Map,URL,URLSearchParams,console,setTimeout:()=>0,clearTimeout:()=>{}};vm.runInNewContext(source,context);return context.aiBrowserApp();}
test('switching between Profile and task preserves editor and task iframe instances',()=>{
 const app=setup();let display='none';const frame={style:{get display(){return display},set display(v){display=v}}};app.frames.set('editor:one',{frame});app.editorKey='editor:one';app.view='editor';app.updateFrames();assert.equal(display,'block');app.selectProfile({key:'default'});assert.equal(display,'none');assert.equal(app.frames.size,1);app.openTask({id:'task',status:'queued'});assert.equal(app.frames.size,1);app.view='editor';app.updateFrames();assert.equal(display,'block');
});
test('task lists separate queued and interrupted from terminal history across domains',()=>{
 const app=setup();app.tasks=[{id:'a',status:'queued',profile_key:'one'},{id:'b',status:'interrupted',profile_key:'two'},{id:'c',status:'completed',profile_key:'one'}];assert.deepEqual(Array.from(app.activeTasks,t=>t.id),['a','b']);assert.deepEqual(Array.from(app.recentTasks,t=>t.id),['c']);assert.equal(app.profileTaskCount('one'),0);assert.equal(app.profileTaskCount('two'),1);
});
test('Domain navigation includes compiled and editing Agents without active exports',async()=>{
 const app=setup();
 const drafts=[{id:'google',name:'Google loop',site_scope:['https://google.com/**'],status:'compiled'},
 {id:'weibo',name:'Weibo draft',site_key:'weibo.com',status:'editing'},
 {id:'reader',name:'Reader',site_key:'example.com',status:'active'}];
 app.request=async path=>path==='/browser-workspace'?{domains:['google.com'],tasks:[],settings:{global_limit:4,profile_limit:1}}:
 path==='/agent-drafts'?{items:drafts}:{items:[{agent_id:'reader',name:'read',generation_id:'gen'},{agent_id:'reader',name:'list',generation_id:'gen'},{agent_id:'builtin:read',name:'read'}]};
 app.refreshProfileStates=async()=>{};app.updateFrames=()=>{};app.dispatch=async()=>{};
 await app.refresh();
 const google=app.domains.find(d=>d.name==='google.com');
 assert.equal(google.capabilities.length,1);assert.equal(google.capabilities[0].availability,'已编译 · 待启用');
 assert.equal(app.domains.find(d=>d.name==='weibo.com').capabilities[0].availability,'待编译');
 assert.equal(app.domains.find(d=>d.name==='example.com').capabilities.length,2);
 let edited;app.editAgent=(...args)=>edited=args;app.selectCapability(google.capabilities[0],google.name);
 assert.deepEqual(edited,['google','google.com']);assert.equal(app.selectedCapability,null);
});
test('editing and selecting a saved draft never launch a browser; testing creates one lazily',async()=>{
 const app=setup();let launches=0,navigations=0;
 app.mountFrame=(key,query,context)=>app.frames.set(key,{frame:{style:{}},query,context});
 app.browserSession=async profileKey=>{launches++;return {profileKey,context:'test-tab',connection:{command:async method=>{if(method==='browsingContext.getTree')return {contexts:[{context:'test-tab'}]};navigations++},close:async()=>{}}};};
 await app.editAgent('draft','google.com');
 assert.equal(launches,0);assert.equal(navigations,0);
 const frame=app.frames.get('editor:draft');assert.equal(frame.context.bidi_context,undefined);
 await app.editAgent('draft','google.com');assert.equal(launches,0);
 await Promise.all([frame.frame.ai2appsEnsureBrowserContext(),frame.frame.ai2appsEnsureBrowserContext()]);
 assert.equal(launches,1);assert.equal(navigations,1);
 const context=await frame.frame.ai2appsEnsureBrowserContext();assert.equal(context.bidi_context,'test-tab');assert.equal(launches,1);
});
test('background sync leaves refresh button idle; manual refresh indicates progress without duplicate requests',async()=>{
 const app=setup();let release,calls=0;
 const gate=new Promise(resolve=>release=resolve);
 app.request=async path=>{calls++;await gate;return path==='/browser-workspace'?{domains:[],tasks:[],settings:{global_limit:4,profile_limit:1}}:{items:[]};};
 app.refreshProfileStates=async()=>{};app.updateFrames=()=>{};app.dispatch=async()=>{};
 const background=app.refresh();assert.equal(app.syncing,true);assert.equal(app.refreshing,false);
 await app.refresh({manual:true});assert.equal(app.refreshing,true);assert.equal(calls,4);
 release();await background;assert.equal(app.refreshing,false);assert.equal(app.syncing,false);
 const manual=app.refresh({manual:true});assert.equal(app.refreshing,true);await manual;assert.equal(app.refreshing,false);
});
test('Agent cards and sidebar entries open the same details for active and compiled Agents',()=>{
 const app=setup();app.updateFrames=()=>{};app.selectedDomain='google.com';
 app.drafts=[{id:'active',name:'Search',status:'active'},{id:'draft',status:'compiled'}];
 let edited=0,selected=0;app.editAgent=()=>edited++;app.selectCapability=()=>selected++;
 app.openAgent(app.drafts[0]);assert.equal(app.view,'agent');assert.equal(app.selectedAgent.id,'active');
 app.openAgentForCapability({agent_id:'draft'},'example.com');assert.equal(app.view,'agent');assert.equal(app.selectedAgent.id,'draft');assert.equal(app.selectedDomain,'example.com');assert.equal(edited,0);assert.equal(selected,0);
});
test('Domain creation opens goal-and-attachments flow without creating a browser session',async()=>{
 const app=setup();let launches=0;
 app.browserSession=async()=>{launches++;throw Error('must not launch');};
 app.mountFrame=(key,query,context)=>app.frames.set(key,{frame:{style:{}},query,context});
 await app.editAgent(null,'example.com');
 const entry=app.frames.get('editor:example.com');
 assert.equal(entry.query.workspace_create,'1');assert.equal(entry.query.draft_id,undefined);
 assert.equal(entry.context.url,'https://example.com/');assert.equal(launches,0);
});
test('editor Profile selection creates isolated lazy sessions and reuses only the matching Profile',async()=>{
 const app=setup(),opened=[];
 app.mountFrame=(key,query,context)=>app.frames.set(key,{frame:{style:{}},query,context});
 app.browserSession=async profileKey=>{opened.push(profileKey);return {profileKey,context:'tab-'+profileKey,connection:{command:async method=>method==='browsingContext.getTree'?{contexts:[{context:'tab-'+profileKey}]}:undefined,close:async()=>{}}};};
 await app.editAgent('draft','example.com');const frame=app.frames.get('editor:draft').frame;
 assert.equal(opened.length,0);
 assert.equal((await frame.ai2appsEnsureBrowserContext('work')).bidi_context,'tab-work');
 assert.equal((await frame.ai2appsEnsureBrowserContext('personal')).bidi_context,'tab-personal');
 assert.equal((await frame.ai2appsEnsureBrowserContext('work')).profile_key,'work');
 assert.deepEqual(opened,['work','personal']);
});

test('closed editor Tab is replaced once before a new trial; unrelated Tabs are never adopted',async()=>{
 const app=setup();let closed=0,opened=0,navigated=0;
 app.sessions.set('editor:work',{context:'gone',connection:{command:async()=>({contexts:[{context:'unrelated'}]}),close:async()=>{closed++}}});
 app.browserSession=async profileKey=>{opened++;assert.equal(profileKey,'work');return {context:'fresh',connection:{command:async()=>{navigated++},close:async()=>{}}};};
 const results=await Promise.all([app.ensureEditorSession('editor:work','work','example.com'),app.ensureEditorSession('editor:work','work','example.com')]);
 assert.equal(closed,1);assert.equal(opened,1);assert.equal(navigated,1);assert.equal(results[0].bidi_context,'fresh');assert.equal(results[1].bidi_context,'fresh');
});

test('saved exploration Recipes appear under Domain and reopen the same Recipe editor',async()=>{
 const app=setup();app.request=async path=>path==='/browser-workspace'?{domains:[],tasks:[],settings:{global_limit:4,profile_limit:1}}:
 path==='/agent-recipes'?{items:[{id:'recipe',site_key:'example.com',name:'Read articles',status:'tested'},
 {id:'committed',site_key:'example.com',committed_draft_id:'draft'}]}:{items:[]};
 app.refreshProfileStates=async()=>{};app.updateFrames=()=>{};app.dispatch=async()=>{};
 await app.refresh();assert.equal(app.domains.length,1);const cap=app.domains[0].capabilities[0];
 assert.equal(app.domains[0].capabilities.length,1);assert.equal(cap.title,'Read articles');assert.equal(cap.availability,'制作草稿 · 待审核');
 app.mountFrame=(key,query,context)=>app.frames.set(key,{frame:{style:{}},query,context});
 await app.selectCapability(cap,'example.com');
 const entry=app.frames.get('editor:recipe');assert.equal(entry.query.recipe_id,'recipe');assert.equal(entry.query.workspace_create,'1');assert.equal(entry.query.draft_id,undefined);
});

test('deleting a saved Recipe reads current revision before confirmation and refreshes Domain',async()=>{
 const app=setup();let approved=false,requests=[],refreshed=0;
 const context={crypto:{randomUUID:()=> 'worker'},window:{t,confirm:()=>approved},document:{getElementById:()=>null},Map,URL,URLSearchParams,console,setTimeout:()=>0,clearTimeout:()=>{}};
 vm.runInNewContext(source,context);const browser=context.aiBrowserApp();
 browser.request=async(...args)=>{if(args[0]==='/agent-recipes')return {items:[{id:'recipe',name:'List',revision:4}]};requests.push(args);};browser.refresh=async()=>{refreshed++};
 const draft={id:'recipe',name:'List',recipe_only:true,revision:3};
 await browser.deleteSavedDraft(draft);assert.equal(requests.length,0);
 approved=true;await browser.deleteSavedDraft(draft);
 assert.equal(requests[0][0],'/agent-recipes/recipe/archive');assert.equal(requests[0][2].expected_revision,4);assert.equal(refreshed,1);
});

test('duplicate deletion clicks share one pending request and revision conflict refreshes without retry',async()=>{
 let release;const gate=new Promise(resolve=>release=resolve);let reads=0,posts=0,refreshes=0,failure;
 const ctx={crypto:{randomUUID:()=> 'worker'},window:{t,confirm:()=>true},document:{getElementById:()=>null},Map,URL,URLSearchParams,console,setTimeout:()=>0,clearTimeout:()=>{}};
 vm.runInNewContext(source,ctx);const app=ctx.aiBrowserApp();app.refresh=async()=>{refreshes++};app.fail=e=>failure=e.message;
 app.request=async(path,method)=>{if(!method){reads++;await gate;return {items:[{id:'recipe',name:'Latest',revision:8}]};}posts++;throw Object.assign(Error('revision changed'),{status:409});};
 const draft={id:'recipe',name:'Old',revision:1,recipe_only:true};const pending=app.deleteSavedDraft(draft);
 await app.deleteSavedDraft(draft);assert.equal(reads,1);release();await pending;
 assert.equal(posts,1);assert.equal(refreshes,1);assert.match(failure,/列表已刷新/);assert.equal(app.deletingDrafts.length,0);
});

test('committed compiled site Agent is labelled as Agent, distinct from exploration Recipe draft',()=>{
 const app=setup();assert.equal(app.savedAgentStatus({status:'compiled'}),'已编译 · 待启用');
 assert.equal(app.savedAgentDeleteLabel({status:'compiled'}),'删除 Agent');
 assert.equal(app.savedAgentStatus({recipe_only:true,status:'draft'}),'制作草稿 · 待审核');
 assert.equal(app.savedAgentDeleteLabel({recipe_only:true,status:'draft'}),'删除草稿');
 assert.equal(app.savedAgentStatus({status:'active'}),'可运行');
});

test('active website Agent exposes deletion and archives only after named confirmation',async()=>{
 let confirmed='',posted;
 const ctx={crypto:{randomUUID:()=> 'worker'},window:{t,confirm:message=>{confirmed=message;return true}},document:{getElementById:()=>null},Map,URL,URLSearchParams,console,setTimeout:()=>0,clearTimeout:()=>{}};
 vm.runInNewContext(source,ctx);const app=ctx.aiBrowserApp();app.refresh=async()=>{};
 app.request=async(path,method,data)=>{if(!method)return {id:'active',name:'Article reader',status:'active',revision:7};posted={path,data};};
 await app.deleteSavedDraft({id:'active',status:'active',name:'Article reader'});
 assert.match(confirmed,/删除Agent/);assert.match(confirmed,/Article reader/);
 assert.equal(posted.path,'/agent-drafts/active/archive');assert.equal(posted.data.expected_revision,7);
 const template=fs.readFileSync(__dirname+'/../web/templates/system_apps/ai_browser.html','utf8');
 assert.match(template,/\['editing','compiled','active'\]\.includes\(draft.status\)/);
});

test('empty Domains require explicit confirmation; Agent-bearing Domains cannot be deleted',async()=>{
 let approved=false,confirmations=0,requests=0,refreshes=0;
 const ctx={crypto:{randomUUID:()=> 'worker'},window:{t,confirm:()=>{confirmations++;return approved}},document:{getElementById:()=>null},Map,URL,URLSearchParams,console,setTimeout:()=>0,clearTimeout:()=>{}};
 vm.runInNewContext(source,ctx);const app=ctx.aiBrowserApp();
 app.selectedDomain='example.com';app.domains=[{name:'example.com',capabilities:[]}];app.drafts=[];
 app.request=async(path,method)=>{assert.equal(path,'/browser-workspace/domains/example.com');assert.equal(method,'DELETE');requests++};
 app.refresh=async()=>{refreshes++};
 assert.equal(app.canDeleteDomain(),true);
 await app.deleteDomain();assert.equal(requests,0);assert.equal(app.selectedDomain,'example.com');
 app.drafts=[{site_key:'example.com'}];assert.equal(app.canDeleteDomain(),false);
 approved=true;await app.deleteDomain();assert.equal(confirmations,1);assert.equal(requests,0);
 app.drafts=[];app.domains[0].capabilities=[{name:'read'}];assert.equal(app.canDeleteDomain(),false);
 app.domains[0].capabilities=[];await app.deleteDomain();assert.equal(requests,1);assert.equal(refreshes,1);assert.equal(app.selectedDomain,'');
});

test('Agent details expose multiple capabilities and activate only a validated generation',async()=>{
 const app=setup();app.updateFrames=()=>{};app.selectedDomain='example.com';
 app.drafts=[{id:'agent',status:'compiled',source:{capabilities:[{id:'list',name:'web.extract-list',title:'List'},{id:'read',name:'web.read-page',title:'Read'}]}}];
 app.domains=[{name:'example.com',capabilities:[{agent_id:'agent',name:'web.extract-list',generation_id:'old'}]}];
 app.openAgent(app.drafts[0]);assert.equal(app.agentCapabilities.length,2);assert.ok(app.agentCapabilities[0].runnable);assert.equal(app.agentCapabilities[1].runnable,null);
 const requests=[];let refreshed=0;app.refresh=async()=>refreshed++;
 app.request=async(path,method)=>{requests.push(path);return path.endsWith('/compile')?{id:'new',status:'validated'}:{};};
 await app.activateAgent();assert.deepEqual(requests,['/agent-drafts/agent/compile','/agent-drafts/agent/generations/new/activate']);assert.equal(refreshed,1);
 requests.length=0;app.request=async path=>{requests.push(path);return {id:'bad',status:'failed'}};app.fail=()=>{};
 await app.activateAgent();assert.equal(requests.length,1);assert.equal(app.busyKey,'');
});

test('SSE updates tasks without refreshing the catalog and ignores duplicate replay',()=>{
 const app=setup();let stream,refreshes=0,dispatches=0,closed=0;
 class Events{constructor(url,options){this.url=url;this.options=options;this.listeners={};stream=this;}addEventListener(name,fn){this.listeners[name]=fn;}close(){closed++;}}
 const context={crypto:{randomUUID:()=> 'worker'},window:{t,},EventSource:Events,document:{getElementById:()=>null},Map,URL,URLSearchParams,console,setTimeout:()=>0,clearTimeout:()=>{}};
 vm.runInNewContext(source,context);const browser=context.aiBrowserApp();
 browser.refresh=()=>{refreshes++};browser.dispatch=()=>{dispatches++};browser.updateFrames=()=>{};
 browser.connectWorkspaceEvents();
 const send=(name,id,value)=>stream.listeners[name]({lastEventId:String(id),data:JSON.stringify(value)});
 send('browser.workspace.snapshot',10,{tasks:[{id:'one',status:'queued',created_at:1}],settings:{global_limit:4,profile_limit:1}});
 send('browser.workspace.changed',11,{payload:{task:{id:'one',status:'running',created_at:1}}});
 send('browser.workspace.changed',11,{payload:{task:{id:'one',status:'queued',created_at:1}}});
 assert.equal(browser.tasks[0].status,'running');assert.equal(refreshes,0);assert.equal(dispatches,0);
 stream.onerror();assert.equal(browser.streamState,'reconnecting');assert.equal(browser.tasks.length,1);
 stream.onopen();assert.equal(browser.streamState,'connected');
 browser.connectWorkspaceEvents();assert.equal(closed,1);
});
