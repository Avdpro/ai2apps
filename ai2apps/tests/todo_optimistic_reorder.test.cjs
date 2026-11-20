const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('web/static/js/todo.js','utf8');
function setup(){
 let resolve,reject;
 const request=new Promise((yes,no)=>{resolve=yes;reject=no;}),events=[];
 const ctx=vm.createContext({reorderBusy:false,fieldSavePending:0,fieldSaveEpoch:0,zh:false,
  api:()=>{events.push('request');return request;},notice:text=>events.push(text),tr:s=>s,
  refresh:async detail=>events.push(['refresh',detail])});
 vm.runInContext(source.slice(source.indexOf('async function saveReorderOptimistically('),source.indexOf('function clearDirectoryDrag(')),ctx);
 return {ctx,events,resolve,reject,save:()=>ctx.saveReorderOptimistically(()=>events.push('apply'),()=>events.push('rollback'),'/tasks/reorder',{})};
}
test('drop updates UI before response and synchronizes without forced detail reset',async()=>{
 const h=setup(),pending=h.save();
 assert.deepEqual(h.events.slice(0,3),['apply','Saving order…','request']);
 assert.equal(h.ctx.fieldSavePending,1);
 await h.save();assert.equal(h.events.filter(e=>e==='request').length,1);
 h.resolve({ok:true});await pending;
 assert.ok(!h.events.includes('rollback'));
 assert.deepEqual(h.events.at(-1),['refresh',false]);
 assert.equal(h.ctx.fieldSavePending,0);assert.equal(h.ctx.reorderBusy,false);
 assert.equal(h.ctx.fieldSaveEpoch,2);
});
test('failed background save rolls back and releases pending guards',async()=>{
 const h=setup(),pending=h.save();h.reject(new Error('Conflict'));await pending;
 assert.ok(h.events.includes('rollback'));assert.ok(h.events.some(e=>typeof e==='string'&&e.includes('Conflict')));
 assert.equal(h.ctx.fieldSavePending,0);assert.equal(h.ctx.reorderBusy,false);
});
