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
function setup(device, cloudFails=false) {
 const list=new Element(), error=new Element(), calls=[];
 const context={root:{querySelector:selector=>selector.includes('devices')?list:error}, document:{createElement:()=>new Element()},tr:key=>key,
 request:async()=>({devices:device?[device]:[],connector:{available:true}}),
 jsonRequest:async(path)=>{calls.push(path); if(path.endsWith('reconcile')) { if(cloudFails) throw Error('offline'); return {devices:[device]}; } device.enabled=!device.enabled; return device; }};
 const source=fs.readFileSync('web/static/js/shell.js','utf8');
 vm.createContext(context);
 vm.runInContext(source.slice(source.indexOf('    const homeRemote ='),source.indexOf('    function provisioningReturnApp(')),context);
 return {context,list,error,calls};
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
