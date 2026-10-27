const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/../web/templates/chat.html', 'utf8');
const creation = source.slice(source.indexOf('    async startNewChat('), source.indexOf('    async loadChat('));
// Run the real first-send routing up to parameter validation; stop before effects.
const routing = source.slice(source.indexOf('    async sendMessage() {'), source.indexOf('        try {\n            await this.persistDocuments', source.indexOf('    async sendMessage() {'))) + 'return {useAgent, sourceAgentKey}; },';
function setup(core = true) {
 const methods = vm.runInNewContext('({' + creation + routing + '})', {
  CHAT_PRINCIPAL_IS_CORE: core, chatAudioPipeline: null,
  window: {innerWidth: 1000},
 });
 const state = {
  ...methods, currentChatId: null, currentModel: 'chosen-model', agentMode: true,
  currentAgentKey: 'chosen-agent', inputMessage: 'hello', uploadImages: [], uploadDocuments: [],
  promptProfiles: [], chatSessions: {},
  cancelPersistModelSettingsTimer() {}, loadModels: async () => {},
  resolveGatewayModelId: id => id, resolvePreferredDefaultModel: () => 'default-model',
  defaultAgentKey: () => 'default-agent', ensureSessionModelSettings: async () => {},
  saveModelSettingsForModel() {}, getStreamSession: () => ({}), resetStreamSession() {},
  emptyStats: () => ({}), stopStatsPollingIfIdle() {}, saveCurrentChat() {}, $nextTick() {},
  hasPendingUploads: () => false, isCurrentChatStreaming: () => false,
  getChatSession(id) { return this.chatSessions[id]; },
  resolveAgentInvocation(prompt) { return {agentKey: this.currentAgentKey, prompt}; },
  cloneData: value => value, agentParametersFor: () => ({}), validateAgentParameters: () => null,
 };
 return state;
}
test('first send retains selected Agent, model and persisted mode before routing', async () => {
 const state = setup();
 const result = await state.sendMessage();
 assert.equal(result.useAgent, true);
 assert.equal(result.sourceAgentKey, 'chosen-agent');
 assert.equal(state.currentModel, 'chosen-model');
 assert.equal(state.chatSessions[state.currentChatId].agentMode, true);
 assert.equal(state.chatSessions[state.currentChatId].agentKey, 'chosen-agent');
});
test('first send in Chat remains direct model conversation', async () => {
 const state = setup(); state.agentMode = false;
 assert.equal((await state.sendMessage()).useAgent, false);
 assert.equal(state.chatSessions[state.currentChatId].agentMode, false);
});
test('explicit new conversation still starts with default selections', async () => {
 const state = setup(); await state.startNewChat();
 assert.equal(state.agentMode, true);
 assert.equal(state.currentAgentKey, 'default-agent');
 assert.equal(state.currentModel, 'default-model');
});
test('non-Core principal cannot enable Agent via first-send options', async () => {
 const state = setup(false);
 assert.equal((await state.sendMessage()).useAgent, false);
 assert.equal(state.chatSessions[state.currentChatId].agentMode, false);
});

test('Explicit Chat choice made while New Chat is loading survives completion', async () => {
 const state=setup();let release;state.loadModels=()=>new Promise(resolve=>release=resolve);
 const creating=state.startNewChat();assert.equal(state.agentMode,true);
 state.agentMode=false;state.currentAgentKey='user-selected-agent';release();await creating;
 assert.equal(state.agentMode,false);assert.equal(state.currentAgentKey,'user-selected-agent');
 assert.equal(state.chatSessions[state.currentChatId].agentMode,false);
 assert.equal(state.chatSessions[state.currentChatId].agentKey,'user-selected-agent');
});
