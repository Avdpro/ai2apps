const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.join(__dirname,'..'),locales=['en','zh','zh-TW','ja','ko','fr','de','es','pt-BR','ru'];
const read=relative=>fs.readFileSync(path.join(root,relative),'utf8');
const escape=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
test('all ten languages render Desktop and Mobile without translating user data',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{for(const locale of locales){for(const width of [1440,390]){
  const catalog={...JSON.parse(read('web/i18n/en.json')),...JSON.parse(read('web/i18n/'+locale+'.json'))};
  const content=read('web/templates/system_apps/intelligence.html').split('{% block content %}')[1].split('{% endblock %}')[0].replace(/\{\{ t\('([^']+)'\) \}\}/g,(_,key)=>escape(catalog[key]||key));
  const page=await browser.newPage({viewport:{width,height:1000},hasTouch:width===390});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('https://intel.test/**',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html lang="'+locale+'"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+content+'</html>'}));
  await page.goto('https://intel.test');await page.addStyleTag({content:read('web/static/css/intelligence.css')});
  await page.evaluate(({catalog,mobile})=>{
   window._t=catalog;window.AI2APPS_MOBILE_SURFACE=mobile;window.EventSource=class{addEventListener(){}close(){}};
   const state={channels:[{id:'c',name:'腕表 Model X',interests:'原文内容保持不变',sections:[{id:'s',name:'我的栏目'}]}],articles:[{id:'a',channel_id:'c',title:'原文标题 Model Y',summary:'原文摘要',body:'原文正文',section_id:'s',sources:[]}],sources:[],runs:[{id:'r',channel_id:'c',status:'running',message:'后台采集中：原文来源',started_at:new Date().toISOString(),progress:{phase:'list',pages_read:2,articles_extracted:1,sources_completed:0,active_pages:[{url:'https://example.com',source_name:'原文来源',status:'queued'}]}}]};
   window.fetch=async url=>({ok:true,json:async()=>String(url).includes('/conversation')?{turns:[]}:String(url).includes('browser-profiles')?[{key:'default',name:'Default'}]:String(url).includes('knowledge')?{items:[]}:JSON.parse(JSON.stringify(state))});
  },{catalog,mobile:width===390});
  for(const name of ['mini_app_chat','intelligence_i18n','intelligence_cards','intelligence_entities','intelligence'])await page.addScriptTag({content:read('web/static/js/'+name+'.js')});
  await page.waitForSelector('[data-channel="c"]');await page.click('[data-channel="c"]');await page.waitForSelector('[data-article="a"]');
  assert.match(await page.locator('#intel-content').innerText(),/原文标题 Model Y/);
  const i18n=await page.evaluate(()=>({settings:IntelligenceI18n.text('频道设置'),runs:IntelligenceI18n.text('更新记录'),collecting:IntelligenceI18n.message('后台采集中：原文来源')}));
  assert.equal(i18n.settings,catalog['intelligence.ui.10c2b3f19265']);
  await page.locator('[data-tab="runs"]').evaluate(e=>e.click());
  assert.ok((await page.locator('#intel-content').innerText()).includes(i18n.collecting),locale+' '+width+' status');
  assert.match(await page.locator('#intel-content').innerText(),/原文来源/);
  await page.locator('#edit-channel').evaluate(e=>e.click());await page.waitForFunction(()=>document.querySelector('#channel-dialog').open);
  assert.equal(await page.locator('#channel-dialog-title').textContent(),i18n.settings);
  assert.equal(await page.locator('#channel-name').inputValue(),'腕表 Model X');
  const bounds=await page.locator('#channel-dialog').boundingBox();assert.ok(bounds.x>=-1&&bounds.x+bounds.width<=width+1,locale+' '+width+' dialog bounds');
  const submit=page.locator('#channel-form button[type=submit]');assert.equal(await submit.textContent(),catalog['intelligence.ui.a59b14292059']);
  const overflow=await submit.evaluate(e=>e.scrollWidth>e.clientWidth+2);assert.equal(overflow,false,locale+' '+width+' save button overflow');
  if((locale==='de'&&width===1440)||(locale==='ja'&&width===390))await page.screenshot({path:'/tmp/intelligence-'+locale+'-'+width+'.png'});
  assert.deepEqual(errors,[],locale+' '+width+' JS errors');
  await page.close();
 }}}
 finally{await browser.close();}
});
