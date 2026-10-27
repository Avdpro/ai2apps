const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/mobile.js','utf8');
function fixture(){
 let index=0,handler;const stack=[{appId:null,mobileRoot:true}],requests=[];
 const c={catalogReady:true,activeAppId:null,pendingAppNavigation:null,sequence:0,history:{get state(){return stack[index]},pushState(s){stack.splice(++index);stack[index]=s},go(n){index+=n;assert.ok(index>=0);queueMicrotask(()=>handler({state:stack[index]}));}},appsById:new Map(['a','b','c'].map(id=>[id,{id}])),mounts:new Map(),frames:new Map(),loading:{},stage:{},home:{},errorView:{},errorMessage:{},title:{},closeOverlays(){},hideTodoDetail(){},leaveTodoDetail(){return true},renderDock(){},request:async url=>{requests.push(url);return {id:url}},displayMount(app){c.activeAppId=app.id},window:{addEventListener(_,fn){handler=fn}},URLSearchParams,location:{hash:''},todoDetail:null};
 Object.assign(c,{homePath:'/mobile',agentHome:false,root:{querySelector:()=>null},window:{addEventListener(_,fn){handler=fn},dispatchEvent(){}},CustomEvent:class {}});
 vm.createContext(c);
 vm.runInContext(source.slice(source.indexOf('    function appHistoryDepth('),source.indexOf('    function framedUrl(')),c);
 vm.runInContext(source.slice(source.indexOf('    async function openApp('),source.indexOf('    async function closeApp(')),c);
 const start=source.indexOf("    window.addEventListener('popstate',");vm.runInContext(source.slice(start,source.indexOf('    async function boot()',start)),c);
 return {c,stack,requests,flush:()=>new Promise(r=>setImmediate(r))};
}
test('100 App switches retain only Home and current App',async()=>{
 const f=fixture();for(let i=0;i<100;i++){await f.c.openApp(i%2?'b':'a');await f.flush();assert.equal(f.stack.length,2);assert.equal(f.stack[0].appId,null);}
 assert.equal(f.c.history.state.appId,'b');f.c.history.go(-1);await f.flush();assert.equal(f.c.activeAppId,null);
});
test('same App click keeps detail and sends no focus request',async()=>{
 const f=fixture();await f.c.openApp('a');f.c.history.pushState({appId:'a',browserMiniApp:'mini'});
 const before=f.requests.length;await f.c.openApp('a');assert.equal(f.stack.length,3);assert.equal(f.requests.length,before);assert.equal(f.c.history.state.browserMiniApp,'mini');
});
test('switching out of a Mini-App discards its history and returns new App directly to Home',async()=>{
 const f=fixture();await f.c.openApp('a');f.c.history.pushState({appId:'a',browserMiniApp:'mini'});await f.c.openApp('b');await f.flush();assert.equal(f.stack.length,2);assert.equal(f.c.history.state.appId,'b');
 f.c.showHome();await f.flush();assert.equal(f.c.activeAppId,null);await f.c.openApp('c');assert.equal(f.stack.length,2);
});
test('latest navigation wins while traversing Home; repeated pending open is deduplicated',async()=>{
 const f=fixture();await f.c.openApp('a');f.c.openApp('b');f.c.openApp('c');await f.flush();assert.equal(f.c.activeAppId,'c');assert.equal(f.requests.length,2);
});
test('Todo leave veto preserves current history',async()=>{
 const f=fixture();await f.c.openApp('a');f.c.leaveTodoDetail=()=>false;await f.c.openApp('b');assert.equal(f.c.history.state.appId,'a');assert.equal(f.requests.length,1);
});
