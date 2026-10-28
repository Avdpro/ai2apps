const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const read=f=>fs.readFileSync(path.join(__dirname,'..',f),'utf8');
test('Chat composer omits budget editing and legacy local override; server owns round defaults',()=>{
 const source=read('web/templates/chat.html');
 assert.ok(!source.includes('Agent token budget'));
 assert.ok(!source.includes('chat-agent-budget'));
 assert.ok(!source.includes('ai2apps.agentTokenBudget'));
 assert.ok(!source.includes('agentModelTokenBudget'));
 assert.ok(source.includes("body: JSON.stringify({ agent: agentKey || 'ai2apps.general-agent', input })"));
 assert.ok(!read('web/templates/mobile_chat_content.html').includes('Agent token budget'));
 assert.ok(source.includes("window.t('chat.mode.chat_tooltip')"));
 assert.ok(source.includes("window.t('chat.mode.agent_tooltip')"));
});
