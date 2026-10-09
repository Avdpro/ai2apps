const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const code=source.slice(source.indexOf('    async function plannedStep('),source.indexOf('    function showStepExecution('));
test('invalid rule plan invokes AI with authored source, saves binding and validates again',async()=>{
 const original={name:'打开网页',operation:'open',desc:'打开url参数指定的页面。',arguments:{},on:{success:'done',failed:'failed'}};
 const capability={inputs:{properties:{url:{type:'string'}}},steps:[original]};
 const state={draft:{id:'draft',source:capability},capabilityId:null};
 let plans=0,repairs=0,saves=0;
 const ctx={state,structuredClone,encodeURIComponent,syncEditor:()=>{},persistDraft:async()=>saves++,currentCapability:()=>capability,
 showStepExecution:()=>{},renderSteps:()=>{},builderSelection:()=>({model_tier:'standard'}),tr:k=>k,
 api:async(path,options)=>{
  if(path==='/agent-steps/revisions'){
   repairs++;const request=JSON.parse(options.body);assert.equal(request.source.steps[0].desc,original.desc);
   assert.equal(request.source.inputs.properties.url.type,'string');
   return {step:{...original,arguments:{url:'${input.url}'}}};
  }
  plans++;return plans===1?{valid:false,report:{errors:[{code:'open_url_required'}]}}:{valid:true,step:{id:original.name,arguments:capability.steps[0].arguments}};
 }};
 vm.createContext(ctx);vm.runInContext(code,ctx);
 const result=await ctx.plannedStep(0);
 assert.equal(result.arguments.url,'${input.url}');assert.equal(repairs,1);assert.equal(plans,2);assert.equal(saves,2);
});
