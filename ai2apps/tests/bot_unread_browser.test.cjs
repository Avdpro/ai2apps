const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
const read=(dir,file)=>fs.readFileSync(path.join(__dirname,'../web/static',dir,file),'utf8');
test('first unread anchors beyond recent 50; history preserves unread; only visible bottom acknowledges loaded messages; task reference edits control the sent message',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.setContent('<html lang="en"><main style="height:450px"></main></html>');await page.addStyleTag({content:read('css','messager.css')});
 await page.evaluate(()=>{
  Object.defineProperty(window,'localStorage',{value:{getItem:()=>null,setItem(){}}});window.errors=[];window.readPosts=[];window.turns=[];Object.defineProperty(crypto,'randomUUID',{value:()=> 'fixture-turn-id'});window.cursor=20;window.latest=100;window.fixtureHidden=false;Object.defineProperty(document,'hidden',{get:()=>fixtureHidden});
  const unread=()=>({read_sequence:cursor,unread_count:latest-cursor,first_unread_sequence:cursor<latest?cursor+1:null,latest_sequence:latest});
  window.fetch=async(url,options={})=>{let value={items:[]};if(url.endsWith('/app-chat/sessions'))value={session_id:'session'};
   else if(url.includes('/unread?'))value=unread();else if(url.endsWith('/read')){cursor=Math.max(cursor,JSON.parse(options.body).through_sequence);readPosts.push(cursor);value=unread();}
   else if(url.includes('/messages')){const u=new URL(url,'https://fixture');let first=u.searchParams.has('after')?Number(u.searchParams.get('after'))+1:Math.max(1,latest-49),last=latest;if(u.searchParams.has('before')){last=Number(u.searchParams.get('before'))-1;first=Math.max(1,last-49);}value={items:Array.from({length:Math.max(0,Math.min(50,last-first+1))},(_,i)=>({id:'m'+(first+i),sequence:first+i,role:'assistant',content:'Reply '+(first+i)+' '+('paragraph '.repeat(15))})),has_more:last-first+1>50};}
   else if(url.includes('/task-sessions?'))value={items:[{id:'task-ref-1',title:'Watch report'}]};
   else if(url.endsWith('/dialogue/turns')){turns.push(JSON.parse(options.body));value={run_id:'fixture-run'};}
   else if(url.includes('/state'))value={runs:[],task_sessions:[{id:'task-ref-1',title:'Watch report'}]};return {ok:true,json:async()=>value};};
  window.AI2AppsBotModelSelection={resolve:async()=>({allModels:[],models:[{id:'fixture'}],selected:'fixture',notice:''})};window.AI2AppsBotMaterials={attachments(){},enhance(){},dispose(){}};window.AI2AppsBotTaskFeed={create:()=>({update(){},dispose(){}})};window.AI2AppsMiniAppChat={bindMessageActions:()=>({attach(){},dispose(){}})};window.AI2AppsBotInteractions={release(){}};
 });
 for(const file of ['bot_composer.js','bot_conversation.js'])await page.addScriptTag({content:read('js',file)});
 await page.evaluate(async()=>{window.controller=await AI2AppsBotConversation.create({bot:{id:'one'},root:document.querySelector('main'),onState:v=>window.lastState=v,onError:e=>errors.push(e.message)});});
 await page.locator('[data-message-id="m100"]').waitFor();assert.equal(await page.locator('.bot-unread-divider').textContent(),'Unread messages');assert.equal(await page.evaluate(()=>readPosts.length),0);
 const anchor=await page.locator('.bot-unread-divider').evaluate(e=>e.getBoundingClientRect().top-e.closest('.bot-message-stream').getBoundingClientRect().top);assert(Math.abs(anchor)<50);
 const jump=page.getByRole('button',{name:'Scroll to latest message',exact:true});await jump.waitFor();await jump.click();await page.waitForFunction(()=>cursor===100);assert.equal(await jump.isVisible(),false);assert.equal(await page.locator('.bot-unread-divider').count(),0);
 await page.evaluate(async()=>{fixtureHidden=true;latest=101;await controller.refresh(true);});assert.equal(await page.evaluate(()=>cursor),100);
 await page.evaluate(()=>{fixtureHidden=false;document.dispatchEvent(new Event('visibilitychange'));});await page.locator('.bot-message-stream').evaluate(e=>e.scrollTop=e.scrollHeight);await page.waitForFunction(()=>cursor===101);
 const draft=page.getByRole('textbox',{name:'Message…'});
 await draft.fill('/#Watch');
 await page.getByRole('button',{name:'Watch report',exact:true}).waitFor({timeout:5000});
 await draft.press('ArrowDown');await draft.press('Enter');
 assert.equal(await draft.inputValue(),'/#task-ref-1 ');
 assert.equal(await page.evaluate(()=>turns.length),0);
 await draft.fill('a draft');
 await page.evaluate(()=>controller.continueTask({id:'task-ref-1',title:'Watch report'}));
 assert.equal(await draft.inputValue(),'Continue /#task-ref-1 a draft');
 await page.getByRole('button',{name:'Remove continuation reference'}).click();
 assert.equal(await draft.inputValue(),'a draft');
 await page.getByRole('button',{name:'Send',exact:true}).click();
 await page.waitForFunction(()=>turns.length===1,{},{timeout:5000});
 const turn=await page.evaluate(()=>turns[0]);assert.equal(turn.text,'a draft');assert.equal(turn.task_session_id,undefined);
 assert.deepEqual(await page.evaluate(()=>errors),[]);await page.evaluate(()=>controller.dispose());
 }finally{await browser.close();}
});
