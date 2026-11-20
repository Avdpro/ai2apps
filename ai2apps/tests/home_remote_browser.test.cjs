const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
test('homepage consent dialog rotates then starts; dismissal sends neither request',async()=>{
 const source=fs.readFileSync('web/static/js/shell.js','utf8');
 const code=source.slice(source.indexOf('    async function request('),source.indexOf('    function provisioningReturnApp('));
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{for(const agree of [true,false]){
 const page=await browser.newPage();const calls=[];let enabled=false,needsSession=false;
 const device=()=>({deviceId:'device-one',displayName:'Test Mac',status:'active',enabled,credentialExpiresAt:'2020-01-01T00:00:00Z'});
 await page.route('https://home.fixture/**',async route=>{const p=new URL(route.request().url()).pathname;if(p==='/')return route.fulfill({contentType:'text/html',body:'<!doctype html><meta charset="utf-8"><main><div data-home-remote-devices></div><p data-home-remote-error hidden></p></main>'});calls.push(p);if(p.endsWith('/credentials/rotate')){assert.deepEqual(route.request().postDataJSON(),{ownerPassword:'fixture-password'});needsSession=true;}if(p.endsWith('/cloud-member/activate'))needsSession=false;if(needsSession&&(p.endsWith('/start')||p.endsWith('/status')))return route.fulfill({status:401,json:{error:{code:'local_session_required',message:'Session expired'}}});if(p.endsWith('/start'))enabled=true;return route.fulfill({json:{devices:[device()],connector:{available:true}}});});
 await page.goto('https://home.fixture/');await page.addStyleTag({content:fs.readFileSync('web/static/css/shell.css','utf8')});await page.addScriptTag({content:`const root=document.querySelector('main'),strings=${JSON.stringify(JSON.parse(fs.readFileSync('web/i18n/zh.json','utf8')))},tr=k=>strings[k]||k;`+code+';refreshHomeRemote();'});
 await page.getByRole('switch').click();
 const dialog=page.locator('dialog');await dialog.waitFor();const input=dialog.locator('input');assert.equal(await input.getAttribute('type'),'password');if(agree)await page.screenshot({path:'/tmp/home-owner-password-dialog.png'});
 if(agree){await input.fill('fixture-password');await dialog.locator('button[type=submit]').click();}else await dialog.locator('button[type=button]').click();
 await page.waitForFunction(()=>!homeRemoteBusy);assert.equal(await page.locator('dialog').count(),0);
 assert.deepEqual(calls.filter(x=>x.endsWith('/credentials/rotate')||x.endsWith('/start')),agree?['/v1/platform/remote/devices/device-one/credentials/rotate','/v1/platform/remote/devices/device-one/start']:[]);
 if(agree)assert.ok(calls.indexOf('/v1/platform/auth/cloud-member/activate')>calls.indexOf('/v1/platform/remote/devices/device-one/credentials/rotate')&&calls.indexOf('/v1/platform/auth/cloud-member/activate')<calls.indexOf('/v1/platform/remote/devices/device-one/start'));
 assert.equal(await page.getByRole('switch').getAttribute('aria-checked'),String(agree));await page.close();
 }}finally{await browser.close();}
});
