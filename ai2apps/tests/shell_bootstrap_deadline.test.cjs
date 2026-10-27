const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(process.env.AI2APPS_SHELL_SOURCE || path.resolve(__dirname,'../../../moz/acefox-firefox-153/browser/components/ai2apps/content/shell.mjs'),'utf8');
const body=source.slice(source.indexOf('function readJSON('),source.indexOf('\nfunction installNavigationGuard'));
function fixture(){
 let timer,callback,cleared=false,cancelled=false;
 const channel={loadFlags:0,QueryInterface(){return this},cancel(){cancelled=true}};
 const scope={NetUtil:{newChannel:()=>channel,asyncFetch:(ch,cb)=>callback=cb,readInputStreamToString:()=>'{"status":"ready"}'},
 Ci:{nsIContentPolicy:{TYPE_OTHER:1},nsIRequest:{LOAD_BYPASS_CACHE:1},nsIHttpChannel:{}},Cr:{NS_ERROR_NET_TIMEOUT:7},
 Components:{isSuccessCode:n=>n===0},setTimeout:(cb,ms)=>{assert.equal(ms,5000);timer=cb;return 1},clearTimeout:()=>cleared=true};
 vm.createContext(scope);vm.runInContext(body,scope);
 return {run:()=>scope.readJSON('http://127.0.0.1/bootstrap'),timeout:()=>timer(),
 reply:()=>callback({available:()=>1,close(){}},0,{QueryInterface:()=>({responseStatus:200})}),
 state:()=>({cleared,cancelled})};
}
test('hung bootstrap request cancels and rejects rather than blocking startup deadline',async()=>{
 const f=fixture(),p=f.run();f.timeout();await assert.rejects(p,/timed out/);assert.equal(f.state().cancelled,true);
});
test('successful bootstrap clears request deadline',async()=>{
 const f=fixture(),p=f.run();f.reply();assert.equal((await p).status,'ready');assert.equal(f.state().cleared,true);
});
