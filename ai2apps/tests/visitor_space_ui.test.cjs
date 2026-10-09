const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/space.js'),'utf8');
function setup(){
 const make=tag=>({tag,children:[],append(...nodes){this.children.push(...nodes);},replaceChildren(...nodes){this.children=nodes;},addEventListener(name,fn){this[name]=fn;}});
 const window={};vm.runInNewContext(source,{window,URL,document:{createElement:make,querySelector:()=>null}});return {render:window.renderVisitorSpace,root:make('main')};
}
function all(root){return [root,...root.children.flatMap(all)];}
test('shared preview uses text, hides unpublished cards and cannot launch apps',()=>{
 const {render,root}=setup();render(root,{title:'<script>secret()</script>',theme:'violet',cards:[{kind:'text',title:'hidden',hidden:true},{kind:'app',title:'Game'},{kind:'link',title:'Link',url:'https://example.com'}]},{preview:true});
 const nodes=all(root);assert.equal(nodes.find(n=>n.tag==='h1').textContent,'<script>secret()</script>');
 assert.ok(!nodes.some(n=>n.textContent==='hidden'));assert.equal(nodes.find(n=>n.tag==='button').disabled,true);
 let prevented=false;nodes.find(n=>n.tag==='a').click({preventDefault(){prevented=true;}});assert.ok(prevented);
 assert.ok(nodes.every(n=>!n.innerHTML));
});
test('invalid external URLs never become clickable script URLs',()=>{
 const {render,root}=setup();render(root,{title:'Space',cards:[{kind:'link',url:'javascript:alert(1)'}]});assert.equal(all(root).find(n=>n.tag==='a').href,undefined);
});
async function failedRecovery(saved){
 const elements=Object.fromEntries(['visitor-root','status','space-recovery','visitor-player'].map(id=>[id,{hidden:true,replaceChildren(){}}]));
 const context={window:{addEventListener(){}},URL,URLSearchParams,location:{hash:'',pathname:'/mobile/space/complete'},history:{replaceState(){}},sessionStorage:{getItem(){return saved},setItem(){}},clearTimeout(){},setTimeout(){},fetch:async()=>({ok:false,status:401}),document:{querySelector:()=>true,getElementById:id=>elements[id],addEventListener(){}}};
 vm.runInNewContext(source,context);await new Promise(resolve=>setImmediate(resolve));return elements;
}
test('first failed connection without user URL cannot navigate to Cloud root',async()=>{
 for(const value of [null,'https://coder.ai2apps.com/','https://evil.example/u/00000000-0000-0000-0000-000000000000','https://user@coder.ai2apps.com/u/00000000-0000-0000-0000-000000000000']){
  const e=await failedRecovery(value);assert.equal(e['space-recovery'].hidden,true);assert.equal(e['space-recovery'].href,undefined);assert.match(e.status.textContent,/重新扫描/);
 }
});
test('failed connection retains verified fixed user URL for reentry',async()=>{
 const url='https://coder.ai2apps.com/u/00000000-0000-0000-0000-000000000000';const e=await failedRecovery(url);assert.equal(e['space-recovery'].hidden,false);assert.equal(e['space-recovery'].href,url);
});
test('foreground reading renews without rerendering, background does not report activity',async()=>{
 let now=1000000,version=1;const calls=[],handlers={};
 const make=()=>({children:[],dataset:{},append(...n){this.children.push(...n)},replaceChildren(...n){this.children=n;this.replaced=(this.replaced||0)+1},addEventListener(){}});
 const elements=Object.fromEntries(['visitor-root','status','space-recovery','visitor-player'].map(id=>[id,make()]));
 const document={visibilityState:'visible',querySelector:s=>s==='[data-visitor-public]',getElementById:id=>elements[id],createElement:make,addEventListener:(n,f)=>handlers[n]=f};
 const context={window:{addEventListener:(n,f)=>handlers[n]=f},URL,URLSearchParams,Date:{now:()=>now},document,location:{hash:'',pathname:'/mobile/space/home'},history:{replaceState(){}},sessionStorage:{getItem(){return null},setItem(){}},setTimeout(){},clearTimeout(){},fetch:async(path,opts)=>{calls.push(opts.method);return{ok:true,json:async()=>({sessionProtocol:'personal-space-anonymous-session-v1',expiresAt:now/1000+120,leaseVersion:version++,revision:1,userUrl:'https://coder.ai2apps.com/u/00000000-0000-0000-0000-000000000000',space:{title:'Published',cards:[]}})}}};
 vm.runInNewContext(source,context);await new Promise(r=>setImmediate(r));const replaced=elements['visitor-root'].replaced;
 now+=65000;handlers.pageshow();await new Promise(r=>setImmediate(r));assert.equal(calls.at(-1),'POST');assert.equal(elements['visitor-root'].replaced,replaced);
 now+=65000;document.visibilityState='hidden';handlers.pageshow();await new Promise(r=>setImmediate(r));assert.equal(calls.at(-1),'GET');assert.equal(elements['visitor-root'].replaced,replaced);
});
test('pageshow cannot check Cookie before handoff exchange completes',async()=>{
 let release;const calls=[],handlers={};const make=()=>({children:[],dataset:{},append(){},replaceChildren(){},addEventListener(){}});const elements={};
 const context={window:{addEventListener:(n,f)=>handlers[n]=f},URL,URLSearchParams,Date,location:{hash:'#handoff=vs1.test.secret',pathname:'/mobile/space/session/complete'},history:{replaceState(){}},sessionStorage:{getItem(){return null},setItem(){}},setTimeout(){},clearTimeout(){},document:{visibilityState:'visible',querySelector:s=>s==='[data-visitor-public]'||s==='[data-visitor-session]',getElementById:id=>elements[id]||(elements[id]=make()),createElement:make,addEventListener:(n,f)=>handlers[n]=f},fetch:async(path)=>{calls.push(path);if(path.endsWith('/exchange'))await new Promise(r=>release=r);return{ok:true,json:async()=>({expiresAt:Date.now()/1000+120,revision:1,space:{title:'Test',cards:[]}})}}};
 vm.runInNewContext(source,context);handlers.pageshow();handlers.visibilitychange();assert.equal(calls.length,1);release();await new Promise(r=>setImmediate(r));assert.equal(calls.length,2);assert.ok(calls[1].endsWith('/bootstrap'));
});
