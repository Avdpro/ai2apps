/* Imagine-owned configuration adapter shared by presets and Agent continuations. */
(()=>{
 'use strict';
 const APP='ai2apps.imagine-studio',MINI='ai2apps.imagine.style-transfer';
 const PACKAGE_STATE = {
  'ai2apps.imagine.comic-studio': 'ai2apps:comic-studio-state/v1',
  'ai2apps.imagine.fantasy-feed': 'ai2apps:fantasy-feed-state/v1',
  'ai2apps.imagine.comic-translation': 'ai2apps:comic-translation-state/v1',
 };
 const MINIS=[MINI,'ai2apps.imagine.text-to-image','ai2apps.imagine.image-edit','ai2apps.imagine.reference-creation','ai2apps.imagine.group-photo','ai2apps.imagine.extract-items','ai2apps.imagine.try-on','ai2apps.imagine.product-poster','ai2apps.imagine.character-design'];
 const copy=v=>v===undefined?undefined:JSON.parse(JSON.stringify(v));
 function mount(app){
  const sdk=window.AI2AppsAppState,instanceId=app.appInstanceId();if(!sdk||!instanceId)return null;
  const root=app.$root,files=new WeakMap();let fileId=0,pending=null;
  const revision=()=>JSON.stringify({mini:app.miniAppId,draft:app.draftPayload(),layout:[app.leftView,app.leftCollapsed,app.rightCollapsed],busy:app.generating||app.stickerBatchBusy,files:app.referenceFiles.map(f=>{if(!f)return null;if(!files.has(f))files.set(f,++fileId);return files.get(f);})});
  const busy=value=>{if(root)root.inert=value;};
  const main=sdk.register({target:{app_id:APP,mini_app_id:null,contract_version:1},instanceId,revision,
   capture:()=>({left_panel:app.leftView==='assets'?'assets':'mini-apps',left_collapsed:app.leftCollapsed,right_collapsed:app.rightCollapsed}),
   dirty:()=>false,validate(){if(app.generating||app.stickerBatchBusy)throw Error('Wait for the active operation before restoring layout');},
   async apply(v){app.leftView=v.left_panel;app.leftCollapsed=v.left_collapsed;app.rightCollapsed=v.right_collapsed;await app.$nextTick();app.persistPreferences();},setBusy:busy});
  const capture=()=>{const dimensions=app.parseSize(app.requestedSize);if(!dimensions&&app.requestedSize!=='auto')throw Error('Choose a valid canvas size before saving a preset');return {model_id:app.modelId,style_id:app.style||'',width:dimensions?.width??null,height:dimensions?.height??null,quality:app.quality,format:app.format};};
  function validate(v,mini){
   if(app.miniAppId!==mini||app.packageMiniAppId||!app.miniApps?.some(m=>m.id===mini&&m.status==='ready'&&m.source!=='package'))throw Error('Open the requested built-in Mini-App first');
   const continuation=pending?.target.mini_app_id===mini;
   if(app.generating||app.stickerBatchBusy||(!continuation&&(app.parameterHandoff||app.parameterHandoffLoading)))throw Error('Wait for the active operation before restoring settings');
   const model=app.compatibleModels.find(m=>m.id===v.model_id);
   if(!model||model.load_failed||model.checkpointReady===false)throw Object.assign(Error('Model '+v.model_id+' is unavailable. Configure that model first; no substitute will be selected.'),{code:'dependency_unavailable'});
   if(mini===MINI&&v.style_id&&!app.allStyles.some(s=>s.id===v.style_id))throw Error('The selected style is unavailable');
   if(!(model.qualities||['auto']).includes(v.quality)||!(model.formats||['png']).includes(v.format))throw Error('Model does not support the selected quality or format');
   if((v.width===null)!==(v.height===null))throw Error('Both canvas dimensions must be specified together');
   const canvas=v.width===null?'auto':v.width+'x'+v.height;
   if(!model.sizeCapability)throw Error('Model size configuration is unavailable');
   if(canvas!=='auto'&&(!model.sizeCapability?.width||!model.sizeCapability?.height))throw Error('Model size configuration is unavailable');
   const invalid=app.validateSize.call({sizeCapability:model.sizeCapability,flexibleSizes:model.source==='local'||model.sizeCapability.mode==='bounded-custom',parseSize:app.parseSize.bind(app),tr:app.tr.bind(app),locale:app.locale},canvas);
   if(invalid)throw Error(invalid);
  }
  // This is the only assignment/rollback implementation for image settings.
  async function apply(v,mini){
   validate(v,mini);
   const keys=['modelId','modelSelectionMode','style','size','customWidth','customHeight','quality','format','sizeCapability','flexibleSizes','pricingVersion'];
   const old=Object.fromEntries(keys.map(k=>[k,copy(app[k])]));
   const privateKeys=['prompt','groupBackgroundDescription','groupAtmosphere','groupPose','parameterHandoffDraftId','extractTarget','extractCustom','tryOnInteraction','tryOnPose','tryOnPoseText','tryOnBackground','tryOnBackgroundText','productScene','productSceneDescription','productLight','productComposition','productUseStyle','productSettingStyle'];
   const priorPrivate=Object.fromEntries(privateKeys.map(k=>[k,app[k]]));
   const materialKeys=['referenceFiles','referencePreviews','referenceAssets','referenceDimensions'];
   const priorMaterials=Object.fromEntries(materialKeys.map(k=>[k,app[k]]));
   let committed=false;app.appStateRestoring=true;
   try{
    if(pending){
     // Resources remain inside the original authenticated continuation, never in App-State packets.
     for(const k of materialKeys)app[k]=[];
     for(const ref of pending.parameters.references||[])await app.materializeAssetReference({workspaceArtifactId:ref.artifact_id,workspaceSessionId:ref.session_id,name:ref.name},ref.slot,true);
     const values=pending.parameters.values;
     app.prompt=values.prompt||'';app.groupBackgroundDescription=values.background||'';
     if(mini==='ai2apps.imagine.extract-items')Object.assign(app,{extractTarget:values.target||'outfit',extractCustom:values.target_description||''});
     if(mini==='ai2apps.imagine.try-on')Object.assign(app,{tryOnInteraction:values.interaction||'wear',tryOnPose:values.pose||'keep',tryOnPoseText:values.pose_description||'',tryOnBackground:values.background||'keep',tryOnBackgroundText:values.background_description||''});
     if(mini==='ai2apps.imagine.product-poster')Object.assign(app,{productScene:values.scene||'white',productSceneDescription:values.scene_description||'',productLight:values.lighting||'soft',productComposition:values.composition||'center',productUseStyle:false,productSettingStyle:values.setting_style||''});
     app.groupAtmosphere=values.atmosphere||app.groupAtmosphere;app.groupPose=values.pose||app.groupPose;
    }
    const m=app.compatibleModels.find(m=>m.id===v.model_id);
    Object.assign(app,{modelId:v.model_id,modelSelectionMode:'explicit',style:v.style_id,size:v.width===null?'auto':v.width+'x'+v.height,customWidth:v.width??app.customWidth,customHeight:v.height??app.customHeight,quality:v.quality,format:v.format,sizeCapability:copy(m.sizeCapability),flexibleSizes:m.source==='local'||m.sizeCapability.mode==='bounded-custom',pricingVersion:String(m.pricingVersion||'')});
    await app.$nextTick();
    const actual=capture();if(Object.keys(v).some(k=>actual[k]!==v[k]))throw Error('Settings could not be restored exactly');
    if(pending)app.parameterHandoffDraftId=pending.interaction_id;
    app.persistPreferences();app.scheduleDraftSave();committed=true;
   }catch(e){
    if(pending){for(const url of app.referencePreviews||[])if(url)URL.revokeObjectURL(url);Object.assign(app,priorPrivate,priorMaterials);}
    Object.assign(app,old);await app.$nextTick();throw e;
   }finally{
    if(committed&&pending)for(const url of priorMaterials.referencePreviews||[])if(url)URL.revokeObjectURL(url);
    app.appStateRestoring=false;app.scheduleDraftSave();
   }
  }
  let initial='';try{initial=JSON.stringify(capture());}catch{}
  const bindings=new Map(MINIS.map(mini=>[mini,sdk.register({target:{app_id:APP,mini_app_id:mini,contract_version:1},instanceId,revision,capture,
   activate:async()=>{if(app.generating||app.stickerBatchBusy||app.parameterHandoff)throw Error('Finish the active operation first');if(app.miniAppId!==mini)await app.selectMiniApp(mini);},configureDependencies:()=>app.configureLocalModel(true),
   validate:v=>validate(v,mini),apply:v=>apply(v,mini),needsApply:()=>Boolean(pending),
   dirty:()=>Boolean(app.prompt?.trim()||app.referenceFiles.some(Boolean)||JSON.stringify(capture())!==initial),setBusy:busy})]));
  const activatePackages = new Map();
  for (const [id, type] of Object.entries(PACKAGE_STATE)) {
   const available = () => app.miniApps.some(item => item.id === id && item.source === 'package');
   if (!available()) continue;
   let snapshot = null;
   function currentFrame() {
    const frame = app.$refs.packageMiniApp;
    if (app.miniAppId !== id || app.packageMiniAppId !== id || !frame?.contentWindow || !app.packageMiniAppMountId) return null;
    const expected = new URL(app.packageMiniAppUrl, location.origin);
    return expected.origin === location.origin && expected.href === frame.src &&
     expected.searchParams.get('mount_id') === app.packageMiniAppMountId ? frame : null;
   }
   function request(action, values) {
    const frame = currentFrame();
    if (!frame) throw Error('The Mini-App is not mounted');
    const target = frame.contentWindow, src = frame.src;
    return new Promise((resolve, reject) => {
     const channel = new MessageChannel();
     const finish = (error, state) => {
      clearTimeout(timeout);
      frame.removeEventListener('load', changed);
      channel.port1.close();
      if (error) reject(error); else resolve(state);
     };
     const changed = () => finish(Error('Mini-App mount changed'));
     const timeout = setTimeout(() => finish(Error('Mini-App did not respond')), action === 'capture' ? 700 : 5000);
     frame.addEventListener('load', changed, {once: true});
     channel.port1.onmessage = ({data}) => {
      const state = data?.state;
      if (currentFrame() !== frame || frame.src !== src || frame.contentWindow !== target) return changed();
      if (data?.error || !Number.isInteger(state?.revision) || !state.values || typeof state.busy !== 'boolean')
       return finish(Error(data?.error || 'Invalid Mini-App settings response'));
      finish(null, state);
     };
     target.postMessage({type, action, values, instance: snapshot?.instance, revision: snapshot?.revision}, '*', [channel.port2]);
    });
   }
   async function activate() {
    if (!available()) throw Error('The Mini-App is unavailable');
    if (app.generating || app.stickerBatchBusy || app.parameterHandoff) throw Error('Finish the active operation first');
    if (app.miniAppId !== id) await app.selectMiniApp(id);
    for (let attempt = 0; attempt < 8; attempt++) {
     try { snapshot = await request('capture'); return; }
     catch (error) { if (attempt === 7) throw error; await new Promise(resolve => setTimeout(resolve, 125)); }
    }
   }
   activatePackages.set(id, activate);
   bindings.set(id, sdk.register({
    target: {app_id: APP, mini_app_id: id, contract_version: 1}, instanceId, activate,
    capture: () => snapshot?.values,
    revision: () => JSON.stringify([app.packageMiniAppMountId, snapshot?.revision]),
    dirty: () => snapshot?.dirty ?? Boolean(snapshot?.revision),
    validate() {
     if (!currentFrame() || !snapshot || snapshot.busy) throw Error('Open the Mini-App and finish the active operation first');
    },
    async apply(values) { snapshot = await request('apply', values); },
   }));
  }
  async function continueHandoff(handoff,{confirmConflict=()=>sdk.confirmConflict({message:(document.documentElement.lang||'').startsWith('zh')?'当前目标页面有编辑内容。继续会替换设置、文字和素材；不会启动任务。原 Agent 任务仍等待你在 App 中执行。':'The target page has edits. Continuing replaces settings, text and materials. No task starts; the original Agent waits for you to execute in the App.'})}={}){
   if(pending)throw Error('Another configuration handoff is pending');
   const binding=bindings.get(handoff.target.mini_app_id);if(!binding)throw Error('This Mini-App has no shared App-State adapter');
   if(handoff.target.app_id!==APP||handoff.status!=='pending'||!handoff.interaction_id)throw Error('Invalid App continuation');
   const values=handoff.parameters.values;
   const model=app.compatibleModels.find(m=>m.id===(values.model||app.modelId)||Boolean(values.model&&app.canonicalHandoffModelId&&m.id===app.canonicalHandoffModelId(values.model)));
   if(!model)throw Error('The selected model is unavailable. Configure that model first; no substitute will be selected.');
   const size=values.size||model.sizeCapability?.default||app.requestedSize,dimensions=app.parseSize(size);
   if(!dimensions&&size!=='auto')throw Error('The transferred canvas size is invalid');
   const packet={schema:'ai2apps.app-state/v1',target:binding.target,values:{model_id:model.id,style_id:values.style??app.style??'',width:dimensions?.width??null,height:dimensions?.height??null,quality:values.quality??'auto',format:values.format??'png'}};
   pending=handoff;
   try{return await binding.restore(packet,{requestId:'handoff-'+handoff.interaction_id+'-'+crypto.randomUUID(),confirmConflict});}finally{pending=null;}
  }
  return {main,style:bindings.get(MINI),continueHandoff,
   available:()=>!app.packageMiniAppId || bindings.has(app.packageMiniAppId),
   async open(){
    const binding=bindings.get(app.miniAppId)||main;
    await activatePackages.get(app.miniAppId)?.();
    return sdk.panel(binding);
   },
   dispose(){main.dispose();for(const b of bindings.values())b.dispose();}};
 }
 window.AI2AppsImagineState=Object.freeze({mount});
})();
