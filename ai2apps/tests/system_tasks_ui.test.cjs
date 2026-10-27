const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {chromium}=require('playwright');
for(const mobile of [false,true])test(`system tasks ${mobile?'Mobile':'Desktop'} lists, controls, escaping and preserved details`,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width:mobile?390:1200,height:850}});
 await page.setContent(mobile?'<html lang="zh"><main id="mobile-todo"><section id="list-view"><button id="system-tasks-entry"></button></section><section id="detail-view" hidden></section></main>':'<html lang="en"><div id="todo-workspace" class="todo-workspace"><aside><button id="system-tasks-entry"></button><button data-directory="d">Folder</button></aside><main class="todo-main"><header>Projects</header></main><aside class="todo-detail"></aside></div>');
 await page.addStyleTag({path:path.join(__dirname,'../web/static/css/system_tasks.css')});
 await page.evaluate(()=>{
  window.calls=[];window.timer=null;window.setInterval=fn=>{window.timer=fn;};
  window.fetch=async(url,options)=>{window.calls.push([url,options]);return {ok:true,json:async()=>url.endsWith('/system-tasks')?{apps:{'test.app':{name:'Test App',icon:'satellite-dish'}},tasks:[{id:'one',name:'Refresh <img src=x onerror=alert(1)>',app_id:'test.app',status:'running',attempt:1,created_at:Date.now()/1000,started_at:Date.now()/1000,progress:{}},{id:'two',name:'Queued',app_id:'test.app',status:'queued',attempt:0,created_at:Date.now()/1000,progress:{}}],schedules:[{id:'schedule',name:'Daily refresh',app_id:'test.app',next_run:Date.now()/1000+3600,interval_seconds:3600}]}:url.endsWith('/one')?{children:[{id:'child',name:'Read page',status:'running'}],attempts:[{number:1,status:'running',started_at:1}]}:{id:'one',status:'cancelling'}};};
 });
 await page.addScriptTag({path:path.join(__dirname,'../web/static/js/system_tasks.js')});
 await page.click('#system-tasks-entry');await page.waitForSelector('.system-task-card');
 assert.equal(await page.locator('.system-task-card img').count(),0);
 assert.equal(await page.locator('.system-task-app').first().innerText(),'Test App');
 assert.equal(await page.locator('.system-task-app [data-lucide]').first().getAttribute('data-lucide'),'satellite-dish');
 await page.click('[data-system-detail="one"]');assert.match(await page.locator('[data-system-children="one"]').innerText(),/Read page/);
 await page.evaluate(()=>window.timer());await page.waitForTimeout(40);
 assert.ok(await page.locator('[data-system-children="one"]').isVisible());
 await page.click('[data-system-action="force"]');
 let calls=await page.evaluate(()=>window.calls);assert.ok(calls.some(([url,opt])=>url.endsWith('/one/cancel')&&JSON.parse(opt.body).force===true));
 await page.click('[data-system-tab="queued"]');await page.click('[data-system-action="start"]');
 await page.click('[data-system-tab="scheduled"]');await page.click('[data-system-schedule]');
 calls=await page.evaluate(()=>window.calls);assert.ok(calls.some(([url])=>url.endsWith('/system-schedules/schedule/start')));
 assert.equal(await page.locator('[data-system-tab=running]').getAttribute('aria-pressed'),'true');
 assert.equal(await page.locator('#system-task-panel').evaluate(e=>e.scrollWidth>innerWidth),false);
 await page.evaluate(()=>{window.fetch=async()=>({ok:true,json:async()=>({tasks:Array.from({length:45},(_,i)=>({id:'history'+i,name:'History '+i,app_id:'test.app',status:'completed',attempt:1,created_at:1,finished_at:2,progress:{}})),schedules:[]})});});
 await page.click('[data-system-refresh]');await page.click('[data-system-tab="history"]');
 assert.equal(await page.locator('.system-task-card').count(),20);
 await page.click('[data-system-more]');assert.equal(await page.locator('.system-task-card').count(),40);
 await page.click('[data-system-more]');assert.equal(await page.locator('.system-task-card').count(),45);
 assert.equal(await page.locator('[data-system-more]').count(),0);
 await page.click('[data-system-close]');assert.ok(await page.locator('#system-task-panel').isHidden());
 }finally{await browser.close();}
});
