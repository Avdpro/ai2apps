const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/todo.js'),'utf8');
function harness(fail=false) {
  const handlers = {};
  const emoji = {value:'',setCustomValidity(v){this.error=v;},reportValidity(){},addEventListener(k,fn){handlers[k]=fn;}};
  const priority = {value:'C',addEventListener(k,fn){handlers['priority:'+k]=fn;}};
  const form = {elements:{emoji,priority,status:{value:'not_started',addEventListener(k,fn){handlers['status:'+k]=fn;}},progress:{value:'0',blur(){this.blurred=true;},reportValidity(){return true;},addEventListener(k,fn){handlers['progress:'+k]=fn;}},title:{value:'Unsaved title'}}};
  const task = {id:'one',title:'Saved title',description:'Saved description',emoji:'',priority:'C',status:'not_started',progress:0,revision:1};
  const calls=[],errors=[];
  const slider={value:'0',blur(){this.blurred=true;},focus(){},addEventListener(k,fn){handlers['slider:'+k]=fn;}};
  const context = vm.createContext({Intl,Promise,Array,Set,console,
    $:s=>s==='#task-form'?form:s==='#project-progress-slider'?slider:{addEventListener(){},focus(){}},el:{querySelectorAll:()=>[]},t:task,draftTask:{...task},state:{tasks:[task]},
    fieldSavePending:0,fieldSaveEpoch:0,fieldSaveQueue:Promise.resolve(),dirty:false,
    tr:k=>k,notice:e=>errors.push(e),renderTree:()=>{},renderDirectory:()=>{},chatController:null,
    taskBody:({id,revision,...rest})=>rest,
    api:async(path,method,body)=>{calls.push(body);await Promise.resolve();if(fail)throw Error('conflict');return {...body,id:'one',revision:body.revision+1};}
  });
  const start=source.indexOf("const emojiForm=$('#task-form'),emojiInput=");
  const end=source.indexOf("$('#generate-emoji').onclick",start);
  vm.runInContext(source.slice(start,end),context);
  return {context,handlers,emoji,priority,calls,errors,slider,form};
}
test('rapid field changes serialize revisions and preserve unrelated drafts', async()=>{
  const h=harness();
  h.emoji.value='🎬';h.handlers.input({isComposing:false});
  h.priority.value='U';h.handlers['priority:change']();
  h.emoji.value='🚀';h.handlers.input({isComposing:false});
  await h.context.fieldSaveQueue;
  assert.deepEqual(h.calls.map(x=>x.revision),[1,2,3]);
  assert.ok(h.calls.every(x=>x.title==='Saved title'));
  assert.equal(h.context.state.tasks[0].emoji,'🚀');
  assert.equal(h.context.state.tasks[0].priority,'U');
  assert.equal(h.context.dirty,false);
  assert.equal(h.context.fieldSavePending,0);
});
test('Enter confirms emoji only, composition and invalid input do not save', async()=>{
  const h=harness();
  h.emoji.value='🎬';h.handlers.input({isComposing:true});
  assert.equal(h.calls.length,0);
  let prevented=false,stopped=false;
  h.handlers.keydown({key:'Enter',preventDefault(){prevented=true;},stopPropagation(){stopped=true;}});
  await h.context.fieldSaveQueue;
  assert.ok(prevented&&stopped);assert.equal(h.calls.length,1);
  h.emoji.value='not emoji';h.handlers.input({isComposing:false});
  await h.context.fieldSaveQueue;assert.equal(h.calls.length,1);assert.equal(h.context.dirty,true);
});
test('failed autosave keeps draft dirty and saved state unchanged',async()=>{
  const h=harness(true);h.emoji.value='🎬';h.handlers.input({isComposing:false});
  await h.context.fieldSaveQueue;
  assert.equal(h.context.state.tasks[0].emoji,'');assert.equal(h.context.dirty,true);
  assert.deepEqual(h.errors,['conflict']);assert.equal(h.context.fieldSavePending,0);
});

test('progress slider previews while dragging and saves on commit',async()=>{
  const h=harness();h.slider.value='35';h.handlers['slider:input']();
  assert.equal(h.form.elements.progress.value,'35');assert.equal(h.calls.length,0);
  h.handlers['slider:change']();await h.context.fieldSaveQueue;
  assert.equal(h.calls.length,1);assert.equal(h.calls[0].progress,35);
  assert.equal(h.slider.blurred,true);assert.equal(h.form.elements.progress.blurred,true);
  assert.equal(h.context.dirty,false);
});
