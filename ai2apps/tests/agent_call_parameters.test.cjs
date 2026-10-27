const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');
const code=source.slice(source.indexOf('    agentToolCallDetails(run) {'),source.indexOf('    agentRunDetails(run) {'));
const helper=vm.runInNewContext('({'+code+'})');
test('shows each actual Tool input in order, including failed calls',()=>{
 const run={steps:[{kind:'model'},{id:'1',kind:'tool',tool_name:'image.edit',status:'failed',input:{artifact_id:'art_1',prompt:'make blue'}},{id:'2',kind:'tool',tool_name:'image.edit',status:'running',input:{prompt:'retry'}}]};
 const calls=helper.agentToolCallDetails(run);
 assert.equal(calls.length,2);assert.equal(calls[0].status,'failed');
 assert.equal(JSON.parse(calls[0].parameters).artifact_id,'art_1');
 assert.equal(calls[1].id,'2');
});
test('bounds large inputs, summarizes binary data and does not change stored input',()=>{
 const input={prompt:'x'.repeat(20000),image:'data:image/png;base64,'+'A'.repeat(10000),api_key:'private',nested:{password:'private'}};
 const call=helper.agentToolCallDetails({steps:[{kind:'tool',tool_name:'test',input}]})[0];
 assert.ok(call.parameters.length<10000);assert.ok(call.parameters.includes('20000 chars'));
 assert.ok(call.parameters.includes('[Base64:'));assert.ok(!call.parameters.includes('private'));
 assert.equal(input.prompt.length,20000);assert.equal(input.api_key,'private');
 assert.ok(source.includes('x-text="call.parameters"'));
});
test('actual execution metadata is shown only from durable Tool results',()=>{
 const calls=helper.agentToolCallDetails({steps:[{kind:'tool',tool_name:'image.edit',input:{provider:'requested'},output:{provider:'actual',mini_app_id:'mini.edit',model:'cloud/model',studio_job_id:'job',studio_run_id:'run',provider_attempts:[{provider:'first',status:'unavailable'},{provider:'actual',status:'succeeded'}]}},{kind:'tool',tool_name:'image.edit',input:{provider:'requested'}}]});
 assert.equal(calls[0].execution.find(x=>x.key==='provider').value,'actual');
 assert.equal(calls[0].execution.find(x=>x.key==='mini_app_id').value,'mini.edit');
 assert.ok(calls[0].execution.find(x=>x.key==='provider_attempts').value.includes('first · unavailable → actual · succeeded'));
 assert.equal(calls[1].execution.length,0);
});
test('stale translation catalog uses readable Chinese labels',()=>{
 const h=vm.runInNewContext('({'+code+'})',{document:{documentElement:{lang:'zh'}},navigator:{language:'zh'}});
 h.t=key=>key;
 assert.equal(h.agentCallLabel('parameters'),'调用参数');
 assert.equal(h.agentCallLabel('model'),'实际模型');
});
test('App and Mini-App use their own declared icons and share a row with names',()=>{
 helper.agentCallCatalog={apps:[{id:'studio',name:'创意画坊',icon:'palette'}],providers:[{id:'edit',app_id:'studio'}],minis:[{id:'mini.edit',name:'修图',icon:'scan-search'}]};
 const call=helper.agentToolCallDetails({steps:[{kind:'tool',tool_name:'image.edit',output:{provider:'edit',mini_app_id:'mini.edit'}}]})[0];
 assert.equal(call.owners[0].icon,'palette');assert.equal(call.owners[0].name,'创意画坊');
 assert.equal(call.owners[1].icon,'scan-search');assert.equal(call.owners[1].name,'修图');
 assert.ok(source.includes('x-html="agentCallIcon(owner.icon)"'));
});
test('collapsed status uses actual running provider identity and latest completed call',()=>{
 helper.agentCallCatalog={apps:[{id:'studio',name:'Studio',icon:'palette'}],providers:[{id:'edit',app_id:'studio'}],minis:[{id:'mini.edit',name:'Edit',icon:'scan-search'}]};
 const run={status_line:{content:{provider:'edit',app_id:'studio',mini_app_id:'mini.edit'}}};
 assert.equal(helper.agentRunOwners(run)[1].icon,'scan-search');
 assert.equal(helper.agentRunOwners({steps:[{kind:'tool',tool_name:'image.edit',output:run.status_line.content}]}).length,2);
 assert.equal(helper.agentRunOwners({steps:[]}).length,0);
});
test('whole row toggles details and controls stop propagation',()=>{
 helper.agentRunHasDetails=()=>true; helper.loadAgentCallIcons=()=>{};
 const run={};helper.toggleAgentRunDetails(run);assert.equal(run.expanded,true);
 helper.toggleAgentRunDetails(run);assert.equal(run.expanded,false);
 assert.ok(source.includes('@click="toggleAgentRunDetails(run)"'));
 for(const action of ['pause','resume','cancel']) assert.ok(source.includes('@click.stop="'+action+'AgentRun(run.id)"'));
});
test('failed calls show recorded App Mini-App identity stage reason and parameters',()=>{
 helper.agentCallCatalog={apps:[{id:'studio',name:'Studio',icon:'palette'}],providers:[],minis:[{id:'mini',name:'Group photo',icon:'users'}]};
 const call=helper.agentToolCallDetails({steps:[{kind:'tool',tool_name:'image.group_photo',status:'failed',input:{person_artifact_ids:['a','b']},error:{message:'Reference roles conflict',details:{provider:'actual',app_id:'studio',mini_app_id:'mini',phase:'prepare',provider_attempts:[{provider:'actual',status:'incompatible',reason:'Reference roles conflict'}]}}}]})[0];
 assert.equal(call.owners.length,2);assert.equal(call.owners[1].icon,'users');
 assert.equal(call.execution.find(x=>x.key==='phase').value,'prepare');
 assert.ok(call.execution.find(x=>x.key==='provider_attempts').value.includes('Reference roles conflict'));
 assert.equal(JSON.parse(call.parameters).person_artifact_ids[1],'b');
 assert.equal(call.error,'Reference roles conflict');
});
test('summary retains and deduplicates all recorded owners after infrastructure calls',()=>{
 helper.agentCallCatalog={apps:[{id:'app.alpha',name:'Alpha',icon:'list-checks'},{id:'app.beta',name:'Beta',icon:'palette'}],providers:[],minis:[]};
 const run={steps:[{kind:'tool',tool_name:'arbitrary.lookup',output:{app_id:'app.alpha'}},{kind:'tool',tool_name:'arbitrary.count',output:{app_id:'app.alpha'}},{kind:'tool',tool_name:'another.render',output:{app_id:'app.beta'}},{kind:'tool',tool_name:'agent.read_tool_result',output:{text:'stored result'}}],status_line:{content:{provider:'selected',app_id:'app.beta'}}};
 assert.equal(helper.agentRunOwners(run).map(x=>x.id).join(','),'app.alpha,app.beta');
 assert.equal(helper.agentRunOwners({...run,status_line:{content:{}}}).map(x=>x.id).join(','),'app.alpha,app.beta');
 assert.equal(helper.agentRunOwners({steps:[{kind:'tool',tool_name:'arbitrary.lookup',input:{app_id:'app.alpha'}}]}).length,0);
});
