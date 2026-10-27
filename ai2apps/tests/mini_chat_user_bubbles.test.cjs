const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),read=p=>fs.readFileSync(path.join(root,p),'utf8');
const fullCSS=read('web/templates/chat.html').match(/<style>([\s\S]*?)<\/style>/)[1];
for(const width of [320,480,1000])for(const embedded of [false,true])test(`Mini user bubble matches full Chat: ${width}px embedded=${embedded}`,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width,height:900}});
  await page.setContent('<meta charset="utf-8"><style>'+read('web/static/css/tailwind.css')+fullCSS+read('web/static/css/chat_mini.css')+read('web/static/css/chat_message_stream.css')+`body{margin:0;font-family:system-ui} .fixture{width:100%;padding:12px;box-sizing:border-box} .chat-mini{min-height:0;padding:0} .user-row{display:flex;justify-content:flex-end}:root{--bg-secondary:#f5f5f5;--text-primary:#171717}</style><section class="fixture chat-shell"><div class="user-row"><div class="user-message"><div class="user-message-bubble">再试试</div></div></div></section><section class="fixture"><main class="chat-mini ${embedded?'chat-mini-embedded':''}"><div id="mini-messages"></div></main></section>`);
  await page.addScriptTag({content:read('web/static/js/mini_app_chat.js')});
  await page.addStyleTag({content:'.fixture.chat-shell{height:auto!important;min-height:0}'});
  // Use the actual shared surface append path, without model or Tool calls.
  await page.evaluate(()=>{
   const mini=document.querySelector('.chat-mini');
   mini.innerHTML='<section class="chat-mini-messages"><div data-mini-messages></div></section><form><textarea></textarea><button type="submit">Send</button></form>';
   window.surface=AI2AppsMiniAppChat.bindConversationSurface(mini);surface.appendMessage('user','再试试');
  });
  const metrics=()=>page.evaluate(()=>{
   const f=document.querySelector('.user-message-bubble'),m=document.querySelector('.chat-mini-message.user');
   const props=['backgroundColor','color','borderRadius','paddingTop','paddingRight','paddingBottom','paddingLeft','fontSize','lineHeight','overflowWrap','wordBreak'];
   const style=e=>Object.fromEntries(props.map(k=>[k,getComputedStyle(e)[k]]));
   return {full:style(f),mini:style(m),m:m.getBoundingClientRect().toJSON(),parent:m.parentElement.getBoundingClientRect().toJSON(),scroll:document.documentElement.scrollWidth};
  });
  let data=await metrics();assert.deepEqual(data.mini,data.full);assert.ok(data.m.width<130);assert.ok(Math.abs(data.m.right-data.parent.right)<1);
  await page.evaluate(()=>{document.querySelector('.chat-mini-message.user').textContent='长消息与连续字符自动换行'.repeat(100)+'https://example.test/'+'x'.repeat(250);});
  data=await metrics();assert.ok(data.m.width<=Math.min(672,data.parent.width*.85)+1);assert.ok(data.scroll<=width);
  await page.evaluate(()=>{document.documentElement.style.setProperty('--bg-secondary','#292929');document.documentElement.style.setProperty('--text-primary','#ededed');});
  data=await metrics();assert.deepEqual(data.mini,data.full);assert.equal(data.mini.color,'rgb(255, 255, 255)');assert.equal(data.mini.backgroundColor,'rgb(23, 23, 23)');
  if(width===480&&embedded){await page.evaluate(()=>{document.querySelector('.chat-mini-message.user').textContent='再试试';});await page.screenshot({path:'/tmp/mini-chat-user-bubbles.png'});}
 }finally{await browser.close();}
});
