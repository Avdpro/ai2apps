const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
test('resolved model choices and contract errors use the shared form without submission',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});let submitted=0,setups=0;
 try{
  const page=await browser.newPage();
  await page.route('https://contract.fixture/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname;
   if(p==='/')return route.fulfill({contentType:'text/html',body:'<html lang="en"><body><div id="form"></div><script src="/widget.js"></script><script>AI2AppsParameterForms.mount(document.querySelector("#form"),{id:"run"},{id:"item"},()=>{});</script></body></html>'});
   if(p==='/widget.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.resolve(__dirname,'../web/static/js/agent_parameter_forms.js'))});
   if(p.endsWith('/parameters')&&req.method()==='GET')return route.fulfill({json:{revision:0,values:{old_field:'retained'},descriptor:{app_id:'fixture.owner',schema:{type:'object',required:['engine'],properties:{engine:{type:'string'}}},fields:[{key:'engine',type:'model',label:'Engine'},{key:'quality',type:'select',label:'Quality',options:[{value:'standard',label:'Standard'}]}]},models:[{id:'ready-engine',label:'Ready engine',ready:true},{id:'unavailable-engine',label:'Unavailable engine',ready:false}],parameter_contract_error:{errors:[{validator:'additionalProperties'}]},install:{appId:'fixture.owner',capability:'fixture.setup'},missing:['engine'],invalid:[],configure_only:true}});
   if(p.endsWith('/submit'))submitted++;
   if(p.includes('/setup/session'))setups++;
   return route.fulfill({json:{items:[],providers:[]}});
  });
  await page.goto('https://contract.fixture');
  await page.locator('[data-parameter-key="engine"] select').waitFor();
  assert.deepEqual(await page.locator('[data-parameter-key="engine"] option').allTextContents(),['Select model','Ready engine']);
  assert.equal(await page.locator('[data-parameter-key="quality"] select').count(),1);
  await page.getByRole('alert').filter({hasText:'Original values are retained'}).waitFor();
  await page.getByRole('button',{name:'Set up required capability',exact:true}).waitFor();
  assert.equal(submitted,0);assert.equal(setups,0);
 }finally{await browser.close();}
});

test('schema enum fallback renders all fields and setup actions on Desktop and Mobile',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{for(const width of [1100,390]){
  const page=await browser.newPage({viewport:{width,height:900}});let submitted=0;
  const schema={type:'object',properties:{language:{type:'string',enum:['en','fr'],default:'en'},format:{type:'string',enum:['png','html'],default:'png'},direction:{type:'string',enum:['auto','vertical'],default:'auto'},crop:{type:'boolean',default:true}},required:['language']};
  const fields=[{key:'language',type:'select',label:'Target language'},{key:'format',type:'select',label:'Output format'},{key:'direction',type:'select',label:'Source layout',options:null},{key:'crop',type:'boolean',label:'Auto-crop'}];
  await page.route('https://enum.fixture/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname;
   if(p==='/')return route.fulfill({contentType:'text/html',body:`<html lang="en"><body><div id="form"></div><script>window.AI2APPS_MOBILE_SURFACE=${width<500}</script><script src="/widget.js"></script><script>AI2AppsParameterForms.mount(document.querySelector('#form'),{id:'run'},{id:'enum-${width}'},()=>{})</script></body></html>`});
   if(p==='/widget.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.resolve(__dirname,'../web/static/js/agent_parameter_forms.js'))});
   if(p.endsWith('/parameters'))return route.fulfill({json:{revision:0,values:{language:'en',format:'png',direction:'auto',crop:true},descriptor:{app_id:'arbitrary.owner',capability:'arbitrary.action',schema,fields},models:[],missing:[],invalid:[],configure_only:true,configuration_required:true,install:{appId:'arbitrary.owner',capability:'arbitrary.setup'}}});
   if(p.endsWith('/submit'))submitted++;
   return route.fulfill({json:{items:[]}});
  });
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('https://enum.fixture');
  await page.getByLabel('Target language',{exact:true}).waitFor();
  assert.deepEqual(await page.getByLabel('Target language',{exact:true}).locator('option').evaluateAll(options=>options.map(o=>o.value)),['en','fr']);
  assert.equal(await page.getByLabel('Output format',{exact:true}).inputValue(),'png');
  assert.equal(await page.getByLabel('Source layout',{exact:true}).inputValue(),'auto');
  assert.equal(await page.getByLabel('Auto-crop',{exact:true}).isChecked(),true);
  assert.equal(await page.getByRole('heading',{name:'Set up required capability',exact:true}).count(),1);
  assert.equal(await page.getByRole('button',{name:'Confirm parameters and return to Agent',exact:true}).isDisabled(),true);
  assert.equal(await page.getByRole('button',{name:width<500?'Desktop setup instructions':'Set up required capability',exact:true}).isVisible(),true);
  assert.equal(await page.getByRole('button',{name:'Cancel',exact:true}).isVisible(),true);
  assert.deepEqual(errors,[]);assert.equal(submitted,0);await page.close();
 }}finally{await browser.close();}
});

test('declared dependency select refreshes contract and install-free configuration can recheck',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{for(const mobile of [false,true]){
  const page=await browser.newPage({viewport:{width:mobile?390:1100,height:900}});
  let values={variant:'blocked',note:'keep me'},revision=0,reads=0,ready=false,submitted=0;
  await page.route('https://dependency.fixture/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname;
   if(p==='/')return route.fulfill({contentType:'text/html',body:`<html lang="en"><body><div id="form"></div><script>window.AI2APPS_MOBILE_SURFACE=${mobile}</script><script src="/widget.js"></script><script>AI2AppsParameterForms.mount(document.querySelector('#form'),{id:'run'},{id:'dependency'},()=>{})</script></body></html>`});
   if(p==='/widget.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.resolve(__dirname,'../web/static/js/agent_parameter_forms.js'))});
   if(p.endsWith('/parameters')){
    if(req.method()==='PUT'){values=req.postDataJSON().values;revision++;return route.fulfill({json:{revision,missing:[],invalid:[]}});}
    reads++;return route.fulfill({json:{revision,values,model_field:'variant',configuration_required:values.variant==='blocked'||!ready,install:values.variant==='blocked'?{appId:'arbitrary.owner',capability:'arbitrary.setup'}:null,models:[],missing:[],invalid:[],configure_only:true,auto_submit_allowed:false,descriptor:{schema:{type:'object',properties:{variant:{type:'string'},note:{type:'string'}}},fields:[{key:'variant',type:'select',label:'Variant',options:[{value:'blocked',label:'Blocked'},{value:'available',label:'Available'}]},{key:'note',type:'text',label:'Note'}]}}});
   }
   if(p.endsWith('/submit'))submitted++;
   return route.fulfill({json:{items:[]}});
  });
  await page.goto('https://dependency.fixture');
  await page.getByLabel('Variant',{exact:true}).selectOption('available');
  await page.waitForFunction(()=>document.querySelector('#form')._parameterForm?.state.values.variant==='available'&&!document.querySelector('#form')._parameterForm.busy);
  assert.equal(reads,2);
  assert.equal(await page.getByRole('button',{name:mobile?'Desktop setup instructions':'Set up required capability',exact:true}).count(),0);
  assert.equal(await page.getByLabel('Note',{exact:true}).inputValue(),'keep me');
  assert.equal(await page.getByRole('button',{name:'Confirm parameters and return to Agent',exact:true}).isDisabled(),true);
  ready=true;
  await page.getByRole('button',{name:'Recheck',exact:true}).click();
  await page.waitForFunction(()=>!document.querySelector('#form')._parameterForm?.state.configuration_required);
  assert.equal(await page.getByRole('button',{name:'Confirm parameters and return to Agent',exact:true}).isEnabled(),true);
  assert.equal(values.note,'keep me');assert.equal(reads,3);assert.equal(submitted,0);
  await page.close();
 }}finally{await browser.close();}
});
