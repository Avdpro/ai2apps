const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
async function initialize(runs,options){
 const rendered=[];
 const state={presentations:new Map([['old',{}]]),resultMode:'ai',run:{id:'old'},client:null,context:{}};
 const context={state,notice(){},renderRun:run=>{state.run=run;rendered.push(run);},api:async path=>path.startsWith('/agent-draft-runs')?{items:runs}:{items:[]},refreshDrafts:async()=>{},loadBuilderModels:async()=>{},$:()=>({replaceChildren(){}}),Option:function(){},tr:key=>key,client:async()=>({pageState:async()=>({})}),driveRun(){},URL,location:{href:'http://localhost/admin/agent-mini'}};
 vm.runInNewContext(source.slice(source.indexOf('    async function initialize('),source.indexOf('    function contextKey('))+'\nglobalThis.initialize=initialize;',context);
 await context.initialize(options);return {state,rendered};
}
test('explicit refresh clears prior results and does not restore completed history',async()=>{
 const {state,rendered}=await initialize([{id:'old',status:'completed'}],{restoreCompleted:false});
 assert.equal(state.run,null);assert.deepEqual(rendered,[null]);assert.equal(state.presentations.size,0);assert.equal(state.resultMode,'json');
});
test('initial mount still restores previous results and refresh retains active run controls',async()=>{
 const completed={id:'old',status:'completed'};assert.equal((await initialize([completed])).state.run,completed);
 const active={id:'active',status:'waiting_input'};assert.equal((await initialize([completed,active],{restoreCompleted:false})).state.run,active);
});
