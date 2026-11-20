const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
function editor(){
 const calls=[];const ctx={window:{},crypto:require('crypto').webcrypto,fetch:async(url,options)=>{calls.push({url,options});return{ok:true,json:async()=>({id:'c1',...JSON.parse(options.body),revision:1})}}};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/imagine_characters.js','utf8'),ctx);
 const app=ctx.window.ImagineCharacters();Object.assign(app,{locale:'zh',prompt:'',currentMiniApp:{adapter:'character-design'},fail:e=>{throw e;},success:()=>{},scheduleDraftSave:()=>{}});return{app,calls};
}
test('identity has independent named appearances; prompt compiles only selected appearance',()=>{
 const{app}=editor();app.newCharacter();app.characterDraft.name='本人';app.characterAppearance.name='卡通';app.characterAppearance.style='chibi';const original=app.appearanceId;
 app.newAppearance();app.characterAppearance.name='超级英雄';app.characterAppearance.outfit='red cape';
 assert.match(app.characterDesignPrompt(),/red cape/);assert.doesNotMatch(app.characterDesignPrompt(),/chibi/);
 app.appearanceId=original;assert.match(app.characterDesignPrompt(),/chibi/);assert.doesNotMatch(app.characterDesignPrompt(),/red cape/);
});
test('saving strips server appearance revision and uses current identity revision',async()=>{
 const{app,calls}=editor();app.newCharacter();app.characterDraft.name='熊猫';app.characterAppearance.revision=9;await app.saveCharacter();
 assert.equal(app.characterId,'c1');assert.equal(calls[0].options.method,'POST');assert.equal(JSON.parse(calls[0].options.body).appearances[0].revision,undefined);
 await app.saveCharacter();assert.equal(calls[1].options.method,'PUT');assert.equal(JSON.parse(calls[1].options.body).revision,1);
});
test('shared appearance clears old Slots and pins provenance before reuse',async()=>{
 const{app}=editor();app.newCharacter();app.characterDraft.name='本人';app.characterDraft.id='c1';app.characterId='c1';app.characterDraft.revision=4;app.characterAppearance.reference_ids=['original'];app.characterAppearance.definition_image_id='r1';app.characterAppearance.summary='Reusable guide';app.characterAppearance.revision=2;
 app.characterAppearance.approved=true;app.characterItems=[JSON.parse(JSON.stringify({...app.characterDraft,id:'c1'}))];app.currentMiniApp={adapter:'sticker-workshop'};app.referenceSlotCount=2;const steps=[];app.clearReference=i=>steps.push('clear'+i);app.materializeAssetReference=async(ref,i)=>steps.push(ref.assetId+':'+i);
 await app.useCharacterAppearance();assert.deepEqual(steps,['clear0','clear1','r1:0']);assert.equal(app.characterReference.revision,4);assert.equal(app.prompt,'Reusable guide');
});
test('Studio composes lazy character getters without evaluating them before initialization',()=>{
 const ctx={window:{},structuredClone,document:{documentElement:{lang:'zh'}}};vm.createContext(ctx);
 for(const file of ['imagine_characters.js','imagine_studio.js'])vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/'+file,'utf8'),ctx);
 const app=ctx.window.imagineStudioApp();assert.equal(app.isCharacterMode,false);app.miniAppId='ai2apps.imagine.character-design';assert.equal(app.isCharacterMode,true);assert.equal(app.currentMiniApp.status,'ready');
});
test('appearance style picker uses shared catalog without changing global style; cancellation is inert',()=>{
 const ctx={window:{},structuredClone,crypto:require('crypto').webcrypto,document:{documentElement:{lang:'zh'}}};vm.createContext(ctx);
 for(const file of ['imagine_characters.js','imagine_style_catalog.js','imagine_studio.js'])vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/'+file,'utf8'),ctx);
 const app=ctx.window.imagineStudioApp();app.icons=()=>{};app.newCharacter();app.characterDraft.name='Panda';app.characterAppearance.name='Hero';app.characterAppearance.style='Custom';app.characterAppearance.proportions='three heads';
 const preset=app.allStyles[0];app.style='global-choice';app.openStyleDialog('character');app.chooseStyle(preset.id);app.applyStyle();
 assert.equal(app.characterAppearance.style,preset.prompt);assert.equal(app.characterAppearance.style_id,preset.id);assert.equal(app.style,'global-choice');assert.equal(app.characterStyleLabel,app.localizedName(preset));
 app.openStyleDialog('character');app.chooseStyle('');app.closeStyleDialog();assert.equal(app.characterAppearance.style,preset.prompt);
 app.prompt='stale hidden prompt';assert.match(app.characterDesignPrompt(),/three heads/);assert.doesNotMatch(app.characterDesignPrompt(),/stale hidden prompt/);
});
test('character Slots precede appearance parameters and share the standard Slot implementation',()=>{
 const html=fs.readFileSync(__dirname+'/../web/templates/system_apps/_imagine_characters.html','utf8');
 assert.ok(html.indexOf("_imagine_reference_slots.html")>html.indexOf('派生形象'));
 assert.ok(html.indexOf("_imagine_reference_slots.html")<html.indexOf('形象名称'));
 assert.match(html,/openStyleDialog\('character'\)/);assert.match(html,/身形比例/);
 const host=fs.readFileSync(__dirname+'/../web/templates/system_apps/imagine_studio.html','utf8');assert.match(host,/!isUpscaleMode&&!isCharacterMode.*vs-field vs-prompt/);
});
test('render preparation writes a missing guide, saves and pins the exact appearance',async()=>{
 const{app}=editor();app.newCharacter();app.characterDraft.name='Mug';app.characterAppearance.revision=3;
 const order=[];app.generateCharacterDescription=async()=>{order.push('guide');app.characterAppearance.summary='An editable guide';};app.saveCharacter=async()=>{order.push('save');return{id:'saved'};};
 assert.equal(await app.prepareCharacterRender(),true);assert.deepEqual(order,['guide','save']);assert.equal(app.characterDesignTarget.character_id,'saved');assert.equal(app.characterDesignTarget.appearance_revision,3);
 order.length=0;await app.prepareCharacterRender();assert.deepEqual(order,['save']);
});
test('completed image collection preserves unsaved edits and merges generated pictures into the original appearance',async()=>{
 const ctx={window:{},crypto:require('crypto').webcrypto};vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/imagine_characters.js','utf8'),ctx);
 const app=ctx.window.ImagineCharacters();app.locale='en';app.currentMiniApp={adapter:'character-design'};app.newCharacter();app.characterDraft.name='Mug';app.characterId='original';app.characterDraft.id='original';app.characterDraft.revision=1;
 const original=JSON.parse(JSON.stringify(app.characterDraft));app.characterItems=[original];const target=app.appearanceId;
 app.characterDraft.description='Unsaved identity refinement';const saved=JSON.parse(JSON.stringify(original));saved.revision=2;saved.appearances[0].generated_images=[{asset_id:'img',artifact_id:'art',appearance_revision:1}];
 ctx.fetch=async()=>({ok:true,json:async()=>saved});app.historyHeaders=()=>({});app.runs=[{id:'run',miniAppId:'ai2apps.imagine.character-design',status:'succeeded',input:{characterDesignTarget:{character_id:'original',appearance_id:target}}}];
 await app.collectCharacterRuns();assert.equal(app.characterDraft.description,'Unsaved identity refinement');assert.equal(app.characterDraft.revision,2);assert.equal(app.characterDraft.appearances[0].generated_images[0].asset_id,'img');
 const revision=app.characterDraft.revision;await app.collectCharacterRuns();assert.equal(app.characterDraft.revision,revision);
});

test('new appearance is first menu option and creates a blank draft with cleared Slots',()=>{
 const{app}=editor();app.newCharacter();app.characterAppearance.style='old';app.referenceSlotCount=4;const cleared=[];app.clearReference=i=>cleared.push(i);
 app.selectCharacterAppearance('__new__');assert.equal(app.characterDraft.appearances.length,2);assert.equal(app.characterAppearance.style,'');assert.equal(app.characterAppearance.reference_ids.length,0);assert.deepEqual(cleared,[0,1,2,3]);
 const html=fs.readFileSync(__dirname+'/../web/templates/system_apps/_imagine_characters.html','utf8');assert.ok(html.indexOf('value="__new__"')<html.indexOf('x-for="a in characterDraft.appearances"'));
});
test('derivation clones settings but uses the current appearance generated sheet, never unrelated Output',async()=>{
 const{app}=editor();app.newCharacter();const source=app.characterAppearance;source.name='Daily';source.style='photo';source.summary='Existing guide';source.approved=true;source.generated_images=[{asset_id:'old',artifact_id:'a1'},{asset_id:'latest',artifact_id:'a2'}];
 app.activeArtifact={kind:'image',id:'unrelated',galleryAssetId:'wrong'};app.referenceSlotCount=4;const steps=[];app.clearReference=i=>steps.push('clear'+i);app.materializeAssetReference=async(ref,i)=>steps.push(ref.assetId+':'+i);
 await app.deriveCharacterAppearance();const derived=app.characterAppearance;assert.notEqual(derived.id,source.id);assert.equal(derived.style,'photo');assert.equal(derived.summary,'Existing guide');assert.equal(derived.reference_ids[0],'latest');assert.equal(derived.approved,false);assert.equal(derived.generated_images,undefined);assert.equal(source.approved,true);assert.equal(source.generated_images.length,2);assert.deepEqual(steps,['latest:0','clear1','clear2','clear3']);
 app.appearanceId=source.id;app.activeArtifact={kind:'image',id:'output',metadata:{workspaceArtifactId:'a1'}};assert.equal(app.characterDerivationImage.asset_id,'old');
});
test('failed reference loading does not create a derived appearance',async()=>{
 const{app}=editor();app.newCharacter();const source=app.characterAppearance;source.generated_images=[{asset_id:'missing'}];let error;app.fail=e=>error=e;app.materializeAssetReference=async()=>{throw Error('Unavailable')};
 await app.deriveCharacterAppearance();assert.equal(app.characterDraft.appearances.length,1);assert.equal(app.characterAppearance.id,source.id);assert.equal(app.characterDeriving,false);assert.match(error.message,/Unavailable/);
});

test('unlinking generated image keeps unsaved form edits and server revision',async()=>{
 const ctx={window:{},crypto:require('crypto').webcrypto};vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/imagine_characters.js','utf8'),ctx);
 const app=ctx.window.ImagineCharacters();app.locale='en';app.newCharacter();app.characterId='c1';app.characterDraft.name='Unsaved name';app.characterDraft.revision=5;app.historyHeaders=()=>({});app.success=()=>{};app.fail=e=>{throw e;};
 const a=app.characterAppearance;a.generated_images=[{artifact_id:'art'}];const saved={id:'c1',name:'Saved name',revision:6,appearances:[{...a,generated_images:[]}]};
 ctx.fetch=async(url,options)=>{assert.equal(options.method,'DELETE');assert.equal(JSON.parse(options.body).revision,5);return{ok:true,json:async()=>saved}};
 await app.removeGeneratedCharacterImage(a.generated_images[0]);assert.equal(app.characterDraft.name,'Unsaved name');assert.equal(app.characterDraft.revision,6);assert.equal(a.generated_images.length,0);assert.equal(app.characterBusy,false);
});

test('choosing a definition image preserves all input references and never writes input Slots',async()=>{
 const{app}=editor();app.newCharacter();const a=app.characterAppearance;a.reference_ids=['original-input'];a.summary='Guide';let saved=false;
 app.saveCharacter=async()=>{saved=true};app.materializeAssetReference=()=>{throw Error('Must not touch input Slots')};
 await app.useGeneratedCharacterImage({asset_id:'definition'});assert.equal(a.definition_image_id,'definition');assert.equal(a.reference_ids[0],'original-input');assert.ok(saved);
});
test('derivation prefers explicitly selected definition image over generated history',()=>{
 const{app}=editor();app.newCharacter();app.characterAppearance.definition_image_id='chosen';app.characterAppearance.generated_images=[{asset_id:'latest'}];assert.equal(app.characterDerivationImage.asset_id,'chosen');
});

test('switching appearances restores independent unsaved input files, including an empty appearance',async()=>{
 const{app}=editor();app.newCharacter();app.referenceSlotCount=2;app.referenceFiles=[{name:'A.png'},null];app.referenceAssets=[{assetId:'A'},null];
 app.clearReference=i=>{app.referenceFiles[i]=null;app.referenceAssets[i]=null};app.setReference=async(i,file,asset)=>{app.referenceFiles[i]=file;app.referenceAssets[i]=asset};
 const first=app.appearanceId;app.newAppearance();const second=app.appearanceId;assert.equal(app.referenceFiles[0],null);
 app.referenceFiles[0]={name:'B.png'};app.referenceAssets[0]={assetId:'B'};
 await app.selectCharacterAppearance(first);assert.equal(app.referenceFiles[0].name,'A.png');
 await app.selectCharacterAppearance(second);assert.equal(app.referenceFiles[0].name,'B.png');assert.equal(app.referenceAssets[0].assetId,'B');
});
test('persisted references load for selected appearance and saving binds only its own Slots',async()=>{
 const{app,calls}=editor();app.newCharacter();app.referenceSlotCount=2;app.referenceFiles=[null,null];app.referenceAssets=[null,null];app.clearReference=i=>{app.referenceFiles[i]=null;app.referenceAssets[i]=null};
 const first=app.appearanceId;app.characterAppearance.reference_ids=['saved-A'];app.newAppearance();const second=app.appearanceId;app.characterAppearance.reference_ids=['saved-B'];
 app.characterSlotCache={};app.appearanceId='';app.materializeAssetReference=async(ref,i)=>{app.referenceFiles[i]={name:ref.assetId};app.referenceAssets[i]=ref};
 await app.selectCharacterAppearance(first);assert.equal(app.referenceFiles[0].name,'saved-A');
 await app.selectCharacterAppearance(second);assert.equal(app.referenceFiles[0].name,'saved-B');
 app.referenceAssets[0]={assetId:'new-B'};app.characterDraft.name='Mug';await app.saveCharacter();const sent=JSON.parse(calls[0].options.body);
 assert.equal(sent.appearances.find(a=>a.id===first).reference_ids[0],'saved-A');assert.equal(sent.appearances.find(a=>a.id===second).reference_ids[0],'new-B');
});
test('collection tolerates key order and newly defaulted fields while preserving selected definition',()=>{
 const{app}=editor();app.newCharacter();app.characterId='c';app.characterDraft.id='c';app.characterDraft.revision=1;const a=app.characterAppearance;
 const base=JSON.parse(JSON.stringify(app.characterDraft));delete base.appearances[0].definition_image_id;
 a.definition_image_id='unsaved-choice';const saved=JSON.parse(JSON.stringify(base));saved.revision=2;
 saved.appearances[0]=Object.fromEntries(Object.entries({...saved.appearances[0],definition_image_id:'',generated_images:[{asset_id:'generated'}],revision:1}).reverse());
 app.mergeCharacterCollection(saved,base);assert.equal(app.characterDraft.revision,2);assert.equal(a.definition_image_id,'unsaved-choice');assert.equal(a.generated_images[0].asset_id,'generated');assert.equal(app.characterCollectError,'');
});
test('real concurrent text conflict does not silently advance revision or overwrite edits',()=>{
 const{app}=editor();app.newCharacter();app.characterId='c';app.characterDraft.id='c';app.characterDraft.revision=1;const base=JSON.parse(JSON.stringify(app.characterDraft));
 app.characterAppearance.summary='Local edit';const saved=JSON.parse(JSON.stringify(base));saved.revision=2;saved.appearances[0].summary='Different external edit';saved.appearances[0].generated_images=[{asset_id:'new'}];
 app.mergeCharacterCollection(saved,base);assert.equal(app.characterAppearance.summary,'Local edit');assert.equal(app.characterDraft.revision,1);assert.equal(app.characterAppearance.generated_images.length,1);assert.ok(app.characterCollectError);
});
test('save waits for pending image collection and submits its latest revision',async()=>{
 const calls=[];let complete;
 const ctx={window:{},crypto:require('crypto').webcrypto};vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/imagine_characters.js','utf8'),ctx);
 const app=ctx.window.ImagineCharacters();app.locale='en';app.currentMiniApp={adapter:'character-design'};app.newCharacter();app.characterDraft.name='Mug';app.characterId='c';app.characterDraft.id='c';app.characterDraft.revision=1;app.characterItems=[JSON.parse(JSON.stringify(app.characterDraft))];app.historyHeaders=()=>({});app.success=()=>{};app.fail=e=>{throw e};
 app.runs=[{id:'run',miniAppId:'ai2apps.imagine.character-design',status:'succeeded',input:{characterDesignTarget:{character_id:'c'}}}];
 ctx.fetch=async(url,options)=>{if(url.endsWith('/collect'))return await new Promise(resolve=>{complete=()=>{const saved=JSON.parse(JSON.stringify(app.characterItems[0]));saved.revision=2;saved.appearances[0].generated_images=[{asset_id:'new'}];resolve({ok:true,json:async()=>saved});};});calls.push(JSON.parse(options.body));return{ok:true,json:async()=>({...app.characterDraft,revision:3})};};
 const collecting=app.collectCharacterRuns(),saving=app.saveCharacter();assert.equal(calls.length,0);complete();await collecting;await saving;assert.equal(calls.length,1);assert.equal(calls[0].revision,2);assert.equal(app.characterDraft.revision,3);
});
test('readonly shared selector materializes one definition and guide, then invalidates on input replacement',async()=>{
 const {app}=editor();app.currentMiniApp={adapter:'sticker-workshop'};app.sharedCharacterId='c';app.sharedAppearanceId='a';app.referenceSlotCount=3;app.referenceAssets=[];
 app.loadSharedCharacterDefinitions=async()=>{app.characterSharedItems=[{id:'c',revision:2,appearances:[{id:'a',revision:1,definition_image_id:'def',summary:'Blue cape'}]}];return true;};
 const cleared=[];app.materializeAssetReference=async(ref,i)=>{assert.equal(i,0);app.referenceAssets[0]=ref;};app.clearReference=i=>cleared.push(i);
 await app.useSharedCharacterDefinition();assert.equal(app.characterReuseGuide(),'Blue cape');assert.deepEqual(cleared,[1,2]);
 app.referenceAssets[0]={assetId:'different'};assert.equal(app.characterReuseGuide(),'');
});
test('failed refresh cannot reuse stale shared appearance',async()=>{
 const {app}=editor();app.loadSharedCharacterDefinitions=async()=>false;app.materializeAssetReference=()=>assert.fail('stale material used');await app.useSharedCharacterDefinition();
});
test('sticker and regular drawing prompts include the selected reusable guide',()=>{
 const ctx={window:{},structuredClone,document:{documentElement:{lang:'zh'}}};vm.createContext(ctx);
 for(const file of ['imagine_characters.js','imagine_studio.js'])vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/'+file,'utf8'),ctx);
 const app=ctx.window.imagineStudioApp();app.miniAppId='ai2apps.imagine.sticker-workshop';app.characterReference={definitionImageId:'def',summary:'Unique blue cape guide'};app.referenceAssets=[{assetId:'def'}];
 assert.equal(app.composedPrompt().split('Unique blue cape guide').length,2);
 app.miniAppId='ai2apps.imagine.image-edit';assert.match(app.composedPrompt(),/Unique blue cape guide/);
});
test('character ASCBot binding captures portable drawing settings without character materials',async()=>{
 const defs=[];const ctx={window:{AI2AppsAppState:{register:d=>{defs.push(d);return {target:d.target,dispose(){}};},panel:()=>{}}}};vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/imagine_app_state.js','utf8'),ctx);
 const app={appInstanceId:()=> 'instance',miniApps:[],referenceFiles:[{private:true}],requestedSize:'1024x1024',parseSize:()=>({width:1024,height:1024}),modelId:'byok/model',style:'chibi',quality:'auto',format:'png'};
 ctx.window.AI2AppsImagineState.mount(app);const binding=defs.find(d=>d.target.mini_app_id==='ai2apps.imagine.character-design');assert(binding);
 const value=binding.capture();assert.equal(value.style_id,'chibi');assert.equal(value.model_id,'byok/model');assert.equal(value.referenceFiles,undefined);assert.equal(value.characterId,undefined);
});
test('character UI helpers switch Chinese and English labels',()=>{const {app}=editor();assert.match(app.characterProportionPresets[0],/头身/);app.locale='en';assert.match(app.characterProportionPresets[0],/heads tall/);});
