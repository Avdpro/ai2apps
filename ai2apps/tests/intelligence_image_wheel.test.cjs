const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/intelligence.js'),'utf8');
function setup(){const listeners={};const stage={addEventListener:(name,fn)=>listeners[name]=fn,getBoundingClientRect:()=>({left:0,top:0,width:400,height:400}),classList:{toggle(){}}};const image={naturalWidth:400,naturalHeight:400,style:{},addEventListener(){}};const c={Map,Math,performance};vm.createContext(c);vm.runInContext(source.slice(source.indexOf('function installImageGestures('),source.indexOf('let imagePreview=null;')),c);const controls=c.installImageGestures(stage,image,()=>{});return {listeners,image,controls};}
test('ordinary wheel zooms around cursor, clamps and resets',()=>{
 const {listeners,image,controls}=setup();let prevented=0;
 const wheel=(deltaY,deltaMode=0)=>listeners.wheel({deltaY,deltaMode,clientX:300,clientY:200,ctrlKey:false,preventDefault(){prevented++}});
 wheel(-100);const m=image.style.transform.match(/translate\(([-.\d]+)px,([-.\d]+)px\) scale\(([-.\d]+)\)/);const scale=Number(m[3]);assert.ok(scale>1);assert.ok(Math.abs(Number(m[1])-100*(1-scale))<1e-8);
 for(let i=0;i<20;i++)wheel(-100);assert.match(image.style.transform,/scale\(5\)/);
 for(let i=0;i<20;i++)wheel(100);assert.equal(image.style.transform,'translate(0px,0px) scale(1)');
 wheel(-3,1);assert.notEqual(image.style.transform,'translate(0px,0px) scale(1)');controls.reset();assert.equal(image.style.transform,'translate(0px,0px) scale(1)');assert.ok(prevented>0);
});
