const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
const asset=name=>fs.readFileSync(path.join(__dirname,'../web/static',name),'utf8');
test('Desktop and 390px trim dialogs require confirmation, retain scope and support cleanup retry',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{for(const width of [1200,390]){
  const page=await browser.newPage({viewport:{width,height:800}});
  await page.setContent('<html lang="en"><head></head><body><div id="toolbar"></div></body></html>');
  await page.addStyleTag({content:asset('css/chat_message_feedback.css')});
  await page.addScriptTag({content:asset('js/bot_conversation_trim.js')});
  await page.evaluate(()=>{window.calls=[];window.refreshed=0;window.AI2AppsConversationTrim.attach({toolbar:document.querySelector('#toolbar'),botId:'test',sessionId:'sid',item:{id:'anchor',content:'Keep this exact reply'},label:(_,en)=>en,onError:e=>{throw e;},refresh:async()=>window.refreshed++,request:async(path,method,body)=>{calls.push({path,body});if(path.endsWith('/review'))return {deleted_messages:3,deleted_materials:2,review_hash:'hash'};return {cleanup_pending:calls.filter(c=>c.path.endsWith('/apply')).length===1?1:0};}});});
  await page.getByRole('button',{name:'Trim later conversation'}).click();
  await page.getByRole('dialog').waitFor();assert.equal(await page.evaluate(()=>calls.length),1);
  assert.match(await page.getByRole('dialog').innerText(),/Access, memory and Tasks stay unchanged/);
  assert.match(await page.getByRole('dialog').innerText(),/3 messages and 2 materials/);
  const box=await page.getByRole('dialog').boundingBox();assert(box.width<=width-24);
  await page.getByRole('button',{name:'Cancel',exact:true}).click();assert.equal(await page.evaluate(()=>calls.length),1);
  await page.getByRole('button',{name:'Trim later conversation'}).click();
  await page.getByRole('button',{name:'Trim conversation',exact:true}).click();
  await page.getByRole('button',{name:'Retry material cleanup'}).waitFor();
  await page.getByRole('button',{name:'Retry material cleanup'}).click();
  await page.waitForFunction(()=>refreshed===2);assert.equal(await page.getByRole('dialog').count(),0);
  const applies=await page.evaluate(()=>calls.filter(c=>c.path.endsWith('/apply')));assert.equal(applies.length,2);assert.deepEqual(applies[0].body,applies[1].body);
  await page.screenshot({path:'/tmp/bot-trim-'+width+'.png'});await page.close();
 }}finally{await browser.close();}
});
test('Poke is visible during an unresolved request and persistence replaces it without duplication',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.goto('http://127.0.0.1:1').catch(()=>{});
 await page.route('https://bot.fixture/**',async route=>{
  const u=new URL(route.request().url());if(u.pathname==='/')return route.fulfill({body:'<html lang="en"><div id="host"></div></html>',contentType:'text/html'});
  return route.fulfill({json:{}});
 });await page.goto('https://bot.fixture/');
 await page.evaluate(()=>{
  window.historyFixture=[{id:'anchor',sequence:1,role:'assistant',content:'Anchor'}];window.pendingPokeResolve=null;window.errors=[];
  window.fetch=async(url,options={})=>{let value={};if(url.endsWith('/app-chat/sessions'))value={session_id:'sid'};else if(url.includes('/messages')){const after=Number(new URL(url,location.origin).searchParams.get('after')||0);value={items:historyFixture.filter(m=>m.sequence>after),has_more:false,conversation_revision:0};}else if(url.includes('/dialogue/state'))value={runs:[]};else if(url.endsWith('/poke')){const request=JSON.parse(options.body);await new Promise(r=>pendingPokeResolve=r);window.acceptedPoke=request;window.postReturned=true;}return {ok:true,json:async()=>value};};
  window.AI2AppsConversationTrim={attach(options){window.trimRefresh=options.refresh;}};
  window.AI2AppsBotModelSelection={resolve:async()=>({models:[{id:'fixture'}],selected:'fixture',allModels:[]})};
  window.AI2AppsBotInteractions={release(){}};window.AI2AppsBotTaskFeed={create:()=>({update(){},dispose(){}})};window.AI2AppsBotMaterials={attachments(){},enhance(){}};
  window.AI2AppsMiniAppChat={bindMessageActions:()=>({attach(article){const toolbar=document.createElement('div');article.append(toolbar);return {toolbar};},dispose(){}})};
  window.AI2AppsBotComposer={create(options){const poke=document.createElement('button');poke.type='button';poke.textContent='Poke Bot';poke.onclick=options.onPoke;options.form.append(poke);let busy=false,pokeBusy=false;return {blocked:()=>false,hasFiles:()=>false,setBusy(value){busy=value;poke.disabled=busy||pokeBusy;},setPokeBusy(value){pokeBusy=value;poke.disabled=busy||pokeBusy;},setModels(){},dispose(){}};}};
 });
 await page.addScriptTag({content:asset('js/bot_conversation.js')});
 await page.evaluate(async()=>{window.controller=await AI2AppsBotConversation.create({bot:{id:'bot'},root:document.querySelector('#host'),onState(){},onError:e=>errors.push(e.message)});});
 await page.getByRole('button',{name:'Poke Bot',exact:true}).click();
 await page.waitForFunction(()=>typeof pendingPokeResolve==='function');
 assert.equal(await page.locator('.user-message-bubble').count(),1);assert.equal(await page.locator('.user-message-bubble').innerText(),'👋 Poke');
 assert.equal(await page.getByRole('button',{name:'Poke Bot',exact:true}).isDisabled(),true);
 await page.evaluate(()=>pendingPokeResolve());await page.waitForFunction(()=>postReturned===true);
 assert.equal(await page.getByRole('button',{name:'Poke Bot',exact:true}).isDisabled(),true);
 await page.evaluate(async()=>{historyFixture.push({id:'poke',sequence:2,role:'user',content:'👋 Poke',client_request_id:acceptedPoke.request_id});await controller.refresh(true);});
 await page.waitForFunction(()=>!!document.querySelector('[data-message-id="poke"]'));
 await page.waitForFunction(()=>!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Poke Bot').disabled);
 assert.equal(await page.locator('.user-message-bubble').count(),1);assert.deepEqual(await page.evaluate(()=>errors),[]);
 // A durable trim receipt can remove a Poke before the ordinary message poll sees it.
 await page.evaluate(()=>postReturned=false);await page.getByRole('button',{name:'Poke Bot',exact:true}).click();
 await page.evaluate(()=>pendingPokeResolve());await page.waitForFunction(()=>postReturned===true);
 assert.equal(await page.getByRole('button',{name:'Poke Bot',exact:true}).isDisabled(),true);
 await page.evaluate(async()=>{historyFixture=historyFixture.filter(m=>m.id==='anchor');await trimRefresh({retired_request_ids:[acceptedPoke.request_id]});});
 await page.waitForFunction(()=>!Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='Poke Bot').disabled);
 assert.equal(await page.locator('.user-message-bubble').count(),0);
 await page.evaluate(()=>controller.dispose());
 }finally{await browser.close();}
});
test('compact name tips anchor beside the avatar and disappear on expansion',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage({viewport:{width:1000,height:700}});
 await page.setContent('<html><body><section id="shell" class="sidebar-compact" style="width:950px"><button class="messager-bot-card" aria-label="Long Bot name" style="width:150px;height:70px;text-align:left"><img class="messager-avatar" style="width:36px;height:36px;margin-left:15px"></button><button class="bot-group-toggle" aria-label="My full group name">Group</button><div id="handle" tabindex="0"></div></section></body></html>');
 await page.addStyleTag({content:asset('css/messager.css')});await page.addScriptTag({content:asset('js/messager_sidebar.js')});
 await page.evaluate(()=>{window.controller=AI2AppsMessagerSidebar.mount({shell:document.querySelector('#shell'),handle:document.querySelector('#handle'),onWidth:width=>document.querySelector('#shell').classList.toggle('sidebar-compact',width<168)});});
 await page.locator('#handle').press('Home');await page.locator('.messager-bot-card').hover();await page.getByRole('tooltip').waitFor();
 assert.equal(await page.getByRole('tooltip').textContent(),'Long Bot name');
 const avatar=await page.locator('.messager-avatar').boundingBox(),tip=await page.getByRole('tooltip').boundingBox();assert(Math.abs(tip.x-avatar.x-avatar.width-8)<1);
 await page.locator('.bot-group-toggle').focus();assert.equal(await page.getByRole('tooltip').textContent(),'My full group name');
 await page.locator('#handle').press('End');assert.equal(await page.getByRole('tooltip').count(),0);
 }finally{await browser.close();}
});
