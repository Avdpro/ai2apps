const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/intelligence.js'),'utf8');
function fixture(fail=false){
 const handlers={},calls=[],notices=[];
 const rows=['a','b','c'].map((id,i)=>({dataset:{channel:id},classList:{add(){},remove(){}},getBoundingClientRect:()=>({top:i*50,bottom:(i+1)*50,height:50})}));
 const list={children:[...rows],addEventListener:(t,f)=>handlers[t]=f,setPointerCapture(){},querySelectorAll(){return this.children},closest(){return null},append(row){this.children=this.children.filter(r=>r!==row);this.children.push(row)},insertBefore(row,target){this.children=this.children.filter(r=>r!==row);let i=this.children.indexOf(target);this.children.splice(i<0?this.children.length:i,0,row)}};
 const c={state:{channels:rows.map(r=>({id:r.dataset.channel}))},$:()=>list,api:async(...a)=>{calls.push(a);if(fail)throw Error('save failed')},render(){},notice:m=>notices.push(m),Map,CSS:{escape:x=>x}};
 vm.createContext(c);vm.runInContext(src.slice(src.indexOf('let channelDrag=null'),src.indexOf('function render(){')),c);
 const grip={closest:()=>rows[0]};
 const event=(y,type='pointermove')=>({type,pointerId:1,button:0,clientY:y,target:{closest:()=>grip},preventDefault(){},stopPropagation(){}});
 return {c,handlers,calls,notices,list,event};
}
test('pointer drag saves reordered IDs through existing channel edit route',async()=>{
 const f=fixture();f.handlers.pointerdown(f.event(10,'pointerdown'));f.handlers.pointermove(f.event(140));f.handlers.pointerup(f.event(140,'pointerup'));
 await new Promise(setImmediate);
 assert.deepEqual(f.list.children.map(r=>r.dataset.channel),['b','c','a']);
 assert.equal(f.calls[0][0],'/channels/b');assert.equal(f.calls[0][1],'PUT');
 assert.deepEqual(Array.from(f.calls[0][2].channel_order),['b','c','a']);
});
test('cancel restores DOM order and never saves',()=>{
 const f=fixture();f.handlers.pointerdown(f.event(10));f.handlers.pointermove(f.event(140));f.handlers.pointercancel(f.event(140,'pointercancel'));
 assert.deepEqual(f.list.children.map(r=>r.dataset.channel),['a','b','c']);assert.equal(f.calls.length,0);
});
test('failed save restores state and reports failure',async()=>{
 const f=fixture(true);await f.c.saveChannelOrder(['c','b','a']);
 assert.deepEqual(Array.from(f.c.state.channels,c=>c.id),['a','b','c']);assert.deepEqual(f.notices,['save failed']);
});
