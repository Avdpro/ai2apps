const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');const root=path.resolve(__dirname,'../..'),source=path.join(root,'packages/ai2apps-audio-generation-suite/web');
test('real Package frame loads slowly, exposes current draft and saves edits without execution',async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
 try{const context=await browser.newContext();
  await context.route('https://package.test/**',async route=>{
   const name=new URL(route.request().url()).pathname.split('/').pop();
   if(name==='host')return route.fulfill({contentType:'text/html',body:'<iframe id="pkg" sandbox="allow-scripts" src="/sfx.html"></iframe>'});
   if(!/^[\w.-]+$/.test(name)||!fs.existsSync(path.join(source,name)))return route.fulfill({status:404,body:''});
   if(name==='package_mini_chat.js')await new Promise(r=>setTimeout(r,800));
   return route.fulfill({contentType:name.endsWith('.js')?'application/javascript':name.endsWith('.css')?'text/css':'text/html',body:fs.readFileSync(path.join(source,name))});
  });
  const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{window.operations=[];window.saved=null;window.addEventListener('message',event=>{
   if(event.data?.type!=='ai2apps:studio-connect')return;
   const channel=new MessageChannel();channel.port1.onmessage=e=>{const m=e.data;operations.push(m.operation);let value=null;
    if(m.operation==='audio-generation.models')value={items:[{id:'fixture.sfx',label:'Fixture',ready:true,minimumSeconds:1,maximumSeconds:120}]};
    if(m.operation==='draft.set')saved=JSON.parse(m.value);
    channel.port1.postMessage({id:m.id,value});};
   event.source.postMessage({type:'ai2apps:studio-connected',version:1,locale:'en'},'*',[channel.port2]);
  });});
  await page.goto('https://package.test/host',{waitUntil:'domcontentloaded'});
  await page.addScriptTag({content:fs.readFileSync(path.join(root,'ai2apps/web/static/js/mini_app_chat.js'),'utf8')});
  const snapshot=await page.evaluate(async()=>{window.bridge=AI2AppsMiniAppChat.createPackageBridge(()=>document.querySelector('#pkg'),{system_prompt:'UI only',help:{resource:'help.md'},tools:[]});return bridge.describe({id:'arbitrary.sfx'});});
  assert.equal(snapshot.context.values.model,'fixture.sfx');
  await page.evaluate(()=>bridge.invoke('update_current_draft',{prompt:'Soft rain',duration:2}));
  assert.equal(await page.frameLocator('#pkg').locator('#prompt').inputValue(),'Soft rain');
  assert.equal((await page.evaluate(()=>saved)).duration,'2');
  assert.ok(!(await page.evaluate(()=>operations)).includes('audio-generation.generate'));
  await assert.rejects(page.evaluate(()=>bridge.invoke('run_current',{})),/cannot execute/);
  assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
