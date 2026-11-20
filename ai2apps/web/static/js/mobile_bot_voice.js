/* Mobile adapter: shared Bot speech UI, bounded scoped media, no task authority. */
(()=>{'use strict';
 let reader=null,liveOutput=null;
 function resetRead(button,label){button.setAttribute('aria-pressed','false');button.removeAttribute('aria-busy');button.textContent=label('读出','Read aloud');}
 function stopRead(){if(!reader)return;const previous=reader;reader=null;previous.control.abort();resetRead(previous.button,previous.label);}
 async function readReply({botId,sessionId,text,button,label,onError,onSetup}){
  if(reader?.button===button){stopRead();return;}
  if(liveOutput?.busy()){onError(Error(label('请先结束录音再读出','Finish recording before reading aloud')));return;}
  stopRead();liveOutput?.interrupt();
  const state={control:new AbortController(),button,label};reader=state;const signal=state.control.signal;
  button.textContent=label('停止读出','Stop reading');button.setAttribute('aria-pressed','true');button.setAttribute('aria-busy','true');
  try{
   const cleaned=window.AI2AppsStreamingTTS.cleanSpeechText(text);if(!cleaned)throw Error(label('这条回复没有可朗读文字','This reply has no text to read'));
   if(cleaned.length>12000)throw Error(label('回复太长，请选择较短的回复读出','This reply is too long to read aloud'));
   const segmenter=new window.AI2AppsStreamingTTS.StreamingTextSegmenter(),segments=[...segmenter.append(cleaned),...segmenter.finish()];
   await window.AI2AppsStreamingTTS.playSegments({segments,signal,maxPrepared:1,synthesize:async part=>{
    const response=await fetch('/v1/platform/messager-mobile/bots/'+encodeURIComponent(botId)+'/voice/read',{method:'POST',credentials:'same-origin',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:sessionId,text:part})});
    if(!response.ok){const error=await response.json().catch(()=>({}));const failure=Error(error.detail||error.error?.message||label('读出失败','Reading failed'));failure.status=response.status;throw failure;}return response.blob();
   },play:blob=>new Promise((resolve,reject)=>{
    if(signal.aborted){resolve();return;}const url=URL.createObjectURL(blob),audio=new Audio(url);let done=false;
    const end=error=>{if(done)return;done=true;audio.pause();audio.onended=null;audio.onerror=null;signal.removeEventListener('abort',abort);URL.revokeObjectURL(url);if(error)reject(error);else resolve();};
    const abort=()=>end();signal.addEventListener('abort',abort,{once:true});audio.onended=()=>end();audio.onerror=()=>end(Error(label('音频播放失败','Audio playback failed')));button.removeAttribute('aria-busy');audio.play().catch(end);
   })});
  }catch(error){if(!signal.aborted){onError(error);if(error.status===409&&onSetup)try{await onSetup();}catch(setupError){onError(setupError);}}}
  finally{if(reader===state){reader=null;resetRead(button,label);}}
 }
 window.addEventListener('pagehide',stopRead);document.addEventListener('visibilitychange',()=>{if(document.hidden)stopRead();});
 function create({botId,sessionId,form,input,controls,attach,poke,send,api,getModel,isBusy,getFiles,removeFiles,onAccepted,label,onError,onSetup}){
  let disposed=false,recording=false,processing=false,realtime=false,recorder=null,recordEpoch=0,recordingBody=null,recordAbort=null;
  const mic=document.createElement('button');mic.type='button';mic.className='mm-icon mm-voice-input';mic.textContent='♩';mic.setAttribute('aria-label',label('语音输入','Voice input'));mic.title=mic.getAttribute('aria-label');controls.insertBefore(mic,poke);
  const notice=document.createElement('div');notice.className='mm-voice-notice';notice.setAttribute('role','status');form.append(notice);
  let row,column,panel,modeButton;
  function render(){send.disabled=isBusy()||recording||processing;mic.disabled=disposed||realtime||processing||isBusy();mic.setAttribute('aria-pressed',String(recording));if(recording)mic.textContent='■';else mic.innerHTML='<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/></svg>';mic.setAttribute('aria-label',recording?label('停止录音','Stop recording'):label('语音输入','Voice input'));}
  async function transcribe(blob,{session,controller,signal}={}){
   if(blob.size>4*1024*1024)throw Error(label('录音不能超过4 MiB','Recording must be under 4 MiB'));
   const data=new FormData();data.append('file',blob,'speech.'+(blob.type.includes('mp4')?'m4a':blob.type.includes('wav')?'wav':blob.type.includes('ogg')?'ogg':'webm'));data.append('session_id',sessionId);if(session){data.append('voice_id',session.id);data.append('controller',controller);}
   const response=await fetch('/v1/platform/messager-mobile/bots/'+encodeURIComponent(botId)+'/voice/transcriptions',{method:'POST',body:data,signal,credentials:'same-origin'});const result=await response.json();if(!response.ok)throw Error(result.detail||result.error?.message||'Transcription failed');return result;
  }
  async function recognize(blob,e){processing=true;recordAbort=new AbortController();render();try{const result=await transcribe(blob,{signal:recordAbort.signal});if(disposed||e!==recordEpoch)return;if(!result.text?.trim())throw Error(label('未识别到文字','No speech recognized'));const value=input.value+(input.value.trim()?' ':'')+result.text;if(value.length>input.maxLength)throw Error(label('草稿过长，请精简后重试录音','Draft is too long. Shorten it and retry the recording'));input.value=value;input.dispatchEvent(new Event('input'));recordingBody=null;notice.replaceChildren();}
   catch(error){if(disposed||e!==recordEpoch)return;notice.textContent=error.message;const retry=document.createElement('button');retry.type='button';retry.textContent=label('重试录音','Retry recording');retry.onclick=()=>{if(!processing&&recordingBody)void recognize(recordingBody,recordEpoch);};notice.append(retry);}
   finally{if(e===recordEpoch){processing=false;recordAbort=null;render();}}
  }
  mic.onclick=async()=>{stopRead();if(disposed||processing||realtime||isBusy())return;if(recording){await recorder.stop();return;}const e=++recordEpoch;processing=true;render();try{
   const device=new window.AI2AppsStudioAudioRecorder();recorder=device;await device.start(30);if(disposed||e!==recordEpoch){device.dispose();return;}recording=true;processing=false;notice.textContent=label('正在录音，点击停止；最长30秒','Recording; tap to stop, up to 30 seconds');render();const result=await device.result;device.dispose();if(recorder===device)recorder=null;
   if(disposed||e!==recordEpoch)return;recording=false;if(result.error)throw Error(result.error);recordingBody=result.body;await recognize(result.body,e);
  }catch(error){if(!disposed&&e===recordEpoch){recording=false;processing=false;recorder?.dispose();recorder=null;onError(error);render();}}};
  const composer={canStartRealtime:()=>{stopRead();return !recording&&!processing&&!isBusy();},setRealtimeActive(v){realtime=v;render();},
   hasFiles:()=>getFiles().length>0,ids:()=>getFiles().map(f=>f.id),blocked:()=>isBusy(),removeIds:removeFiles,
   captureAttachments(){const selected=getFiles().slice();return ()=>{if(selected.some(f=>!getFiles().includes(f)))throw Error(label('附件选择已改变','Attachment selection changed'));return isBusy()?null:selected.map(f=>f.id);};},
   mountRealtime(button,voicePanel){modeButton=button;panel=voicePanel;button.classList.add('mm-icon');button.innerHTML='<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.7a2 2 0 0 1-.4 2.1L8.1 9.8a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.8.3 1.7.6 2.7.7a2 2 0 0 1 1.8 2.1z"/></svg>';controls.insertBefore(button,mic.nextSibling);row=document.createElement('div');row.className='mm-voice-row';column=document.createElement('div');column.className='mm-voice-column';form.insertBefore(row,input);column.append(input,controls);row.append(column,panel);},
  };
  const voice=window.AI2AppsBotRealtime.create({botId,sessionId,form,composer,getModel,label,onError,onAccepted,onSetup,
   request:(path,method='GET',body)=>api(path.replace('/messager/bots/','/bots/'),method,body),media:{transcribe,onSpeechStart:stopRead,
    close:(session,controller)=>api('/bots/'+botId+'/realtime/sessions/'+session.id+'/close','POST',{controller}),
    async synthesize(text,{session,controller,signal}){stopRead();const response=await fetch('/v1/platform/messager-mobile/bots/'+encodeURIComponent(botId)+'/voice/speech',{method:'POST',credentials:'same-origin',signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({session_id:sessionId,voice_id:session.id,controller,text})});if(!response.ok)throw Error(label('播报失败，请查看文字','Playback failed; read the reply'));return response.blob();},
   }});
  const output={interrupt:voice.interrupt,busy:()=>recording||processing};liveOutput=output;
  function stopRecording(){recordEpoch++;recordAbort?.abort();recorder?.dispose();recorder=null;recording=false;processing=false;recordingBody=null;render();}
  const hidden=()=>{if(document.hidden){stopRecording();void voice.stop();}};document.addEventListener('visibilitychange',hidden);
  async function settings(host){const [config,catalog]=await Promise.all([api('/bots/'+botId+'/realtime/settings'),api('/bots/'+botId+'/voice/catalog')]);if(disposed)return;
   const hint=document.createElement('p');hint.textContent=label('语音在手机采集，由Desktop模型处理。安装模型请在Desktop完成。','Audio is captured on this phone and processed by Desktop models. Install models on Desktop.');host.append(hint);
   const stt=document.createElement('select'),tts=document.createElement('select'),named=document.createElement('select');
   for(const [select,title,choices,selected] of [[stt,label('识别模型','Recognition model'),catalog.stt||[],config.stt_model_id],[tts,label('对话声音模型','Conversation voice model'),catalog.tts||[],config.tts_model_id]]){const wrapper=document.createElement('label');wrapper.textContent=title;select.setAttribute('aria-label',title);select.add(new Option(select===tts?label('仅输入，不读出','Input only (no readout)'):label('不使用语音输入','No voice input'),''));for(const m of choices)select.add(new Option(m.name,m.id));select.value=selected||'';wrapper.append(select);host.append(wrapper);}
   function voices(){named.hidden=!tts.value;named.replaceChildren();const available=(catalog.tts||[]).find(m=>m.id===tts.value)?.voices||[];if(!available.length)named.add(new Option(label('模型默认音色','Model default voice'),''));for(const v of available)named.add(new Option(v,v));}voices();if(config.voice)named.value=config.voice;tts.onchange=voices;named.setAttribute('aria-label',label('音色','Voice'));host.append(named);
   const save=document.createElement('button');save.type='button';save.textContent=label('应用实时对话设置','Apply conversation settings');save.onclick=async()=>{save.disabled=true;try{if(recording||processing)throw Error(label('请先结束录音','Finish recording first'));await voice.stop();const profile=config.profile_id&&tts.value===config.tts_model_id&&(named.value||null)===(config.voice||null)?config.profile_id:null;const value=await api('/bots/'+botId+'/realtime/settings','PUT',{stt_model_id:stt.value||null,tts_model_id:tts.value||null,voice:!tts.value||profile?null:named.value||null,profile_id:profile,revision:config.revision});Object.assign(config,value);await voice.refresh();hint.textContent=value.ready?label('已保存，返回对话后可开启。','Saved. Return to the conversation to start.'):label('读出设置已保存；使用语音输入还需选择识别模型。','Readout saved; select a recognition model for voice input.');}catch(error){onError(error);}finally{save.disabled=false;}};host.append(save);
  }
  render();return {blocked:()=>recording||processing,messages:voice.messages,observe:voice.observe,sync(){render();voice.sync();},settings,stop(){stopRecording();return voice.stop();},
   dispose(){if(disposed)return;disposed=true;stopRead();if(liveOutput===output)liveOutput=null;stopRecording();voice.dispose();document.removeEventListener('visibilitychange',hidden);if(row){form.insertBefore(input,row);form.insertBefore(controls,row);row.remove();}mic.remove();modeButton?.remove();notice.remove();},};
 }
 window.AI2AppsMobileBotVoice={create,readReply,stopRead};
})();
