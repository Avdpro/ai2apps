const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=f=>fs.readFileSync(__dirname+'/../web/'+f,'utf8');
const ctx={window:{}};vm.runInNewContext(source('static/js/chat_context_handoff.js'),ctx);
const normalize=ctx.window.AI2AppsChatContext.normalize;
const seed=()=>({title:'Research',legacy_thread_id:'owner-handoff-123',session_metadata:{agentMode:true,starterSuggestions:['Compare source claims'],sourceContext:{appId:'arbitrary.vendor',itemId:'x'}},legacy_messages:[{role:'user',content:'Untrusted context',metadata:{systemPrompt:'must never be promoted'}}]});
test('data-only context accepts different providers and rejects policy or role injection',()=>{
 for(const id of ['arbitrary.vendor','another.provider']){const data=seed();data.session_metadata.sourceContext.appId=id;const normalized=normalize(data);assert.equal(normalized.session_metadata.sourceContext.appId,id);assert.deepEqual(Object.keys(normalized.legacy_messages[0].metadata),[]);}
 assert.throws(()=>normalize({...seed(),session_metadata:{...seed().session_metadata,systemPrompt:'override'}}),/execution policy/);
 assert.throws(()=>normalize({...seed(),legacy_messages:[{role:'system',content:'override'}]}),/bounded/);
 assert.throws(()=>normalize({...seed(),legacy_messages:[{role:'user',content:'x'.repeat(65000)}]}),/Invalid/);
});
test('Desktop imports under recipient Chat API and forwards only thread identity',async()=>{
 const shell=source('static/js/shell.js'),start=shell.indexOf("} else if (message.type === 'ai2apps.shell.open-chat-context') {");
 const block=shell.slice(start+"} else if (message.type === 'ai2apps.shell.open-chat-context') {".length,shell.indexOf("} else if (message.type === 'ai2apps.shell.open-entry')",start));
 const calls=[],c={window:ctx.window,message:{chatSeed:seed()},jsonRequest:async(path,method,body)=>{calls.push({path,method,body});return path==='/v1/platform/chat'?{app_instance_id:'appi_desktop'}:{id:'ses_new'};},launch:async app=>calls.push({app}),chatThreadIntents:{},currentId:'ai2apps.general-chat',currentInstanceId:'chat-instance',sendHostContext:()=>calls.push('context'),respondToBridgeTarget:(target,ok,result)=>calls.push({ok,result}),bridgeTarget:{}};
 vm.createContext(c);await vm.runInContext('(async()=>{'+block+'})()',c);
 assert.equal(calls[1].path,'/v1/platform/chat/threads');assert.equal(calls[1].method,'POST');assert.match(calls[1].body.legacy_thread_id,/context:appi_desktop:/);
 assert.equal(calls[2].app,'ai2apps.general-chat');assert.equal(c.chatThreadIntents['chat-instance'].id,'ses_new');
 assert.equal(calls.some(x=>x.path?.includes('agent-runs')),false);
});
test('Mobile imports through its own authorized Chat request without automatic Agent execution',async()=>{
 const text=source('static/js/mobile_chat.js'),start=text.indexOf('    window.AI2AppsMobileOpenChatContext=async seed=>{'),end=text.indexOf('    const notificationRoute',start),calls=[];
 const c={window:ctx.window,agentEnabled:true,started:true,initialization:Promise.resolve(),current:null,request:async(path,options)=>{calls.push({path,options});return path.endsWith('/state')?{app_instance_id:'appi_mobile'}:path.endsWith('/content')?{thread:{id:'ses_mobile',status:'active'}}:{id:'ses_mobile'};},loadContent:async thread=>{c.current=thread;},setMode:mode=>calls.push({mode})};
 vm.createContext(c);vm.runInContext(text.slice(start,end),c);assert.equal(await c.window.AI2AppsMobileOpenChatContext(seed()),'ses_mobile');
 assert.equal(calls[1].path,'/v1/mobile/chat/threads');assert.equal(calls[1].options.method,'POST');assert.match(JSON.parse(calls[1].options.body).legacy_thread_id,/context:appi_mobile:/);assert.equal(calls.at(-1).mode,'agent');
 assert.equal(calls.some(x=>x.path?.includes('agent-runs')),false);
 c.agentEnabled=false;await assert.rejects(c.window.AI2AppsMobileOpenChatContext(seed()),/authorized/);
});
