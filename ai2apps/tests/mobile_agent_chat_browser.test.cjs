const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),{execFileSync}=require('child_process');
const {chromium}=require('playwright');
const base=path.resolve(__dirname,'..'),git=path.resolve(base,'..');
function html(enabled){return execFileSync(git+'/.venv/bin/python',['-c',`from jinja2 import Environment,FileSystemLoader\ne=Environment(loader=FileSystemLoader('${base}/web/templates'))\ne.globals['mobile_static']=lambda name:'/assets/'+name\nprint(e.get_template('mobile_chat.html').render(current_lang='zh',owner_home=${enabled?'False':'True'},mobile_agent_ready=${enabled?'True':'False'}))`],{encoding:'utf8'});}
const view=layout=>({provider:'fixture.'+layout,view:{schema:'ai2apps.aaat-view/v1',id:layout,layout,title:layout==='table'?'商品清单':'新闻',columns:[{key:'state',label:'状态'}],items:[{id:'one',title:'原始内容 <script>evil()</script>',url:'https://original.test/article',image:{url:'/photo.png'},fields:{state:'partial'}}]}});
test('Mobile full client: mode, parameter draft recovery, progress, budget consent, rich results and reload',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage({viewport:{width:390,height:844}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let runs=[],messages=[],revision=0,values={query:'原始词'},draftRevision=0;const writes=[];
 const run={id:'run_1',session_id:'thread',status:'waiting_input',agent_display_name:'Fixture Agent',status_line:{text:'等待参数确认',progress:.25},steps:[{kind:'tool',tool_name:'fixture.operation',output:{mini_app_id:'fixture.mini'}}],interactions:[{id:'interaction_1',status:'pending',kind:'form',revision:1,prompt:'准备调用已注册的 App，请确认参数。',request:{control:'parameter_form'},ui_hints:{control:'parameter_form'}}]};
 const content=()=>({thread:{id:'thread',title:'Mobile fixture',revision:++revision},session_metadata:{},messages});
 await page.route('https://fixture.test/**',async route=>{const req=route.request(),url=new URL(req.url()),p=url.pathname,m=req.method();let data={};
  if(p.startsWith('/assets/')){const file=path.join(base,'web/static',p.slice(8));return route.fulfill({status:fs.existsSync(file)?200:404,contentType:p.endsWith('.css')?'text/css':'application/javascript',body:fs.existsSync(file)?fs.readFileSync(file):''});}
  if(p==='/photo.png')return route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZ1kAAAAASUVORK5CYII=','base64')});
  if(p==='/')return route.fulfill({contentType:'text/html',body:html(true)});
  if(m!=='GET')writes.push([p,m,req.postData()]);
  if(p==='/v1/mobile/agent-runs/run_1/owners')data={apps:[{app_key:'fixture.app',display_name:'Example App',navigation:{icon:'palette'}}],minis:[{id:'fixture.mini',app_id:'fixture.app',displayName:'Example Mini',icon:'users'}]};
  else if(p==='/v1/mobile/apps')data={items:[{app_key:'fixture.app',display_name:'Example App',navigation:{icon:'palette'}}]};
  else if(p==='/v1/platform/studios/fixture.app/mini-apps')data={items:[{id:'fixture.mini',displayName:'Example Mini',icon:'users'}]};
  else if(p==='/v1/mobile/chat/state')data={selected_thread_id:'thread'};
  else if(p==='/v1/mobile/models')data={data:[{id:'capable',display_name:'Declared work model',model_type:'llm',capabilities:['work_standard','tool_calling_reliable','conversation']}]};
  else if(p==='/v1/mobile/agents')data={items:[{agent_key:'ai2apps.general-agent',display_name:'General Agent',status:'enabled',discoverable:true},{agent_key:'fixture.specialist',display_name:'Specialist Agent',status:'enabled',discoverable:true}]};
  else if(p==='/v1/mobile/chat/threads')data={items:[{id:'thread',title:'Mobile fixture'}]};
  else if(p==='/v1/mobile/chat/threads/thread/content')data=content();
  else if(p==='/v1/mobile/chat/threads/thread/agent-runs'){if(m==='POST'){assert.equal(req.postDataJSON().agent,'ai2apps.general-agent');runs=[run];}data=m==='POST'?run:{items:runs};}
  else if(p.endsWith('/parameters/submit')){
   const body=req.postDataJSON();assert.equal(body.revision,draftRevision);assert.equal(body.values.query,'用户修改');
   run.status_line={text:'正文读取 1/2',progress:.5};run.interactions=[{id:'budget',status:'pending',revision:1,kind:'menu',prompt:'预算用尽，是否继续？',response_schema:{required:['answer'],properties:{answer:{enum:['继续','结束并保留结果']}}}}];data={};
  }else if(p.endsWith('/parameters')){
   if(m==='PUT'){const b=req.postDataJSON();assert.equal(b.revision,draftRevision);values=b.values;draftRevision++;}
   data={revision:draftRevision,values,missing:[],descriptor:{capability:'fixture.read',display_name:'Fixture reader',schema:{required:['query']},fields:[{key:'query',label:'搜索词',type:'text'}]}};
  }else if(p.endsWith('/respond')){
   assert.equal(req.postDataJSON().response.answer,'继续');run.status='completed';run.status_line={text:'部分完成',progress:1};run.interactions=[];run.output={message_id:'done',aaat_views:[view('table'),view('cards')]};messages=[{role:'assistant',content:'实际结果：partial',metadata:{agent_run_id:run.id,aaat_views:run.output.aaat_views}}];data=run;
  }else if(p==='/v1/mobile/agent-runs/run_1')data=run;
  else return route.fulfill({status:404,json:{detail:'not exposed'}});
  return route.fulfill({json:data});
 });
 await page.goto('https://fixture.test');assert.equal(await page.locator('select[data-mobile-chat-agent]').count(),0);await page.getByRole('button',{name:'Agent',exact:true}).click();
 await page.locator('[data-mobile-chat-input]').fill('执行只读任务');await page.locator('[data-mobile-chat-send]').click();
 await page.getByRole('heading',{name:'确认调用参数',exact:true}).waitFor();assert.equal(await page.getByRole('heading',{name:'确认调用参数',exact:true}).count(),1);
 await page.locator('.mchat-agent-owner[data-owner-id="fixture.app"] svg').waitFor();
 assert.equal(await page.locator('.mchat-agent-owner[aria-label="Mini-App · Example Mini"] svg').count(),1);
 const field=page.locator('[data-run-id] input:not([type=checkbox])');await field.fill('用户修改');await field.dispatchEvent('change');
 await page.waitForFunction(()=>document.querySelector('[data-run-id] input')?.value==='用户修改');
 const beforeReload=writes.length;await page.reload();await page.getByRole('heading',{name:'确认调用参数',exact:true}).waitFor();assert.equal(await page.getByRole('heading',{name:'确认调用参数',exact:true}).count(),1);assert.equal(await page.locator('[data-run-id] input:not([type=checkbox])').inputValue(),'用户修改');assert.equal(writes.length,beforeReload);
 await page.getByRole('button',{name:'提交',exact:true}).click();await page.getByText('预算用尽，是否继续？').waitFor();assert.equal(writes.filter(([p])=>p.endsWith('/respond')).length,0);
 await page.getByRole('button',{name:'继续',exact:true}).click();await page.locator('.aaat-view-card').waitFor();
 assert.equal(await page.locator('.aaat-result-view').count(),2);assert.equal(await page.locator('table tbody tr').count(),1);
 await page.waitForFunction(()=>document.images.length===2&&[...document.images].every(i=>i.naturalWidth>0));
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 const finishedWrites=writes.length;await page.reload();await page.locator('.aaat-view-card').waitFor();await page.locator('.mchat-agent-owner[data-owner-id="fixture.app"] svg').waitFor();assert.equal(await page.locator('.mchat-agent-owner[data-owner-id="fixture.mini"] svg').count(),1);assert.equal(writes.length,finishedWrites);assert.equal(writes.filter(([p,m])=>p==='/v1/mobile/chat/threads/thread/agent-runs'&&m==='POST').length,1);assert.equal(await page.locator('.aaat-view-card a').getAttribute('href'),'https://original.test/article');assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
test('Mobile new Sessions default to Agent while a saved Chat Session retains Chat mode',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  const page=await browser.newPage({viewport:{width:390,height:844}});let created=null,existing=false;
  await page.route('https://default.test/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname;let data={};
   if(p.startsWith('/assets/')){const file=path.join(base,'web/static',p.slice(8));return route.fulfill({status:fs.existsSync(file)?200:404,contentType:p.endsWith('.css')?'text/css':'application/javascript',body:fs.existsSync(file)?fs.readFileSync(file):''});}
   if(p==='/')return route.fulfill({contentType:'text/html',body:html(true)});
   if(p==='/v1/mobile/chat/state')data={selected_thread_id:existing?'thread':null};
   else if(p==='/v1/mobile/models')data={data:[{id:'capable',capabilities:['work_standard','tool_calling_reliable','conversation']}]};
   else if(p==='/v1/mobile/agents')data={items:[{agent_key:'ai2apps.general-agent',display_name:'General Agent',status:'enabled',discoverable:true}]};
   else if(p==='/v1/mobile/chat/threads'){
    if(req.method()==='POST'){created=req.postDataJSON();data={id:'thread',title:'New chat'};}
    else data={items:existing?[{id:'thread',title:'Saved Chat'}]:[]};
   }else if(p.endsWith('/content'))data={thread:{id:'thread',revision:1},session_metadata:existing?{agentMode:false}:created?.session_metadata||{},messages:[]};
   else if(p.endsWith('/agent-runs')||p.endsWith('/turns'))data={items:[]};
   else return route.fulfill({status:404,json:{detail:'not exposed'}});
   return route.fulfill({json:data});
  });
  await page.goto('https://default.test/');
  await page.waitForFunction(()=>document.querySelector('[data-mobile-chat-input]')?.placeholder==='Give the Agent a task');
  await page.waitForFunction(()=>!document.querySelector('[data-mobile-chat-status]')||document.querySelector('[data-mobile-chat-status]').hidden);
  assert.equal(created.session_metadata.agentMode,true);
  assert.equal(await page.locator('[data-mobile-chat-mode="agent"]').evaluate(n=>n.classList.contains('is-active')),true);
  await page.locator('[data-mobile-chat-mode="chat"]').click();
  await page.locator('[data-mobile-chat-new]').first().click();
  await page.waitForFunction(()=>document.querySelector('[data-mobile-chat-mode="agent"]')?.classList.contains('is-active'));
  assert.equal(created.session_metadata.agentMode,true);
  existing=true;await page.reload();
  await page.waitForFunction(()=>document.querySelector('[data-mobile-chat-input]')?.placeholder==='Message AI2Apps');
  assert.equal(await page.locator('[data-mobile-chat-mode="chat"]').evaluate(n=>n.classList.contains('is-active')),true);
 } finally {await browser.close();}
});

test('Owner Mobile still has a noninteractive Chat label and performs no Agent requests',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();const agentRequests=[];
 await page.route('https://fixture.test/**',route=>{const p=new URL(route.request().url()).pathname;if(p.includes('agent'))agentRequests.push(p);
 if(p==='/')return route.fulfill({contentType:'text/html',body:html(false)});
 if(p.startsWith('/assets/')){const file=path.join(base,'web/static',p.slice(8));return route.fulfill({body:fs.existsSync(file)?fs.readFileSync(file):'',contentType:'application/javascript'});}
 return route.fulfill({json:p.endsWith('/state')?{}:p.endsWith('/models')?{data:[]}:p.endsWith('/threads')?{items:[{id:'s'}]}:{thread:{id:'s'},messages:[]}});});
 await page.goto('https://fixture.test');await page.locator('.mchat-empty').waitFor();assert.equal(await page.getByRole('button',{name:'Agent',exact:true}).count(),0);assert.equal(await page.getByRole('button',{name:'Chat',exact:true}).count(),0);assert.equal(agentRequests.filter(p=>p.startsWith('/v1/')).length,0);
 }finally{await browser.close();}
});

test('terminal error identical to status appears once across mobile snapshots',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage({viewport:{width:390,height:844}});await page.setContent('<main id="runs"></main>');
 await page.addScriptTag({content:fs.readFileSync(path.join(base,'web/static/js/mobile_agent_chat.js'),'utf8')});
 await page.evaluate(()=>{window.client=new AI2AppsMobileAgentChat.Client({container:document.querySelector('#runs'),enabled:true});const run={id:'failure',status:'failed',status_line:{text:'Prepare rejected'},error:{message:'Prepare rejected'}};client.show(run);client.show(run);});
 assert.equal(await page.getByText('Prepare rejected',{exact:true}).count(),1);
 await page.evaluate(()=>client.show({id:'failure',status:'failed',status_line:{text:'Stopped'},error:{message:'Prepare rejected'}}));
 assert.equal(await page.getByText('Prepare rejected',{exact:true}).count(),1);assert.equal(await page.getByText('Stopped',{exact:true}).count(),1);
 }finally{await browser.close()}
});

test('mobile history interleaves each run with its input and answer after reload and snapshot updates',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width:390,height:844}});
 const messages=[
  {role:'user',content:'First request',metadata:{agent_run_id:'r1'}},
  {role:'assistant',content:'First answer',metadata:{agent_run_id:'r1'}},
  {role:'user',content:'Second request',metadata:{agent_run_id:'r2'}},
  {role:'assistant',content:'Second answer',metadata:{agent_run_id:'r2'}}];
 const runs=[{id:'r2',session_id:'thread',status:'completed',agent_display_name:'Second process'},
  {id:'r1',session_id:'thread',status:'failed',agent_display_name:'First process',error:{message:'Historical error'}}];
 await page.route('**/*',route=>{
  const p=new URL(route.request().url()).pathname;
  if(p==='/')return route.fulfill({contentType:'text/html',body:html(true)});
  if(p.startsWith('/assets/')){const file=path.join(base,'web/static',p.slice(8));return route.fulfill({contentType:'application/javascript',body:fs.existsSync(file)?fs.readFileSync(file):''});}
  let data={};
  if(p.endsWith('/state'))data={selected_thread_id:'thread'};
  else if(p.endsWith('/models'))data={data:[]};
  else if(p.endsWith('/agents'))data={items:[]};
  else if(p.endsWith('/threads'))data={items:[{id:'thread',title:'Chronology'}]};
  else if(p.endsWith('/content'))data={thread:{id:'thread'},messages};
  else if(p.endsWith('/agent-runs'))data={items:runs};
  return route.fulfill({json:data});
 });
 const order=()=>page.locator('[data-mobile-chat-list] > .mchat-message, [data-mobile-chat-list] > .mchat-agent-run').evaluateAll(nodes=>nodes.map(n=>n.dataset.runId||n.textContent.replace(/^Agent/,'').trim()));
 const expected=['First request','r1','First answer','Second request','r2','Second answer'];
 await page.goto('https://fixture.test');await page.locator('[data-run-id="r1"]').waitFor();assert.deepEqual(await order(),expected);
 await page.reload();await page.locator('[data-run-id="r2"]').waitFor();assert.deepEqual(await order(),expected);
 await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
 await page.locator('[data-run-id="r1"]').waitFor();assert.deepEqual(await order(),expected);
 assert.equal(await page.locator('[data-run-id]').count(),2);
 }finally{await browser.close();}
});

test('mobile assistant Markdown renders tables and links safely while user input stays literal',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width:390,height:844}});
 const md='## 帖子清单\n\n**加粗**\n\n| 时间 | 链接 |\n| --- | --- |\n| 09:42 | [原帖](https://x.com/example/status/1) |\n\n- 第一项\n- 第二项\n\n```js\nconst n = 1;\n```\n\n<script>window.pwned=true</script><img src="https://evil.test/pixel" onerror="window.pwned=true">[坏链接](javascript:alert(1))';
 const messages=[{role:'user',content:'**用户原文**'},{role:'assistant',content:md}];let evilRequests=0;
 await page.route('**/*',route=>{
  const u=new URL(route.request().url()),p=u.pathname;
  if(u.hostname==='evil.test'){evilRequests++;return route.abort();}
  if(p==='/')return route.fulfill({contentType:'text/html',body:html(true)});
  if(p.startsWith('/assets/')){const file=path.join(base,'web/static',p.slice(8));return route.fulfill({contentType:p.endsWith('.css')?'text/css':'application/javascript',body:fs.existsSync(file)?fs.readFileSync(file):''});}
  let data={};if(p.endsWith('/state'))data={selected_thread_id:'thread'};
  else if(p.endsWith('/models'))data={data:[]};else if(p.endsWith('/agents')||p.endsWith('/agent-runs'))data={items:[]};
  else if(p.endsWith('/threads'))data={items:[{id:'thread',title:'Markdown'}]};
  else if(p.endsWith('/content'))data={thread:{id:'thread'},messages};
  return route.fulfill({json:data});
 });
 for(let pass=0;pass<2;pass++){
  if(pass)await page.reload();else await page.goto('https://fixture.test');
  await page.locator('.mchat-markdown table').waitFor();
  assert.equal(await page.locator('.mchat-markdown h2').textContent(),'帖子清单');
  assert.equal(await page.locator('.mchat-markdown strong').textContent(),'加粗');
  assert.equal(await page.locator('.mchat-markdown ul li').count(),2);
  assert.match(await page.locator('.mchat-markdown pre code').textContent(),/const n = 1/);
  assert.equal(await page.locator('.mchat-table-scroll table tbody tr').count(),1);
  const link=page.getByRole('link',{name:'原帖'});assert.equal(await link.getAttribute('href'),'https://x.com/example/status/1');assert.match(await link.getAttribute('rel'),/noopener/);
  assert.equal(await page.locator('.mchat-markdown img,.mchat-markdown script,.mchat-markdown [onerror],.mchat-markdown a[href^="javascript:"]').count(),0);
  assert.equal(await page.locator('.mchat-message.user').textContent(),'**用户原文**');
  assert.equal(await page.evaluate(()=>Boolean(window.pwned)),false);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 }
 assert.equal(evilRequests,0);
 }finally{await browser.close();}
});
