const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
function harness(){
 const nodes=new Map(),state={draft:{source:{capabilities:[{id:'capability-2',name:'site.old',title:'Old',steps:[{name:'original'}]}]}},capabilityId:'capability-2'};
 const $=key=>{if(!nodes.has(key))nodes.set(key,{value:'',hidden:true,open:false,showModal(){this.open=true},close(){this.open=false},reportValidity(){this.invalid=true},focus(){},selectedOptions:[{}]});return nodes.get(key)};
 let confirmed=false,syncs=0;
 const env={state,$,structuredClone,capabilities:()=>state.draft.source.capabilities,currentCapability:()=>state.draft.source.capabilities.find(x=>x.id===state.capabilityId),syncEditor:()=>syncs++,ensureCapabilitySource(){},renderDraft(){},notice(){},tr:(key,args)=>args?.name || key,window:{confirm:()=>confirmed}};
 vm.runInNewContext(source.slice(source.indexOf("        $('#agent-capability-title').onchange"),source.indexOf("        $('#agent-refresh').onclick")),env);
 return {state,$,env,approve:()=>confirmed=true,syncs:()=>syncs};
}
test('standard capability creates a working call with schema and unique id; repeat selects existing',()=>{
 const h=harness();h.state.capabilityTemplates=[{name:'web.extract-list',title:'Extract list',description:'Read items',agent_id:'builtin:web:extract-list',generation_id:'v2',input_schema:{type:'object',properties:{limit:{type:'integer',default:20}}},output_schema:{type:'object',properties:{items:{type:'array'}}}}];
 h.$('#agent-capability-template').value='0';h.$('#agent-create-capability').onclick();
 const cap=h.state.draft.source.capabilities[1];assert.equal(cap.id,'capability-3');assert.equal(cap.name,'web.extract-list');assert.equal(cap.steps[0].arguments.parameters.limit,'${input.limit}');assert.equal(cap.inputs.properties.limit.default,20);assert.equal(cap.steps[0].on.success,'done');
 h.$('#agent-create-capability').onclick();assert.equal(h.state.draft.source.capabilities.length,2);assert.equal(h.state.capabilityId,cap.id);
});
test('delete capability requires confirmation, preserves other capabilities and allows deleting final one',()=>{
 const h=harness();h.$('#agent-delete-capability').onclick();assert.equal(h.state.draft.source.capabilities.length,1);
 h.$('#agent-capability-template').value='';h.$('#agent-new-capability-name').value='Custom';h.$('#agent-create-capability').onclick();const added=h.state.capabilityId;
 h.approve();h.$('#agent-delete-capability').onclick();assert.equal(h.state.draft.source.capabilities.length,1);assert.equal(h.state.draft.source.capabilities[0].steps[0].name,'original');
 h.state.capabilityId='capability-2';h.$('#agent-delete-capability').onclick();assert.equal(h.state.draft.source.capabilities.length,0);assert.equal(h.state.capabilityId,null);
});

test('capability edit and delete controls belong to shared editor, not hidden Review panel',()=>{
 const html=fs.readFileSync(__dirname+'/../web/templates/system_apps/agent_mini.html','utf8');
 const build=html.slice(html.indexOf('<section id="agent-build-panel"'),html.indexOf('</main>'));
 const review=html.slice(html.indexOf('<section id="agent-recipe-review"'),html.indexOf('<section id="agent-build-panel"'));
 for(const id of ['agent-capability-details','agent-capability-title','agent-capability-description','agent-delete-capability']){
  assert.ok(build.includes('id="'+id+'"'),id+' must be in shared editor');
  assert.ok(!review.includes('id="'+id+'"'),id+' must not be hidden in Review');
 }
});

test('new capability chooser opens without mutation and Cancel leaves existing capability intact',()=>{
 const h=harness(),before=JSON.stringify(h.state.draft.source);
 h.$('#agent-add-capability').onclick();assert.equal(h.$('#agent-new-capability-panel').open,true);
 assert.equal(JSON.stringify(h.state.draft.source),before);assert.equal(h.syncs(),0);
 h.$('#agent-cancel-capability').onclick();assert.equal(h.$('#agent-new-capability-panel').open,false);
 assert.equal(JSON.stringify(h.state.draft.source),before);
});

test('custom capability dialog validates name, then adds entered name and description only on confirmation',()=>{
 const h=harness();h.$('#agent-add-capability').onclick();
 h.$('#agent-create-capability').onclick();assert.equal(h.state.draft.source.capabilities.length,1);assert.equal(h.$('#agent-new-capability-name').invalid,true);
 h.$('#agent-capability-template').value='0';h.$('#agent-capability-template').onchange();assert.equal(h.$('#agent-custom-capability-fields').hidden,true);
 h.$('#agent-capability-template').value='';h.$('#agent-capability-template').onchange();assert.equal(h.$('#agent-custom-capability-fields').hidden,false);
 h.$('#agent-new-capability-name').value=' Article reader ';h.$('#agent-new-capability-description').value=' Read titles and links. ';
 h.$('#agent-create-capability').onclick();const added=h.state.draft.source.capabilities[1];
 assert.equal(added.title,'Article reader');assert.equal(added.description,'Read titles and links.');assert.equal(h.$('#agent-new-capability-panel').open,false);
});

test('runtime uses compiled capability guidance even when another capability is selected',()=>{
 const state={draft:{source:{description:'Agent guidance'}}};
 const env={state,currentCapability:()=>({working_goal:'Other capability guidance'})};
 vm.runInNewContext(source.slice(source.indexOf('    function stepWorkingGoal('),source.indexOf('    async function executeAIStep(')),env);
 assert.equal(env.stepWorkingGoal({working_goal:'Compiled capability guidance'}),'Compiled capability guidance');
 assert.equal(env.stepWorkingGoal({working_goal:''}),'');
 assert.equal(env.stepWorkingGoal({}),'Other capability guidance');
 env.currentCapability=()=>({working_goal:'  '});
 assert.equal(env.stepWorkingGoal({}),'Agent guidance');
});
