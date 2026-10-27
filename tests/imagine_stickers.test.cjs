const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),test=require('node:test');
function fixture(mobile=false){
 const requests=[];const ctx={window:{innerWidth:mobile?390:1200,confirm:()=>true,location:{origin:'http://local'}},document:{documentElement:{lang:'zh'}},structuredClone,console,URL,
 FileReader:class{readAsDataURL(file){this.result=file.url;this.onload();}},fetch:async(url,options)=>{requests.push({url,body:options.body?JSON.parse(options.body):null});return {ok:true,json:async()=>({id:'job',status:'queued'})}}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../ai2apps/web/static/js/imagine_studio.js','utf8'),ctx);
 const a=ctx.window.imagineStudioApp();a.miniAppId='ai2apps.imagine.sticker-workshop';a.models=[{id:'cloud/test',source:'cloud',label:'Test',operations:['image_edit']}];a.modelId='cloud/test';
 a.referenceFiles=[{url:'data:image/png;base64,original'}];a.icons=()=>{};a.scheduleDraftSave=()=>{};a.saveDraft=async()=>{};a.historyHeaders=()=>({});a.refreshRuns=async()=>{};a.fail=e=>{throw e};
 Object.defineProperty(a,'canGenerate',{value:true});a.createRun=async input=>({id:'run',status:'queued',miniAppId:a.miniAppId,input,artifacts:[]});
 return {a,ctx,requests};
}
for(const mobile of [false,true])test(`sticker batch submits once with frozen prompts and references (${mobile?'Mobile':'Desktop'})`,async()=>{
 const {a,requests}=fixture(mobile);a.stickerEmotion='sad';a.prompt='Keep red scarf';
 a.saveDraft=async()=>{a.prompt='changed';a.referenceFiles=[{url:'different'}];};
 await a.generateStickerSet();assert.equal(requests.length,1);const body=requests[0].body;
 assert.equal(body.kind,'sticker-batch');assert.equal(body.payload.prompts.length,4);
 assert.match(body.payload.prompts[0],/Laughing joyfully/);assert.match(body.payload.prompts[3],/teary eyes/);
 assert(body.payload.prompts.every(p=>p.includes('Keep red scarf')));assert.equal(body.payload.imageDataUrls[0],'data:image/png;base64,original');
 assert.equal(a.stickerBatchBusy,false);assert.equal(a.stickerEmotion,'sad');assert.equal(a.selectedRunId,'run');
});
test('declined paid batch submits nothing',async()=>{const {a,ctx,requests}=fixture();ctx.window.confirm=()=>false;await a.generateStickerSet();assert.equal(requests.length,0)});
test('batch stop is a server operation and can be recovered from shared Runs',async()=>{const {a,requests}=fixture();a.runs=[{id:'run',miniAppId:a.miniAppId,status:'running',input:{stickerBatch:true},artifacts:[]}];await a.stopStickerBatch();assert.equal(requests[1].url,'/v1/platform/studio-jobs/job/cancel?after_current=true');});
for(const mobile of [false,true])test(`all built-in Mini-Apps preserve shared Output and selection (${mobile?'Mobile':'Desktop'})`,async()=>{
 const {a}=fixture(mobile);a.runs=[{id:'output',status:'running',artifacts:[{id:'image'}]}];a.selectedRunId='output';a.selectedArtifactId='image';
 a.saveDraft=async()=>{};a.loadDraft=async()=>({});a.persistPreferences=()=>{};a.reconcileSelectedModel=()=>{};a.trimReferences=()=>{};a.preferOpenAIEditingModel=()=>{};a.applySelectedModelCapability=()=>{};
 for(const item of a.miniApps.filter(item=>item.source!=='package'&&item.status==='ready')){
  await a.selectMiniApp(item.id);assert.equal(a.miniAppId,item.id);assert.equal(a.selectedRunId,'output');assert.equal(a.selectedArtifactId,'image');assert.equal(a.runs.length,1);
 }
});
for(const mobile of [false,true])test(`Package Mini-App shares the same Output (${mobile?'Mobile':'Desktop'})`,async()=>{
 const {a}=fixture(mobile);a.runs=[{id:'run',artifacts:[{id:'image'}]}];a.selectedRunId='run';a.selectedArtifactId='image';
 const packageItem={id:'test.package',source:'package',status:'ready'};Object.defineProperty(a,'miniApps',{value:[packageItem]});
 a.persistPreferences=()=>{};a.mountPackageMiniApp=async()=>{a.packageMiniAppId=packageItem.id;};
 await a.selectMiniApp(packageItem.id);assert.equal(a.selectedRunId,'run');assert.equal(a.selectedArtifactId,'image');assert.equal(a.runs.length,1);
});
