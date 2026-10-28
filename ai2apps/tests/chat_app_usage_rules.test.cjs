const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');
const methods=source.slice(source.indexOf('    async loadAppUsageRule('),source.indexOf('    async setConversationMode('));
const make=()=>({...vm.runInNewContext('({'+methods+'})',{CHAT_PRINCIPAL_IS_CORE:true,window:{t:k=>k}}),appUsageRule:'manual',appUsageRuleRevision:0,appUsageRuleBusy:false,currentChatId:'ses_one'});
test('restore exact conversation rule and ignore an old conversation response',async()=>{
 const state=make();state.agentPlatformFetch=async()=>({mode:'ai',revision:2});await state.loadAppUsageRule('ses_one');assert.equal(state.appUsageRule,'ai');assert.equal(state.appUsageRuleRevision,2);
 let release;state.agentPlatformFetch=()=>new Promise(r=>release=r);const pending=state.loadAppUsageRule('ses_one');state.currentChatId='ses_two';release({mode:'always',revision:4});await pending;assert.equal(state.appUsageRule,'manual');
});
test('rule change uses dedicated revisioned API; new empty conversation is materialized first',async()=>{
 const state=make();state.currentChatId=null;state.currentModel='neutral';state.agentMode=true;const calls=[];
 state.startNewChat=async()=>{state.currentChatId='ses_new';state.appUsageRule='manual';state.appUsageRuleRevision=0;};
 state.agentPlatformFetch=async(url,options)=>{calls.push([url,JSON.parse(options.body)]);return {mode:'always',revision:1};};
 await state.setAppUsageRule('always');assert.equal(state.appUsageRule,'always');assert.equal(calls[0][0],'/sessions/ses_new/tool-approval-rule');assert.deepEqual(calls[0][1],{mode:'always',expected_revision:0});assert.equal(state.appUsageRuleBusy,false);
 state.agentPlatformFetch=async()=>{throw new Error('conflict')};await state.setAppUsageRule('ai');assert.equal(state.appUsageRule,'always');assert.equal(state.appUsageRuleError,'conflict');
});
test('new conversations reset to manual and all ten locales have rule labels',()=>{
 const newChat=source.slice(source.indexOf('    async startNewChat('),source.indexOf('    async loadChat('));assert.match(newChat,/this.appUsageRule = 'manual'/);
 for(const lang of ['zh','zh-TW','en','de','es','fr','ja','ko','pt-BR','ru']){
 const data=JSON.parse(fs.readFileSync(__dirname+'/../web/i18n/'+lang+'.json'));for(const key of ['title','manual','ai','always','tooltip','unavailable'])assert.ok(data['chat.app_usage.'+key]);}
});
