const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs');
const {chromium}=require('playwright');
const template=fs.readFileSync(__dirname+'/../web/templates/shell.html','utf8');
const start=template.indexOf('<dialog class="desktop-home-space-dialog"'),end=template.indexOf('</dialog>',start)+9;
async function fixture(run,unified=false){
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();const ctx={state:{status:'qr',generation:1},decisions:[],acks:0,configured:0,created:0,ackLoss:false};
 await page.route('http://127.0.0.1:55555/**',route=>{const req=route.request(),p=new URL(req.url()).pathname;
 if(p==='/')return route.fulfill({contentType:'text/html',body:'<meta charset="utf-8"><button data-home-space-open>链接二维码</button>'+template.slice(start,end)+'<script src="/client.js"></script>'});
 if(p==='/client.js')return route.fulfill({contentType:'application/javascript',body:fs.readFileSync(__dirname+'/../web/static/js/desktop_mobile_agent.js')});
 if(p==='/v1/platform/remote/devices/reconcile')return route.fulfill({json:{}});
 if(p==='/v1/platform/remote/status')return route.fulfill({json:{connector:{deviceId:'this-local'},devices:[{deviceId:'other',status:'active',enabled:true,proxyConnected:true},{deviceId:'this-local',status:'active',enabled:true,proxyConnected:true}]}});
 if(p.endsWith('/confirmation'))return route.fulfill({json:{token:'fixture'}});
 assert.ok(p.startsWith('/v1/platform/remote/mobile-agent/this-local/'));
 if(p.endsWith('/status'))return route.fulfill({json:{ready:false}});
 if(p.endsWith('/configure')){ctx.configured++;return route.fulfill({json:{ready:true}});}
 if(p.endsWith('/pairings')){ctx.created++;return route.fulfill({json:{...(unified?{mobileAccessProtocol:'owner-mobile-unified-v1',commitMode:'exchange-v1'}:{}),connectionId:'connection',pairingQrDataUrl:'data:image/svg+xml;base64,PHN2Zy8+'}});}
 if(p.endsWith('/decision')){const b=req.postDataJSON();assert.equal(b.humanConfirmed,true);ctx.decisions.push(b.decision);ctx.lastDecision=b;ctx.state={...ctx.state,status:b.decision==='connect'?'awaiting_exchange':b.decision==='agent'?'active':b.decision==='chat'?'chat':'denied'};if(ctx.ackLoss){ctx.state.status='awaiting_ack';ctx.state.generation=2;return route.fulfill({status:503,json:{detail:'ACK response lost'}});}return route.fulfill({json:ctx.state});}
 if(p.endsWith('/ack')){ctx.acks++;ctx.state.status='active';return route.fulfill({json:ctx.state});}
 return route.fulfill({json:{...ctx.state,serverTime:Date.now()/1000}});
 });
 await page.goto('http://127.0.0.1:55555');await page.getByText('链接二维码',{exact:true}).click();await page.waitForFunction(()=>!document.querySelector('[data-home-space-qr]').hidden);
 const scan=async()=>{ctx.state={status:'pending',generation:1,clientLabel:'<script>bad()</script>',displayDeadline:new Date(Date.now()+30000).toISOString(),approvalDeadline:new Date(Date.now()+35000).toISOString()};await page.waitForFunction(()=>!document.querySelector('[data-agent-allow]').disabled);};
 await run(page,ctx,scan);
 }finally{await browser.close();}
}
test('Home QR starts unchecked/disabled, scan shows green check and explicit consent closes after ACK',()=>fixture(async(page,c,scan)=>{
 assert.equal(c.configured,1);assert.equal(c.created,1);assert.deepEqual(c.decisions,[]);
 assert.equal(await page.locator('[data-agent-allow]').isDisabled(),true);assert.equal(await page.locator('[data-agent-allow]').isChecked(),false);assert.equal(await page.locator('[data-agent-scanned]').isVisible(),false);
 await scan();assert.equal(await page.locator('[data-agent-scanned]').isVisible(),true);assert.equal(await page.locator('[data-agent-allow]').isChecked(),false);assert.equal(await page.locator('[data-agent-desktop-label]').textContent(),'<script>bad()</script>');
 await page.locator('[data-agent-allow]').check();assert.deepEqual(c.decisions,[]);
 await page.locator('[data-agent-confirm]').click();await page.waitForFunction(()=>!document.querySelector('dialog').open);assert.deepEqual(c.decisions,['agent']);
 await page.getByText('链接二维码',{exact:true}).click();assert.equal(await page.locator('[data-agent-allow]').isChecked(),false);
}));
test('unchecked post-scan confirmation is Chat only; pending/reloaded UI never automatically grants Agent',()=>fixture(async(page,c,scan)=>{
 await scan();await page.locator('[data-agent-confirm]').click();await page.waitForFunction(()=>!document.querySelector('dialog').open);assert.deepEqual(c.decisions,['chat']);
 await page.reload();assert.equal(c.created,1);assert.deepEqual(c.decisions,['chat']);assert.equal(await page.locator('[data-agent-allow]').isDisabled(),true);
}));
test('ACK loss keeps dialog open, retries only same ACK; expired pending cannot be confirmed',()=>fixture(async(page,c,scan)=>{
 await scan();c.ackLoss=true;await page.locator('[data-agent-allow]').check();await page.locator('[data-agent-confirm]').click();await page.getByText('重试确认',{exact:true}).waitFor();assert.equal(c.acks,0);assert.deepEqual(c.decisions,['agent']);
 await page.locator('[data-agent-confirm]').click();await page.waitForFunction(()=>!document.querySelector('dialog').open);assert.equal(c.acks,1);assert.deepEqual(c.decisions,['agent']);
 c.state={status:'pending',generation:2,displayDeadline:new Date(Date.now()-1000).toISOString()};await page.getByText('链接二维码',{exact:true}).click();await page.waitForFunction(()=>document.querySelector('[data-agent-desktop-status]').textContent.includes('超时'));
 assert.equal(await page.locator('[data-agent-allow]').isDisabled(),true);assert.equal(await page.locator('[data-agent-allow]').isChecked(),false);assert.equal(await page.locator('[data-agent-confirm]').isDisabled(),true);assert.deepEqual(c.decisions,['agent']);
}));

for(const disconnect of [false,true])test('unified confirmation awaits exchange without granting authority; disconnectOthers='+disconnect,()=>fixture(async(page,c,scan)=>{
 await scan();assert.equal(await page.locator('[data-agent-option-label]').textContent(),'断开其它客户端连接');
 assert.equal(await page.locator('[data-agent-allow]').isChecked(),false);
 if(disconnect)await page.locator('[data-agent-allow]').check();
 await page.locator('[data-agent-confirm]').click();await page.waitForFunction(()=>!document.querySelector('dialog').open);
 assert.equal(c.state.status,'awaiting_exchange');assert.equal(c.acks,0);
 assert.deepEqual(c.decisions,['connect']);assert.equal(c.lastDecision.disconnectOtherClients,disconnect);
},true));
