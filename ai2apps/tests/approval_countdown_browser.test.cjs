const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
async function fixture(surface,fn,{seconds=60,control='approval',effects=['external_read','network']}={}){
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:surface==='mobile'?390:1000,height:900}});await page.clock.install();
  const responses=[];let run={id:'r',session_id:'s',agent_display_name:'Fixture Agent',status:'waiting_capability',steps:[],interactions:[{id:'i',kind:'approval',status:'pending',revision:1,prompt:'允许这次运行？',ui_hints:{control,auto_approve_seconds:seconds},request:{tool_name:'fixture.reader',effects},response_schema:{type:'object',properties:{decision:{enum:['approve','deny']},scope:{enum:['once','app']}},required:['decision']}}]};
  await page.route('https://approval.fixture/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname;
   if(p.endsWith('.js'))return route.fulfill({contentType:'application/javascript; charset=utf-8',body:fs.readFileSync(path.join(__dirname,'../web/static/js',p.slice(1)),'utf8')});
   if(p==='/')return route.fulfill({contentType:'text/html; charset=utf-8',body:`<html lang="zh"><head><meta charset="utf-8"></head><body><main id="root"></main><script src="/agent_parameter_forms.js"></script><script src="/mobile_agent_chat.js"></script><script>
    window.run=${JSON.stringify(run)};const request=async(url,opts)=>{const r=await fetch(url,opts);return r.json()};
    if(${JSON.stringify(surface)}==='mobile'){window.client=new AI2AppsMobileAgentChat.Client({container:document.querySelector('#root'),request,enabled:true});client.show(run);}
    else{const root=document.querySelector('#root');root.innerHTML='<h3>允许这次运行？</h3><button id="allow">仅允许这一次</button><button id="deny">拒绝</button>';const approve=()=>request('/respond',{method:'POST',body:JSON.stringify({response:{decision:'approve',scope:'once'}})});root.querySelector('#allow').onclick=approve;root.querySelector('#deny').onclick=()=>request('/respond',{method:'POST',body:JSON.stringify({response:{decision:'deny'}})});AI2AppsParameterForms.mountApproval(root,run,run.interactions[0],approve);}
    </script></body></html>`});
   if(p.endsWith('/respond')){responses.push(req.postDataJSON());run={...run,status:'completed',interactions:[]};return route.fulfill({json:run});}
   return route.fulfill({json:run});
  });
  await page.goto('https://approval.fixture');await page.locator('.agent-approval-countdown').waitFor({state:'attached'});
  await fn(page,responses);
 }finally{await browser.close();}
}
for(const surface of ['desktop','mobile'])test(`${surface} timed approval permits only once after 60 seconds`,()=>fixture(surface,async(page,responses)=>{
 await page.getByText('60 秒后仅允许这一次',{exact:true}).waitFor();
 await page.clock.fastForward(59000);assert.equal(responses.length,0);
 await page.clock.fastForward(1000);await page.waitForFunction(()=>document.querySelector('.agent-parameter-countdown')?.hidden!==false);
 await page.waitForTimeout(50);assert.equal(responses.length,1);assert.deepEqual(responses[0].response,{decision:'approve',scope:'once'});
 await page.clock.fastForward(120000);assert.equal(responses.length,1);
}));
test('cancel auto-approval leaves manual denial available and reload does not re-arm',()=>fixture('desktop',async(page,responses)=>{
 await page.getByRole('button',{name:'取消自动批准',exact:true}).click();await page.clock.fastForward(120000);assert.equal(responses.length,0);
 await page.reload();await page.locator('.agent-approval-countdown').waitFor({state:'attached'});assert.equal(await page.locator('.agent-parameter-countdown').isVisible(),false);
 await page.getByRole('button',{name:'拒绝',exact:true}).click();assert.equal(responses.length,1);assert.deepEqual(responses[0].response,{decision:'deny'});
}));
test('page hide and leaving cancel approval without a background decision',()=>fixture('mobile',async(page,responses)=>{
 await page.getByText('60 秒后仅允许这一次',{exact:true}).waitFor();await page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));await page.clock.fastForward(120000);assert.equal(responses.length,0);
}));
for(const options of [{seconds:null},{control:'agent_confirmation'}])test('manual confirmation without trusted ordinary-approval policy never auto-approves '+JSON.stringify(options),()=>fixture('desktop',async(page,responses)=>{
 assert.equal(await page.locator('.agent-parameter-countdown').isVisible(),false);await page.clock.fastForward(120000);assert.equal(responses.length,0);
},options));
test('expired or changed approval stops its original timer',()=>fixture('mobile',async(page,responses)=>{
 await page.getByText('60 秒后仅允许这一次',{exact:true}).waitFor();await page.evaluate(()=>{run.status='cancelled';client.show(run);});await page.clock.fastForward(120000);assert.equal(responses.length,0);
}));
test('expired approval never reaches an automatic decision',()=>fixture('desktop',async(page,responses)=>{
 await page.getByText('60 秒后仅允许这一次',{exact:true}).waitFor();
 await page.evaluate(()=>{run.deadline_at=new Date(Date.now()-1).toISOString();});await page.clock.fastForward(60000);assert.equal(responses.length,0);
}));
test('repeated Mobile snapshots keep the original deadline',()=>fixture('mobile',async(page,responses)=>{
 await page.getByText('60 秒后仅允许这一次',{exact:true}).waitFor();await page.clock.fastForward(30000);
 await page.evaluate(()=>client.show(run));await page.clock.fastForward(30000);await page.waitForTimeout(50);assert.equal(responses.length,1);
}));
