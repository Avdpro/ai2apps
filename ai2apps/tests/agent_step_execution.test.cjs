const test=require('node:test'), assert=require('node:assert/strict'), vm=require('node:vm'), fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const executeSource=source.slice(source.indexOf('    async function execute(step,'),source.indexOf('    async function executeAIStep('));
function executor(result, mode) {
 const calls=[], bidi={contextId:'tab'};
 const ctx={state:{},client:async()=>bidi,executeInContext:async()=>{calls.push('direct');return result;},
 executeAIStep:async(step,scopes,ids,failure)=>{calls.push(['ai',step.ai.tier,Boolean(failure)]);return {outcome:'success'};}};
 vm.runInNewContext(executeSource+';globalThis.run=execute',ctx);
 return {calls,run:preview=>ctx.run({operation:'input',mode,ai:{tier:'complex'}},preview)};
}
test('interpreted steps go straight to selected AI tier; preview does not call AI',async()=>{
 const x=executor({outcome:'success'},'interpreted');await x.run(false);
 assert.deepEqual(x.calls,[['ai','complex',false]]);
 const y=executor({outcome:'success'},'interpreted');await y.run(true);assert.deepEqual(y.calls,['direct']);
});
test('adaptive falls back after failure; compiled and successful steps stay direct',async()=>{
 const x=executor({outcome:'not_found'},'adaptive');await x.run(false);
 assert.deepEqual(x.calls,['direct',['ai','complex',true]]);
 for(const [outcome,mode] of [['success','adaptive'],['failed','compiled'],['restricted','adaptive'],['needs_user','adaptive']]) {
 const y=executor({outcome},mode);await y.run(false);assert.deepEqual(y.calls,['direct']); }
});
const aiSource=source.slice(source.indexOf('    function stepWorkingGoal('),source.indexOf('    async function executeInContext('));
test('AI planning uses fresh DOM, exact selected tier, bound arguments and no tier escalation',async()=>{
 const requests=[],actions=[],ctx={currentCapability:()=>null,state:{attachments:[]},client:async()=>({contextId:'tab',explorationObservation:async()=>({url:'https://example.com',controls:[{ref:'e1'}]}),relatedWindowObservations:async()=>[],pageState:async()=>({})}),
 api:async(url,opts)=>{requests.push(JSON.parse(opts.body));return requests.length===1?{decision:'action',compiled_step:{operation:'input',arguments:{value:'hello'}}}:{decision:'complete'};},
 explorationActionNeedsConfirmation:()=>false, execute:async action=>{actions.push(action);return {outcome:'success',evidence:{}};}};
 vm.runInNewContext(aiSource+';globalThis.run=executeAIStep',ctx);
 const result=await ctx.run({description:'Type text',ai:{tier:'simple'},arguments:{value:'hello'}},['https://example.com/**'],[]);
 assert.equal(result.outcome,'success');assert.equal(requests[0].model_tier,'simple');assert.equal(requests[0].allow_model_escalation,false);
 assert.match(requests[0].goal,/hello/);assert.equal(requests[0].observation.context,'tab');assert.equal(actions[0].mode,'compiled');
 assert.equal(requests[1].attempts.length,1);
});
