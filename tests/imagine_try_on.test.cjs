const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx={window:{confirm:()=>true},document:{documentElement:{lang:'en'}},structuredClone,console};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../ai2apps/web/static/js/imagine_studio.js','utf8'),ctx);
const a=ctx.window.imagineStudioApp();a.miniAppId='ai2apps.imagine.try-on';a.icons=()=>{};a.scheduleDraftSave=()=>{};
a.models=[{id:'one',operations:['image_edit'],referenceLimits:{maximum:1}},{id:'two',label:'Two',source:'cloud',operations:['image_edit'],referenceLimits:{minimum:1,maximum:2}}];a.modelId='two';
Object.defineProperty(a,'sizeError',{value:''});Object.defineProperty(a,'selectedStyle',{value:{prompt:'UNWANTED_STYLE'}});
assert.equal(a.requiredOperation,'image_edit');assert.equal(a.compatibleModels.length,1);assert.equal(a.prefersOpenAIModel,true);
assert.equal(a.canGenerate,false);a.referenceFiles=[{name:'person'}];assert.equal(a.canGenerate,false);
a.referenceFiles=[null,{name:'item'}];assert.equal(a.canGenerate,false);a.referenceFiles[0]={name:'person'};assert.equal(a.canGenerate,true);
assert.equal(a.referenceSlotRequirement(1),'Required');
for(const interaction of ['wear','use','hold']){
 a.tryOnInteraction=interaction;assert.equal(a.canGenerate,true);assert.match(a.composedPrompt(),/Image 1 is the ONLY identity reference/);assert.match(a.composedPrompt(),/Image 2 is ITEM ONLY/);assert.doesNotMatch(a.composedPrompt(),/UNWANTED_STYLE/);
}
assert.match(a.composedPrompt(),/holding/);
a.tryOnPose='custom';assert.equal(a.canGenerate,false);a.tryOnPoseText='Raised right arm';assert.equal(a.canGenerate,true);
a.tryOnBackground='custom';assert.equal(a.canGenerate,false);a.tryOnBackgroundText='A quiet library';assert.equal(a.canGenerate,true);
assert.match(a.composedPrompt(),/Raised right arm/);assert.match(a.composedPrompt(),/quiet library/);
const saved=a.draftPayload();a.restoreTryOnDraft({});assert.equal(a.tryOnInteraction,'wear');a.restoreTryOnDraft(saved);assert.equal(a.tryOnInteraction,'hold');assert.equal(a.tryOnBackgroundText,'A quiet library');
a.editSubmissionPrompt('manual');a.tryOnBackground='white';a.syncSubmissionPrompt();assert.match(a.submissionPrompt,/white photography studio/);assert.doesNotMatch(a.submissionPrompt,/quiet library/);
a.setLocale('zh');assert.equal(a.currentMiniApp.name,'试穿试用');assert.equal(a.referenceSlotLabel(1),'物品参考图');
(async()=>{
 ctx.FileReader=class{readAsDataURL(file){this.result='data:image/png;base64,'+file.name;this.onload();}};
 let payload;a.saveDraft=async()=>{};a.createRun=async()=>({id:'try',status:'queued'});a.selectRun=()=>{};a.dismissNotice=()=>{};
 a.executeCloudRun=async(_,p)=>{payload=p;};a.waitForRun=async()=>({id:'try',status:'succeeded'});a.fail=e=>{throw e;};
 await a.generate();assert.deepEqual(Array.from(payload.imageDataUrls),['data:image/png;base64,person','data:image/png;base64,item']);
 assert.equal(payload.prompt,a.submissionPrompt);
 console.log('Try On required references, modes, model filtering, draft, i18n and request order: passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
