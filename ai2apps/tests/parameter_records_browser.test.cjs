const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
test('generic record form shows named rows, saves quantities and restores exact review before submit',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 let revision=0,values={rows:[{key:'a',count:2},{key:'b',count:2},{key:'c',count:2}]},submissions=[];
 const field={key:'rows',label:'Review items',type:'json',presentation:'records',maxItems:5,columns:[{key:'key',label:'Item',type:'select',options:['a','b','c'].map(value=>({value,label:'Observed '+value}))},{key:'count',label:'Quantity',type:'number',minimum:1,maximum:10}]};
 try{const page=await browser.newPage({viewport:{width:390,height:844}});
 await page.route('https://form.fixture/**',async route=>{const req=route.request(),p=new URL(req.url()).pathname;
  if(p==='/')return route.fulfill({contentType:'text/html',body:'<html lang="en"><body><div id="form"></div><script src="/widget.js"></script><script>AI2AppsParameterForms.mount(document.querySelector("#form"),{id:"run",agent_display_name:"Agent"},{id:"item"},()=>{});</script></body></html>'});
  if(p==='/widget.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.resolve(__dirname,'../web/static/js/agent_parameter_forms.js'))});
  if(p.endsWith('/parameters')&&req.method()==='GET')return route.fulfill({json:{revision,values,descriptor:{capability:'arbitrary.review',app_id:'arbitrary.app',schema:{type:'object',properties:{rows:{type:'array'}}},fields:[field]},missing:[],invalid:[],models:[],configure_only:true}});
  if(req.method()==='PUT'){const b=req.postDataJSON();assert.equal(b.revision,revision);values=b.values;return route.fulfill({json:{revision:++revision,values}});}
  if(p.endsWith('/submit')){submissions.push(req.postDataJSON());return route.fulfill({json:{result:{arguments:values}}});}
  return route.fulfill({json:{items:[],providers:[]}});
 });
 await page.goto('https://form.fixture');await page.getByLabel('Quantity 3',{exact:true}).waitFor();
 assert.equal(await page.locator('.agent-records-table select').count(),3);
 assert.equal(await page.getByLabel('Quantity 1',{exact:true}).inputValue(),'2');
 assert.equal(await page.getByLabel('Item 1',{exact:true}).locator('option:checked').textContent(),'Observed a');
 await page.getByLabel('Quantity 2',{exact:true}).fill('3');await page.getByLabel('Quantity 2',{exact:true}).dispatchEvent('change');
 await page.waitForFunction(()=>document.querySelector('[aria-label="Quantity 2"]').value==='3');
 await page.reload();await page.getByLabel('Quantity 2',{exact:true}).waitFor();assert.equal(await page.getByLabel('Quantity 2',{exact:true}).inputValue(),'3');assert.equal(submissions.length,0);
 await page.getByRole('button',{name:'Confirm parameters and return to Agent',exact:true}).click();await page.waitForTimeout(50);
 assert.equal(submissions.length,1);assert.deepEqual(submissions[0].values,{rows:[{key:'a',count:2},{key:'b',count:3},{key:'c',count:2}]});
 }finally{await browser.close();}
});

test('localized owner labels fall back to English and compact fields wrap without changing values',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{for(const language of ['zh-TW','fr']){const page=await browser.newPage({viewport:{width:1000,height:800}});let submitted;
 const values={count:2,mode:'safe',note:'unchanged'};
 const fields=[{key:'count',type:'number',label:{zh:'数量',en:'Quantity'}},{key:'mode',type:'select',width:'compact',label:{zh:'模式',en:'Mode'},options:[{value:'safe',label:{zh:'标准',en:'Standard'},description:{zh:'实际观察的身份','en':'Observed identity'},url:'https://example.org/account',image:'javascript:alert(1)'}]},{key:'note',type:'text',label:'Legacy label'}];
 await page.route('https://form.fixture/**',async route=>{const req=route.request(),p=new URL(req.url()).pathname;
 if(p==='/')return route.fulfill({contentType:'text/html',body:`<html lang="${language}"><head></head><body style="padding:20px"><div id="form"></div><script src="/widget.js"></script><script>AI2AppsParameterForms.mount(document.querySelector('#form'),{id:'run'},{id:'form'},()=>{});</script></body></html>`});
 if(p==='/widget.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.resolve(__dirname,'../web/static/js/agent_parameter_forms.js'))});
 if(p.endsWith('/parameters')&&req.method()==='GET')return route.fulfill({json:{revision:0,values,descriptor:{capability:'example.configure',app_id:'example',schema:{type:'object',properties:{}},fields},models:[],missing:[],invalid:[],submit_label:{zh:'确认配置',en:'Confirm configuration'}}});
 if(req.method()==='PUT')return route.fulfill({json:{revision:1}});
 if(p.endsWith('/submit')){submitted=req.postDataJSON();return route.fulfill({json:{}});}
 return route.fulfill({json:{items:[]}});
 });
 await page.goto('https://form.fixture');const count=page.getByLabel(language==='zh-TW'?'数量':'Quantity',{exact:true}),mode=page.getByLabel(language==='zh-TW'?'模式':'Mode',{exact:true});await count.waitFor();
 assert.equal(await page.locator('.agent-parameter-title').count(),1);
 const typography=await page.evaluate(()=>({title:getComputedStyle(document.querySelector('.agent-parameter-title')).fontSize,weight:getComputedStyle(document.querySelector('.agent-parameter-title')).fontWeight,label:getComputedStyle(document.querySelector('.agent-parameter-field>label')).fontSize}));
 assert.deepEqual(typography,{title:'15px',weight:'700',label:'13px'});
 assert.equal(await page.evaluate(()=>AI2AppsParameterForms.prompt({prompt:'fallback',ui_hints:{prompt_labels:{zh:'确认参数',en:'Confirm parameters'}}})),language==='zh-TW'?'确认参数':'Confirm parameters');
 assert.equal(await mode.locator('option:checked').textContent(),language==='zh-TW'?'标准':'Standard');
 assert.equal(await page.locator('.agent-parameter-field a').getAttribute('href'),'https://example.org/account');assert.equal(await page.locator('.agent-parameter-field img').count(),0);
 assert.equal(await count.inputValue(),'2');const a=await count.boundingBox(),b=await mode.boundingBox();assert.equal(a.y,b.y);assert.ok(a.width<=140);
 await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 assert.ok((await count.boundingBox()).height>=44);
 await Promise.all([page.waitForResponse(r=>r.url().endsWith('/submit')),page.getByRole('button',{name:language==='zh-TW'?'确认配置':'Confirm configuration',exact:true}).click()]);assert.deepEqual(submitted.values,values);await page.close();
 }}finally{await browser.close();}
});

for(const provider of ['arbitrary.alpha','package.beta'])test(`numeric Schema permits decimals without relaxing integers (${provider})`,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 let revision=0,values={amount:0.5,count:2},submitted=[];
 try{
 const page=await browser.newPage();
 await page.route('https://numeric.fixture/**',async route=>{
  const req=route.request(),p=new URL(req.url()).pathname;
  if(p==='/')return route.fulfill({contentType:'text/html',body:'<html lang="en"><body><div id="form"></div><script src="/widget.js"></script><script>AI2AppsParameterForms.mount(document.querySelector("#form"),{id:"run"},{id:"item"},()=>{});</script></body></html>'});
  if(p==='/widget.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.resolve(__dirname,'../web/static/js/agent_parameter_forms.js'))});
  if(p.endsWith('/parameters')&&req.method()==='GET')return route.fulfill({json:{revision,values,descriptor:{capability:provider+'.adjust',app_id:provider,schema:{type:'object',properties:{amount:{type:'number'},count:{type:'integer'}}},fields:[{key:'amount',label:'Amount',type:'number'},{key:'count',label:'Count',type:'number'}]},models:[],configure_only:true}});
  if(req.method()==='PUT'){values=req.postDataJSON().values;return route.fulfill({json:{revision:++revision,values}});}
  if(p.endsWith('/submit')){submitted.push(req.postDataJSON().values);return route.fulfill({json:{result:{arguments:values}}});}
  return route.fulfill({json:{items:[],providers:[]}});
 });
 await page.goto('https://numeric.fixture');await page.getByLabel('Amount',{exact:true}).waitFor();
 assert.equal(await page.getByLabel('Amount',{exact:true}).getAttribute('step'),'any');
 assert.equal(await page.getByLabel('Count',{exact:true}).getAttribute('step'),'1');
 await page.getByLabel('Amount',{exact:true}).fill('0.25');await page.getByLabel('Amount',{exact:true}).dispatchEvent('change');
 await page.getByRole('button',{name:'Confirm parameters and return to Agent',exact:true}).click();
 await page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/submit'));
 assert.deepEqual(submitted,[{amount:.25,count:2}]);
 await page.reload();await page.getByLabel('Count',{exact:true}).fill('1.5');await page.getByLabel('Count',{exact:true}).dispatchEvent('change');
 await page.getByRole('button',{name:'Confirm parameters and return to Agent',exact:true}).click();
 assert.equal(submitted.length,1);
 assert.equal(await page.getByLabel('Count',{exact:true}).evaluate(el=>el.validity.stepMismatch),true);
 }finally{await browser.close();}
});

test('owner handoff-only form exposes one primary continuation without a submit or Enter bypass',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{for(const language of ['zh','en']){
  const page=await browser.newPage();let submits=0,handoffs=0,opens=0;
  await page.exposeFunction('observeOpen',()=>{opens++;});
  await page.route('https://form.fixture/**',async route=>{const p=new URL(route.request().url()).pathname;
   if(p==='/')return route.fulfill({contentType:'text/html',body:`<html lang="${language}"><body><div id="form"></div><script>window.ai2appsShell={openHandoff:()=>window.observeOpen()};</script><script src="/widget.js"></script><script>AI2AppsParameterForms.mount(document.querySelector('#form'),{id:'run'},{id:'item'},()=>{});</script></body></html>`});
   if(p==='/widget.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.resolve(__dirname,'../web/static/js/agent_parameter_forms.js'))});
   if(p.endsWith('/parameters')&&route.request().method()==='GET')return route.fulfill({json:{revision:0,values:{target:'exact'},descriptor:{capability:'arbitrary.review',app_id:'arbitrary.owner',schema:{type:'object',properties:{}},fields:[{key:'target',type:'text',label:'Target'}]},models:[],missing:[],invalid:[],configuration_required:true,handoff_only:true,can_continue_in_app:true,continue_label:{zh:'前往审核',en:'Review in owner App'},handoff_message:{zh:'请先完成审核，任务会保留。',en:'Complete review first; your task is preserved.'}}});
   if(p.endsWith('/handoff'))handoffs++;
   if(p.endsWith('/submit'))submits++;
   return route.fulfill({json:{revision:1,items:[]}});
  });
  await page.goto('https://form.fixture');const next=page.getByRole('button',{name:language==='zh'?'前往审核':'Review in owner App',exact:true});await next.waitFor();
  assert.equal(await page.locator('button[type=submit]').count(),0);
  assert.match(await next.getAttribute('class'),/agent-interaction-button--primary/);
  assert.equal(await page.locator('.agent-parameter-handoff-note').textContent(),language==='zh'?'请先完成审核，任务会保留。':'Complete review first; your task is preserved.');
  await page.getByLabel('Target',{exact:true}).press('Enter');assert.equal(submits,0);
  await next.click();await page.waitForFunction(()=>document.body.textContent.includes('Waiting for the App')||document.body.textContent.includes('等待 App'));
  assert.equal(handoffs,1);assert.equal(submits,0);assert.equal(opens,1);await page.close();
 }}finally{await browser.close();}
});
