const {test}=require('node:test'),assert=require('node:assert/strict');
const {chromium}=require('playwright');const path=require('node:path');
for(const width of [390,1100])test('Mobile renders owner wait reason, metrics, scoped actions and icons at '+width,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage({viewport:{width,height:844}});await page.setContent('<style>:root{--ink:#171717;--muted:#737373;--line:#ddd;--blue:#1689ff}body{background:#f8f8f8;font-family:Arial;padding:12px}</style><main class="mchat" id="runs"></main>');await page.addStyleTag({path:path.join(__dirname,'../web/static/css/mobile_chat.css')});
 await page.addScriptTag({path:path.join(__dirname,'../web/static/js/lucide.min.js')});
 await page.addScriptTag({path:path.join(__dirname,'../web/static/js/mobile_agent_chat.js')});
 await page.evaluate(()=>{
  Object.defineProperty(window,'crypto',{value:{randomUUID:()=> 'response-id'}});window.actions=[];window.client=new AI2AppsMobileAgentChat.Client({enabled:true,container:document.querySelector('#runs'),
   loadOwners:async()=>({apps:[{app_key:'fixture.app',display_name:'Fixture',navigation:{icon:'globe'}}],minis:[{id:'fixture.mini',app_id:'fixture.app',icon:'shopping-cart'}]}),
   request:async(url,options)=>{if(options)actions.push([url,JSON.parse(options.body)]);if(!url.includes('/browser-tasks/'))return window.run;return {id:'task',status:'waiting_input',requires_user:true,interactions:[{id:'help',control:'browser_user_assistance'}]};}});
  window.run={id:'run',session_id:'session',status:'running',status_line:{text:'Preparing',content:{app_id:'fixture.app',mini_app_id:'fixture.mini',browser_task_id:'task',task_progress:{state:'waiting',requires_user:true,wait_reason:'数量控件需要协助',metrics:[{label:'商品',value:1,total:3}]}}}};
  client.show(run);
 });
 await page.getByText('数量控件需要协助',{exact:true}).waitFor();await page.getByRole('button',{name:'已处理，继续'}).waitFor();
 assert.equal(await page.getByText('商品 · 1 / 3',{exact:true}).count(),1);
 await page.waitForFunction(()=>document.querySelectorAll('.mchat-agent-owner svg').length===2);
 assert.equal(await page.locator('.mchat-agent-owner[aria-label="App · Fixture"]').count(),1);
 await page.getByRole('button',{name:'在 Desktop 打开问题页面'}).click();
 await page.waitForFunction(()=>window.actions.length>0);const actions=await page.evaluate(()=>window.actions);assert.equal(actions[0][0],'/v1/mobile/agent-runs/run/browser-tasks/task');assert.equal(actions[0][1].action,'open');
 if(width===390)await page.screenshot({path:'/tmp/shopping-mobile-assistance.png'});
 }finally{await browser.close();}
});
