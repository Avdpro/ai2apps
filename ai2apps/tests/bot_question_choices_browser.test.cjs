const {test}=require('node:test'),assert=require('node:assert/strict'),{chromium}=require('playwright'),path=require('node:path');
for(const width of [390,1100])test(`question choices and free text at ${width}px`,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage({viewport:{width,height:800}});await page.route('https://question.fixture/**',route=>route.fulfill({contentType:'text/html',body:'<main class="bot-interactions bot-interaction-card" style="max-width:700px;margin:16px"></main>'}));await page.goto('https://question.fixture/');
 await page.addStyleTag({path:path.join(__dirname,'../web/static/css/'+(width===390?'messager_mobile.css':'messager.css'))});
 await page.addScriptTag({path:path.join(__dirname,'../web/static/js/bot_interactions.js')});
 await page.evaluate(()=>{window.sent=[];window.mountQuestion=()=>{const root=document.querySelector('main');root.replaceChildren();root._botInteractionKey='q';window.AI2AppsBotInteractions.answerForm({root,item:{id:'q',prompt:'请选择调查方向',schema:{properties:{answer:{type:'string'}},required:['answer']},ui_hints:{options:['只读检查工作区的大文件','列出素材库占用情况']}},label:(zh,en)=>zh,onError:e=>{throw e},submit:async(answer,id)=>sent.push({answer,id})});};mountQuestion();});
 const options=page.locator('.bot-question-option');assert.equal(await options.count(),2);
 const colors=async option=>option.evaluate(el=>({text:getComputedStyle(el).color,background:getComputedStyle(el).backgroundColor}));
 assert.deepEqual(await colors(options.first()),{text:'rgb(64, 64, 64)',background:'rgb(255, 255, 255)'});
 await options.first().hover();assert.deepEqual(await colors(options.first()),{text:'rgb(23, 23, 23)',background:'rgb(245, 245, 245)'});
 await options.first().click();assert.deepEqual(await colors(options.first()),{text:'rgb(255, 255, 255)',background:'rgb(23, 23, 23)'});assert.equal(await page.locator('textarea').inputValue(),'只读检查工作区的大文件');assert.equal((await page.evaluate(()=>sent)).length,0);
 await page.getByRole('button',{name:'提交回答',exact:true}).click();await page.waitForFunction(()=>sent.length===1);assert.equal((await page.evaluate(()=>sent[0].answer.answer)),'只读检查工作区的大文件');assert.equal(await options.first().isDisabled(),true);assert.deepEqual(await colors(options.first()),{text:'rgb(255, 255, 255)',background:'rgb(23, 23, 23)'});
 await page.evaluate(()=>mountQuestion());await page.locator('.bot-question-option').first().click();await page.locator('textarea').fill('只列清单，不删除文件');assert.equal(await page.locator('.bot-question-option').first().getAttribute('aria-pressed'),'false');await page.getByRole('button',{name:'提交回答',exact:true}).click();await page.waitForFunction(()=>sent.length===2);assert.equal((await page.evaluate(()=>sent[1].answer.answer)),'只列清单，不删除文件');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 }finally{await browser.close();}
});
test('Mobile Messager renders original pending question and submits through its scoped route',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage({viewport:{width:390,height:844}});page.setDefaultTimeout(5000);const errors=[];page.on('pageerror',e=>errors.push(e.message));let answered=false,submitted;
 const template=require('node:fs').readFileSync(path.join(__dirname,'../web/templates/system_apps/messager_mobile.html'),'utf8');
 const content=template.split('{% block content %}')[1].split('{% endblock %}')[0].replace(/{{[^}]+}}/g,'Messager');
 await page.route('https://mobile-question.fixture/**',async route=>{const url=new URL(route.request().url()),p=url.pathname;let data={};
 if(p==='/')return route.fulfill({contentType:'text/html',body:`<html lang="zh"><body>${content}</body></html>`});
 if(p.endsWith('/bots'))data={items:[{id:'bot',name:'Fixture Bot',definition:{execution_mode:'standard'}}]};
 else if(p.endsWith('/bot-groups'))data={items:[]};
 else if(p.endsWith('/open'))data={session_id:'session',profile:{}};
 else if(p.endsWith('/models'))data={data:[],defaults:{}};
 else if(p.endsWith('/state'))data={runs:[{id:'original-run',status:'waiting_input',task_context:{task:'检查占用'},interactions:answered?[]:[{id:'original-question',kind:'menu',prompt:'请选择检查范围',request:{question_id:'scope'},schema:{properties:{answer:{type:'string'}},required:['answer']},ui_hints:{options:['工作区','素材库']}}]}],task_sessions:[],unread:{unread_count:0}};
 else if(p.endsWith('/messages'))data={items:[],has_more:false};
 else if(p.endsWith('/respond')){submitted=route.request().postDataJSON();assert.equal(p,'/v1/platform/messager-mobile/bots/bot/runs/original-run/questions/original-question/respond');answered=true;data={submitted:true};}
 else if(p.endsWith('/read'))data={unread_count:0};
 return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});});
 await page.goto('https://mobile-question.fixture/');
 await page.addScriptTag({path:path.join(__dirname,'../web/static/js/bot_interactions.js')});
 await page.addScriptTag({path:path.join(__dirname,'../web/static/js/bot_avatars.js')});await page.addScriptTag({path:path.join(__dirname,'../web/static/js/messager_mobile.js')});
 await page.getByText('Fixture Bot',{exact:true}).click().catch(e=>{throw Error(e.message+' errors: '+JSON.stringify(errors));});await page.locator('.bot-question-option').first().click();await page.getByRole('button',{name:'提交回答',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#mm-work')?.textContent.includes('已收到回复'));
 assert.equal(submitted.response.answer,'工作区');assert.equal(submitted.session_id,'session');assert.ok(submitted.response_id);
 }finally{await browser.close();}
});
