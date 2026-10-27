const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),source=fs.readFileSync(root+'/web/templates/chat.html','utf8');
const css=source.match(/<style>([\s\S]*?)<\/style>/)[1];
const assistant=source.split('<!-- Assistant Message -->')[1].split('<!-- Streaming Message -->')[0];
const header=assistant.slice(assistant.indexOf('<div class="message-header">'),assistant.lastIndexOf('</template>'));
test('Desktop reply retains all existing action and Thinking bindings below content',()=>{
 assert.ok(assistant.indexOf('class="message-header"')>assistant.indexOf('class="message-body markdown-content"'));
 for(const action of ['copyMarkdown(msg, $event.currentTarget)','requestSpeechSynthesis(msg)','regenerateMessage(index)','msg._perfVisible = !msg._perfVisible','externalReviewOpen = !externalReviewOpen','contextOpen = !contextOpen','branchChat(index)','deleteMessage(index)','openKnowledgeSave(index,'])assert.ok(header.includes(action),action);
 assert.ok(assistant.includes('@click="msg._thinkingOpen = !msg._thinkingOpen"'));
 assert.ok(assistant.includes('msg._recentStats.thinking_tokens'));
 assert.ok(source.includes('@click="stopStreaming()"'));
 assert.ok(source.includes('@click="startEdit(index)"'));
});
for(const width of [390,900,1440])test('Desktop Codex-style layout '+width,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width,height:1000}});
  // Real checked-in CSS and action markup; model/network execution is not exercised here.
  await page.setContent('<meta charset="utf-8"><style>'+fs.readFileSync(root+'/web/static/css/tailwind.css','utf8')+fs.readFileSync(root+'/web/static/css/chat_message_stream.css','utf8')+css+`\n:root{--bg-primary:white;--bg-secondary:#f5f5f5;--text-primary:#171717;--text-secondary:#555;--text-tertiary:#777;--border-faint:#ddd}body{margin:0}.fixture{max-width:864px;margin:auto;padding:24px 16px}.user-row{display:flex;justify-content:flex-end}.message-header [x-show],.message-header template{display:none}</style>
   <main class="fixture"><div class="user-row"><div class="user-message"><div class="user-message-actions"><button class="user-message-action-btn">Copy</button></div><div class="user-message-bubble">再试试</div></div></div>
   <article class="assistant-message"><details class="thinking-container"><summary class="thinking-header">Thought for 9s · 120 tok</summary><div class="thinking-content">思考内容</div></details><div class="message-body markdown-content"><h2>项目现状</h2><p>这是一段直接呈现的 AI 回复，不再被卡片外框包围。</p><table><tr><th>行动项</th><th>负责人</th></tr><tr><td>提交初稿</td><td>林悦</td></tr></table></div>`+header+`</main>`);
  const data=await page.evaluate(()=>{const u=document.querySelector('.user-message'),a=document.querySelector('.assistant-message'),h=a.querySelector('.message-header'),b=a.querySelector('.message-body');return{u:u.getBoundingClientRect().toJSON(),a:a.getBoundingClientRect().toJSON(),h:h.getBoundingClientRect().toJSON(),b:b.getBoundingClientRect().toJSON(),border:getComputedStyle(a).borderTopWidth,bg:getComputedStyle(a).backgroundColor,scroll:document.documentElement.scrollWidth};});
  assert.ok(data.u.width<160,'short user message shrinks');assert.ok(data.u.x>width/2,'user is right-aligned');
  assert.equal(data.border,'0px');assert.equal(data.bg,'rgba(0, 0, 0, 0)');assert.ok(data.h.y>=data.b.bottom);assert.ok(data.scroll<=width);
  await page.locator('summary').click();assert.equal(await page.locator('details').getAttribute('open'),'');
  await page.locator('.user-message-action-btn').focus();await page.waitForFunction(()=>getComputedStyle(document.querySelector('.user-message-actions')).opacity==='1');
  if(width===900)await page.screenshot({path:'/tmp/desktop-chat-presentation.png'});
  await page.locator('.user-message-bubble').evaluate(e=>e.textContent='长消息自动换行与附件区域保持正常。'.repeat(100));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 }finally{await browser.close();}
});
