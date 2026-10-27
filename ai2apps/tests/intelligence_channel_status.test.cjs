const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');const {chromium}=require('playwright');
const root=path.join(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
test('channel cards show independent refresh times and statuses on Desktop and Mobile',async()=>{
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
  await page.waitForSelector('[data-channel=c]');
  if(width===390){
   await page.locator('#channel-list [data-channel=c]').focus();
   const normal=await page.locator('#channel-list [data-channel=c]').evaluate(e=>getComputedStyle(e).backgroundColor);
   await page.locator('#channel-list [data-channel=c]').evaluate(e=>e.classList.remove('active'));
   assert.equal(await page.locator('#channel-list [data-channel=c]').evaluate(e=>getComputedStyle(e).backgroundColor),normal);
   await page.locator('#channel-list [data-channel=c]').hover();
   assert.equal(await page.locator('#channel-list [data-channel=c]').evaluate(e=>getComputedStyle(e).backgroundColor),normal);
  }

  await page.evaluate(()=>{
   fixture.channels=Array.from({length:5},(_,i)=>({id:'c'+i,name:'Channel '+i,sections:[]}));
   fixture.runs=[
    {id:'r0',channel_id:'c0',status:'completed',started_at:'2026-10-15T10:00:00Z',finished_at:'2026-10-15T10:10:00Z'},
    {id:'r1',channel_id:'c1',status:'failed',started_at:'2026-10-15T11:00:00Z',finished_at:'2026-10-15T11:10:00Z'},
    {id:'r2',channel_id:'c2',status:'partial',started_at:'2026-10-15T12:00:00Z',finished_at:'2026-10-15T12:10:00Z'},
    {id:'r3',channel_id:'c3',status:'running',started_at:'2026-10-15T13:00:00Z'},
    {id:'old',channel_id:'c3',status:'failed',finished_at:'2026-10-14T10:00:00Z'}
   ];window.dispatchEvent(new Event('focus'));
  });
  await page.waitForSelector('[data-channel=c4]');
  for(const [i,label] of ['Update complete','Update failed','Partially complete','Refreshing','Not refreshed yet'].entries()){
   const card=page.locator('[data-channel=c'+i+']'),status=card.locator('.channel-update-status');
   const text=await status.innerText(),detail=await status.getAttribute('title');assert.ok(detail.startsWith(label),detail);
   if(width===390||i>=3)assert.ok(text.startsWith(label),text);else assert.match(text,/ago/);
   if(i<4)assert.match(detail,/2026|Oct|10/);
   assert.equal(await status.isVisible(),true);
   assert.equal(await card.locator('.channel-label').innerText(),'Channel '+i);
   assert.equal(await status.evaluate(e=>e.scrollWidth<=e.clientWidth),true);
  }
  await page.evaluate(()=>{fixture.runs.find(r=>r.id==='r3').status='completed';fixture.runs.find(r=>r.id==='r3').finished_at='2026-10-15T13:05:00Z';window.dispatchEvent(new Event('focus'));});
  await page.waitForFunction(()=>document.querySelector('[data-channel=c3] .channel-update-status').title.startsWith('Update complete'));
  if(width===1440){
   for(const [hours,expected] of [[2,'2 hours ago'],[72,'3 days ago'],[240,'10 days ago'],[264,'10+ days ago']]){
    await page.evaluate(hours=>{fixture.runs[0].finished_at=new Date(Date.now()-hours*3600000-1000).toISOString();window.dispatchEvent(new Event('focus'));},hours);
    await page.waitForFunction(expected=>document.querySelector('[data-channel=c0] .channel-update-status').textContent===expected,expected);
   }
  }
  await page.close();
 }}finally{await browser.close();}
});
