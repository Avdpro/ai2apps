const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/todo.js'),'utf8');
function setup(){
 const elements=Object.fromEntries(['name-dialog','dialog-title','dialog-name','dialog-task-fields','dialog-priority','dialog-description'].map(id=>['#'+id,{}]));
 let close;elements['#name-dialog'].showModal=()=>{};elements['#name-dialog'].addEventListener=(_,fn)=>{close=fn;};
 const calls=[];
 const ctx=vm.createContext({$:id=>elements[id],aggregateId:null,canLeave:()=>true,tr:x=>x,state:{tasks:[{id:'parent',directory_id:'parent-dir'}]},directoryId:'current-dir',api:async(...args)=>{calls.push(args);return {id:'new'};},setColumn:()=>{},collapsed:new Set(['parent']),refresh:async()=>{}});
 vm.runInContext(source.slice(source.indexOf('async function nameDialog('),source.indexOf('function attachmentRows(')),ctx);
 return {ctx,elements,calls,close:(value='save')=>{elements['#name-dialog'].returnValue=value;close();}};
}
test('new child submits priority and multiline instructions with its parent directory',async()=>{
 const s=setup();const pending=s.ctx.createTask('parent');
 assert.equal(s.elements['#dialog-task-fields'].hidden,false);
 assert.equal(s.elements['#dialog-priority'].value,'C');
 s.elements['#dialog-name'].value=' Task ';
 s.elements['#dialog-priority'].value='U';
 s.elements['#dialog-description'].value='First step\nSecond step';s.close();await pending;
 assert.deepEqual(JSON.parse(JSON.stringify(s.calls[0])),['/tasks','POST',{title:'Task',priority:'U',description:'First step\nSecond step',directory_id:'parent-dir',parent_id:'parent'}]);
});
test('cancelling creates nothing; reopening for directory resets and hides task fields',async()=>{
 const s=setup();const task=s.ctx.createTask();s.elements['#dialog-description'].value='draft';s.close('cancel');await task;assert.equal(s.calls.length,0);
 const directory=s.ctx.nameDialog('Directory');assert.equal(s.elements['#dialog-task-fields'].hidden,true);assert.equal(s.elements['#dialog-description'].value,'');s.elements['#dialog-name'].value=' Work ';s.close();assert.equal(await directory,'Work');
});
