/* Shared Desktop/Mobile confirmation for owner-reviewed conversation trimming. */
(function(){'use strict';
 function attach({toolbar,botId,sessionId,item,previewText,request,label,refresh,onError}){
  const button=document.createElement('button');button.type='button';
  button.title=label('剪裁后续对话','Trim later conversation');button.setAttribute('aria-label',button.title);
  button.className='bot-trim-action';
  button.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="m8 8 12 12M8 16 20 4"/></svg>';
  if(toolbar.hidden)for(const child of toolbar.children)child.hidden=true;
  toolbar.hidden=false;toolbar.append(button);
  button.onclick=async()=>{
   const dialog=document.createElement('dialog');dialog.className='bot-trim-dialog';
   dialog.setAttribute('aria-label',button.title);
   const header=document.createElement('header'),title=document.createElement('h2');title.textContent=button.title;header.append(title);
   const body=document.createElement('section'),note=document.createElement('p'),preview=document.createElement('blockquote'),scope=document.createElement('p'),error=document.createElement('p');
   note.textContent=label('保留这条 Bot 回复，永久删除它之后的全部对话及关联的独占输入、输出素材。','Keep this Bot reply and permanently delete all later conversation and its unshared input and output materials.');
   preview.textContent=(previewText||item.content||'').replace(/\s+/g,' ').trim().slice(0,200);scope.textContent=label('Access、记忆及 Task 保留，任务不会取消。素材库副本、磁盘原文件及仍被使用的共享素材保留。','Access, memory and Tasks stay unchanged; Tasks keep running. Gallery copies, original files and shared materials still in use are retained.');
   const count=document.createElement('p');count.setAttribute('role','status');count.textContent=label('正在核对范围…','Reviewing the scope…');error.setAttribute('role','alert');body.append(note,preview,count,scope,error);
   const footer=document.createElement('footer'),cancel=document.createElement('button'),confirm=document.createElement('button');
   cancel.type=confirm.type='button';cancel.textContent=label('取消','Cancel');cancel.autofocus=true;confirm.textContent=label('确认剪裁','Trim conversation');confirm.disabled=true;confirm.className='danger';footer.append(cancel,confirm);dialog.append(header,body,footer);document.body.append(dialog);
   const abort=new AbortController();let busy=false,review=null;
   dialog.oncancel=event=>{if(busy)event.preventDefault();};cancel.onclick=()=>dialog.close();
   dialog.onclose=()=>{abort.abort();dialog.remove();button.focus?.({preventScroll:true});};dialog.showModal();
   const path='/bots/'+encodeURIComponent(botId)+'/conversation-trim/',input={session_id:sessionId,message_id:item.id};
   async function reviewScope(){error.textContent='';try{review=await request(path+'review','POST',input,abort.signal);if(abort.signal.aborted)return;count.textContent=label('将删除 ','Delete ')+review.deleted_messages+label(' 条消息、',' messages and ')+review.deleted_materials+label(' 份素材。',' materials.');confirm.disabled=review.deleted_messages===0;}
   catch(e){if(!abort.signal.aborted)error.textContent=e.message;}}
   await reviewScope();
   confirm.onclick=async()=>{if(busy)return;if(!review){confirm.disabled=true;await reviewScope();confirm.textContent=label('确认剪裁','Trim conversation');return;}busy=true;confirm.disabled=cancel.disabled=true;error.textContent='';
    try{const result=await request(path+'apply','POST',{...input,review_hash:review.review_hash},abort.signal);
     if(result.cleanup_pending){await refresh(result);error.textContent=label('对话已剪裁，部分素材尚未清理，请点击重试。','Conversation trimmed; some materials still need cleanup. Retry to finish.');confirm.textContent=label('重试素材清理','Retry material cleanup');}
     else{dialog.close();await refresh(result);}
    }catch(e){if(!abort.signal.aborted){error.textContent=e.message;if(e.status===409){review=null;confirm.textContent=label('重新核对范围','Review scope again');}}}
    finally{busy=false;if(dialog.isConnected)confirm.disabled=cancel.disabled=false;}
   };
  };
  return button;
 }
 window.AI2AppsConversationTrim={attach};
})();
