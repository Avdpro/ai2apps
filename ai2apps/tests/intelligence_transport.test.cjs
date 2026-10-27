const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');const {chromium,webkit}=require('playwright');
const root=path.join(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
test('malformed transport responses recover for reads and never repeat mutations',async()=>{
 const browser=await (process.env.INTELLIGENCE_TEST_WEBKIT?webkit.launch({headless:true}):chromium.launch({channel:'chrome',headless:true}));
 try{for(const width of [390,1440]){
  const page=await browser.newPage({viewport:{width,height:850},hasTouch:width===390});
  const catalog=JSON.parse(read('web/i18n/en.json'));const html=read('web/templates/system_apps/intelligence.html').split('{% block content %}')[1].split('{% endblock %}')[0].replace(/\{\{ t\('([^']+)'\) \}\}/g,(_,k)=>catalog[k]||k);
  await page.route('https://images.example/**',r=>r.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="350"><rect width="600" height="350" fill="silver"/></svg>'}));
  await page.route('https://intel.test/**',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+html+'</html>'}));
  await page.goto('https://intel.test');await page.addStyleTag({content:read('web/static/css/intelligence.css')});
  await page.evaluate(({catalog,mobile})=>{
   window._t=catalog;window.AI2APPS_MOBILE_SURFACE=mobile;window.EventSource=class{addEventListener(){}close(){}};
   window.fixture={channels:[{id:'c',name:'Channel',interests:'News',sections:[{id:'s',name:'Section'}]}],sources:[],runs:[],articles:Array.from({length:45},(_,i)=>({id:'a'+i,channel_id:'c',section_id:'s',title:'Story '+i,summary:'Summary '+i,body:'Body '+i,read:false,updated_at:'2026-10-16T00:00:'+String(59-i).padStart(2,'0')+'Z',sources:[],cover_image:{url:'https://images.example/'+i}}))};
   window.snapshotPlans=[];window.snapshotCalls=0;window.patchCalls=0;window.badPatch=false;
   window.fetch=async(url,options={})=>{if(url.split('?')[0]==='/v1/platform/intelligence'){snapshotCalls++;if(snapshotPlans.length)return new Response(snapshotPlans.shift(),{status:200,headers:{'Content-Type':'text/html'}});return new Response(JSON.stringify(fixture));}
    if(options.method==='PATCH'){patchCalls++;if(badPatch)return new Response('');}
if(options.method==='PATCH'){const article=fixture.articles.find(a=>url.endsWith('/'+a.id));Object.assign(article,JSON.parse(options.body));return {ok:true,json:async()=>({...article})};}return {ok:true,json:async()=>url.endsWith('/entities')?{items:[]}:url.endsWith('/conversation')?{turns:[]}:JSON.parse(JSON.stringify(fixture))};};
  },{catalog,mobile:width===390});
  for(const name of ['mini_app_chat','intelligence_i18n','intelligence_cards','intelligence_entities','intelligence'])await page.addScriptTag({content:read('web/static/js/'+name+'.js')});
  await page.waitForSelector('[data-channel=c]');await page.click('[data-channel=c]');await page.waitForSelector('[data-article=a0]');
  await page.evaluate(()=>{window.kept=document.querySelector('[data-article=a0]');window.keptImage=kept.querySelector('img');window.snapshotPlans=['<html>relay reconnect</html>'];window.beforeCalls=snapshotCalls;window.dispatchEvent(new Event('focus'));});
  await page.waitForFunction(()=>snapshotCalls>=beforeCalls+2);await page.waitForTimeout(100);
  assert.equal(await page.locator('#intel-notice').isVisible(),false);
  assert.equal(await page.evaluate(()=>kept===document.querySelector('[data-article=a0]')&&keptImage===kept.querySelector('img')),true);
  await page.evaluate(()=>{snapshotPlans=['','{"broken":'];beforeCalls=snapshotCalls;window.dispatchEvent(new Event('focus'));});
  await page.waitForFunction(()=>snapshotCalls>=beforeCalls+2);await page.waitForSelector('#intel-notice');
  assert.doesNotMatch(await page.locator('#intel-notice').innerText(),/expected pattern|JSON|SyntaxError/);
  assert.match(await page.locator('#intel-notice').innerText(),/interrupted|retry/i);
  assert.equal(await page.evaluate(()=>kept===document.querySelector('[data-article=a0]')),true);
  await page.locator('[data-article=a0] [data-card-menu]').click();
  await page.evaluate(()=>{window.badPatch=true;window.beforePatch=patchCalls;});
  await page.locator('[data-card-favorite]').click();await page.waitForFunction(()=>patchCalls===beforePatch+1);await page.waitForTimeout(600);
  assert.equal(await page.evaluate(()=>patchCalls),await page.evaluate(()=>beforePatch+1));
  assert.doesNotMatch(await page.locator('#intel-notice').innerText(),/expected pattern|JSON|SyntaxError/);
  await page.close();
 }}finally{await browser.close();}
});

test('Mobile gateway normalizes malformed relay envelopes and HTML errors',async()=>{
 const browser=await (process.env.INTELLIGENCE_TEST_WEBKIT?webkit.launch({headless:true}):chromium.launch({channel:'chrome',headless:true}));
 try{
  const page=await browser.newPage();await page.route('https://intel.test/**',r=>r.fulfill({contentType:'text/html',body:'<html><script id="mobile-app-gateway" type="application/json">{"apiPrefix":"/v1/platform/fixture","resourceBase":"/resource/","bridge":"/bridge"}</script></html>'}));await page.goto('https://intel.test');
  await page.evaluate(()=>{window.plans=[];window.bridgeCalls=0;window.t=()=> 'Connection interrupted; retry';window.fetch=async()=>{bridgeCalls++;const next=plans.shift();return new Response(next.body,{status:next.status});};});
  await page.addScriptTag({content:read('web/static/js/mobile_app_gateway.js')});
  const results=await page.evaluate(async()=>{
   const cases=[{status:200,body:'<html>reconnecting</html>'},{status:200,body:''},{status:200,body:'{}'},{status:200,body:JSON.stringify({status:200,contentType:'application/json',body:'!bad!'})},{status:503,body:'<html>unavailable</html>'},{status:401,body:'<html>sign in</html>'}];
   const out=[];for(const plan of cases){plans.push(plan);const response=await fetch('/v1/platform/fixture',{method:'PATCH',body:'{}'});out.push({status:response.status,value:await response.json()});}
   plans.push({status:200,body:JSON.stringify({status:200,contentType:'application/json',body:btoa(JSON.stringify({ok:true}))})});out.push({status:200,value:await(await fetch('/v1/platform/fixture')).json()});return {out,calls:bridgeCalls};
  });
  assert.equal(results.calls,7);for(let i=0;i<6;i++){assert.equal(results.out[i].status,i===4?503:i===5?401:502);assert.match(results.out[i].value.error.code,/mobile_gateway_/);}assert.deepEqual(results.out[6].value,{ok:true});
  await browser.close();
 }finally{await browser.close();}
});
