const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {webkit}=require('playwright');
const root=path.join(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
test('Mobile hidden dock releases its space and restores on leaving focus mode',async()=>{
 const browser=await webkit.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:390,height:850}});
  await page.setContent('<div id="shell" class="mobile-shell"><header class="mobile-topbar">App name</header><main class="mobile-main"></main><nav class="mobile-dock">Navigation</nav></div>');
  await page.addStyleTag({content:read('web/static/css/mobile.css')});
  const before=await page.locator('.mobile-main').boundingBox();
  await page.locator('#shell').evaluate(node=>node.classList.add('mobile-dock-hidden'));
  assert.equal(await page.locator('.mobile-dock').isVisible(),false);
  const after=await page.locator('.mobile-main').boundingBox();
  assert.ok(after.height-before.height>=78);
  await page.locator('#shell').evaluate(node=>node.classList.add('mobile-topbar-hidden'));
  assert.equal(await page.locator('.mobile-topbar').isVisible(),false);
  const focused=await page.locator('.mobile-main').boundingBox();
  assert.ok(focused.height-after.height>=58);
  await page.locator('#shell').evaluate(node=>node.classList.remove('mobile-topbar-hidden'));
  assert.equal(await page.locator('.mobile-topbar').isVisible(),true);
  await page.locator('#shell').evaluate(node=>node.classList.remove('mobile-dock-hidden'));
  assert.equal(await page.locator('.mobile-dock').isVisible(),true);
  assert.deepEqual(await page.locator('.mobile-main').boundingBox(),before);
 }finally{await browser.close();}
});
for(const width of [390,1440])test('Article dialogue topics, answer, followup, reset and confirmed research at '+width,async()=>{
 const browser=await webkit.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width,height:780},hasTouch:width===390});
  await page.route('https://article.test/**',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1"><div id="intel-app" data-mobile-page="reader"><aside id="intel-reader" class="intel-reader"><header class="intel-mobile-bar"><button id="test-back">Back</button></header><div class="intel-right-tabs"><button id="test-article">Article</button><button id="test-chat">Discussion</button></div><div id="test-detail">Article contents</div><button data-article-chat="a">Discuss</button></aside></div>'}));
  await page.goto('https://article.test');await page.addStyleTag({content:'#intel-app{height:100dvh;display:flex}#intel-reader{height:100%;box-sizing:border-box;width:100%;padding:14px;overflow:auto}body{margin:0}'});await page.addStyleTag({content:read('web/static/css/intelligence.css')});
  await page.evaluate(catalog=>{window.IntelligenceI18n={format:key=>catalog[key]||key};},JSON.parse(read('web/i18n/en.json')));
  await page.addStyleTag({content:read('web/static/css/chat_mini.css')});await page.addStyleTag({content:read('web/static/css/chat_message_stream.css')});await page.addScriptTag({content:read('web/static/js/mini_app_chat.js')});await page.addScriptTag({content:read('web/static/js/intelligence_article_chat.js')});
  await page.evaluate(()=>{
   window.calls=[];window.state={thread:'thread-1234567890',turns:[],questions:[],analysis:'',busy:null};window.actions={};window.count=0;
   const pane=document.querySelector('#intel-reader');
   const show=active=>{pane.classList.toggle('article-chat-visible',active);document.querySelector('#test-detail').hidden=active;window.IntelligenceArticleChat.setVisible(active);};
   document.querySelector('#test-back').onclick=()=>show(false);document.querySelector('#test-article').onclick=()=>show(false);document.querySelector('#test-chat').onclick=()=>show(true);
   window.IntelligenceArticleChat.init({panelRoot:pane,showPanel:()=>show(true),showArticle:()=>show(false),getArticle:async()=>({id:'a',title:'Ada and a new model'}),openArticle:()=>{},notice:message=>{throw Error(message)},
    api:async(path,method='GET',body)=>{
     calls.push({path,method,body});
     if(path.endsWith('/chat?purpose=research')){if(window.fixturePurpose!=='research'){window.explainState=state;state=window.researchState||{thread:'research-1234567890',purpose:'research',turns:[],questions:[],analysis:'',busy:null};}window.fixturePurpose='research';return structuredClone(state);}
     if(path.endsWith('/chat')&&window.fixturePurpose==='research'){window.researchState=state;state=window.explainState;window.fixturePurpose='explain';return structuredClone(state);}
     if(path.endsWith('/reset')){state={thread:'new-thread-123456789',turns:[],questions:[],analysis:'',busy:null};return structuredClone(state);}
     if(path.endsWith('/search/confirm'))return {confirmation_id:'confirmed-search'};
     if(path.endsWith('/search'))return {id:'prep',status:'completed',query:'Ada model evidence',fast_source:window.cloudFixture?'deepseek':'google',cloud_offer:window.cloudFixture?{available:true,price_version:'price-1',points_per_search:'1'}:{},sources:['google'],choices:[{id:'google',name:'Google'},{id:'deepseek',name:'DeepSeek'},{id:'bing',name:'Bing'}]};
     if(path.endsWith('/actions')&&method==='POST'){actions[body.request_id]=body;state.busy=body.request_id;return {status:'queued'};}
     if(path.includes('/actions/')){
      const action=actions[path.split('/').pop()];
      if(action.mode==='answer'&&action.question.startsWith('Find')&&!action.confirmation_id){state.pending_search={id:'prep',status:'completed',query:'Ada model evidence',question:action.question,fast_source:window.cloudFixture?'deepseek':'google',cloud_offer:window.cloudFixture?{available:true,price_version:'price-1',points_per_search:'1'}:{},choices:[{id:'google',name:'Google'},{id:'deepseek',name:'DeepSeek'},{id:'bing',name:'Bing'}]};}
      else if(action.mode==='answer'){delete state.pending_search;state.turns.push({question:action.question,answer:action.confirmation_id?'Read original sources [1]':'Article answer [1]',references:[{number:1,id:'a',title:'Article'}]});}
      else{state.topic_style=window.fixturePurpose==='research'?'research':'explain';state.analysis='Possible angles';state.questions=action.mode==='followup'?['What evidence is missing?']:['Who is Ada?','How does this model work?'];}
      state.busy=null;return {status:'completed'};
     }
     return structuredClone(state);
    }});
  });
  await page.locator('[data-article-chat]').click();
  await page.locator('[data-app-chat-suggestion="Who is Ada?"]').waitFor();
  assert.equal(await page.locator('.app-chat-intro').innerText(),'Possible angles');
  assert.equal(await page.locator('.intel-article-chat .chat-mini-embedded>header h1').isVisible(),width!==390);
  assert.equal(await page.locator('[data-app-chat-action="close"]').count(),0);
  assert.equal(await page.locator('.intel-article-chat .chat-mini-embedded>header p').isVisible(),true);
  const before=await page.evaluate(()=>calls.length);
  await page.locator('[data-app-chat-suggestion="Who is Ada?"]').click();
  assert.equal(await page.locator('[data-app-chat-input]').inputValue(),'Who is Ada?');
  assert.equal(await page.evaluate(()=>calls.length),before);
  await page.locator(width===390?'#test-back':'#test-article').click();
  assert.equal(await page.locator('.intel-article-chat').isVisible(),false);
  await page.locator(width===390?'[data-article-chat]':'#test-chat').click();
  assert.equal(await page.locator('[data-app-chat-input]').inputValue(),'Who is Ada?');
  assert.equal(await page.evaluate(()=>calls.length),before);
  assert.equal(await page.locator('dialog').count(),0);
  await page.locator('[data-app-chat-send]').click();
  assert.equal(await page.locator('[data-app-chat-suggestions]').isVisible(),false);
  await page.waitForFunction(()=>document.querySelector('[data-app-chat-messages]').textContent.includes('Article answer'));
  assert.equal(await page.locator('[data-app-chat-suggestions]').isVisible(),false);
  const userStyle=await page.locator('.chat-mini-message.user').first().evaluate(e=>({bg:getComputedStyle(e).backgroundColor,radius:getComputedStyle(e).borderRadius,width:e.getBoundingClientRect().width,parent:e.parentElement.getBoundingClientRect().width}));
  assert.equal(userStyle.bg,'rgb(23, 23, 23)');assert.equal(userStyle.radius,'18px');assert.ok(userStyle.width<userStyle.parent);
  assert.equal(await page.locator('[data-app-chat-action="followup"],[data-app-chat-action="search"]').count(),0);
  assert.equal(await page.locator('[data-app-chat-send]').innerText(),'');
  assert.ok(await page.locator('[data-app-chat-send]').getAttribute('aria-label'));
  await page.locator('[data-app-chat-input]').fill('Find background');
  await page.locator('[data-app-chat-send]').click();
  await page.locator('.app-chat-interaction:not([hidden])').waitFor();
  assert.equal(await page.evaluate(()=>calls.filter(c=>c.path.endsWith('/actions')&&c.body?.confirmation_id).length),0);
  assert.equal(await page.locator('.app-chat-interaction [name="source"] option').count(),1);
  assert.equal(await page.locator('.app-chat-interaction [name="source"]').inputValue(),'google');
  await page.locator('.app-chat-interaction [name="query"]').fill('Ada primary sources');
  await page.locator('.app-chat-interaction button[type="submit"]').click();
  await page.waitForFunction(()=>document.querySelector('[data-app-chat-messages]').textContent.includes('Read original sources'));
  assert.equal(await page.evaluate(()=>calls.find(c=>c.path.endsWith('/search/confirm')).body.query),'Ada primary sources');
  await page.evaluate(()=>window.cloudFixture=true);
  await page.locator('[data-app-chat-input]').fill('Find more background');
  await page.locator('[data-app-chat-send]').click();
  await page.locator('.app-chat-interaction [name="cloud_consent"]').waitFor();
  assert.equal(await page.locator('.app-chat-interaction [name="cloud_consent"]').inputValue(),'false');
  assert.equal(await page.locator('.app-chat-interaction [name="source"]').inputValue(),'deepseek');
  await page.locator('.app-chat-interaction [name="cloud_consent"]').selectOption('true');
  await page.locator('.app-chat-interaction button[type="submit"]').click();
  await page.waitForFunction(()=>calls.filter(c=>c.path.endsWith('/search/confirm')).length===2);
  assert.deepEqual(await page.evaluate(()=>{const b=calls.filter(c=>c.path.endsWith('/search/confirm')).at(-1).body;return [b.cloud_consent,b.cloud_price_version,b.cloud_max_points];}),[true,'price-1','1']);
  await page.waitForFunction(()=>!state.busy);

  await page.locator('[data-app-chat-action="reset"]').click();
  await page.locator('[data-app-chat-suggestion="Who is Ada?"]').waitFor();
  assert.equal(await page.locator('[data-app-chat-messages]').innerText(),'');
  assert.equal(await page.locator('[data-app-chat-input]').inputValue(),'');
  const box=await page.locator('.intel-article-chat').boundingBox();
  const composer=await page.locator('.chat-mini-form').boundingBox(),input=await page.locator('[data-app-chat-input]').boundingBox();
  assert.ok(input.x>=composer.x&&input.x+input.width<=composer.x+composer.width+1,'input fits shared composer');
  assert.equal(await page.locator('.chat-mini-embedded').count(),1);
  for(const selector of ['[data-app-chat-send]','[data-app-chat-action="reset"]']){
   const button=await page.locator(selector).boundingBox();assert.ok(button.y>=box.y&&button.y+button.height<=box.y+box.height+1);
  }
  assert.equal(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight),true);
  if(process.env.ARTICLE_CHAT_SCREENSHOT_DIR)await page.screenshot({path:process.env.ARTICLE_CHAT_SCREENSHOT_DIR+'/article-chat-'+width+'.png'});
  const explainThread=await page.evaluate(()=>state.thread);
  await page.evaluate(()=>IntelligenceArticleChat.open({id:'a',title:'Ada and a new model'},'research'));
  assert.equal(await page.evaluate(()=>IntelligenceArticleChat.currentTitle()),'Deep research');
  assert.equal(await page.evaluate(()=>state.thread),'research-1234567890');
  await page.locator('[data-app-chat-input]').fill('Research question');await page.locator('[data-app-chat-send]').click();
  await page.waitForFunction(()=>state.turns.length===1);
  await page.evaluate(()=>IntelligenceArticleChat.open({id:'a',title:'Ada and a new model'}));
  assert.equal(await page.evaluate(()=>state.thread),explainThread);
  assert.equal(await page.evaluate(()=>state.turns.length),0);
  assert.equal(await page.locator('.chat-mini-embedded').count(),1);
  await page.locator(width===390?'#test-back':'#test-article').click();assert.equal(await page.locator('.intel-article-chat').isVisible(),false);
 }finally{await browser.close();}
});

test('shared Mini-Entry surface renders arbitrary owner text safely and submits once',async()=>{
 const browser=await webkit.launch({headless:true});
 try{
  const page=await browser.newPage();await page.setContent('<div class="user-message-bubble">Full Chat</div><main id="host"></main>');
  await page.addStyleTag({content:read('web/static/css/chat_mini.css')});await page.addStyleTag({content:read('web/static/css/chat_message_stream.css')});
  await page.addScriptTag({content:read('web/static/js/mini_app_chat.js')});
  await page.evaluate(()=>{
   window.surface=AI2AppsMiniAppChat.createConversationSurface({root:document.querySelector('#host'),title:'Other owner',placeholder:'Question',sendLabel:'Send'});
   surface.renderTurns([{question:'<img src=x onerror="window.executed=true">',answer:'<script>bad()</script>'}]);
   window.submits=0;surface.form.onsubmit=event=>{event.preventDefault();submits++;};
  });
  assert.equal(await page.locator('.chat-mini-message img,.chat-mini-message script').count(),0);
  assert.match(await page.locator('.chat-mini-message.user').innerText(),/<img/);
  const styles=await page.evaluate(()=>['.user-message-bubble','.chat-mini-message.user'].map(selector=>{const s=getComputedStyle(document.querySelector(selector));return [s.backgroundColor,s.color,s.borderRadius,s.padding,s.lineHeight];}));
  assert.deepEqual(styles[0],styles[1]);
  await page.locator('textarea').fill('Question');await page.locator('textarea').press('Control+Enter');
  assert.equal(await page.evaluate(()=>submits),1);
 }finally{await browser.close();}
});

test('research button waits for topics then transfers a frozen seed to the Chat host',async()=>{
 const browser=await webkit.launch({headless:true});try{
  const page=await browser.newPage();
  await page.route('https://research.test/**',route=>route.fulfill({contentType:'text/html',body:route.request().url().includes('/article')?'<button data-article-chat="a" data-article-chat-purpose="research">Research</button>':'<iframe src="/article#ai2apps-mount=mount&ai2apps-instance=instance"></iframe>'}));
  await page.goto('https://research.test');
  await page.evaluate(()=>{window.received=[];addEventListener('message',event=>{if(event.source!==document.querySelector('iframe').contentWindow||event.origin!==location.origin||event.data.type!=='ai2apps.shell.open-chat-context')return;received.push(event.data);event.source.postMessage({type:'ai2apps.host.response',requestId:event.data.requestId,mountToken:'mount',ok:true,result:{threadId:'ses_new'}},location.origin);});});
  const frame=page.frames().find(f=>f.url().includes('/article'));
  await frame.addScriptTag({content:read('web/static/js/intelligence_article_chat.js')});
  await frame.evaluate(()=>{
   window.IntelligenceI18n={format:key=>key};window.done=false;window.calls=[];const snapshot={thread:'research-thread-123',questions:[],topic_style:'research',busy:null,turns:[]};
   IntelligenceArticleChat.init({getArticle:async()=>({id:'a'}),notice:message=>{throw Error(message)},api:async(path,method,body)=>{
    calls.push({path,method,body});
    if(path.endsWith('/actions')){snapshot.busy=body.request_id;return {};}
    if(path.includes('/actions/')){if(!done)return {status:'queued'};snapshot.busy=null;snapshot.questions=['Compare the evidence'];return {status:'completed'};}
    if(path.endsWith('/research-handoff'))return {chat_seed:{title:'Article research',legacy_thread_id:'frozen-request',session_metadata:{agentMode:true,starterSuggestions:snapshot.questions},legacy_messages:[{role:'user',content:'Article context',metadata:{}}]}};
    return structuredClone(snapshot);
   }});
  });
  await frame.locator('[data-article-chat]').click();
  await frame.locator('dialog[open]').waitFor();assert.equal(await page.evaluate(()=>received.length),0);
  await frame.evaluate(()=>{done=true;});
  await page.waitForFunction(()=>received.length===1);
  assert.equal(await page.evaluate(()=>received[0].chatSeed.session_metadata.agentMode),true);
  assert.deepEqual(await page.evaluate(()=>received[0].chatSeed.session_metadata.starterSuggestions),['Compare the evidence']);
  await frame.locator('dialog').waitFor({state:'detached'});
  assert.equal(await frame.locator('.intel-article-chat').count(),0);
 }finally{await browser.close();}
});
