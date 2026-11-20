const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
const read=p=>fs.readFileSync(path.join(__dirname,'..',p),'utf8');
test('Bot assets use Chat image/file actions with original resource identity and safe preview',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({acceptDownloads:true});const imports=[];
  const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aYV8AAAAASUVORK5CYII=','base64');
  await page.route('https://bot-assets.fixture/**',async route=>{
   const r=route.request(),p=new URL(r.url()).pathname;
   if(p==='/')return route.fulfill({contentType:'text/html',body:'<html lang="en"><meta charset="utf-8"><main class="bot-message-stream" style="height:400px;overflow:auto"></main><div x-data="galleryResultViewer()" @bot-preview-material.window="openResults($event.detail.items,$event.detail.index)" @keydown.window="handlePreviewKey($event)">'+read('web/templates/system_apps/_gallery_preview_dialog.html').replace(/{{ t\('([^']+)'\) }}/g,'$1')+'</div></html>' });
   if(p.includes('/import-')){imports.push({path:p,body:r.postDataJSON()});return route.fulfill({json:{created:true}});}
   if(p.includes('image')||p.includes('att_photo'))return route.fulfill({contentType:'image/png',headers:{'Content-Disposition':'attachment; filename="image.png"'},body:png});
   if(p.includes('audio'))return route.fulfill({contentType:'audio/wav',body:Buffer.from('RIFF fixture')});
   if(p.includes('html'))return route.fulfill({contentType:'text/html',body:'<script>window.pwned=1</script>'});
   return route.fulfill({contentType:'text/plain',headers:{'Content-Disposition':'attachment; filename="notes.txt"'},body:'notes'});
  });
  await page.goto('https://bot-assets.fixture');
  for(const css of ['gallery.css','chat_message_stream.css','messager.css','chat_artifacts.css'])await page.addStyleTag({content:read('web/static/css/'+css)});
  for(const js of ['gallery.js','chat_image_actions.js','chat_artifacts.js','bot_materials.js','alpine.min.js'])await page.addScriptTag({content:read('web/static/js/'+js)});
  await page.evaluate(()=>{
   const root=document.querySelector('main');
   AI2AppsBotMaterials.outputs(root,[
    {url:'/v1/platform/sessions/s/artifacts/art_image/download',filename:'Panda.png',media_type:'image/png'},
    {url:'/v1/platform/sessions/s/artifacts/art_audio/download',filename:'Voice.wav',media_type:'audio/wav'},
    {url:'/v1/platform/sessions/s/artifacts/art_notes/download',filename:'Notes.txt',media_type:'text/plain'},
    {url:'/v1/platform/sessions/s/artifacts/art_html/download',filename:'Page.html',media_type:'text/html'},
    {url:'https://evil.invalid/image.png',filename:'unsafe.png',media_type:'image/png'}
   ]);
   AI2AppsBotMaterials.attachments(root,[{id:'att_photo',filename:'Photo.png',media_type:'image/png'}],'s');
  });
  assert.equal(await page.locator('.chat-image-card').count(),2);assert.equal(await page.locator('.chat-artifact-card').count(),3);
  const image=page.locator('.chat-image-card').first();
  const position=await page.locator('main').evaluate(e=>e.scrollTop);
  await image.getByRole('button',{name:'Preview image: Panda.png',exact:true}).click();
  await page.getByRole('dialog').waitFor();
  assert.equal(await page.locator('.gallery-preview-title strong').textContent(),'Panda.png');
  assert.equal(await page.locator('.gallery-preview-title small').textContent(),'1 / 5 · 0 B');
  await page.locator('.gallery-zoom-tools button').nth(1).click();assert.equal(await page.locator('.gallery-zoom-tools output').textContent(),'125%');
  await page.locator('.gallery-preview-nav.next').click();assert.equal(await page.locator('.gallery-preview-title strong').textContent(),'Voice.wav');
  await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});
  assert.equal(imports.length,0);
  assert.equal(await page.locator('main').evaluate(e=>e.scrollTop),position);
  assert.equal(await image.getByRole('button',{name:'Preview image: Panda.png',exact:true}).evaluate(e=>e===document.activeElement),true);
  await image.getByRole('button',{name:'Add to Gallery',exact:true}).click();
  await image.getByRole('status').getByText('Added to Gallery').waitFor();
  assert.deepEqual(imports[0],{path:'/v1/platform/gallery/assets/import-artifact/s/art_image',body:{sourceAppId:'ai2apps.messager'}});
  await page.locator('.chat-image-card').last().getByRole('button',{name:'Add to Gallery',exact:true}).click();
  assert.deepEqual(imports[1],{path:'/v1/platform/gallery/assets/import-attachment/s/att_photo',body:{sourceAppId:'ai2apps.messager'}});
  const download=page.waitForEvent('download');await image.getByRole('button',{name:'Save image',exact:true}).click();assert.equal((await download).suggestedFilename(),'chat-image.png');
  const audio=page.locator('.chat-artifact-card').filter({hasText:'Voice.wav'});await audio.getByRole('button',{name:'Load audio',exact:true}).click();await page.locator('.gallery-preview-media audio[controls]').waitFor();await page.keyboard.press('Escape');
  const notes=page.locator('.chat-artifact-card').filter({hasText:'Notes.txt'});await notes.getByRole('button',{name:'Preview / open',exact:true}).click();await page.locator('.gallery-generic-preview').waitFor();await page.keyboard.press('Escape');
  await notes.getByRole('button',{name:'Add to library',exact:true}).click();assert.equal(imports[2].body.sourceAppId,'ai2apps.messager');
  await page.evaluate(()=>{const embedded=document.createElement('aside');embedded.id='embedded';embedded.innerHTML='<img src="/v1/platform/sessions/s/artifacts/art_image/preview" alt="Embedded">';document.body.append(embedded);AI2AppsBotMaterials.enhance(embedded);AI2AppsBotMaterials.outputs(embedded,[{url:'/v1/platform/sessions/s/artifacts/art_image/download',filename:'Embedded',media_type:'image/png'}]);});
  assert.equal(await page.locator('#embedded .chat-image-card').count(),1);
  assert.equal(await page.locator('#embedded img').getAttribute('src'),'/v1/platform/sessions/s/artifacts/art_image/download');
  assert.equal(await page.locator('iframe').count(),0);assert.equal(await page.evaluate(()=>window.pwned),undefined);
  const ref=await image.evaluate(node=>{const dt=new DataTransfer();node.dispatchEvent(new DragEvent('dragstart',{bubbles:true,dataTransfer:dt}));return JSON.parse(dt.getData('application/x-ai2apps-session-artifact'));});
  assert.equal(ref.artifactId,'art_image');assert.equal(ref.sourceAppId,'ai2apps.messager');
  await page.evaluate(()=>{const shell=document.createElement('div');shell.id='bubble-layout';shell.className='chat-shell';shell.style.width='800px';shell.innerHTML='<div class="bot-message-list"><article class="user-message"><div class="user-message-bubble">hi</div></article></div>';document.body.append(shell);AI2AppsBotMaterials.attachments(shell.querySelector('article'),[{id:'att_photo',filename:'Photo.png',media_type:'image/png',size_bytes:68}],'s');});
  const bubble=page.locator('#bubble-layout .user-message-bubble').first();
  await page.evaluate(()=>{
   const messages=document.querySelector('#bubble-layout .bot-message-list');
   for(const [id, text] of [['short','几点了'],['pending','几点了'],['poke','👋 Poke'],['newline','第一行\n第二行'],['long','longunbrokenword'.repeat(100)]]) {
    const message=document.createElement('article');
    message.className='user-message';
    if(id==='pending')message.dataset.pendingRequestId='test';
    const body=document.createElement('div');
    body.id=id;
    body.className='user-message-bubble';
    body.textContent=text;
    message.append(body);
    messages.append(message);
   }
  });
  for(const width of [800,260]){
   await page.locator('#bubble-layout').evaluate((shell,width)=>shell.style.width=width+'px',width);
   for(const [id,lines] of [['short',1],['pending',1],['poke',1],['newline',2],['long',3]]){
    const layout=await page.locator('#'+id).evaluate(e=>{
     const rect=e.getBoundingClientRect(),style=getComputedStyle(e),oneLine=parseFloat(style.lineHeight);
     return {lines:Math.round((rect.height-parseFloat(style.paddingTop)-parseFloat(style.paddingBottom))/oneLine),
      width:rect.width,overflow:e.scrollWidth>e.clientWidth,right:rect.right,east:e.closest('.bot-message-list').getBoundingClientRect().right};
    });
    assert.ok(id==='long'?layout.lines>=lines:layout.lines===lines, JSON.stringify({id,width,...layout}));
    assert.ok(!layout.overflow&&Math.abs(layout.right-layout.east)<1&&layout.width<=Math.min(600,width*.72)+1);
   }
  }
  await page.locator('#bubble-layout').evaluate(shell=>shell.style.width='800px');
  const sizes=await bubble.evaluate(e=>({bubble:e.getBoundingClientRect().width,message:e.parentElement.getBoundingClientRect().width}));
  assert.ok(sizes.bubble<100&&sizes.message>sizes.bubble+50,JSON.stringify(sizes));
  assert.equal(await page.locator('#bubble-layout .chat-image-card img').count(),1);
  assert.equal(await page.locator('#bubble-layout .chat-artifact-card').count(),0);
  await bubble.evaluate(e=>e.textContent='Long prompt '.repeat(100));
  assert.ok(await bubble.evaluate(e=>e.getBoundingClientRect().width<=672&&e.scrollWidth<=e.clientWidth));
  await page.evaluate(()=>AI2AppsBotMaterials.dispose(document.querySelector('main')));
 }finally{await browser.close();}
});
