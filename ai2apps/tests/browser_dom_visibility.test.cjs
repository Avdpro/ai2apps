const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8');
const visible=vm.runInNewContext('('+source+')',{getComputedStyle:n=>n.style||{},innerWidth:100,innerHeight:100});
function element({parent=null,style={},attrs={},box=true,host=null}={}){return {parentElement:parent,style,getAttribute:k=>attrs[k],getRootNode:()=>({host}),getBoundingClientRect:()=>({width:box?10:0,height:box?10:0,left:200,right:210,top:0,bottom:10})};}
test('shared visibility rejects hidden, inert, aria-hidden and CSS-hidden ancestors',()=>{for(const parent of [{hidden:true},{inert:true},element({attrs:{'aria-hidden':'true'}}),...['display','visibility','contentVisibility'].map(k=>element({style:{[k]:k==='display'?'none':'hidden'}}))])assert.equal(visible(element({parent})),false);});
test('shared visibility rejects effective transparency across ancestors',()=>{assert.equal(visible(element({parent:element({style:{opacity:'0.00001'}})})),false);assert.equal(visible(element({style:{opacity:'.2'},parent:element({style:{opacity:'.2'}})})),false);assert.equal(visible(element({style:{opacity:'.8'}})),true);});
test('shared visibility follows a Shadow DOM host',()=>{assert.equal(visible(element({host:element({attrs:{'aria-hidden':'true'}})})),false);});
test('shared visibility distinguishes rendered offscreen nodes from viewport input targets',()=>{assert.equal(visible(element()),true);assert.equal(visible(element(),{viewport:true}),false);assert.equal(visible(element({box:false})),false);assert.equal(visible(element({box:false}),{requireBox:false}),true);});
test('Python and frontend SDK inject the same helper without page globals',()=>{for(const file of ['../browser/dom_visibility.py','../web/static/js/browser_bidi_client.js'])assert.match(fs.readFileSync(__dirname+'/'+file,'utf8'),/browser_dom_visibility\.js/);assert.match(fs.readFileSync(__dirname+'/../browser/background_page.py','utf8'),/page_function\(source, arguments\)/);});
test('frontend native BiDi calls bind the shared helper and reuse its loaded source',async()=>{
 let loads=0;const context={window:{addEventListener(){}},fetch:async url=>{assert.equal(url,'/admin/static/js/browser_dom_visibility.js?v=1');loads++;return {ok:true,text:async()=>source};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8'),context);
 const client=new context.window.AI2AppsBiDi.AI2AppsPageClient({});client.contextId='test';
 client.connection={command:async(method,params)=>{assert.equal(method,'script.callFunction');const page={getComputedStyle:n=>n.style};const value=await vm.runInNewContext('('+params.functionDeclaration+')()',page);assert.equal(page.ai2appsDOMVisible,undefined);return {type:'success',result:{type:'string',value}};}};
 const code="function(){return ai2appsDOMVisible({style:{opacity:'1'},getBoundingClientRect:()=>({width:10,height:10}),parentElement:{style:{opacity:'0.00001'}}});}";
 assert.equal(await client.callJSON(code),false);assert.equal(await client.callJSON(code),false);assert.equal(loads,1);
});
