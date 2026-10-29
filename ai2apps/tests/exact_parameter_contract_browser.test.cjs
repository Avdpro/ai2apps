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
