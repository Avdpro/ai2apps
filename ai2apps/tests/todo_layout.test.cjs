const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function setup(saved){
 const values={},classes=new Set(),handles=[];let stored=saved;
 const workspace={clientWidth:1500,classList:{contains:x=>classes.has(x),add:x=>classes.add(x),remove:x=>classes.delete(x)},style:{setProperty:(k,v)=>values[k]=v},append:h=>handles.push(h),getBoundingClientRect:()=>({left:0}),querySelector:()=>({getBoundingClientRect:()=>({left:1000,right:340})})};
 const context={document:{documentElement:{lang:'zh'},getElementById:()=>workspace,createElement:()=>({style:{},setAttribute(){},setPointerCapture(){}})},localStorage:{getItem:()=>stored,setItem:(_,v)=>stored=v},getComputedStyle:()=>({columnGap:'16',paddingLeft:'18',paddingRight:'18',getPropertyValue:k=>values[k]}),ResizeObserver:class{constructor(fn){this.fn=fn;}observe(){this.fn();}},MutationObserver:class{observe(){}},console};
 vm.runInNewContext(fs.readFileSync('web/static/js/todo_layout.js','utf8'),context);
 return {values,handles,workspace,stored:()=>JSON.parse(stored)};
}
test('defaults wider, pointer drag persists, reload restores and double-click resets',()=>{
 const x=setup(null);assert.equal(x.values['--left'],'340px');assert.equal(x.values['--right'],'420px');
 x.handles[0].onpointerdown({button:0,pointerId:1,clientX:340,preventDefault(){}});
 x.handles[0].onpointermove({pointerId:1,clientX:400});x.handles[0].onpointerup({pointerId:1});
 assert.equal(x.stored().left,400);assert.equal(setup(JSON.stringify(x.stored())).values['--left'],'400px');
 x.handles[0].ondblclick();assert.equal(x.stored().left,340);
});
test('oversized preferences fit central space and malformed storage falls back',()=>{
 const x=setup(JSON.stringify({left:640,right:640}));
 assert.ok(parseInt(x.values['--left'])+parseInt(x.values['--right'])<=1500-36-32-320);
 assert.equal(setup('broken').values['--left'],'340px');
});
