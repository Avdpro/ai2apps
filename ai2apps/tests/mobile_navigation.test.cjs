const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/mobile.js'),'utf8');
const display = source.slice(source.indexOf('    function displayMount('),source.indexOf('    async function openApp('));
test('reopening a loaded Chat frame dismisses the spinner without reloading it',()=>{
    const callbacks=[];
    const context={hideTodoDetail(){},hideInlineChat(){},activeAppId:null,mounts:new Map(),frames:new Map(),title:{},home:{},stage:{},errorView:{},errorMessage:{},loading:{},Date,Math,
        crypto:{randomUUID:()=> 'test'},document:{createElement:()=>({addEventListener:(_,fn)=>callbacks.push(fn),contentWindow:{postMessage(){}},contentDocument:{URL:'https://device.example/mobile/chat',contentType:'text/html',body:{children:[{}]}},remove(){}})},
        frameHost:{appendChild(frame){assert.equal(frame.src,'/chat','initial URL must exist before the iframe is connected');}},framedUrl:()=>'/chat',closeOverlays(){},renderDock(){},trimFrames(){},history:{pushState(){}}};
    context.pendingAppNavigation=null;context.agentHome=false;context.agentConnected=false;context.homePath='/mobile';vm.createContext(context);vm.runInContext(display,context);
    const app={id:'chat',name:'Chat'}, mount={id:'mount',app_instance_id:'instance',content_url:'/chat'};
    context.displayMount(app,mount,false);
    assert.equal(context.loading.hidden,false);
    callbacks[0]();
    assert.equal(context.loading.hidden,true);
    const frame=context.frames.get('chat').frame;
    context.activeAppId=null;frame.hidden=true; // Home keeps the warm frame.
    context.displayMount(app,mount,false);
    assert.equal(context.frames.get('chat').frame,frame);
    assert.equal(callbacks.length,1);
    assert.equal(context.loading.hidden,true);
    assert.equal(frame.hidden,false);
});
test('reopening a still-loading frame keeps its spinner until load',()=>{
    const record={loaded:false,lastUsed:0,frame:{contentWindow:{postMessage(){}}},mountId:'mount'};
    const context={hideTodoDetail(){},hideInlineChat(){},activeAppId:null,mounts:new Map(),frames:new Map([['chat',record]]),title:{},home:{},stage:{},errorView:{},errorMessage:{},loading:{},Date,
        closeOverlays(){},renderDock(){},trimFrames(){},history:{pushState(){}}};
    context.pendingAppNavigation=null;context.agentHome=false;context.agentConnected=false;context.homePath='/mobile';vm.createContext(context);vm.runInContext(display,context);
    context.displayMount({id:'chat',name:'Chat'},{id:'mount'},false);
    assert.equal(context.loading.hidden,false);
});

test('blocked iframe displays an actionable error instead of a blank page',()=>{
 let loaded;const frame={contentWindow:{postMessage(){}},contentDocument:null,addEventListener(_,fn){loaded=fn;}};
 const context={hideTodoDetail(){},hideInlineChat(){},activeAppId:null,mounts:new Map(),frames:new Map(),title:{},home:{},stage:{},errorView:{},errorMessage:{},loading:{},Date,Math,crypto:{randomUUID:()=> 'test'},document:{createElement:()=>frame},frameHost:{appendChild(){}},framedUrl:()=>'/mobile/knowledge',closeOverlays(){},renderDock(){},trimFrames(){},history:{pushState(){}}};
 context.pendingAppNavigation=null;context.agentHome=false;context.agentConnected=false;context.homePath='/mobile';vm.createContext(context);vm.runInContext(display,context);context.displayMount({id:'knowledge',name:'Knowledge'},{id:'m',app_instance_id:'i'},false);loaded();assert.equal(context.errorView.hidden,false);assert.match(context.errorMessage.textContent,/重新打开/);assert.equal(context.loading.hidden,true);
});
test('Gallery and unknown catalog icons resolve to bundled icons',()=>{
 const iconSource=source.slice(source.indexOf('    function icon('),source.indexOf('    function appIcon('));const lucide=require('../web/static/js/lucide.min.js');const context={window:{lucide}};context.pendingAppNavigation=null;context.agentHome=false;context.agentConnected=false;context.homePath='/mobile';vm.createContext(context);vm.runInContext(iconSource,context);assert.match(context.icon('gallery-stacked-horizontal'),/data-lucide="images"/);assert.match(context.icon('missing-icon'),/data-lucide="app-window"/);
});
const open=source.slice(source.indexOf('    async function openApp('),source.indexOf('    async function closeApp('));
function openFixture(status){
 const calls=[];let removed=false,displayed=false;
 const context={catalogReady:true,appsById:new Map([['studio',{id:'studio'}]]),sequence:0,loading:{},stage:{},home:{},errorView:{},errorMessage:{},closeOverlays(){},mounts:new Map([['studio',{app_instance_id:'expired'}]]),frames:new Map([['studio',{frame:{remove(){removed=true;}}}]]),request:async(url)=>{calls.push(url);if(calls.length===1)throw Object.assign(new Error('failed'),{status});return {id:'fresh'};},displayMount(){displayed=true;}};
 context.pendingAppNavigation=null;context.agentHome=false;context.agentConnected=false;context.homePath='/mobile';vm.createContext(context);vm.runInContext(open,context);return {context,calls,removed:()=>removed,displayed:()=>displayed};
}
test('expired Studio instance is reopened once by App ID',async()=>{
 const f=openFixture(404);await f.context.openApp('studio',false);
 assert.deepEqual(f.calls,['/v1/mobile/app-instances/expired/focus','/v1/mobile/apps/studio/open']);
 assert.equal(f.removed(),true);assert.equal(f.displayed(),true);
});
test('authorization and server errors never retry as a fresh App',async()=>{
 for(const code of [401,403,500]){const f=openFixture(code);await f.context.openApp('studio',false);assert.equal(f.calls.length,1);assert.equal(f.removed(),false);assert.equal(f.context.errorView.hidden,false);}
});

test('sandbox readiness sends a JSON context request and completes loading',async()=>{
 const record={token:'token',instanceId:'instance',mountId:'mount',renderer:'sandbox',frame:{contentWindow:{postMessage(message){replies.push(message);}}}};
 const replies=[],calls=[];let handler;
 const c={frames:new Map([['snake',record]]),hideTodoDetail(){},hideInlineChat(){},activeAppId:'snake',loading:{hidden:false},errorView:{hidden:true},errorMessage:{},
 window:{location:{origin:'https://device.example'},addEventListener:(name,fn)=>handler=fn},
 fetch:async(url,options)=>{calls.push({url,options});assert.equal(options.headers['Content-Type'],'application/json');assert.deepEqual(JSON.parse(options.body),{method:'context'});return {ok:true,json:async()=>({surface:'mobile',capabilities:[]})};}};
 c.pendingAppNavigation=null;c.agentHome=false;c.agentConnected=false;c.homePath='/mobile';vm.createContext(c);
 vm.runInContext(source.slice(source.indexOf('    async function request('),source.indexOf('    function normalizeApp(')),c);
 const start=source.indexOf("    window.addEventListener('message', async");
 const end=source.indexOf("\n    });",start)+8;
 vm.runInContext(source.slice(start,end),c);
 await handler({source:record.frame.contentWindow,origin:'null',data:{type:'ai2apps.shell.ready',mountToken:'token',instanceId:'instance'}});
 assert.equal(calls.length,1);assert.match(calls[0].url,/app-mounts\/mount\/bridge$/);
 assert.equal(record.ready,true);assert.equal(c.loading.hidden,true);assert.equal(c.errorView.hidden,true);
 assert.equal(replies[0].type,'ai2apps.host.context');
});


test('reopening a failed frame retries its authorized mount instead of retaining failure',()=>{
 let removed=false;
 const frame={contentWindow:{postMessage(){}},addEventListener(){}};
 const c={hideTodoDetail(){},hideInlineChat(){},activeAppId:null,mounts:new Map(),frames:new Map([['studio',{failed:true,mountId:'m',frame:{remove(){removed=true;},contentWindow:{postMessage(){}}}}]]),title:{},home:{},stage:{},errorView:{},errorMessage:{},loading:{},Date,Math,crypto:{randomUUID:()=> 'new-token'},document:{createElement:()=>frame},frameHost:{appendChild(){}},framedUrl:()=>'/mobile/app-content/studio',closeOverlays(){},renderDock(){},trimFrames(){},history:{pushState(){}}};
 c.pendingAppNavigation=null;c.agentHome=false;c.agentConnected=false;c.homePath='/mobile';vm.createContext(c);vm.runInContext(display,c);
 c.displayMount({id:'studio',name:'Studio'},{id:'m',app_instance_id:'i'},false);
 assert.equal(removed,true);assert.equal(c.frames.get('studio').frame,frame);
 assert.equal(c.errorView.hidden,true);assert.equal(c.loading.hidden,false);
});

test('inner history traversal leaves the visible loaded App mounted',()=>{
 let handler,opens=0,homes=0;
 const record={loaded:true,failed:false,frame:{hidden:false}};
 const c={window:{addEventListener:(_,fn)=>handler=fn},URLSearchParams,location:{hash:'#app=todo'},frames:new Map([['todo',record]]),todoDetail:null,activeAppId:'todo',stage:{hidden:false},mounts:new Map(),appsById:new Map(),openApp(){opens++},showHome(){homes++}};
 c.pendingAppNavigation=null;c.agentHome=false;c.agentConnected=false;c.homePath='/mobile';vm.createContext(c);
 const start=source.indexOf("    window.addEventListener('popstate',");
 vm.runInContext(source.slice(start,source.indexOf('\n    async function boot()',start)),c);
 handler({state:{appId:'todo'}});assert.equal(opens,0);assert.equal(homes,0);
 record.failed=true;handler({state:{appId:'todo'}});assert.equal(opens,1);
 record.failed=false;c.activeAppId=null;handler({state:{appId:'todo'}});assert.equal(opens,2);
 c.location.hash='';handler({state:{appId:null}});assert.equal(homes,1);
});


test('opening captures history before replacing Home with loading state',async()=>{
 const f=openFixture(403);let pushes=0;
 f.context.home.hidden=false;f.context.stage.hidden=true;f.context.loading.hidden=true;
 f.context.history={pushState(state){pushes++;assert.equal(state.appId,'studio');assert.equal(f.context.home.hidden,false);assert.equal(f.context.stage.hidden,true);assert.equal(f.context.loading.hidden,true);}};
 await f.context.openApp('studio');assert.equal(pushes,1);
});
test('history restores a warm App synchronously without focus or spinner',()=>{
 let handler,restored=0;
 const record={loaded:true,failed:false,frame:{hidden:true}},app={id:'browser'},mount={id:'mount'};
 const c={window:{addEventListener:(_,fn)=>handler=fn},URLSearchParams,location:{hash:'#app=browser'},frames:new Map([['browser',record]]),mounts:new Map([['browser',mount]]),appsById:new Map([['browser',app]]),todoDetail:null,activeAppId:null,stage:{hidden:true},sequence:5,
 displayMount(a,m,push){assert.equal(a,app);assert.equal(m,mount);assert.equal(push,false);restored++;},openApp(){throw Error('no network focus on warm history');},showHome(){}};
 c.pendingAppNavigation=null;c.agentHome=false;c.agentConnected=false;c.homePath='/mobile';vm.createContext(c);const start=source.indexOf("    window.addEventListener('popstate',");vm.runInContext(source.slice(start,source.indexOf('\n    async function boot()',start)),c);
 handler({state:{appId:'browser'}});assert.equal(restored,1);assert.equal(c.sequence,6);
});

test('warm Intel displays before focus resolves and restores article history',async()=>{
 const id='ai2apps.intelligence',mount={id:'m',app_instance_id:'i'};
 const record={loaded:true,mountId:'m',intelDepth:2,frame:{remove(){}}};
 let resolve,shown=0;const entries=[];
 const c={catalogReady:true,appsById:new Map([[id,{id}]]),frames:new Map([[id,record]]),mounts:new Map([[id,mount]]),pendingAppNavigation:null,sequence:0,
 history:{state:{},pushState(s){this.state=s;entries.push(s)}},location:{href:'/mobile'},
 closeOverlays(){},displayMount(){shown++},request:()=>new Promise(r=>resolve=r),loading:{},stage:{},home:{},errorView:{},errorMessage:{},Date};
 c.agentHome=false;c.agentConnected=false;c.homePath='/mobile';vm.createContext(c);vm.runInContext(open,c);
 const pending=c.openApp(id);
 assert.equal(shown,1,'show live page before waiting for network');
 assert.deepEqual(entries.map(e=>e.intelDepth||0),[0,1,2]);
 resolve(mount);await pending;assert.equal(shown,1,'focus confirmation must not reactivate/reset the App');
});

// Exercise the real response parser and opening flow together: an outer proxy
// error must not be confused with the Local API's expired-instance response.
function recoveryFixture(responses, warm = true) {
    const calls = [], removed = [], displayed = [];
    const old = {loaded:warm, mountId:'old', frame:{remove(){removed.push('list');}},
        browserDetail:{frame:{remove(){removed.push('detail');}}}};
    const c = {catalogReady:true, appsById:new Map([['studio',{id:'studio'}]]), sequence:0,
        pendingAppNavigation:null, loading:{hidden:true}, stage:{}, home:{},
        errorView:{hidden:true}, errorMessage:{}, closeOverlays(){},
        mounts:new Map([['studio',{id:'old',app_instance_id:'expired'}]]),
        frames:new Map([['studio',old]]),
        fetch:async(url,options)=>{
            calls.push({url,method:options.method});
            const next=responses.shift();
            if(next instanceof Error)throw next;
            assert.ok(next,'unexpected retry');
            return {ok:next.status<400,status:next.status,json:async()=>{
                if(next.html)throw new SyntaxError('Unexpected token <');
                return next.body;
            }};
        },
        displayMount(app,mount){
            displayed.push(mount.id);
            c.mounts.set(app.id,mount);
            if(mount.id!=='old')c.frames.set(app.id,{mountId:mount.id,loaded:true});
        }};
    c.agentHome=false;c.agentConnected=false;c.homePath='/mobile';vm.createContext(c);
    vm.runInContext(source.slice(source.indexOf('    async function request('),source.indexOf('    function showToast(')),c);
    vm.runInContext(open,c);
    return {c,calls,removed,displayed,old};
}
test('HTML proxy 404 retains warm App and detail without reopening or replaying POST',async()=>{
    const f=recoveryFixture([{status:404,html:true}]);
    await f.c.openApp('studio',false);
    assert.equal(f.calls.length,1);
    assert.equal(f.calls[0].method,'POST');
    assert.equal(f.c.frames.get('studio'),f.old);
    assert.deepEqual(f.removed,[]);
    assert.deepEqual(f.displayed,['old']);
});
test('HTML proxy 404 without a usable frame shows an error and never reopens',async()=>{
    const f=recoveryFixture([{status:404,html:true}],false);
    await f.c.openApp('studio',false);
    assert.equal(f.calls.length,1);
    assert.equal(f.c.errorView.hidden,false);
    assert.match(f.c.errorMessage.textContent,/中转/);
    assert.equal(f.c.loading.hidden,true);
    assert.deepEqual(f.removed,[]);
});
test('Local JSON 404 removes both old frames and opens one replacement',async()=>{
    const f=recoveryFixture([{status:404,body:{detail:'App instance not found'}},{status:200,body:{id:'new'}}]);
    await f.c.openApp('studio',false);
    assert.deepEqual(f.removed,['detail','list']);
    assert.deepEqual(f.calls.map(x=>x.url),['/v1/mobile/app-instances/expired/focus','/v1/mobile/apps/studio/open']);
    assert.deepEqual(f.displayed,['old','new']);
    assert.equal(f.c.frames.get('studio').mountId,'new');
});
for(const failure of [429,503,'network','html404'])test(`replacement ${failure} shows recoverable error after old frames are removed`,async()=>{
    const failed=failure==='network'?new Error('Network unavailable'):failure==='html404'?{status:404,html:true}:{status:failure,body:{detail:'Unavailable'}};
    const f=recoveryFixture([{status:404,body:{detail:'App instance not found'}},failed]);
    await f.c.openApp('studio',false);
    assert.equal(f.calls.length,2);
    assert.deepEqual(f.removed,['detail','list']);
    assert.equal(f.c.frames.size,0);
    assert.equal(f.c.errorView.hidden,false);
    assert.equal(f.c.loading.hidden,true);
    assert.ok(f.c.errorMessage.textContent);
    // A later explicit retry uses the normal open endpoint, not the dead instance.
    f.c.fetch=async(url)=>{assert.equal(url,'/v1/mobile/apps/studio/open');return {ok:true,status:200,json:async()=>({id:'recovered'})};};
    await f.c.openApp('studio',false);
    assert.equal(f.c.frames.get('studio').mountId,'recovered');
});
for(const status of [401,403])test(`focus ${status} does not attempt replacement and clears inaccessible warm frames`,async()=>{
    const f=recoveryFixture([{status,body:{detail:'Access denied'}}]);
    await f.c.openApp('studio',false);
    assert.equal(f.calls.length,1);
    assert.deepEqual(f.removed,['detail','list']);
    assert.equal(f.c.errorView.hidden,false);
});
