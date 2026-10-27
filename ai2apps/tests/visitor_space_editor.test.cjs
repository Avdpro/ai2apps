const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/visitor_space_editor.js'),'utf8');
const tick=()=>new Promise(r=>setImmediate(r));
async function setup(fail, cards=[]){
 const els={},calls=[],previews=[];const make=()=>({children:[],dataset:{},setAttribute(){},value:'',append(...n){this.children.push(...n);},replaceChildren(...n){this.children=n;},addEventListener(name,fn){this[name]=fn;}});const $=id=>els[id]||(els[id]=make());
 let state={version:0,revision:0,enabled:false,appGatewayReady:true,apps:[],draft:{title:'Title',description:'',theme:'ocean',cards}};
 vm.runInNewContext(source,{document:{getElementById:$,querySelectorAll:()=>[],querySelector:()=>null,createElement:make,createTextNode:t=>({textContent:t,children:[]})},window:{renderVisitorSpace(root,draft,options){previews.push({draft:structuredClone(draft),options:{...options}});},addEventListener(){}},structuredClone,fetch:async(path,options)=>{
  if(path==='/v1/platform/cloud/profile')return{ok:true,json:async()=>({avatarUrl:null})};
  const endpoint=path.replace('/v1/platform/remote/visitor-space','');calls.push({endpoint,body:options.body&&JSON.parse(options.body)});
  if(endpoint===fail)return{ok:false,json:async()=>({error:{message:'请先发布空间内容'}})};
  if(endpoint==='/html-ai')return{ok:true,json:async()=>({asset:{id:'b'.repeat(64)},model:'test'})};
  if(endpoint==='/draft')state={...state,version:state.version+1,draft:JSON.parse(options.body).draft};
  if(endpoint==='/publish')state={...state,version:state.version+1,revision:1};
  if(endpoint==='/enabled')state={...state,version:state.version+1,enabled:true};
  return{ok:true,json:async()=>endpoint?{version:state.version,revision:state.revision,enabled:state.enabled,draft:state.draft}:state};
 }});await tick();return{els,calls,previews};
}
test('first enable saves edited draft then publishes then enables with current versions',async()=>{
 const {els,calls}=await setup();assert.equal(els['vs-toggle'].textContent,'发布并开启访客空间');els['vs-title'].value='Edited';els['vs-title'].input();await els['vs-toggle'].onclick();
 assert.deepEqual(calls.map(x=>x.endpoint),['','/draft','/publish','/enabled']);assert.equal(calls[1].body.draft.title,'Edited');assert.equal(calls[3].body.version,2);assert.equal(els['vs-notice'].dataset.kind,'success');
});
test('publish failure preserves draft and never enables, showing platform error message',async()=>{
 const {els,calls}=await setup('/publish');await els['vs-toggle'].onclick();assert.deepEqual(calls.map(x=>x.endpoint),['','/publish']);assert.equal(els['vs-notice'].textContent,'请先发布空间内容');assert.equal(els['vs-notice'].dataset.kind,'error');assert.equal(els['vs-toggle'].disabled,false);
});

const descendants=n=>[n,...(n.children||[]).flatMap(descendants)];
test('AI authoring applies generated asset and runs draft preview without publishing',async()=>{
 const q=await setup(null,[{kind:'html',assetId:'a'.repeat(64),title:'Stars',text:''}]);
 let nodes=descendants(q.els['vs-cards']);const prompt=nodes.find(n=>n.placeholder?.startsWith('例如'));prompt.value='改成蓝色';prompt.oninput();
 nodes.find(n=>n.textContent==='发送需求并修改').onclick();await tick();
 assert.equal(q.calls.at(-1).endpoint,'/html-ai');assert.equal(q.calls.at(-1).body.assetId,'a'.repeat(64));
 assert.equal(q.previews.at(-1).draft.cards[0].assetId,'b'.repeat(64));assert.equal(q.previews.at(-1).options.autoRunAsset,'b'.repeat(64));
 assert.ok(!q.calls.some(c=>c.endpoint==='/publish'));
 nodes=descendants(q.els['vs-cards']);nodes.find(n=>n.textContent==='恢复上个版本').onclick();assert.equal(q.previews.at(-1).draft.cards[0].assetId,'a'.repeat(64));
});
test('AI failure leaves existing card and requirement intact',async()=>{
 const q=await setup('/html-ai',[{kind:'html',assetId:'a'.repeat(64)}]);const nodes=descendants(q.els['vs-cards']);const prompt=nodes.find(n=>n.placeholder?.startsWith('例如'));prompt.value='蓝色';prompt.oninput();nodes.find(n=>n.textContent==='发送需求并修改').onclick();await tick();
 assert.equal(q.previews.at(-1).draft.cards[0].assetId,'a'.repeat(64));assert.equal(prompt.value,'蓝色');assert.equal(q.els['vs-notice'].dataset.kind,'error');
});
