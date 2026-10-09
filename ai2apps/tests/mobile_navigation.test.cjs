const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/mobile.js'),'utf8');
const display = source.slice(source.indexOf('    function displayMount('),source.indexOf('    async function openApp('));
test('reopening a loaded Chat frame dismisses the spinner without reloading it',()=>{
    const callbacks=[];
    const context={activeAppId:null,mounts:new Map(),frames:new Map(),title:{},home:{},stage:{},errorView:{},errorMessage:{},loading:{},Date,Math,
        crypto:{randomUUID:()=> 'test'},document:{createElement:()=>({addEventListener:(_,fn)=>callbacks.push(fn),contentWindow:{postMessage(){}},contentDocument:{URL:'https://device.example/mobile/chat',contentType:'text/html',body:{children:[{}]}},remove(){}})},
        frameHost:{appendChild(){}},framedUrl:()=>'/chat',closeOverlays(){},renderDock(){},trimFrames(){},history:{pushState(){}}};
    vm.createContext(context);vm.runInContext(display,context);
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
    const context={activeAppId:null,mounts:new Map(),frames:new Map([['chat',record]]),title:{},home:{},stage:{},errorView:{},errorMessage:{},loading:{},Date,
        closeOverlays(){},renderDock(){},trimFrames(){},history:{pushState(){}}};
    vm.createContext(context);vm.runInContext(display,context);
    context.displayMount({id:'chat',name:'Chat'},{id:'mount'},false);
    assert.equal(context.loading.hidden,false);
});

test('blocked iframe displays an actionable error instead of a blank page',()=>{
 let loaded;const frame={contentWindow:{postMessage(){}},contentDocument:null,addEventListener(_,fn){loaded=fn;}};
 const context={activeAppId:null,mounts:new Map(),frames:new Map(),title:{},home:{},stage:{},errorView:{},errorMessage:{},loading:{},Date,Math,crypto:{randomUUID:()=> 'test'},document:{createElement:()=>frame},frameHost:{appendChild(){}},framedUrl:()=>'/mobile/knowledge',closeOverlays(){},renderDock(){},trimFrames(){},history:{pushState(){}}};
 vm.createContext(context);vm.runInContext(display,context);context.displayMount({id:'knowledge',name:'Knowledge'},{id:'m',app_instance_id:'i'},false);loaded();assert.equal(context.errorView.hidden,false);assert.match(context.errorMessage.textContent,/嵌入策略/);assert.equal(context.loading.hidden,true);
});
test('Gallery and unknown catalog icons resolve to bundled icons',()=>{
 const iconSource=source.slice(source.indexOf('    function icon('),source.indexOf('    function appIcon('));const lucide=require('../web/static/js/lucide.min.js');const context={window:{lucide}};vm.createContext(context);vm.runInContext(iconSource,context);assert.match(context.icon('gallery-stacked-horizontal'),/data-lucide="images"/);assert.match(context.icon('missing-icon'),/data-lucide="app-window"/);
});
const open=source.slice(source.indexOf('    async function openApp('),source.indexOf('    async function closeApp('));
function openFixture(status){
 const calls=[];let removed=false,displayed=false;
 const context={catalogReady:true,appsById:new Map([['studio',{id:'studio'}]]),sequence:0,loading:{},stage:{},home:{},errorView:{},errorMessage:{},closeOverlays(){},mounts:new Map([['studio',{app_instance_id:'expired'}]]),frames:new Map([['studio',{frame:{remove(){removed=true;}}}]]),request:async(url)=>{calls.push(url);if(calls.length===1)throw Object.assign(new Error('failed'),{status});return {id:'fresh'};},displayMount(){displayed=true;}};
 vm.createContext(context);vm.runInContext(open,context);return {context,calls,removed:()=>removed,displayed:()=>displayed};
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
 const c={frames:new Map([['snake',record]]),activeAppId:'snake',loading:{hidden:false},errorView:{hidden:true},errorMessage:{},
 window:{location:{origin:'https://device.example'},addEventListener:(name,fn)=>handler=fn},
 fetch:async(url,options)=>{calls.push({url,options});assert.equal(options.headers['Content-Type'],'application/json');assert.deepEqual(JSON.parse(options.body),{method:'context'});return {ok:true,json:async()=>({surface:'mobile',capabilities:[]})};}};
 vm.createContext(c);
 vm.runInContext(source.slice(source.indexOf('    async function request('),source.indexOf('    function normalizeApp(')),c);
 const start=source.indexOf("    window.addEventListener('message',");
 const end=source.indexOf("\n    });",start)+8;
 vm.runInContext(source.slice(start,end),c);
 await handler({source:record.frame.contentWindow,origin:'null',data:{type:'ai2apps.shell.ready',mountToken:'token',instanceId:'instance'}});
 assert.equal(calls.length,1);assert.match(calls[0].url,/app-mounts\/mount\/bridge$/);
 assert.equal(record.ready,true);assert.equal(c.loading.hidden,true);assert.equal(c.errorView.hidden,true);
 assert.equal(replies[0].type,'ai2apps.host.context');
});
