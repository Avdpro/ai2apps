const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');const root=path.join(__dirname,'..');
test('English Mobile and desktop preserve Chinese user data and translate run activity',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:390,height:780},hasTouch:true});
  const catalog=JSON.parse(fs.readFileSync(path.join(root,'web/i18n/en.json')));
  let html=fs.readFileSync(path.join(root,'web/templates/system_apps/intelligence.html'),'utf8').split('{% block content %}')[1].split('{% endblock %}')[0];
  html=html.replace(/\{\{ t\('([^']+)'\) \}\}/g,(_,key)=>catalog[key]||key);
  await page.route('https://intel.test/**',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html lang="en-US"><meta name="viewport" content="width=device-width,initial-scale=1">'+html+'</html>'}));
  await page.goto('https://intel.test');await page.addStyleTag({path:path.join(root,'web/static/css/intelligence.css')});
  const state={channels:[{id:'c',name:'体育',interests:'赛车新闻',sections:[{id:'s',name:'赛车'}]}],articles:[{id:'a',channel_id:'c',title:'频道设置',summary:'用户摘要：腕表',body:'用户文章正文',section_id:'s',sources:[]}],sources:[],runs:[{id:'r',channel_id:'c',status:'running',message:'后台采集中：频道设置',started_at:new Date().toISOString(),progress:{cached_pages:7,cache_articles_saved:2,refresh_stage:'fresh',phase:'list',pages_read:2,articles_extracted:1,sources_completed:0,active_pages:[{url:'https://example.com',source_name:'频道设置',status:'queued'}]}}]};
  await page.evaluate(({catalog,state})=>{window._t=catalog;window.fixtureState=state;window.fixtureDrafts=[];window.AI2APPS_MOBILE_SURFACE=true;window.IntelligenceEntities={init(){}};window.EventSource=class{addEventListener(){}close(){}};window.fetch=async(url)=>({ok:true,json:async()=>url.includes('/articles/')&&url.endsWith('/entities')?{items:[{id:'e',name:'Watch X',kind:'model',attribute_groups:[{key:'case_thickness',values:[{value:'11 mm',evidence:[{article_id:'a',article_title:'频道设置',quote:'厚度 11 mm'}]}]}]}]}:url.endsWith('/conversation')?{turns:[]}:url.includes('/posts?')?{items:[{id:'post',author:'作者',text:'原帖内容 <script>不执行</script>',briefings:[],url:'https://x.com/a/status/1'}],next_offset:null}:url.endsWith('/promote')?state.articles[0]:url.includes('browser-profiles')?[{key:'default',name:'Default'}]:url.includes('/drafts?')?{items:window.fixtureDrafts.slice(Number(new URL(url,'https://intel.test').searchParams.get('offset')),Number(new URL(url,'https://intel.test').searchParams.get('offset'))+20),next_offset:Number(new URL(url,'https://intel.test').searchParams.get('offset'))+20<window.fixtureDrafts.length?Number(new URL(url,'https://intel.test').searchParams.get('offset'))+20:null}:JSON.parse(JSON.stringify(state))});},{catalog,state});
  for(const file of ['mini_app_chat','intelligence_i18n','intelligence_cards','intelligence_entities','intelligence'])await page.addScriptTag({path:path.join(root,'web/static/js/'+file+'.js')});
  await page.waitForSelector('[data-channel="c"]');await page.click('[data-channel="c"]');
  await page.waitForFunction(()=>document.querySelector('#intel-content').textContent.includes('频道设置'));
  assert.match(await page.locator('#intel-content').innerText(),/频道设置/);
  assert.equal(await page.locator('#mobile-channel-refresh-status').innerText(),'Refreshing');
  await page.waitForTimeout(350);
  const mobileLayout=await page.locator('.intel-mobile-channel-title-row').evaluate(e=>{const [a,b]=e.children;return {name:a.getBoundingClientRect().top,status:b.getBoundingClientRect().top,right:b.getBoundingClientRect().right,width:innerWidth};});
  assert.ok(Math.abs(mobileLayout.name-mobileLayout.status)<4);assert.ok(mobileLayout.right<mobileLayout.width);

  await page.locator('[data-tab="runs"]').evaluate(e=>e.click());
  await page.waitForFunction(()=>document.querySelector('#intel-content').textContent.includes('Collecting in the background'));
  const content=await page.locator('#intel-content').innerText();assert.match(content,/Collecting in the background: 频道设置/);assert.match(content,/Pages read/);assert.match(content,/Cached pages reused.*7/);assert.match(content,/Briefings recovered from cache.*2/);assert.match(content,/Pages newly read this run.*0/);assert.match(content,/Queued/);assert.doesNotMatch(content,/后台采集中|读取列表|准备采集|等待执行/);
  await page.locator('.intel-main .intel-mobile-menu summary').click();
  await page.locator('.intel-main .intel-mobile-menu [data-browse-posts]').click();
  assert.match(await page.locator('#posts-list').innerText(),/原帖内容/);
  assert.match(await page.locator('#posts-list').innerText(),/Supplementary evidence/);
  await page.locator('[data-promote-post]').click();
  await page.waitForTimeout(300);
  assert.equal(await page.locator('#intel-notice').isVisible(),false,await page.locator('#intel-notice').innerText());
  await page.waitForFunction(()=>!document.querySelector('#posts-dialog').open);
  assert.match(await page.locator('#intel-article-reader').innerText(),/频道设置/);
  await page.waitForSelector('#article-entities .intel-article-entity');
  assert.match(await page.locator('#article-entities').innerText(),/Watch X/);
  assert.match(await page.locator('#article-entities').innerText(),/11 mm/);
  assert.match(await page.locator('#article-entities').innerText(),/Evidence from this article/);
  await page.setViewportSize({width:1440,height:900});assert.match(await page.locator('#intel-content').innerText(),/Collecting in the background: 频道设置/);
  assert.equal(await page.locator('#channel-refresh-status').innerText(),'Refreshing');
  await page.evaluate(()=>{window.fixtureState.runs[0].status='completed';window.fixtureState.runs[0].finished_at='2026-10-15T04:30:00Z';window.dispatchEvent(new Event('focus'));});
  await page.waitForFunction(()=>document.querySelector('#channel-refresh-status').textContent.startsWith('Last refresh'));
  const desktopLayout=await page.locator('.intel-channel-title-row').evaluate(e=>[...e.children].map(n=>{const r=n.getBoundingClientRect();return {top:r.top,bottom:r.bottom};}));
  assert.ok(desktopLayout[1].top>=desktopLayout[0].top&&desktopLayout[1].bottom<=desktopLayout[0].bottom);
  assert.match(await page.locator('#channel-refresh-status').innerText(),/Oct 15/);
  await page.evaluate(()=>{window.fixtureState.runs=[];window.dispatchEvent(new Event('focus'));});
  await page.waitForFunction(()=>document.querySelector('#channel-refresh-status').textContent==='Not refreshed yet');
  await page.setViewportSize({width:390,height:780});await page.click('[data-channel="c"]');
  assert.equal(await page.locator('#mobile-channel-refresh-status').innerText(),'Not refreshed yet');
  await page.evaluate(()=>{const a=window.fixtureState.articles[0];window.fixtureState.articles=Array.from({length:45},(_,n)=>({...a,id:'article-'+n,title:'Story '+n,updated_at:'2026-10-15T00:00:'+String(n).padStart(2,'0')+'Z'}));window.dispatchEvent(new Event('focus'));});
  await page.waitForFunction(()=>document.querySelectorAll('#intel-content [data-article]').length===20);
  assert.match(await page.locator('#intel-content [data-article]').first().innerText(),/Story 44/);
  await page.click('[data-list-more="articles"]');assert.equal(await page.locator('#intel-content [data-article]').count(),40);
  await page.click('[data-list-more="articles"]');assert.equal(await page.locator('#intel-content [data-article]').count(),45);
  assert.equal(await page.locator('[data-list-more="articles"]').count(),0);
  await page.setViewportSize({width:1440,height:900});await page.evaluate(()=>{window.AI2APPS_MOBILE_SURFACE=false;});await page.fill('#search-articles','Story');assert.equal(await page.locator('#intel-content [data-article]').count(),20);
  await page.setViewportSize({width:1440,height:900});assert.equal(await page.locator('#intel-content [data-article]').count(),20);
  await page.evaluate(()=>{window.fixtureDrafts=Array.from({length:45},(_,n)=>({id:'draft-'+n,channel_id:'c',title:'Draft '+n,kind:'short_post',revision:1,scope_label:'Channel',updated_at:'2026-10-15T00:00:'+String(44-n).padStart(2,'0')+'Z'}));});
  await page.click('[data-tab="drafts"]');await page.waitForFunction(()=>document.querySelectorAll('[data-draft-preview]').length===20);
  await page.click('[data-list-more="drafts"]');await page.waitForFunction(()=>document.querySelectorAll('[data-draft-preview]').length===40);
  await page.click('[data-list-more="drafts"]');await page.waitForFunction(()=>document.querySelectorAll('[data-draft-preview]').length===45);
  assert.equal(await page.locator('[data-list-more="drafts"]').count(),0);



 }finally{await browser.close();}
});
