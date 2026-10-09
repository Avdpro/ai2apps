const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const path=process.env.ACEFOX_SHELL_SOURCE;
if(!path)throw Error('Set ACEFOX_SHELL_SOURCE to the matching native Shell source');
const source=fs.readFileSync(path,'utf8');
const start=source.indexOf('  const pollShellBrowserWindow = async () =>');
const end=source.indexOf('\n  const ',start+10);
const fn=source.slice(start,end);
function harness(request){
 const calls=[];const context={activeConnection:{localOrigin:'http://127.0.0.1:1234',helperToken:'test'},shellBrowserRequestBusy:false,
 readJSON:async()=>request,currentBrowserProfile:async()=>{calls.push('profile');throw Error('account service unavailable')},
 openOrFocusAceFoxBrowser:(...args)=>{calls.push(['open',...args]);return 'launched'},completeShellBrowserRequest:async(_,status)=>calls.push(status),
 aceFoxBrowserWindows:new Map(),focusAI2AppsWindow(){},setTimeout(){},console:{error(){}}};
 vm.runInNewContext(fn+'\nglobalThis.poll=pollShellBrowserWindow;',context);return {context,calls};
}
test('default Profile opens without waiting for embedded account/profile query',async()=>{
 const {context,calls}=harness({action:'open',profile_key:'key',profile_name:'Default',is_default:true});
 context.currentBrowserProfile=()=>new Promise(()=>{});
 await Promise.race([context.poll(),new Promise((_,reject)=>setTimeout(()=>reject(Error('launch stalled on profile query')),100))]);
 assert.equal(calls[0][0],'open');assert.equal(calls[0][3],'Default');assert.equal(calls[1],'launched');
});
test('named Profile keeps supplied identity and initial URL',async()=>{
 const {context,calls}=harness({action:'open',profile_key:'key',profile_name:'Work',is_default:false,initial_url:'https://example.com'});
 await context.poll();assert.equal(calls.includes('profile'),false);assert.deepEqual(Array.from(calls[0]),['open','key','https://example.com','Work']);
});
test('old Local without Profile metadata retains fallback',async()=>{
 const {context,calls}=harness({action:'open',profile_key:'key'});await context.poll();assert.equal(calls[0],'profile');assert.equal(calls[1][0],'open');
});
