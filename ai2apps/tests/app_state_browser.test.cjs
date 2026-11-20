const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
const script=name=>fs.readFileSync(__dirname+'/../web/static/js/'+name,'utf8');
for(const viewport of [{width:1280,height:800},{width:390,height:844}])test('state presets preserve private materials and restore settings at '+viewport.width,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport});await page.setContent('<html lang="en"><main><button id="presets">State presets</button></main></html>');await page.addStyleTag({content:fs.readFileSync(__dirname+'/../web/static/css/app_state.css','utf8')});
 // Use a secure local fixture origin so WebCrypto matches the real localhost App.
 await page.route('https://state.fixture/**',route=>route.fulfill({contentType:'text/html',body:'<html lang="en"><main><button id="presets">State presets</button></main></html>'}));await page.goto('https://state.fixture/');
 await page.addStyleTag({content:fs.readFileSync(__dirname+'/../web/static/css/app_state.css','utf8')});
 await page.evaluate(()=>{
  window.saved=[];window.requests=[];window.generated=0;let uuid=0;
  window.fetch=async(url,options={})=>{const body=options.body?JSON.parse(options.body):null;requests.push({url,body});let v={};
   const target={app_id:'ai2apps.imagine-studio',mini_app_id:'ai2apps.imagine.style-transfer',contract_version:1};
   if(url.includes('/contract?'))v={...target,name:'Style transfer settings',contract_digest:'a'.repeat(64),schema:{properties:Object.fromEntries(['model_id','style_id','width','height','quality','format'].map(k=>[k,{}]))}};
   else if(url.endsWith('/validate'))v={packet:body.packet,contract_digest:'a'.repeat(64)};
   else if(url.endsWith('/presets')&&options.method==='POST'){saved.push({id:String(++uuid),name:body.name,packet:body.packet});v={id:String(uuid)};}
   else if(url.includes('/presets?'))v={items:saved};else if(url.endsWith('/applications'))v={id:String(++uuid),status:'prepared'};else if(url.endsWith('/complete'))v={status:body.status};
   return {ok:true,json:async()=>v};
  };
  const capability={mode:'fixed',width:{max:2048,multipleOf:1},height:{max:2048,multipleOf:1},minPixels:1,maxPixels:2048*2048,maxAspectRatio:4,presets:['1024x1024','1536x1024']};
  window.owner={miniApps:[{id:'ai2apps.imagine.style-transfer',status:'ready',source:'official'}],miniAppId:'ai2apps.imagine.style-transfer',packageMiniAppId:'',leftView:'mini-apps',leftCollapsed:false,rightCollapsed:false,modelId:'cloud/fixture/image',style:'ghibli',size:'1024x1024',customWidth:1024,customHeight:1024,quality:'high',format:'png',sizeCapability:capability,pricingVersion:'1',flexibleSizes:false,locale:'en',prompt:'PRIVATE TEXT',referenceFiles:[new File(['PRIVATE IMAGE'],'photo.png')],
   compatibleModels:[{id:'cloud/fixture/image',source:'cloud',qualities:['auto','high'],formats:['png'],sizeCapability:capability}],allStyles:[{id:'ghibli'},{id:'plain'}],
   $root:document.querySelector('main'),appInstanceId:()=> 'fixture-instance',draftPayload(){return {prompt:this.prompt,model:this.modelId,style:this.style};},get requestedSize(){return this.size;},parseSize(s){const [width,height]=s.split('x').map(Number);return {width,height};},validateSize(s){return this.sizeCapability.presets.includes(s)?'':'Unsupported canvas';},tr:k=>k,
   $nextTick:async()=>{},persistPreferences(){},scheduleDraftSave(){},generate(){generated++;throw Error('State restore must not generate');}};
 });
 await page.addScriptTag({content:script('app_state.js')});await page.addScriptTag({content:script('imagine_app_state.js')});
 await page.evaluate(()=>{window.controller=AI2AppsImagineState.mount(owner);document.querySelector('#presets').onclick=()=>controller.open();});
 await page.getByRole('button',{name:'State presets',exact:true}).click();await page.getByPlaceholder('Preset name').fill('Ghibli preset');await page.getByRole('button',{name:'Save current settings',exact:true}).click();await page.getByRole('button',{name:'Ghibli preset',exact:true}).waitFor();
 assert(!JSON.stringify(await page.evaluate(()=>saved)).includes('PRIVATE'));
 await page.evaluate(()=>{owner.style='plain';});await page.getByRole('button',{name:'Ghibli preset',exact:true}).click();await page.getByRole('heading',{name:'Restore settings preset?'}).waitFor();
 await page.getByRole('button',{name:'Keep current settings',exact:true}).click();assert.equal(await page.evaluate(()=>owner.style),'plain');
 await page.getByRole('button',{name:'Ghibli preset',exact:true}).click();await page.getByRole('button',{name:'Restore these settings',exact:true}).click();await page.waitForFunction(()=>owner.style==='ghibli');
 assert.equal(await page.evaluate(()=>owner.prompt),'PRIVATE TEXT');assert.equal(await page.evaluate(()=>owner.referenceFiles.length),1);assert.equal(await page.evaluate(()=>generated),0);assert.equal(await page.evaluate(()=>owner.$root.inert),false);
 const bounds=await page.locator('.app-state-dialog').first().boundingBox();assert(bounds.width<=viewport.width);
 await page.getByRole('button',{name:'Close',exact:true}).click();
 // The Agent handoff uses the same dialog and transaction, but explicitly replaces private content.
 await page.evaluate(()=>{
  owner.materializeAssetReference=async function(ref,slot){this.referenceFiles[slot]=new File(['NEW'],'new.png');};
  window.handoff={run_id:'fixture-run',interaction_id:'fixture-interaction',status:'pending',target:{app_id:'ai2apps.imagine-studio',mini_app_id:'ai2apps.imagine.style-transfer'},parameters:{values:{model:'cloud/fixture/image',style:'ghibli',size:'1536x1024',quality:'high',format:'png',prompt:'PRIVATE HANDOFF'},references:[{session_id:'private-session',artifact_id:'private-artifact',slot:0}]}};
  window.startHandoff=()=>{window.handoffDone=false;window.handoffResult=controller.continueHandoff(handoff).then(()=>{handoffDone=true;},e=>{window.handoffError=e.message;handoffDone=true;});};startHandoff();
 });
 await page.getByRole('heading',{name:'Restore settings preset?'}).waitFor();await page.getByText('The target page has edits.',{exact:false}).waitFor();
 await page.getByRole('button',{name:'Keep current settings',exact:true}).click();await page.waitForFunction(()=>handoffDone);assert.equal(await page.evaluate(()=>owner.prompt),'PRIVATE TEXT');
 await page.evaluate(()=>startHandoff());await page.getByRole('button',{name:'Restore these settings',exact:true}).click();await page.waitForFunction(()=>handoffDone&&owner.prompt==='PRIVATE HANDOFF');
 assert.equal(await page.evaluate(()=>owner.size),'1536x1024');assert.equal(await page.evaluate(()=>owner.parameterHandoffDraftId),'fixture-interaction');assert.equal(await page.evaluate(()=>generated),0);
 const packets=await page.evaluate(()=>requests.map(r=>r.body).filter(Boolean));assert(!JSON.stringify(packets).includes('PRIVATE HANDOFF'));assert(!JSON.stringify(packets).includes('private-artifact'));
 await page.evaluate(()=>controller.dispose());
 }finally{await browser.close();}
});
