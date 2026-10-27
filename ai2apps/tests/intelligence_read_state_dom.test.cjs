const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');const {chromium}=require('playwright');
const root=path.join(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
test('read acknowledgement, polling, pagination and unread filtering preserve surviving cards and images',async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{for(const width of [390,1440]){
  const page=await browser.newPage({viewport:{width,height:850},hasTouch:width===390});
  const catalog=JSON.parse(read('web/i18n/en.json'));const html=read('web/templates/system_apps/intelligence.html').split('{% block content %}')[1].split('{% endblock %}')[0].replace(/\{\{ t\('([^']+)'\) \}\}/g,(_,k)=>catalog[k]||k);
  await page.route('https://images.example/**',r=>r.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="350"><rect width="600" height="350" fill="silver"/></svg>'}));
  await page.route('https://intel.test/**',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+html+'</html>'}));
  await page.goto('https://intel.test');await page.addStyleTag({content:read('web/static/css/intelligence.css')});
  await page.evaluate(({catalog,mobile})=>{
   window._t=catalog;window.AI2APPS_MOBILE_SURFACE=mobile;window.EventSource=class{addEventListener(){}close(){}};
   window.fixture={channels:[{id:'c',name:'Channel',interests:'News',sections:[{id:'s',name:'Section'}]}],sources:[],runs:[],articles:Array.from({length:45},(_,i)=>({id:'a'+i,channel_id:'c',section_id:'s',title:'Story '+i,summary:'Summary '+i,body:'Body '+i,read:false,updated_at:'2026-10-16T00:00:'+String(59-i).padStart(2,'0')+'Z',sources:[],cover_image:{url:'https://images.example/'+i}}))};
   window.fetch=async(url,options={})=>{if(options.method==='PATCH'){const article=fixture.articles.find(a=>url.endsWith('/'+a.id));await new Promise(resolve=>{window.finishRead=resolve;});Object.assign(article,JSON.parse(options.body));return {ok:true,json:async()=>({...article})};}return {ok:true,json:async()=>url.endsWith('/entities')?{items:[]}:url.endsWith('/conversation')?{turns:[]}:JSON.parse(JSON.stringify(fixture))};};
  },{catalog,mobile:width===390});
  for(const name of ['mini_app_chat','intelligence_i18n','intelligence_cards','intelligence_entities','intelligence'])await page.addScriptTag({content:read('web/static/js/'+name+'.js')});
  await page.waitForSelector('[data-channel=c]');await page.click('[data-channel=c]');await page.waitForSelector('[data-article=a0]');
  await page.evaluate(()=>{window.kept=[...document.querySelectorAll('#intel-content [data-article]')];window.images=kept.map(e=>e.querySelector('img'));window.cardRemovals=0;new MutationObserver(records=>{for(const record of records)for(const n of record.removedNodes)if(n.nodeType===1&&n.matches('[data-article]'))cardRemovals++;}).observe(document.querySelector('#intel-content'),{childList:true});});
  await page.locator('[data-article=a0]').click();await page.waitForSelector('.intel-article-loading');assert.equal(await page.locator('#channel-chat').isHidden(),true);assert.equal(await page.locator('#intel-article-reader').isVisible(),true);assert.match(await page.locator('.intel-article-loading').innerText(),/Loading article/);assert.equal(await page.locator('[data-article=a0]').evaluate(e=>e.classList.contains('selected')),true);assert.equal(await page.locator('#intel-content .intel-story.selected').count(),1);await page.evaluate(()=>finishRead());
  if(width===390){
   await page.waitForSelector('[data-article=a0] .intel-unread-ribbon.is-pending-read',{state:'attached'});
   await page.waitForTimeout(500);
   assert.equal(await page.locator('[data-article=a0] .intel-unread-ribbon.is-pending-read').count(),1);
   await page.evaluate(()=>{window.exitSeen=false;new MutationObserver(()=>{if(document.querySelector('[data-article=a0] .is-leaving'))window.exitSeen=true;}).observe(document.querySelector('[data-article=a0]'),{subtree:true,attributes:true});});
   await page.locator('#intel-reader [data-mobile-back]').click();
   await page.waitForFunction(()=>document.querySelector('#intel-app').dataset.mobilePage==='channel');
  }
  if(width===390)await page.waitForFunction(()=>exitSeen);
  else await page.waitForSelector('[data-article=a0] .intel-unread-ribbon.is-leaving',{state:'attached'});
  if(width!==390){
  const motion=await page.locator('[data-article=a0] .intel-unread-ribbon').evaluate(e=>({clip:getComputedStyle(e).overflow,cardClip:getComputedStyle(e.closest('[data-article]')).overflow,animation:getComputedStyle(e.firstElementChild).animationName}));
  assert.equal(motion.clip,'hidden');assert.equal(motion.cardClip,'hidden');assert.equal(motion.animation,'intel-unread-leave');
  }
  await page.waitForFunction(()=>!document.querySelector('[data-article=a0] .intel-unread-ribbon'));
  assert.equal(await page.evaluate(()=>cardRemovals),0);
  assert.equal(await page.evaluate(()=>kept.every((e,i)=>e===document.querySelectorAll('#intel-content [data-article]')[i]&&e.querySelector('img')===images[i])),true);
  await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await page.waitForTimeout(150);assert.equal(await page.evaluate(()=>cardRemovals),0);
  await page.locator('[data-list-more=articles]').evaluate(e=>e.click());assert.equal(await page.locator('#intel-content [data-article]').count(),40);assert.equal(await page.evaluate(()=>kept.every((e,i)=>e===document.querySelectorAll('#intel-content [data-article]')[i])),true);
  await page.selectOption('#article-filter','unread',{force:true});assert.equal(await page.locator('[data-article=a0]').count(),0);assert.equal(await page.evaluate(()=>document.querySelector('[data-article=a1]')===kept[1]),true);
  // Genuine content updates must still replace the affected card only.
  await page.evaluate(()=>{fixture.articles[1].summary='Changed summary';window.dispatchEvent(new Event('focus'));});await page.waitForFunction(()=>document.querySelector('[data-article=a1]').textContent.includes('Changed summary'));
  assert.equal(await page.evaluate(()=>document.querySelector('[data-article=a1]')!==kept[1]),true);assert.equal(await page.evaluate(()=>document.querySelector('[data-article=a2]')===kept[2]),true);
  // Selecting another article updates the existing cards before the delayed read request returns.
  await page.locator('[data-article=a2]').evaluate(e=>e.click());
  await page.waitForSelector('.intel-article-loading');
  assert.equal(await page.locator('[data-article=a2]').evaluate(e=>e.classList.contains('selected')),true);
  assert.equal(await page.locator('#intel-content .intel-story.selected').count(),1);
  assert.equal(await page.evaluate(()=>document.querySelector('[data-article=a2]')===kept[2]),true);
  // Switching section while a read is pending must synchronously update navigation
  // and return to channel chat, including after the old request eventually completes.
  await page.locator('[data-section=s]').evaluate(e=>e.click());
  assert.equal(await page.locator('[data-section=s]').getAttribute('aria-pressed'),'true');
  assert.equal(await page.locator('[data-section=""]').getAttribute('aria-pressed'),'false');
  assert.equal(await page.locator('[data-write=section]').isVisible(),true);
  assert.equal(await page.locator('#show-channel-chat').evaluate(e=>e.classList.contains('active')),true);
  assert.equal(await page.locator('#intel-article-reader').isHidden(),true);
  assert.equal(await page.locator('.intel-article-loading').count(),0);
  await page.evaluate(()=>finishRead());
  await page.waitForTimeout(200);
  assert.equal(await page.locator('#intel-article-reader').isHidden(),true);
  assert.equal(await page.locator('#show-channel-chat').evaluate(e=>e.classList.contains('active')),true);
  assert.equal(await page.locator('.intel-article-loading').count(),0);
  await page.close();
 }}finally{await browser.close();}
});
