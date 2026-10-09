const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const items = ['sunburst', 'flare'].map(name => ({id:`cloud/openai/gpt-image-2.5-${name}`,display_name:`(BYOK) OpenAI · ${name}`,source_type:'byok',model_type:'image_generation',capabilities:['image_generation','image_edit'],imageOptions:{quality:['auto','high'],outputFormat:['png'],size:{mode:'fixed',default:'1024x1024',presets:['1024x1024']}}}));
const ctx = {window:{}, document:{documentElement:{lang:'en'}}, structuredClone, console,
 fetch:async url => ({ok:!url.includes('/cloud/'),status: url.includes('/cloud/')?403:200,json:async()=>url.includes('/cloud/')?{error:{message:'offline'}}:{data:items}})};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/imagine_studio.js','utf8'),ctx);
(async()=>{ const a=ctx.window.imagineStudioApp();a.$nextTick=async()=>{};a.icons=()=>{};
 await a.loadModelCatalog();assert.equal(a.models.length,2);assert.equal(a.compatibleModels.length,2);
 assert.match(a.tr('cloudSubmitHint'),/directly/); assert.doesNotMatch(a.tr('uploadConfirm',{count:1}),/AI2Apps Cloud/);
 assert.equal(a.modelId,items[0].id);assert.equal(a.usingLocalModel,false);assert.equal(a.models[0].source,'byok');
 a.modelId=items[1].id;await a.loadModelCatalog();assert.equal(a.modelId,items[1].id);
 let sent;
 a.prompt='A blue square';a.saveDraft=async()=>{};a.createRun=async()=>({id:'test-run',status:'queued'});
 a.selectRun=()=>{};a.dismissNotice=()=>{};a.executeCloudRun=async(_,payload)=>{sent=payload;};
 a.waitForRun=async()=>({id:'test-run',status:'succeeded'});a.refreshRuns=async()=>{};a.fail=e=>{throw e;};
 await a.generate();assert.equal(sent.model,items[1].id);assert.equal(sent.prompt.length>0,true);
 items.length=0;await a.loadModelCatalog();assert.equal(a.models.length,0);assert.equal(a.modelId,'');
 console.log('BYOK catalog survives offline Cloud, preserves IDs/selection, no fake fallback: passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
