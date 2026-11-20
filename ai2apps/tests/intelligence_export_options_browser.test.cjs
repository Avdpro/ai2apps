const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{spawnSync}=require('node:child_process'),{pathToFileURL}=require('node:url'),{chromium,webkit}=require('playwright');
const root=path.join(__dirname,'..'),source=fs.readFileSync(path.join(root,'web/static/js/intelligence.js'),'utf8');
const code=source.slice(source.indexOf('function initExportOptions(){'),source.indexOf('\nfunction initBackupTransfer(){'));
test('export options freeze dates, single HTML scope, progress, cancel and recovery on desktop/mobile',async()=>{
 const browser=await(process.env.INTEL_EXPORT_WEBKIT?webkit.launch({headless:true}):chromium.launch({headless:true,channel:'chrome'}));
 try{for(const width of [1200,390]){
  const page=await browser.newPage({viewport:{width,height:width===390?600:950},isMobile:width===390,hasTouch:width===390});
  await page.route('https://fixture.test/**',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><style>:root{--font-sans:system-ui}</style>'}));await page.goto('https://fixture.test');
  await page.addStyleTag({path:path.join(root,'web/static/css/intelligence.css')});
  await page.evaluate(()=>{window.MobileAppResource=url=>'/mobile/mount'+url;window.handoffText=(zh,en)=>en;window.safe=fn=>fn;window.calls=[];window.status='running';window.requestJSON=async(url,options={})=>{calls.push({url,options});if(url.endsWith('/exports/cover'))return{url:'/v1/platform/intelligence/imports/'+'a'.repeat(64)+'/share-cover.jpg'};if(url.endsWith('/cancel')){window.status='cancelled';return {status:'cancelled'};}if(options.method==='POST')return {id:'stask_'+'a'.repeat(32),status:'queued'};return {status:window.status,message:'Embedding images',progress:{images_total:2,images_done:1,images_failed:0},result:{format:'html',size:2000,images_failed:1,missing_images:[{url:'https://example.org/unavailable.jpg',reason:'HTTP 404'}]}};};});
  await page.addScriptTag({content:code+'\nwindow.openExport=initExportOptions();'});
  await page.evaluate(()=>window.openExport('channel'));
  const dialog=page.locator('.intel-export-dialog');const selects=dialog.locator('select');
  assert.deepEqual(await selects.nth(3).locator('option').evaluateAll(xs=>xs.map(x=>x.value)),['zip','html']);
  await selects.nth(1).selectOption('24');await selects.nth(3).selectOption('html');
  await dialog.locator('input[type=checkbox]').uncheck();await dialog.locator('input[type=file]').setInputFiles({name:'cover.png',mimeType:'image/png',buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j6xkAAAAASUVORK5CYII=','base64')});
  assert(!(await dialog.getByRole('button',{name:'Use default cover',exact:true}).isDisabled()));
  if(process.env.INTEL_EXPORT_SCREENSHOT)await page.screenshot({path:process.env.INTEL_EXPORT_SCREENSHOT+'-'+width+'.png'});
  await dialog.getByRole('button',{name:'Export',exact:true}).click();
  const payload=await page.evaluate(()=>JSON.parse(window.calls.find(x=>x.url==='/v1/platform/intelligence/exports'&&x.options.method==='POST').options.body));
  assert.match(payload.share_cover,/\/share-cover.jpg$/);assert.equal(payload.include_toc,false);assert.equal(payload.format,'html');assert.equal(payload.channel_id,'channel');assert.ok(Math.abs((new Date(payload.until)-new Date(payload.since))-86400000)<2000);
  await dialog.getByRole('button',{name:'Close',exact:true}).click();assert.equal(await page.locator('dialog[open]').count(),0);
  await page.evaluate(()=>window.openExport('another'));await dialog.getByRole('button',{name:'Cancel export',exact:true}).click();
  await page.waitForFunction(()=>window.calls.some(c=>c.url.endsWith('/cancel')));
  await page.waitForFunction(()=>!document.querySelector('.intel-export-dialog button[type=submit]').disabled);
  await selects.nth(0).selectOption('all');assert.equal(await selects.nth(3).inputValue(),'zip');
  assert.equal(await selects.nth(3).locator('option[value=html]').evaluate(o=>o.disabled),true);
  await page.evaluate(()=>{window.status='completed';sessionStorage.setItem('intelligence-export-v1','stask_'+'a'.repeat(32));});
  await dialog.getByRole('button',{name:'Close',exact:true}).click();
  await page.addScriptTag({content:'window.restoreExport=initExportOptions();'});await page.evaluate(()=>window.restoreExport('channel'));
  const restored=page.locator('.intel-export-dialog').last();await restored.getByRole('link',{name:'Download file'}).waitFor();
  assert.match(await restored.innerText(),/1 images missing/);
  assert.equal(await restored.locator('details li').textContent(),'https://example.org/unavailable.jpg · HTTP 404');
  assert.match(await restored.getByRole('link',{name:'Download file'}).getAttribute('href'),/^\/mobile\/mount\/v1\/platform\/intelligence\/exports\//);
  assert.equal(await restored.evaluate(e=>e.scrollTop),0);
  const save=restored.getByRole('button',{name:'Save to Gallery',exact:true});await save.scrollIntoViewIfNeeded();if(process.env.INTEL_EXPORT_SCREENSHOT)await page.screenshot({path:process.env.INTEL_EXPORT_SCREENSHOT+'-ready-'+width+'.png'});await save.click();await restored.getByRole('button',{name:'Saved to Gallery',exact:true}).waitFor();assert(await restored.getByRole('button',{name:'Saved to Gallery',exact:true}).isDisabled());assert.equal(await page.evaluate(()=>calls.filter(c=>c.url.endsWith('/gallery')).length),1);
  await restored.locator('select').nth(3).selectOption('html');assert.equal(await restored.getByRole('link',{name:'Download file'}).isVisible(),false);assert.match(await restored.innerText(),/Options changed/);
  assert.ok(await restored.evaluate(e=>e.getBoundingClientRect().width)<=width);
  await page.close();
 }}finally{await browser.close();}
});
test('standalone HTML reads offline without search or filters',async()=>{
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'intel-html-test-')),file=path.join(tmp,'channel.html');
 const py=spawnSync(path.join(root,'../.venv/bin/python'),['-c',`import asyncio,io\nfrom pathlib import Path\nfrom PIL import Image\nfrom ai2apps.intelligence.html_export import build_html\nfrom ai2apps.intelligence.article_content import image_id\nraw=io.BytesIO();Image.new('RGB',(20,20),'red').save(raw,format='PNG')\nu='https://example.org/image.png';sid=image_id('https://example.org/source',u)\na={'title':'Watch Alpha','summary':'Summary','body':'Paragraph [1]','sources':[{'url':'https://example.org/source','title':'Original'}],'images':[{'id':sid,'url':u,'source_url':'https://example.org/source'}],'content_schema':'ai2apps.article-content/v1','content_blocks':[{'type':'paragraph','text':'Paragraph [1]'},{'type':'image','image_id':sid}]}\nselected={'channels':[{'id':'c','data':{'name':'Watches','interests':'News','sections':[]}}],'articles':[{'id':'a','data':a}]}\ndata,info=asyncio.run(build_html(None,'owner',selected,loader=lambda *args:(raw.getvalue(),'image/png'),include_toc=False))\nPath(${JSON.stringify(file)}).write_bytes(data)`],{cwd:path.join(root,'..'),encoding:'utf8'});
 assert.equal(py.status,0,py.stderr);
 const browser=await(process.env.INTEL_EXPORT_WEBKIT?webkit.launch({headless:true}):chromium.launch({headless:true,channel:'chrome'}));
 try{const page=await browser.newPage(),external=[];page.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url());});await page.goto(pathToFileURL(file).href);await page.waitForFunction(()=>document.querySelector('img').naturalWidth===20);assert.deepEqual(external,[]);assert.equal(await page.locator('input,select').count(),0);assert.equal(await page.locator('script').count(),1);assert.equal(await page.locator('article:visible').count(),1);await page.setViewportSize({width:390,height:600});await page.locator('.article-content').evaluate(e=>e.style.minHeight='1200px');await page.locator('summary').first().click();await page.waitForFunction(()=>document.querySelector('details.article-card').dataset.read==='true');assert.equal(await page.locator('.read-ribbon .read').isVisible(),true);await page.waitForFunction(()=>document.querySelector('.article-content').getBoundingClientRect().top<360&&window.scrollY>0);await page.locator('summary').first().click();assert.equal(await page.locator('.read-ribbon .read').isVisible(),true);const preview=await browser.newContext({javaScriptEnabled:false});const offline=await preview.newPage();await offline.goto(pathToFileURL(file).href);assert.equal(await offline.locator('nav').count(),0);assert.equal(await offline.locator('details.article-card[open]').count(),0);assert.match(await offline.locator('summary img').getAttribute('src'),/^data:image\/png;base64,/);assert.equal(await offline.locator('summary img').evaluate(i=>i.naturalWidth),20);await offline.locator('summary').first().click();assert.equal(await offline.locator('details.article-card[open]').count(),1);await preview.close();assert.deepEqual(external,[]);}finally{await browser.close();fs.rmSync(tmp,{recursive:true,force:true});}
});
