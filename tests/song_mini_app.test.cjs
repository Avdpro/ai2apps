const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('packages/ai2apps-audio-generation-suite/web/song.js','utf8');
const tick=()=>new Promise(r=>setImmediate(r));
async function harness(locale='en',items=[],draft=null){
 const els={},listeners={},calls=[];let output={completed:true},hold=false,held;
 const defaults={planning:'full',limit:'120',steps:'32',seed:'831001'};
 const el=id=>els[id]??={value:defaults[id]||'',textContent:'',options:[],dataset:{},classList:{toggle(){}},setAttribute(k,v){this[k]=v;},removeAttribute(k){delete this[k];},replaceChildren(){this.options=[];this.value='';},add(o){this.options.push(o);},reportValidity(){return true;}};
 const parent={postMessage(){}},stages=Array.from({length:5},(_,i)=>Object.assign(el('stage'+i),{dataset:{stage:String(i)}}));
 const document={body:{},documentElement:{},getElementById:el,querySelectorAll:q=>q==='[data-stage]'?stages:[]};
 const port={postMessage(m){calls.push(m);queueMicrotask(()=>{let value,error;
  if(m.operation==='audio-generation.models')value={items};
  if(m.operation==='draft.get')value=draft;
  if(m.operation==='setup')error='Unavailable model';
  if(m.operation==='audio-generation.generate'){if(hold){held=m;return;}value=output;}
  if(m.operation==='audio-generation.cancel'&&held){port.onmessage({data:{id:held.id,error:'Cancelled'}});held=null;}
  port.onmessage({data:{id:m.id,value,error}});
 });}};
 vm.runInNewContext(source,{document,window:{parent,addEventListener:(k,f)=>listeners[k]=f,removeEventListener(){}},location:{search:'?locale='+locale},URLSearchParams,Option:function(text,value){this.text=text;this.value=value;},ResizeObserver:class{observe(){}},TextEncoder,TextDecoder,Map,Promise});
 listeners.message({source:{},data:{type:'ai2apps:studio-connected',version:1},ports:[port]});assert.equal(calls.length,0);
 listeners.message({source:parent,data:{type:'ai2apps:studio-connected',version:1,locale},ports:[port]});await tick();await tick();
 return {el,port,calls,setOutput:v=>output=v,hold:()=>hold=true,async submit(){await el('form').onsubmit({preventDefault(){}});await tick();}};
}
const model={id:'yue2',label:'YuE2',ready:true,maximumSeconds:120,maximumTokens:3000,planningModes:['full','melody','off']};
(async()=>{
 let checks=0;
 for(const locale of ['en','zh']){
  const h=await harness(locale,[model]);h.el('prompt').value='Piano song';h.el('lyrics').value='[Verse]\nHello';h.el('abc').value='X:1\nK:C\nCDEF|';
  await h.submit();let req=h.calls.find(c=>c.operation==='audio-generation.generate');assert.equal(req.capability,'audio.song_generation');assert.equal(req.payload.schema,'ai2apps.audio-generation/v2');assert.equal(req.payload.generation.max_semantic_tokens,3000);assert.equal(req.payload.generation.abc,h.el('abc').value);assert.ok(!('duration' in req.payload));assert.equal(req.payload.steps,32);checks++;
  h.el('planning').value='off';h.el('planning').onchange();assert.equal(h.el('abc').disabled,true);await h.submit();req=h.calls.filter(c=>c.operation==='audio-generation.generate').at(-1);assert.ok(!('abc' in req.payload.generation));assert.ok(h.el('abc').value);checks++;
  const previous=h.el('model').value;h.el('model').value='__install_model__';h.el('model').onchange();await tick();await tick();assert.equal(h.el('model').value,previous);assert.equal(h.calls.find(c=>c.operation==='setup').installMore,true);checks++;
  h.setOutput({completed:true,reachedLimit:true});await h.submit();assert.match(h.el('status').textContent,locale==='zh'?/截断/:/cut off/);checks++;
  h.hold();const pending=h.submit();await tick();await tick();h.port.onmessage({data:{type:'ai2apps:studio-progress',progress:{phaseIndex:2}}});assert.match(h.el('status').textContent,locale==='zh'?/声学合成/:/Synthesize/);await h.el('cancel').onclick();await pending;assert.match(h.el('status').textContent,locale==='zh'?/取消/:/cancelled/);assert.equal(h.el('inputs').disabled,false);checks++;
  h.el('planning').value='full';h.el('planning').onchange();const bytes=new TextEncoder().encode('X:1\nK:C\nCDEF|');h.el('abc-file').files=[{name:'test.abc',size:bytes.length,arrayBuffer:async()=>bytes.buffer}];await h.el('abc-file').onchange();assert.equal(h.el('abc').value,'X:1\nK:C\nCDEF|');checks++;
  h.el('abc-file').files=[{name:'large.abc',size:131073}];await h.el('abc-file').onchange();assert.match(h.el('error').textContent,/128 KiB/);assert.equal(h.el('abc').value,'X:1\nK:C\nCDEF|');checks++;
  const restored=await harness(locale,[model],JSON.stringify({schema:'ai2apps.mini-app-draft/v1',miniApp:'ai2apps.audio-generation.song',model:'yue2',prompt:'Saved lyrics',lyrics:'Hello',planning:'melody',limit:'60',abc:'X:2'}));assert.equal(restored.el('prompt').value,'Saved lyrics');assert.equal(restored.el('planning').value,'melody');assert.equal(String(restored.el('limit').value),'60');checks++;
  const empty=await harness(locale,[]);assert.equal(empty.el('generate').disabled,true);assert.equal(empty.el('model').options.at(-1).value,'__install_model__');checks++;
 }
 console.log(`${checks} song Mini-App interaction checks passed`);
})();
