const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture(fetch, clock=Date){
 const nodes=[];function node(tag){const n={tag,value:'',add(option){this.children.push(option);},get options(){return this.children;},get selectedOptions(){return this.children.filter(o=>o.value===this.value);},children:[],dataset:{},isConnected:true,append(...v){this.children.push(...v);},insertBefore(v){this.children.unshift(v);},replaceChildren(...v){this.children=v;},setAttribute(){},showModal(){},close(){this.onclose?.();},remove(){this.isConnected=false;},querySelector(selector){return this.children.find(c=>'.'+c.className===selector);},querySelectorAll(selector){return this.children.filter(c=>selector==='button'?c.tag==='button':c.dataset?.messageId);}};nodes.push(n);return n;}
 const document={documentElement:{lang:'en'},createElement:node,body:node('body')},events=[];
 const window={dispatchEvent(e){events.push(e);}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/bot_knowledge.js','utf8'),{document,window,fetch,AbortController,Option:class{constructor(text,value){this.textContent=text;this.value=value;}},Date:clock,crypto:{randomUUID(){return 'stable-undo-request';}},CustomEvent:class {constructor(type,options){this.type=type;this.detail=options.detail;}}});
 return {api:window.AI2AppsBotKnowledge,node,nodes,events};
}
test('memory feed binds only exact owned message IDs and never grants or executes',async()=>{
 const calls=[],previews=[];const f=fixture(async(url,o)=>{calls.push([url,o]);return {ok:true,async json(){if(url.includes('feed=true'))return {items:[{id:'candidate',message_id:'not-visible',state:'review',value:{text:'Review me'}}]};return {items:[{change_id:'change',message_id:'receipt'}, {change_id:'wrong',message_id:'not-visible'}]};}};});
 const root=f.node('div'),receipt=f.node('article'),other=f.node('article');receipt.dataset.messageId='receipt';other.dataset.messageId='model-text';root.append(receipt,other);
 const feed=f.api.createFeed({botId:'bot-a',sessionId:'session-a',root,onPending:items=>previews.push(...items)});await feed.refresh();
 assert.deepEqual(previews.map(item=>[item.id,item.state,item.value.text]),[['candidate','review','Review me']]);
 assert.equal(calls.length,2);const lookup=calls.find(c=>c[0].includes('/memory-changes?'));assert.ok(lookup[0].includes('session_id=session-a'));assert.ok(lookup[0].includes('message_id=receipt'));assert.ok(calls.every(c=>c[1].method==='GET'));
 assert.equal(receipt.children[0].children[0].textContent,'View memory / Undo');assert.equal(other.children.length,0);feed.dispose();
});
test('late memory lookup cannot repaint a disposed conversation',async()=>{
 let release;const pending=new Promise(r=>release=r);const f=fixture(async()=>{await pending;return {ok:true,async json(){return {items:[{change_id:'change',message_id:'receipt'}]};}};});
 const root=f.node('div'),receipt=f.node('article');receipt.dataset.messageId='receipt';root.append(receipt);
 let previews=0;const feed=f.api.createFeed({botId:'bot-a',sessionId:'session-a',root,onPending:()=>previews++});const work=feed.refresh();feed.dispose();release();await work;assert.equal(receipt.children.length,0);assert.equal(f.events.length,0);assert.equal(previews,0);
});
test('a batch of new saved-memory receipts asks the sidebar to refresh once',async()=>{
 let now=3000;
 const f=fixture(async url=>({ok:true,async json(){
  return {items:url.includes('/memory-changes?')?[
   {change_id:'first',message_id:'receipt-a'},{change_id:'second',message_id:'receipt-b'},
  ]:[]};
 }}),{now:()=>now});
 const root=f.node('div');
 for(const id of ['receipt-a','receipt-b']){
  const article=f.node('article');article.dataset.messageId=id;root.append(article);
 }
 const feed=f.api.createFeed({botId:'bot-a',sessionId:'session-a',root});
 await feed.refresh();
 now+=3000;
 await feed.refresh();
 assert.equal(f.events.length,1);
 assert.equal(f.events[0].type,'ai2apps:bot-memory-changed');
 assert.equal(f.events[0].detail.botId,'bot-a');
 feed.dispose();
});
test('undo uses the inspected change and a stable request, blocks double clicks',async()=>{
 const calls=[];let release;const pending=new Promise(r=>release=r);const f=fixture(async(url,o)=>{calls.push([url,o]);if(o.method==='POST')await pending;return {ok:true,async json(){return o.method==='POST'?{}:{after:{text:'<script>never HTML</script>'},before:null,evidence:[],source:{},created_at:'2026-11-04',can_undo:true};}};});
 await f.api.viewChange('bot-a','change-a');const undo=f.nodes.find(n=>n.textContent==='Undo this change');assert.ok(undo);assert.equal(f.nodes.find(n=>n.textContent?.startsWith('After: ')).textContent,'After: <script>never HTML</script>');
 const first=undo.onclick();await undo.onclick();assert.equal(calls.filter(c=>c[1].method==='POST').length,1);release();await first;
 assert.ok(calls[1][0].endsWith('/change-a/undo'));assert.equal(JSON.parse(calls[1][1].body).request_id,'stable-undo-request');assert.equal(f.events[0].detail.botId,'bot-a');
});
test('pending candidate is safe text, and cancel is bound to the exact candidate once',async()=>{
 const calls=[];let release,done=false;const gate=new Promise(r=>release=r);
 const f=fixture(async(url,o)=>{calls.push([url,o]);if(o.method==='POST'){await gate;done=true;}return {ok:true,async json(){return {items:done?[]:[{id:'candidate-a',state:'review',value:{text:'<img onerror=unsafe>'}}]};}};});
 f.api.open('bot-a','pending');await new Promise(setImmediate);
 assert.ok(f.nodes.some(n=>n.textContent==='<img onerror=unsafe>'));
 const cancel=f.nodes.find(n=>n.tag==='button'&&n.textContent==='Cancel');assert.ok(cancel);
 const first=cancel.onclick();await cancel.onclick();assert.equal(calls.filter(c=>c[1].method==='POST').length,1);
 assert.ok(calls.at(-1)[0].endsWith('/candidate-a/cancel'));release();await first;
});
test('returned memory review exposes task and quoted source as safe text',async()=>{
 const f=fixture(async()=>({ok:true,async json(){return {items:[{id:'return:x',state:'review',value:{text:'finding',predicate:'task result'},provenance:{source_bot:'Child <img>',title:'Reviewed task',proof:{quote:'exact <script>'},path:['child','parent']}}]};}}));
 f.api.open('parent','pending');await new Promise(setImmediate);
 assert.ok(f.nodes.some(n=>n.textContent==='Source Bot: Child <img>'));
 assert.ok(f.nodes.some(n=>n.textContent==='Evidence: exact <script>'));
 assert.ok(f.nodes.some(n=>n.textContent==='Confirm memory'));
});

test('model memory uses server purposes and catalog, saves typed values without granting access',async()=>{
 const calls=[];const f=fixture(async(url,options)=>{calls.push([url,options]);return {ok:true,async json(){return options.method==='POST'?{}:{purposes:['image_generation','future_model_purpose'],models:[{id:'ready-model',label:'Ready model',ready:true},{id:'not-ready',label:'Missing',ready:false}]};}};});
 await f.api.modelMemory('bot-a');
 const [purpose,profile,model]=f.nodes.filter(n=>n.tag==='select');
 assert.deepEqual(purpose.options.map(o=>o.value),['image_generation','future_model_purpose']);
 assert.deepEqual(model.options.map(o=>o.value),['','ready-model']);
 model.value='ready-model';model.onchange();
 const save=f.nodes.find(n=>n.textContent==='Save model memory');await save.onclick();
 const body=JSON.parse(calls.at(-1)[1].body);
 assert.equal(body.kind,'model');assert.deepEqual(body.value,{purpose:'image_generation',profile:'normal',model:'ready-model'});
 assert.ok(calls.at(-1)[0].endsWith('/memory-records'));assert.equal(f.events.length,1);
 assert.ok(calls.every(c=>!c[0].includes('access')));
});
test('late normal catalog cannot overwrite privacy model choices',async()=>{
 let release;const gate=new Promise(r=>release=r);let count=0;
 const f=fixture(async url=>{const seq=++count;if(seq===2)await gate;return {ok:true,async json(){return {purposes:['image_generation'],models:[{id:url.includes('profile=privacy')?'private':'normal',label:'Model',ready:true}]};}};});
 await f.api.modelMemory('bot-a');const [purpose,profile,model]=f.nodes.filter(n=>n.tag==='select');
 const slow=purpose.onchange();profile.value='privacy';await profile.onchange();release();await slow;
 assert.deepEqual(model.options.map(o=>o.value),['','private']);
});
test('editing a model memory preserves its slot and optimistic revision',async()=>{
 const calls=[];const f=fixture(async(url,o)=>{calls.push([url,o]);return {ok:true,async json(){return {purposes:['work_chat'],models:[{id:'new-model',label:'New',ready:true}]};}};});
 await f.api.modelMemory('bot-a',{revision:7,metadata:{value:{purpose:'work_chat',profile:'privacy',model:'old-model'}}});
 const [purpose,profile,model]=f.nodes.filter(n=>n.tag==='select');assert.equal(purpose.disabled,true);assert.equal(profile.disabled,true);
 model.value='new-model';model.onchange();await f.nodes.find(n=>n.textContent==='Save model memory').onclick();
 const body=JSON.parse(calls.at(-1)[1].body);assert.equal(body.mode,'replace');assert.equal(body.expected_revision,7);assert.equal(body.value.profile,'privacy');
});
