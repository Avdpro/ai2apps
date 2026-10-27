const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright'),root=path.join(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,'web/static/js',f),'utf8');
test('shared surface restores background answer after page close; UI command applied once',async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.AI2APPS_TEST_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{
  const context=await browser.newContext();const errors=[],calls=[];
  const state={session_id:'session-1',scope:{directory_id:'d'},owner:'fixture.chat',version:'1',ui_revision:1,ui:{search:''},messages:[],runs:[],commands:[],tools:['fixture.query']};
  let accepted=0,ack=0,finish;
  await context.route('https://appchat.test/**',async route=>{
   const req=route.request(),u=new URL(req.url()),p=u.pathname;calls.push(p);
   if(p==='/v1/models')return route.fulfill({json:{data:[{id:'fixture-model'}]}});
   if(p==='/admin/api/model-manager')return route.fulfill({json:{defaults:{work_standard:'fixture-model'}}});
   if(p.includes('/cloud/ai/defaults'))return route.fulfill({json:{}});
   if(p.endsWith('/turns')){accepted++;state.runs=[{id:'run-1',status:'running',text:'后台读取',interactions:[]}];state.messages=[{id:'u',role:'user',content:req.postDataJSON().text}];return route.fulfill({json:{run_id:'run-1'}});}
   if(p.endsWith('/ui')&&req.method()==='PUT'){state.ui=req.postDataJSON().ui;return route.fulfill({json:state});}
   if(p.includes('/ui/command-1')){ack++;state.commands=[];return route.fulfill({json:{status:'applied'}});}
   if(p.startsWith('/v1/platform/app-chat/'))return route.fulfill({json:state});
   return route.fulfill({contentType:'text/html',body:'<meta charset="utf-8"><main id="chat"></main>'});
  });
  async function open(){const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto('https://appchat.test');
   await page.addScriptTag({content:read('mini_app_chat.js')});await page.addScriptTag({content:read('app_chat.js')});
   await page.evaluate(async()=>{window.ui={search:''};window.applies=0;window.c=await AI2AppsAppChat.create({appId:'fixture.app',registration:'fixture.chat',title:'Fixture',scope:()=>({directory_id:'d'}),readUI:()=>ui,applyUI:async args=>{applies++;ui.search=args.query;return ui;}});window.view=AI2AppsMiniAppChat.mount({root:document.querySelector('#chat'),transport:c});});return page;
  }
  let page=await open();await page.locator('[data-app-chat-input]').fill('读取项目');await page.locator('[data-app-chat-send]').click();
  await page.waitForFunction(()=>document.body.textContent.includes('后台读取'));
  await page.close();
  // Server completion has no page or client callback.
  state.runs[0].status='completed';state.runs[0].text='Completed';state.messages.push({id:'a',role:'assistant',content:'关闭页面后完成的结果',format:'markdown'});
  page=await open();await page.locator('[data-message-id="a"]').waitFor();assert.match(await page.locator('body').innerText(),/关闭页面后完成/);assert.equal(accepted,1);
  const mount=await page.evaluate(()=>c.invoke('describe').then(s=>s.binding.sessionId));assert.equal(mount,'session-1');
  // Read the actual mount from the last heartbeat, rather than inventing it.
  let actualMount;const extra=async route=>{actualMount=route.request().postDataJSON().mount;state.ui=route.request().postDataJSON().ui;await route.fulfill({json:state});};
  await page.route('https://appchat.test/v1/platform/app-chat/sessions/session-1/ui',extra);
  await page.waitForFunction(()=>document.querySelector('[data-app-chat-input]')!==null);await new Promise(r=>setTimeout(r,1400));
  assert.ok(actualMount);state.commands=[{id:'command-1',mount:actualMount,revision:1,arguments:{action:'set_search',query:'Bound'}}];
  await page.waitForFunction(()=>applies===1);await new Promise(r=>setTimeout(r,1400));assert.equal(await page.evaluate(()=>applies),1);assert.equal(ack,1);
  assert.ok(!calls.includes('/v1/chat/completions'));assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
