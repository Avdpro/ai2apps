const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const code=source.slice(source.indexOf('    const stepConversations ='),source.indexOf('    function renderSteps()'));
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.value='';}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=items;}
 setAttribute(){}
}
function setup(api){
 const step={name:'read',desc:'Read',operation:'inspect'};
 const state={draft:{id:'draft',source:{steps:[step]}},capabilityId:null};
 const root=new Element('div');const opened={};
 const ctx={state,Map,JSON,structuredClone,document:{createElement:t=>new Element(t)},
 tr:k=>k,tierSelect:value=>Object.assign(new Element('select'),{value}),syncEditor:()=>{},
 api,withBusy:fn=>fn(),currentCapability:()=>state.draft.source,renderSteps:()=>{},
 $:()=>({children:[opened]}),notice:()=>{}};
 vm.runInNewContext(code+';globalThis.render=renderStepConversation;',ctx);
 ctx.render(root,0,step);
 const panel=root.children[0];
 return {state,panel,ctx,step,root,prompt:panel.children.find(e=>e.tag==='textarea'),
 send:panel.children.find(e=>e.tag==='button'&&e.textContent.endsWith('send')),
 apply:panel.children.find(e=>e.tag==='button'&&e.textContent.endsWith('apply'))};
}
test('step dialogue keeps conversation and requires explicit apply without saving or running',async()=>{
 const requests=[];
 const view=setup(async(url,options)=>{requests.push({url,body:JSON.parse(options.body)});
 return {step:{...view.step,desc:'Read title'},message:'Updated title extraction'};});
 view.prompt.value='Read only the title';view.prompt.oninput();await view.send.onclick();
 assert.equal(view.state.draft.source.steps[0].desc,'Read');
 assert.equal(requests[0].url,'/agent-steps/revisions');assert.equal(requests[0].body.step_index,0);
 view.prompt.value='Keep the transition';await view.send.onclick();
 assert.equal(requests[1].body.messages.length,2);
 assert.equal(requests[1].body.messages[1].role,'assistant');
 await view.apply.onclick();assert.equal(view.state.draft.source.steps[0].desc,'Read title');
 assert.equal(requests.length,2);
});
test('stale proposal cannot overwrite newer manual edits',async()=>{
 const view=setup(async()=>({step:{name:'read',desc:'AI result'},message:'Changed'}));
 view.prompt.value='Improve';await view.send.onclick();
 view.state.draft.source.steps[0].desc='Manual update';
 await assert.rejects(view.apply.onclick(),/step_chat_stale/);
 assert.equal(view.state.draft.source.steps[0].desc,'Manual update');
});
test('failed model request retains text for retry and does not add a fake assistant message',async()=>{
 const view=setup(async()=>{throw new Error('model unavailable');});
 view.prompt.value='Keep this request';view.prompt.oninput();
 await assert.rejects(view.send.onclick(),/model unavailable/);
 assert.equal(view.prompt.value,'Keep this request');assert.equal(view.send.disabled,false);
 const other=new Element('div');view.ctx.render(other,0,view.step);
 assert.equal(other.children[0].children.find(e=>e.tag==='textarea').value,'Keep this request');
});
