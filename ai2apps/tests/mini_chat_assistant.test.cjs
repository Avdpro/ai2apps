const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright'),root=path.resolve(__dirname,'..'),read=p=>fs.readFileSync(path.join(root,p),'utf8');
async function fixture(run){const browser=await chromium.launch({headless:true,channel:'chrome'});try{
 const page=await browser.newPage({viewport:{width:390,height:844}});await page.setContent('<html lang="zh"><main class="chat-mini chat-mini-embedded"><section class="chat-mini-messages"></section><form><textarea></textarea><button>Send</button></form></main></html>');
 await page.addStyleTag({content:read('web/static/css/chat_mini.css')+read('web/static/css/chat_message_stream.css')});
 await page.addScriptTag({content:read('web/static/js/marked.umd.js')});await page.addScriptTag({content:read('web/static/js/purify.min.js')});await page.addScriptTag({content:read('web/static/js/mini_app_chat.js')});
 await page.evaluate(()=>{window.surface=AI2AppsMiniAppChat.bindConversationSurface(document.querySelector('main'));window.target=surface.beginTurn('Question','Thinking…').target;});
 await run(page);
}finally{await browser.close();}}
test('Mini assistant streams split thinking tags, retains collapsible thinking and copies only Markdown answer',()=>fixture(async page=>{
 await page.evaluate(()=>{window.copied='';Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>copied=text},configurable:true});
 surface.startCompletion(target);surface.consumeDelta(target,{content:'<thi'});surface.consumeDelta(target,{content:'nk>私有思考'});surface.consumeDelta(target,{content:'</think>## 答案\n\n**结果**'});surface.finishTurn(target);});
 assert.equal(await page.locator('.chat-mini-thinking>div').textContent(),'私有思考');assert.equal(await page.locator('.chat-mini-thinking').getAttribute('open'),null);
 await page.locator('.chat-mini-thinking summary').click();assert.equal(await page.locator('.chat-mini-thinking').getAttribute('open'),'');
 assert.equal(await page.locator('.chat-mini-answer h2').innerText(),'答案');await page.locator('[data-mini-copy]').click();assert.equal(await page.evaluate(()=>copied),'## 答案\n\n**结果**');
 const style=await page.locator('.chat-mini-message.assistant').evaluate(e=>{const s=getComputedStyle(e);return[s.backgroundColor,s.borderTopWidth,s.borderRadius]});assert.deepEqual(style,['rgba(0, 0, 0, 0)','0px','0px']);
 await page.screenshot({path:'/tmp/mini-chat-assistant.png'});
}));
test('Reasoning delta and real tool activity remain separate from final answer; no extra execution',()=>fixture(async page=>{
 await page.evaluate(()=>{surface.startCompletion(target);surface.consumeDelta(target,{reasoning_content:'思考 A'});surface.setActivity(target,'Running declared_tool…');surface.startCompletion(target);surface.consumeDelta(target,{reasoning_content:'思考 B',content:'Final'});surface.finishTurn(target);});
 assert.equal(await page.locator('.chat-mini-thinking>div').textContent(),'思考 A思考 B');assert.equal(await page.locator('.chat-mini-activity').innerText(),'Running declared_tool…');assert.equal(await page.locator('.chat-mini-answer').innerText(),'Final');
}));
test('Desktop TTS is explicit, excludes thinking/code, and stop releases audio; no phone speech fallback',()=>fixture(async page=>{
 await page.evaluate(()=>{window.calls=[];window.speechSynthesis={speak(){throw Error('system voice prohibited')}};
 Object.defineProperty(HTMLMediaElement.prototype,'src',{configurable:true,get(){return this.dataset.fixtureSrc||'';},set(value){this.dataset.fixtureSrc=value;}});
 HTMLMediaElement.prototype.play=()=>Promise.resolve();HTMLMediaElement.prototype.pause=function(){};
 window.fetch=async(url,options={})=>{calls.push({url,body:options.body});return url==='/v1/models'?new Response(JSON.stringify({data:[{id:'desktop-tts',model_type:'audio_tts',checkpoint_ready:true}]}),{headers:{'Content-Type':'application/json'}}):new Response(new Uint8Array([1,2]),{headers:{'Content-Type':'audio/wav'}});};
 surface.updateMessage(target,'正文\n\n```js\nsecretCode()\n```',{thinking:'private',format:'markdown'});surface.finishTurn(target);});
 await page.locator('[data-mini-speak]').click();await page.locator('audio').waitFor();
 const calls=await page.evaluate(()=>calls);assert.equal(calls.length,2);const body=JSON.parse(calls[1].body);assert.equal(body.model,'desktop-tts');assert.ok(body.input.includes('正文'));assert.ok(!body.input.includes('secretCode'));assert.ok(!body.input.includes('private'));
 await page.locator('[data-mini-speak]').click();assert.equal(await page.locator('audio').count(),0);assert.equal(await page.locator('[data-mini-speak]').getAttribute('aria-pressed'),'false');
}));
test('Missing Desktop TTS instructs configuration and errors never expose read buttons',()=>fixture(async page=>{
 await page.evaluate(()=>{window.fetch=async()=>new Response('{"data":[]}',{headers:{'Content-Type':'application/json'}});surface.updateMessage(target,'Answer');surface.finishTurn(target);});
 await page.locator('[data-mini-speak]').click();await page.getByText('Desktop 没有可用的 TTS 模型，请在 Desktop 安装并配置语音合成模型。',{exact:true}).waitFor();
 await page.evaluate(()=>surface.finishTurn(target,'Failed'));assert.equal(await page.locator('[data-mini-speak]').isVisible(),false);assert.equal(await page.locator('.chat-mini-message.error').getAttribute('role'),'alert');
}));
test('Owner snapshot thinking and actions coexist without opening Agent Chat or executing on render',()=>fixture(async page=>{
 await page.evaluate(()=>{surface.dispose();document.querySelector('main').replaceChildren();window.hookCalls=0;window.controller=AI2AppsMiniAppChat.createController({identity:{appId:'arbitrary.owner',providerId:'arbitrary.provider',version:'1'},describe:()=>({binding:{sessionId:'s',contextId:'c',revision:'1'},messages:[{id:'a',role:'assistant',content:'Safe <img src=x onerror=alert(1)>',thinking:'Owner thought',thinking_tokens:23,format:'markdown'}]}),actions:[{id:'inspect',hook:'inspect',label:'Inspect',placement:'message'}],hooks:{inspect:()=>hookCalls++}});window.view=AI2AppsMiniAppChat.mount({root:document.querySelector('main'),transport:controller});});
 await page.getByText('思考 · 23 tok',{exact:true}).waitFor();assert.equal(await page.locator('.chat-mini-message img').count(),0);assert.equal(await page.evaluate(()=>hookCalls),0);
 await page.locator('[data-app-chat-action=inspect]').click();await page.waitForFunction(()=>hookCalls===1);assert.equal(await page.locator('[data-mini-copy]').count(),1);
 await page.evaluate(()=>view.dispose());
}));
