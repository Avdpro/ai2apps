const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const {chromium}=require('playwright');
async function fixture(fn,{complete=true,affirmative=false,width=1000,dark=false}={}){
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width,height:900}});await page.clock.install();
  let values={count:0,enabled:false,mode:'single',...(complete?{origin:'Beijing'}:{origin:''})},revision=0,submits=0;
  const schema={type:'object',properties:{origin:{type:'string'},count:{type:'integer'},enabled:affirmative?{const:true}:{type:'boolean'},mode:{enum:['single','return']},end:{type:'string'}},required:['origin','count','enabled'],allOf:[{if:{properties:{mode:{const:'return'}},required:['mode']},then:{required:['end']}}]};
  if(affirmative)values.enabled=true;
  const required=()=>['origin','count','enabled',...(values.mode==='return'?['end']:[])];
  const fields=[{key:'origin',label:{zh:'出发地',en:'Origin'},type:'text'},{key:'count',label:'Count',type:'number'},{key:'enabled',label:'Enabled',type:'boolean'},{key:'mode',label:'Mode',type:'select',options:[{value:'single',label:'Single'},{value:'return',label:'Return'}]},{key:'end',label:'End',type:'text'}];
  await page.route('https://required.fixture/**',async route=>{
   const req=route.request(),p=new URL(req.url()).pathname;
   if(p==='/')return route.fulfill({contentType:'text/html',body:`<html lang="zh" class="${dark?'dark':''}"><head><meta charset="utf-8"></head><body><div id="form"></div><script src="/form.js"></script><script>AI2AppsParameterForms.mount(document.querySelector('#form'),{id:'r',agent_key:'fixture.agent'},{id:'one'},()=>window.finished=true)</script></body></html>`});
   if(p==='/form.js')return route.fulfill({contentType:'application/javascript; charset=utf-8',body:fs.readFileSync(path.join(__dirname,'../web/static/js/agent_parameter_forms.js'),'utf8')});
   if(p.endsWith('/submit')){submits++;return route.fulfill({json:{}});}
   if(p.endsWith('/parameters')){
    if(req.method()==='PUT'){values=req.postDataJSON().values;revision++;return route.fulfill({json:{revision,values,required_fields:required(),missing:[],invalid:[]}});}
    return route.fulfill({json:{revision,values,configure_only:true,models:[],missing:[],invalid:[],required_fields:required(),descriptor:{capability:'fixture.action',schema,fields}}});
   }
   return route.fulfill({json:{items:[]}});
  });
  await page.goto('https://required.fixture');await page.locator('.agent-parameter-title').waitFor();
  await fn(page,()=>submits);
 }finally{await browser.close();}
}
for(const dark of [false,true])test(`required stars and empty backgrounds update including conditional fields (${dark?'dark':'light'})`,()=>fixture(async(page,submits)=>{
 const origin=page.getByLabel('出发地',{exact:true}),group=page.locator('[data-parameter-key=origin]');
 assert.equal(await group.locator('.agent-parameter-required').isVisible(),true);
 const emptyColor=await origin.evaluate(el=>getComputedStyle(el).backgroundColor);
 assert.equal(emptyColor,dark?'rgb(59, 32, 39)':'rgb(255, 241, 242)');
 await origin.fill('Shanghai');assert.equal(await group.getAttribute('data-empty-required'),'false');
 assert.notEqual(await origin.evaluate(el=>getComputedStyle(el).backgroundColor),emptyColor);
 assert.equal(await group.locator('.agent-parameter-required').isVisible(),true);
 assert.equal(await page.locator('[data-parameter-key=count]').getAttribute('data-empty-required'),'false');
 assert.equal(await page.locator('[data-parameter-key=enabled]').getAttribute('data-empty-required'),'false');
 await page.getByLabel('Mode',{exact:true}).selectOption('return');
 await page.waitForFunction(()=>document.querySelector('[data-parameter-key=end]').dataset.emptyRequired==='true');
 assert.equal(await page.getByLabel('End',{exact:true}).getAttribute('aria-required'),'true');
 await page.clock.fastForward(120000);assert.equal(submits(),0);
 },{complete:false,dark,width:dark?390:1000}));
test('complete initial values auto-submit once at 60 seconds through normal save and submit',()=>fixture(async(page,submits)=>{
 await page.getByText('· 60 秒后自动提交',{exact:true}).waitFor();
 await page.clock.fastForward(59000);assert.equal(submits(),0);
 await page.clock.fastForward(1000);await page.waitForFunction(()=>window.finished===true);assert.equal(submits(),1);
 await page.clock.fastForward(120000);assert.equal(submits(),1);
}));
test('starting an edit cancels immediately and reload never restarts countdown',()=>fixture(async(page,submits)=>{
 await page.getByText('· 60 秒后自动提交',{exact:true}).waitFor();
 await page.getByLabel('出发地',{exact:true}).focus();
 assert.equal(await page.locator('.agent-parameter-countdown').isVisible(),false);
 await page.clock.fastForward(120000);assert.equal(submits(),0);
 await page.reload();await page.locator('.agent-parameter-title').waitFor();assert.equal(await page.locator('.agent-parameter-countdown').isVisible(),false);
 await page.clock.fastForward(120000);assert.equal(submits(),0);
}));
test('leaving the page cancels the timer without submitting',()=>fixture(async(page,submits)=>{
 await page.getByText('· 60 秒后自动提交',{exact:true}).waitFor();
 await page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));
 await page.clock.fastForward(120000);assert.equal(submits(),0);
}));
test('user can cancel countdown without changing values',()=>fixture(async(page,submits)=>{
 await page.getByRole('button',{name:'取消自动提交',exact:true}).click();
 await page.clock.fastForward(120000);assert.equal(submits(),0);
 assert.equal(await page.getByLabel('出发地',{exact:true}).inputValue(),'Beijing');
}));
test('required affirmative confirmation never auto-submits',()=>fixture(async(page,submits)=>{
 assert.equal(await page.locator('.agent-parameter-countdown').isVisible(),false);
 await page.clock.fastForward(120000);assert.equal(submits(),0);
},{affirmative:true}));
