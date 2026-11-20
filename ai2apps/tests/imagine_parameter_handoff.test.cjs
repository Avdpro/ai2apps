const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
const source=fs.readFileSync(__dirname+'/../web/static/js/imagine_studio.js','utf8');
function setup(values,models){
 const handoff={run_id:'r',interaction_id:'i',status:'pending',target:{app_id:'ai2apps.imagine-studio',mini_app_id:'ai2apps.imagine.group-photo'},parameters:{values,references:[{artifact_id:'a',session_id:'s',slot:0},{artifact_id:'b',session_id:'s',slot:1}]}};
 const requests=[];const ctx={TextEncoder,AbortController,setTimeout,clearTimeout,crypto:webcrypto,structuredClone,window:{},document:{documentElement:{lang:'zh'}},console,URL:{revokeObjectURL(){}},fetch:async(url,options={})=>{const body=options.body&&JSON.parse(options.body);requests.push({url,body});let value=handoff;if(url.includes('/contract?'))value={contract_version:1,contract_digest:'a'.repeat(64),schema:{properties:Object.fromEntries(['model_id','style_id','width','height','quality','format'].map(k=>[k,{}]))}};else if(url.endsWith('/validate'))value={packet:body.packet,contract_digest:'a'.repeat(64)};else if(url.endsWith('/applications'))value={id:'apply',status:'prepared'};else if(url.endsWith('/complete'))value={status:body.status};return {ok:true,json:async()=>value};}};vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/app_state.js','utf8'),ctx);vm.runInNewContext(source,ctx);vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/imagine_app_state.js','utf8'),ctx);
 const app=ctx.window.imagineStudioApp();Object.assign(app,{models,modelId:model.id,size:'1024x1024',style:'',quality:'auto',format:'png',miniApps:[{id:'ai2apps.imagine.group-photo',status:'ready',mode:'group-photo',personSlots:3,backgroundSlot:3,maxImages:4}],miniAppId:'ai2apps.imagine.group-photo',icons(){},fail(e){this.failure=e.message;},selectMiniApp:async()=>{},materializeAssetReference:async function(_,slot){this.referenceFiles[slot]={};this.referenceDimensions[slot]={width:1536,height:1024};},saveDraft:async function(){this.saved=this.draftPayload();},syncSubmissionPrompt(){}});
 app.$nextTick=async()=>{app.applySelectedModelCapability();};Object.assign(app,{appInstanceId:()=> 'instance',persistPreferences(){},scheduleDraftSave(){}});app.appStateController=ctx.window.AI2AppsImagineState.mount(app);app.requests=requests;app.handoffFixture=handoff;return app;
}
const model={id:'cloud/openai/gpt-image-test',source:'byok',label:'Test',operations:['image_generation','image_edit'],referenceLimits:{maximum:4},formats:['png'],qualities:['auto'],sizeCapability:{mode:'fixed',default:'1024x1024',presets:['1024x1024','1536x1024','1024x1536'],width:{max:2048,multipleOf:1},height:{max:2048,multipleOf:1},minPixels:1,maxPixels:4194304,maxAspectRatio:4}};
test('App continuation preserves exact model, requested canvas and materials across reactive updates',async()=>{
 const app=setup({model:model.id,size:'1024x1024',prompt:'Group photo',background:'Bamboo',quality:'auto',format:'png'},[model]);
 await app.openParameterHandoff({runId:'r',interactionId:'i'});app.applySelectedModelCapability();
 assert.equal(app.modelId,model.id);assert.equal(app.selectedModel.id,model.id);assert.equal(app.size,'1024x1024');assert.equal(app.referenceFiles.length,2);assert.equal(app.saved.size,'1024x1024');assert.equal(app.saved.parameterHandoffInteractionId,'i');
});
test('unavailable or incompatible transferred model cannot silently select a different provider',async()=>{
 for(const models of [[model],[{...model,id:'not-compatible',referenceLimits:{maximum:1}}]]){
  const app=setup({model:'not-compatible',size:'1024x1024'},models);await assert.rejects(app.openParameterHandoff({runId:'r',interactionId:'i'}),/unavailable/);
  assert.equal(app.parameterHandoff,null);assert.equal(app.referenceFiles.length,0);assert(!app.requests.some(r=>r.url.endsWith('/applications')));
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


test('identical settings still import continuation content once through the shared restore transaction',async()=>{
 const app=setup({model:model.id,size:'1024x1024',prompt:'PRIVATE incoming'},[model]);
 let commits=0;const original=app.materializeAssetReference;app.materializeAssetReference=async function(...args){commits++;return original.apply(this,args);};
 await app.openParameterHandoff({runId:'r',interactionId:'i'});await app.openParameterHandoff({runId:'r',interactionId:'i'});
 assert.equal(commits,2);assert.equal(app.prompt,'PRIVATE incoming');
 const states=app.requests.filter(r=>r.url.includes('/app-state/'));assert(states.some(r=>r.url.endsWith('/applications')));
 assert(!JSON.stringify(states).includes('PRIVATE incoming'));assert(!JSON.stringify(states).includes('artifact_id'));
});
test('continuation conflict cancellation preserves text, settings and materials without a prepared application',async()=>{
 const app=setup({model:model.id,size:'1536x1024',prompt:'new'},[model]);app.prompt='Existing private draft';const files=[{}];app.referenceFiles=files;
 await assert.rejects(app.appStateController.continueHandoff(app.handoffFixture,{confirmConflict:async()=>false}),/保留|retained/);
 assert.equal(app.prompt,'Existing private draft');assert.equal(app.size,'1024x1024');assert.equal(app.referenceFiles,files);assert.equal(app.parameterHandoffDraftId,'');
 assert(!app.requests.some(r=>r.url.endsWith('/applications')));
});
test('resource failure rolls back the complete UI configuration and retains the original materials',async()=>{
 const app=setup({model:model.id,size:'1536x1024',prompt:'new'},[model]);app.prompt='Old draft';const files=[{}];app.referenceFiles=files;
 app.materializeAssetReference=async function(_,slot){this.referenceFiles[slot]={};if(slot===1)throw Error('reference unavailable');};
 await assert.rejects(app.appStateController.continueHandoff(app.handoffFixture,{confirmConflict:async()=>true}),/reference unavailable/);
 assert.equal(app.prompt,'Old draft');assert.equal(app.size,'1024x1024');assert.equal(app.referenceFiles,files);assert.equal(app.appStateRestoring,false);assert.equal(app.parameterHandoffDraftId,'');
 assert(app.requests.some(r=>r.body?.status==='failed'));
});
test('preset and continuation share the same owner validation for unsupported canvas settings',async()=>{
 const app=setup({model:model.id,size:'999x999'},[model]);
 await assert.rejects(app.openParameterHandoff({runId:'r',interactionId:'i'}));
 assert.equal(app.size,'1024x1024');assert.equal(app.referenceFiles.length,0);assert(!app.requests.some(r=>r.url.endsWith('/applications')));
});
test('automatic canvas preserves model-supported auto semantics',async()=>{
 const app=setup({model:model.id,size:'auto'},[{...model,sizeCapability:{...model.sizeCapability,auto:true}}]);
 await app.openParameterHandoff({runId:'r',interactionId:'i'});assert.equal(app.size,'auto');
 const call=app.requests.find(r=>r.url.endsWith('/applications'));assert.equal(call.body.packet.values.width,null);assert.equal(call.body.packet.values.height,null);
});

test('a different continuation with identical settings still replaces its own private content',async()=>{
 const app=setup({model:model.id,size:'1024x1024',prompt:'first'},[model]);
 await app.openParameterHandoff({runId:'r',interactionId:'i'});
 const next={...app.handoffFixture,interaction_id:'next-interaction',parameters:{...app.handoffFixture.parameters,values:{...app.handoffFixture.parameters.values,prompt:'second'}}};
 await app.appStateController.continueHandoff(next,{confirmConflict:async()=>true});
 assert.equal(app.prompt,'second');assert.equal(app.parameterHandoffDraftId,'next-interaction');
 assert.equal(app.requests.filter(r=>r.url.endsWith('/applications')).length,2);
});

test('generation stays disabled while an App continuation is being prepared',()=>{
 const app=setup({model:model.id},[model]);app.parameterHandoffLoading=true;
 assert.equal(app.canGenerate,false);
});

for(const [mini,values,expected] of [
 ['extract-items',{target:'custom',target_description:'yellow coat'},['extractTarget','custom','extractCustom','yellow coat']],
 ['try-on',{interaction:'hold',pose:'custom',pose_description:'seated',background:'park'},['tryOnInteraction','hold','tryOnPoseText','seated']],
 ['product-poster',{scene:'stone',lighting:'window',composition:'right',setting_style:'minimal'},['productScene','stone','productSettingStyle','minimal']]
])test('commerce handoff restores roles and settings: '+mini,async()=>{
 const app=setup({model:model.id,size:'1536x1024',quality:'auto',format:'png',...values},[model]);
 const id='ai2apps.imagine.'+mini;app.miniApps.push({id,status:'ready',mode:mini,maxImages:mini==='try-on'?2:1});
 app.miniAppId=id;app.handoffFixture.target.mini_app_id=id;
 app.handoffFixture.parameters.references=app.handoffFixture.parameters.references.slice(0,mini==='try-on'?2:1);
 await app.openParameterHandoff({runId:'r',interactionId:'i'});
 assert.equal(app[expected[0]],expected[1]);assert.equal(app[expected[2]],expected[3]);assert.equal(app.size,'1536x1024');
 assert.equal(app.referenceFiles.length,mini==='try-on'?2:1);
});
