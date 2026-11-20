const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function fixture(){
 function node(tag){return {tag,isConnected:true,dataset:{},children:[],setAttribute(k,v){this[k]=v;},append(...items){this.children.push(...items);}};}
 const window={},root=node('article');root._botInteractionKey='question';let seq=0;
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/bot_interactions.js'),'utf8'),{window,crypto:{randomUUID:()=>String(++seq)},document:{createElement:node}});
 const accepted=[],errors=[],item={id:'question',prompt:'Which source?',schema:{properties:{answer:{type:'string'}}}};
 function mount(submit){const form=window.AI2AppsBotInteractions.answerForm({root,item,label:(a,b)=>b,submit,onSubmitted:id=>accepted.push(id),onError:e=>errors.push(e)});return {form,field:form.children[1].children[0],button:form.children[2],status:form.children[3],send:()=>form.onsubmit({preventDefault(){}})};}
 return {root,accepted,errors,mount};
}
test('answer remains visible as a disabled receipt immediately after acknowledgement, with duplicate submit blocked',async()=>{
 const f=fixture(),calls=[];let finish;const ui=f.mount((...args)=>{calls.push(args);return new Promise(resolve=>finish=resolve);});ui.field.value='Use the summarizer';const pending=ui.send();assert.equal(f.root.dataset.interactionState,'submitting');assert.equal(ui.button.disabled,true);await ui.send();assert.equal(calls.length,1);finish({});await pending;assert.equal(f.root.dataset.interactionState,'submitted');assert.equal(ui.button.hidden,true);assert.equal(ui.field.disabled,true);assert.equal(ui.field.value,'Use the summarizer');assert.match(ui.status.textContent,/Reply received/);assert.deepEqual(f.accepted,['question']);await ui.send();assert.equal(calls.length,1);
});
test('uncertain delivery retains draft and retry identity, while edited answer gets a new identity',async()=>{
 const f=fixture(),calls=[];let fail=true;const ui=f.mount(async(response,id)=>{calls.push({response,id});if(fail)throw Error('network');});ui.field.value='A';await ui.send();assert.equal(f.root.dataset.interactionState,'error');assert.equal(ui.field.disabled,false);assert.match(ui.status.textContent,/not confirmed/);await ui.send();assert.equal(calls[0].id,calls[1].id);ui.field.value='B';fail=false;await ui.send();assert.notEqual(calls[2].id,calls[1].id);assert.equal(f.root.dataset.interactionState,'submitted');
});
test('late acknowledgement cannot repaint a different interaction',async()=>{
 const f=fixture();let finish;const ui=f.mount(()=>new Promise(resolve=>finish=resolve));ui.field.value='A';const pending=ui.send();f.root._botInteractionKey='new-question';f.root.dataset.interactionState='waiting';finish({});await pending;assert.equal(f.root.dataset.interactionState,'waiting');assert.equal(f.accepted.length,1);
});
