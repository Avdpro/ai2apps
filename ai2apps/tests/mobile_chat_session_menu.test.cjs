const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{execFileSync}=require('node:child_process');
const {chromium}=require('playwright'),root=path.resolve(__dirname,'..'),git=path.resolve(root,'..');
test('Mobile session menu renames without switching, confirms delete and keeps failed operations visible',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});try{
 const page=await browser.newPage({viewport:{width:390,height:844}});
 const html=execFileSync(git+'/.venv/bin/python',['-c',`from jinja2 import Environment,FileSystemLoader\ne=Environment(loader=FileSystemLoader('${root}/web/templates'))\ne.globals['mobile_static']=lambda n:'/assets/'+n\nprint(e.get_template('mobile_chat.html').render(current_lang='zh',owner_home=True,mobile_agent_ready=False))`],{encoding:'utf8'});
 let threads=[{id:'a',title:'First',revision:1,updated_at:new Date().toISOString()},{id:'b',title:'Second',revision:2,updated_at:new Date().toISOString()}],patches=0,deletes=0,fail=false;
 await page.route('https://fixture.test/**',async route=>{const req=route.request(),url=new URL(req.url()),p=url.pathname;let body;
 if(p==='/')return route.fulfill({contentType:'text/html',body:html});
 if(p.startsWith('/assets/')){const f=path.join(root,'web/static',p.slice(8));return route.fulfill({contentType:p.endsWith('.css')?'text/css':'application/javascript',body:fs.existsSync(f)?fs.readFileSync(f):''});}
 if(p.endsWith('/state'))body={selected_thread_id:'a'};
 else if(p.endsWith('/models'))body={data:[{id:'m',model_type:'llm'}]};
 else if(p.endsWith('/threads'))body={items:threads};
 else if(p.endsWith('/content'))body={thread:threads.find(t=>p.includes('/'+t.id+'/')),messages:[],session_metadata:{mobile_model_id:'m'}};
 else if(p.endsWith('/turns'))body={items:[]};
 else if(/\/threads\/[ab]\/manage$/.test(p)){
 assert.equal(req.method(),'POST');const t=threads.find(t=>p.endsWith('/'+t.id+'/manage'));const data=req.postDataJSON();
 if(fail)return fail==='html'?route.fulfill({status:404,contentType:'text/html',body:'<h1>Not found</h1>'}):route.fulfill({status:409,json:{detail:'Revision conflict'}});
 if(data.action==='rename'){assert.equal(data.expected_revision,t.revision);t.title=data.title;t.revision++;patches++;body={...t};}
 else if(data.action==='delete'){assert.equal(data.expected_revision,t.revision);deletes++;threads=threads.filter(v=>v!==t);body={...t,status:'deleted'};}
 }else return route.fulfill({status:404,json:{detail:'Not exposed'}});
 return route.fulfill({json:body});});
 await page.goto('https://fixture.test');await page.locator('[data-mobile-chat-sessions]').click();
 await page.evaluate(()=>{window.confirm=()=>{throw Error('Native confirm unavailable in WKWebView');};window.prompt=()=>{throw Error('Native prompt unavailable in WKWebView');};});
 const row=id=>page.locator('.mchat-session-row').filter({has:page.locator('button.mchat-session[data-thread-id='+id+']')});
 await row('b').locator('summary').click();await row('b').locator('[data-thread-action=rename]').click();await page.locator('[role=dialog] input').fill('Renamed <img src=x>');await page.locator('[data-thread-dialog-accept]').click();await page.waitForFunction(()=>document.querySelector('.mchat-session[data-thread-id=b] strong')?.textContent==='Renamed <img src=x>');
 assert.equal(patches,1);assert.equal(await page.locator('.mchat-session.is-active').getAttribute('data-thread-id'),'a');assert.equal(await page.locator('.mchat-session-list img').count(),0);
 await row('b').locator('summary').click();await row('b').locator('[data-thread-action=delete]').click();await page.locator('[data-thread-dialog-cancel]').click();assert.equal(deletes,0);
 await row('a').locator('summary').click();await row('a').locator('[data-thread-action=delete]').click();await page.screenshot({path:'/tmp/mobile-chat-delete-confirm.png'});await page.locator('[data-thread-dialog-accept]').click();
 await page.waitForFunction(()=>document.querySelector('.mchat-session.is-active')?.dataset.threadId==='b');assert.equal(deletes,1);
 await page.locator('[data-mobile-chat-sessions]').click();fail=true;await row('b').locator('summary').click();await row('b').locator('[data-thread-action=delete]').click();await page.locator('[data-thread-dialog-accept]').click();
 await page.getByText('Revision conflict (HTTP 409)',{exact:true}).waitFor();assert.equal(await row('b').count(),1);assert.equal(deletes,1);
 fail='html';await row('b').locator('summary').click();await row('b').locator('[data-thread-action=delete]').click();await page.locator('[data-thread-dialog-accept]').click();await page.getByText('Request failed (HTTP 404)',{exact:true}).waitFor();assert.equal(await row('b').count(),1);
 }finally{await browser.close();}
});
