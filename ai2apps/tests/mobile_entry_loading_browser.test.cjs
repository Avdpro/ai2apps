const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),crypto=require('node:crypto');
const {chromium}=require('playwright');
const {execFileSync}=require('node:child_process');
const repo=path.resolve(__dirname,'../..');
const python=fs.existsSync(path.join(repo,'.venv/bin/python'))?path.join(repo,'.venv/bin/python'):'python3';
const rendered=JSON.parse(execFileSync(python,['-c',`from jinja2 import Environment,FileSystemLoader
from types import SimpleNamespace as N
e=Environment(loader=FileSystemLoader('ai2apps/web/templates'),autoescape=True)
import json
c=dict(request=N(url=N(path='/mobile/home')),owner_home=False,current_lang='zh',mobile_static=lambda p:'/mobile/static/'+p)
print(json.dumps(dict(owner=e.get_template('mobile.html').render(**dict(c,owner_home=True)),home=e.get_template('mobile_agent_pair.html').render(**c),chat=e.get_template('mobile_chat.html').render(**c,mobile_agent_ready=True,mobile_agent_signed=True))))`],{cwd:repo,encoding:'utf8'}));
const homeHTML=rendered.home;
const uuid='11111111-1111-4111-8111-111111111111',jti='22222222-2222-4222-8222-222222222222',nonce='A'.repeat(43);
function verify(jwk,input,sig){return crypto.verify('sha256',Buffer.from(input),{key:crypto.createPublicKey({key:jwk,format:'jwk'}),dsaEncoding:'ieee-p1363'},Buffer.from(sig,'base64url'));}
test('Mobile entry masks partial catalogs and coalesces connection events into one reveal',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}});let appReads=0,mountReads=0;const releases={};
  const catalog={items:[{app_key:'ai2apps.messager',display_name:'Messenger',entry_source:'builtin',navigation:{icon:'messages-square'}},{app_key:'ai2apps.todo',display_name:'Todo',entry_source:'builtin',navigation:{icon:'list-todo'}}]};
  await page.addInitScript(()=>document.addEventListener('DOMContentLoaded',()=>{window.reveals=[];const root=document.getElementById('ai2apps-mobile');new MutationObserver(()=>{if(!root.classList.contains('mobile-booting'))reveals.push({state:root.dataset.entryState,apps:document.querySelectorAll('.mobile-home-app').length});}).observe(root,{attributes:true,attributeFilter:['class']});}));
  await page.route('https://entry.fixture/**',async route=>{
   const p=new URL(route.request().url()).pathname;
   if(p==='/mobile')return route.fulfill({contentType:'text/html',body:rendered.owner});
   if(p.startsWith('/mobile/static/')){const f=path.join(repo,'ai2apps/web/static',p.slice('/mobile/static/'.length));return route.fulfill({path:f});}
   if(p==='/v1/mobile/apps'){const n=++appReads;await new Promise(resolve=>releases['apps'+n]=resolve);return route.fulfill({json:catalog});}
   if(p==='/v1/mobile/mounts'){const n=++mountReads;await new Promise(resolve=>releases['mounts'+n]=resolve);return route.fulfill({json:{items:[]}});}
   if(p==='/v1/mobile/owner-home/status')return route.fulfill({json:{authorized:true,agentAuthorized:false,ownerAuthorizationUrl:'https://coder.ai2apps.com/u/11111111-1111-4111-8111-111111111111'}});
   return route.fulfill({status:404,json:{detail:'not available'}});
  });
  const until=async fn=>{const end=Date.now()+5000;while(!fn()){if(Date.now()>end)throw Error('Entry fixture did not settle');await new Promise(r=>setTimeout(r,10));}};
  await page.goto('https://entry.fixture/mobile',{waitUntil:'domcontentloaded'});await until(()=>appReads===1&&mountReads===1);
  assert.equal(await page.locator('.mobile-boot-loading').isVisible(),true);assert.equal(await page.locator('.mobile-home').isVisible(),false);assert.equal(await page.locator('.mobile-dock').isVisible(),false);assert.equal(await page.locator('#ai2apps-mobile').getAttribute('aria-busy'),'true');
  releases.apps1();await page.waitForTimeout(60);assert.equal(await page.locator('.mobile-home').isVisible(),false);assert.equal(await page.locator('.mobile-home-app').count(),0);
  await page.screenshot({path:'/tmp/mobile-entry-loading-390.png'});
  await page.evaluate(()=>{for(let i=0;i<3;i++)dispatchEvent(new Event('ai2apps-agent-connection-ready'));});
  releases.mounts1();await until(()=>appReads===2&&mountReads===2);
  assert.equal(await page.locator('.mobile-home-app').count(),2);assert.equal(await page.locator('.mobile-home').isVisible(),false,'first pipeline must not reveal while a connection update is queued');assert.deepEqual(await page.evaluate(()=>reveals),[]);
  releases.apps2();releases.mounts2();await page.waitForFunction(()=>document.getElementById('ai2apps-mobile').dataset.entryState==='ready');
  assert.equal(await page.locator('.mobile-home').isVisible(),true);assert.equal(await page.locator('.mobile-dock').isVisible(),true);assert.equal(await page.locator('.mobile-boot-loading').isVisible(),false);assert.equal(await page.locator('#ai2apps-mobile').getAttribute('aria-busy'),'false');
  assert.deepEqual(await page.evaluate(()=>reveals),[{state:'ready',apps:2}]);assert.equal(appReads,2);assert.equal(mountReads,2);await page.screenshot({path:'/tmp/mobile-entry-ready-390.png'});
 }finally{await browser.close();}
});
test('Mobile entry exits loading into a usable error state when catalog fails',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage({viewport:{width:390,height:844}});let fail=true;
  await page.route('https://entry-error.fixture/**',async route=>{const p=new URL(route.request().url()).pathname;if(p==='/mobile')return route.fulfill({contentType:'text/html',body:rendered.owner});if(p.startsWith('/mobile/static/'))return route.fulfill({path:path.join(repo,'ai2apps/web/static',p.slice('/mobile/static/'.length))});if(p==='/v1/mobile/apps'){assert.equal(route.request().method(),'GET');return fail?route.fulfill({status:503,json:{detail:'Desktop temporarily unavailable'}}):route.fulfill({json:{items:[{app_key:'ai2apps.messager',display_name:'Messenger',entry_source:'builtin',navigation:{icon:'messages-square'}}]}});}if(p==='/v1/mobile/mounts')return route.fulfill({json:{items:[]}});if(p==='/v1/mobile/owner-home/status')return route.fulfill({json:{authorized:true}});return route.fulfill({status:404,json:{}});});
  await page.goto('https://entry-error.fixture/mobile');await page.waitForFunction(()=>document.getElementById('ai2apps-mobile').dataset.entryState==='error');assert.equal(await page.locator('.mobile-boot-loading').isVisible(),false);assert.equal(await page.getByRole('button',{name:'重试连接',exact:true}).isVisible(),true);assert.equal(await page.locator('.mobile-home-app').count(),0);assert.equal(await page.getByText('Desktop temporarily unavailable',{exact:true}).isVisible(),true);fail=false;await page.getByRole('button',{name:'重试连接',exact:true}).click();await page.waitForFunction(()=>document.getElementById('ai2apps-mobile').dataset.entryState==='ready');assert.equal(await page.locator('.mobile-home-app').count(),1);assert.equal(await page.locator('.mobile-hero-status').textContent(),'Owner 连接已就绪');assert.equal(await page.locator('.mobile-activity-card').isVisible(),true);
 }finally{await browser.close();}
});
