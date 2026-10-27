const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/imagine_studio.js','utf8');
function setup(values,models){
 const handoff={run_id:'r',interaction_id:'i',status:'pending',target:{app_id:'ai2apps.imagine-studio',mini_app_id:'group-photo'},parameters:{values,references:[{artifact_id:'a',session_id:'s',slot:0},{artifact_id:'b',session_id:'s',slot:1}]}};
 const ctx={structuredClone,window:{},document:{documentElement:{lang:'zh'}},console,URL:{revokeObjectURL(){}},fetch:async()=>({ok:true,json:async()=>handoff})};vm.runInNewContext(source,ctx);
 const app=ctx.window.imagineStudioApp();Object.assign(app,{models,miniApps:[{id:'group-photo',status:'ready',mode:'group-photo',personSlots:3,backgroundSlot:3,maxImages:4}],miniAppId:'group-photo',icons(){},fail(e){this.failure=e.message;},selectMiniApp:async()=>{},materializeAssetReference:async function(_,slot){this.referenceFiles[slot]={};this.referenceDimensions[slot]={width:1536,height:1024};},saveDraft:async function(){this.saved=this.draftPayload();},syncSubmissionPrompt(){}});
 app.$nextTick=async()=>{app.applySelectedModelCapability();};return app;
}
const model={id:'cloud/openai/gpt-image-test',source:'byok',label:'Test',operations:['image_generation','image_edit'],referenceLimits:{maximum:4},formats:['png'],qualities:['auto'],sizeCapability:{mode:'fixed',default:'1024x1024',presets:['1024x1024','1536x1024','1024x1536']}};
test('App continuation preserves exact model, requested canvas and materials across reactive updates',async()=>{
 const app=setup({model:model.id,size:'1024x1024',prompt:'Group photo',background:'Bamboo',quality:'auto',format:'png'},[model]);
 await app.openParameterHandoff({runId:'r',interactionId:'i'});app.applySelectedModelCapability();
 assert.equal(app.modelId,model.id);assert.equal(app.selectedModel.id,model.id);assert.equal(app.size,'1024x1024');assert.equal(app.referenceFiles.length,2);assert.equal(app.saved.size,'1024x1024');assert.equal(app.saved.parameterHandoffInteractionId,'i');
});
test('unavailable or incompatible transferred model cannot silently select a different provider',async()=>{
 for(const models of [[model],[{...model,id:'not-compatible',referenceLimits:{maximum:1}}]]){
  const app=setup({model:'not-compatible',size:'1024x1024'},models);await app.openParameterHandoff({runId:'r',interactionId:'i'});
  assert.equal(app.selectedModel,null);assert.equal(app.modelId,'');assert.equal(app.canGenerate,false);assert.match(app.failure,/unavailable/);
 }
});
test('reopening a handed-off App preserves the user-edited draft',async()=>{
 const app=setup({model:model.id,size:'1024x1024',prompt:'original'},[model]);app.parameterHandoffDraftId='i';app.prompt='User edit';app.size='1536x1024';
 await app.openParameterHandoff({runId:'r',interactionId:'i'});assert.equal(app.prompt,'User edit');assert.equal(app.size,'1536x1024');assert.equal(app.saved,undefined);
});

test('persisted handoff draft keeps resolution and cannot fall back during reload before host context arrives',()=>{
 const app=setup({},[model]);app.parameterHandoffDraftId='i';app.parameterHandoff=null;app.referenceDimensions=[{width:1536,height:1024}];app.modelId=model.id;app.size='1024x1024';app.reconcileSelectedModel();assert.equal(app.size,'1024x1024');
 app.modelId='removed-model';app.reconcileSelectedModel();assert.equal(app.modelId,'');assert.equal(app.selectedModel,null);
});
