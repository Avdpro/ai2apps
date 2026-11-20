const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
const read=p=>fs.readFileSync(path.join(__dirname,'../web/static/js',p),'utf8');
test('Flash shows a pending submission and preserves the next draft while speech discovery stalls',{timeout:15000},async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage();await page.setContent('<html lang="en"><main></main></html>');
 await page.evaluate(()=>{
  Object.defineProperty(window,'localStorage',{value:{getItem:()=>null,setItem(){}}});
  Object.defineProperty(window.crypto,'randomUUID',{value:()=> 'fixture-request-0001'});
  window.errors=[];window.submissions=[];window.output=false;
  const processing=new Promise(resolve=>{window.finishSubmission=resolve;});
  window.fetch=async(url,options={})=>{
   if(url==='/admin/api/models')return new Promise(()=>{});
   if(url.endsWith('/dialogue/turns')){const body=JSON.parse(options.body);submissions.push(body);if(submissions.length>1)return {ok:false,json:async()=>({message:'Turn rejected'})};await processing;output=true;return {ok:true,json:async()=>({run_id:'flash-request'})};}
   const items=output?[{id:'user',sequence:1,role:'user',content:submissions[0].text,client_request_id:submissions[0].request_id},{id:'answer',sequence:2,role:'assistant',content:'(2 + 3) * 4 = 20'}]:[];
   return {ok:true,json:async()=>url.endsWith('/app-chat/sessions')?{session_id:'session'}:url.includes('/messages')?{items,has_more:false}:url.includes('/state')?{runs:window.runs||[]}:{items:[]}};
  };
  window.AI2AppsBotModelSelection={resolve(){throw Error('Calculator must not fetch models');},forBot(){throw Error('Calculator must not fetch models');}};
  window.AI2AppsBotMaterials={attachments(){},enhance(){}};window.AI2AppsBotTaskFeed={create:()=>({update(){},dispose(){}})};
  window.AI2AppsMiniAppChat={bindMessageActions:()=>({attach(){},dispose(){}})};window.AI2AppsBotInteractions={release(){}};
 });
 await page.addScriptTag({content:read('bot_composer.js')});await page.addScriptTag({content:read('bot_conversation.js')});
 await page.addStyleTag({content:fs.readFileSync(path.join(__dirname,'../web/static/css/messager.css'),'utf8')});
 await page.evaluate(async()=>{window.controller=await AI2AppsBotConversation.create({bot:{id:'calc',definition:{execution_mode:'flash'}},root:document.querySelector('main'),onState(){},onError:e=>errors.push(e.message)});});
 assert.equal(await page.getByRole('button',{name:'Add attachments',exact:true}).isVisible(),true);assert.equal(await page.getByRole('button',{name:'Voice input',exact:true}).isVisible(),true);
 assert.equal(await page.getByRole('button',{name:'Add attachments',exact:true}).isEnabled(),true);assert.equal(await page.getByRole('button',{name:'Voice input',exact:true}).isEnabled(),true);
 const textbox=page.getByRole('textbox'),send=page.getByRole('button',{name:'Send',exact:true});
 const processing=page.getByText('Sending to Flash-Bot…',{exact:true});
 const waitingBubble=page.locator('[data-pending-request-id] .user-message-bubble');
 await textbox.fill('(2 + 3) * 4');await send.click();await processing.waitFor();
 assert.equal(await waitingBubble.textContent(),'(2 + 3) * 4');
 assert.equal(await send.isDisabled(),true);
 await textbox.fill('5 * 7');await textbox.press('Enter');
 assert.equal(await page.evaluate(()=>submissions.length),1);
 await page.evaluate(()=>finishSubmission());await page.getByText('(2 + 3) * 4 = 20',{exact:true}).waitFor();
 assert.equal(await waitingBubble.count(),0);
 assert.equal(await page.locator('.user-message-bubble').count(),1);
 assert.equal(await processing.isVisible(),false);assert.equal(await send.isEnabled(),true);
 assert.equal(await textbox.inputValue(),'5 * 7');assert.equal(await page.evaluate(()=>submissions.length),1);assert.deepEqual(await page.evaluate(()=>errors),[]);
 await page.evaluate(async()=>{
  window.runs=[{id:'failed-run',status:'failed',interactions:[],error_details:{code:'flash_missing_binding'}}];
  await controller.refresh(true);
 });
 const errorDetails=page.locator('.flash-error-details');
 await errorDetails.getByText('Error details').waitFor();
 for(const width of [1200,480]){
  await page.setViewportSize({width,height:800});
  const [details,list]=await Promise.all([errorDetails.boundingBox(),page.locator('.bot-message-list').boundingBox()]);
  assert.ok(Math.abs(details.x-list.x)<1,'Error details align with the message list');
 }
 await errorDetails.getByText('Error details').click();
 assert.equal(await errorDetails.getByText(/flash_missing_binding/).isVisible(),true);
 await page.evaluate(async()=>{
  window.runs.push({id:'next-run',status:'running',interactions:[]});
  await controller.refresh(true);
 });
 await errorDetails.waitFor({state:'detached'});
 await send.click();
 await page.waitForFunction(()=>errors.includes('Turn rejected'));
 assert.equal(await waitingBubble.count(),0);
 assert.equal(await textbox.inputValue(),'5 * 7');
 await page.evaluate(()=>controller.dispose());
 }finally{await browser.close();}
});

test('Flash conversation reviews the exact draft, supports cancel, and activates only on confirmation',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width:900,height:800}});await page.setContent('<html lang="en"><main></main></html>');await page.addStyleTag({content:fs.readFileSync(path.join(__dirname,'../web/static/css/bot_creation.css'),'utf8')});
 await page.evaluate(()=>{
  Object.defineProperty(window,'localStorage',{value:{getItem:()=>null,setItem(){}}});
  let requestNumber=0;Object.defineProperty(window.crypto,'randomUUID',{value:()=> 'fixture-request-'+(++requestNumber)});window.errors=[];window.submissions=[];window.activations=[];
  const plan={name:'Heading translator',usage:'Translate text with a heading',input_kind:'text',steps:[{kind:'ai',instruction:'Translate and add a heading',arguments:{}}]};
  window.fetch=async(url,options={})=>{
   let value={items:[]};
   if(url.endsWith('/dialogue/turns')){submissions.push(JSON.parse(options.body));value={kind:'workflow_review',expected_revision:3,previous_plan:{usage:'Translate text'},draft:{review_id:'b'.repeat(64),role:'Translate and add a heading',model:'fixture',apps:[],plan}};}
   else if(url.endsWith('/flash-workflow')){activations.push(JSON.parse(options.body));value={execution_mode:'flash',revision:4,config:{plan,model:'fixture'}};}
   else if(url.endsWith('/compile'))throw Error('Already reviewed draft must not be recompiled');
   else if(url.endsWith('/app-chat/sessions'))value={session_id:'session'};
   else if(url.includes('/messages'))value={items:[],has_more:false};
   else if(url.includes('/state'))value={runs:[]};
   return {ok:true,json:async()=>value};
  };
  window.AI2AppsBotMaterials={attachments(){},enhance(){}};window.AI2AppsBotTaskFeed={create:()=>({update(){},dispose(){}})};
  window.AI2AppsMiniAppChat={bindMessageActions:()=>({attach(){},dispose(){}})};window.AI2AppsBotInteractions={release(){}};
 });
 for(const script of ['bot_creation.js','bot_composer.js','bot_conversation.js'])await page.addScriptTag({content:read(script)});
 await page.evaluate(async()=>{window.controller=await AI2AppsBotConversation.create({bot:{id:'flash',definition:{execution_mode:'flash',config:{plan:{usage:'Translate text'}}}},root:document.querySelector('main'),onState(){},onError:e=>errors.push(e.message)});});
 assert.equal(await page.getByRole('button',{name:/^(Edit|Run) workflow$/}).count(),0);await page.getByRole('textbox').fill('Add headings to future translations');await page.getByRole('button',{name:'Send',exact:true}).click();await page.waitForFunction(()=>document.querySelector('dialog')||errors.length);assert.deepEqual(await page.evaluate(()=>errors),[]);
 assert.equal(await page.getByText('Proposed changes',{exact:true}).isVisible(),true);assert.equal(await page.evaluate(()=>activations.length),0);
 await page.getByRole('button',{name:'Edit',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('dialog'));await page.waitForFunction(()=>document.querySelector('textarea').value==='');
 await page.getByRole('textbox').fill('Add headings to future translations');await page.getByRole('button',{name:'Send',exact:true}).click();await page.getByRole('button',{name:'Confirm workflow',exact:true}).click();await page.waitForFunction(()=>activations.length===1);
 assert.equal(await page.evaluate(()=>submissions[0].workflow_edit),undefined);assert.equal(await page.evaluate(()=>activations[0].expected_revision),3);assert.equal(await page.evaluate(()=>activations[0].review_id),'b'.repeat(64));assert.deepEqual(await page.evaluate(()=>errors),[]);
 await page.evaluate(()=>controller.dispose());
 }finally{await browser.close();}
});
