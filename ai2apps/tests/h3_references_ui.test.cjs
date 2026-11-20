const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx={window:{},document:{documentElement:{lang:'en'}},structuredClone,console};vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/imagine_studio.js','utf8'),ctx);
const a=ctx.window.imagineStudioApp();a.miniAppId='ai2apps.imagine.reference-creation';
a.models=[{id:'h3',operations:['image_generation','image_edit'],referenceLimits:{minimum:1,maximum:16}},{id:'gpt',operations:['image_edit'],referenceLimits:{minimum:1,maximum:4}}];
a.modelId='h3';assert.equal(a.referenceSlotCount,16);a.modelId='gpt';assert.equal(a.referenceSlotCount,4);
console.log('H3 reference slots follow selected model limits');
