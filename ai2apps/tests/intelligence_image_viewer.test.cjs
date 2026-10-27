const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');const root=path.join(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
test('image viewer fits controls, supports touch swipe, pinch and pan, and resets on navigation',async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{for(const viewport of [{width:390,height:550},{width:320,height:430},{width:844,height:300},{width:1440,height:900}]){
  const page=await browser.newPage({viewport,hasTouch:true,isMobile:true});
  await page.route('https://images.example/**',r=>r.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="1200"><rect width="800" height="1200" fill="#bed5e8"/><circle cx="400" cy="600" r="200" fill="#4f6680"/></svg>'}));
  const catalog=JSON.parse(read('web/i18n/zh.json'));let html=read('web/templates/system_apps/intelligence.html');const start=html.indexOf('<dialog id="article-image-dialog"');html=html.slice(start,html.indexOf('</dialog>',start)+9).replace(/\{\{ t\('([^']+)'\) \}\}/g,(_,k)=>catalog[k]);
  await page.setContent('<meta name="viewport" content="width=device-width,initial-scale=1">'+html);await page.addStyleTag({content:read('web/static/css/mobile_app.css')});await page.addStyleTag({content:read('web/static/css/intelligence.css')});await page.addStyleTag({content:read('web/static/css/app-readability.css')});
  const source=read('web/static/js/intelligence.js'),code=source.slice(source.indexOf('function installImageGestures('),source.indexOf("$('#article-image-large').onerror="));
  await page.addScriptTag({content:`const $=s=>document.querySelector(s),link=s=>s;window.IntelligenceCards={imageURL:(a,url)=>url};const state={articles:[]};const selectedId='a',articleImages=a=>a.images;${code};imagePreview={article:{title:'Long source caption '.repeat(30)},images:[0,1,2].map(i=>({url:'https://images.example/'+i,source_url:'https://example.com'})),index:1};renderImagePreview();$('#article-image-dialog').showModal();window.currentImage=()=>imagePreview.index;`});
  await page.waitForFunction(()=>document.querySelector('#article-image-large').naturalWidth>0);
  const fit=await page.locator('#article-image-dialog').evaluate(d=>{const r=d.getBoundingClientRect(),footer=d.querySelector('footer').getBoundingClientRect(),header=d.querySelector('header').getBoundingClientRect(),stage=d.querySelector('.intel-image-stage').getBoundingClientRect();return {scroll:d.scrollHeight-d.clientHeight,top:r.top,bottom:r.bottom,header:header.top,footer:footer.bottom,stage:stage.height};});
  const closeBounds=await page.locator('#article-image-dialog header [data-close]').boundingBox();
  assert.ok(closeBounds.width>=44&&closeBounds.height>=44);assert.ok(closeBounds.y>=fit.top&&closeBounds.y+closeBounds.height<=fit.bottom);
  const icon=await page.locator('#article-image-dialog header [data-close] svg').boundingBox();
  assert.ok(Math.abs(icon.x+icon.width/2-closeBounds.x-closeBounds.width/2)<1);
  assert.ok(Math.abs(icon.y+icon.height/2-closeBounds.y-closeBounds.height/2)<1);
  assert.ok(fit.scroll<=1,JSON.stringify({viewport,fit}));assert.ok(fit.top>=0&&fit.bottom<=viewport.height+1,JSON.stringify({viewport,fit}));assert.ok(fit.header>=fit.top&&fit.footer<=fit.bottom);assert.ok(fit.stage>20);
  for(const id of ['prev','next','origin','save']){const bounds=await page.locator('#article-image-'+id).boundingBox();assert.ok(bounds.y>=0&&bounds.y+bounds.height<=viewport.height);}
  if(viewport.width===390){
   const stage=page.locator('.intel-image-stage'),b=await stage.boundingBox(),cx=b.x+b.width/2,cy=b.y+b.height/2;
   const cdp=await page.context().newCDPSession(page),touch=(type,points)=>cdp.send('Input.dispatchTouchEvent',{type,touchPoints:points.map(([x,y,id])=>({x,y,id}))});
   const swipe=async delta=>{await touch('touchStart',[[cx,cy,1]]);await touch('touchMove',[[cx+delta,cy+5,1]]);await touch('touchEnd',[]);};
   await touch('touchStart',[[cx,cy,1]]);await touch('touchMove',[[cx-60,cy,1]]);
   const dragging=await page.locator('.intel-image-track').evaluate(e=>({x:new DOMMatrix(getComputedStyle(e).transform).m41,next:e.querySelector('[data-image-neighbor=next]').getBoundingClientRect().left,stage:e.parentElement.getBoundingClientRect().right}));
   assert.ok(dragging.x< -30);assert.ok(dragging.next<dragging.stage);
   await touch('touchCancel',[]);await page.waitForTimeout(260);
   assert.equal(await page.evaluate(()=>currentImage()),1);
   await swipe(-90);assert.equal(await page.evaluate(()=>currentImage()),2);await swipe(-90);assert.equal(await page.evaluate(()=>currentImage()),2);await swipe(90);assert.equal(await page.evaluate(()=>currentImage()),1);
   await touch('touchStart',[[cx-25,cy,1],[cx+25,cy,2]]);await touch('touchMove',[[cx-70,cy,1],[cx+70,cy,2]]);await touch('touchEnd',[]);
   assert.equal(await stage.evaluate(e=>e.classList.contains('is-zoomed')),true);assert.equal(await page.evaluate(()=>currentImage()),1);
   const before=await page.locator('#article-image-large').evaluate(e=>e.style.transform);
   await touch('touchStart',[[cx,cy,1]]);await touch('touchMove',[[cx+35,cy+35,1]]);await touch('touchEnd',[]);
   assert.notEqual(await page.locator('#article-image-large').evaluate(e=>e.style.transform),before);assert.equal(await page.evaluate(()=>currentImage()),1);
   await page.locator('#article-image-next').click();assert.equal(await page.evaluate(()=>currentImage()),2);assert.equal(await stage.evaluate(e=>e.classList.contains('is-zoomed')),false);
   await touch('touchStart',[[cx,cy,1]]);await touch('touchMove',[[cx+80,cy+2,1]]);await touch('touchCancel',[]);assert.equal(await page.evaluate(()=>currentImage()),2);
   await page.keyboard.press('ArrowLeft');assert.equal(await page.evaluate(()=>currentImage()),1);
   await page.screenshot({path:'/tmp/intelligence-image-viewer-mobile.png'});await cdp.detach();
  }
  await page.close();
 }}finally{await browser.close();}
});
