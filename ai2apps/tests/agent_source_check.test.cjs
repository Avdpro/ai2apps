const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const code=source.slice(source.indexOf('    async function checkSteps('),source.indexOf('    async function runEditorStep('));
test('check only submits source and reports each step without browser actions',async()=>{
 const calls=[],statuses=[];
 const authored={capabilities:[{id:'run',steps:[{name:'open'},{name:'read'}]}]};
 const ctx={state:{capabilityId:'run'},editorSource:()=>authored,withBusy:fn=>fn(),tr:k=>k,
  api:async(path,options)=>{calls.push(path);assert.deepEqual(JSON.parse(options.body).source,authored);return{valid:false,report:{errors:[{path:'capabilities.0.steps.1.on.success',code:'missing_target'}]}};},
  showStepExecution:(...args)=>statuses.push(args),notice:()=>{},$:()=>({setAttribute:()=>{},focus:()=>{},scrollIntoView:()=>{}})};
 vm.createContext(ctx);vm.runInContext(code,ctx);
 await ctx.checkSteps();
 assert.deepEqual(calls,['/agent-source/check']);
 assert.equal(statuses[0][2],'success');assert.equal(statuses[1][2],'error');
 assert.match(statuses[1][1],/missing_target/);
});
