const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx={window:{},document:{documentElement:{lang:'en'}},structuredClone,console};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../ai2apps/web/static/js/imagine_studio.js','utf8'),ctx);
const a=ctx.window.imagineStudioApp();a.miniAppId='ai2apps.imagine.extract-items';
a.scheduleDraftSave=()=>{};a.icons=()=>{};
a.models=[{id:'edit',source:'local',operations:['image_edit']}];a.modelId='edit';
Object.defineProperty(a,'sizeError',{value:''});
Object.defineProperty(a,'selectedStyle',{value:{prompt:'UNWANTED_STYLE'}});
assert.equal(a.currentMiniApp.name,'Extract Items');assert.equal(a.requiredOperation,'image_edit');
assert.equal(a.canGenerate,false);a.referenceFiles=[{name:'source.png'}];assert.equal(a.canGenerate,true);
for(const [id,key] of a.extractOptions){
 a.extractTarget=id;
 if(id==='custom'){assert.equal(a.canGenerate,false);a.extractCustom='The red mug on the left';}
 assert.equal(a.canGenerate,true);assert.notEqual(a.tr(key),key);
 assert.doesNotMatch(a.composedPrompt(),/UNWANTED_STYLE/);
 assert.match(a.composedPrompt(),/pure white background/);
}
assert.match(a.composedPrompt(),/red mug on the left/);
const draft=a.draftPayload();a.restoreExtractDraft({});assert.equal(a.extractTarget,'outfit');
a.restoreExtractDraft(draft);assert.equal(a.extractTarget,'custom');assert.equal(a.extractCustom,'The red mug on the left');
a.editSubmissionPrompt('manual');a.extractCustom='The blue bag';a.syncSubmissionPrompt();assert.match(a.submissionPrompt,/blue bag/);
a.restoreExtractDraft({extractTarget:'invalid',extractCustom:'x'.repeat(3000)});assert.equal(a.extractTarget,'outfit');assert.equal(a.extractCustom.length,2000);
a.setLocale('zh');assert.equal(a.currentMiniApp.name,'提取物品');
console.log('Extract Items target presets, validation, prompts, draft and language: passed');
