/* Chat-owned action labels and clipboard acknowledgement across surfaces. */
(function(root){'use strict';
 const doc=root.document,zh=()=>doc.documentElement.lang.toLowerCase().startsWith('zh');
 const selector='.message-header button[title],.user-message-actions button[title],.mchat-message-actions button[title]';
 function label(event){const button=event.target.closest?.(selector);if(!button||button.dataset.copySuccess)return;const text=button.title;if(text){button.dataset.chatTip=text;button.setAttribute('aria-label',text);button.title='';}}
 doc.addEventListener('pointerover',label);doc.addEventListener('focusin',label);
 let notice,timer;
 function show(button,success=true,silent=false){
  const text=success?(zh()?'已复制':'Copied'):(zh()?'复制失败，请重试':'Could not copy. Try again');
  if(button){const prior=button._chatTipOriginal??button.dataset.chatTip??button.title;button._chatTipOriginal=prior;clearTimeout(button._chatTipTimer);button.dataset.chatTip=text;button.dataset.copySuccess=String(success);button.classList.add('chat-tip-visible');button._chatTipTimer=setTimeout(()=>{button.classList.remove('chat-tip-visible');delete button.dataset.copySuccess;button.dataset.chatTip=prior;delete button._chatTipOriginal;},1800);}
  if(silent)return;
  if(!notice){notice=doc.createElement('div');notice.className='chat-copy-notice';notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');doc.body.append(notice);}
  clearTimeout(timer);notice.textContent=text;notice.hidden=false;timer=setTimeout(()=>{notice.hidden=true;},1800);
 }
 root.AI2AppsChatFeedback={show};
})(window);
