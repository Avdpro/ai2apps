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
test('browser origin key, Cloud handoff, lease proof and exact local request signature interoperate',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});let jwk,thumb,leaseRequests=0,businessWrites=0,activeRun=false,appsSession=false,exchanges=0,rejectLease=false;
 try{const page=await browser.newPage({viewport:{width:390,height:844}});
 await page.route('https://device-fixture.ai2apps.com/**',async route=>{const req=route.request(),url=new URL(req.url()),p=url.pathname;
  if(p==='/mobile')return route.fulfill({contentType:'text/html',body:rendered.owner});
  if(p==='/mobile/home')return route.fulfill({contentType:'text/html',body:homeHTML});
  if(p==='/mobile/agent-chat')return route.fulfill({contentType:'text/html',headers:{'Content-Security-Policy':"default-src 'self'; img-src 'self' blob:; style-src 'self' 'unsafe-inline', default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'"},body:rendered.chat});
  if(p.startsWith('/mobile/static/')){const relative=p.slice('/mobile/static/'.length),file=path.resolve(__dirname,'../web/static',relative);if(!fs.existsSync(file))return route.fulfill({status:404,body:''});return route.fulfill({contentType:p.endsWith('.js')?'application/javascript':p.endsWith('.css')?'text/css':'application/octet-stream',body:fs.readFileSync(file)});}
  if(p==='/v1/mobile/apps/arbitrary.installed-app/open')return route.fulfill({json:{id:'fixture-mount',app_instance_id:'fixture-instance',app_key:'arbitrary.installed-app',content_url:'/mobile/fixture-app',renderer:'host'}});
  if(p==='/mobile/fixture-app')return route.fulfill({contentType:'text/html',body:'<main>Authorized App body</main>'});
  if(p==='/client.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.resolve(__dirname,'../web/static/js/mobile_agent_connection.js'))});
  if(p==='/v1/mobile/member-session/exchange'){
   const body=req.postDataJSON();assert.equal(body.appHandoffProtocol,'desktop-mobile-app-handoff-v1');assert.equal(body.mobileConnectionId,uuid);assert.match(body.handoff,/^oh1\./);exchanges++;appsSession=true;
   return route.fulfill({headers:{'Set-Cookie':'__Secure-ai2apps_owner_home=fixture-owner; Path=/; Secure; HttpOnly; SameSite=Strict'},json:{connected:true}});
  }
  if(['/v1/mobile/apps','/v1/mobile/mounts','/v1/mobile/owner-home/status'].includes(p)&&appsSession){
   assert.ok(req.headers().cookie.includes('__Secure-ai2apps_owner_home=fixture-owner'));
   const apps=[{app_key:'ai2apps.general-chat',display_name:'聊天',entry_source:'builtin',navigation:{icon:'message-square'}},{app_key:'arbitrary.installed-app',display_name:'Authorized Package',entry_source:'package',navigation:{icon:'box'}},{app_key:'ai2apps.intelligence',display_name:'情报中心',entry_source:'builtin',navigation:{icon:'radio'}}];
   apps.push(...Array.from({length:5},(_,i)=>({app_key:'arbitrary.more.'+i,display_name:'More authorized '+i,entry_source:'package',navigation:{icon:'box'}})));
   return route.fulfill({json:p.endsWith('/apps')?{items:apps}:p.endsWith('/mounts')?{items:[]}:{authorized:true,leaseExpiresAt:Date.now()/1000+60}});
  }
  if(p.endsWith('/bootstrap'))return route.fulfill({json:{enabled:true}});
  if(p.endsWith('/challenge'))return route.fulfill({json:{nonce,clientKeyThumbprint:thumb}});
  if(p.endsWith('/lease')){if(rejectLease)return route.fulfill({status:503,json:{detail:'fixture temporary lease failure'}});leaseRequests++;const b=req.postDataJSON();assert.deepEqual(b.publicKey,jwk);assert.ok(verify(jwk,['ai2apps-mobile-agent-proof-v1','lease',uuid,nonce,thumb].join('\n'),b.signature));return route.fulfill({json:{agent:true,jti,connectionId:uuid,expiresAt:new Date(Date.now()+60000).toISOString()}});}
  if(p.endsWith('/nonce'))return route.fulfill({json:{nonce,jti}});
  if(p==='/v1/mobile/agent/artifacts/run_image/art_png'||p==='/v1/mobile/agent/assets/run_image/0/0')return route.fulfill({contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAEklEQVR4nGNkaGCAAyYEEx8HABoEAIgBCl8RAAAAAElFTkSuQmCC','base64')});
  const catalog={
   '/v1/mobile/agent/chat/state':{selected_thread_id:'thread'},
   '/v1/mobile/agent/models':{data:[{id:'capable',display_name:'Declared work model',model_type:'llm',capabilities:['work_standard','tool_calling_reliable','conversation']}]},
   '/v1/mobile/agent/agents':{items:[{agent_key:'ai2apps.general-agent',display_name:'General Agent',status:'enabled',discoverable:true},{agent_key:'fixture.specialist',display_name:'Specialist Agent',status:'enabled',discoverable:true}]},
   '/v1/mobile/agent/chat/threads':{items:[{id:'thread',title:'Signed history'},{id:'other',title:'Other history'}]},
   '/v1/mobile/agent/chat/threads/thread/content':{thread:{id:'thread',title:'Signed history'},messages:[{role:'assistant',content:[{type:'text',text:'Existing generated image'},{type:'image_url',image_url:{artifact_id:'art_png',filename:'fixture.png',url:'/v1/platform/sessions/thread/artifacts/art_png/download'}}],metadata:{agent_run_id:'run_image',aaat_views:[{provider:'arbitrary.fixture',view:{schema:'ai2apps.aaat-view/v1',id:'news',layout:'cards',title:'Fixture evidence',items:[{id:'one',title:'Evidence',image:{url:'/v1/platform/owner/image'},url:'https://source.example/article'}]}}]}}]},
   '/v1/mobile/agent/chat/threads/other/content':{thread:{id:'other',title:'Other history'},messages:[{role:'assistant',content:'Other saved answer'}]},
   '/v1/mobile/agent/chat/threads/other/agent-runs':{items:[]},
   '/v1/mobile/agent/agent-runs/run_image':{id:'run_image',status:activeRun?'running':'completed'},
   '/v1/mobile/agent/chat/threads/thread/agent-runs':{items:[{id:'run_image',status:activeRun?'running':'completed',agent_display_name:'Fixture Agent',status_line:{text:'Completed'}}]}
  };
  if(req.method()==='GET'&&catalog[p]){const h=req.headers();const input=['ai2apps-mobile-agent-local-v1',uuid,jti,'GET',p+url.search,crypto.createHash('sha256').update('').digest('hex'),nonce].join('\n');assert.ok(verify(jwk,input,h['x-ai2apps-agent-signature']));return route.fulfill({json:catalog[p]});}
  if(p==='/v1/mobile/agent/chat/threads/thread/manage'){
   assert.equal(req.method(),'POST');const h=req.headers(),body=req.postDataBuffer();const input=['ai2apps-mobile-agent-local-v1',uuid,jti,'POST',p,crypto.createHash('sha256').update(body).digest('hex'),nonce].join('\n');assert.ok(verify(jwk,input,h['x-ai2apps-agent-signature']));assert.equal(req.postDataJSON().action,'rename');return route.fulfill({json:{id:'thread',title:'Renamed',revision:2}});
  }
  if(p==='/v1/mobile/agent/chat/threads'){
   businessWrites++;const h=req.headers(),body=req.postDataBuffer();const input=['ai2apps-mobile-agent-local-v1',uuid,jti,req.method(),p,crypto.createHash('sha256').update(body).digest('hex'),nonce].join('\n');assert.ok(verify(jwk,input,h['x-ai2apps-agent-signature']));return route.fulfill({json:{id:'thread'}});
  }
  return route.fulfill({status:404,json:{detail:'not allowed'}});
 });
 await page.route('https://coder.ai2apps.com/**',route=>route.fulfill({contentType:'text/html',body:'Cloud fixture login and Desktop approval'}));
 await page.goto('https://device-fixture.ai2apps.com/mobile');
 await page.waitForFunction(()=>document.querySelector('.mobile-connection')?.textContent==='未连接');
 assert.equal(new URL(page.url()).pathname,'/mobile');assert.equal(leaseRequests,0);
 const ticket='mag1.'+uuid+'.'+'B'.repeat(43);await page.goto('https://device-fixture.ai2apps.com/mobile/home#agent_pair='+ticket);await page.waitForURL('https://coder.ai2apps.com/mobile/agent-pair*');
 const params=new URLSearchParams(new URL(page.url()).hash.slice(1));jwk=JSON.parse(params.get('client_jwk'));thumb=crypto.createHash('sha256').update(JSON.stringify(jwk)).digest('base64url');assert.deepEqual(Object.keys(jwk),['crv','kty','x','y']);assert.ok(verify(jwk,['ai2apps-mobile-agent-claim-v1',ticket,thumb].join('\n'),params.get('signature')));
 await page.goto('https://device-fixture.ai2apps.com/mobile/home#agent_connection='+uuid);await page.waitForFunction(()=>document.querySelector('[data-agent-pair-note]')?.textContent==='Agent 连接已就绪');assert.equal(await page.locator('[data-agent-pair-note]').textContent(),'Agent 连接已就绪');assert.equal(new URL(page.url()).hash,'');
 await page.waitForFunction(()=>document.querySelector('[data-agent-pair-note]')?.textContent==='Agent 连接已就绪');assert.equal(new URL(page.url()).pathname,'/mobile/home');assert.equal(await page.locator('#ai2apps-mobile').getAttribute('data-view'),'home');assert.equal(await page.locator('[data-agent-pair-open]').count(),0);assert.equal(businessWrites,0);
 assert.equal(await page.evaluate(async cid=>(await window.AI2AppsAgentConnection.key(cid)).privateKey.extractable,uuid),false);
 const result=await page.evaluate(async()=>{const r=await window.AI2AppsAgentConnection.signedFetch('/v1/mobile/chat/threads',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':'one'},body:JSON.stringify({title:'签名正文'})});return r.json();});assert.equal(result.id,'thread');assert.equal(businessWrites,1);
 const renamed=await page.evaluate(async()=>{const r=await AI2AppsAgentConnection.signedFetch('/v1/mobile/chat/threads/thread/manage',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'rename',expected_revision:1,title:'Renamed'})});return r.json();});assert.equal(renamed.title,'Renamed');
 await page.reload();await page.evaluate(()=>window.AI2AppsAgentConnection.resume());assert.equal(businessWrites,1);assert.ok(leaseRequests>=2);await page.locator('.mobile-dock-item[data-mobile-app="ai2apps.general-chat"]').click();await page.waitForFunction(()=>document.querySelector('[data-mobile-inline-agent]')?.hidden===false);assert.equal(new URL(page.url()).pathname,'/mobile/home');assert.equal(await page.locator('.mobile-dock').isVisible(),true);assert.equal(await page.locator('.mchat-agent-home').count(),0);assert.equal(await page.locator('[data-mobile-inline-agent] iframe').count(),0);const compose=await page.locator('.mchat-compose').boundingBox(),dock=await page.locator('.mobile-dock').boundingBox();assert.ok(compose.y+compose.height<=dock.y+1);await page.waitForFunction(()=>document.querySelector('[data-mobile-chat-mode=agent]')?.classList.contains('is-active'));assert.equal(await page.locator('[data-mobile-chat-mode=agent]').isEnabled(),true);assert.equal(await page.locator('[data-mobile-chat-mode=agent]').isVisible(),true);await page.waitForFunction(()=>document.querySelector('canvas.mchat-generated-image')?.width>0);await page.waitForFunction(()=>document.querySelector('.aaat-view-image canvas')?.width===4);assert.equal(await page.locator('canvas.mchat-generated-image').evaluate(c=>c.getContext('2d').getImageData(0,0,1,1).data[1]),128);assert.equal(await page.locator('.mchat-agent-run progress').isVisible(),false);assert.equal(await page.locator('.mchat-agent-run progress').getAttribute('value'),'1');activeRun=true;await page.reload();await page.waitForFunction(()=>document.querySelector('.mchat-agent-run header')?.textContent.includes('running'));await page.locator('[data-mobile-chat-sessions]').click();await page.locator('[data-thread-id=other]').click();await page.waitForFunction(()=>document.querySelector('[data-mobile-chat-title]')?.textContent==='Other history');await page.waitForFunction(()=>document.querySelector('[data-mobile-chat-list]')?.textContent.includes('Other saved answer'));assert.equal(await page.locator('.mchat-agent-run').count(),0);assert.equal(businessWrites,1);await page.locator('.mobile-dock-item[data-mobile-action=home]').click();await page.waitForFunction(()=>document.querySelector('[data-agent-pair-note]')?.textContent==='Agent 连接已就绪');assert.equal(new URL(page.url()).pathname,'/mobile/home');assert.equal(businessWrites,1);await page.evaluate(ticket=>{location.hash='agent_pair='+ticket;},'mag1.'+uuid+'.'+'C'.repeat(43));await page.waitForURL('https://coder.ai2apps.com/mobile/agent-pair*');assert.equal(businessWrites,1);
 const handoff='oh1.'+uuid+'.'+'D'.repeat(43);
 await page.goto('https://device-fixture.ai2apps.com/mobile/home#'+new URLSearchParams({agent_connection:uuid,apps_connection:uuid,apps_handoff:handoff}));
 await page.waitForFunction(()=>document.querySelector('[data-agent-pair-note]')?.textContent==='应用与 Agent 均已连接。');
 assert.equal(await page.locator('.mobile-home-app[data-mobile-app]').count(),8);assert.equal(await page.locator('.mobile-launcher-app[data-mobile-app]').count(),8);assert.equal(await page.locator('.mobile-reauthorize').count(),0);assert.equal(new URL(page.url()).hash,'');assert.equal(exchanges,1);
 await page.locator('.mobile-dock-item[data-mobile-app="ai2apps.general-chat"]').click();await page.waitForFunction(()=>document.querySelector('[data-mobile-inline-agent]')?.hidden===false);
 await page.locator('.mobile-dock-item[data-mobile-action=home]').click();await page.waitForFunction(()=>document.querySelector('.mobile-home')?.hidden===false);
 await page.locator('.mobile-home-app[data-mobile-app="arbitrary.installed-app"]').click();await page.waitForFunction(()=>document.querySelector('.mobile-app-frame')?.hidden===false);assert.equal(await page.locator('.mobile-dock').isVisible(),true);
 await page.locator('.mobile-dock-item[data-mobile-app="ai2apps.general-chat"]').click();await page.waitForFunction(()=>document.querySelector('[data-mobile-inline-agent]')?.hidden===false);assert.equal(await page.locator('.mobile-app-frame').isVisible(),false);assert.equal(new URL(page.url()).pathname,'/mobile/home');
 await page.goto('https://device-fixture.ai2apps.com/mobile/agent-chat');await page.waitForURL('**/mobile/home#app=*');await page.waitForFunction(()=>document.querySelector('[data-mobile-inline-agent]')?.hidden===false);assert.equal(await page.locator('.mobile-dock').isVisible(),true);assert.equal(businessWrites,1);
 // Native reconnect/refresh may reopen the ordinary Owner URL. Restore the
 // signed Shell without replaying a handoff or doing business writes.
 // Legacy false preference must not mask an independently live Agent grant.
 await page.evaluate(async()=>{const db=await new Promise(resolve=>{const r=indexedDB.open('ai2apps.mobile-agent.v1',1);r.onsuccess=()=>resolve(r.result);});await new Promise(resolve=>{const t=db.transaction('connections','readwrite');t.objectStore('connections').put(false,'prefer-agent');t.oncomplete=resolve;});db.close();});
 const reconnectLeases=leaseRequests;
 await page.goto('https://device-fixture.ai2apps.com/mobile#app=ai2apps.general-chat');
 await page.waitForURL('**/mobile/home#app=*');
 await page.waitForFunction(()=>document.querySelector('[data-mobile-chat-mode=agent]')?.classList.contains('is-active'));
 assert.equal(await page.locator('.mobile-dock').isVisible(),true);
 assert.ok(leaseRequests>reconnectLeases);assert.equal(exchanges,1);assert.equal(businessWrites,1);
 assert.equal(await page.evaluate(()=>document.cookie.includes('fixture-owner')),false);
 assert.equal(await page.evaluate(h=>JSON.stringify(localStorage).includes(h),handoff),false);
 // A temporary lease failure must keep the signed Agent surface and expose
 // the failure, never silently substitute an ordinary Owner Chat iframe.
 rejectLease=true;
 await page.goto('https://device-fixture.ai2apps.com/mobile/home#app=ai2apps.general-chat');
 await page.reload();
 await page.waitForFunction(()=>document.querySelector('[data-mobile-inline-agent]')?.hidden===false);
 assert.equal(await page.locator('[data-mobile-chat-mode=agent]').isVisible(),true);
 await page.waitForFunction(()=>document.querySelector('[data-mobile-chat-model]')?.textContent.includes('fixture temporary lease failure'));
 assert.equal(await page.locator('.mobile-app-frame').count(),0);assert.equal(businessWrites,1);
 rejectLease=false;
 await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
 await page.waitForFunction(()=>document.querySelector('[data-mobile-chat-mode=agent]')?.classList.contains('is-active'));
 assert.equal(businessWrites,1);
 const before=leaseRequests;
 await page.goto('https://device-fixture.ai2apps.com/mobile/home#'+new URLSearchParams({apps_connection:uuid,apps_handoff:'oh1.'+uuid+'.'+'E'.repeat(43)}));
 await page.waitForFunction(()=>document.querySelector('[data-agent-pair-note]')?.textContent==='应用与 Agent 均已连接。');
 assert.equal(await page.locator('.mobile-home-app[data-mobile-app]').count(),8);assert.ok(leaseRequests>before);assert.equal(exchanges,2);
 await page.reload();await page.waitForFunction(()=>document.querySelector('[data-agent-pair-note]')?.textContent==='应用与 Agent 均已连接。');assert.equal(exchanges,2);assert.ok(leaseRequests>before);assert.equal(businessWrites,1);
 // A client with no approved connection remains App-only: no lease requests.
 await page.evaluate(async()=>{const db=await new Promise(resolve=>{const r=indexedDB.open('ai2apps.mobile-agent.v1',1);r.onsuccess=()=>resolve(r.result);});await new Promise(resolve=>{const t=db.transaction('connections','readwrite');t.objectStore('connections').delete('active');t.oncomplete=resolve;});db.close();});
 const noAgentLeases=leaseRequests;
 await page.goto('https://device-fixture.ai2apps.com/mobile/home');
 await page.waitForFunction(()=>document.querySelector('[data-agent-pair-note]')?.textContent==='应用已连接。');
 assert.equal(leaseRequests,noAgentLeases);
 await page.goto('https://device-fixture.ai2apps.com/mobile');
 await page.waitForFunction(()=>document.querySelector('.mobile-home-app[data-mobile-app]'));
 assert.equal(new URL(page.url()).pathname,'/mobile');assert.equal(leaseRequests,noAgentLeases);
 await page.goto('https://device-fixture.ai2apps.com/mobile/home#'+new URLSearchParams({agent_connection:uuid,apps_connection:'33333333-3333-4333-8333-333333333333',apps_handoff:handoff}));
 await page.waitForFunction(()=>document.querySelector('[data-agent-pair-note]')?.getAttribute('role')==='alert');
 assert.equal(await page.locator('.mobile-home-app[data-mobile-app]').count(),0);assert.equal(exchanges,2);assert.equal(businessWrites,1);
 }finally{await browser.close();}
});

test('unified Owner session uses cookie-bound Agent route without a paired key',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  const page=await browser.newPage();let writes=0,statusRequests=0;
  await page.route('https://device-unified.ai2apps.com/**',async route=>{
   const p=new URL(route.request().url()).pathname;
   if(p==='/mobile/home')return route.fulfill({contentType:'text/html',body:'<main></main><script src="/client.js"></script>'});
   if(p==='/client.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(path.resolve(__dirname,'../web/static/js/mobile_agent_connection.js'))});
   if(p==='/v1/mobile/owner-home/status'){statusRequests++;return route.fulfill({json:{authorized:true,agentAuthorized:true}});}
   if(p==='/v1/mobile/owner-agent/chat/threads'){writes++;assert.equal(route.request().method(),'POST');return route.fulfill({json:{id:'thread'}});}
   throw Error('Unexpected legacy/signing request: '+p);
  });
  await page.goto('https://device-unified.ai2apps.com/mobile/home');
  assert.equal(await page.evaluate(()=>AI2AppsAgentConnection.resume()),true);
  assert.equal(await page.evaluate(async()=>{const r=await AI2AppsAgentConnection.signedFetch('/v1/mobile/chat/threads',{method:'POST',body:'{}',headers:{'Content-Type':'application/json'}});return (await r.json()).id;}),'thread');
  assert.equal(writes,1);assert.equal(statusRequests,1);
 } finally {await browser.close();}
});
