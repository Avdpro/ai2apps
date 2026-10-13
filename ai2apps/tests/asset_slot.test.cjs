const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/static/js/asset_slot.js'),'utf8');
function element(){const handlers={};return {handlers,hidden:false,disabled:false,files:[],value:'',classList:{add(){},remove(){},toggle(){}},dataset:{},attrs:{},addEventListener(t,fn){handlers[t]=fn},setAttribute(k,v){this.attrs[k]=v},removeAttribute(k){delete this[k]},contains(x){return x===this},click(){this.clicked=(this.clicked||0)+1}};}
function fixture(){const root=element(),input=element(),image=element(),empty=element(),filled=element(),clear=element();root.querySelector=s=>s.startsWith('input')?input:s==='img'||s==='video'?image:s==='button'?clear:s==='[data-slot-filled]'?filled:empty;const ctx={window:{}};vm.createContext(ctx);vm.runInContext(source,ctx);return {root,input,image,empty,filled,clear,bind:ctx.window.AI2AppsAssetSlot.bind};}
test('canonical Asset Slot source and Package vendored copy are identical',()=>{
 for(const [kind,name] of [['js','asset_slot.js'],['css','asset_slot.css']])assert.equal(fs.readFileSync(path.join(__dirname,'../web/static',kind,name),'utf8'),fs.readFileSync(path.join(__dirname,'../../packages/ai2apps-frozen-time/web',name),'utf8'));
});
test('Imagine image inputs use standard slots; adjustment Canvas and batch pickers remain specialized',()=>{
 const template=fs.readFileSync(path.join(__dirname,'../web/templates/system_apps/imagine_studio.html'),'utf8');
 const singleInputs=template.split('\n').filter(line=>line.includes('type="file"')&&!line.includes(' multiple'));
 assert.equal(singleInputs.length,2,'common Mini-App slots and adjustment source only');
 for(const line of singleInputs)assert.ok(line.includes('AI2AppsAssetSlot.bind'));
 assert.ok(template.includes('select:file=>setReference(0,file)'));
 assert.ok(template.includes('drop:event=>handleGalleryDrop(event,0)'));
 assert.ok(template.includes('x-ref="adjustCanvas"'));
 assert.ok(!template.includes('is-adjust-import'));
 assert.ok(template.includes('x-ref="adjustmentBatchFiles"'));
 assert.ok(template.includes('x-ref="adjustmentBatchFolder"'));
});
test('slot shares keyboard, replace, clear, preview and disabled behavior',async()=>{
 const {root,input,image,empty,clear,bind}=fixture();let selected,cleared=0;const api=bind(root,{select:f=>selected=f,clear:()=>cleared++});
 api.update({preview:'blob:preview',label:'原图',clearLabel:'清除图片'});assert.equal(image.src,'blob:preview');assert.equal(empty.hidden,true);assert.equal(clear.hidden,false);assert.equal(root.attrs['aria-label'],'原图');
 root.handlers.keydown({target:root,key:'Enter',preventDefault(){}});assert.equal(input.clicked,1);
 const file={name:'test.png'};input.files=[file];input.handlers.change();await new Promise(resolve=>setImmediate(resolve));assert.equal(selected,file);assert.equal(input.value,'');
 clear.handlers.click({preventDefault(){},stopPropagation(){}});await new Promise(resolve=>setImmediate(resolve));assert.equal(cleared,1);
 api.update({preview:'',disabled:true});assert.equal(image.hidden,true);assert.equal(empty.hidden,false);assert.equal(clear.hidden,true);assert.equal(input.disabled,true);
 root.handlers.keydown({target:root,key:' ',preventDefault(){}});assert.equal(input.clicked,1);
});
test('Gallery and Output drop resolution is supplied by the host adapter, never fetched by component',async()=>{
 const {root,bind}=fixture();let drop=0,selected=0;bind(root,{select:()=>selected++,drop:()=>drop++});
 const event={dataTransfer:{files:[]},preventDefault(){},stopPropagation(){}};root.handlers.drop(event);assert.equal(drop,1,'adapter reads DataTransfer synchronously before event access expires');await new Promise(resolve=>setImmediate(resolve));assert.equal(drop,1);
 event.dataTransfer.files=[{}];root.handlers.drop(event);await new Promise(resolve=>setImmediate(resolve));assert.equal(selected,1);assert.ok(!source.includes('fetch('));
});
test('delegated mobile picker supports selection, cancellation and locking without opening native input',async()=>{
 const {root,input,bind}=fixture();let selected,resolve;const api=bind(root,{choose:()=>new Promise(r=>resolve=r),select:file=>selected=file});
 const click=()=>root.handlers.keydown({target:root,key:'Enter',preventDefault(){}});
 click();resolve({name:'gallery.png'});await new Promise(r=>setImmediate(r));assert.equal(selected.name,'gallery.png');assert.equal(input.clicked,undefined);
 selected=null;click();resolve(null);await new Promise(r=>setImmediate(r));assert.equal(selected,null);
 click();api.update({disabled:true});resolve({name:'late.png'});await new Promise(r=>setImmediate(r));assert.equal(selected,null);
});
test('media slots share preview, multi-file selection, replacement and clear behavior',async()=>{
 const {root,input,image,empty,filled,clear,bind}=fixture();let chosen=[],cleared=0;
 const api=bind(root,{kind:'video',selectFiles:files=>{chosen=files;},clear:()=>cleared++});
 api.update({preview:'blob:video',name:'clip.mp4',count:2,label:'参考视频',clearLabel:'清除参考视频'});
 assert.equal(root.dataset.assetSlot,'video');assert.equal(image.src,'blob:video');assert.equal(filled.textContent,'clip.mp4 · 2');
 assert.equal(empty.hidden,true);assert.equal(clear.hidden,false);
 input.files=[{name:'a.mp4'},{name:'b.mp4'}];input.handlers.change();await new Promise(r=>setImmediate(r));
 assert.deepEqual(Array.from(chosen,file=>file.name),['a.mp4','b.mp4']);
 clear.handlers.click({preventDefault(){},stopPropagation(){}});await new Promise(r=>setImmediate(r));assert.equal(cleared,1);
 api.update({preview:'',name:'',count:0});assert.equal(image.hidden,true);assert.equal(filled.hidden,true);
 const audio=fixture();audio.bind(audio.root,{kind:'audio',select:()=>{},clear:()=>{}}).update({name:'voice.wav',count:1});
 assert.equal(audio.root.dataset.assetSlot,'audio');assert.equal(audio.filled.hidden,false);
});
