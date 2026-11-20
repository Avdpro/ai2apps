/* Mobile owns navigation only; durable dialogue, tasks and access remain in Messager. */
(()=>{'use strict';
 const base='/v1/platform/messager-mobile',el=id=>document.getElementById('mm-'+id),zh=document.documentElement.lang.startsWith('zh'),t=(a,b)=>zh?a:b,terminal=new Set(['completed','failed','cancelled','interrupted','timed_out']);
 let groupDrag=null,groupTouch=null,groupClickUntil=0,groups=[],pokePending=null,pokeAwaitingReceipt=null,bots=[],bot=null,sid='',epoch=0,newest=0,oldest=null,hasOlder=false,loading=false,sending=false,uploading=false,readBusy=false,initial=false,unread={},items=new Map(),files=[],pending=null,timer=null,listTimer=null,noticeTimer=null,modelCatalog=null,profileModel=null,sessions=[];
 let conversationRevision,voiceUI=null;
 const outgoing = new Map();
 const drafts=new Map(),root=document.getElementById('messager-mobile');
 let page='list-page',slides=[],navigation=0,detailsRequest=0,backPending=false,conversationRoute=null,detailReady=false,creationForm=null,creationMenu=null,lastRoute='chat',creationRoute=null;
 const pages=['list-page','chat-page','details-panel','creation-page'];
 function showPage(next,back=false,animate=true){
  if(page===next&&animate)return;
  const revision=++navigation,previous=el(page),target=el(next);slides.forEach(a=>a.cancel());slides=[];
  for(const id of pages){el(id).hidden=!([page,next].includes(id));el(id).inert=id!==next;}
  page=next;root.dataset.page=next;previous.style.zIndex=back?'2':'1';target.style.zIndex=back?'1':'2';
  const finish=()=>{if(revision!==navigation)return;for(const id of pages){el(id).hidden=id!==next;el(id).style.zIndex='';}};
  if(!animate||!target.animate||window.matchMedia('(prefers-reduced-motion: reduce)').matches){finish();return;}
  const options={duration:240,easing:'ease-out'};
  slides=[previous.animate([{transform:'translateX(0)'},{transform:back?'translateX(100%)':'translateX(-25%)'}],options),target.animate([{transform:back?'translateX(-25%)':'translateX(100%)'},{transform:'translateX(0)'}],options)];
  Promise.allSettled(slides.map(a=>a.finished)).then(finish);
 }
 function hosted(){return window.parent!==window&&!!mount.get('ai2apps-mount')&&!!mount.get('ai2apps-instance');}
 function navigationMessage(type,extra={}){window.parent.postMessage({type,mountToken:mount.get('ai2apps-mount'),instanceId:mount.get('ai2apps-instance'),...extra},location.origin);}
 function pushNavigation(depth){if(hosted()){backPending=false;navigationMessage('ai2apps.shell.navigation.push',{depth});}}
 function requestBack(){if(!backPending){backPending=true;navigationMessage('ai2apps.shell.navigation.back');}}
 function backToConversation(fromHistory=false,animate=true){if(page!=='details-panel')return;if(hosted()&&!fromHistory){requestBack();return;}detailsRequest++;showPage('chat-page',true,animate);updateJump();el('details').focus({preventScroll:true});}
 function backToList(fromHistory=false,animate=true){if(!bot||(!fromHistory&&(sending||uploading)))return;if(hosted()&&!fromHistory){requestBack();return;}window.AI2AppsMobileBotVoice?.stopRead();voiceUI?.dispose();voiceUI=null;drafts.set(bot.id,el('input').value);conversationRoute={bot,sid,initial};epoch++;detailsRequest++;initial=false;bot=null;sid='';showPage('list-page',true,animate);el('back').hidden=true;el('title').textContent=t('消息','Messager');el('details').hidden=true;chrome(true);loadBots().catch(error);}
 function back(){if(page==='creation-page'){if(hosted())requestBack();else cancelCreation();}else if(page==='details-panel')backToConversation();else if(page==='chat-page')backToList();}
 let swipe=null;
 root.addEventListener('touchstart',event=>{const point=event.touches[0],nativeEdge=hosted()&&point.clientX-root.getBoundingClientRect().left<=24;swipe=!nativeEdge&&page!=='list-page'&&event.touches.length===1&&!event.target.closest('input,textarea,select,button,a,pre,audio,video')&&!document.querySelector('dialog[open]')?{x:point.clientX,y:point.clientY,page}:null;},{passive:true});
 root.addEventListener('touchmove',event=>{if(!swipe)return;if(event.touches.length!==1){swipe=null;return;}const point=event.touches[0],dx=point.clientX-swipe.x,dy=point.clientY-swipe.y;if(Math.abs(dy)>20&&Math.abs(dy)>Math.abs(dx)){swipe=null;return;}if(dx>12&&dx>Math.abs(dy)*1.5&&event.cancelable)event.preventDefault();},{passive:false});
 root.addEventListener('touchend',event=>{if(!swipe)return;const start=swipe,point=event.changedTouches[0];swipe=null;const dx=point.clientX-start.x,dy=point.clientY-start.y;if(start.page===page&&dx>72&&dx>Math.abs(dy)*1.5){if(event.cancelable)event.preventDefault();back();}},{passive:false});
 root.addEventListener('touchcancel',()=>{swipe=null;},{passive:true});
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&page==='details-panel'&&!document.querySelector('dialog[open]')){event.preventDefault();back();}});
 function cancelCreation(animate=true){creationForm?.dispose({preserveDOM:true});creationForm=null;showPage('list-page',true,animate);chrome(true);loadBots().catch(error);}
 function beginCreation(push=true,animate=true,botType='standard',groupId=null){lastRoute='creation';creationRoute={botType,groupId};showPage('creation-page',false,animate);chrome(false);if(push)pushNavigation(1);creationForm?.dispose();creationForm=window.AI2AppsBotCreation.mount(el('creation-host'),{botType,request:(path,method='GET',body)=>api(path==='/options'?'/creation/options':path==='/submit'?'/creation':path,method,path==='/submit'&&groupId?{...body,group_id:groupId}:body),models:async()=>{const c=await api('/models'),policy=AI2AppsConversationModelPolicy,models=policy.agentOptions(c.data||[]);return {models,selected:policy.agentDefault(models,c.defaults?.work_agent,[c.defaults?.work_standard,c.defaults?.work_complex],c.api_default?'cloud/ai2apps/'+c.api_default:null)||''};},onCancel:()=>hosted()?requestBack():cancelCreation(),onCreated:result=>{creationForm?.dispose({preserveDOM:true});creationForm=null;loadBots().catch(error);open(result,{restore:true}).catch(error);}});}
 const mount=new URLSearchParams(location.hash.slice(1));
 function chrome(dockVisible){if(window.parent===window)return;for(const [type,visible] of [['ai2apps.shell.set-dock-visible',dockVisible],['ai2apps.shell.set-topbar-visible',false]])window.parent.postMessage({type,mountToken:mount.get('ai2apps-mount'),instanceId:mount.get('ai2apps-instance'),visible},location.origin);}
 window.addEventListener('message',event=>{
  if(event.source!==window.parent||event.origin!==location.origin||event.data?.mountToken!==mount.get('ai2apps-mount'))return;
  if(event.data.type==='ai2apps.host.activate'){chrome(page==='list-page');return;}
  if(event.data.type!=='ai2apps.shell.navigation.history'||event.data.instanceId!==mount.get('ai2apps-instance'))return;
  const depth=Number(event.data.depth);if(!Number.isInteger(depth)||depth<0||depth>2)return;backPending=false;
  const instant=event.data.animate!==true;if(instant){root.classList.add('mm-navigation-instant');requestAnimationFrame(()=>requestAnimationFrame(()=>root.classList.remove('mm-navigation-instant')));}
  if(depth===0){if(page==='creation-page'){cancelCreation(!instant);if(instant)root.getBoundingClientRect();return;}if(page==='details-panel')backToConversation(true,false);backToList(true,!instant);}
  else{
   if(depth===1&&lastRoute==='creation'){if(page!=='creation-page'||!creationForm)beginCreation(false,!instant,creationRoute?.botType,creationRoute?.groupId);else showPage('creation-page',false,!instant);return;}
   if(!bot&&conversationRoute){if(!conversationRoute.initial){void open(conversationRoute.bot,{restore:true,animate:!instant}).then(()=>{if(depth===2&&bot)void details(false,!instant);}).catch(error);return;}({bot,sid,initial}=conversationRoute);el('title').textContent=bot.name;el('back').hidden=false;el('details').hidden=!initial;chrome(false);}
   if(bot){attachVoice();if(depth===1){if(page==='details-panel')backToConversation(true,!instant);else showPage('chat-page',false,!instant);}
    else if(detailReady)showPage('details-panel',false,!instant);else void details(false,!instant);
    updateJump();}
  }
  if(instant)root.getBoundingClientRect();
 });
 let noticeSource='',listFailures=0,listRequest=null,groupGeneration=0;const groupViews=new Map();
 function error(e,source=''){noticeSource=source;el('notice').textContent=e.message||String(e);el('notice').hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>el('notice').hidden=true,6000);}
 function clockHeaders(){return {'X-AI2Apps-Timezone':Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC'};}
  async function api(path,method='GET',body,headers={}){const r=await fetch(base+path,{method,credentials:'same-origin',headers:body instanceof FormData?headers:{'Content-Type':'application/json',...headers},...(body?{body:body instanceof FormData?body:JSON.stringify(body)}:{})});const value=await r.json().catch(()=>({}));if(!r.ok){const error=Error(value.detail?.message||value.detail||value.error?.message||t('连接失败，请重试','Connection failed. Try again.'));error.status=r.status;error.code=value.error?.code||'';error.requestId=r.headers.get('X-AI2Apps-Request-Id')||'';throw error;}return value;}
 const resource=path=>window.MobileAppResource?.(base+path)||base+path;
 const bottom=()=>page==='chat-page'&&el('stream').scrollHeight-el('stream').scrollTop-el('stream').clientHeight<32;
 function updateJump(){el('bottom').hidden=bottom();}
 function dimensions(){el('stream').style.scrollBehavior='auto';document.documentElement.style.setProperty('--mm-height',(window.visualViewport?.height||window.innerHeight)+'px');updateJump();}
 function statusRing(task=false){const ring=document.createElement('span');ring.className='mm-ring'+(task?' task':'');ring.setAttribute('role','img');ring.setAttribute('aria-label',task?t('执行任务','Running task'):t('正在回复','Replying'));return ring;}
 function acceptGroups(rows){
  const previous=new Map(groups.map(g=>[g.id,g]));
  groups=rows.map(g=>{const old=previous.get(g.id);return old&&old.revision>g.revision?old:g;});
  for(const g of groups){const view=groupViews.get(g.id);if(view&&!view.pending&&!view.busy){view.desired=!!g.collapsed;view.confirmed=!!g.collapsed;view.revision=g.revision;}}
 }
 function paintGroup(id){
  const view=groupViews.get(id);if(!view)return;
  const section=[...el('bots').children].find(node=>node.dataset.botGroupId===id);if(!section)return;
  const toggle=section.querySelector('.mm-group-heading > button');toggle?.setAttribute('aria-expanded',String(!view.desired));
  const arrow=toggle?.querySelector('.mm-group-chevron');if(arrow)arrow.textContent=view.desired?'›':'⌄';
  section.lastElementChild.hidden=view.desired;
 }
 function toggleGroup(id){
  const group=groups.find(g=>g.id===id);if(!group)return;
  let view=groupViews.get(id);if(!view){view={desired:!!group.collapsed,confirmed:!!group.collapsed,revision:group.revision,pending:false,busy:false,timer:null};groupViews.set(id,view);}
  view.desired=!view.desired;view.pending=true;groupGeneration++;paintGroup(id);
  clearTimeout(view.timer);view.timer=setTimeout(()=>void saveGroup(id,view),120);
 }
 async function saveGroup(id,view){
  if(view.busy)return;view.busy=true;let conflicts=0;
  try{
   while(view.desired!==view.confirmed){
    const desired=view.desired;
    try{
     const result=await api('/bot-groups/'+encodeURIComponent(id),'PATCH',{revision:view.revision,collapsed:desired});
     groupGeneration++;acceptGroups(result.items);const saved=groups.find(g=>g.id===id);
     if(!saved)throw Error(t('分组已不存在','Group is no longer available'));
     view.confirmed=!!saved.collapsed;view.revision=saved.revision;
    }catch(err){
     // Read back an uncertain write; never blindly replay a failed mutation.
     try{const result=await api('/bot-groups');groupGeneration++;acceptGroups(result.items);const actual=groups.find(g=>g.id===id);if(actual){view.confirmed=!!actual.collapsed;view.revision=actual.revision;}else throw Error('Group unavailable');}
     catch(_){throw err;}
     if(view.desired===view.confirmed)break;
     if(err.status===409&&conflicts++<1)continue;
     throw err;
    }
   }
   if(noticeSource==='group-save'){el('notice').hidden=true;noticeSource='';}
  }catch(err){
   view.desired=view.confirmed;
   error(Error(t('分组显示状态保存失败，请重试。','Could not save group display. Please try again.')),'group-save');
  }finally{view.pending=false;view.busy=false;paintGroup(id);}
 }
 function refreshList(){return loadBots().catch(err=>{if(++listFailures>=2||[401,403].includes(err.status))error(err,'list-refresh');});}
 async function loadBots(){
  if(groupDrag||groupTouch||creationMenu)return;
  if(listRequest)return listRequest;
  listRequest=(async()=>{const generation=groupGeneration;const [value,groupValue]=await Promise.all([api('/bots?language='+t('zh','en')),api('/bot-groups')]);
   if(groupDrag||groupTouch||creationMenu)return;
   bots=value.items;if(generation===groupGeneration)acceptGroups(groupValue.items);
   listFailures=0;if(noticeSource==='list-refresh'){el('notice').hidden=true;noticeSource='';}
   renderBots();
  })();
  try{return await listRequest;}finally{listRequest=null;}
 }
 function renderBots(){el('bots').replaceChildren();for(const g of [{id:null,name:t('无分组','Ungrouped')},...groups]){const members=bots.filter(b=>(b.group_id||null)===g.id);const section=document.createElement('section'),header=document.createElement('div');section.dataset.botGroupId=g.id||'ungrouped';header.className='mm-group-heading';if(g.id)header.dataset.groupOrderId=g.id;const toggle=document.createElement('button');toggle.type='button';if(g.id){const arrow=document.createElement('span');arrow.className='mm-group-chevron';arrow.textContent=(groupViews.get(g.id)?.desired??g.collapsed)?'›':'⌄';arrow.setAttribute('aria-hidden','true');toggle.append(arrow);}const groupName=document.createElement('span'),count=document.createElement('small');
 groupName.className='mm-group-name';groupName.textContent=g.id==='quick'?t('快捷Bot','Quick Bots'):g.name;
 count.textContent=members.length;
 toggle.append(groupName,count);toggle.setAttribute('aria-expanded',String(!(groupViews.get(g.id)?.desired??g.collapsed)));toggle.onclick=()=>{if(!g.id||Date.now()<groupClickUntil)return;toggleGroup(g.id);};header.append(toggle);
 if(g.id){
  const action=document.createElement(g.permanent?'span':'button');
  action.className='mm-group-action';
  if(g.permanent){
   action.setAttribute('aria-label',t('默认分组','Default group'));
   action.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4"/></svg>';
  }else{
   action.type='button';
   action.setAttribute('aria-label',t('分组操作：','Group actions: ')+g.name);
   action.setAttribute('aria-haspopup','menu');
   action.setAttribute('aria-expanded','false');
   action.innerHTML='<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path stroke-linecap="round" d="M5 12h.01M12 12h.01M19 12h.01"/></svg>';
   action.onclick=()=>openGroupMenu(action,g);
  }
  header.append(action);
 }
 section.append(header);const container=document.createElement('div');container.hidden=!!(groupViews.get(g.id)?.desired??g.collapsed);for(const b of members){const row=document.createElement('button');row.className='mm-bot';row.dataset.botOrderId=b.id;
const mode = b.definition?.execution_mode;
const botType = mode === 'flash' ? 'FlashBot' : mode === 'app_shortcut' ? 'ASCBot' : '';
row.setAttribute('aria-label', botType ? b.name + ' · ' + botType : b.name);
if (botType) {
  const iconPath = mode === 'flash' ? 'm25 15-6 7h4l-1 6 6-8h-4z' : 'M18 24h10m-4-4 4 4-4 4';
  row.innerHTML = '<svg class="bot-type-corner" viewBox="0 0 32 32" aria-hidden="true"><path fill="none" stroke="#d6d6d6" d="M0 32 32 0"/><path fill="none" stroke="#858585" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" d="' + iconPath + '"/></svg>';
}
const avatar=document.createElement('img');avatar.alt='';avatar.src=b.avatar?.kind==='image'?resource('/bots/'+encodeURIComponent(b.id)+'/avatar'):AI2AppsBotAvatars.url(b);const name=document.createElement('strong');name.textContent=b.name;row.append(avatar,name);if(b.unread_count){const ribbon=document.createElement('span');ribbon.className='mm-unread';ribbon.textContent=b.unread_count>99?'99+':b.unread_count;row.append(ribbon);}if(b.needs_user_assistance||['waiting_input','waiting_capability'].includes(b.reply_status)||['waiting_input','waiting_capability'].includes(b.task_status)){const ribbon=document.createElement('span');ribbon.className='mm-assistance';ribbon.textContent='!';ribbon.setAttribute('role','img');ribbon.setAttribute('aria-label',t('等待用户协助','Waiting for your help'));row.append(ribbon);}if(b.reply_status&&!terminal.has(b.reply_status)&&!['waiting_input','waiting_capability'].includes(b.reply_status))row.append(statusRing());if(['running','planning'].includes(b.task_status))row.append(statusRing(true));row.onclick=()=>{if(Date.now()>groupClickUntil)open(b).catch(error);};container.append(row);}section.append(container);el('bots').append(section);}if(!bots.length)el('bots').append(document.createTextNode(t('尚无机器人','No Bots yet.')));}

 // Long press enables touch grouping without interfering with normal list scrolling.
 const groupList=el('bots');
 groupList.addEventListener('touchstart',event=>{if(event.touches.length!==1||groupTouch)return;if(event.target.closest('.mm-group-heading > button:last-child:not(:first-child)'))return;const row=event.target.closest('[data-bot-order-id]')||event.target.closest('[data-group-order-id]');if(!row)return;const kind=row.dataset.groupOrderId?'group':'bot';const point=event.touches[0];groupTouch={kind,id:row.dataset.groupOrderId||row.dataset.botOrderId,x:point.clientX,y:point.clientY,timer:setTimeout(()=>{if(groupTouch){groupDrag={kind:groupTouch.kind,id:groupTouch.id,target:null};row.classList.add('mm-group-dragging');groupClickUntil=Date.now()+1000;}},450)};},{passive:true});
 groupList.addEventListener('touchmove',event=>{if(!groupTouch)return;const point=event.touches[0];if(!groupDrag){if(Math.hypot(point.clientX-groupTouch.x,point.clientY-groupTouch.y)>8){clearTimeout(groupTouch.timer);groupTouch=null;}return;}if(event.cancelable)event.preventDefault();const target=document.elementFromPoint(point.clientX,point.clientY)?.closest('[data-bot-group-id]');groupDrag.target=target?.dataset.botGroupId||null;if(groupDrag.kind==='group'){if(groupDrag.target==='ungrouped')groupDrag.target=null;const rect=target?.getBoundingClientRect();groupDrag.after=rect?point.clientY>rect.top+rect.height/2:false;}for(const section of groupList.querySelectorAll('[data-bot-group-id]'))section.classList.toggle('mm-group-drop',section===target);},{passive:false});
 function endGroupDrag(cancelled=false){clearTimeout(groupTouch?.timer);groupTouch=null;const drag=groupDrag;groupDrag=null;for(const row of groupList.querySelectorAll('.mm-group-dragging,.mm-group-drop'))row.classList.remove('mm-group-dragging','mm-group-drop');if(!drag)return;groupClickUntil=Date.now()+500;if(!cancelled&&drag.target){if(drag.kind==='group'){if(drag.target===drag.id)return;const ids=groups.map(g=>g.id).filter(id=>id!==drag.id);ids.splice(ids.indexOf(drag.target)+(drag.after?1:0),0,drag.id);api('/bot-groups-order','PUT',{ids}).then(loadBots).catch(error);return;}const ids=bots.filter(b=>b.id!==drag.id).map(b=>b.id);ids.push(drag.id);api('/bots-order','PUT',{ids,move:{bot_id:drag.id,group_id:drag.target==='ungrouped'?null:drag.target}}).then(loadBots).catch(error);}}
 groupList.addEventListener('contextmenu',event=>{if(groupDrag)event.preventDefault();});
 groupList.addEventListener('touchend',()=>endGroupDrag(),{passive:true});groupList.addEventListener('touchcancel',()=>endGroupDrag(true),{passive:true});
 function openGroupMenu(anchor,group){
  if(anchor.getAttribute('aria-expanded')==='true'){creationMenu?.dispose();return;}
  creationMenu?.dispose();
  const onClose=()=>{creationMenu=null;};
  creationMenu=window.AI2AppsBotCreation.groupMenu(anchor,{
   onClose,
   onCreate:()=>{creationMenu=window.AI2AppsBotCreation.menu(anchor,{
    grouped:true,below:true,onClose,onChoose:type=>beginCreation(true,true,type,group.id),
   });},
   onRename:()=>groupDialog(group,'rename'),
   onDelete:()=>groupDialog(group),
  });
 }
 function groupDialog(group=null,mode=group?'delete':'create'){
  if(mode!=='delete'){
   window.AI2AppsTextInputDialog.open({
    title:group?t('重新命名分组','Rename group'):t('新建分组','New group'),
    label:t('分组名称','Group name'), value:group?.name, maxLength:64,
    submitLabel:group?t('保存','Save'):t('创建','Create'), cancelLabel:t('取消','Cancel'),
    onSubmit:async name=>{
     await api(group?'/bot-groups/'+group.id:'/bot-groups',group?'PATCH':'POST',
      group?{revision:group.revision,name}:{name});
     loadBots().catch(error);
    },
   });
   return;
  }
  const dialog=document.createElement('dialog'),form=document.createElement('form');
  const title=document.createElement('h2'),info=document.createElement('p');
  const cancel=document.createElement('button'),remove=document.createElement('button');
  title.textContent=t('删除分组','Delete group');
  info.textContent=group.name+' · '+t('Bot 将变为无分组，对话保留。','Bots become ungrouped; conversations are kept.');
  cancel.type='button';cancel.textContent=t('取消','Cancel');
  remove.type='submit';remove.textContent=t('删除分组','Delete group');
  cancel.onclick=()=>dialog.close();
  form.append(title,info,cancel,remove);
  dialog.append(form);
  dialog.className='mm-group-dialog';
  dialog.oncancel=event=>{if(remove.disabled)event.preventDefault();};
  form.onsubmit=async event=>{
   event.preventDefault();
   if(remove.disabled)return;
   cancel.disabled=remove.disabled=true;
   try{
    await api('/bot-groups/'+group.id,'DELETE',{revision:group.revision});
    dialog.close();
    await loadBots();
   }catch(e){error(e);}
   finally{cancel.disabled=remove.disabled=false;}
  };
  dialog.onclose=()=>dialog.remove();
  document.body.append(dialog);
  dialog.showModal();
  cancel.focus();
 }
 function localFile(ref,kind){const session=ref.session_id||sid,id=kind==='attachments'?ref.id:ref.artifact_id;return '/bots/'+encodeURIComponent(bot.id)+'/files/'+encodeURIComponent(session)+'/'+kind+'/'+encodeURIComponent(id);}
 function media(article,ref,kind){const path=localFile(ref,kind),type=ref.media_type||'',name=ref.filename||t('附件','Attachment'),card=document.createElement('div');card.className='mm-media';if(type.startsWith('image/')&&type!=='image/svg+xml'){const image=document.createElement('img');image.src=resource(path+'?preview=true');image.alt=name;image.loading='lazy';image.decoding='async';image.onclick=()=>{const d=document.createElement('dialog'),close=document.createElement('button'),full=document.createElement('img');close.textContent=t('关闭','Close');full.src=resource(path);full.alt=name;full.style.cssText='max-width:100%;max-height:80dvh';close.onclick=()=>d.close();d.append(close,full);d.style.cssText='max-width:95vw;border:1px solid #ddd;border-radius:12px;padding:12px';d.onclose=()=>d.remove();document.body.append(d);d.showModal();};card.append(image);}else if(type.startsWith('audio/')||type.startsWith('video/')){const player=document.createElement(type.startsWith('audio/')?'audio':'video');player.src=resource(path);player.controls=true;player.preload='metadata';card.append(player);}else{const title=document.createElement('div');title.textContent=name;card.append(title);}const download=document.createElement('button');download.textContent=t('下载','Download');download.onclick=async()=>{download.disabled=true;try{const r=await fetch(base+path);if(!r.ok)throw Error(t('文件不可用','File unavailable'));const blob=await r.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);}catch(e){error(e);}finally{download.disabled=false;}};card.append(download);article.append(card);}
 function removeOutgoing(requestId,acknowledged=false) {
  outgoing.get(requestId)?.remove();
  outgoing.delete(requestId);
  if(pokeAwaitingReceipt===requestId){pokeAwaitingReceipt=null;if(acknowledged)pokePending=null;fileChips();}
 }
 function showOutgoing(requestId, text) {
  if (Array.from(items.values()).some(item => item.client_request_id === requestId)) return;
  const article = document.createElement('article');
  article.className = 'mm-message user';
  const bubble = document.createElement('div');
  bubble.className = 'mm-body';
  bubble.textContent = text;
  article.append(bubble);
  outgoing.set(requestId, article);
  el('messages').append(article);
  el('stream').scrollTop = el('stream').scrollHeight;
  updateJump();
 }
 function render(list,prepend=false){if(initial&&!prepend)voiceUI?.messages(list);const fragment=document.createDocumentFragment();for(const item of list){if(item.role==='user'&&item.client_request_id)removeOutgoing(item.client_request_id,true);newest=Math.max(newest,item.sequence);oldest=oldest===null?item.sequence:Math.min(oldest,item.sequence);if(items.has(item.id)||!['assistant','user'].includes(item.role))continue;items.set(item.id,item);const article=document.createElement('article');article.className='mm-message '+(item.role==='user'?'user':'assistant');article.dataset.sequence=item.sequence;const body=document.createElement('div');body.className='mm-body';const embedded=[];if(item.role==='assistant'&&item.format==='markdown'){DOMPurify.addHook('uponSanitizeAttribute',(node,data)=>{if(node.tagName!=='IMG')return;if(data.attrName==='src'){try{const u=new URL(data.attrValue,location.origin),m=u.pathname.match(/^\/v1\/platform\/sessions\/([^/]+)\/(artifacts|attachments)\/([^/]+)\/(?:download|preview|content)$/);if(u.origin===location.origin&&m&&decodeURIComponent(m[1])===sid)embedded.push({kind:m[2],ref:{session_id:sid,id:decodeURIComponent(m[3]),artifact_id:decodeURIComponent(m[3]),media_type:'image/png',filename:node.getAttribute('alt')||'Image'}});}catch(_){}data.keepAttr=false;}if(data.attrName==='srcset')data.keepAttr=false;});try{body.innerHTML=DOMPurify.sanitize(marked.parse(item.content||''),{FORBID_TAGS:['iframe','video','audio','object','style','svg','math'],FORBID_ATTR:['style','srcset','poster']});}finally{DOMPurify.removeHook('uponSanitizeAttribute');}}else body.textContent=item.content||'';for(const image of body.querySelectorAll('img'))image.remove();for(const a of body.querySelectorAll('a')){let url;try{url=new URL(a.getAttribute('href'),location.origin);}catch(_){a.removeAttribute('href');continue;}if(!['http:','https:'].includes(url.protocol)){a.removeAttribute('href');continue;}if(url.origin===location.origin&&url.pathname.startsWith('/v1/platform/')){a.removeAttribute('href');continue;}a.target='_blank';a.rel='noopener noreferrer';}article.append(body);const shown=new Set();for(const entry of [...embedded,...(item.attachments||[]).map(ref=>({ref,kind:'attachments'})),...(item.artifacts||[]).map(ref=>({ref,kind:'artifacts'}))]){const key=entry.kind+':'+(entry.ref.artifact_id||entry.ref.id);if(shown.has(key))continue;shown.add(key);media(article,entry.ref,entry.kind);}if(item.role==='assistant'){const toolbar=document.createElement('div');toolbar.className='mm-message-actions';article.append(toolbar);const read=document.createElement('button');read.type='button';read.className='mm-read-reply';read.textContent=t('读出','Read aloud');read.setAttribute('aria-label',t('读出回复','Read reply'));read.setAttribute('aria-pressed','false');const readBot=bot.id,readSession=sid;read.onclick=()=>void window.AI2AppsMobileBotVoice.readReply({botId:readBot,sessionId:readSession,text:item.content,button:read,label:t,onError:error,onSetup:openVoiceSettings});toolbar.append(read);window.AI2AppsConversationTrim?.attach({toolbar,botId:bot.id,sessionId:sid,item,previewText:body.textContent,request:(path,method,body)=>api(path,method,body),label:t,refresh:async result=>{conversationRevision=result?.conversation_revision??conversationRevision;for(const id of result?.retired_request_ids||[])removeOutgoing(id,true);resetHistory();await poll();},onError:error});}fragment.append(article);}if(prepend)el('messages').prepend(fragment);else el('messages').insertBefore(fragment,outgoing.values().next().value||null);updateJump();}
 function resetHistory(){window.AI2AppsMobileBotVoice?.stopRead();void voiceUI?.stop();el('messages').replaceChildren(...outgoing.values());items.clear();newest=0;oldest=null;hasOlder=false;}
 function historyChanged(page){const revision=page.conversation_revision??0;if(conversationRevision!==undefined&&conversationRevision!==revision){conversationRevision=revision;resetHistory();return true;}conversationRevision=revision;return false;}
 function divider(){if(!unread.first_unread_sequence||el('messages').querySelector('.mm-unread-line'))return;const target=el('messages').querySelector('[data-sequence="'+unread.first_unread_sequence+'"]');if(target){const d=document.createElement('div');d.className='mm-unread-line';d.textContent=t('以下是未读消息','Unread messages');target.before(d);}}
 async function markRead(){if(!initial||!bot||readBusy||document.hidden||!bottom()||newest<=(unread.read_sequence||0))return;const e=epoch,b=bot.id,s=sid,through=newest;readBusy=true;try{const result=await api('/bots/'+b+'/read','POST',{session_id:s,through_sequence:through});if(e!==epoch)return;unread=result;if(!result.unread_count)el('messages').querySelector('.mm-unread-line')?.remove();await loadBots();}catch(e){error(e);}finally{readBusy=false;}}
 const questionCards=new Map(),answeredQuestions=new Set();
 function work(value){
  voiceUI?.observe(value.runs||[]);sessions=value.task_sessions||[];const host=el('work'),visible=new Set();host.querySelector('.mm-conversation-loading')?.remove();
  for(const run of value.runs||[]){if(terminal.has(run.status))continue;
   const item=(run.interactions||[]).find(i=>!answeredQuestions.has(i.id));
   if(!item){const receipt=[...questionCards].find(([,card])=>card.dataset.questionRun===run.id&&card.dataset.interactionState==='submitted');if(receipt){visible.add(receipt[0]);continue;}}
   const question=item&&['text','menu'].includes(item.kind)&&item.request?.question_id;
   const key=question?item.id:run.id;visible.add(key);let block=questionCards.get(key);
   if(!block){block=document.createElement('div');block.className='mm-wait';questionCards.set(key,block);host.append(block);
    if(question){block.classList.add('bot-interaction-card');block._botInteractionKey=item.id;block.dataset.questionRun=run.id;
     if(run.task_context){const context=document.createElement('p');context.textContent=t('正在处理：','Task: ')+run.task_context.task;block.append(context);}
     const selectedBot=bot.id,selectedSession=sid;
     window.AI2AppsBotInteractions.answerForm({root:block,item,label:t,onError:error,
      submit:(response,responseId)=>api('/bots/'+encodeURIComponent(selectedBot)+'/runs/'+encodeURIComponent(run.id)+'/questions/'+encodeURIComponent(item.id)+'/respond','POST',{session_id:selectedSession,response_id:responseId,response}),
      onSubmitted:id=>{answeredQuestions.add(id);void poll();}});
    }
   }
   if(!question)block.textContent=run.interactions?.length?t('此任务需要确认或补充参数，请在桌面 Messager 中处理；你可以继续聊天。','This task needs confirmation or parameters. Open desktop Messager to respond; you can keep chatting.'):(run.text||run.title||t('处理中…','Working…'));
   if(!question&&run.job_id){const stop=document.createElement('button');stop.textContent=t('停止任务','Stop task');stop.onclick=async()=>{stop.disabled=true;try{await api('/bots/'+bot.id+'/jobs/'+run.job_id+'/cancel','POST',{});await poll();}catch(e){error(e);}finally{stop.disabled=false;}};block.append(stop);}
  }
  for(const [key,block] of questionCards){if(!visible.has(key)){block._botInteractionKey=null;block.remove();questionCards.delete(key);}}
 }

 async function poll(){if(!bot||!sid||!initial||loading||document.hidden)return;loading=true;const e=epoch,b=bot.id,s=sid,follow=bottom();try{for(let n=0;n<4;n++){const page=await api('/bots/'+b+'/messages?session_id='+encodeURIComponent(s)+'&after='+newest);if(e!==epoch)return;if(historyChanged(page))continue;render(page.items);if(!page.has_more)break;}const state=await api('/bots/'+b+'/state?session_id='+encodeURIComponent(s));if(e!==epoch)return;unread=state.unread;work(state);if(follow)el('stream').scrollTop=el('stream').scrollHeight;else divider();updateJump();await markRead();}catch(err){if(e===epoch)error(err);}finally{loading=false;}}
 async function older(){if(page!=='chat-page'||!bot||!hasOlder||loading)return;loading=true;const e=epoch,stream=el('stream'),height=stream.scrollHeight,top=stream.scrollTop;try{const page=await api('/bots/'+bot.id+'/messages?session_id='+encodeURIComponent(sid)+'&before='+oldest);if(e!==epoch)return;if(historyChanged(page)){setTimeout(poll,0);return;}render(page.items,true);hasOlder=page.has_more;el('older').hidden=!hasOlder;stream.scrollTop=top+stream.scrollHeight-height;}catch(e){error(e);}finally{loading=false;}}
 function fileChips(){el('back').disabled=sending||uploading;el('files').replaceChildren();for(const f of files){const remove=document.createElement('button');remove.type='button';remove.textContent=f.filename+' ×';remove.onclick=()=>{files=files.filter(x=>x.id!==f.id);fileChips();};el('files').append(remove);}voiceUI?.sync();el('send').disabled=!initial||!sid||sending||uploading||!!voiceUI?.blocked();el('attach').disabled=!initial||!sid||uploading;el('attach').hidden=false;el('poke').hidden=bot?.definition?.execution_mode==='flash';el('poke').disabled=!initial||!sid||sending||uploading||!!pokeAwaitingReceipt;el('input').maxLength=bot?.definition?.execution_mode==='flash'&&!bot.definition?.config?.plan?512:16000;el('input').placeholder=bot?.definition?.execution_mode==='flash'?bot.definition?.config?.plan?.usage||t('数学表达式，例如 (2 + 3) * 4','Expression, e.g. (2 + 3) * 4'):t('发消息…','Message…');}
 async function open(selected,{restore=false,animate=true}={}){window.AI2AppsMobileBotVoice?.stopRead();voiceUI?.dispose();voiceUI=null;if(selected.definition?.execution_mode==='app_shortcut'){await window.AI2AppsAppShortcuts.open(selected.id);return;}lastRoute='chat';if(bot)drafts.set(bot.id,el('input').value);const e=++epoch;initial=false;bot=selected;sid='';conversationRevision=undefined;newest=0;oldest=null;items.clear();outgoing.clear();questionCards.clear();answeredQuestions.clear();hasOlder=false;files=[];pending=null;pokePending=null;pokeAwaitingReceipt=null;detailReady=false;conversationRoute=null;showPage('chat-page',false,animate);if(!restore)pushNavigation(1);chrome(false);el('back').hidden=false;el('title').textContent=bot.name;el('messages').replaceChildren();el('work').replaceChildren();const loadingNotice=document.createElement('span');loadingNotice.className='mm-conversation-loading';loadingNotice.textContent=t('正在读取对话…','Loading conversation…');el('work').append(loadingNotice);el('input').value=drafts.get(bot.id)||'';el('send').disabled=true;fileChips();const opened=await api('/open','POST',{bot_id:bot.id});if(e!==epoch)return;sid=opened.session_id;profileModel=opened.profile||null;el('details').hidden=false;chrome(false);const state=await api('/bots/'+bot.id+'/state?session_id='+encodeURIComponent(sid));if(e!==epoch)return;unread=state.unread;const page=await api('/bots/'+bot.id+'/messages?session_id='+encodeURIComponent(sid)+(unread.unread_count?'&after='+Math.max(0,unread.first_unread_sequence-1):''));if(e!==epoch)return;historyChanged(page);render(page.items);hasOlder=unread.unread_count?(oldest||1)>1:page.has_more;el('older').hidden=!hasOlder;work(state);divider();const line=el('messages').querySelector('.mm-unread-line');el('stream').scrollTop=line?line.offsetTop-el('stream').offsetTop:el('stream').scrollHeight;initial=true;attachVoice();fileChips();updateJump();await markRead();void poll();}
 async function openVoiceSettings(){await details();const target=root.querySelector('[data-voice-settings]');if(target){target.open=true;target.scrollIntoView({block:'center'});}}
 function attachVoice(){if(voiceUI||!bot||!sid||bot.definition?.execution_mode==='flash'||!window.AI2AppsMobileBotVoice)return;
  const b=bot.id,s=sid;voiceUI=window.AI2AppsMobileBotVoice.create({botId:b,sessionId:s,form:el('composer'),input:el('input'),controls:root.querySelector('.mm-composer-actions'),attach:el('attach'),poke:el('poke'),send:el('send'),api,getModel:()=>profileModel?.effective_model||profileModel?.model_id||'',isBusy:()=>sending||uploading,getFiles:()=>files,removeFiles:ids=>{files=files.filter(f=>!ids.includes(f.id));fileChips();},onAccepted:()=>{if(bot?.id===b&&sid===s)void poll();},label:t,onError:error,onSetup:openVoiceSettings});
 }
 async function poke(){if(!bot||!sid||sending||pokeAwaitingReceipt||uploading||bot.definition?.execution_mode==='flash')return;const b=bot.id,e=epoch;pokePending=pokePending||{session_id:sid,request_id:crypto.randomUUID(),language:document.documentElement.lang};const submission=pokePending;pokeAwaitingReceipt=submission.request_id;fileChips();showOutgoing(submission.request_id,'👋 Poke');try{await api('/bots/'+b+'/poke','POST',submission,clockHeaders());if(e===epoch){await poll();}}catch(err){if(e===epoch){removeOutgoing(submission.request_id);error(err);}}finally{fileChips();}}

 async function send(event) {
  event.preventDefault();
  const input = el('input');
  if (!initial || !bot || !sid || sending || uploading || voiceUI?.blocked() || (!input.value.trim() && !files.length)) return;
  const draft = input.value;
  const text = draft.trim() || t('请查看附件','Please review the attachments');
  const e = epoch, b = bot.id;
  const body = {session_id:sid,text,attachments:files.map(f=>f.id),language:document.documentElement.lang};
  if (!pending || JSON.stringify(pending.body) !== JSON.stringify(body)) {
   pending = {body,request_id:crypto.randomUUID()};
  }
  const submission = pending;
  sending = true;
  showOutgoing(submission.request_id, text);
  fileChips();
  try {
   const response = await api('/bots/'+b+'/turns','POST',{...body,request_id:submission.request_id},clockHeaders());
   if (e !== epoch) return;
   if (input.value === draft) input.value = '';
   drafts.delete(b);
   files = files.filter(file => !body.attachments.includes(file.id));
   pending = null;
   if (response.kind === 'workflow_review') {
    await poll();
    const updated = await window.AI2AppsBotCreation.reviewConversation({response,botId:b,sessionId:sid,request:api});
    if (e !== epoch) return;
    if (updated) Object.assign(bot,updated);
   }
   await poll();
  } catch (err) {
   if (e === epoch) {
    if (pending === submission) removeOutgoing(submission.request_id);
    error(err);
   }
  } finally {
   sending = false;
   fileChips();
  }
 }
 async function upload(event){const e=epoch,b=bot?.id,s=sid;if(!b||!s)return;uploading=true;fileChips();try{for(const f of [...event.target.files].slice(0,8-files.length)){if(f.size>(f.type.startsWith('image/')?8:20)*1024*1024)throw Error(t('附件过大','Attachment is too large'));const data=new FormData();data.append('file',f);const result=await api('/bots/'+b+'/attachments?session_id='+encodeURIComponent(s),'POST',data);if(e!==epoch)return;files.push(result);fileChips();}}catch(err){error(err);}finally{event.target.value='';uploading=false;fileChips();}}
 function section(title){const d=document.createElement('details'),h=document.createElement('summary'),body=document.createElement('div');h.textContent=title;d.append(h,body);el('details-content').append(d);return {d,body};}
 function line(parent,text){const p=document.createElement('p');p.textContent=text;parent.append(p);return p;}
 async function details(push=true,animate=true){void voiceUI?.stop();if(!bot||!initial||backPending)return;const e=epoch,b=bot,request=++detailsRequest;const dialog=el('details-panel');el('details-title').textContent=b.name;el('details-content').textContent=t('正在加载…','Loading…');detailReady=false;showPage('details-panel',false,animate);if(push)pushNavigation(2);try{const value=await api('/bots/'+b.id+'/details');if(e!==epoch||request!==detailsRequest)return;profileModel=value.model;el('details-content').replaceChildren();const profile=section(t('身份设定','Profile'));profile.d.open=true;
 line(profile.body,t('Bot头像','Bot Avatar'));const avatar=document.createElement('img');avatar.className='mm-profile-avatar';avatar.src=b.avatar?.kind==='image'?resource('/bots/'+encodeURIComponent(b.id)+'/avatar'):AI2AppsBotAvatars.url(b);avatar.alt=t('Bot头像','Bot Avatar');profile.body.append(avatar);
 const name=document.createElement('input'),duty=document.createElement('textarea'),select=document.createElement('select');name.value=value.identity.name;name.maxLength=64;duty.value=value.identity.duty;duty.maxLength=600;duty.rows=4;select.id='mm-model';select.add(new Option(value.model.effective_model||t('未配置','Not configured'),value.model.effective_model||''));
 const flash=b.definition?.execution_mode==='flash';if(flash){duty.readOnly=false;line(profile.body,t('固定工作流：','Fixed workflow: ')+b.definition.config.workflow_id+' · '+b.definition.config.workflow_version);}for(const [label,input] of [[t('名字','Name'),name],[t('职责','Role'),duty],...(!flash?[[t('对话模型','Conversation model'),select]]:[])]){const l=document.createElement('label');l.textContent=label;l.append(input);profile.body.append(l);}
 // Catalog is optional: the saved model works even if discovery fails.
 if(!flash)void api('/models').then(catalog=>{if(e!==epoch||!select.isConnected)return;modelCatalog=catalog;const selected=value.model.effective_model||'';select.replaceChildren();for(const m of catalog.data||[])select.add(new Option(m.display_name||m.name||m.id,m.id));if(selected&&![...select.options].some(o=>o.value===selected))select.add(new Option(selected,selected));select.value=selected;}).catch(()=>{});
 const effort=document.createElement('select');let effortRequest=0,savingProfile=false;
 function setEfforts(levels,selected){
  effort.replaceChildren(...['',...(levels||[])].map(level=>new Option(AI2AppsConversationModelPolicy.reasoningLabel(level,document.documentElement.lang),level)));
  effort.value=selected||'';effort.disabled=effort.options.length<=1||savingProfile;
 }
 if(!flash){
  const label=document.createElement('label');label.textContent=t('思考档位','Thinking level');effort.setAttribute('aria-label',label.textContent);label.append(effort);profile.body.append(label);
  setEfforts(value.model.supported_reasoning_efforts,value.model.reasoning_effort);
  select.onchange=async()=>{
   const rev=++effortRequest,id=select.value;
   if(id===profileModel.effective_model){setEfforts(profileModel.supported_reasoning_efforts,profileModel.reasoning_effort);return;}
   setEfforts([]);
   if(!id)return;
   try{
    const response=await api('/bots/'+b.id+'/reasoning-efforts?model_id='+encodeURIComponent(id));
    if(e===epoch&&request===detailsRequest&&rev===effortRequest&&id!==profileModel.effective_model)setEfforts(response.supported_reasoning_efforts);
   }catch(err){if(e===epoch&&request===detailsRequest&&rev===effortRequest)error(err);}
  };
 }
 if(b.template_id){const reset=document.createElement('button');reset.type='button';reset.textContent=t('填入默认职责','Use default Role');reset.onclick=async()=>{const draft=duty.value;reset.disabled=true;try{const v=await api('/creation/options'),template=v.templates?.find(x=>x.id===b.template_id);if(template&&e===epoch&&request===detailsRequest&&draft===duty.value)duty.value=t(template.role.zh,template.role.en);}catch(err){error(err);}finally{reset.disabled=false;}};profile.body.append(reset);}
 const save=document.createElement('button');save.className='mm-primary';save.textContent=t('保存','Save');save.onclick=async()=>{save.disabled=true;savingProfile=true;select.disabled=true;effort.disabled=true;try{if(flash&&duty.value.trim()!==b.duty){const catalog=await api('/models'),m=b.definition.config.model||AI2AppsConversationModelPolicy.agentDefault(AI2AppsConversationModelPolicy.agentOptions(catalog.data||[]),catalog.defaults?.work_agent,[catalog.defaults?.work_standard,catalog.defaults?.work_complex]);if(!m)throw Error(t('请先配置执行模型','Configure an execution model'));const access=await api('/bots/'+b.id+'/app-access'),apps=access.items.filter(a=>a.enabled).map(a=>({app_id:a.app_id,enabled:true}));const review=await AI2AppsBotCreation.reviewWorkflow({request:api,role:duty.value.trim(),model:m,apps});if(!review)return;b.definition=await api('/bots/'+b.id+'/flash-workflow','POST',{role:duty.value.trim(),model:m,apps,review_id:review.review_id,expected_revision:b.definition.revision});}await api('/bots/'+b.id+'/profile','PATCH',{name:name.value,duty:duty.value});if(!flash&&select.value&&(select.value!==profileModel.effective_model||(effort.value||null)!==(profileModel.reasoning_effort??null))){profileModel=await api('/bots/'+b.id+'/conversation-model','PUT',{model_id:select.value,revision:profileModel.revision,reasoning_effort:effort.value||null});setEfforts(profileModel.supported_reasoning_efforts,profileModel.reasoning_effort);}b.name=name.value;b.duty=duty.value;el('title').textContent=b.name;el('details-title').textContent=b.name;save.textContent=t('已保存','Saved');await loadBots();}catch(err){error(err);}finally{savingProfile=false;save.disabled=false;select.disabled=false;effort.disabled=effort.options.length<=1;}};profile.body.append(save);
 const tasks=section(t('任务会话','Tasks'));tasks.d.open=true;for(const item of sessions){const row=document.createElement('div');row.className='mm-detail-task';line(row,item.title);line(row,item.summary||item.status||'');const resume=document.createElement('button');resume.textContent=t('继续此任务','Continue task');resume.onclick=()=>{
  const input=el('input'),prefix=t('继续 ','Continue ')+'/#'+item.id+' ';
  const rest=input.value.replace(/^\s*(?:继续|续接|continue)\s+\/#(?:"[^"\n]+"|[^\s"<>，。！？：；、（）【】,.!?:;()\[\]]+)\s*/i,'');
  if(prefix.length+rest.length>input.maxLength){error(Error(t('草稿太长，无法插入任务引用。','The draft is too long to insert a task reference.')));return;}
  input.value=prefix+rest;backToConversation();input.focus({preventScroll:true});input.setSelectionRange(prefix.length,prefix.length);
 };row.append(resume);const usage=document.createElement('details'),heading=document.createElement('summary'),body=document.createElement('div');heading.textContent=t('此任务累计用量','Task lifetime usage');usage.append(heading,body);let read=false;usage.ontoggle=async()=>{if(!usage.open||read)return;read=true;try{const v=await api('/bots/'+b.id+'/statistics?task_session_id='+encodeURIComponent(item.id));line(body,t('执行次数：','Executions: ')+v.executions);if(v.task_usage){const format=(value,known)=>value!=null?window.formatMessagerUsage(value):known==null?t('未知','Unk.'):'>'+window.formatMessagerUsage(known,true);for(const [key,zh,en] of [['task','任务自身','Task itself'],['aaat','AaAT','AaAT'],['delegated','委派 Bot','Delegated Bots'],['total','总计','Total']]){const row=v.task_usage[key];line(body,t(zh,en)+' · Tokens: '+format(row.tokens,row.known_tokens)+' · Points: '+format(row.points,row.known_points));}}line(body,t('任务自身 BYOK：','Task BYOK: ')+(Object.entries(v.usage.currency_costs).map(([k,v])=>k+' '+v).join(' · ')||t('未报告','Not reported')));}catch(err){read=false;error(err);}};row.append(usage);tasks.body.append(row);}if(!sessions.length)line(tasks.body,t('暂无任务','No tasks.'));
 const stats=section(t('统计与用量','Statistics & usage')),period=document.createElement('select');period.setAttribute('aria-label',t('统计时间范围','Statistics period'));for(const [id,name] of [['today',t('今日','Today')],['7d',t('过去7天','Past 7 days')],['30d',t('过去30天','Past 30 days')],['all',t('全部历史','All history')]])period.add(new Option(name,id));stats.body.append(period);const report=document.createElement('div');stats.body.append(report);let statsRevision=0;async function refreshStats(){const rev=++statsRevision;try{const v=await api('/bots/'+bot.id+'/statistics?period='+period.value+'&timezone_name='+encodeURIComponent(Intl.DateTimeFormat().resolvedOptions().timeZone));if(rev!==statsRevision)return;report.replaceChildren();line(report,t('执行的任务 / 次数：','Tasks run / executions: ')+v.tasks+' / '+v.executions);line(report,t('已完成 / 进行中：','Completed / active: ')+v.completed+' / '+v.active);line(report,'Tokens: '+(v.usage.unreported_model_calls?'≥ ':'')+window.formatMessagerUsage(v.usage.input_tokens+v.usage.output_tokens,Boolean(v.usage.unreported_model_calls)));line(report,'Cloud Points: '+(v.usage.known_charged_points==null?t('未报告','Not reported'):window.formatMessagerUsage(v.usage.known_charged_points)));line(report,'BYOK: '+(Object.entries(v.usage.currency_costs).map(([k,v])=>k+' '+v).join(' · ')||t('未报告','Not reported')));line(report,(v.start?new Date(v.start).toLocaleString():t('全部历史','All history'))+' — '+new Date(v.end).toLocaleString());line(report,t('仅统计此 Bot 已记录用量，含有结算记录的失败调用。未知费用不代表免费。','Recorded own usage, including billed failures. Unreported charges do not mean free.'));}catch(e){error(e);}}period.onchange=refreshStats;void refreshStats();
 const access=section(t('App 访问权限','App access'));for(const item of (value.access?.items||[]).filter(item=>item.selected)){line(access.body,(item.name||item.app_id)+' · '+(item.enabled?t('已允许','Allowed'):t('已关闭','Disabled')));}if(!access.body.children.length)line(access.body,t('尚未授权 App 或 Mini-App','No App or Mini-App access.'));line(access.body,t('权限修改与审批请在桌面处理。','Manage access and approvals on the desktop.'));
 const memory=section(t('记忆','Memory'));for(const item of value.memories?.items||[])if(!item.deleted)line(memory.body,item.text||item.content||'');if(!memory.body.children.length)line(memory.body,t('暂无记忆','No memories.'));
 const voice=section(t('语音与对话模式','Voice and conversation'));voice.d.dataset.voiceSettings='true';if(voiceUI)void voiceUI.settings(voice.body).catch(error);else line(voice.body,t('此Bot不支持对话模式','Conversation mode unavailable for this Bot'));
 const notifications=section(t('任务与提醒策略','Task notifications'));for(const [key,label] of [['success',t('任务完成','Task completed')],['failure',t('任务失败','Task failed')],['waiting',t('需要协助','Needs assistance')],['reminder',t('提醒','Reminders')]])if(value.notifications?.policy&&key in value.notifications.policy)line(notifications.body,label+' · '+(value.notifications.policy[key]?t('开启','On'):t('关闭','Off')));line(notifications.body,t('提醒策略可在桌面修改。','Manage notification settings on the desktop.'));
 detailReady=true;
 }catch(err){if(e===epoch&&request===detailsRequest)el('details-content').textContent=err.message;}}
 el('create').setAttribute('aria-label',t('新建 Bot','Create Bot'));el('create').onclick=()=>{if(creationMenu){creationMenu.dispose();creationMenu=null;return;}creationMenu=window.AI2AppsBotCreation.menu(el('create'),{below:true,onAddGroup:()=>groupDialog(),onClose:()=>{creationMenu=null;},onChoose:type=>{creationMenu=null;beginCreation(true,true,type);}});};
 el('details').setAttribute('aria-label',t('Bot 详情与设置','Bot details and settings'));el('details').onclick=()=>details().catch(error);el('details-back').setAttribute('aria-label',t('返回对话','Back to conversation'));el('details-back').onclick=()=>backToConversation();
 el('title').textContent=t('消息','Messager');el('back').setAttribute('aria-label',t('返回机器人列表','Back to Bots'));el('input').placeholder=t('发消息…','Message…');el('older').textContent=t('加载更早消息','Earlier messages');el('bottom').title=el('bottom').ariaLabel=t('滚动到消息末尾','Scroll to latest message');el('send').setAttribute('aria-label',t('发送','Send'));el('attach').setAttribute('aria-label',t('添加附件','Add attachments'));
 el('poke').onclick=poke;el('poke').setAttribute('aria-label',t('唤醒 Bot','Poke Bot'));el('composer').onsubmit=send;el('attach').onclick=()=>el('upload').click();el('upload').onchange=upload;el('back').onclick=()=>backToList();el('older').onclick=older;el('bottom').onclick=()=>{el('stream').scrollTop=el('stream').scrollHeight;updateJump();markRead().catch(error);};el('stream').onscroll=()=>{updateJump();if(el('stream').scrollTop<60)void older();void markRead();};el('stream').addEventListener('load',updateJump,true);document.addEventListener('visibilitychange',()=>{if(!document.hidden){void refreshList();void poll();}});window.visualViewport?.addEventListener('resize',dimensions);window.addEventListener('resize',dimensions);dimensions();chrome(true);loadBots().catch(error);timer=setInterval(()=>{if(!document.hidden&&bot)void poll();},2000);listTimer=setInterval(()=>{if(!document.hidden&&!bot)void refreshList();},5000);window.addEventListener('pagehide',()=>{voiceUI?.dispose();voiceUI=null;clearInterval(timer);clearInterval(listTimer);},{once:true});
})();
