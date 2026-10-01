const vm=require('node:vm'), fs=require('node:fs'), assert=require('node:assert/strict');
const {File}=require('node:buffer');
class Element {
 constructor(){this.value='';this.children=[];this.files=[];this.listeners={};this.classList={add(){},remove(){}};this.label={textContent:''};}
 replaceChildren(...items){this.children=items;this.value=items[0]?.value||'';} prepend(item){this.children.unshift(item)}
 setAttribute(){} removeAttribute(){} pause(){} querySelector(){return this.label;} addEventListener(name,fn){this.listeners[name]=fn;} contains(){return false;}
}
(async()=>{
 const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
 const listeners={},parent={},requests=[],revoked=[];
 const model={id:'provider/lite',label:'Lite',ready:true,presets:[{id:'standard',label:'Standard'}],resolutions:['512x512'],minimumSeconds:0,maximumSeconds:60,defaults:{preset:'standard',resolution:'512x512'}};
 const port={postMessage(req){requests.push(req);let value=req.operation==='avatar.models'?{items:[model]}:req.operation==='avatar.jobs'?{items:[]}:req.operation==='avatar.input.read'?{body:new Blob(['media'],{type:req.kind==='image'?'image/png':'audio/wav'}),name:req.kind==='image'?'gallery.png':'output.wav'}:{};queueMicrotask(()=>port.onmessage({data:{id:req.id,value}}));}};
 const ctx={document:{getElementById:get,createElement:()=>new Element(),body:{},documentElement:{}},window:{parent,addEventListener:(k,v)=>listeners[k]=v,removeEventListener(){}},File,Blob,URL:{createObjectURL:()=> 'blob:test',revokeObjectURL:u=>revoked.push(u)},ResizeObserver:class{observe(){}},setInterval(){},setTimeout};
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
 console.log('PASS: model ACPF option, Finder/Gallery drop handlers, previews, clearing and type rejection');
})().catch(e=>{console.error(e);process.exitCode=1});
