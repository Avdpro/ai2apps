/* Chat-style Bot input: selected session material and editable speech transcription. */
(() => {
 'use strict';
 function create({form,input,send,cancel,sessionId,models,label,onError,onChange,dropTarget=form,inputPolicy={},onPoke=null}){
  let disposed=false,busy=false,pokeBusy=false,starting=false,recording=false,transcribing=false,entries=[],recorder=null,pendingAudio=null,voiceEpoch=0,realtimeActive=false;
  const fileInput=document.createElement('input');fileInput.type='file';fileInput.multiple=true;fileInput.hidden=true;
  fileInput.accept='';
  const previews=document.createElement('div');previews.className='bot-attachment-previews';
  const controls=document.createElement('div');controls.className='bot-composer-controls';
  function icon(name,title){const b=document.createElement('button');b.type='button';b.title=title;b.setAttribute('aria-label',title);b.className='bot-composer-icon';
   b.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+name+'</svg>';return b;}
  const attach=icon('<path d="m21 11-8 8a6 6 0 0 1-8-8l9-9a4 4 0 0 1 6 6l-9 9a2 2 0 0 1-3-3l8-8"/>',label('添加附件','Add attachments'));
  const mic=icon('<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3m-4 0h8"/>',label('语音输入','Voice input'));
  const poke=onPoke?icon('<path d="M9 12V4a2 2 0 0 1 4 0v7m0-2a2 2 0 0 1 4 0v3m0-1a2 2 0 0 1 4 0v4c0 4-3 7-7 7h-2c-2 0-3-1-4-3l-4-6a2 2 0 0 1 3-2l2 2"/>',label('唤醒 Bot','Poke Bot')):null;
  if(poke)poke.onclick=()=>{if(!busy&&!pokeBusy&&!starting&&!recording&&!transcribing)void onPoke();};
  const speechModel=document.createElement('select');speechModel.className='bot-speech-model';speechModel.title=label('语音识别模型','Speech recognition model');speechModel.setAttribute('aria-label',speechModel.title);
  let saved='';try{saved=JSON.parse(localStorage.getItem('ai2apps-chat-audio-v1')||'{}').sttModel||'';}catch(_){}
  function setModels(items){
   const current=speechModel.value||saved;
   const stt=items.filter(m=>(m.model_type==='audio_stt'||m.type==='audio_stt')&&m.checkpoint_ready!==false&&!m.is_hidden&&!m.load_failed);
   speechModel.replaceChildren();speechModel.value='';
   for(const m of stt)speechModel.add(new Option(m.name||m.id,m.id));
   if(stt.some(m=>m.id===current))speechModel.value=current;
   speechModel.hidden=inputPolicy.voice===false||stt.length<2;
  }
  setModels(models);
  const spacer=document.createElement('span');spacer.className='bot-composer-spacer';
  send.classList.add('bot-send-icon');send.title=label('发送','Send');send.setAttribute('aria-label',send.title);send.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="m5 12 7-7 7 7M12 5v15"/></svg>';
  const voiceNotice=document.createElement('div');voiceNotice.className='chat-mini-message-notice';voiceNotice.setAttribute('role','status');
  controls.append(attach,mic);if(poke)controls.append(poke);controls.append(speechModel,spacer,cancel,send);form.replaceChildren(previews,input,controls,voiceNotice,fileInput);
  async function request(url,options){const r=await fetch(url,{credentials:'same-origin',...options});const v=await r.json().catch(()=>({}));if(!r.ok){const error=Error(v.error?.message||v.detail?.message||v.detail||'Request failed');error.status=r.status;throw error;}return v;}
  function render(){previews.replaceChildren();for(const entry of entries){const chip=document.createElement('div');chip.className='bot-attachment-chip';
    if(entry.url){const img=document.createElement('img');img.src=entry.url;img.alt='';chip.append(img);}
    const name=document.createElement('span');name.textContent=entry.file.name+(entry.pending?label(' · 上传中',' · Uploading'):entry.error?label(' · 失败',' · Failed'):'');chip.append(name);
    const remove=document.createElement('button');remove.type='button';remove.title=label('移除附件','Remove attachment');remove.setAttribute('aria-label',remove.title+' '+entry.file.name);remove.textContent='×';remove.disabled=busy;
    remove.onclick=()=>{entries=entries.filter(e=>e!==entry);if(entry.url)URL.revokeObjectURL(entry.url);render();};chip.append(remove);previews.append(chip);}
   if(poke)poke.disabled=busy||pokeBusy||starting||recording||transcribing||entries.some(e=>e.pending||e.error);
   attach.hidden=inputPolicy.attachments===false;mic.hidden=inputPolicy.voice===false;attach.disabled=busy;mic.disabled=busy||starting||transcribing||realtimeActive;mic.classList.toggle('is-recording',recording);mic.setAttribute('aria-pressed',String(recording));mic.title=realtimeActive?label('对话模式正在使用麦克风','Conversation mode is using the microphone'):transcribing?label('正在识别…','Transcribing…'):recording?label('停止录音并转写','Stop recording and transcribe'):label('语音输入','Voice input');mic.setAttribute('aria-label',mic.title);speechModel.disabled=recording||transcribing||realtimeActive;onChange();}
  async function add(files){if(busy||inputPolicy.attachments===false)return;for(const file of files){if(entries.length>=8){onError(Error(label('最多添加 8 个附件','Choose at most 8 attachments')));break;}
   if(file.size>(file.type.startsWith('image/')?8:25)*1024*1024){onError(Error(label('附件过大：','Attachment too large: ')+file.name));continue;}
   const entry={file,pending:true,url:file.type.startsWith('image/')?URL.createObjectURL(file):null};entries.push(entry);render();
   try{const data=new FormData();data.append('file',file);const value=await request('/v1/platform/sessions/'+encodeURIComponent(sessionId)+'/attachments/upload',{method:'POST',body:data});entry.id=value.id;}
   catch(e){entry.error=true;if(!disposed)onError(e);}finally{entry.pending=false;if(!disposed)render();}
  }}
  attach.onclick=()=>fileInput.click();fileInput.onchange=()=>{const files=Array.from(fileInput.files||[]);fileInput.value='';void add(files);};
  async function addGallery(ids){if(inputPolicy.attachments===false)return;for(const id of ids.slice(0,8)){if(disposed||busy)return;if(entries.length>=8){onError(Error(label('最多添加 8 个附件','Choose at most 8 attachments')));return;}try{const base='/v1/platform/gallery/assets/'+encodeURIComponent(id);const asset=await request(base);if(disposed)return;const max=asset.media_type?.startsWith('image/')?8:25;if(asset.size_bytes>max*1024*1024)throw Error(label('素材过大：','Material too large: ')+asset.name);const response=await fetch(base+'/content',{credentials:'same-origin'});if(!response.ok)throw Error(label('素材不可用','Material unavailable'));const blob=await response.blob();if(disposed)return;if(blob.size>max*1024*1024)throw Error(label('素材过大','Material too large'));await add([new File([blob],asset.name,{type:asset.media_type||blob.type})]);}catch(e){if(!disposed)onError(e);}}}
  const drag=e=>{if(window.AI2AppsGalleryPicker?.acceptsDrop(e.dataTransfer)||e.dataTransfer?.types.includes('Files')){e.preventDefault();e.dataTransfer.dropEffect='copy';}};
  const drop=e=>{try{const ids=window.AI2AppsGalleryPicker?.droppedAssetIds(e.dataTransfer)||[];if(ids.length){e.preventDefault();e.stopPropagation();void addGallery(ids);}else if(e.dataTransfer?.files.length){e.preventDefault();e.stopPropagation();void add(Array.from(e.dataTransfer.files));}}catch(error){e.preventDefault();onError(error);}};
  dropTarget.addEventListener('dragover',drag);dropTarget.addEventListener('drop',drop);
  mic.onclick=async()=>{if(inputPolicy.voice===false||realtimeActive)return;if(starting||transcribing||busy)return;
   if(!speechModel.value){offerRecognition(Error(label('尚未配置语音识别模型','Speech recognition is not configured')));return;}
   try{if(!recording){starting=true;voiceEpoch++;pendingAudio=null;voiceNotice.replaceChildren();render();recorder=new window.AI2AppsStudioAudioRecorder();await recorder.start(120);if(disposed){recorder.dispose();return;}starting=false;recording=true;render();
      // Handles the recorder time limit as well as the explicit stop button.
      recorder.result.then(()=>{if(recording&&!disposed)finishRecording();});
     }else await finishRecording();
   }catch(e){starting=false;recording=false;recorder?.dispose();recorder=null;if(!disposed){render();onError(e);}}};
  function offerRecognition(error,setup=true){
   const epoch=++voiceEpoch;
   if(!window.AI2AppsBotVoice?.offerSetup){onError(error);return;}
   if(setup)window.AI2AppsBotVoice.offerSetup({notice:voiceNotice,operation:'speech_recognition',error,isCurrent:()=>!disposed&&epoch===voiceEpoch,onConfigured:async result=>{
    const model=result.provider?.modelId||result.session?.provider?.modelId;
    if(model){if(!Array.from(speechModel.options||speechModel.children).some(m=>m.value===model))speechModel.add(new Option(model,model));speechModel.value=model;}
    else{const value=await request('/admin/api/models');if(disposed||epoch!==voiceEpoch)return;const available=(value.models||[]).filter(m=>m.model_type==='audio_stt'&&m.checkpoint_ready!==false&&!m.is_hidden&&!m.load_failed);speechModel.replaceChildren();for(const m of available)speechModel.add(new Option(m.name||m.id,m.id));speechModel.hidden=available.length<2;}
   }});
   if(!setup){voiceNotice.replaceChildren();voiceNotice.textContent=error.message;}
   if(pendingAudio){const retry=document.createElement('button');retry.type='button';retry.className='messager-button';retry.textContent=label('重试这段录音','Retry this recording');retry.onclick=()=>{if(!disposed&&epoch===voiceEpoch&&!transcribing&&!busy&&pendingAudio)void transcribe(pendingAudio);};voiceNotice.append(retry);}
  }
  async function transcribe(result){transcribing=true;render();
   try{const body=new FormData();body.append('file',result.body,result.name);body.append('model',speechModel.value);body.append('response_format','json');
    const value=await request('/v1/audio/transcriptions',{method:'POST',body});if(disposed)return;const text=String(value.text||'').trim();if(!text)throw Error(label('未识别到文字','No speech recognized'));
    input.value=(input.value.trim()?input.value.trim()+' ':'')+text;input.dispatchEvent(new Event('input'));input.focus();pendingAudio=null;voiceNotice.replaceChildren();
   }catch(e){if(!disposed){offerRecognition(e,!!e.status&&![401,403,429].includes(e.status));}}finally{transcribing=false;if(!disposed)render();}
  }
  async function finishRecording(){if(!recording)return;recording=false;transcribing=true;render();const current=recorder;
   try{const result=await current.stop();if(disposed)return;pendingAudio=result;await transcribe(result);}
   catch(e){if(!disposed)onError(e);}finally{current?.dispose();if(recorder===current)recorder=null;transcribing=false;if(!disposed)render();}}

  // Match Chat: desktop Enter sends, Shift+Enter / touch Enter inserts a newline.
  // keyCode 229 covers IME confirmation events that omit isComposing.
  const touchInput=!!(window.matchMedia&&window.matchMedia('(pointer: coarse)').matches);
  function onEnter(event){
   if(event.defaultPrevented||event.key!=='Enter'||touchInput||event.shiftKey||event.isComposing||event.keyCode===229)return;
   event.preventDefault();
   if(!disposed&&!send.disabled&&!busy&&!starting&&!recording&&!transcribing&&!entries.some(e=>e.pending||e.error))form.requestSubmit(send);
  }
  input.addEventListener('keydown',onEnter);
  render();
  return {setModels,mountRealtime(button,panel){controls.insertBefore(button,mic.nextSibling);const row=document.createElement('div');row.className='bot-realtime-input-row';const column=document.createElement('div');column.className='bot-realtime-compose-column';form.insertBefore(row,input);column.append(input,controls);row.append(column,panel);},canStartRealtime:()=>!busy&&!starting&&!recording&&!transcribing&&!disposed,setRealtimeActive(value){realtimeActive=value;render();},setPokeBusy(value){pokeBusy=value;render();},captureAttachments(){const selected=entries.slice();return ()=>{if(selected.some(e=>!entries.includes(e)))throw Error(label('附件选择已变化，请重新提交这段输入。','Attachment selection changed. Submit a new input.'));if(selected.some(e=>e.error))throw Error(label('附件上传失败，请处理后重新提交。','An attachment failed. Resolve it and submit again.'));return selected.some(e=>e.pending)?null:selected.map(e=>e.id);};},removeIds(ids){const removed=entries.filter(e=>ids.includes(e.id));for(const e of removed)if(e.url)URL.revokeObjectURL(e.url);entries=entries.filter(e=>!ids.includes(e.id));render();},ids:()=>entries.map(e=>e.id),hasFiles:()=>entries.length>0,blocked:()=>starting||recording||transcribing||entries.some(e=>e.pending||e.error),setBusy(value){busy=value;render();},clear(){for(const e of entries)if(e.url)URL.revokeObjectURL(e.url);entries=[];render();},dispose(){disposed=true;input.removeEventListener('keydown',onEnter);pendingAudio=null;recording=false;recorder?.dispose();for(const e of entries)if(e.url)URL.revokeObjectURL(e.url);dropTarget.removeEventListener('dragover',drag);dropTarget.removeEventListener('drop',drop);}};
 }
 window.AI2AppsBotComposer={create};
})();
