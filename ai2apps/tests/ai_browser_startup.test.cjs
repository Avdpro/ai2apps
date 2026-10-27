const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/ai_browser.js','utf8');
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};}
for(const mobile of [false,true])test(`${mobile?'mobile detail':'desktop'} Mini-App catalog and mount do not await workspace or profiles`,async()=>{
 const profiles=deferred(),workspace=deferred(),catalog=deferred(),events=[];
 const c={window:{innerWidth:1000,AI2APPS_MOBILE_SURFACE:mobile,addEventListener(){}},location:{hash:'#ai2apps-browser-detail=search'},URLSearchParams,crypto:{randomUUID:()=> 'id'},Map};
 vm.runInNewContext(source,c);const app=c.aiBrowserApp();
 app.setupMobileHistory=()=>{};app.loadProfiles=()=>{events.push('profiles');return profiles.promise;};
 app.refresh=()=>{events.push('workspace');return workspace.promise;};
 app.refreshMiniApps=async()=>{events.push('catalog');await catalog.promise;app.miniApps=[{id:'search'}];};
 app.shellBrowserNavigation=action=>{events.push(action);return mobile;};
 app.openMiniApp=async()=>events.push('mount');app.connectProfileStatus=async()=>events.push('profile-status');app.connectWorkspaceEvents=()=>events.push('events');
 const initializing=app.init();assert(events.includes('catalog'));assert(events.includes('workspace'));
 catalog.resolve();await initializing;
 if(mobile)assert(events.includes('mount'));else assert(!events.includes('profile-status'));
 assert(events.includes('events'));profiles.resolve();workspace.resolve();await Promise.resolve();await Promise.resolve();
 if(!mobile)assert(events.includes('profile-status'));
});
const host=fs.readFileSync(__dirname+'/../web/static/js/studio_mini_apps.js','utf8');
for(const includeDraft of [false,true])test(`startup launches independent ${includeDraft?'draft':'sources'} reads concurrently`,async()=>{
 const pending=new Map(),paths=[];let reply;
 const a=host.indexOf("                else if (request.operation === 'web-agent.startup')");
 const b=host.indexOf("                else if (request.operation === 'web-agent.profiles')",a);
 const branch=host.slice(a,b).replace(/^\s*else if/,'if');
 const c={request:{operation:'web-agent.startup',includeDraft},binding:{studioId:'ai2apps.ai-browser'},base:'/mount',abort:{signal:{}},payload:async response=>response,fetch:path=>{paths.push(path);const d=deferred();pending.set(path,d);return d.promise;},reply:value=>reply=value};
 const running=vm.runInNewContext('(async()=>{'+branch+'})()',c);
 assert.equal(paths.length,2,'both reads must start before either response arrives');
 assert(paths.includes('/v1/platform/client/browser-profiles'));
 assert(paths.includes(includeDraft?'/mount/draft':'/mount/web-agent/custom-sources'));
 pending.get(paths[0]).resolve([{key:'default',name:'Default',is_default:true,private:'hidden'}]);pending.get(paths[1]).resolve(includeDraft?{value:null}:{sources:[]});
 await running;assert.equal(reply.value.profiles[0].private,undefined);
 if(includeDraft)assert.equal(reply.value.draft,null);else assert.equal(reply.value.sources.length,0);
});
test('catalog loading is independent of profiles and only a successful empty response permits empty state',async()=>{
 const pending=deferred();const c={window:{innerWidth:1000,AI2AppsStudioMiniApps:{list:()=>pending.promise}},crypto:{randomUUID:()=> 'id'},Map};
 vm.runInNewContext(source,c);const app=c.aiBrowserApp();app.refreshIcons=()=>{};app.updateFrames=()=>{};app.fail=()=>{};app.tr=k=>k;
 assert.equal(app.miniAppsState,'loading');const request=app.refreshMiniApps();
 app.loading=false;assert.equal(app.miniAppsState,'loading');pending.resolve({items:[]});await request;assert.equal(app.miniAppsState,'ready');
 c.window.AI2AppsStudioMiniApps.list=async()=>{throw Error('offline');};await app.refreshMiniApps();assert.equal(app.miniAppsState,'error');
 for(const name of ['mobile_ai_browser.html','system_apps/ai_browser_workspace.html']){
  const template=fs.readFileSync(__dirname+'/../web/templates/'+name,'utf8');
  assert(template.includes(`miniAppsState==='ready'&&!miniApps.length`));assert(template.includes(`miniAppsState==='loading'&&!miniApps.length`));
 }
});
test('composite Task shows paused only when every unfinished child awaits assistance',()=>{
 const c={window:{innerWidth:1000,t:k=>k},crypto:{randomUUID:()=> 'id'},Map};vm.runInNewContext(source,c);const app=c.aiBrowserApp();
 app.taskTree=[{id:'root',kind:'search',status:'running',created_at:1}];app.tasks=[{id:'a',root_task_id:'root',status:'waiting_input',paused:true}];
 assert.equal(app.taskGroups[0].paused,true);assert.equal(app.statusLabel('running',app.taskGroups[0]),'ai_browser.workspace.paused_waiting_help');
 app.tasks.push({id:'b',root_task_id:'root',status:'running',paused:false});assert.equal(app.taskGroups[0].paused,false);
});
