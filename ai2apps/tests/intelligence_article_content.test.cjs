const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.join(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
test('mixed article body uses source-bound images, existing viewer and safe legacy fallback on Desktop/Mobile',async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{for(const width of [390,1440]){
  const page=await browser.newPage({viewport:{width,height:900},hasTouch:width===390});
  const catalog=JSON.parse(read('web/i18n/en.json'));
  const html=read('web/templates/system_apps/intelligence.html').split('{% block content %}')[1].split('{% endblock %}')[0].replace(/\{\{ t\('([^']+)'\) \}\}/g,(_,k)=>catalog[k]||k);
  await page.route('https://cdn.example.org/**',r=>r.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="350"><rect width="600" height="350" fill="silver"/></svg>'}));
  await page.route('https://intel.test/**',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1">'+html}));
  await page.goto('https://intel.test');await page.addStyleTag({content:read('web/static/css/intelligence.css')});
  await page.evaluate(({catalog,mobile})=>{
   window._t=catalog;window.AI2APPS_MOBILE_SURFACE=mobile;window.EventSource=class{addEventListener(){}close(){}};
   const images=[{id:'img_a',url:'https://cdn.example.org/a.jpg',alt:'Dial <script>unsafe</script>',source_url:'https://example.org/a'},
    {id:'img_b',url:'https://cdn.example.org/b.jpg',alt:'Movement',source_url:'https://example.org/b'},
    {id:'img_c',url:'https://cdn.example.org/c.jpg',alt:'Extra',source_url:'https://example.org/a'}];
   const article={id:'a',channel_id:'c',title:'Report',summary:'Summary',body:'First paragraph.[1]\n\nSecond paragraph.[2]',updated_at:'2026-10-25T01:00:00Z',read:true,images,
    sources:[{url:'https://example.org/a',source_name:'A'},{url:'https://example.org/b',source_name:'B'}],content_schema:'ai2apps.article-content/v1',content_blocks:[{type:'paragraph',text:'First paragraph.[1]'},{type:'image',image_id:'img_a'},{type:'paragraph',text:'Second paragraph.[2]'},{type:'image',image_id:'img_b'}]};
   window.fixture={channels:[{id:'c',name:'Channel',sections:[]}],articles:[article],sources:[],runs:[]};
   window.fetch=async(url,options={})=>({ok:true,json:async()=>url.endsWith('/entities')?{items:[]}:url.endsWith('/conversation')?{turns:[]}:options.method==='PATCH'?article:JSON.parse(JSON.stringify(fixture))});
  },{catalog,mobile:width===390});
  for(const name of ['mini_app_chat','intelligence_i18n','intelligence_cards','intelligence_entities','intelligence'])await page.addScriptTag({content:read('web/static/js/'+name+'.js')});
  await page.waitForSelector('[data-channel=c]');await page.click('[data-channel=c]');await page.locator('[data-article=a]').click();
  await page.waitForSelector('.intel-inline-image');
  const body=page.locator('#intel-article-reader>.intel-body');
  assert.deepEqual(await body.locator(':scope > *').evaluateAll(nodes=>nodes.map(n=>n.tagName)),['P','FIGURE','P','FIGURE']);
  assert.equal(await body.locator('script').count(),0);
  assert.match(await body.locator('figcaption').first().innerText(),/Dial <script>unsafe<\/script>/);
  assert.equal(await body.locator('figcaption a').nth(1).getAttribute('href'),'https://example.org/b');
  assert.equal(await page.locator('.intel-image-grid button').count(),3);
  const box=await body.locator('figure').first().boundingBox();assert.ok(box.width<=width);
  await body.locator('[data-image-index="1"]').click();
  await page.waitForSelector('#article-image-dialog[open]');
  assert.match(await page.locator('#article-image-caption').innerText(),/^2 \/ 3/);
  assert.equal(await page.locator('#article-image-origin').getAttribute('href'),'https://example.org/b');
  await page.locator('[data-close=article-image-dialog]').click();
  await page.evaluate(()=>{const a=fixture.articles[0];a.content_schema='ai2apps.article-content/v2';a.editorial_sections=[{id:'s1',title:'Movement'},{id:'s2',title:'Comfort'}];let n=0,pid;for(const b of a.content_blocks){if(b.type==='paragraph'){n++;pid='p_'+String(n).repeat(24);b.id=pid;b.section_id='s'+n;}else b.paragraph_id=pid;}window.dispatchEvent(new Event('focus'));});
  await page.waitForSelector('.intel-body-section');
  assert.deepEqual(await body.locator('h3').allTextContents(),['Movement','Comfort']);
  assert.equal(await body.locator('figure').count(),2);
  // Source-backed manual imports preserve more than six original photographs.
  await page.evaluate(()=>{const a=fixture.articles[0],paragraphs=a.content_blocks.filter(b=>b.type==='paragraph');a.images=Array.from({length:24},(_,i)=>({id:'img_'+String(i).padStart(24,'0'),url:'https://cdn.example.org/photo'+i+'.jpg',source_url:a.sources[0].url,alt:'Source photograph '+i}));a.content_blocks=[paragraphs[0],...a.images.map(i=>({type:'image',image_id:i.id,paragraph_id:paragraphs[0].id})),paragraphs[1]];window.dispatchEvent(new Event('focus'));});
  await page.waitForFunction(()=>document.querySelectorAll('.intel-inline-image').length===24);
  assert.equal(await body.locator('figure').count(),24);
  assert.equal(await page.locator('.intel-image-grid button').count(),24);
  assert.equal(await page.locator('.intel-article-images h3').innerText(),'Article images · 24');
  // A stale/invalid block set must fall back to canonical text, never partial content.
  await page.evaluate(()=>{fixture.articles[0].content_blocks[1].image_id='missing';window.dispatchEvent(new Event('focus'));});
  await page.waitForFunction(()=>!document.querySelector('.intel-inline-image'));
  assert.equal(await body.innerText(),'First paragraph.[1]\n\nSecond paragraph.[2]');
  await page.close();
 }}finally{await browser.close();}
});
