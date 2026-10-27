const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');const base=path.resolve(__dirname,'../web');
const read=p=>fs.readFileSync(path.join(base,p),'utf8');
for(const mobile of [false,true])test(`${mobile?'Mobile':'Desktop'} bubble, hover label and real copy outcome`,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage({viewport:{width:mobile?390:1100,height:800}});
 const source=read('templates/chat.html');
 await page.setContent(`<html lang="zh"><body><main class="${mobile?'mchat-list':'chat-shell'}" style="padding:30px;--text-primary:#171717"><div class="${mobile?'mchat-message user':'user-message'}"><div class="${mobile?'':'user-message-bubble markdown-content'}"><p>请查看最近三个帖子，<strong>优先使用列表</strong>中的信息。<a href="https://example.test">链接</a><code>代码</code><br>Long message https://example.test/${'abc'.repeat(50)}</p></div></div><div class="${mobile?'mchat-message-actions':'message-header'}"><button title="复制" id="copy">Copy</button><button title="重新生成" id="other">Again</button></div></main></body></html>`);
 await page.addStyleTag({content:read('static/css/'+(mobile?'mobile_chat.css':'chat_message_stream.css'))});
 if(!mobile)await page.addStyleTag({content:source.match(/<style>([\s\S]*?)<\/style>/)[1]});
 await page.addStyleTag({content:read('static/css/chat_message_feedback.css')});await page.addScriptTag({content:read('static/js/chat_message_feedback.js')});
 const bubble=page.locator(mobile?'.mchat-message.user':'.user-message-bubble');
 const styles=await bubble.evaluate(n=>({bg:getComputedStyle(n).backgroundColor,color:getComputedStyle(n.querySelector('p')).color,overflow:document.documentElement.scrollWidth>innerWidth}));
 assert.equal(styles.bg,'rgb(23, 23, 23)');assert.equal(styles.color,'rgb(255, 255, 255)');assert.equal(styles.overflow,false);
 assert.deepEqual(await bubble.locator('strong,a,code').evaluateAll(nodes=>nodes.map(n=>getComputedStyle(n).color)),Array(3).fill('rgb(255, 255, 255)'));
 if(!mobile){await page.locator('.user-message').evaluate(n=>n.classList.add('is-editing'));assert.equal(await bubble.evaluate(n=>getComputedStyle(n).color),'rgb(23, 23, 23)');await page.locator('.user-message').evaluate(n=>n.classList.remove('is-editing'));}
 await page.locator('#other').hover();assert.equal(await page.locator('#other').getAttribute('data-chat-tip'),'重新生成');
 if(mobile){const js=read('static/js/mobile_chat.js');await page.addScriptTag({content:js.slice(0,js.indexOf('\n(function ()'))});await page.evaluate(()=>{window.messages=[];window.controller=new AI2AppsMobileMessageActions.Controller(t=>messages.push(t));document.querySelector('#copy').onclick=()=>controller.copy('hello',document.querySelector('#copy'));});}
 else{const methods=source.slice(source.indexOf('    _copyFallback(text) {'),source.indexOf('    async loadKnowledgeBucketsForSave()'));await page.evaluate(code=>{window.vm=Function('return ({'+code+'})')();document.querySelector('#copy').onclick=()=>vm._copyWithFeedback('hello',document.querySelector('#copy'));},methods);}
 await page.evaluate(()=>Object.defineProperty(window,'isSecureContext',{configurable:true,value:true}));
 await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{await new Promise(r=>setTimeout(r,40));window.copied='hello';}}}));
 await page.locator('#copy').click();await page.waitForFunction(()=>document.querySelector('#copy').dataset.copySuccess==='true');assert.equal(await page.evaluate(()=>copied),'hello');assert.equal(await page.locator('#copy').getAttribute('data-chat-tip'),'已复制');
 await page.evaluate(()=>{navigator.clipboard.writeText=async()=>{throw Error('denied')};document.execCommand=()=>false;});
 await page.locator('#copy').click();await page.waitForFunction(()=>document.querySelector('#copy').dataset.copySuccess==='false');assert.match(await page.locator('#copy').getAttribute('data-chat-tip'),/复制失败/);
 assert.ok(await page.locator('#copy').evaluate(n=>getComputedStyle(n,'::after').left==='0px'));
 await page.screenshot({path:'/tmp/chat-message-'+(mobile?'mobile':'desktop')+'.png'});
 }finally{await browser.close();}
});
