/* Creation-dialog dictation uses the shared recorder and capability flow. */
(() => {
 const dialog=document.getElementById('name-dialog'),status=document.getElementById('todo-dictation-status');
 const buttons=[...dialog.querySelectorAll('[data-todo-dictate]')];
 const zh=document.documentElement.lang.startsWith('zh');
 let active=null,epoch=0;
 const message=(cn,en)=>zh?cn:en;
 function render(){for(const b of buttons){b.disabled=!!active&&!(active.button===b&&active.recording);b.textContent=active?.button===b&&active.recording?message('停止并转写','Stop and transcribe'):message(b.dataset.todoDictate==='dialog-name'?'🎙 语音输入标题':'🎙 语音输入内容','🎙 Dictate');}}
 function cancel(){epoch++;active?.recorder?.dispose();active?.abort?.abort();active=null;status.textContent='';render();}
 dialog.addEventListener('close',cancel);
 window.addEventListener('pagehide',cancel);
 dialog.querySelector('form').addEventListener('submit',e=>{if(active){e.preventDefault();status.textContent=message('请等待语音输入完成，或取消对话框。','Wait for dictation to finish or cancel the dialog.');}});
 for(const button of buttons)button.addEventListener('click',async()=>{
  if(active){if(active.button===button&&active.recording){active.recording=false;render();active.recorder.stop().catch(()=>{});}return;}
  const token=++epoch,target=document.getElementById(button.dataset.todoDictate);
  const operation={button,recorder:null,abort:new AbortController(),recording:false};active=operation;render();
  try{
   status.textContent=message('检查语音识别模型…','Checking speech recognition…');
   const result=await window.AI2AppsCapabilities.ensure({appId:'ai2apps.todo',capability:'audio.speech_recognition',actionId:'create-project-dictation',requirements:{operations:['speech_recognition']},intent:{returnTo:'/apps/ai2apps.todo',resumeToken:crypto.randomUUID(),completionPolicy:'configure_only'}});
   if(token!==epoch||!dialog.open)return;
   const model=result.provider?.modelId;if(!model)throw new Error(message('语音识别尚未配置完成，请重试。','Speech recognition is not ready. Please retry.'));
   if(result.outcome==='configured'&&result.session?.id)await window.AI2AppsCapabilities.acknowledge(result.session.id,{appId:'ai2apps.todo'});
   if(token!==epoch||!dialog.open)return;
   operation.recorder=new window.AI2AppsStudioAudioRecorder();await operation.recorder.start(120);
   if(token!==epoch||!dialog.open)return;
   operation.recording=true;render();status.textContent=message('正在录音，再次点击停止（最长 2 分钟）…','Recording; click again to stop (up to 2 minutes)…');
   const audio=await operation.recorder.result;if(token!==epoch||!dialog.open)return;
   if(audio.error)throw new Error(audio.error);
   operation.recording=false;render();status.textContent=message('正在转写…','Transcribing…');
   const form=new FormData();form.append('file',audio.body,audio.name);form.append('model',model);form.append('response_format','json');
   const timer=setTimeout(()=>operation.abort.abort(),180000);
   let response;try{response=await fetch('/v1/audio/transcriptions',{method:'POST',credentials:'same-origin',body:form,signal:operation.abort.signal});}finally{clearTimeout(timer);}
   const payload=await response.json();if(!response.ok)throw new Error(payload.error?.message||payload.detail||'Transcription failed');
   if(token!==epoch||!dialog.open)return;
   const text=String(payload.text||'').trim();if(!text)throw new Error(message('没有识别到文字，请重试。','No speech recognized. Please retry.'));
   // Append to the current value, preserving typing made while recognition ran.
   const value=target.value+(target.value.trim()?'\n':'')+text;
   if(value.length>target.maxLength)throw new Error(message('识别结果超过输入长度限制，请缩短录音。','Result exceeds the input limit. Use a shorter recording.'));
   target.value=target.tagName==='INPUT'?value.replace(/\n/g,' '):value;target.dispatchEvent(new Event('input',{bubbles:true}));target.focus();
   status.textContent=message('已填入，可编辑后创建。','Inserted. Review and edit before creating.');
  }catch(error){if(token===epoch)status.textContent=message('语音输入未完成：','Dictation failed: ')+(error.message||String(error));}
  finally{operation.recorder?.dispose();if(token===epoch){active=null;render();}}
 });
 render();
})();
