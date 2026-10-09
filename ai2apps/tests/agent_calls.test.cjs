const test = require('node:test'), assert = require('node:assert/strict');
const vm = require('node:vm'), fs = require('node:fs');
const src = fs.readFileSync(__dirname + '/../web/static/js/agent_mini.js', 'utf8');
const fn = src.slice(src.indexOf('    async function executeAgentCall('), src.indexOf('    async function saveEvidence('));

test('calling capability pauses for real assistance and resumes same durable run', async () => {
    const step = {operation:'agent.call',arguments:{agent_id:'login',capability:'site.ensure-login'}};
    const exploration = {status:'running'}, requests = [], checkpoints = [];
    let phase = 'paused';
    const context = {state:{exploration,context:{bidi_context:'tab-1'}}, Date,
        crypto:{randomUUID:()=> 'request-1'},
        client:async()=>({contextId:'tab-1',pageState:async()=>({url:'https://example.com'})}),
        persistExplorationCheckpoint:async()=>checkpoints.push(JSON.parse(JSON.stringify(exploration))),
        api:async(url,options)=>{
            requests.push({url,body:options && JSON.parse(options.body)});
            if(url==='/agent-calls/runs') return {run_id:'run-1',session_id:'session-1'};
            if(url.endsWith('/respond')) {phase='complete';return {};}
            return phase==='complete' ? {id:'run-1',status:'completed',output:{result:{outcome:'success'}}} :
                {id:'run-1',status:'waiting_input',interactions:[{id:'help-1',status:'pending',
                    prompt:'请扫描登录二维码',request:{control:'browser_user_assistance'}}]};
        }};
    vm.runInNewContext(fn+'\nglobalThis.call=executeAgentCall;',context);
    const first = await context.call(step);
    assert.equal(first.outcome,'needs_user');
    assert.equal(first.evidence.reason,'请扫描登录二维码');
    assert.equal(exploration.pendingCall.run_id,'run-1');
    assert.equal(checkpoints[0].pendingCall.request_key,'request-1');
    assert.equal(requests.filter(r=>r.url.endsWith('/respond')).length,0);
    // Simulate restoring the checkpoint in the reloaded Sidebar.
    context.state.exploration = JSON.parse(JSON.stringify(exploration));
    const second = await context.call(step);
    assert.equal(second.outcome,'success');
    assert.equal(requests.filter(r=>r.url==='/agent-calls/runs').length,1);
    assert.deepEqual(requests.find(r=>r.url.endsWith('/respond')).body.response,{continued:true});
    assert.equal(context.state.exploration.pendingCall,undefined);
});

test('preview never invokes child browser actions', async () => {
    const context = {state:{},api:()=>{throw Error('must not create run');}};
    vm.runInNewContext(fn+'\nglobalThis.call=executeAgentCall;',context);
    assert.equal((await context.call({operation:'agent.call'},true)).evidence.preview,true);
});

test('nested blocker cleanup does not reuse or clear the outer exploration call',async()=>{
 const outer={step:{arguments:{agent_id:'builtin:web:light-explore',capability:'web.light-explore'}},run_id:'outer'};
 const state={exploration:{status:'running',pendingCall:outer},context:{bidi_context:'page'}};let created;
 const context={state,Date,crypto:{randomUUID:()=> 'nested'},client:async()=>({contextId:'page',pageState:async()=>({url:'https://example.com'})}),persistExplorationCheckpoint:async()=>{},api:async(url,options)=>{
 if(url==='/agent-calls/runs'){created=JSON.parse(options.body);return {run_id:'cleanup'};}
 return {id:'cleanup',status:'completed',output:{result:{outcome:'false'}}};}};
 vm.runInNewContext(fn+'\nglobalThis.call=executeAgentCall;',context);
 const result=await context.call({operation:'agent.call',arguments:{agent_id:'builtin:web:clear-blockers',capability:'web.clear-blockers'}});
 assert.equal(result.outcome,'success');assert.equal(created.capability,'web.clear-blockers');assert.equal(state.exploration.pendingCall,outer);
 assert.equal(Object.keys(state.exploration.nestedCalls).length,0);
});
