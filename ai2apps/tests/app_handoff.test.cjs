const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const shell=fs.readFileSync(__dirname+'/../web/static/js/shell.js','utf8');
const start=shell.indexOf("} else if (message.type === 'ai2apps.shell.open-handoff') {");
const block=shell.slice(start+'} else if (message.type === \'ai2apps.shell.open-handoff\') {'.length,shell.indexOf("            } else if (message.type",start+1));
function harness(handoff,message){
 const calls=[];const context={message,bridgeTarget:{source:'original-frame'},encodeURIComponent,
 jsonRequest:async(url,method)=>{calls.push({url,method});return handoff;},
 currentId:'ai2apps.chat',currentInstanceId:'chat-1',appInteractionIntents:{},
 launch:async(app,options)=>{calls.push({app,options});context.currentId=app;context.currentInstanceId=options.instanceId||'intel-1';},
 saveInteractionIntent:(instance,intent)=>calls.push({instance,intent}),sendHostContext:()=>calls.push('context'),
 respondToBridgeTarget:(target,ok,result)=>calls.push({target,ok,result})};
 vm.runInNewContext('globalThis.run=async()=>{'+block+'}',context);return {context,calls};
}
const handoff={run_id:'run-1',interaction_id:'help-1',status:'pending',target:{app_id:'ai2apps.intelligence',mini_app_id:null},origin:{app_id:'ai2apps.chat',instance_id:'chat-1',session_id:'session-1'}};
test('open forwards server-selected target; reply returns to requesting frame',async()=>{
 const {context,calls}=harness(handoff,{runId:'run-1',interactionId:'help-1'});await context.run();
 assert.equal(calls[1].app,'ai2apps.intelligence');assert.equal(calls[2].intent.returning,false);
 assert.equal(calls.at(-1).target.source,'original-frame');
});
test('return uses original instance and session, not model-supplied destination',async()=>{
 const {context,calls}=harness(handoff,{runId:'run-1',interactionId:'help-1',returning:true,sessionId:'wrong'});await context.run();
 assert.equal(calls[1].options.instanceId,'chat-1');assert.equal(calls[2].intent.sessionId,'session-1');
});
test('resolved interaction cannot reopen target or launch again',async()=>{
 const {context,calls}=harness({...handoff,status:'submitted'},{runId:'run-1',interactionId:'help-1'});
 await assert.rejects(context.run(),/no longer pending/);assert.equal(calls.length,1);
});
test('Mini-App destination retains host and registered Mini-App identity',async()=>{
 const {context,calls}=harness({...handoff,target:{app_id:'ai2apps.voice-studio',mini_app_id:'test.voice-mini'}},{runId:'run-1',interactionId:'help-1'});await context.run();
 assert.equal(calls[1].app,'ai2apps.voice-studio');assert.equal(calls[2].intent.miniAppId,'test.voice-mini');
});
const chat=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');
const listener=chat.slice(chat.indexOf("window.addEventListener('ai2apps:host-context', async event => {"),chat.indexOf('                const outerHash',chat.indexOf('            setupMiniEntryBridge()')));
test('Chat restores canonical origin session and observes resumed Run',async()=>{
 let callback;const calls=[];const state={agentPlatformFetch:async()=>handoff,loadChat:async id=>calls.push(id),refreshAgentRun:async id=>calls.push(id)};
 const ctx={window:{ai2appsShell:{acknowledgeHandoff:async id=>calls.push('ack:'+id)},addEventListener:(name,fn)=>{callback=fn;}},encodeURIComponent,console,state};
 vm.runInNewContext('(function(){'+listener+'}).call(state)',ctx);
 await callback({detail:{appInteraction:{returning:true,runId:'run-1',interactionId:'help-1',sessionId:'wrong'}}});
 assert.deepEqual(calls,['session-1','run-1','ack:help-1']);
 await callback({detail:{appInteraction:{returning:true,runId:'run-1',interactionId:'help-1'}}});assert.equal(calls.length,6);
});
const startRun=chat.slice(chat.indexOf('    async startAgentRun({'),chat.indexOf('    async finalizeAgentRun(run)'));
test('new Agent run attaches to reactive message and persists before streaming',async()=>{
 const original={id:'m1',content:'Create channel'},reactive={...original};const session={messages:[reactive],model:'test'};const calls=[];
 const ctx={currentChatId:'s1',agentRuns:{},retrieveChatKnowledge:async()=>null,resolveGatewayModelId:m=>m,agentModelOptions:()=>({}),cloneData:x=>x,agentPlatformFetch:async()=>({id:'r1'}),getChatSession:()=>session,normalizeAgentRun:x=>x,saveCurrentChat:()=>calls.push('save'),rememberActiveAgentRuns:()=>{},connectAgentRunStream:()=>calls.push('stream')};
 vm.runInNewContext('Object.assign(ctx, {'+startRun+'});',{ctx});
 await ctx.startAgentRun({chatId:'s1',userMessage:original,model:'test',invocationPrompt:'Create channel'});
 assert.equal(reactive.agent_run_id,'r1');assert.equal(ctx.messages[0].agent_run_id,'r1');assert.deepEqual(calls,['save','stream']);
});

test('length-limited Agent output is visibly incomplete in both languages',()=>{
 const body=chat.slice(chat.indexOf('    agentStatusView(run) {'),chat.indexOf('    agentStatusText(view) {'));
 for(const lang of ['zh-CN','en']) {
  const ctx={agentStatusRenderers:{resolve:()=>({text:'Completed'})},document:{documentElement:{lang}}};
  vm.runInNewContext('globalThis.view=({'+body+'}).agentStatusView',ctx);
  const result=ctx.view({status:'completed',output:{finish_reason:'length'}});
  assert.equal(result.icon,'warning');assert.equal(result.tone,'warning');
  assert.match(result.text,lang==='en'?/incomplete/:/未完成/);
  assert.equal(ctx.view({status:'completed',output:{finish_reason:'stop'}}).icon,'check');
 }
});
