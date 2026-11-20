const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
for(const signed of [false,true])test('Mobile image thumbnail first, original only on open/download: '+signed,async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{const page=await browser.newPage({viewport:{width:390,height:844}}),reads=[];
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aYV8AAAAASUVORK5CYII=','base64');
 await page.route('https://images.fixture/**',async route=>{const u=new URL(route.request().url());if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:'<!doctype html><html lang="en"><body><div id="cards"></div></body></html>'});reads.push(u.pathname+u.search);return route.fulfill({contentType:'image/png',body:png});});
 await page.goto('https://images.fixture/');for(const name of ['chat_artifacts.js'])await page.addScriptTag({content:fs.readFileSync(__dirname+'/../web/static/js/'+name,'utf8')});
 await page.evaluate(signed=>{
  window.AI2AppsAgentConnection={signedFetch:(path,options)=>fetch(path,options)};
  const path='/owned/picture',request=(file,action,signal)=>action==='gallery'?null:fetch(path+(action==='thumbnail'?'?preview=mobile':''),{signal});
  const original=file=>AI2AppsMobileImages.open({load:async signal=>{const r=await fetch(signed?'/v1/mobile/agent/files/run/art_picture':path,{signal}),url=URL.createObjectURL(await r.blob());return {url,dispose:()=>URL.revokeObjectURL(url)};}});
  AI2AppsChatArtifacts.render(document.getElementById('cards'),[{artifact_id:'art_picture',filename:'picture.png',media_type:'image/png',url:'/v1/platform/sessions/session/artifacts/art_picture/download'}],{mobile:true,signed,runId:'run',includeImages:true,request:signed?null:request,openImage:original});
 },signed);
 await page.locator('.chat-artifact-preview img').waitFor();await page.waitForFunction(()=>document.querySelector('.chat-artifact-preview img').naturalWidth>0);
 assert.equal(reads.length,1);assert.match(reads[0],/\?preview=mobile$/);
 await page.locator('.chat-artifact-preview img').click();await page.waitForFunction(()=>document.querySelector('.mobile-original-image img')?.naturalWidth>0);assert.equal(reads.filter(x=>!x.includes('?preview=mobile')).length,1);
 await page.getByRole('button',{name:'Close',exact:true}).click();await page.locator('.mobile-original-image').waitFor({state:'detached'});
 const download=page.waitForEvent('download');await page.getByRole('button',{name:'Download',exact:true}).click();await download;
 assert.equal(reads.filter(x=>!x.includes('?preview=mobile')).length,2);assert.equal(reads.filter(x=>x.includes('?preview=mobile')).length,1);
 await page.close();
 }finally{await browser.close();}
});
