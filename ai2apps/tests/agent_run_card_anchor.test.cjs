const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');
const start=source.indexOf('    agentRunForMessage(message) {'),end=source.indexOf('    agentRunIsActive(',start);
const methods=vm.runInNewContext('({'+source.slice(start,end)+'})');
function view(messages){return {...methods,messages,agentRuns:{r:{id:'r',status:'completed'},s:{id:'s',status:'running'}}};}
test('duplicate optimistic and restored inputs show only the later Run card',()=>{
 const early={id:'local',role:'user',_agentRunId:'r'},late={id:'server',role:'user',agent_run_id:'r'};
 const app=view([early,late,{role:'assistant',agent_run_id:'r'}]);assert.equal(app.agentRunForMessage(early),null);assert.equal(app.agentRunForMessage(late),app.agentRuns.r);
});
test('distinct Runs with identical text retain independent cards',()=>{
 const first={role:'user',content:'same request',agent_run_id:'r'},second={role:'user',content:'same request',agent_run_id:'s'};
 const app=view([first,second]);assert.equal(app.agentRunForMessage(first),app.agentRuns.r);assert.equal(app.agentRunForMessage(second),app.agentRuns.s);
});
test('active sole anchor remains visible and absent message IDs do not merge anchors',()=>{
 const early={role:'user',agent_run_id:'s'},late={role:'user',agent_run_id:'s'};const app=view([early]);assert.equal(app.agentRunForMessage(early),app.agentRuns.s);
 app.messages.push(late);assert.equal(app.agentRunForMessage(early),null);assert.equal(app.agentRunForMessage(late),app.agentRuns.s);assert.equal(app.agentRunForMessage({role:'user'}),null);
});
