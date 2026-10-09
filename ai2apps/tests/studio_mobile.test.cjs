const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
function fixture(mobile=true, imagine=false, overrides={}, appId=null){
 class Element {constructor(){this.dataset={};this.children=[];this.classList={add(){},remove(){},toggle(){}};this.hidden=false;this.isConnected=true;} append(...x){this.children.push(...x);} prepend(x){this.children.unshift(x);} querySelectorAll(){return [];} querySelector(s){return this.selectors?.[s]||null;} addEventListener(k,f){(this.events??={})[k]=f;} }
 const header=new Element(),list=new Element(),editor=new Element(),output=new Element(),root=new Element();root.dataset.appId=appId||(imagine?'ai2apps.imagine-studio':'ai2apps.video-studio');root.selectors={'.studio-header':header,'.vs-studio-sidebar,.ra-studio-sidebar':list,'.is-mini-app-workspace,.vs-mini-app-workspace,.ra-pipeline-workspace':editor,'.vs-render-workspace,.ra-render-workspace':output};
 const media={matches:mobile,addEventListener(k,f){this.change=f;}};
 const messages={};const context={setTimeout:()=>1,clearTimeout(){},window:{location:{origin:'http://localhost'},matchMedia:()=>media,addEventListener(k,f){messages[k]=f;}},document:{documentElement:{lang:'zh'},elementFromPoint:()=>null,createElement:()=>new Element()},console};vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/studio_mobile.js','utf8'),context);
 let calls=0;const app={currentMiniApp:{id:'a'},leftView:'assets',prompt:'keep',selectedOutput:{id:'out'},async selectMiniApp(id){calls++;this.currentMiniApp={id};}};
 Object.assign(app,overrides);
 context.window.AI2AppsMobileStudio.mount(root,app);
 return {root,app,header,media,messages,get calls(){return calls;},accepts:context.window.AI2AppsMobileStudio.accepts};
}
test('mobile list, editor and shared output retain draft and selection',async()=>{const f=fixture();assert.equal(f.root.dataset.smPage,'library');await f.app.selectMiniApp('a');assert.equal(f.calls,0);assert.equal(f.root.dataset.smPage,'create');f.header.children[1].onclick();assert.equal(f.root.dataset.smPage,'output');f.header.children[0].onclick();assert.equal(f.root.dataset.smPage,'create');assert.equal(f.app.prompt,'keep');assert.equal(f.app.selectedOutput.id,'out');f.header.children[0].onclick();assert.equal(f.root.dataset.smPage,'library');});
test('switching Mini-App retains the original activation implementation',async()=>{const f=fixture();await f.app.selectMiniApp('b');assert.equal(f.calls,1);assert.equal(f.root.dataset.smPage,'create');});
test('desktop activation is unchanged',async()=>{const f=fixture(false);await f.app.selectMiniApp('a');assert.equal(f.calls,1);assert.equal(f.root.dataset.smPage,undefined);});
test('Gallery matching rejects wrong media, supports extension and wildcard',()=>{const {accepts}=fixture();assert.equal(accepts('image/png,image/jpeg','audio/wav','x.wav'),false);assert.equal(accepts('audio/*','audio/wav'),true);assert.equal(accepts('.MP4','video/mp4','clip.mp4'),true);assert.equal(accepts('image/png','image/svg+xml','test.svg'),false);});

test('only the current same-origin Gallery frame can switch to Mini-App during drag',async()=>{
 const f=fixture();const frame={contentWindow:{},getBoundingClientRect:()=>({left:10,top:20})};f.root.selectors['iframe[x-ref="galleryMini"]']=frame;
 const data={type:'ai2apps.gallery.studio-drag',phase:'start',touch:false,asset:{id:'asset',name:'image.png',kind:'image'},x:30,y:40};
 await f.messages.message({origin:'https://other.example',source:frame.contentWindow,data});assert.equal(f.root.dataset.smPage,'library');
 await f.messages.message({origin:'http://localhost',source:{},data});assert.equal(f.root.dataset.smPage,'library');
 f.app.leftView='assets';await f.messages.message({origin:'http://localhost',source:frame.contentWindow,data});assert.equal(f.root.dataset.smPage,'create');assert.equal(f.app.currentMiniApp.id,'a');assert.equal(f.app.prompt,'keep');
 await f.messages.message({origin:'http://localhost',source:frame.contentWindow,data:{...data,phase:'end'}});assert.equal(f.root.dataset.smPage,'library');assert.equal(f.app.leftView,'assets');
});

test('Imagine completion opens shared mobile output and returns to editor',async()=>{
 const f=fixture(true,true);await f.app.selectMiniApp('a');
 f.app.openMobileOutput();assert.equal(f.root.dataset.smPage,'output');
 f.app.openMobileOutput();f.header.children[0].onclick();
 assert.equal(f.root.dataset.smPage,'create');assert.equal(f.app.prompt,'keep');
});

test('video feed ignores old history, failure and repeats; opens new completed task',async()=>{
 let rows=[{id:'old',status:'succeeded'}];
 const f=fixture(true,false,{tasks:[],async refresh(){this.tasks=rows;}});
 await f.app.refresh();assert.equal(f.root.dataset.smPage,'library');
 await f.app.selectMiniApp('a');rows=[{id:'new',status:'failed'},...rows];
 await f.app.refresh();assert.equal(f.root.dataset.smPage,'create');
 rows=[{id:'new',status:'succeeded'},rows[1]];
 await f.app.refresh();assert.equal(f.root.dataset.smPage,'output');assert.equal(f.app.selectedTaskId,'new');
 f.header.children[0].onclick();await f.app.refresh();assert.equal(f.root.dataset.smPage,'create');
});
test('Voice selects new shared output without changing Mini-App or private cache',async()=>{
 let rows=[{id:'old',downloadUrl:'/old'}];
 const f=fixture(true,false,{studioOutputs:[],lineAudioArtifact:{id:'private'},async refreshOutputs(){this.studioOutputs=rows;}},'ai2apps.readaloud');
 await f.app.refreshOutputs();await f.app.selectMiniApp('a');
 rows=[{id:'new',downloadUrl:'/new'},...rows];await f.app.refreshOutputs();
 assert.equal(f.root.dataset.smPage,'output');assert.equal(f.app.selectedOutput.id,'new');
 assert.equal(f.app.lineAudioArtifact.id,'private');assert.equal(f.app.currentMiniApp.id,'a');
});
test('Package output requires this Studio and a published result',()=>{
 const f=fixture();const publish=detail=>f.messages['ai2apps:studio-output']({detail});
 publish({studioId:'ai2apps.readaloud',result:{downloadUrl:'/file'}});assert.equal(f.root.dataset.smPage,'library');
 publish({studioId:'ai2apps.video-studio'});assert.equal(f.root.dataset.smPage,'library');
 publish({studioId:'ai2apps.video-studio',result:{downloadUrl:'/file'}});assert.equal(f.root.dataset.smPage,'output');
});
test('desktop completed output does not change mobile navigation',async()=>{
 let rows=[];const f=fixture(false,false,{tasks:[],async refresh(){this.tasks=rows;}});
 await f.app.refresh();rows=[{id:'done',status:'succeeded'}];await f.app.refresh();assert.equal(f.root.dataset.smPage,undefined);
});

test('mobile output shrinks progressively, keeps scroll footprint and restores desktop',()=>{
 const values=new Map(),classes=new Set(),events={};let resize;
 const preview={offsetHeight:315,classList:{add:x=>classes.add(x),remove:x=>classes.delete(x),contains:x=>classes.has(x)},style:{setProperty:(k,v)=>values.set(k,v),getPropertyValue:k=>values.get(k)}};
 const panel={scrollTop:0,querySelector:()=>preview,addEventListener:(k,f)=>events[k]=f};
 const media={matches:true,addEventListener:(k,f)=>media.change=f};
 const context={window:{getComputedStyle:()=>({marginBottom:'16px'})},ResizeObserver:class{constructor(f){resize=f;}observe(){}},console};
 vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/studio_mobile.js','utf8'),context);
 context.window.AI2AppsMobileStudio.mountOutputCollapse(panel,media);resize();
 assert.equal(values.get('--sm-preview-expanded'),'315px');assert.equal(values.get('--sm-preview-shrink'),'0px');
 panel.scrollTop=80;events.scroll();assert.equal(values.get('--sm-preview-shrink'),'80px');
 panel.scrollTop=600;events.scroll();assert.equal(values.get('--sm-preview-shrink'),'203px');
 panel.scrollTop=0;events.scroll();assert.equal(values.get('--sm-preview-shrink'),'0px');
 panel.scrollTop=-20;events.scroll();assert.equal(values.get('--sm-preview-shrink'),'0px');
 media.matches=false;media.change();assert.equal(classes.size,0);
 const css=fs.readFileSync(__dirname+'/../web/static/css/studio_mobile.css','utf8');
 assert.match(css,/margin-bottom:calc\(var\(--sm-preview-margin,0px\) \+ var\(--sm-preview-shrink,0px\)\)/);
});
