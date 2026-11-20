const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const context={window:{addEventListener(){},},document:{documentElement:{lang:'en'}}};
vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/capability_provisioning.js','utf8'),context);
const select=context.window.AI2AppsCapabilities.miniAppPackageComponents;
test('ACPF Mini-App selection requires declared host placement',()=>{
 const reader={componentId:'reader',placements:['ai2apps.ai-browser']},image={componentId:'image',placements:['ai2apps.imagine-studio']};
 assert.equal(select({miniApps:[reader,image]},'ai2apps.ai-browser').length,1);
 assert.equal(select({manifest:{miniApps:[reader]}},'ai2apps.ai-browser')[0],reader);
 assert.equal(select({miniApps:[image]},'ai2apps.ai-browser').length,0);
 assert.equal(select({miniApps:[{componentId:'unknown'}]},'ai2apps.ai-browser').length,0);
 assert.equal(select({miniApps:'invalid'},'ai2apps.ai-browser').length,0);
});

test('every Studio placement uses the shared ACPF picker and refreshes only after installation', async () => {
 const window={addEventListener(){}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/studio_mini_apps.js','utf8'),{window});
 for(const placement of ['ai2apps.imagine-studio','ai2apps.video-studio','ai2apps.readaloud','ai2apps.doc-studio','ai2apps.ai-browser']){
  let refreshed=0;
  for(const installed of [false,true]){
   window.AI2AppsCapabilities={openMiniAppPackages:async options=>{
    assert.equal(options.placement,placement);return {installed};
   }};
   await window.AI2AppsStudioPackages.install(placement,()=>refreshed++);
   assert.equal(refreshed,Number(installed));
  }
 }
});

test('version refresh only accepts activation for the embedded Studio from its Shell', () => {
 const parent={},location={origin:'https://studio.test',hash:'#ai2apps-mount=mount-token'};
 const handlers=new Set();
 const window={parent,location,addEventListener:(type,handler)=>handlers.add(handler),
     removeEventListener:(type,handler)=>handlers.delete(handler)};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/studio_mini_apps.js','utf8'),{window,URLSearchParams});
 let refreshes=0;
 const stop=window.AI2AppsStudioPackages.watchActivation(()=>refreshes++);
 const activation={origin:location.origin,source:parent,data:{type:'ai2apps.host.activate',mountToken:'mount-token'}};
 const send=event=>{for(const handler of handlers)handler(event);};
 send({...activation,source:{}});
 send({...activation,origin:'https://other.test'});
 send({...activation,data:{...activation.data,mountToken:'other'}});
 assert.equal(refreshes,0);
 send(activation);
 stop();
 send(activation);
 assert.equal(refreshes,1);
});
