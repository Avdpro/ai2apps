const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const {chromium}=require('playwright');
const source=fs.readFileSync(path.join(__dirname,'../web/static/js/capability_provisioning.js'),'utf8');
const css=fs.readFileSync(path.join(__dirname,'../web/static/css/capability_provisioning.css'),'utf8');
const messagerCss=fs.readFileSync(path.join(__dirname,'../web/static/css/messager.css'),'utf8');
const forms=fs.readFileSync(path.join(__dirname,'../web/static/js/agent_parameter_forms.js'),'utf8');

test('a pending Chat or Bot form opens the opted-in setup card before any confirmation',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  for(const {owner,mobile} of [{owner:'fixture.alpha',mobile:false},{owner:'package.beta',mobile:true}]) {
   const page=await browser.newPage();
   await page.route('https://fixture.test/**',route=>route.fulfill({
    contentType:'text/html',body:'<!doctype html><html lang="en"><body><article id="chat"></article></body></html>',
   }));
   await page.goto('https://fixture.test');
   await page.addStyleTag({content:css});
   await page.addScriptTag({content:source});
   await page.addScriptTag({content:forms});
   await page.evaluate(({owner,mobile})=>{
    window.AI2APPS_MOBILE_SURFACE=mobile;
    window.writes=[];
    window.setupReads=0;
    window.setupSession=null;
    window.mountForm=()=>{
     window.AI2AppsParameterForms.mount(document.querySelector('#chat'),{id:'run',agent_key:'fixture'},
      {id:'interaction'},()=>{}, {request:async(url,options={})=>{
       if(options.method==='POST')writes.push(url);
       if(url.endsWith('/setup/session')){
        if(options.method==='POST')setupSession={
         id:'setup',status:'awaiting_confirmation',plan:{device:{},steps:[]},progress:{},
        };
        else setupReads++;
        return {session:setupSession};
       }
       if(url.endsWith('/setup/session/cancel')){
        setupSession={...setupSession,status:'cancelled'};
        return setupSession;
       }
       if(url.endsWith('/parameters'))return {
        configure_only:true,configuration_required:true,inline_setup:true,values:{},revision:0,
        install:{appId:owner},descriptor:{capability:'fixture.tool',app_id:owner,
         schema:{type:'object',properties:{}},fields:[]},
       };
       return {};
      }});
    };
    window.mountForm();
   },{owner,mobile});
   await page.locator('#chat form').waitFor();
   if(mobile){
    await page.getByRole('button',{name:'Desktop setup instructions'}).waitFor();
    await page.waitForFunction(()=>setupReads===1);
    assert.deepEqual(await page.evaluate(()=>writes),[]);
   }else{
    const card=page.locator('#chat .acpf-inline');
    await card.locator('[data-action=confirm]').waitFor();
    assert.equal(await page.locator('#chat > :first-child').getAttribute('class'),'agent-parameter-setup');
    assert.deepEqual((await page.evaluate(()=>writes)).map(url=>url.split('/').at(-1)),['session']);
    await card.locator('[data-action=cancel]').click();
    await card.waitFor({state:'hidden'});
    await page.evaluate(()=>{
     window.AI2AppsParameterForms.release('interaction');
     const root=document.querySelector('#chat');
     root.replaceWith(root.cloneNode(false));
     window.mountForm();
    });
    await page.locator('#chat form').waitFor();
    await page.waitForFunction(()=>setupReads>=2);
    assert.deepEqual((await page.evaluate(()=>writes)).map(url=>url.split('/').at(-1)),['session','cancel']);
   }
   await page.close();
  }
 } finally {await browser.close();}
});

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
test('ACPF requires explicit Qwen Image 2.1 license confirmation before continuing',async()=>{
 const spec=JSON.parse(fs.readFileSync(path.join(__dirname,'../../packages/ai2apps-model-qwen-image-mlx/META/checkpoint-distribution-21.json'),'utf8'));
 const manifestDigest='sha256:'+'a'.repeat(64);
 const challenge={distributionId:spec.distributionId,manifestDigest,license:spec.license,acceptanceOptions:spec.license.downloadConsent.acceptanceOptions};
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  for(const decision of challenge.acceptanceOptions){
   const page=await browser.newPage();
   try{
    await page.route('https://fixture.test/**',route=>route.fulfill({contentType:'text/html',body:'<article id="chat"></article>'}));
    await page.goto('https://fixture.test');
    await page.addStyleTag({content:css});await page.addStyleTag({content:messagerCss});await page.addStyleTag({content:'input { width:100%; } label { display:block; }'});await page.addScriptTag({content:source});
    await page.evaluate(challenge=>{
     window.calls=[];window.session={id:'license_test',status:'awaiting_confirmation',plan:{device:{},steps:[]},intent:{},progress:{},error:{code:'checkpoint_license_consent_required',challenges:[challenge]}};
     window.pending=window.AI2AppsCapabilities.runSession(window.session,'fixture.owner',{root:document.querySelector('#chat'),request:async(url,options={})=>{
      if(options.method==='POST'){calls.push(JSON.parse(options.body));session={...session,status:'ready',error:null};}
      return session;
     }});
    },challenge);
    await page.locator('[data-action=confirm]').click();
    const license=page.locator('#chat .acpf-license-overlay');
    await license.waitFor();
    assert.equal(await license.evaluate(n=>getComputedStyle(n).position),'static');
    assert.equal(await page.locator('#chat > .acpf-overlay').count(),1);
    assert.equal(await page.locator('.acpf-run-sheet').isVisible(),false);
    const geometry=await license.locator('.acpf-license-options label').first().evaluate(label=>{const a=label.querySelector('input').getBoundingClientRect(),b=label.querySelector('span').getBoundingClientRect();return {width:a.width,topDelta:Math.abs(a.top-b.top),beside:a.right<=b.left};});
    assert.equal(geometry.width,16);assert.ok(geometry.topDelta<=3);assert.ok(geometry.beside);
    assert.ok((await license.textContent()).includes(spec.license.name));
    assert.ok((await license.textContent()).includes('FOR NON-COMMERCIAL PURPOSES ONLY'));
    await license.locator('[data-license-action=cancel]').click();
    assert.equal(await page.locator('.acpf-license-overlay').count(),0);
    assert.equal(await page.locator('.acpf-run-sheet').isVisible(),true);
    assert.equal(await page.evaluate(()=>calls.length),0);
    await page.locator('[data-action=confirm]').click();await license.waitFor();
    const accept=license.locator('[data-license-action=accept]');
    assert.ok(await accept.isDisabled());
    assert.equal(await license.locator('input[type=radio]:checked').count(),0);
    assert.equal(await page.evaluate(()=>calls.length),0);
    const choice=license.locator(`input[type=radio][value="${decision}"]`);
    await choice.check();assert.ok(await accept.isDisabled());
    await license.locator('input[type=checkbox]').check();await accept.click();
    await page.waitForFunction(()=>calls.length===1);
    assert.equal(await page.locator('.acpf-license-overlay').count(),0);
    assert.equal(await page.locator('.acpf-run-sheet').isVisible(),true);
    assert.deepEqual((await page.evaluate(()=>calls))[0].licenseConsents,[{
     distributionId:spec.distributionId,manifestDigest,termsHash:spec.license.termsHash,decision,confirmed:true,
    }]);
    await page.locator('[data-action=done]').click();
    assert.equal((await page.evaluate(()=>pending)).outcome,'configured');
   }finally{await page.close();}
  }
 }finally{await browser.close();}
});
