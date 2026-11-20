const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
const read=p=>fs.readFileSync(path.join(__dirname,'../web/static/js',p),'utf8');
test('history and full composer appear while the model catalog is still pending',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage();await page.setContent('<html lang="en"><main></main></html>');
  await page.evaluate(()=>{
   Object.defineProperty(window,'localStorage',{value:{getItem:()=>null,setItem(){}}});
   window.errors=[];
   window.fetch=async url=>({ok:true,json:async()=>url.endsWith('/app-chat/sessions')?{session_id:'session'}:url.includes('/messages')?{items:[{id:'msg',sequence:1,role:'assistant',content:'History already available'}],has_more:false}:url.includes('/state')?{runs:[]}:{items:[]}});
   window.AI2AppsBotModelSelection={resolve:()=>new Promise(r=>window.finishModels=()=>r({allModels:[],models:[{id:'fixture'}],selected:'fixture',notice:''}))};
   window.AI2AppsBotMaterials={attachments(){},enhance(){}};
   window.AI2AppsBotTaskFeed={create:()=>({update(){},dispose(){}})};
   window.AI2AppsMiniAppChat={bindMessageActions:()=>({attach(){},dispose(){}})};
   window.AI2AppsBotInteractions={release(){}};
  });
  await page.addScriptTag({content:read('bot_composer.js')});await page.addScriptTag({content:read('bot_conversation.js')});
  await page.evaluate(()=>{window.opening=AI2AppsBotConversation.create({bot:{id:'one'},root:document.querySelector('main'),onState(){},onError:e=>errors.push(e.message)});});
  await page.getByText('History already available').waitFor();
  assert.equal(await page.getByRole('button',{name:'Add attachments',exact:true}).count(),1);
  assert.equal(await page.getByRole('button',{name:'Voice input',exact:true}).count(),1);
  assert.equal(await page.getByRole('button',{name:'Send',exact:true}).isEnabled(),false);
  await page.getByRole('textbox').fill('Draft survives catalog loading');
  await page.evaluate(()=>finishModels());await page.evaluate(async()=>{window.controller=await opening;});
  assert.equal(await page.getByRole('textbox').inputValue(),'Draft survives catalog loading');
  assert.equal(await page.getByRole('button',{name:'Send',exact:true}).isEnabled(),true);
  assert.deepEqual(await page.evaluate(()=>errors),[]);
  await page.evaluate(()=>controller.dispose());
 }finally{await browser.close();}
});

test('five-entry LRU restores older messages and scroll immediately, then refreshes without jumping',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage();await page.setContent('<html lang="en"><main style="height:400px"></main></html>');
  await page.addStyleTag({content:fs.readFileSync(path.join(__dirname,'../web/static/css/messager.css'),'utf8')});
  await page.evaluate(()=>{
   Object.defineProperty(window,'localStorage',{value:{getItem:()=>null,setItem(){}}});
   window.errors=[];window.hold=false;window.empty=false;
   window.fetch=async(url,options={})=>{
    if(url.endsWith('/app-chat/sessions')){
     const bot=JSON.parse(options.body).scope.bot_id;
     if(window.deny)return {ok:false,json:async()=>({detail:'Access revoked'})};
     if(hold)await new Promise(r=>window.releaseSession=r);
     return {ok:true,json:async()=>({session_id:bot})};
    }
    let value={items:[]};
    if(url.includes('/messages')){
     if(window.failHistory){window.failHistory=false;return {ok:false,json:async()=>({detail:'History unavailable'})};}
     const bot=url.match(/sessions\/([^/]+)\/messages/)[1],older=url.includes('before=');
     value={items:empty||url.includes('after=')?[]:Array.from({length:older?30:50},(_,i)=>{const n=i+(older?1:31);return {id:bot+'-'+n,sequence:n,role:'assistant',content:bot+' message '+n};}),has_more:!older};
    }else if(url.includes('/state'))value={runs:[]};
    return {ok:true,json:async()=>value};
   };
   window.AI2AppsBotModelSelection={resolve:async()=>{if(window.holdModel)await new Promise(r=>window.releaseModel=r);return {allModels:[],models:[{id:'fixture'}],selected:'fixture',notice:''};}};
   window.AI2AppsBotMaterials={attachments(){},enhance(){}};
   window.AI2AppsBotTaskFeed={create:()=>({update(){},dispose(){}})};
   window.AI2AppsMiniAppChat={bindMessageActions:()=>({attach(){},dispose(){}})};
   window.AI2AppsBotInteractions={release(){}};
  });
  await page.addScriptTag({content:read('bot_composer.js')});await page.addScriptTag({content:read('bot_conversation.js')});
  await page.evaluate(()=>{
   window.host=document.querySelector('main');
   window.openBot=async id=>{window.controller?.dispose();window.controller=await AI2AppsBotConversation.create({bot:{id},root:host,onState(){},onError:e=>errors.push(e.message)});};
  });
  await page.evaluate(()=>openBot('b1'));
  await page.getByRole('button',{name:'Load older messages'}).click();
  await page.getByText('b1 message 1',{exact:true}).waitFor();
  await page.evaluate(()=>{document.querySelector('.bot-message-stream').scrollTop=240;document.querySelector('textarea').value='saved draft';document.querySelector('.bot-interactions').textContent='Old approval';});
  await page.evaluate(()=>openBot('b2'));
  await page.evaluate(()=>{hold=true;window.opening=openBot('b1');});
  assert.equal(await page.getByText('b1 message 1',{exact:true}).count(),1);
  assert.equal(await page.getByText('Old approval',{exact:true}).count(),0);
  assert.equal(await page.locator('.bot-message-stream').evaluate(e=>e.scrollTop),240);
  assert.equal(await page.getByRole('button',{name:'Send',exact:true}).isEnabled(),false);
  await page.evaluate(()=>{hold=false;releaseSession();});await page.evaluate(()=>opening);
  assert.equal(await page.getByText('b1 message 1',{exact:true}).count(),1);
  assert.equal(await page.locator('.bot-message-stream').evaluate(e=>e.scrollTop),240);
  assert.equal(await page.getByRole('textbox').inputValue(),'saved draft');
  for(const id of ['b3','b4','b5'])await page.evaluate(id=>openBot(id),id);
  await page.evaluate(()=>openBot('b1')); // Touch b1: b2 becomes the least recently used.
  await page.evaluate(()=>openBot('b6'));
  await page.evaluate(()=>{hold=true;window.opening=openBot('b2');});
  assert.equal(await page.locator('[aria-busy=true]').count(),0); // b2 was evicted.
  await page.evaluate(()=>{hold=false;releaseSession();});await page.evaluate(()=>opening);
  // Destructive cleanup invalidates before disposal and must not restore a snapshot.
  await page.evaluate(()=>{AI2AppsBotConversation.invalidate(host,'b2');controller.dispose({discard:true});controller=null;hold=true;window.opening=openBot('b2');});
  assert.equal(await page.locator('[aria-busy=true]').count(),0);
  await page.evaluate(()=>{hold=false;empty=true;releaseSession();});await page.evaluate(()=>opening);
  assert.equal(await page.locator('.assistant-message').count(),0);
  assert.deepEqual(await page.evaluate(()=>errors),[]);
  // A cached readonly preview is replaced as soon as session identity is known,
  // even when the model catalog is pending and history fails.
  await page.getByRole('textbox').fill('cached draft');
  await page.evaluate(()=>openBot('b3'));
  await page.evaluate(()=>{holdModel=true;failHistory=true;window.opening=openBot('b2');});
  await page.waitForFunction(()=>document.querySelector('textarea')?.readOnly===false);
  await page.getByRole('textbox').fill('editable while model pending');
  assert.equal(await page.getByRole('button',{name:'Send',exact:true}).isEnabled(),false);
  await page.evaluate(()=>{holdModel=false;releaseModel();});await page.evaluate(()=>opening);
  assert.equal(await page.getByRole('textbox').inputValue(),'editable while model pending');
  assert.equal(await page.getByRole('button',{name:'Send',exact:true}).isEnabled(),true);
  assert.deepEqual(await page.evaluate(()=>errors),['History unavailable']);
  await page.evaluate(()=>{failHistory=false;controller.dispose({discard:true});});
  const denied=await page.evaluate(async()=>{window.deny=true;try{await openBot('b1');return false;}catch(e){return e.message;}});
  assert.equal(denied,'Access revoked');assert.equal(await page.locator('main').textContent(),'');
 }finally{await browser.close();}
});
