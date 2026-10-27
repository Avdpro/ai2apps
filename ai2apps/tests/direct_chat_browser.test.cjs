const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),{execFileSync}=require('child_process');
const {chromium}=require('playwright');
const base=path.resolve(__dirname,'..'),git=path.resolve(base,'..');
function html(){return execFileSync(git+'/.venv/bin/python',['-c',`from jinja2 import Environment,FileSystemLoader\ne=Environment(loader=FileSystemLoader('${base}/web/templates'))\ne.globals['mobile_static']=lambda n:'/assets/'+n\nprint(e.get_template('mobile_chat.html').render(current_lang='zh',owner_home=True,mobile_agent_ready=False))`],{encoding:'utf8'});}
test('Mobile closes while running, reconnects to same turn, receives result and continues without replay',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844}});let revision=1,messages=[],turn=null,posts=0,contentWrites=0;const errors=[];
  const content=()=>({thread:{id:'s',title:'Offline test',revision},session_metadata:{mobile_model_id:'local/test'},messages});
  await context.route('https://fixture.test/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname,m=req.method();let data;
   if(p==='/')return route.fulfill({contentType:'text/html',body:html()});
   if(p.startsWith('/assets/')){const file=path.join(base,'web/static',p.slice(8));return route.fulfill({contentType:p.endsWith('.css')?'text/css':'application/javascript',body:fs.existsSync(file)?fs.readFileSync(file):''});}
   if(p.endsWith('/state'))data={selected_thread_id:'s'};
   else if(p.endsWith('/models'))data={data:[{id:'local/test',display_name:'Test model',model_type:'llm'}]};
   else if(p.endsWith('/threads'))data={items:[{id:'s',title:'Offline test'}]};
   else if(p.endsWith('/content')){if(m==='PUT'){contentWrites++;const b=req.postDataJSON();assert.equal(b.expected_revision,revision);messages=b.messages;revision++;}data=content();}
   else if(p.endsWith('/turns')){
    if(m==='POST'){posts++;const body=req.postDataJSON();assert.equal(body.expected_revision,revision);assert.ok(body.request_id);assert.equal(body.request.temperature,null);turn={id:'run_'+posts,session_id:'s',model:'local/test',status:'running',status_line:{text:'Thinking',content:{completion_preview:{content:'Partial'}}}};data=turn;}
    else data={items:turn?[turn]:[]};
   }else if(p.includes('/turns/run_')){if(p.endsWith('/cancel'))turn.status='cancelled';data=turn;}
   else return route.fulfill({status:404,json:{detail:'not exposed'}});
   return route.fulfill({json:data});
  });
  let page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto('https://fixture.test');
  await page.locator('[data-mobile-chat-model]').selectOption('local/test');
  await page.locator('[data-mobile-chat-input]').fill('First question');await page.locator('[data-mobile-chat-send]').click();
  await page.getByText('Partial',{exact:true}).waitFor();assert.equal(posts,1);
  await page.close();assert.equal(turn.status,'running');
  // Fixture simulates the backend committing while no page exists. Backend
  // independence itself is exercised with the real scheduler by Python tests.
  messages.push({role:'assistant',content:'Saved offline answer',metadata:{chat_turn_id:turn.id,id:'saved-1'}});revision++;turn.status='completed';
  page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto('https://fixture.test');
  await page.getByText('Saved offline answer',{exact:true}).waitFor();assert.equal(posts,1);
  await page.locator('[data-mobile-chat-input]').fill('Follow up');await page.locator('[data-mobile-chat-send]').click();
  await page.getByText('Partial',{exact:true}).waitFor();assert.equal(posts,2);
  assert.equal(messages[1].content,'Saved offline answer');assert.equal(messages[2].content,'Follow up');
  await page.locator('[data-mobile-chat-send]').click();
  await page.waitForFunction(()=>document.querySelector('[data-mobile-chat-send]').getAttribute('aria-label')==='Send');
  assert.equal(turn.status,'cancelled');assert.equal(messages.length,3);assert.equal(posts,2);
  assert.ok(contentWrites>=2);assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});

test('Desktop observer detaches without cancelling; restore reads existing result/run only',async()=>{
 const vm=require('vm'),source=fs.readFileSync(base+'/web/templates/chat.html','utf8');
 const methods=source.slice(source.indexOf('    async refreshDirectChatContent('),source.indexOf('            async streamResponse('));
 const stream={},calls=[],notices=[];let refreshes=0;
 const ctx=vm.createContext({console:{warn(){}},Date,setTimeout:fn=>{fn();return 0;},crypto:require('crypto').webcrypto});
 const object=vm.runInContext('({'+methods+'})',ctx);
 Object.assign(object,{backendChatReady:true,terminalAssistantMode:false,getStreamSession:()=>stream,getChatSession:()=>({messages:[]}),maybeAutoSpeak(){},startStatsPolling(){},stopStatsPollingIfIdle(){},resetStreamSession(s){s.isStreaming=false;},setEngineStatus(id,status){notices.push(status.text);},refreshDirectChatContent:async()=>{refreshes++;},
  platformChatFetch:async path=>{calls.push(path);if(path.endsWith('/turns'))return {items:[{id:'r',session_id:'ses_s',model:'m',status:'running'}]};throw Error('offline');}});
 await object.observeDirectChatTurn('ses_s',{id:'r',model:'m',status:'running',created_at:new Date().toISOString()});
 assert.ok(notices.some(n=>n.includes('连接中断')));assert.equal(stream.durableTurnId,null);assert.ok(!calls.some(p=>p.includes('cancel')));
 calls.length=0;
 object.platformChatFetch=async path=>{calls.push(path);return path.endsWith('/turns')?{items:[{id:'r',model:'m',status:'running'}]}:{id:'r',model:'m',status:'completed'};};
 await object.restoreDirectChatTurns('ses_s');await new Promise(r=>setImmediate(r));
 assert.equal(refreshes,2);assert.ok(calls.every(p=>!p.includes('cancel')));assert.equal(stream.isStreaming,false);
});
