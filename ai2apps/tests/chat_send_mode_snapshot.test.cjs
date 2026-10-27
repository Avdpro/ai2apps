const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');
test('first send preserves selected Agent mode across asynchronous thread hydration',async()=>{
 const start=source.indexOf('    async sendMessage() {'),end=source.indexOf('        const invocation = useAgent',start);
 const ctx={CHAT_PRINCIPAL_IS_CORE:true};vm.runInNewContext('send=({'+source.slice(start,end)+'return {useAgent, sourceModel, sourceSystemPrompt};}}).sendMessage',ctx);
 const session={};let received;
 const app={agentMode:true,currentAgentKey:'chosen-agent',currentModel:'chosen-model',systemPrompt:'chosen-prompt',inputMessage:'Make a group photo',uploadImages:[],uploadDocuments:[],hasPendingUploads:()=>false,isCurrentChatStreaming:()=>false,
 startNewChat:async function(options){received=options;this.currentChatId='created';this.agentMode=false;this.currentAgentKey='old-agent';this.currentModel='old-model';this.systemPrompt='old-prompt';},getChatSession:()=>session};
 const result=await ctx.send.call(app);assert.equal(result.useAgent,true);assert.equal(app.agentMode,true);assert.equal(app.currentAgentKey,'chosen-agent');assert.equal(result.sourceModel,'chosen-model');assert.equal(result.sourceSystemPrompt,'chosen-prompt');assert.equal(session.agentMode,true);assert.equal(received.initialAgentMode,true);
});
