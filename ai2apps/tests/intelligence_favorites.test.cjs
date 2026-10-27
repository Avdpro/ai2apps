const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');const {chromium}=require('playwright');
const root=path.join(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
test('favorite toggle, tooltip and fixed category work on Desktop and Mobile without reader redraw',async()=>{
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
   window.fetch=async(url,options={})=>{if(options.method==='PATCH'){const article=fixture.articles.find(a=>url.endsWith('/'+a.id));Object.assign(article,JSON.parse(options.body));return {ok:true,json:async()=>({...article})};}return {ok:true,json:async()=>url.endsWith('/entities')?{items:[]}:url.endsWith('/conversation')?{turns:[]}:JSON.parse(JSON.stringify(fixture))};};
  },{catalog,mobile:width===390});
  for(const name of ['mini_app_chat','intelligence_i18n','intelligence_cards','intelligence_entities','intelligence'])await page.addScriptTag({content:read('web/static/js/'+name+'.js')});
  await page.waitForSelector('[data-channel=c]');await page.click('[data-channel=c]');await page.waitForSelector('[data-article=a0]');
  await page.locator('[data-article=a0]').click();await page.waitForSelector('#intel-article-reader .intel-favorite');
  const favorite=page.locator('#intel-article-reader [data-favorite=a0]');
  for(const [selector,label] of [['[data-article-chat-purpose=research]','Deep research'],['[data-write=article]','Write a draft'],['[data-article-chat]:not([data-article-chat-purpose])','Chat']]){
   const action=page.locator('.intel-article-head '+selector);
   assert.equal(await action.innerText(),'');
   assert.equal(await action.getAttribute('aria-label'),label);
   assert.equal(await action.getAttribute('data-action-tip'),label);
   assert.equal(await action.locator('[data-lucide]').count(),1);
   assert.equal(await action.isVisible(),true);
   if(width===1440){await action.hover();await page.waitForTimeout(350);assert.equal(await action.evaluate(e=>getComputedStyle(e,'::after').visibility),'visible');}
  }
  assert.equal(await favorite.isVisible(),true);assert.equal(await favorite.getAttribute('aria-pressed'),'false');assert.equal(await favorite.innerText(),'');
  await page.evaluate(()=>window.readerImage=document.querySelector('#intel-article-reader img'));
  await favorite.click();await page.waitForFunction(()=>document.querySelector('[data-favorite=a0]').getAttribute('aria-pressed')==='true');
  assert.equal(await favorite.innerText(),'');assert.equal(await favorite.locator('svg').getAttribute('fill'),'currentColor');assert.equal(await favorite.getAttribute('data-favorite-tip'),'Unsave article');
  assert.equal(await page.evaluate(()=>readerImage===document.querySelector('#intel-article-reader img')),true);
  await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>readerImage===document.querySelector('#intel-article-reader img')),true);
  if(width===1440){await favorite.hover();await page.waitForTimeout(350);assert.equal(await favorite.evaluate(e=>getComputedStyle(e,'::after').visibility),'visible');}
  if(width===390){await page.locator('#intel-reader [data-mobile-back]').click();await page.waitForTimeout(300);}
  const category=page.locator('[data-section="$favorites"]');assert.equal(await category.count(),1);assert.equal(await category.getAttribute('draggable'),null);assert.match(await category.innerText(),/Saved.*1/s);
  await category.click();assert.equal(await page.locator('#intel-content [data-article]').count(),1);assert.equal(await page.locator('#intel-content [data-article=a0]').count(),1);
  await page.locator('[data-article=a0]').click();await page.waitForSelector('#intel-article-reader [data-favorite=a0]');
  await favorite.click();await page.waitForFunction(()=>document.querySelector('[data-favorite=a0]').getAttribute('aria-pressed')==='false');
  assert.equal(await favorite.locator('svg').getAttribute('fill'),'none');assert.equal(await favorite.getAttribute('data-favorite-tip'),'Save article');
  if(width===390){await page.locator('#intel-reader [data-mobile-back]').click();await page.waitForTimeout(300);}
  assert.equal(await page.locator('#intel-content [data-article]').count(),0);assert.match(await page.locator('#intel-content').innerText(),/No saved articles/);
  await page.close();
 }}finally{await browser.close();}
});
