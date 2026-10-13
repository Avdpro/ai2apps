const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function ui(mode="custom",api=false,options={}){
 const nodes=new Map(),calls=[],submittedCalls=[];let submitted=0;
 function node(tag){return {tag,children:[],childNodes:[],dataset:{},value:'',checked:false,setAttribute(){},addEventListener(){},append(...children){this.children.push(...children);this.childNodes=this.children;},replaceChildren(){this.children=[];this.childNodes=[];},showModal(){this.open=true;},close(){this.open=false;}};}
 function get(id){if(!nodes.has(id))nodes.set(id,node(id));return nodes.get(id);}
 get('mode').value=mode;get('query').value='ASR Model';get('limit').value='3';get('profile').value='default';get('exclude-ads').checked=true;
 const task={id:'old',capability:'x',status:'completed'};
 const context={crypto:{randomUUID:()=> 'search-batch'},location:{search:'?locale=zh'},document:{documentElement:{lang:'zh'},getElementById:get,createElement:node,querySelectorAll:s=>s.includes('input[name=source]')?[{value:'x'}]:[]},URLSearchParams,URL,Map,Set,console,
 SearchAllStartup:{complete:()=>{calls.push("ready");},fail:error=>{calls.push("startup-error:"+error.message);}},
 SearchAllResults:{merge:()=>[]},SearchAllPresentation:{groups:()=>[]},SearchAllDiagnostics:{explain:()=>''},
 AI2AppsWebAgent:{...(options.bootstrap?{startup:async()=>{calls.push("bootstrap");return {profiles:[{key:"default",name:"Default",is_default:true}],sources:[]};}}:{}),customSources:async()=>({sources:[]}),onTask(){},profiles:async()=>[{key:'default',name:'Default',is_default:true}],searchConfig:async()=>({configured:api}),retainedTasks:async()=>{calls.push('retained');return options.retained?await options.retained:mode==='custom'?[task]:[];},pages:async(id,action='list')=>{calls.push(action);return {pages:action==='close'?[]:[{url:'https://x.com/search'}]};},submit:async(capability,parameters,options)=>{submitted++;submittedCalls.push({capability,parameters,options});return {id:'new'+submitted,status:'completed',result:capability==='plan'?{sources:['xiaohongshu','bilibili','google'],x_sort:'top',xiaohongshu_sort:'likes',limit:5,reason:'Recipe plan'}:{items:[]}};},watch:async()=>({id:'new',status:'completed',result:{items:[]}})}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../../packages/ai2apps-search-all/web/modes.js','utf8'),context);vm.runInNewContext(fs.readFileSync(__dirname+'/../../packages/ai2apps-search-all/web/search.js','utf8'),context);return {get,calls,submittedCalls,submitted:()=>submitted};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('new search cancellation leaves old pages open and re-enables search',async()=>{
 const u=ui();await tick();const pending=u.get('search').onsubmit({preventDefault(){}});await tick();assert.equal(u.get('new-search-dialog').open,true);u.get('cancel-search').onclick();await pending;assert.equal(u.submitted(),0);assert.equal(u.get('run').disabled,false);assert.equal(u.calls.includes('close'),false);
});
test('close and search verifies old pages before submitting a new Task',async()=>{
 const u=ui();await tick();const pending=u.get('search').onsubmit({preventDefault(){}});await tick();u.get('close-and-search').onclick();await pending;assert.equal(u.calls.includes('close'),true);assert.equal(u.submitted(),1);
});
test('keep and search leaves retained tabs untouched',async()=>{
 const u=ui();await tick();const pending=u.get('search').onsubmit({preventDefault(){}});await tick();u.get('keep-and-search').onclick();await pending;assert.equal(u.calls.includes('close'),false);assert.equal(u.submitted(),1);
});

test('fast without configured API submits one Google source and hides custom settings',async()=>{const u=ui('fast');await tick();await u.get('search').onsubmit({preventDefault(){}});assert.equal(u.submitted(),1);assert.equal(u.submittedCalls[0].capability,'google');assert.equal(u.get('source-options').hidden,true);assert.equal(u.get('custom-settings').hidden,true);assert.equal(u.get('api-settings').hidden,false);assert.match(u.get('strategy').textContent,/Google/);});

test('preferred executes validated source order and per-source settings through shared Tasks',async()=>{const u=ui('preferred');await tick();await u.get('search').onsubmit({preventDefault(){}});assert.deepEqual(u.submittedCalls.map(c=>c.capability),['plan','xiaohongshu','bilibili','google']);assert.equal(u.submittedCalls[1].parameters.xiaohongshu_sort,'likes');assert.equal(u.submittedCalls[1].parameters.limit,5);assert.equal(u.get('source-options').hidden,true);});

 test('ready form does not wait for historical page verification; new search still waits',async()=>{
 let resolve;const retained=new Promise(r=>{resolve=r;});const u=ui('custom',false,{bootstrap:true,retained});
 await tick();assert.deepEqual(u.calls.slice(0,3),['bootstrap','ready','retained']);
 assert.equal(u.get('profile').disabled,false);
 const pending=u.get('search').onsubmit({preventDefault(){}});await tick();
 assert.equal(u.submitted(),0);assert.equal(u.get('new-search-dialog').open,undefined);
 resolve([{id:'old',capability:'x',status:'completed'}]);await tick();
 assert.equal(u.get('new-search-dialog').open,true);u.get('cancel-search').onclick();await pending;
 assert.equal(u.calls.filter(c=>c==='retained').length,1);
 });

test("source submissions share one bounded parallel search batch",async()=>{const u=ui("preferred");await tick();await u.get("search").onsubmit({preventDefault(){}});const sources=u.submittedCalls.filter(c=>c.capability!=="plan");assert.equal(sources.length,3);assert(sources.every(c=>c.options.batchId==="search-batch"&&c.options.batchSize===3));});
