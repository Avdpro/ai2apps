const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),crypto=require('node:crypto');
const path=require('node:path');
function node(tag){return {tag,children:[],listeners:{},style:{},textContent:'',append(...children){this.children.push(...children)},replaceChildren(...children){this.children=[...children]},setAttribute(){},addEventListener(t,fn){this.listeners[t]=fn},get firstChild(){return this.children[0]},focus(){},showModal(){this.open=true},close(){this.open=false},remove(){this.removed=true}};}
const request={id:'phr_one',state:'pending',consumer:'<img src=x onerror=bad()>',publisher:'Signed publisher',version:'1.0.0',event:'Record changed',scope:'subjects',subjects:['record-one'],filters:[],background:false,read_details:false,actions:[],grant_expires:2000000000,review_hash:'a'.repeat(64)};
function host(){const calls=[],body=node('body'),window={},document={documentElement:{lang:'en'},body,createElement:node};
 const sandbox={window,document,navigator:{language:'en'},crypto,fetch:async(url,options)=>{calls.push({url,...options});return {ok:true,json:async()=>options.method==='GET'?request:{status:'approved',grant_id:'phg_one'}};}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/static/js/hook_consent.js'),'utf8'),sandbox);return {calls,body,window,sandbox};}
async function flush(){await new Promise(r=>setImmediate(r));}
test('host review renders Package text as text and never grants before an explicit click',async()=>{const f=host();const result=f.window.AI2AppsHookConsent.review('phr_one');await flush();assert.equal(f.calls.length,1);assert.equal(f.calls[0].method,'GET');
 const d=f.body.children[0];assert.ok(d.open);assert.ok(d.children.some(x=>x.textContent===request.consumer));assert.ok(!d.children.some(x=>x.tag==='img'));
 const controls=d.children.at(-1);await controls.children[2].listeners.click();assert.equal((await result).status,'approved');assert.equal(f.calls[1].method,'POST');const sent=JSON.parse(f.calls[1].body);assert.equal(sent.review_hash,request.review_hash);assert.ok(sent.request_id);assert.ok(!('approved' in sent));});
test('closing review leaves the request pending and sends no decision',async()=>{const f=host();const result=f.window.AI2AppsHookConsent.review('phr_one');await flush();f.body.children[0].listeners.cancel({preventDefault(){}});assert.equal((await result).status,'pending');assert.equal(f.calls.length,1);});
test('lost decision acknowledgement reuses its request ID on retry',async()=>{const f=host();const fetch=f.sandbox.fetch;let lost=false;
 f.sandbox.fetch=async(...args)=>{const value=await fetch(...args);if(args[1].method==='POST'&&!lost){lost=true;throw Error('lost acknowledgement');}return value;};
 const result=f.window.AI2AppsHookConsent.review('phr_one');await flush();const button=f.body.children[0].children.at(-1).children[2];
 await button.listeners.click();assert.equal(f.body.children[0].open,true);await button.listeners.click();await result;
 const posts=f.calls.filter(x=>x.method==='POST');assert.equal(posts.length,2);assert.equal(JSON.parse(posts[0].body).request_id,JSON.parse(posts[1].body).request_id);
});
test('sandbox App SDK only accepts replies from its parent and exact mount',async()=>{
 const listeners={},messages=[],parent={postMessage:m=>messages.push(m)};
 const root={location:{hash:'#ai2apps-mount=trusted-mount&ai2apps-instance=owned-instance'},parent,addEventListener:(t,fn)=>listeners[t]=fn,removeEventListener(){}};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/static/js/package_events.js'),'utf8'),{globalThis:root,URLSearchParams,crypto,setTimeout,clearTimeout,Map,Error});const client=root.AI2AppsPackageEvents.client({timeout:1000});
 let settled=false;const promise=client.list().then(x=>{settled=true;return x});const sent=messages[0];assert.equal(sent.instanceId,'owned-instance');
 const response={type:'ai2apps.host.response',requestId:sent.requestId,mountToken:'trusted-mount',instanceId:'owned-instance',ok:true,result:{items:[]}};
 listeners.message({source:{},data:response});listeners.message({source:parent,data:{...response,mountToken:'forged'}});await flush();assert.equal(settled,false);
 listeners.message({source:parent,data:response});assert.deepEqual(JSON.parse(JSON.stringify(await promise)),{items:[]});client.close();await assert.rejects(()=>client.list(),/closed/);
});

test('global permission manager reads first and pauses with a version-bound explicit action',async()=>{const f=host();f.sandbox.fetch=async(url,options)=>{f.calls.push({url,...options});return {ok:true,json:async()=>url.endsWith('/requests')?{items:[]}:{items:[{id:'phg_one',consumer:'Observer',state:'active',revision:3,expires:2000000000,accepted_release:{version:'1.0.0'},permissions:{event_type:'arbitrary.changed',scope:'subjects',subjects:['record-one'],background:false,read_details:false,actions:[]}}]}};};
 await f.window.AI2AppsHookConsent.manage();assert.equal(f.calls.length,2);assert.ok(f.calls.every(x=>x.method==='GET'));const content=f.body.children[0].children[1];const row=content.children.find(x=>x.tag==='section');assert.ok(row);const pause=row.children.find(x=>x.tag==='button'&&x.textContent==='Pause');await pause.listeners.click();const post=f.calls.find(x=>x.method==='POST');assert.equal(post.url,'/v1/platform/package-hooks/grants/phg_one/control/pause');assert.equal(JSON.parse(post.body).expected_revision,3);
});
