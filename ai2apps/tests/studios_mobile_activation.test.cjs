const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function studio(name,width=390,force=false,fetcher=async()=>({ok:true,json:async()=>({items:[],draft:{}})})){
 const c={fetch:fetcher,window:{innerWidth:width,AI2APPS_MOBILE_SURFACE:force,t:k=>k,matchMedia:()=>({matches:width<=760}),addEventListener(){},location:{origin:'http://localhost'}},document:{documentElement:{lang:'en'},querySelector:()=>({dataset:{appInstanceId:"test"}})},crypto:{randomUUID:()=> 'test'},localStorage:{getItem:()=>null,setItem(){}},URL,console,setTimeout,clearTimeout,setInterval:()=>1,clearInterval(){}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/'+name+'.js','utf8'),c);
 return c.window[name==='readaloud'?'readAloudApp':'videoStudioApp']();
}
for(const name of ['video_studio','readaloud']){
 test(name+' mobile starts idle and rejects Gallery drops before reading data',async()=>{
  const app=studio(name);assert.equal(app.hasActiveMiniApp,false);assert.equal(app.currentMiniApp.id,'');
  const event={get dataTransfer(){throw Error('must not read inactive drop')},preventDefault(){throw Error('must not accept inactive drop')}};
  await (name==='readaloud'?app.acceptGalleryDrop(event):app.handleGalleryDrop(event));
  if(name==='readaloud')await app.acceptGalleryMessage({get origin(){throw Error('must not access inactive message')}});
  else {assert.equal(app.canGenerate,false);assert.equal(app.canPrimaryAction,false);}
 });
 test(name+' Desktop keeps default active Mini-App; forced mobile stays idle',()=>{
  const desktop=studio(name,1280);assert.equal(desktop.hasActiveMiniApp,true);assert.ok(desktop.currentMiniApp.id);
  assert.equal(studio(name,1280,true).currentMiniApp.id,'');
 });
 test(name+' explicit selection activates the matching workspace',async()=>{
  const app=studio(name);app.icons=app.emitBridge=app.persistShellState=()=>{};
  if(name==='readaloud'){
   app.saveDraft=app.loadDraft=app.restoreProject=async()=>{};
   const item=app.miniApps.find(x=>x.mode==='audiobook');await app.selectMiniApp(item.id);
   assert.equal(app.pipelineMode,item.mode);assert.equal(app.currentMiniApp.id,item.id);
  }else{
   app.switchMode=async mode=>{app.mode=mode};app.restoreMiniAppDraft=()=>{};
   const item=app.miniApps.find(x=>x.mode==='i2v');await app.selectMiniApp(item.id);
   assert.equal(app.mode,item.mode);assert.equal(app.currentMiniApp.id,item.id);
  }
  assert.equal(app.hasActiveMiniApp,true);
 });
}


test('Voice mobile reveals selected Mini-App while capability probe is still pending',async()=>{
 const app=studio('readaloud');let reveal=0,release;
 const blocked=new Promise(resolve=>release=resolve);
 for(const name of ['applyResponsiveLayout','refreshAllPackageMiniAppReadiness','refresh','refreshRuns','refreshQuickHistory','refreshTrainingHistory','refreshOutputs'])app[name]=async()=>{};
 app.probeCapabilities=()=>blocked;
 app.openShellMiniApp=async()=>{assert.equal(app.starting,false);reveal++;};
 app.fail=error=>{throw error};
 const pending=app.initializeStudio();
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(reveal,1,'detail must be revealed before the blocked background request finishes');
 release();await pending;assert.equal(reveal,1);
});
test('Voice mobile template relies on Alpine automatic init without a second explicit init',()=>{
 const template=fs.readFileSync(__dirname+'/../web/templates/system_apps/readaloud.html','utf8');
 assert.match(template,/x-init="if \(!mobileViewport\) init\(\);/);
});


test('Voice reveals before slow workspace data and only audiobook requests projects',async()=>{
 let release;const blocked=new Promise(resolve=>release=resolve);const requests=[];
 const app=studio('readaloud',390,false,async url=>{requests.push(url);await blocked;return {ok:true,json:async()=>({items:[],draft:{}})};});
 app.icons=()=>{};app.fail=error=>{throw error;};let revealed=0;
 app.showMobileMiniAppShell=()=>{revealed++;assert.equal(app.starting,true);};
 const pending=app.selectMiniApp('ai2apps.audio.quick-read');
 assert.equal(revealed,1);assert.equal(app.currentMiniApp.id,'ai2apps.audio.quick-read');
 assert.equal(app.starting,true);assert.equal(app.mobileWorkspaceReady,false);
 assert.equal(requests.some(url=>url.endsWith('/projects')),false);
 release();await pending;assert.equal(app.starting,false);assert.equal(app.mobileWorkspaceReady,true);
 await app.selectMiniApp('ai2apps.audio.audiobook');
 assert.equal(requests.filter(url=>url.endsWith('/projects')).length,1);
});

test('Voice keeps editing locked until all parallel draft reads settle after failure',async()=>{
 let release;const draft=new Promise(resolve=>release=resolve);
 const app=studio('readaloud',390,false,async url=>{
  if(url.endsWith('/providers'))throw Error('offline');
  if(url.includes('/drafts/'))await draft;
  return {ok:true,json:async()=>({items:[],draft:{}})};
 });
 app.icons=()=>{};app.fail=()=>{};app.showMobileMiniAppShell=()=>{};
 const pending=app.selectMiniApp('ai2apps.audio.quick-read');
 await new Promise(resolve=>setImmediate(resolve));assert.equal(app.starting,true);
 release();await pending;assert.equal(app.starting,false);assert.equal(app.mobileWorkspaceReady,false);assert.equal(app.startupError,'offline');
});
