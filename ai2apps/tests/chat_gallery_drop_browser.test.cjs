const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const read=f=>fs.readFileSync(path.join(__dirname,'..',f),'utf8');
test('actual Gallery drag producer reaches Chat FileReader and produces an image attachment',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  const page=await browser.newPage();
  const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j5nQAAAAASUVORK5CYII=','base64');
  await page.route('http://chat.test/**',route=>{
   const url=route.request().url();
   if(url.endsWith('/assets/image/content'))return route.fulfill({contentType:'image/png',body:png});
   if(url.endsWith('/assets/image'))return route.fulfill({json:{id:'image',name:'Gallery.png',media_type:'image/png',size_bytes:png.length}});
   return route.fulfill({contentType:'text/html',body:'<div id="drop">Chat composer</div>'});
  });
  await page.goto('http://chat.test/');
  await page.addScriptTag({content:read('web/static/js/gallery_picker.js')});
  await page.addScriptTag({content:read('web/static/js/gallery.js')});
  const html=read('web/templates/chat.html');
  const methods=html.slice(html.indexOf('    async handleDrop(event)'),html.indexOf('    removeImage(index)'));
  await page.addScriptTag({content:`window.app={${methods}uploadDocuments:[],uploadImages:[],chatSettings:{maxImageSizeMb:10},hasVisionSupport:()=>true,imageLimitReached:()=>false}; window.t=k=>k; window.alert=m=>{throw Error(m)}; document.querySelector('#drop').ondrop=e=>{e.preventDefault();app.handleDrop(e)};`});
  await page.evaluate(()=>{
   const gallery=galleryApp();gallery.notifyStudioDrag=()=>{};gallery.contentUrl=()=>'/v1/platform/gallery/assets/image/content';
   const transfer=new DataTransfer();gallery.dragAsset({dataTransfer:transfer},{id:'image',kind:'image',name:'Gallery.png'});
   if(transfer.files.length)throw Error('Fixture must use Gallery IDs, not Files');
   document.querySelector('#drop').dispatchEvent(new DragEvent('drop',{dataTransfer:transfer,bubbles:true,cancelable:true}));
  });
  await page.waitForFunction(()=>app.uploadImages[0]?.base64?.startsWith('data:image/png;base64,'));
  assert.equal(await page.evaluate(()=>app.uploadDocuments.length),0);
  assert.equal(await page.evaluate(()=>app.uploadImages.length),1);
 }finally{await browser.close();}
});
