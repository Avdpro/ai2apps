const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/space.js','utf8');
function setup(language='zh'){
 let timers=[],cleared=0,observers=[];
 const all=n=>[n,...n.children.flatMap(all)];
 const make=tag=>({tag,isConnected:true,remove(){this.isConnected=false;},children:[],dataset:{},attrs:{},append(...n){this.children.push(...n);},prepend(...n){this.children.unshift(...n);},replaceChildren(...n){this.children=n;},querySelector(s){return all(this).find(n=>n.className===s.slice(1));},querySelectorAll(s){return all(this).filter(n=>n.tag===s);},setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,v){this[k]=v;},pause(){this.paused=true;}});
 const window={},document={documentElement:{lang:language},visibilityState:'visible',createElement:make,createTextNode:t=>Object.assign(make('#text'),{textContent:t}),querySelector:()=>null};
 vm.runInNewContext(source,{window,document,URL,IntersectionObserver:class{constructor(fn){observers.push(fn);}observe(){}disconnect(){}},setInterval:f=>(timers.push(f),timers.length),clearInterval:()=>cleared++});
 return {root:make('main'),render:window.renderVisitorSpace,all,timers,document,observers,get cleared(){return cleared;}};
}
test('carousel defaults manual, switches dots, pauses on playback and disposes timer',()=>{
 const q=setup();q.render(q.root,{title:'Space',cards:[{kind:'carousel',cards:[{kind:'text',title:'one'},{kind:'text',title:'two'}]}]});
 const slides=q.all(q.root).find(n=>n.className==='visitor-slides');assert.equal(slides.children[0].hidden,false);q.timers[0]();assert.equal(slides.children[0].hidden,false);
 const dots=q.all(q.root).find(n=>n.className==='visitor-dots');dots.children[1].onclick();assert.equal(slides.children[1].hidden,false);
 const toggle=q.all(q.root).find(n=>n.textContent==='自动轮播');toggle.onclick();q.timers[0]();assert.equal(slides.children[0].hidden,false);
 slides.play();q.timers[0]();assert.equal(slides.children[0].hidden,false);
 q.render(q.root,{title:'new',cards:[]});assert.equal(q.cleared,1);
});
test('article renders HTML as text and resource cards only use opaque identifiers',()=>{
 const q=setup();q.render(q.root,{title:'Space',cards:[{kind:'article',body:'# Title\n<script>steal()</script>\n**bold**'},{kind:'image',assetId:'../secret'},{kind:'html',assetId:'b'.repeat(64)}]},{resourceUrl:id=>'/safe/'+id});
 assert.ok(q.all(q.root).some(n=>n.textContent==='<script>steal()</script>'));assert.ok(!q.all(q.root).some(n=>n.tag==='script'||n.tag==='img'||n.tag==='iframe'));
 const play=q.all(q.root).find(n=>n.attrs?.['aria-label']==='运行互动作品');play.onclick();const frame=q.all(q.root).find(n=>n.tag==='iframe');assert.equal(frame.attrs.sandbox,'allow-scripts');assert.equal(frame.src,'/safe/'+'b'.repeat(64));
});

test('HTML autoload is visibility-bound, manual stop persists, cover returns on stop',()=>{
 const q=setup();q.render(q.root,{title:'Space',cards:[{kind:'html',assetId:'a'.repeat(64),coverId:'b'.repeat(64),autoload:true}]},{resourceUrl:id=>'/media/'+id});
 const poster=q.all(q.root).find(n=>n.attrs?.['aria-label']==='运行互动作品');assert.equal(poster.children.find(n=>n.tag==='img').src,'/media/'+'b'.repeat(64));
 assert.ok(!q.all(q.root).some(n=>n.tag==='iframe'));
 q.observers[0]([{isIntersecting:true}]);assert.equal(poster.hidden,true);assert.equal(q.all(q.root).find(n=>n.tag==='iframe').attrs.sandbox,'allow-scripts');
 const stop=q.all(q.root).find(n=>n.attrs?.['aria-label']==='停止作品');assert.equal(stop.textContent||'','');assert.equal(stop.className,'visitor-html-stop-surface');assert.ok(q.all(q.root).find(n=>n.tag==='iframe').attrs.inert!==undefined);stop.onclick();assert.equal(poster.hidden,false);
 q.observers[0]([{isIntersecting:false}]);q.observers[0]([{isIntersecting:true}]);assert.equal(poster.hidden,false);
 poster.onclick();assert.equal(poster.hidden,true);q.observers[0]([{isIntersecting:false}]);assert.equal(poster.hidden,false);
});

test('untitled HTML is a clean display; titled and manual cards retain controls',()=>{
 const q=setup();q.render(q.root,{cards:[{kind:'html',title:' ',assetId:'a'.repeat(64),autoload:true},{kind:'html',title:'Named',assetId:'b'.repeat(64)}]},{resourceUrl:id=>'/media/'+id});
 const cards=q.all(q.root).filter(n=>n.tag==='article');
 assert.ok(cards[0].className.includes('visitor-html-bare'));
 assert.ok(!cards[0].children.some(n=>n.tag==='h2'||n.className==='visitor-eyebrow'));
 assert.ok(cards[1].children.some(n=>n.textContent==='Named'));
 const stop=cards[1].children.find(n=>n.textContent==='停止作品');assert.ok(stop);
 const play=q.all(cards[1]).find(n=>n.attrs?.['aria-label']==='运行互动作品');play.onclick();assert.equal(stop.hidden,false);
});

test('translated renderer preserves even user text matching system labels',()=>{
 const q=setup('fr');const space={title:'保存草稿',description:'关闭',cards:[{kind:'text',title:'标题',text:'这里还没有添加内容。'},{kind:'article',title:'中文稿件',body:'**用户原文**'}]};const before=JSON.stringify(space);
 q.render(q.root,space);const nodes=q.all(q.root);
 for(const text of ['保存草稿','关闭','标题','这里还没有添加内容。','用户原文'])assert.ok(nodes.some(n=>n.textContent===text),text);
 assert.ok(nodes.some(n=>n.textContent==='Lire la suite'));assert.equal(JSON.stringify(space),before);
});
