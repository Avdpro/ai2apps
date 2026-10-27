const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');const {chromium,webkit}=require('playwright');
const root=path.join(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
test('cold start distinguishes loading, empty, failure and populated channels',async()=>{
 const browser=await (process.env.INTELLIGENCE_TEST_WEBKIT?webkit.launch({headless:true}):chromium.launch({channel:'chrome',headless:true}));
 try{for(const width of [390,1440]){for(const scenario of ['populated','empty','failed']){
  const page=await browser.newPage({viewport:{width,height:850},hasTouch:width===390});
  const catalog=JSON.parse(read('web/i18n/en.json'));const html=read('web/templates/system_apps/intelligence.html').split('{% block content %}')[1].split('{% endblock %}')[0].replace(/\{\{ t\('([^']+)'\) \}\}/g,(_,k)=>catalog[k]||k);
  await page.route('https://images.example/**',r=>r.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="350"><rect width="600" height="350" fill="silver"/></svg>'}));
  await page.route('https://intel.test/**',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+html+'</html>'}));
  await page.goto('https://intel.test');await page.addStyleTag({content:read('web/static/css/intelligence.css')});
  await page.evaluate(({catalog,mobile})=>{
   window._t=catalog;window.AI2APPS_MOBILE_SURFACE=mobile;window.EventSource=class{addEventListener(){}close(){}};
   window.fixture={channels:[{id:'c',name:'Channel',interests:'News',sections:[{id:'s',name:'Section'}]}],sources:[],runs:[],articles:Array.from({length:45},(_,i)=>({id:'a'+i,channel_id:'c',section_id:'s',title:'Story '+i,summary:'Summary '+i,body:'Body '+i,read:false,updated_at:'2026-10-16T00:00:'+String(59-i).padStart(2,'0')+'Z',sources:[],cover_image:{url:'https://images.example/'+i}}))};
   window.snapshotGate=new Promise(resolve=>window.releaseSnapshot=resolve);
   window.profileGate=new Promise(()=>{});window.failSnapshot=false;
   window.fetch=async url=>{
    if(url.includes('browser-profiles'))return profileGate;
    if(url.split('?')[0]==='/v1/platform/intelligence'){
     if(failSnapshot)return new Response('<html>temporarily unavailable</html>',{status:503});
     await snapshotGate;return new Response(JSON.stringify(fixture));
    }
    return {ok:true,json:async()=>url.endsWith('/entities')?{items:[]}:url.endsWith('/conversation')?{turns:[]}:fixture};
   };

  },{catalog,mobile:width===390});
  assert.equal(await page.locator('#channel-loading').isVisible(),true);
  assert.equal(await page.locator('#sidebar-create').isVisible(),false);
  assert.equal(await page.locator('#new-channel').isVisible(),false);
  if(scenario==='failed')await page.evaluate(()=>failSnapshot=true);
  for(const name of ['mini_app_chat','intelligence_i18n','intelligence_cards','intelligence_entities','intelligence'])await page.addScriptTag({content:read('web/static/js/'+name+'.js')});
  assert.equal(await page.locator('#channel-loading-text').innerText(),'Loading channel information…');
  assert.equal(await page.locator('#sidebar-create').isVisible(),false);
  if(scenario==='failed'){
   await page.waitForFunction(()=>document.querySelector('#intel-app').dataset.channelLoad==='failed');
   assert.equal(await page.locator('#channel-loading-retry').isVisible(),true);
   assert.equal(await page.locator('#sidebar-create').isVisible(),false);
   await page.evaluate(()=>failSnapshot=false);await page.locator('#channel-loading-retry').click();
   assert.equal(await page.locator('#intel-app').getAttribute('data-channel-load'),'loading');
  }
  await page.evaluate(empty=>{if(empty){fixture.channels=[];fixture.articles=[];}releaseSnapshot();},scenario==='empty');
  await page.waitForFunction(()=>document.querySelector('#intel-app').dataset.channelLoad==='ready');
  assert.equal(await page.locator('#channel-loading').isVisible(),false);
  assert.equal(await page.locator('#sidebar-create').isVisible(),true);
  assert.equal(await page.locator('#channel-list').getAttribute('aria-busy'),'false');
  assert.equal(await page.locator('#channel-list [data-channel]').count(),scenario==='empty'?0:1);
  await page.close();
 }}}finally{await browser.close();}
});
