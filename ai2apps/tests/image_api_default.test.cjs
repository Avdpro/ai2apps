const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let preferred='cloud/ai2apps/vendor/picture';
const items=['vendor/picture','other/replacement'].map(id=>({id,displayName:id,capabilities:{imageGeneration:true,imageEdit:true}}));
const ctx={window:{innerWidth:1200},document:{documentElement:{lang:'en'}},structuredClone,console,
 fetch:async url=>({ok:true,json:async()=>url.includes('/cloud/')?{items}:{data:[],preferred}})};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/imagine_studio.js','utf8'),ctx);
function app(){const a=ctx.window.imagineStudioApp();a.$nextTick=async()=>{};a.applySelectedModelCapability=()=>{};a.scheduleDraftSave=()=>{};return a;}
(async()=>{
 const a=app();assert.equal(a.modelId,'');await a.loadModelCatalog();assert.equal(a.modelId,preferred);
 preferred='cloud/ai2apps/other/replacement';await a.loadModelCatalog();assert.equal(a.modelId,preferred);
 for(const key of ['restoreTryOnDraft','restoreExtractDraft','restoreProductDraft','restorePortraitDraft','persistStylePreference'])a[key]=()=>{};
 a.applyDraft({modelId:'cloud/ai2apps/vendor/picture',modelSelectionMode:'default'});assert.equal(a.modelId,preferred);
 a.applyDraft({modelId:'cloud/ai2apps/vendor/picture'});assert.equal(a.modelSelectionMode,'explicit');assert.equal(a.modelId,'cloud/ai2apps/vendor/picture');
 a.onModelSelect({value:'cloud/ai2apps/vendor/picture'});await a.loadModelCatalog();assert.equal(a.modelId,'cloud/ai2apps/vendor/picture');
 a.onModelSelect({value:'__default__'});assert.equal(a.modelId,preferred);
 preferred='';await a.loadModelCatalog();assert.equal(a.modelId,'');assert.equal(a.selectedModel,null);
 a.onModelSelect({value:'cloud/ai2apps/vendor/picture'});await a.loadModelCatalog();assert.equal(a.selectedModel.id,'cloud/ai2apps/vendor/picture');
 a.models=[];a.reconcileSelectedModel();assert.equal(a.selectedModel,null);
 const registered=[];
 ctx.window.AI2AppsAppState={register(config){registered.push(config);return {target:config.target,dispose(){}};}};
 vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/imagine_app_state.js','utf8'),ctx);
 preferred='cloud/ai2apps/other/replacement';const b=app();await b.loadModelCatalog();b.appInstanceId=()=> 'fixture';b.persistPreferences=()=>{};
 ctx.window.AI2AppsImagineState.mount(b);
 const settings=registered.find(x=>x.target.mini_app_id==='ai2apps.imagine.text-to-image');
 const value={...settings.capture(),model_id:'cloud/ai2apps/vendor/picture'};
 await settings.apply(value);assert.equal(b.modelSelectionMode,'explicit');
 await b.loadModelCatalog();assert.equal(b.modelId,'cloud/ai2apps/vendor/picture');
 b.modelSelectionMode='default';b.modelId=preferred;
 let fail=true;b.$nextTick=async()=>{if(fail){fail=false;throw Error('fixture rollback');}};
 await assert.rejects(settings.apply(value),/fixture rollback/);
 assert.equal(b.modelSelectionMode,'default');assert.equal(b.modelId,preferred);
 console.log('Cloud image default inheritance, explicit selection and no arbitrary fallback passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
