/* Bot voice preferences; synthesis stays in the existing speech/Voice Studio owners. */
(()=>{'use strict';
 const empty=()=>({mode:'default',model_id:null,voice:null,profile_id:null,revision:0});
 async function request(path,options={}){const response=await fetch(path,{credentials:'same-origin',...options});if(!response.ok){let value={};try{value=await response.json();}catch(_){}throw Error(value.detail?.message||value.detail||value.error?.message||'Voice settings unavailable');}return response.json();}
 async function catalog(signal){const results=await Promise.allSettled([request('/admin/api/models',{signal}),request('/v1/platform/readaloud/voice-profiles',{signal})]);
  const models=results[0].status==='fulfilled'?(results[0].value.models||[]).filter(m=>{const t=m.audio_capabilities?.tts||{};return m.model_type==='audio_tts'&&m.checkpoint_ready!==false&&!m.is_hidden&&!m.load_failed&&(!(m.source_type==='package'||m.engine_type==='package')||m.checkpoint_ready===true)&&!t.instructions?.required&&(!t.voice_profiles?.reference_audio||t.named_voices?.voices?.length);}).map(m=>({id:m.id,name:m.display_name||m.name||m.id,voices:m.audio_capabilities?.tts?.named_voices?.voices||[]})):[];
  const profiles=results[1].status==='fulfilled'?(results[1].value.items||[]):[];return {models,profiles,error:results.some(r=>r.status==='rejected')?'catalog_incomplete':''};
 }
 const path=id=>'/v1/platform/messager/bots/'+encodeURIComponent(id)+'/voice';
 async function resolve(id,signal,{defaultSpeech}={}){
  const plan=await request(path(id)+'/playback',{signal});let index=0,synth=null;
  const words=(cn,en)=>(document.documentElement.lang||'').startsWith('zh')?cn:en;
  async function prepare(settings){
   if(settings.mode==='default'){
    const ready=await window.AI2AppsCapabilities?.probe?.(setupRequest('speech_generation'));
    if(signal?.aborted)throw new DOMException('Aborted','AbortError');
    return defaultSpeech({modelId:ready?.status==='ready'?ready.provider?.modelId:null,useDefaultVoice:true});
   }
   if(settings.mode==='model')return (text,signal)=>fetch('/v1/audio/speech',{method:'POST',credentials:'same-origin',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({model:settings.model_id,input:text,response_format:'wav',...(settings.voice?{voice:settings.voice}:{})})});
   const profiles=await request('/v1/platform/readaloud/voice-profiles',{signal}),profile=(profiles.items||[]).find(p=>p.id===settings.profile_id);
   if(!profile||profile.status!=='ready')throw Error('Voice Studio character is unavailable');
   return (text,signal)=>fetch('/v1/platform/readaloud/quick-read',{method:'POST',credentials:'same-origin',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({text,model_id:profile.modelId||profile.model_id,voice_profile_id:profile.id})});
  }
  const read=async(text,signal)=>{
   while(index<plan.candidates.length){const candidate=plan.candidates[index];
    if(!synth){try{synth=await prepare(candidate.settings);}catch(error){if(error.name==='AbortError')throw error;if(index+1>=plan.candidates.length)throw error;index++;continue;}}
    const response=await synth(text,signal);
    if(!response.ok&&[400,404,409,422,503].includes(response.status)&&index+1<plan.candidates.length){index++;synth=null;continue;}
    if(response.ok){if(candidate.source!=='selected'||index>0)read.notice=words(candidate.source==='previous'?'当前声音不可用，已使用上一次成功朗读的设置。':'当前声音不可用，已使用默认朗读设置。',candidate.source==='previous'?'Using the last working voice because the selected voice is unavailable.':'Using the default voice because the selected voice is unavailable.');
     if(candidate.source==='selected'&&candidate.settings.mode!=='default')request(path(id)+'/used',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:candidate.settings.revision})}).catch(()=>{});
    }return response;
   }throw Error('No speech configuration is available');
  };return read;
 }
 const words=(cn,en)=>(document.documentElement.lang||'').startsWith('zh')?cn:en;
 function setupRequest(operation){return {appId:'ai2apps.messager',capability:'audio.'+operation,actionId:operation==='speech_recognition'?'configure-bot-recognition':'configure-bot-speech',requirements:{operations:[operation]},intent:{returnTo:'/apps/ai2apps.messager',resumeToken:crypto.randomUUID(),completionPolicy:'configure_only'}};}
 async function install(operation='speech_generation',{installMore=true}={}){
  if(!window.AI2AppsCapabilities?.ensure)throw Error(words('能力配置暂时不可用，请重新打开 Messager。','Capability setup is unavailable. Reopen Messager.'));
  const result=await window.AI2AppsCapabilities.ensure(setupRequest(operation),{installMore});
  if(result?.session?.id)await window.AI2AppsCapabilities.acknowledge(result.session,{appId:'ai2apps.messager'});return result;
 }
 function offerSetup({notice,operation,error,isCurrent=()=>true,onConfigured}){
  const recognition=operation==='speech_recognition';notice.replaceChildren();
  const message=document.createElement('span');message.textContent=words(recognition?'语音识别未完成。可配置或安装所需的 Runtime、模型等 Package。':'朗读未完成。可配置或安装所需的 Runtime、模型等 Package。',recognition?'Speech recognition did not finish. Configure or install the required Runtime and model Packages.':'Read aloud did not finish. Configure or install the required Runtime and model Packages.');notice.append(message);
  const button=document.createElement('button');button.type='button';button.className='messager-button';button.textContent=words('配置语音能力','Set up speech');notice.append(button);
  const details=document.createElement('details'),summary=document.createElement('summary'),detail=document.createElement('pre');summary.textContent=words('错误详情','Error details');detail.textContent=String(error?.message||error||'');details.append(summary,detail);notice.append(details);
  button.onclick=async()=>{if(button.disabled||!isCurrent())return;button.disabled=true;try{const result=await install(operation,{installMore:false});if(!isCurrent())return;
   if(result?.outcome==='configured'||result?.outcome==='already_ready'){await onConfigured?.(result);if(isCurrent()){message.textContent=words('配置已完成，请重试。','Setup completed. Please retry.');button.remove();details.remove();}}
  }catch(e){if(isCurrent())message.textContent=words('配置未完成：','Setup did not finish: ')+(e.message||String(e));}finally{if(isCurrent())button.disabled=false;}};
 }

 window.AI2AppsBotVoice={empty,catalog,resolve,install,offerSetup,load:id=>request(path(id)),save:(id,value)=>request(path(id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(value)})};
})();
