const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),{execFileSync}=require('child_process');
const {chromium}=require('playwright');
const base=path.resolve(__dirname,'..'),git=path.resolve(base,'..');
function html(inline){return execFileSync(git+'/.venv/bin/python',['-c',`from jinja2 import Environment,FileSystemLoader\ne=Environment(loader=FileSystemLoader('${base}/web/templates'))\ne.globals['mobile_static']=lambda n:'/assets/'+n\nprint(e.get_template('mobile_chat.html').render(current_lang='zh',owner_home=True,mobile_agent_ready=False,mobile_agent_inline=${inline?'True':'False'}))`],{encoding:'utf8'});}
for(const inline of [false,true])for(const denied of [false,true])test(`Chat notification ${inline?'inline':'framed'}: ${denied?'unavailable fails without fallback':'opens original, not selected thread'}`,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),calls=[];
  await page.addInitScript(()=>{window.addEventListener('message',e=>{if(e.data?.type==='ai2apps.notification.result')window.noticeResult=e.data;});});
  await page.route('https://fixture.test/**',async route=>{
   const p=new URL(route.request().url()).pathname;calls.push(p);
   if(p==='/')return route.fulfill({contentType:'text/html',body:html(inline)});
   if(p.startsWith('/assets/')){const f=path.join(base,'web/static',p.slice(8));return route.fulfill({contentType:p.endsWith('.css')?'text/css':'application/javascript',body:fs.existsSync(f)?fs.readFileSync(f):''});}
   if(p.endsWith('/state'))return route.fulfill({json:{selected_thread_id:'different'}});
   if(p.endsWith('/models'))return route.fulfill({json:{data:[]}});
   if(p==='/v1/mobile/chat/threads/original/content')return denied?route.fulfill({status:404,json:{detail:'Not accessible'}}):route.fulfill({json:{thread:{id:'original',title:'Original mobile conversation',status:'active'},messages:[{role:'assistant',content:'Persisted reply'}],session_metadata:{}}});
   if(p.endsWith('/turns'))return route.fulfill({json:{items:[]}});
   return route.fulfill({status:404,json:{detail:'Unexpected request'}});
  });
  await page.goto('https://fixture.test/#app=ai2apps.general-chat&notification-id=notice&notification-route=conversation&notification-resource=original&ai2apps-mount=mount-token');
  if(inline)await page.evaluate(()=>window.dispatchEvent(new CustomEvent('ai2apps-mobile-chat-visible',{detail:true})));
  await page.waitForFunction(inline?'window.__ai2appsNotificationStatus':'window.noticeResult');
  const result=await page.evaluate(inline?'window.__ai2appsNotificationStatus':'window.noticeResult');
  assert.equal(result.id,'notice');assert.equal(result.status,denied?'failed':'opened');
  if(!inline)assert.equal(result.mountToken,'mount-token');
  assert.ok(!calls.includes('/v1/mobile/chat/threads'));assert.ok(!calls.some(p=>p.includes('/different/')));
  if(!denied)await page.getByText('Persisted reply',{exact:true}).waitFor();
 }finally{await browser.close();}
});
