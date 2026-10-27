const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {webkit}=require('playwright'),root=path.join(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
test('real Mini-Entry iframe supports App buttons and preserves old mode discriminator',async()=>{
 const browser=await webkit.launch({headless:true});try{
  const page=await browser.newPage({viewport:{width:900,height:800}});const errors=[];page.on('pageerror',e=>errors.push(e.stack));
  const entryHTML='<main class="chat-mini"></main><script src="/mini.js"></script><script>AI2AppsMiniAppChat.startChatEntry()</script>';
  await page.route('https://chat.test/**',route=>{const url=new URL(route.request().url());if(url.pathname==='/mini.js')return route.fulfill({contentType:'application/javascript; charset=utf-8',body:read('web/static/js/'+'mini_app_chat.js')});return route.fulfill({contentType:'text/html; charset=utf-8',body:'<meta charset="utf-8">'+(url.pathname.includes('/admin/chat-mini')?entryHTML:'<main><iframe style="width:450px;height:700px"></iframe></main>')});});
  await page.goto('https://chat.test');await page.addScriptTag({content:read('web/static/js/mini_app_chat.js')});
  await page.evaluate(()=>{
   window.events=[];window.state={binding:{sessionId:'session',contextId:'object-a',revision:'1'},title:'Owner chat',messages:[],suggestions:['Suggested question']};
   window.controller=AI2AppsMiniAppChat.createAppChatController({identity:{appId:'brand.example',providerId:'brand.example.chat',version:'1'},describe:()=>state,
    send:async ctx=>{events.push({type:'send',text:ctx.text,binding:ctx.binding});state.messages.push({id:'u',role:'user',content:ctx.text},{id:'a',role:'assistant',content:'Answer'});state.suggestionsVisible=false;},
    actions:[{id:'inspect',hook:'inspect',label:'Inspect message',placement:'message'},{id:'more',hook:'more',label:'More topics',placement:'composer'}],hooks:{
     inspect:ctx=>events.push({type:'inspect',messageId:ctx.messageId,binding:ctx.binding}),more:()=>{state.suggestions=['New topic'];state.suggestionsVisible=true;}
    }});
   const frame=document.querySelector('iframe');controller.bind(frame);frame.src=controller.url();
  });
  const entry=page.frameLocator('iframe');await entry.locator('[data-app-chat-suggestion]').waitFor({timeout:5000}).catch(async e=>{throw Error(e.message+' errors='+JSON.stringify(errors)+' body='+await entry.locator('body').innerText());});
  await entry.locator('[data-app-chat-suggestion]').click();await entry.locator('[data-app-chat-send]').click();
  await entry.locator('[data-message-id="a"]').waitFor();
  assert.equal(await entry.locator('[data-app-chat-input]').inputValue(),'');
  assert.equal(await entry.locator('[data-app-chat-suggestion]').count(),0);
  await entry.locator('[data-message-id="a"] [data-app-chat-action="inspect"]').click();
  await page.waitForFunction(()=>events.some(e=>e.type==='inspect'));
  assert.equal(await page.evaluate(()=>events.find(e=>e.type==='inspect').messageId),'a');
  await entry.locator('[data-app-chat-action="more"]').click();await entry.locator('[data-app-chat-suggestion="New topic"]').waitFor();
  await entry.locator('[data-app-chat-input]').fill('Draft A');
  await page.evaluate(()=>{state={...state,binding:{sessionId:'session-b',contextId:'object-b',revision:'1'},messages:[]};controller.changed();});
  await page.waitForFunction(()=>document.querySelector('iframe').contentDocument.querySelector('textarea').value==='');
  await entry.locator('[data-app-chat-input]').fill('Draft B');
  await page.evaluate(()=>{state={...state,binding:{sessionId:'session',contextId:'object-a',revision:'1'}};controller.changed();});
  await page.waitForFunction(()=>document.querySelector('iframe').contentDocument.querySelector('textarea').value==='Draft A');
  assert.equal(await page.evaluate(()=>events.filter(e=>e.type==='send').length),1);
 }finally{await browser.close();}
});
test('legacy v1 Mini-App iframe still performs begin, tool call, final answer and end with new SDK loaded',async()=>{
 const browser=await webkit.launch({headless:true});try{
  const page=await browser.newPage();let completions=0;
  let html=read('web/templates/system_apps/chat_mini.html').split('{% block content %}')[1].split('{% endblock %}')[0].replace(/\{\{ t\('([^']+)'\) \}\}/g,(_,k)=>k);
  html='<meta charset="utf-8">'+html+'<script src="/mini.js"></script><script>AI2AppsMiniAppChat.startChatEntry()</script>';
  await page.route('https://legacy.test/**',async route=>{
   const url=new URL(route.request().url()),p=url.pathname;
   if(p==='/mini.js')return route.fulfill({contentType:'application/javascript; charset=utf-8',body:read('web/static/js/'+'mini_app_chat.js')});
   if(p==='/v1/chat/completions'){
    completions++;const body=route.request().postDataJSON();
    if(completions===2)assert.equal(body.messages.find(m=>m.role==='tool').tool_call_id,'legacy-call');
    const delta=completions===1?{tool_calls:[{index:0,id:'legacy-call',type:'function',function:{name:'owner_lookup',arguments:'{"key":"one"}'}}]}:{content:'Legacy answer is preserved'};
    return route.fulfill({contentType:'text/event-stream',body:'data: '+JSON.stringify({choices:[{delta}]})+'\n\ndata: [DONE]\n\n'});
   }
   if(p==='/v1/models')return route.fulfill({json:{data:[{id:'fixture-model',model_type:'llm'}]}});
   if(p==='/admin/api/model-manager')return route.fulfill({json:{defaults:{work_standard:'fixture-model'}}});
   if(p.startsWith('/v1/'))return route.fulfill({json:{}});
   return route.fulfill({contentType:'text/html; charset=utf-8',body:p.includes('/admin/chat-mini')?html:'<iframe></iframe>'});
  });
  await page.goto('https://legacy.test');await page.addScriptTag({content:read('web/static/js/mini_app_chat.js')});
  await page.evaluate(()=>{
   window.trace=[];const frame=document.querySelector('iframe');
   const controller=AI2AppsMiniAppChat.createStudioController({
    describe:()=>({schema:AI2AppsMiniAppChat.SCHEMA,enabled:true,miniApp:{id:'old.example',name:'Legacy'},systemPrompt:'Use declared tools',context:{object:'one'},help:{available:true,format:'markdown',maxBytes:1000},tools:[{name:'owner_lookup',description:'Read owner data',inputSchema:{type:'object',properties:{key:{type:'string'}},required:['key'],additionalProperties:false}}]}),
    begin:()=>trace.push('begin'),end:()=>trace.push('end'),invoke:(name,args)=>{trace.push(name+':'+args.key);return {value:'one'};},help:()=>({content:'Help'})});
   controller.bind(frame);frame.src=controller.url();
  });
  const entry=page.frameLocator('iframe');await entry.locator('#chat-mini-model option[value="fixture-model"]').waitFor({state:'attached'});
  await entry.locator('#chat-mini-input').fill('Look up one');await entry.locator('#chat-mini-send').click();
  await entry.getByText('Legacy answer is preserved',{exact:true}).waitFor();
  assert.deepEqual(await page.evaluate(()=>trace),['begin','owner_lookup:one','end']);assert.equal(completions,2);
 }finally{await browser.close();}
});
test('App Chat Markdown is rendered without executable HTML, controls or remote media',async()=>{
 const browser=await webkit.launch({headless:true});try{
  const page=await browser.newPage();await page.setContent('<main id="host"></main>');
  for(const file of ['purify.min','marked.umd','mini_app_chat'])await page.addScriptTag({content:read('web/static/js/'+file+'.js')});
  await page.evaluate(()=>{
   const state={binding:{sessionId:'s',contextId:'c',revision:'1'},messages:[{id:'m',role:'assistant',format:'markdown',content:'**Bold** <img src="https://untrusted.invalid/x" onerror="alert(1)"><button>Fake confirmation</button><a href="javascript:alert(1)">Bad link</a><script>alert(1)</script>'}]};
   const controller=AI2AppsAppChat.createController({identity:{appId:'arbitrary',providerId:'p',version:'1'},describe:()=>state});
   AI2AppsAppChat.mount({root:document.querySelector('#host'),transport:controller});
  });
  await page.locator('.chat-mini-markdown strong').waitFor();assert.equal(await page.locator('.chat-mini-markdown strong').innerText(),'Bold');
  assert.equal(await page.locator('.chat-mini-markdown img,.chat-mini-markdown button,.chat-mini-markdown script,.chat-mini-markdown [href^="javascript:"]').count(),0);
 }finally{await browser.close();}
});

test('one Mini-Chat SDK shows pending prompt and in-stream failure, reconciles once and keeps aliases',async()=>{
 const browser=await webkit.launch({headless:true});try{
  const page=await browser.newPage();await page.setContent('<main id="host"></main>');
  for(const css of ['chat_mini','chat_message_stream'])await page.addStyleTag({content:read('web/static/css/'+css+'.css')});
  await page.addScriptTag({content:read('web/static/js/mini_app_chat.js')});
  await page.evaluate(()=>{
   window.events=[];window.state={binding:{sessionId:'s',contextId:'a',revision:'1'},messages:[],status:''};
   window.controller=AI2AppsMiniAppChat.createController({identity:{appId:'arbitrary.vendor',providerId:'arbitrary.provider',version:'1'},describe:()=>state,
    send:async ctx=>{const snapshot=state;events.push(ctx.text);await new Promise((resolve,reject)=>{window.release=resolve;window.reject=reject;});snapshot.messages.push({id:'u'+events.length,role:'user',content:ctx.text},{id:'a'+events.length,role:'assistant',content:'Done'});snapshot.status='';}});
   window.entry=AI2AppsMiniAppChat.mount({root:document.querySelector('#host'),transport:controller,labels:{thinking:'Thinking…'}});
  });
  await page.locator('[data-app-chat-input]').fill('Immediate prompt');await page.locator('[data-app-chat-send]').click();
  await page.waitForFunction(()=>typeof release==='function');
  assert.equal(await page.locator('.chat-mini-message.user').innerText(),'Immediate prompt');
  assert.equal(await page.locator('[data-app-chat-input]').inputValue(),'');
  assert.equal(await page.locator('.chat-mini-pending').innerText(),'Thinking…');
  assert.equal(await page.locator('[data-mini-status]').isVisible(),false);
  await page.evaluate(()=>{state.status='Reading evidence';controller.changed();});
  await page.getByText('Reading evidence',{exact:true}).waitFor();
  assert.equal(await page.locator('.chat-mini-message.user').count(),1);
  await page.evaluate(()=>release());await page.getByText('Done',{exact:true}).waitFor();
  await page.waitForFunction(()=>!document.querySelector('[data-app-chat-send]').disabled);
  assert.equal(await page.locator('.chat-mini-message.user').count(),1);
  assert.equal(await page.locator('.chat-mini-pending').count(),0);
  await page.locator('[data-app-chat-input]').fill('Uncertain send');await page.locator('[data-app-chat-send]').click();
  await page.waitForFunction(()=>events.length===2);await page.evaluate(()=>reject(Error('Execution outcome unknown')));
  await page.locator('.chat-mini-message.error').waitFor();
  assert.equal(await page.locator('[data-app-chat-input]').inputValue(),'Uncertain send');
  assert.equal(await page.locator('.chat-mini-message.user').last().innerText(),'Uncertain send');
  assert.equal(await page.evaluate(()=>events.length),2);
  await page.locator('[data-app-chat-input]').fill('Bound to A');await page.locator('[data-app-chat-send]').click();
  await page.waitForFunction(()=>events.length===3);
  await page.evaluate(()=>{state={binding:{sessionId:'other',contextId:'b',revision:'1'},messages:[]};controller.changed();});
  await page.waitForFunction(()=>!document.querySelector('.chat-mini-message.user'));
  await page.evaluate(()=>release());
  await page.waitForTimeout(50);
  assert.equal(await page.locator('.chat-mini-message.user').count(),0);
  assert.equal(await page.locator('.chat-mini-message.assistant').count(),0);
  assert.equal(await page.evaluate(()=>AI2AppsAppChat.createController===AI2AppsMiniAppChat.createController&&AI2AppsMiniAppChat.mountAppChat===AI2AppsMiniAppChat.mount),true);
 }finally{await browser.close();}
});

for(const width of [390,1440])test('legacy and owner entries use identical Mini-Chat controls at '+width,async()=>{
 const browser=await webkit.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width,height:900},hasTouch:width===390});
  await page.setContent('<main id="legacy" class="chat-mini"><header><div><h1>Legacy</h1><p>Context</p></div></header><section class="chat-mini-messages"></section><form><textarea placeholder="Question"></textarea><button type="submit">Send</button></form></main><div id="intel-app"><div id="owner"></div></div>');
  await page.addStyleTag({content:read('web/static/css/chat_mini.css')});
  await page.addStyleTag({content:read('web/static/css/intelligence.css')});
  await page.addStyleTag({content:read('web/static/css/chat_message_stream.css')});
  await page.addStyleTag({content:'.mini-chat-entry-host,#owner{position:absolute;left:0;top:0;width:350px;height:650px;padding:10px}#owner{left:0}#intel-app{height:700px;overflow:visible}'});
  await page.addScriptTag({content:read('web/static/js/mini_app_chat.js')});
  await page.evaluate(()=>{
   AI2AppsMiniAppChat.hydrateEntry(document.querySelector('#legacy'));
   window.calls=[];window.ownerState={binding:{sessionId:'s',contextId:'a',revision:'1'},title:'Owner',subtitle:'Context',models:[{id:'first',name:'First'},{id:'second',name:'Second'}],model:'first',messages:[{id:'u',role:'user',content:'Hello'}]};
   const controller=AI2AppsMiniAppChat.createController({identity:{appId:'arbitrary.owner',providerId:'arbitrary.chat',version:'1'},describe:()=>ownerState,send:async()=>{},reset:()=>{calls.push('reset');ownerState.messages=[];},selectModel:ctx=>{calls.push(ctx.model);ownerState.model=ctx.model;}});
   window.view=AI2AppsMiniAppChat.mount({root:document.querySelector('#owner'),transport:controller,labels:{send:'Send',placeholder:'Ask about this article…'}});
  });
  await page.locator('#owner [data-message-id="u"]').waitFor();
  await page.locator('#owner').screenshot({path:'/tmp/unified-mini-chat-'+width+'.png'});
  const measure=selector=>page.locator(selector).evaluate(e=>{const c=getComputedStyle(e);return {height:c.height,padding:c.padding,border:c.borderRadius,font:c.fontSize,display:c.display,bg:c.backgroundColor,color:c.color};});
  for(const selector of ['textarea','button[type="submit"]','.chat-mini-reset','select'])assert.deepEqual(await measure('#owner '+selector),await measure('#legacy '+selector));
  assert.equal(await page.locator('#owner button[type="submit"]').innerText(),'');
  const model=await page.locator('#owner select').boundingBox(),reset=await page.locator('#owner .chat-mini-reset').boundingBox();assert.equal(Math.round(model.y),Math.round(reset.y));
  await page.locator('#owner select').selectOption('second');await page.waitForFunction(()=>calls.includes('second'));
  await page.waitForFunction(()=>!document.querySelector('#owner .chat-mini-reset').disabled);
  await page.locator('#owner .chat-mini-reset').click({force:true});await page.waitForFunction(()=>calls.includes('reset'));
  assert.equal(await page.locator('#owner [data-message-id]').count(),0);
 }finally{await browser.close();}
});

test('standalone template stays inert until the shared component builds it',async()=>{
 const browser=await webkit.launch({headless:true});
 try{
  const page=await browser.newPage();
  const source=read('web/templates/system_apps/chat_mini.html');
  const main=source.slice(source.indexOf('<main '),source.indexOf('</main>')+7).replace(/\{\{[\s\S]*?\}\}/g,'Label');
  await page.setContent(main);
  assert.equal(await page.locator('textarea').count(),0);
  await page.addScriptTag({content:read('web/static/js/mini_app_chat.js')});
  await page.evaluate(()=>AI2AppsMiniAppChat.startChatEntry());
  assert.equal(await page.locator('.chat-mini-embedded').count(),1);
  assert.equal(await page.locator('#chat-mini-model,#chat-mini-reset,#chat-mini-form,#chat-mini-input,#chat-mini-send').count(),5);
  assert.equal(await page.locator('#chat-mini-send').innerText(),'');
 }finally{await browser.close();}
});
