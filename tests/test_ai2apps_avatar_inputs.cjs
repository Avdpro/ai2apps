const vm=require('node:vm'), fs=require('node:fs'), assert=require('node:assert/strict');
const {File}=require('node:buffer');
class Element {
 constructor(){this.value='';this.children=[];this.files=[];this.listeners={};this.classList={add(){},remove(){}};this.label={textContent:''};}
 replaceChildren(...items){this.children=items;this.value=items[0]?.value||'';} prepend(item){this.children.unshift(item)}
 setAttribute(){} removeAttribute(){} pause(){} load(){} querySelector(){return this.label;} addEventListener(name,fn){this.listeners[name]=fn;} contains(){return false;}
}
(async()=>{
 const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
 const listeners={},parent={},requests=[],revoked=[];
 const model={id:'provider/lite',label:'Lite',ready:true,presets:[{id:'standard',label:'Standard'}],resolutions:['512x512'],minimumSeconds:0,maximumSeconds:60,defaults:{preset:'standard',resolution:'512x512'}};
 let catalog=[model];
 const port={postMessage(req){requests.push(req);let value=req.operation==='avatar.models'?{items:catalog}:req.operation==='avatar.jobs'?{items:[]}:req.operation==='avatar.record.start'?{maxSeconds:59}:req.operation==='avatar.record.stop'?{body:new Blob(['recorded'],{type:'audio/webm'}),name:'recorded.webm'}:req.operation==='invoke'?{status:422,body:new Blob([JSON.stringify({error:{message:'decoded audio exceeds the duration limit'}})])}:req.operation==='avatar.input.read'?{body:new Blob(['media'],{type:req.kind==='image'?'image/png':'audio/wav'}),name:req.kind==='image'?'gallery.png':'output.wav'}:{};queueMicrotask(()=>port.onmessage({data:{id:req.id,value}}));}};
 const ctx={URLSearchParams,Event:class {constructor(type){this.type=type}},navigator:{language:'zh-CN'},document:{getElementById:get,createElement:()=>new Element(),body:{},documentElement:{},querySelectorAll:()=>[]},window:{location:{search:''},parent,dispatchEvent:e=>listeners[e.type]?.(e),addEventListener:(k,v)=>listeners[k]=v,removeEventListener(){}},File,Blob,URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:u=>revoked.push(u)},ResizeObserver:class{observe(){}},setInterval(){},clearInterval(){},setTimeout};
 for(const file of ['locales.js','i18n.js']) vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../packages/ai2apps-avatar-studio-suite/web',file),'utf8'),ctx);
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../packages/ai2apps-avatar-studio-suite/web/avatar.js'),'utf8'),ctx);
 listeners.message({source:parent,data:{type:'ai2apps:studio-connected',version:1},ports:[port]});
 await new Promise(resolve=>setImmediate(resolve));
 assert(get('model').children.some(x=>x.textContent==='＋ 安装模型…'));
 get('model').value='__install_model__';await get('model').onchange();
 assert(requests.some(x=>x.operation==='setup'&&x.installMore===true));assert.equal(get('model').value,model.id);
 const event=(file,values={})=>({preventDefault(){},stopPropagation(){},dataTransfer:{files:file?[file]:[],getData:t=>values[t]||''}});
 await get('portrait-slot').listeners.drop(event(new File(['image'],'test.png',{type:'image/png'})));
 assert.match(get('portrait-name').textContent,/test.png/);assert.equal(get('portrait-preview').hidden,false);
 await get('speech-slot').listeners.drop(event(new File(['audio'],'test.wav',{type:'audio/wav'})));
 assert.equal(get('speech-details').hidden,false);
 get('speech-preview').duration=25.4; await get('speech-preview').onloadedmetadata();
 assert.match(get('speech-duration').textContent,/25.4/);
 assert.equal(get('generate').disabled,false);assert.equal(get('speech-clear').hidden,false);
 get('portrait-clear').onclick();assert.equal(get('generate').disabled,true);assert(revoked.length>0);
 await get('portrait-slot').listeners.drop(event(null,{'application/x-ai2apps-gallery-asset':'gallery1'}));
 assert.equal(requests.at(-1).reference.assetId,'gallery1');assert.match(get('portrait-name').textContent,/gallery.png/);
 await get('portrait-slot').listeners.drop(event(null,{'application/x-ai2apps-image-result':JSON.stringify({artifactId:'image1',appInstanceId:'app1'})}));
 assert.equal(requests.at(-1).reference.source,'image-output');
 await get('speech-slot').listeners.drop(event(null,{'application/x-ai2apps-audio-artifact':JSON.stringify({artifactId:'audio1',sessionId:'session1'})}));
 assert.equal(requests.at(-1).reference.source,'audio-output');assert.match(get('speech-name').textContent,/output.wav/);
 await get('speech-slot').listeners.drop(event(new File(['image'],'bad.png',{type:'image/png'})));
 assert.match(get('status').textContent,/声音/);assert.match(get('speech-name').textContent,/output.wav/);
 port.onmessage({data:{type:'ai2apps:studio-locale',locale:'en'}});
 assert.equal(get('speech-pick').label.textContent,'Click to replace file');
 assert.match(get('model-limits').textContent,/60 seconds/);
 assert.match(get('speech-name').textContent,/output.wav/);
 await get('avatar-form').onsubmit({preventDefault(){}});
 assert.match(get('status').textContent,/60-second limit/);
 await get('record-start').onclick(); assert.equal(get('generate').disabled,true);
 await get('record-cancel').onclick(); assert.match(get('speech-name').textContent,/output.wav/);
 await get('record-start').onclick(); await get('record-stop').onclick();
 assert.match(get('speech-name').textContent,/recorded.webm/); assert.equal(get('speech-details').hidden,false);
 get('speech-clear').onclick(); assert.equal(get('speech-details').hidden,true);
 assert(revoked.length>1);
 // A refreshed signed catalog can expose all H3 aliases without Mini-App code changes.
 const variants=['base-4bit','base-8bit','ref2va-4bit','ref2va-8bit','lightx2v-4step-4bit','lightx2v-8step-4bit','openvdn-dmd8-4bit','openvdn-stageb50-4bit'];
 catalog=variants.map(name=>({...model,id:'ai2apps.model.minimax-h3/avatar-'+name,label:name,maximumSeconds:3276,presets:[{id:'strict',label:'Standard'}],defaults:{preset:'strict',resolution:'512x512'}}));
 get('model').value='__install_model__';await get('model').onchange();
 assert.equal(get('model').children.length,9); // Eight models and the install action.
 await get('speech-slot').listeners.drop(event(new File(['long-audio'],'long.wav',{type:'audio/wav'})));
 get('speech-preview').duration=69;await get('speech-preview').onloadedmetadata();
 for(const candidate of catalog){
   get('model').value=candidate.id;await get('model').onchange();
   assert.equal(get('generate').disabled,false);
   assert.match(get('model-limits').textContent,/3276 seconds/);
   const before=requests.filter(r=>r.operation==='invoke').length;
   await get('avatar-form').onsubmit({preventDefault(){}});
   const invoked=requests.filter(r=>r.operation==='invoke');assert.equal(invoked.length,before+1);
   assert.equal(invoked.at(-1).fields.find(([key])=>key==='avatar_model_id')[1],candidate.id);
   assert.equal(invoked.at(-1).fields.find(([key])=>key==='profile')[1],'strict');
 }
 catalog[0].ready=false;get('model').value='__install_model__';await get('model').onchange();
 get('model').value=catalog[0].id;await get('model').onchange();assert.equal(get('generate').disabled,true);
 console.log('PASS: eight H3 choices preserve selected model ID, allow 69-second input, and reject unready models');
 console.log('PASS: model ACPF option, Finder/Gallery drop handlers, previews, clearing and type rejection');
})().catch(e=>{console.error(e);process.exitCode=1});
