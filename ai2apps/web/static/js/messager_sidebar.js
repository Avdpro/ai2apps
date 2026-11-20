/* A captured pointer keeps resizing stable when it crosses a conversation iframe. */
(()=>{
 'use strict';
 const MIN=88,MAX=480,DEFAULT=260,COMPACT=168,KEY='ai2apps.messager.sidebar-width.v1';
 function nameTips(shell){
  if(!shell.addEventListener)return ()=>{};
  let tip=null,target=null;
  const hide=()=>{tip?.remove();tip=null;target=null;};
  function show(event){
   const selected=event.target.closest?.('.messager-bot-card,.bot-group-toggle');
   if(!selected||!shell.classList.contains('sidebar-compact')){hide();return;}
   if(target===selected)return;
   hide();target=selected;tip=document.createElement('div');tip.className='messager-sidebar-name-tip';tip.setAttribute('role','tooltip');
   tip.textContent=selected.getAttribute('aria-label')||selected.title;
   document.body.append(tip);const rect=(selected.querySelector('.messager-avatar')||selected).getBoundingClientRect();
   tip.style.left=Math.min(rect.right+8,window.innerWidth-tip.offsetWidth-12)+'px';
   tip.style.top=Math.max(8,Math.min(rect.top+(rect.height-tip.offsetHeight)/2,window.innerHeight-tip.offsetHeight-12))+'px';
  }
  function leave(event){if(target&&!target.contains(event.relatedTarget))hide();}
  for(const event of ['pointerover','focusin'])shell.addEventListener(event,show);
  for(const event of ['pointerout','focusout'])shell.addEventListener(event,leave);
  shell.addEventListener('scroll',hide,true);window.addEventListener('resize',hide);
  const dispose=()=>{hide();for(const event of ['pointerover','focusin'])shell.removeEventListener(event,show);for(const event of ['pointerout','focusout'])shell.removeEventListener(event,leave);shell.removeEventListener('scroll',hide,true);window.removeEventListener('resize',hide);};
  dispose.hide=hide;return dispose;
 }
 function mount({handle,shell,rightWidth=()=>0,onWidth,side='left'}){
  const stopTips=side==='left'?nameTips(shell):()=>{};
  const isRight=side==='right',storageKey=isRight?'ai2apps.messager.right-sidebar-width.v1':KEY;
  const minimum=()=>isRight?(shell.getBoundingClientRect().width<=1050?250:300):MIN;
  const initial=()=>isRight?minimum():DEFAULT,limit=isRight?720:MAX,direction=isRight?-1:1;
  let preferred=initial(),width=initial(),drag=null,disposed=false;
  try{const raw=localStorage.getItem(storageKey),saved=raw===null?NaN:Number(raw);if(Number.isFinite(saved))preferred=Math.min(limit,Math.max(minimum(),saved));}catch(_){}
  function maximum(){const available=shell.getBoundingClientRect().width;return Math.max(minimum(),Math.min(limit,available<=760?available-24:available-rightWidth()-360));}
  function apply(value){stopTips.hide?.();width=Math.max(minimum(),Math.min(maximum(),value));handle.setAttribute('aria-valuemin',String(minimum()));handle.setAttribute('aria-valuenow',String(Math.round(width)));handle.setAttribute('aria-valuemax',String(Math.round(maximum())));onWidth(Math.round(width));}
  function save(){try{localStorage.setItem(storageKey,String(Math.round(preferred)));}catch(_){} }
  function set(value){preferred=Math.min(limit,Math.max(minimum(),value));apply(preferred);save();}
  function finish(event){if(!drag||event&&event.pointerId!==drag.id)return;const id=drag.id;drag=null;document.documentElement.classList.remove('messager-resizing');if(handle.hasPointerCapture?.(id))handle.releasePointerCapture(id);save();}
  function down(event){if(event.button!==0||event.isPrimary===false||shell.getBoundingClientRect().width<=760)return;event.preventDefault();drag={id:event.pointerId,x:event.clientX,width};handle.setPointerCapture(event.pointerId);handle.focus();document.documentElement.classList.add('messager-resizing');}
  function move(event){if(!drag||event.pointerId!==drag.id)return;event.preventDefault();preferred=Math.max(minimum(),Math.min(maximum(),drag.width+direction*(event.clientX-drag.x)));apply(preferred);}
  function key(event){let value;if(event.key==='ArrowLeft')value=width-direction*16;else if(event.key==='ArrowRight')value=width+direction*16;else if(event.key==='Home')value=minimum();else if(event.key==='End')value=maximum();else return;event.preventDefault();set(value);}
  const reset=()=>set(initial()),resize=()=>{if(!disposed)apply(preferred);};
  const handlers={pointerdown:down,pointermove:move,pointerup:finish,pointercancel:finish,lostpointercapture:finish,keydown:key,dblclick:reset};
  for(const [name,fn] of Object.entries(handlers))handle.addEventListener(name,fn);
  window.addEventListener('resize',resize);const observer=typeof ResizeObserver==='undefined'?null:new ResizeObserver(resize);observer?.observe(shell);
  apply(preferred);
  return {expand(){set(DEFAULT);},refresh:resize,dispose(){stopTips();disposed=true;finish();observer?.disconnect();window.removeEventListener('resize',resize);for(const [name,fn] of Object.entries(handlers))handle.removeEventListener(name,fn);}};
 }
 window.AI2AppsMessagerSidebar={mount,MIN,MAX,DEFAULT,COMPACT};
})();
