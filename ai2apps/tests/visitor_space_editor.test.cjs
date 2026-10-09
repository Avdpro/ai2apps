const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/visitor_space_editor.js'),'utf8');
const tick=()=>new Promise(r=>setImmediate(r));
async function setup(fail){
 const els={},calls=[];const make=()=>({dataset:{},value:'',append(){},replaceChildren(){},addEventListener(name,fn){this[name]=fn;}});const $=id=>els[id]||(els[id]=make());
 let state={version:0,revision:0,enabled:false,appGatewayReady:true,apps:[],draft:{title:'Title',description:'',theme:'ocean',cards:[]}};
 vm.runInNewContext(source,{document:{getElementById:$,querySelectorAll:()=>[],querySelector:()=>null,createElement:make},window:{renderVisitorSpace(){},addEventListener(){}},structuredClone,fetch:async(path,options)=>{
  const endpoint=path.replace('/v1/platform/remote/visitor-space','');calls.push({endpoint,body:options.body&&JSON.parse(options.body)});
  if(endpoint===fail)return{ok:false,json:async()=>({error:{message:'请先发布空间内容'}})};
  if(endpoint==='/draft')state={...state,version:state.version+1,draft:JSON.parse(options.body).draft};
  if(endpoint==='/publish')state={...state,version:state.version+1,revision:1};
  if(endpoint==='/enabled')state={...state,version:state.version+1,enabled:true};
  return{ok:true,json:async()=>endpoint?{version:state.version,revision:state.revision,enabled:state.enabled,draft:state.draft}:state};
 }});await tick();return{els,calls};
}
test('first enable saves edited draft then publishes then enables with current versions',async()=>{
 const {els,calls}=await setup();assert.equal(els['vs-toggle'].textContent,'发布并开启访客空间');els['vs-title'].value='Edited';els['vs-title'].input();await els['vs-toggle'].onclick();
 assert.deepEqual(calls.map(x=>x.endpoint),['','/draft','/publish','/enabled']);assert.equal(calls[1].body.draft.title,'Edited');assert.equal(calls[3].body.version,2);assert.equal(els['vs-notice'].dataset.kind,'success');
});
test('publish failure preserves draft and never enables, showing platform error message',async()=>{
 const {els,calls}=await setup('/publish');await els['vs-toggle'].onclick();assert.deepEqual(calls.map(x=>x.endpoint),['','/publish']);assert.equal(els['vs-notice'].textContent,'请先发布空间内容');assert.equal(els['vs-notice'].dataset.kind,'error');assert.equal(els['vs-toggle'].disabled,false);
});
