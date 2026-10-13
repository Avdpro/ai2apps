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
  const state={channels:[{id:'c',name:'体育',interests:'赛车新闻',sections:[{id:'s',name:'赛车'}]}],articles:[{id:'a',channel_id:'c',title:'频道设置',summary:'用户摘要：腕表',body:'用户文章正文',section_id:'s',sources:[]}],sources:[],runs:[{id:'r',channel_id:'c',status:'running',message:'后台采集中：频道设置',started_at:new Date().toISOString(),progress:{phase:'list',pages_read:2,articles_extracted:1,sources_completed:0,active_pages:[{url:'https://example.com',source_name:'频道设置',status:'queued'}]}}]};
  await page.evaluate(({catalog,state})=>{window._t=catalog;window.AI2APPS_MOBILE_SURFACE=true;window.IntelligenceEntities={init(){}};window.EventSource=class{addEventListener(){}close(){}};window.fetch=async(url)=>({ok:true,json:async()=>url.includes('browser-profiles')?[{key:'default',name:'Default'}]:url.endsWith('/drafts')?{items:[]}:state});},{catalog,state});
  for(const file of ['intelligence_i18n','intelligence_cards','intelligence'])await page.addScriptTag({path:path.join(root,'web/static/js/'+file+'.js')});
  await page.waitForSelector('[data-channel="c"]');await page.click('[data-channel="c"]');
  await page.waitForFunction(()=>document.querySelector('#intel-content').textContent.includes('频道设置'));
  assert.match(await page.locator('#intel-content').innerText(),/频道设置/);
  await page.locator('[data-tab="runs"]').evaluate(e=>e.click());
  await page.waitForFunction(()=>document.querySelector('#intel-content').textContent.includes('Collecting in the background'));
  const content=await page.locator('#intel-content').innerText();assert.match(content,/Collecting in the background: 频道设置/);assert.match(content,/Pages read/);assert.match(content,/Queued/);assert.doesNotMatch(content,/后台采集中|读取列表|准备采集|等待执行/);
  await page.setViewportSize({width:1440,height:900});assert.match(await page.locator('#intel-content').innerText(),/Collecting in the background: 频道设置/);
 }finally{await browser.close();}
});
