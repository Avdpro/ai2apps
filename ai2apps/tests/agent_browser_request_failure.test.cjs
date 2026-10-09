const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const fn=source.slice(source.indexOf('    async function driveRun('),source.indexOf('    async function runAll('));
test('lost browsing context resolves pending browser request as failed instead of leaving waiting_input',async()=>{
 const state={run:{id:'run'}},responses=[];let polls=0;
 const pending={id:'run',status:'waiting_input',interactions:[{id:'interaction',status:'pending',request:{control:'browser_bidi_action',step:{id:'open'}}}]};
 const ctx={state,encodeURIComponent,crypto:{randomUUID:()=> 'response'},setContextPinned(){},notice(){},tr:()=>'',resolveInput:s=>s,
 renderRun:run=>{state.run=run},execute:async()=>{throw Error('no such frame')},returnToWorkspace:async()=>{},focusRunOutcome(){},
 api:async(path,options)=>{if(options){responses.push(JSON.parse(options.body));return {}; }return polls++===0?pending:{id:'run',status:'failed'};}};
 vm.runInNewContext(fn+'\nglobalThis.drive=driveRun',ctx);
 const result=await ctx.drive();assert.equal(result.status,'failed');assert.equal(responses.length,1);
 assert.equal(responses[0].response.outcome,'failed');assert.equal(responses[0].response.evidence.detail,'no such frame');
});
