const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),{execFileSync}=require('child_process');
const {chromium}=require('playwright');
const base=path.resolve(__dirname,'..'),git=path.resolve(base,'..');
function html(){return execFileSync(git+'/.venv/bin/python',['-c',`from jinja2 import Environment,FileSystemLoader\ne=Environment(loader=FileSystemLoader('${base}/web/templates'))\ne.globals['mobile_static']=lambda n:'/assets/'+n\nprint(e.get_template('mobile_chat.html').render(current_lang='zh',owner_home=False,mobile_agent_ready=True))`],{encoding:'utf8'});}
for(const state of ['form','approval','submitted','expired','form-error'])test('Interaction notification '+state,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),writes=[];
  let descriptorStarted=false;
  const item={id:'input-original',kind:state==='approval'?'approval':'form',status:state==='submitted'?'submitted':'pending',revision:1,prompt:'请审阅本步骤',deadline_at:state==='expired'?'2020-01-01T00:00:00Z':'2099-01-01T00:00:00Z',ui_hints:state==='approval'?{}:{control:'parameter_form'}};
  const run={id:'run-original',session_id:'original',status:'waiting_input',deadline_at:'2099-01-01T00:00:00Z',interactions:[item],steps:[]};
  await page.addInitScript(()=>window.addEventListener('message',e=>{if(e.data?.type==='ai2apps.notification.result')window.noticeResult=e.data;}));
  await page.route('https://fixture.test/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname;if(req.method()!=='GET')writes.push(p);
   if(p==='/')return route.fulfill({contentType:'text/html',body:html()});
   if(p.startsWith('/assets/')){const f=path.join(base,'web/static',p.slice(8));return route.fulfill({contentType:p.endsWith('.css')?'text/css':'application/javascript',body:fs.existsSync(f)?fs.readFileSync(f):''});}
   let data;
   if(p.endsWith('/state'))data={selected_thread_id:'wrong'};
   else if(p.endsWith('/models'))data={data:[]};
   else if(p.endsWith('/agents')||p.endsWith('/apps'))data={items:[]};
   else if(p.endsWith('/content'))data={thread:{id:'original',status:'active',title:'Original conversation'},messages:[],session_metadata:{}};
   // Deliberately omit the requested delegated Run from list pagination.
   else if(p.endsWith('/agent-runs'))data={items:[]};
   else if(p.endsWith('/agent-runs/run-original'))data=run;
   else if(p.endsWith('/parameters')){
    descriptorStarted=true;await new Promise(r=>setTimeout(r,180));
    if(state==='form-error')return route.fulfill({status:403,json:{detail:'Unavailable'}});
    data={revision:1,values:{value:'Saved draft'},missing:[],descriptor:{schema:{type:'object',properties:{value:{type:'string'}}},fields:[{key:'value',type:'text',label:'参数值'}]}};
   }else return route.fulfill({status:404,json:{detail:'Unexpected operation'}});
   return route.fulfill({json:data});
  });
  await page.goto('https://fixture.test/#app=ai2apps.general-chat&notification-id=notice&notification-route=interaction&notification-resource=input-original&notification-session=original&notification-run=run-original&ai2apps-mount=bound');
  await page.waitForFunction(()=>window.noticeResult);
  const result=await page.evaluate(()=>window.noticeResult);
  assert.equal(result.status,['form','approval'].includes(state)?'opened':'failed');
  assert.equal(writes.length,0,'Opening a notification must never submit or approve');
  if(state==='form'){assert.ok(descriptorStarted);assert.equal(await page.locator('.agent-parameter-form input').inputValue(),'Saved draft');}
  if(state==='approval'){
   await page.getByRole('button',{name:'仅允许这一次',exact:true}).waitFor();
   assert.equal(await page.getByRole('button',{name:'拒绝',exact:true}).count(),1);
   assert.equal(await page.getByRole('button',{name:'在当前应用中记住此工具',exact:true}).count(),0,'Legacy approval must not gain tool-wide consent');
   assert.equal(writes.length,0,'Rendering the real approval choices must not submit consent');
  }
  if(result.status==='opened')assert.equal(await page.evaluate(()=>document.activeElement.dataset.agentInteractionId),'input-original');
 }finally{await browser.close();}
});
