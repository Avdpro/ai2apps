const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
    constructor() { this.children=[]; this.attrs={}; this.hidden=false; }
    set textContent(value) { this.text=value; this.children=[]; }
    get textContent() { return this.text; }
    append(...items) { this.children.push(...items); }
    replaceChildren() { this.children=[]; }
    setAttribute(key,value) { this.attrs[key]=value; }
    addEventListener(_,fn) { this.click=fn; }
    querySelectorAll() { return this.children.map(row=>row.children[1]); }
}
function setup(device, cloudFails=false, options={}) {
 const list=new Element(), error=new Element(), calls=[];
 const confirmations=[];
 const context={window:{confirm:message=>{confirmations.push(message);return options.agree!==false;}},root:{querySelector:selector=>selector.includes('devices')?list:selector.includes('usage')?null:error}, document:{createElement:()=>new Element()},tr:key=>key,
 request:async()=>({devices:device?[device]:[],connector:{available:true}}),
 jsonRequest:async(path)=>{calls.push(path); if(path.endsWith('reconcile')) { if(cloudFails) throw Error('offline'); return {devices:[device]}; } if(options.failure&&path.endsWith(options.failure))throw Object.assign(Error('request failed'),{code:options.code}); if(path.endsWith('/start'))device.enabled=true;else if(path.endsWith('/stop'))device.enabled=false; return device; }};
 const source=fs.readFileSync('web/static/js/shell.js','utf8');
 vm.createContext(context);
 vm.runInContext(source.slice(source.indexOf('    const homeRemote ='),source.indexOf('    function provisioningReturnApp(')),context);
 context.requestRemoteOwnerPassword=async()=>{confirmations.push('owner password dialog');return options.agree===false?null:'fixture-password';};
 return {context,list,error,calls,confirmations};
}
test('enabled is connecting until proxy is connected; switch stops once',async()=>{
 const h=setup({deviceId:'a/b',displayName:'Device',status:'active',enabled:true,proxyConnected:false});
 await h.context.refreshHomeRemote();
 assert.equal(h.list.children[0].children[0].children[1].textContent,'shell.home.remote.connecting');
 const toggle=h.list.children[0].children[1];
 await Promise.all([toggle.click(),toggle.click()]);
 assert.equal(h.calls.filter(p=>p.endsWith('/stop')).length,1);
 assert.ok(h.calls.includes('/v1/platform/remote/devices/a%2Fb/stop'));
 assert.equal(h.list.children[0].children[1].attrs['aria-checked'],'false');
});
test('cloud failure hides stale online address and preserves stop',async()=>{
 const h=setup({deviceId:'a',displayName:'D',status:'active',enabled:true,proxyConnected:true,publicOrigin:'https://example.com'},true);
 await h.context.refreshHomeRemote();
 const [copy,toggle]=h.list.children[0].children;
 assert.equal(copy.children[1].textContent,'shell.home.remote.unavailable');
 assert.equal(copy.children.length,2);
 assert.equal(toggle.disabled,false);
});
test('empty configuration renders setup state',async()=>{
 const h=setup(null); await h.context.refreshHomeRemote();
 assert.equal(h.list.textContent,'shell.home.remote.empty');
});

function usageSetup() {
 const usage=new Element();let now=0,calls=0,fail=false;
 const context={root:{querySelector:s=>s.includes('usage')?usage:null},Date:{now:()=>now},Intl,
 tr:key=>key,request:async path=>{assert.equal(path,'/v1/platform/remote/usage');calls++;if(fail)throw Error('unavailable');return {usageMonth:'2026-10-01',totalBytes:'1073741824',quotaBytes:'10737418240',ingressBytes:'536870912',egressBytes:'536870912'};}};
 const source=fs.readFileSync('web/static/js/shell.js','utf8');vm.createContext(context);
 vm.runInContext(source.slice(source.indexOf('    const homeRemote ='),source.indexOf('    function provisioningReturnApp(')),context);
 return {context,usage,get calls(){return calls;},advance:ms=>now+=ms,fail:()=>fail=true};
}
test('traffic loads once and refreshes at five minutes independently of status polling',async()=>{
 const h=usageSetup();await Promise.all([h.context.refreshHomeUsage(),h.context.refreshHomeUsage()]);
 assert.equal(h.calls,1);assert.match(h.usage.textContent,/1 GiB \/ 10 GiB/);assert.equal(h.usage.hidden,false);assert.match(h.usage.title,/UTC/);
 h.advance(299999);await h.context.refreshHomeUsage();assert.equal(h.calls,1);
 h.advance(1);await h.context.refreshHomeUsage();assert.equal(h.calls,2);
});
test('traffic failure does not display stale numbers or poll on every connection refresh',async()=>{
 const h=usageSetup();await h.context.refreshHomeUsage();h.fail();h.advance(300000);await h.context.refreshHomeUsage();
 assert.equal(h.usage.textContent,'—');assert.equal(h.usage.title,'');
 await h.context.refreshHomeUsage();assert.equal(h.calls,2);
 vm.runInContext('offlineMode=true',h.context);await h.context.refreshHomeUsage();assert.equal(h.usage.hidden,true);
});

for(const agree of [true,false])test('expiring key requires consent before rotation and start: '+agree,async()=>{
 const h=setup({deviceId:'a/b',displayName:'D',status:'active',enabled:false,credentialExpiresAt:new Date(Date.now()+86400000).toISOString()},false,{agree});await h.context.refreshHomeRemote();const toggle=h.list.children[0].children[1];await Promise.all([toggle.click(),toggle.click()]);assert.equal(h.confirmations.length,1);
 const writes=h.calls.filter(x=>!x.endsWith('/reconcile'));assert.deepEqual(writes,agree?['/v1/platform/remote/devices/a%2Fb/credentials/rotate','/v1/platform/auth/cloud-member/activate','/v1/platform/remote/devices/a%2Fb/start']:[]);
});
test('rotation failure prevents start and displays error',async()=>{
 const h=setup({deviceId:'a',displayName:'D',status:'active',enabled:false,credentialExpiresAt:'2020-01-01'},false,{failure:'/credentials/rotate'});await h.context.refreshHomeRemote();await h.list.children[0].children[1].click();assert.equal(h.calls.some(x=>x.endsWith('/start')),false);assert.equal(h.error.hidden,false);assert.equal(h.error.textContent,'request failed');
});
test('server rotation code handles stale expiry once; other errors do not rotate',async()=>{
 for(const code of ['remote_credential_rotation_required','cloud_unavailable']){
 const h=setup({deviceId:'a',displayName:'D',status:'active',enabled:false},false,{failure:'/start',code});await h.context.refreshHomeRemote();await h.list.children[0].children[1].click();assert.equal(h.confirmations.length,code==='remote_credential_rotation_required'?1:0);assert.equal(h.calls.filter(x=>x.endsWith('/credentials/rotate')).length,code==='remote_credential_rotation_required'?1:0);
 }
});
test('HTTP helper retains structured platform error code',async()=>{
 const source=fs.readFileSync('web/static/js/shell.js','utf8');const context={fetch:async()=>({ok:false,status:409,json:async()=>({error:{code:'remote_credential_rotation_required',message:'Rotate first'}})})};vm.createContext(context);vm.runInContext(source.slice(source.indexOf('    async function request('),source.indexOf('    const homeRemote =')),context);await assert.rejects(context.request('/test'),e=>e.status===409&&e.code==='remote_credential_rotation_required'&&e.message==='Rotate first');
});

test('expired Local session recovers through current Cloud browser identity before status retry',async()=>{
 const h=setup({deviceId:'a',displayName:'D',status:'active',enabled:false});let reads=0;
 h.context.request=async()=>{if(++reads===1)throw Object.assign(Error('session expired'),{status:401,code:'local_session_required'});return {devices:[],connector:{available:true}};};
 await h.context.refreshHomeRemote();assert.equal(reads,2);assert.equal(h.calls.filter(x=>x==='/v1/platform/auth/cloud-member/activate').length,1);assert.equal(h.calls.some(x=>x.endsWith('/credentials/rotate')),false);
});
test('failed identity recovery is shown and bounded, with no rotate or start',async()=>{
 const h=setup(null);let activations=0;h.context.request=async()=>{throw Object.assign(Error('session expired'),{status:401,code:'local_session_required'});};
 h.context.jsonRequest=async()=>{activations++;throw Error('Please sign in again');};await h.context.refreshHomeRemote();await h.context.refreshHomeRemote();assert.equal(activations,1);assert.equal(h.error.textContent,'Please sign in again');assert.equal(h.error.hidden,false);
});
