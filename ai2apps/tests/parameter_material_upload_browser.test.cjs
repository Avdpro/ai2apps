const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
for(const scenario of [
 {provider:'fixture.picture.owner',multiple:true,accept:'image/*',name:'reference.png',mime:'image/png'},
 {provider:'unrelated.sound.provider',multiple:false,accept:'audio/*',name:'reference.wav',mime:'audio/wav'},
]) test(`material chooser stays enabled, cancellation is inert and failed upload can retry: ${scenario.provider}`,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 let attempts=0,writes=0,submissions=0,revision=0,values={},assets=[];
 const field={key:'material',type:'asset',storage:'artifact',label:'Reference material',accept:scenario.accept,multiple:scenario.multiple,maxItems:3};
 try{
  const page=await browser.newPage();
  await page.route('https://material.fixture/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname;
   if(p==='/')return route.fulfill({contentType:'text/html',body:'<html lang="en"><head></head><body><div id="form"></div><script src="/widget.js"></script><script>AI2AppsParameterForms.mount(document.querySelector("#form"),{id:"run"},{id:"item"},()=>{});</script></body></html>'});
   if(p==='/widget.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.resolve(__dirname,'../web/static/js/agent_parameter_forms.js'))});
   if(p.endsWith('/parameters')&&req.method()==='GET')return route.fulfill({json:{revision,values,descriptor:{capability:scenario.provider,app_id:scenario.provider,schema:{type:'object',properties:{}},fields:[field]},models:[],missing:[],invalid:[],configure_only:true}});
   if(p.endsWith('/materials'))return route.fulfill({json:{items:assets}});
   if(p.endsWith('/materials/upload')){
    attempts++;if(attempts===1)return route.fulfill({status:500,json:{detail:'Fixture upload failed'}});
    const asset={id:'owned-material',name:scenario.name,media_type:scenario.mime};assets=[asset];return route.fulfill({json:{asset}});
   }
   if(req.method()==='PUT'){writes++;const b=req.postDataJSON();assert.equal(b.revision,revision);values=b.values;return route.fulfill({json:{revision:++revision}});}
   if(p.endsWith('/submit')){submissions++;return route.fulfill({json:{}});}
   return route.fulfill({json:{items:[],providers:[]}});
  });
  await page.goto('https://material.fixture');
  const upload=page.getByRole('button',{name:'Upload material',exact:true});await upload.waitFor();
  const choose=async()=>{const [chooser]=await Promise.all([page.waitForEvent('filechooser'),upload.click()]);assert.equal(await chooser.element().isDisabled(),false);assert.equal(chooser.isMultiple(),scenario.multiple);return chooser;};
  const cancelled=await choose();await cancelled.setFiles([]);assert.equal(attempts,0);assert.equal(writes,0);assert.equal(await upload.isEnabled(),true);
  const file={name:scenario.name,mimeType:scenario.mime,buffer:Buffer.from('fixture media')};
  await (await choose()).setFiles(file);await page.getByRole('alert').filter({hasText:'Fixture upload failed'}).waitFor();
  assert.equal(attempts,1);assert.equal(await upload.isEnabled(),true);assert.equal(writes,0);
  await (await choose()).setFiles(file);await page.getByText(scenario.name,{exact:true}).first().waitFor();
  assert.equal(attempts,2);assert.equal(writes,1);assert.deepEqual(values.material,scenario.multiple?['owned-material']:'owned-material');assert.equal(submissions,0);
 }finally{await browser.close();}
});
