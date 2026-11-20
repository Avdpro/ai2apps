const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
const js=n=>fs.readFileSync(__dirname+'/../web/static/js/'+n+'.js','utf8');
for(const width of [1280,390])test('ASC capture and launch share App-State, without automatic generation at '+width,{timeout:60000},async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width,height:844}});const writes=[],creations=new Map();let failOnce=true,launches=0,claims=0,applications=0,packet;
 await page.route('https://asc.fixture/**',async route=>{
  const u=new URL(route.request().url()),body=route.request().postDataJSON();
  if(u.pathname==='/host')return route.fulfill({contentType:'text/html',body:`<iframe id="app" style="width:100%;height:800px" src="/app#ai2apps-instance=instance&ai2apps-mount=mount"></iframe><script>window.acks=[];window.addEventListener('message',e=>{const m=e.data;if(m.type==='ai2apps.shell.open-entry'){document.querySelector('iframe').contentWindow.postMessage({type:'ai2apps.host.context',mountToken:'mount',instanceId:'instance',appStateLaunch:m.appStateLaunch},location.origin);e.source.postMessage({type:'ai2apps.host.response',mountToken:'mount',instanceId:'instance',requestId:m.requestId,ok:true,result:{appId:m.appId,instanceId:'instance'}},location.origin);}if(m.type==='ai2apps.shell.ack-app-state')acks.push(m.launchId);});</script>`});
  if(u.pathname==='/app')return route.fulfill({contentType:'text/html',body:'<html lang="en"><main><button id="presets">Presets</button></main></html>'});
  if(u.pathname.includes('/app-state/')){
   let value={};if(u.pathname.endsWith('/contract'))value={contract_version:1,name:'Style Transfer',contract_digest:'a'.repeat(64),schema:{properties:Object.fromEntries(['model_id','style_id','width','height','quality','format'].map(k=>[k,{}]))}};
   else if(u.pathname.endsWith('/validate'))value={packet:body.packet,contract_digest:'a'.repeat(64)};else if(u.pathname.endsWith('/presets'))value={items:[]};else if(u.pathname.endsWith('/applications')){applications++;value={id:'apply-'+applications,status:'prepared'};}else if(u.pathname.endsWith('/complete'))value={status:body.status};
   return route.fulfill({json:value});
  }
  if(u.pathname.endsWith('/app-shortcuts/bots')){writes.push(body);if(!creations.has(body.request_id))creations.set(body.request_id,{id:'bot-1',name:body.name});packet=body.packet;if(failOnce){failOnce=false;return route.fulfill({status:503,json:{detail:'Unknown result'}});}return route.fulfill({status:201,json:creations.get(body.request_id)});}
  if(u.pathname.endsWith('/launch')){launches++;return route.fulfill({json:{id:'ascl_'+String(launches).padStart(32,'0'),target:packet.target}});}
  if(u.pathname.endsWith('/claim')){claims++;return route.fulfill({json:{packet,contract_digest:'a'.repeat(64)}});}
  throw Error('Unexpected fixture call '+u.pathname);
 });
 await page.goto('https://asc.fixture/host');const frame=page.frames().find(f=>f.url().includes('/app#'));await frame.waitForSelector('#presets');
 await frame.addStyleTag({content:fs.readFileSync(__dirname+'/../web/static/css/app_state.css','utf8')});
 await frame.addScriptTag({content:js('app_state')});await frame.addScriptTag({content:js('bot_avatars')});await frame.addScriptTag({content:js('app_shortcuts')});await frame.addScriptTag({content:js('imagine_app_state')});
 await frame.evaluate(()=>{
  const capability={mode:'fixed',default:'1536x1024',width:{max:2048,multipleOf:1},height:{max:2048,multipleOf:1},minPixels:1,maxPixels:4194304,maxAspectRatio:4,presets:['1024x1024','1536x1024']};
  const model={id:'cloud/fixture/exact-model',source:'cloud',qualities:['auto','high'],formats:['png'],sizeCapability:capability};window.generated=0;window.setupCalls=0;
  window.owner={miniApps:[{id:'ai2apps.imagine.style-transfer',status:'ready',source:'official'}],miniAppId:'ai2apps.imagine.style-transfer',packageMiniAppId:'',leftView:'mini-apps',leftCollapsed:false,rightCollapsed:false,modelId:model.id,style:'ghibli',size:'1536x1024',customWidth:1536,customHeight:1024,quality:'high',format:'png',sizeCapability:capability,pricingVersion:'',flexibleSizes:false,locale:'en',prompt:'PRIVATE PROMPT',referenceFiles:[],compatibleModels:[model],allStyles:[{id:'ghibli'},{id:'plain'}],
   $root:document.querySelector('main'),appInstanceId:()=> 'instance',draftPayload(){return {prompt:this.prompt,modelId:this.modelId,style:this.style};},get requestedSize(){return this.size;},parseSize(s){const a=s.match(/^(\d+)x(\d+)$/);return a?{width:+a[1],height:+a[2]}:null;},validateSize(s){return this.sizeCapability.presets.includes(s)?'':'Invalid size';},tr:k=>k,$nextTick:async()=>{},persistPreferences(){},scheduleDraftSave(){},generate(){generated++;},configureLocalModel:async function(){setupCalls++;window.setupHadBlockingDialog=!!document.querySelector('dialog[open]');this.compatibleModels=[model];}};
  window.controller=AI2AppsImagineState.mount(owner);document.querySelector('#presets').onclick=()=>controller.open();
 });
 await frame.getByRole('button',{name:'Presets',exact:true}).click();
 await frame.getByLabel('Preset name').fill('My Ghibli');
 await frame.getByRole('button',{name:'Create shortcut Bot',exact:true}).click();
 assert.equal(await frame.getByLabel('Shortcut Bot name').inputValue(),'My Ghibli');
 await frame.getByRole('button',{name:'Cat',exact:true}).click();
 await frame.getByRole('button',{name:'Blue',exact:true}).click();
 assert.equal(await frame.getByRole('button',{name:'Cat',exact:true}).getAttribute('aria-pressed'),'true');
 assert.equal(await frame.getByRole('button',{name:'Blue',exact:true}).getAttribute('aria-pressed'),'true');
 await frame.getByRole('button',{name:'Create Bot',exact:true}).click();await frame.getByText(/Creation is unconfirmed/).waitFor();await frame.getByRole('button',{name:'Create Bot',exact:true}).click();await frame.getByText('Created. Open it from the Bot list in Messager.').waitFor();
 assert.equal(creations.size,1);assert.deepEqual(writes[0],writes[1]);assert.equal(writes[0].name,'My Ghibli');assert.equal(writes[0].avatar.preset,'cat');assert.equal(writes[0].avatar.color,'#2563eb');assert(!JSON.stringify(writes).includes('PRIVATE PROMPT'));
 await frame.locator('.app-shortcut-create').getByRole('button',{name:'Close',exact:true}).click();await frame.getByRole('button',{name:'Close',exact:true}).click();
 await frame.evaluate(()=>{owner.style='plain';owner.size='1024x1024';void AI2AppsAppShortcuts.open('bot-1');});await frame.getByRole('button',{name:'Restore these settings',exact:true}).click();await frame.waitForFunction(()=>owner.style==='ghibli'&&owner.size==='1536x1024');await page.waitForFunction(()=>acks.length===1);
 assert.equal(await frame.evaluate(()=>generated),0);assert.equal(await frame.evaluate(()=>owner.prompt),'PRIVATE PROMPT');assert.equal(applications,1);
 await page.evaluate(()=>document.querySelector('iframe').contentWindow.postMessage({type:'ai2apps.host.context',mountToken:'mount',instanceId:'instance',appStateLaunch:acks[0]},location.origin));assert.equal(claims,1);
 await frame.evaluate(()=>{owner.compatibleModels=[];owner.style='plain';void AI2AppsAppShortcuts.open('bot-1');});await frame.getByRole('heading',{name:'Shortcut needs attention'}).waitFor();await frame.getByRole('button',{name:'Set up capabilities'}).click();await frame.getByRole('heading',{name:'Continue shortcut'}).waitFor();assert.equal(await frame.evaluate(()=>setupHadBlockingDialog),false);
 await frame.getByRole('button',{name:'Retry restore'}).click();await frame.getByRole('button',{name:'Restore these settings',exact:true}).click();await page.waitForFunction(()=>acks.length===2);assert.equal(await frame.evaluate(()=>setupCalls),1);assert.equal(await frame.evaluate(()=>owner.modelId),'cloud/fixture/exact-model');assert.equal(await frame.evaluate(()=>generated),0);
 }finally{await browser.close();}
});
