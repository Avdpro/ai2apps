const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),{execFileSync}=require('child_process');
const {chromium}=require('playwright');
const base=path.resolve(__dirname,'..'),git=path.resolve(base,'..');
function html(inline){return execFileSync(git+'/.venv/bin/python',['-c',`from jinja2 import Environment,FileSystemLoader\ne=Environment(loader=FileSystemLoader('${base}/web/templates'))\ne.globals['mobile_static']=lambda n:'/assets/'+n\nprint(e.get_template('mobile_chat.html').render(current_lang='zh',owner_home=True,mobile_agent_ready=False,mobile_agent_inline=${inline?'True':'False'}))`],{encoding:'utf8'});}
for(const inline of [false,true])test(`Assistant plain content and local actions (${inline?'inline':'standalone'})`,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width:390,height:844}}),writes=[],speechRequests=[];let ttsAvailable=true;
  const markdown='## 回复示例\n\n这是一段 **AI 回复**，不再使用气泡。\n\n- 支持复制\n- 支持朗读\n\n```js\nDO_NOT_READ_CODE\n```\n\n[参考文档](https://example.com/)';
  await page.addInitScript(()=>{
   window.copied=[];window.cancellations=0;window.systemSpeechCalls=0;
   Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{if(window.clipboardReject)throw Error();window.copied.push(text);}}});
   document.execCommand=command=>{if(command==='copy'){window.copied.push(document.activeElement.value);return true;}return false;};
   window.SpeechSynthesisUtterance=function(){window.systemSpeechCalls++;throw Error('Device voice forbidden');};
   Object.defineProperty(window,'speechSynthesis',{configurable:true,value:{speak:()=>{window.systemSpeechCalls++;throw Error('Device voice forbidden');}}});
   Object.defineProperty(HTMLMediaElement.prototype,'src',{configurable:true,get(){return this._fixtureSrc;},set(value){this._fixtureSrc=value;}});
   HTMLMediaElement.prototype.play=function(){return Promise.resolve();};HTMLMediaElement.prototype.pause=function(){window.cancellations++;};
  });
  await page.route('https://fixture.test/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname;if(p==='/v1/mobile/owner-home/activity')return route.fulfill({json:{}});if(req.method()!=='GET')writes.push(p);
   if(p==='/')return route.fulfill({contentType:'text/html',body:html(inline)});
   if(p.startsWith('/assets/')){const f=path.join(base,'web/static',p.slice(8));return route.fulfill({contentType:p.endsWith('.css')?'text/css':'application/javascript',body:fs.existsSync(f)?fs.readFileSync(f):''});}
   let data;
   if(p.endsWith('/speech')){speechRequests.push(req.postDataJSON());if(!ttsAvailable)return route.fulfill({status:409,json:{detail:'Desktop 没有可用的 TTS 模型，请在 Desktop 安装并配置语音合成模型后重试。'}});return route.fulfill({contentType:'audio/wav',body:Buffer.from('fixture-wave')});}
   if(p.endsWith('/state'))data={selected_thread_id:'s'};
   else if(p.endsWith('/models'))data={data:[]};
   else if(p.endsWith('/threads'))data={items:[{id:'s',title:'展示验收'}]};
   else if(p.endsWith('/content'))data={thread:{id:'s',title:'展示验收'},session_metadata:{},messages:[{role:'user',content:'你再看看？'},{role:'assistant',content:markdown},{role:'assistant',content:'第二段回复'}]};
   else if(p.endsWith('/turns'))data={items:[]};
   else return route.fulfill({status:404,json:{detail:'Unexpected operation'}});
   return route.fulfill({json:data});
  });
  await page.goto('https://fixture.test/');if(inline)await page.evaluate(()=>window.dispatchEvent(new CustomEvent('ai2apps-mobile-chat-visible',{detail:true})));
  await page.getByRole('button',{name:'复制回复',exact:true}).first().waitFor();
  const geometry=await page.locator('.mchat-message.assistant').first().evaluate(n=>({border:getComputedStyle(n).borderTopWidth,background:getComputedStyle(n).backgroundColor,width:n.getBoundingClientRect().width,parent:n.parentElement.clientWidth-26}));
  assert.equal(geometry.border,'0px');assert.equal(geometry.background,'rgba(0, 0, 0, 0)');assert.ok(Math.abs(geometry.width-geometry.parent)<1);
  assert.equal(await page.locator('.mchat-message.user .mchat-message-actions').count(),0);
  assert.equal(await page.locator('.mchat-message-actions svg').count(),4);
  if(!inline)await page.screenshot({path:'/tmp/ai2apps-mobile-assistant-actions.png'});
  await page.getByRole('button',{name:'复制回复',exact:true}).first().click();assert.equal(await page.evaluate(()=>window.copied[0]),markdown);
  await page.evaluate(()=>window.clipboardReject=true);await page.getByRole('button',{name:'复制回复',exact:true}).last().click();assert.equal(await page.evaluate(()=>window.copied.at(-1)),'第二段回复');
  await page.getByRole('button',{name:'朗读回复',exact:true}).first().click();
  await page.locator('audio').waitFor();
  assert.equal(await page.getByRole('button',{name:'停止朗读',exact:true}).count(),1);
  assert.ok(!speechRequests[0].text.includes('DO_NOT_READ_CODE'));
  await page.getByRole('button',{name:'朗读回复',exact:true}).last().click();await page.locator('audio').waitFor();assert.ok(await page.evaluate(()=>window.cancellations>0));
  await page.getByRole('button',{name:'停止朗读',exact:true}).click();assert.equal(await page.getByRole('button',{name:'停止朗读',exact:true}).count(),0);
  await page.getByRole('button',{name:'朗读回复',exact:true}).first().click();await page.locator('audio').waitFor();await page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));
  assert.equal(await page.getByRole('button',{name:'停止朗读',exact:true}).count(),0);
  ttsAvailable=false;await page.getByRole('button',{name:'朗读回复',exact:true}).first().click();await page.locator('.mchat-speech-error').first().getByText('Desktop 没有可用的 TTS 模型，请在 Desktop 安装并配置语音合成模型后重试。',{exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>window.systemSpeechCalls),0);assert.ok(speechRequests.length>=4);assert.ok(writes.every(p=>p.endsWith('/speech')));
 }finally{await browser.close();}
});
