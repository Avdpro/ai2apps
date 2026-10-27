const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {webkit}=require('playwright');
const read=p=>fs.readFileSync(__dirname+'/../'+p,'utf8');
for(const width of [390,1280])test('old article search help is never shown in shared Mini-Chat at '+width,async()=>{
 const browser=await webkit.launch({headless:true});try{
  const page=await browser.newPage({viewport:{width,height:820}});
  await page.route('https://help.test/**',r=>r.fulfill({contentType:'text/html',body:'<meta name="viewport" content="width=device-width,initial-scale=1"><main id="reader"></main>'}));
  await page.goto('https://help.test/#ai2apps-mount=mount&ai2apps-instance=instance');
  await page.evaluate(catalog=>{window.IntelligenceI18n={format:k=>catalog[k]||k};window.messages=[];window.addEventListener('message',e=>messages.push(e.data));},JSON.parse(read('web/i18n/en.json')));
  await page.addScriptTag({content:read('web/static/js/mini_app_chat.js')});await page.addScriptTag({content:read('web/static/js/intelligence_article_chat.js')});
  await page.evaluate(async()=>{
   IntelligenceArticleChat.init({panelRoot:document.querySelector('#reader'),showPanel(){IntelligenceArticleChat.setVisible(true)},showArticle(){},notice(){},
    api:async()=>({thread:'thread-123456789',turns:[],questions:['Question'],analysis:'',topic_style:'explain',busy:null,
      reading_assistance:[{task_id:'btask_help',requires_user:true,assistance_kind:'authentication'}]})});
   await IntelligenceArticleChat.open({id:'article',title:'Article'});
  });
  assert.equal(await page.getByText('This page requires sign-in.',{exact:false}).count(),0);
  assert.equal(await page.getByRole('button',{name:'Open page requiring help'}).count(),0);
  assert.equal(await page.evaluate(()=>messages.some(m=>m.type==='ai2apps.shell.open-browser-task')),false);
 }finally{await browser.close();}
});
test('Browser App selects only a task in the authenticated workspace',()=>{
 const context={window:{innerWidth:1000},document:{},console,crypto:require('node:crypto').webcrypto};vm.createContext(context);vm.runInContext(read('web/static/js/ai_browser.js'),context);
 const app=context.aiBrowserApp();const opened=[];app.openTask=t=>opened.push(t.id);app.tasks=[{id:'btask_owned'}];
 app.pendingTaskId='btask_other';app.consumeTaskIntent();assert.deepEqual(opened,[]);
 app.pendingTaskId='btask_owned';app.consumeTaskIntent();assert.deepEqual(opened,['btask_owned']);assert.equal(app.pendingTaskId,null);
});
