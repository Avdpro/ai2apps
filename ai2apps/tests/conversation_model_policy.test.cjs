const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const policy = require('../web/static/js/conversation_model_policy.js');
const source = fs.readFileSync(__dirname + '/../web/templates/chat.html', 'utf8');
const capable = id => ({id,model_type:'llm',capabilities:['work_standard','tool_calling_reliable']});
test('automatic Agent choice requires explicit complexity AND reliable calling declarations', () => {
 const models=[{id:'famous-powerful-model',model_type:'llm'},
  {id:'light',capabilities:['work_simple','tool_calling_reliable']},
  {id:'untested',capabilities:['work_complex']},capable('arbitrary-qualified')];
 assert.equal(policy.agentDefault(models,'light',['untested']), 'light');
 assert.equal(policy.agentDefault(models.slice(0,3)),null);
 assert.equal(policy.agentDefault([...models,capable('preferred')],'preferred'),'preferred');
 for (const bad of [{...capable('a'),is_hidden:true},{...capable('b'),checkpoint_ready:false},
  {id:'c',capabilities:{work_standard:true,tool_calling_reliable:false}}]) assert.equal(policy.agentEligible(bad),false);
 assert.equal(policy.agentEligible({id:'d',capabilities:{work_complex:true,tool_calling_reliable:true}}),true);
});
test('account API default is the normal Agent default without a capability-name guess', () => {
 const models=[{id:'cloud/ai2apps/arbitrary',model_type:'llm'},capable('other-qualified')];
 assert.equal(policy.agentDefault(models,'',[],models[0].id),models[0].id);
 assert.equal(policy.agentDefault(models,'',[],'cloud/ai2apps/unavailable'),null);
 assert.equal(policy.agentDefault(models,'other-qualified',[],models[0].id),'other-qualified');
});
const mode = source.slice(source.indexOf('    async setConversationMode('), source.indexOf('    focusComposerFromSurface('));
function setup() {
 const session={model:'light',messages:[]};
 const methods=vm.runInNewContext('({' + mode + '})',{CHAT_PRINCIPAL_IS_CORE:true,document:{documentElement:{lang:"zh"}},AI2AppsConversationModelPolicy:policy});
 const state={...methods,agentMode:false,currentChatId:'s',currentModel:'light',modelSelectionExplicit:false,
  preferredChatModel:'light',preferredAgentModel:'qualified',availableModels:[{id:'light'},capable('qualified')],
  getChatSession:()=>session,resolvePreferredDefaultModel:id=>id,
  async selectModel(id,{explicit}) {this.currentModel=id;this.modelSelectionExplicit=explicit;session.model=id;session.modelSelectionExplicit=explicit;},
  saveCurrentChat(){},session};
 return state;
}
test('switching modes uses separate automatic defaults and survives switching back',async()=>{
 const state=setup();await state.setConversationMode('agent');
 assert.equal(state.currentModel,'qualified');assert.equal(state.session.agentMode,true);
 await state.setConversationMode('chat');assert.equal(state.currentModel,'light');
});
test('explicit lightweight choice remains selected and receives a notice',async()=>{
 const state=setup();state.modelSelectionExplicit=true;await state.setConversationMode('agent');
 assert.equal(state.currentModel,'light');assert.match(state.modelSelectionNotice,/明确选择/);
 await state.setConversationMode('chat');assert.equal(state.currentModel,'light');
});
test('no eligible default leaves Agent unselected instead of using lightweight Chat default',async()=>{
 const state=setup();state.preferredAgentModel=null;await state.setConversationMode('agent');
 assert.equal(state.currentModel,null);assert.match(state.modelSelectionNotice,/默认模型不可用/);
});
test('selection provenance is serialized to backend metadata, including legacy choices',()=>{
 const method=source.slice(source.indexOf('    backendSessionMetadata('),source.indexOf('    backendMessagePayload('));
 const state=vm.runInNewContext('({' + method + '})');state.cloneData=x=>x;state.getChatSession=()=>null;
 assert.equal(state.backendSessionMetadata({model:'explicit'}, {model:'explicit',modelSelectionExplicit:true}).modelSelectionExplicit,true);
 assert.equal(state.backendSessionMetadata({model:'automatic'}, {model:'automatic',modelSelectionExplicit:false}).modelSelectionExplicit,false);
 assert.equal(state.backendSessionMetadata({model:'legacy'}).modelSelectionExplicit,true);
});
const creation=source.slice(source.indexOf('    async startNewChat('), source.indexOf('    async loadChat('));
test('new Agent conversation adopts Agent default; explicit choice during hydration wins',async()=>{
 const methods=vm.runInNewContext('({' + creation + '})',{CHAT_PRINCIPAL_IS_CORE:true,chatAudioPipeline:null,window:{innerWidth:1000}});
 const state={...setup(),...methods,_modelChoiceRevision:0,chatSessions:{},currentChatId:null,promptProfiles:[],
  defaultAgentKey:()=> 'agent',cancelPersistModelSettingsTimer(){},loadModels:async()=>{},resolveGatewayModelId:id=>id,
  ensureSessionModelSettings:async()=>{},saveModelSettingsForModel(){},getStreamSession:()=>({}),resetStreamSession(){},
  emptyStats:()=>({}),stopStatsPollingIfIdle(){},$nextTick(){}};
 await state.startNewChat({initialAgentMode:true});assert.equal(state.currentModel,'qualified');
 assert.equal(state.chatSessions[state.currentChatId].modelSelectionExplicit,false);
 state.currentChatId=null;await state.startNewChat();assert.equal(state.agentMode,true);assert.equal(state.currentModel,'qualified');
 state.currentChatId=null;await state.startNewChat({initialAgentMode:false});assert.equal(state.agentMode,false);
 state.currentChatId=null;state.terminalAssistantMode=true;await state.startNewChat();assert.equal(state.agentMode,false);
 state.terminalAssistantMode=false;
 state.currentChatId=null;let release;state.loadModels=()=>new Promise(resolve=>release=resolve);
 const pending=state.startNewChat();state.currentModel='explicit';state.modelSelectionExplicit=true;state._modelChoiceRevision++;release();await pending;
 assert.equal(state.currentModel,'explicit');assert.equal(state.chatSessions[state.currentChatId].modelSelectionExplicit,true);
});

test('manual Agent options rank declarations first and preserve unknown explicit preferences',()=>{
 const models=[{id:'famous',model_type:'llm'},capable('qualified'),{id:'partial',model_type:'llm',capabilities:{tool_calling_reliable:false}},
 {id:'image',model_type:'image_generation'},{...capable('hidden'),is_hidden:true},{id:'missing',model_type:'llm',checkpoint_ready:false}];
 assert.deepEqual(policy.agentOptions(models).map(m=>m.id),['qualified','partial','famous']);
 assert.equal(policy.agentDefault(models,'famous'), 'famous');
 assert.equal(policy.agentDefault(models,'gone'), 'qualified');
 assert.equal(policy.agentDefault([models[0]],'', ['famous']),null);
 assert.equal(policy.agentDeclaration(models[0]),'undeclared');
 assert.equal(policy.agentDeclaration(models[2]),'declared_insufficient');
});
test('settings explains missing automatic candidates and manual unverified choices',()=>{
 const dashboard=fs.readFileSync(__dirname+'/../web/static/js/dashboard.js','utf8');
 const methods=dashboard.slice(dashboard.indexOf('            agentModelLabel(model)'),dashboard.indexOf('            defaultModelLabel(model)'));
 const state=vm.runInNewContext('({'+methods+'})',{AI2AppsConversationModelPolicy:policy,window:{t:key=>key}});
 state.defaultModels={work_agent:''};state.defaultModelLabel=m=>m.id;
 state.defaultModelOptions=()=>[];assert.match(state.agentModelNotice(),/no_models$/);
 state.defaultModelOptions=()=>[{id:'unknown',model_type:'llm'}];assert.match(state.agentModelNotice(),/no_qualified$/);
 state.cloudDefaultPolicy={apiDefault:{modelId:'arbitrary'}};
 assert.match(state.agentModelNotice(),/api_unavailable$/);
 state.defaultModelOptions=()=>[{id:'cloud/ai2apps/arbitrary',model_type:'llm'}];
 assert.match(state.agentModelNotice(),/api_unverified$/);
 state.defaultModelOptions=()=>[{id:'cloud/arbitrary',model_type:'llm'}];
 assert.match(state.agentModelNotice(),/api_unverified$/);
 state.defaultModelOptions=()=>[capable('cloud/ai2apps/arbitrary')];
 assert.equal(state.agentModelNotice(),'');
 state.cloudDefaultPolicy={};
 state.defaultModelOptions=()=>[{id:'unknown',model_type:'llm'}];
 state.defaultModels.work_agent='unknown';assert.match(state.agentModelNotice(),/manual_notice$/);
 assert.match(state.agentModelLabel({id:'unknown',model_type:'llm'}),/undeclared$/);
 state.defaultModelOptions=()=>[capable('qualified')];state.defaultModels.work_agent='qualified';assert.equal(state.agentModelNotice(),'');
});
test('standalone System Apps load the shared model policy before dashboard code',()=>{
 for(const template of ['system_apps/base.html','dashboard.html']){
 const html=fs.readFileSync(__dirname+'/../web/templates/'+template,'utf8');
 assert.ok(html.indexOf('js/conversation_model_policy.js')>=0);
 assert.ok(html.indexOf('js/conversation_model_policy.js')<html.indexOf('js/dashboard.js'));
 }
});

test('missing and unsupported requirements are distinct, including partial task declarations',()=>{
 for(const id of ['famous-powerful','tiny','arbitrary-provider/model']) {
  const model={id,capabilities:{workStandard:true}};
  assert.deepEqual(policy.agentSummary(model).missing,['tool_calling_reliable']);
  assert.deepEqual(policy.agentSummary(model).unsupported,[]);
  assert.match(policy.agentNotice(model),/尚未声明：可靠工具调用/);
  assert.doesNotMatch(policy.agentNotice(model),/明确不支持/);
 }
 const noTasks={capabilities:{work_standard:false,work_complex:false,tool_calling_reliable:true}};
 assert.deepEqual(policy.agentSummary(noTasks).unsupported,['task_complexity']);
 assert.deepEqual(policy.agentSummary(noTasks).missing,[]);
 assert.match(policy.agentNotice(noTasks),/明确不支持：中等或复杂任务能力/);
 const partial={capabilities:{work_standard:false,tool_calling_reliable:true}};
 assert.deepEqual(policy.agentSummary(partial).missing,['task_complexity']);
 assert.deepEqual(policy.agentSummary(partial).unsupported,[]);
 assert.equal(policy.agentEligible({capabilities:{workComplex:true,toolCallingReliable:true}}),true);
 assert.equal(policy.agentEligible({capabilities:{work_complex:'true',tool_calling_reliable:'yes'}}),false);
 assert.match(policy.agentNotice({capabilities:{tool_calling_reliable:false}}),/明确不支持：可靠工具调用.*尚未声明：中等或复杂任务能力/);
});

test('Chat projection and API Default alias preserve server false and unknown declarations',()=>{
 const start=source.indexOf('                        id: gatewayId, // stable id used for API calls');
 const projection=source.slice(start,source.indexOf('                    };',start));
 const map=vm.runInNewContext('(adminModel,m,gatewayId)=>({'+projection+'})',{favoriteIds:new Set(),modelTypeMap:{}});
 const declared={status:'declared_insufficient',declarations:{work_standard:true,work_complex:null,tool_calling_reliable:false}};
 const model=map({capabilities:['work_standard'],agent_capability_declaration:declared},{},'cloud/arbitrary');
 assert.equal(model.agent_capability_declaration,declared);
 const startAlias=source.indexOf('            registerCloudDefaultModel(');
 const method=source.slice(startAlias,source.indexOf('            resolvePreferredDefaultModel(',startAlias));
 const state=vm.runInNewContext('({'+method+'})');state.dedupeAvailableModels=x=>x;
 const alias=state.registerCloudDefaultModel({modelId:'arbitrary',displayName:'Neutral'},[model]).find(x=>x.id==='cloud/ai2apps/arbitrary');
 assert.equal(alias.agent_capability_declaration,declared);
 assert.deepEqual(policy.agentSummary(alias).unsupported,['tool_calling_reliable']);
 assert.equal(policy.agentDefault([alias],'',[],alias.id),alias.id);
 assert.match(policy.agentNotice(alias,{language:'en'}),/Explicitly unsupported: reliable tool calling/);
 const unknown=map({capabilities:[],agent_capability_declaration:{declarations:{work_standard:null,work_complex:null,tool_calling_reliable:null}}},{},'cloud/unknown');
 assert.equal(policy.agentDeclaration(unknown),'undeclared');
 assert.match(policy.agentNotice(unknown),/尚未声明/);
});

test('missing declarations stay out of the composer; unsupported/unavailable remains visible',()=>{
 const start=source.indexOf('            showModelSelectionWarning()');
 const method=source.slice(start,source.indexOf('            registerCloudDefaultModel(',start));
 const state=vm.runInNewContext('({'+method+'})',{AI2AppsConversationModelPolicy:policy});
 Object.assign(state,{agentMode:true,modelSelectionNotice:'details',currentModel:'neutral',availableModels:[{id:'neutral',capabilities:{}}]});
 assert.equal(state.showModelSelectionWarning(),false);
 state.availableModels[0].capabilities={tool_calling_reliable:false};
 assert.equal(state.showModelSelectionWarning(),true);
 state.agentMode=false;assert.equal(state.showModelSelectionWarning(),false);
 state.agentMode=true;state.currentModel=null;assert.equal(state.showModelSelectionWarning(),true);
 assert.match(source,/<details x-show="agentMode && currentModel && modelSelectionNotice && !showModelSelectionWarning\(\)"/);
 assert.match(source,/<p x-show="showModelSelectionWarning\(\)"/);
});
