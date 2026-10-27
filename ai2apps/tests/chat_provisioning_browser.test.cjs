const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const {chromium}=require('playwright');
const source=fs.readFileSync(path.join(__dirname,'../web/static/js/capability_provisioning.js'),'utf8');
const css=fs.readFileSync(path.join(__dirname,'../web/static/css/capability_provisioning.css'),'utf8');
test('ACPF renders inline, requires explicit confirmation, recovers a server session and detaches cleanly',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage();await page.route('https://fixture.test/**',route=>route.fulfill({contentType:'text/html',body:'<!doctype html><html lang="zh"><body><article id="chat"></article></body></html>'}));await page.goto('https://fixture.test');await page.addStyleTag({content:css});await page.addScriptTag({content:source});
 await page.evaluate(()=>{
  window.calls=[];
  window.session={id:'setup_1',status:'awaiting_confirmation',plan:{profileId:'standard',device:{},steps:[],profileOptions:[]},intent:{completionPolicy:'configure_only'},progress:{}};
  window.send=async(url,options={})=>{if(options.method==='POST'){window.calls.push(url);if(url.endsWith('/confirm'))window.session={...window.session,status:'downloading_checkpoint',progress:{percent:40}};}return window.session;};
  window.pending=window.AI2AppsCapabilities.runSession(window.session,'fixture.owner',{root:document.querySelector('#chat'),request:window.send}).catch(error=>error.code);
 });
 const card=page.locator('#chat .acpf-inline');await card.waitFor();assert.equal(await card.evaluate(n=>getComputedStyle(n).position),'static');assert.equal(await page.locator('[aria-modal=true]').count(),0);assert.equal(await page.evaluate(()=>calls.length),0);
 await card.locator('[data-action=confirm]').click();await page.waitForFunction(()=>calls.length===1);assert.match((await page.evaluate(()=>calls))[0],/confirm$/);
 await page.evaluate(()=>document.querySelector('#chat').remove());assert.equal(await page.evaluate(()=>pending),'view_detached');
 await page.evaluate(()=>{document.body.innerHTML='<article id="restored"></article>';window.session.status='ready';window.restored=window.AI2AppsCapabilities.runSession(window.session,'fixture.owner',{root:document.querySelector('#restored'),request:window.send});});
 await page.locator('#restored [data-action=done]').click();assert.equal((await page.evaluate(()=>restored)).outcome,'configured');assert.equal(await page.evaluate(()=>calls.length),1);
 }finally{await browser.close();}
});
test('license interaction stays in the card and never submits unchecked consent',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage();await page.route('https://fixture.test/**',route=>route.fulfill({contentType:'text/html',body:'<article id="chat"></article>'}));await page.goto('https://fixture.test');await page.addStyleTag({content:css});await page.addScriptTag({content:source});
 await page.evaluate(()=>{
  window.calls=[];window.session={id:'license_test',status:'awaiting_confirmation',plan:{device:{},steps:[]},intent:{},progress:{},error:{code:'checkpoint_license_consent_required',challenges:[{distributionId:'fixture',manifestDigest:'sha256:'+'a'.repeat(64),license:{name:'Fixture license',termsText:'Test-only terms',termsHash:'sha256:'+'b'.repeat(64)},acceptanceOptions:['accepted_license_terms']}]}};
  window.pending=window.AI2AppsCapabilities.runSession(window.session,'fixture.owner',{root:document.querySelector('#chat'),request:async(url,options={})=>{if(options.method==='POST'){calls.push(JSON.parse(options.body));session={...session,status:'ready',error:null};}return session;}}).catch(error=>error.code);
 });
 await page.locator('[data-action=confirm]').click();const license=page.locator('#chat .acpf-license-overlay');await license.waitFor();assert.equal(await license.evaluate(n=>getComputedStyle(n).position),'static');const accept=license.locator('[data-license-action=accept]');assert.ok(await accept.isDisabled());assert.equal(await page.evaluate(()=>calls.length),0);
 await license.locator('input[type=radio]').check();assert.ok(await accept.isDisabled());await license.locator('input[type=checkbox]').check();await accept.click();await page.waitForFunction(()=>calls.length===1);assert.equal((await page.evaluate(()=>calls))[0].licenseConsents[0].confirmed,true);
 await page.locator('[data-action=done]').click();await page.evaluate(()=>pending);
 }finally{await browser.close();}
});
