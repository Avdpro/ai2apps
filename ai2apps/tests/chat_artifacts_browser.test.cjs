const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs');
const {chromium}=require('playwright');
for(const mobile of [false,true])test('shared output actions '+(mobile?'mobile signed':'desktop'),async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width:mobile?390:1100,height:900}});let reads=[],imports=0;
 await page.route('https://artifacts.fixture/**',async route=>{
  const r=route.request(),p=new URL(r.url()).pathname;
  if(p==='/')return route.fulfill({contentType:'text/html',body:'<html lang="zh"><body><div id="cards"></div></body></html>'});
  if(p.includes('/artifacts/art_audio/download'))return route.fulfill({contentType:'audio/wav',headers:{'Content-Disposition':`attachment; filename="audio.wav"; filename*=UTF-8''%E8%AF%AD%E9%9F%B3.wav`},body:Buffer.from('RIFF fixture audio')});
  if(p.endsWith('/gallery')||p.includes('/import-artifact/')){imports++;return route.fulfill({json:{created:true}});}
  reads.push(p);return route.fulfill({contentType:p.includes('art_text')?'text/plain':'audio/wav',body:p.includes('art_text')?'<script>window.pwned=1</script>hello':Buffer.from('RIFF fixture audio')});
 });
 await page.goto('https://artifacts.fixture');await page.addStyleTag({content:fs.readFileSync(__dirname+'/../web/static/css/chat_artifacts.css','utf8')});await page.addScriptTag({content:fs.readFileSync(__dirname+'/../web/static/js/chat_artifacts.js','utf8')});
 await page.evaluate(mobile=>{
  window.AI2AppsAgentConnection={signedFetch:(url,options)=>fetch(url,options)};
  AI2AppsChatArtifacts.render(document.querySelector('#cards'),[
   {artifact_id:'art_audio',filename:'语音.wav',media_type:'audio/wav',size_bytes:20,url:'/v1/platform/sessions/s/artifacts/art_audio/download'},
   {artifact_id:'art_text',filename:'笔记.txt',media_type:'text/plain',size_bytes:100,url:'/v1/platform/sessions/s/artifacts/art_text/download'},
   {filename:'evil',media_type:'text/plain',url:'https://evil.invalid/secret'}],{signed:mobile,runId:'r'});
 },mobile);
 assert.equal(await page.locator('.chat-artifact-card').count(),2);assert.equal(reads.length,0);
 assert.equal(await page.locator('.chat-artifact-actions button').first().getAttribute('title'),'加载试听');
 await page.getByRole('button',{name:'加载试听',exact:true}).click();await page.locator('audio[controls]').waitFor();assert.equal(await page.locator('audio[controls]').count(),1);assert.equal(await page.locator('audio').getAttribute('autoplay'),null);
 await page.getByRole('button',{name:'预览 / 打开',exact:true}).click();await page.locator('pre').waitFor();assert.match(await page.locator('pre').textContent(),/<script>/);assert.equal(await page.evaluate(()=>window.pwned),undefined);
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'下载',exact:true}).first().click();assert.equal((await download).suggestedFilename(),'语音.wav');
 await page.getByRole('button',{name:'加入素材库',exact:true}).first().click();await page.waitForFunction(()=>document.querySelector('[role=status]').textContent==='已加入素材库');assert.equal(imports,1);assert.equal(await page.getByRole('status').first().textContent(),'已加入素材库');
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 if(mobile)assert(reads.every(p=>p.startsWith('/v1/mobile/agent/files/r/')));
 }finally{await browser.close();}
});
test('video PDF document metadata errors and lifecycle',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage();await page.route('https://artifacts.fixture/**',r=>{
  const p=new URL(r.request().url()).pathname;if(p==='/')return r.fulfill({contentType:'text/html',body:'<html lang="en"><body><div id="cards"></div></body></html>'});
  if(p.includes('denied'))return r.fulfill({status:403,body:'denied'});
  return r.fulfill({contentType:p.includes('pdf')?'application/pdf':'video/mp4',body:'fixture'});
 });await page.goto('https://artifacts.fixture');await page.addScriptTag({content:fs.readFileSync(__dirname+'/../web/static/js/chat_artifacts.js','utf8')});
 await page.evaluate(()=>{window.files=['video','pdf','docx','denied'].map((name,i)=>({artifact_id:name,filename:name,media_type:['video/mp4','application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document','audio/wav'][i],size_bytes:10,url:'/v1/platform/sessions/s/artifacts/'+name+'/download'}));AI2AppsChatArtifacts.render(document.querySelector('#cards'),files);});
 assert.equal(await page.locator('.chat-artifact-card').count(),4);
 await page.getByRole('button',{name:'Load video',exact:true}).click();await page.locator('video[controls]').waitFor();
 await page.getByRole('button',{name:'Preview / open',exact:true}).click();await page.locator('iframe').waitFor();assert.equal(await page.locator('iframe').getAttribute('sandbox'),'');
 assert.match(await page.locator('.chat-artifact-card').nth(2).textContent(),/compatible app/);
 await page.getByRole('button',{name:'Load audio',exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll('[role=status]')[3].textContent.includes('403'));
 await page.evaluate(()=>{const first=document.querySelector('.chat-artifact-card');AI2AppsChatArtifacts.render(document.querySelector('#cards'),files);window.same=first===document.querySelector('.chat-artifact-card');});assert.equal(await page.evaluate(()=>same),true);
 await page.evaluate(()=>document.querySelector('#cards').remove());
 }finally{await browser.close();}
});
