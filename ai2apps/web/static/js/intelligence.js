(() => {
'use strict';
const lt=window.IntelligenceI18n?.text||(s=>s),it=window.IntelligenceI18n?.template||((parts,...values)=>parts.reduce((s,p,i)=>s+p+(i<values.length?values[i]:''),''));
const systemMessage=window.IntelligenceI18n?.message||(s=>s);
const $ = s => document.querySelector(s);
let appHandoff = null;
let channelHandoff = null;
let openingHandoff = false;
const handoffText=(zh,en)=>document.documentElement.lang.startsWith('zh')?zh:en;
const handoffPanel=document.createElement('aside');
handoffPanel.className='intel-help';handoffPanel.hidden=true;
document.querySelector('.intel-main').prepend(handoffPanel);
function renderHandoff(){
 handoffPanel.replaceChildren();handoffPanel.hidden=!appHandoff;
 if(!appHandoff)return;
 const text=document.createElement('p');text.textContent=handoffText('来自 Agent 的频道创建任务。创建后可先添加信息源并刷新采集，再返回生成简报。关闭页面不会取消任务。','Channel requested by an Agent. Create it, add sources and collect news, then return for a briefing. Closing the page keeps the task pending.');handoffPanel.append(text);
 const button=(zh,en,fn)=>{const b=document.createElement('button');b.textContent=handoffText(zh,en);b.onclick=async()=>{b.disabled=true;try{await fn();}catch(e){text.textContent=e.message;}finally{b.disabled=false;}};handoffPanel.append(b);return b;};
 button(appHandoff.channel?'频道设置':'创建频道',appHandoff.channel?'Channel settings':'Create channel',()=>openHandoffDialog());
 const continueButton=button('返回 Agent 继续','Return and continue',async()=>{
  const handoff=appHandoff;
  await api('/handoffs/'+encodeURIComponent(handoff.run_id)+'/'+encodeURIComponent(handoff.interaction_id)+'/complete','POST',{});
  await window.ai2appsShell.openHandoff(handoff.run_id,handoff.interaction_id,true);
  if(appHandoff===handoff){appHandoff=null;renderHandoff();}
 });
 continueButton.disabled=!appHandoff.channel;
 button('暂时返回（保留任务）','Return without completing',()=>window.ai2appsShell.openHandoff(appHandoff.run_id,appHandoff.interaction_id,true));
}
async function openHandoffDialog(){
 const handoff=appHandoff;
 if(handoff.channel){await channelDialog(handoff.channel);return;}
 await channelDialog();
 channelHandoff=handoff;
 const p=handoff.parameters;
 $('#channel-name').value=p.name||'';$('#channel-interests').value=p.interests||'';$('#channel-excluded').value=p.excluded||'';
}
window.addEventListener('ai2apps:host-context',async event=>{
 const intent=event.detail?.appInteraction;
 if(!intent||intent.returning||openingHandoff||appHandoff?.interaction_id===intent.interactionId)return;
 openingHandoff=true;
 try{
  const response=await fetch('/v1/platform/agent-runs/'+encodeURIComponent(intent.runId)+'/interactions/'+encodeURIComponent(intent.interactionId)+'/handoff',{credentials:'same-origin'});
  if(!response.ok)throw Error('App interaction is unavailable');
  const value=await response.json();
  if(value.target.app_id!=='ai2apps.intelligence'||value.target.mini_app_id||value.status!=='pending')return;
  const progress=await api('/handoffs/'+encodeURIComponent(intent.runId)+'/'+encodeURIComponent(intent.interactionId));
  appHandoff={...value,channel:progress.channel};
  if(progress.channel){channelId=progress.channel.id;await refresh();}
  renderHandoff();
 }catch(error){console.warn(error.message);}finally{openingHandoff=false;}
});

// Compare authored markup, not browser-normalized DOM (Lucide replaces icons).
const renderedMarkup=new WeakMap();
function setHTML(root,markup){
 const scope=root.id==='intel-article-reader'?(previewDraft?'draft:'+previewDraft.id:selectedId?'article:'+selectedId:''):channelId;
 const previous=renderedMarkup.get(root);
 if(previous===markup&&root.dataset.renderScope===String(scope||''))return false;
 const preserve=previous!==undefined&&root.dataset.renderScope===String(scope||'');
 const expanded=preserve?[...root.querySelectorAll('details[open]')].map(d=>d.querySelector('summary')?.textContent):[];
 const scroll=root.closest('.intel-main,.intel-reader')||root;
 const top=scroll.scrollTop,left=root.scrollLeft;
 let reconciled=false;
 if(preserve&&root.id==='intel-content'&&root.classList.contains('intel-article-grid')){
  const old=document.createElement('template'),next=document.createElement('template');
  old.innerHTML=previous;next.innerHTML=markup;
  const before=[...old.content.children].filter(n=>n.hasAttribute('data-article'));
  const after=[...next.content.children].filter(n=>n.hasAttribute('data-article'));
  const live=new Map([...root.children].filter(n=>n.hasAttribute('data-article')).map(n=>[n.dataset.article,n]));
  const authored=new Map(before.map(n=>[n.dataset.article,n]));
  if(before.length&&after.length&&live.size===before.length){
   const contentSignature=node=>{const copy=node.cloneNode(true);copy.classList.remove('selected');copy.removeAttribute('aria-label');copy.querySelector('.intel-unread-ribbon')?.remove();copy.querySelector('.intel-card-favorite')?.remove();return copy.outerHTML;};
   const wanted=new Set(after.map(node=>node.dataset.article));
   for(const [id,card] of live)if(!wanted.has(id)){card.remove();live.delete(id);}
   after.forEach((node,index)=>{
    const id=node.dataset.article,existing=live.get(id),prior=authored.get(id);let card=existing;
    if(!existing)card=node;
    else if(prior.outerHTML!==node.outerHTML){
     if(contentSignature(prior)===contentSignature(node)){
      // Read/selection changes must not recreate cards or reload their images.
      existing.classList.toggle('selected',node.classList.contains('selected'));
      existing.setAttribute('aria-label',node.getAttribute('aria-label'));
      syncCardFavorite(existing,node);
      const ribbon=existing.querySelector('.intel-unread-ribbon'),nextRibbon=node.querySelector('.intel-unread-ribbon');
      if(ribbon&&!nextRibbon&&!ribbon.classList.contains('is-leaving')){
       if(window.matchMedia('(prefers-reduced-motion: reduce)').matches)ribbon.remove();
       else if(mobileQuery.matches&&mobilePage!=='channel')ribbon.classList.add('is-pending-read');
       else animateUnreadRibbonExit(ribbon);
      }else if(ribbon&&nextRibbon){if(ribbon.classList.contains('is-leaving')||ribbon.classList.contains('is-pending-read'))animateUnreadRibbonEnter(ribbon);}
      else if(!ribbon&&nextRibbon){existing.append(nextRibbon);animateUnreadRibbonEnter(nextRibbon);}
     }else{card=node;existing.replaceWith(card);}
    }
    if(root.children[index]!==card)root.insertBefore(card,root.children[index]||null);
    live.delete(id);
   });
   for(const card of live.values())card.remove();
   const more=root.querySelector(':scope > .intel-list-more'),nextMore=next.content.querySelector('.intel-list-more');
   if(!nextMore)more?.remove();else if(!more)root.append(nextMore);else if(more.outerHTML!==nextMore.outerHTML)more.replaceWith(nextMore);
   reconciled=true;
  }
 }
 if(!reconciled)root.innerHTML=markup;
 renderedMarkup.set(root,markup);root.dataset.renderScope=String(scope||'');
 if(preserve){for(const d of root.querySelectorAll('details'))if(expanded.includes(d.querySelector('summary')?.textContent))d.open=true;scroll.scrollTop=top;root.scrollLeft=left;}
 else if(root.id==='intel-article-reader'){scroll.scrollTop=0;root.scrollLeft=0;}
 return true;
}

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const when = s => s ? new Date(s).toLocaleString(window.IntelligenceI18n?.locale||'zh-CN',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : lt('尚未更新');
const labels = {running:lt('正在更新'),completed:lt('更新完成'),partial:lt('部分完成'),failed:lt('更新失败'),interrupted:lt('连接中断'),cancelled:lt('已停止'),success:lt('成功'),needs_user:lt('需要协助'),restricted:lt('访问受限'),deferred:lt('等待下次检查')};
let state = {channels:[],sources:[],articles:[],runs:[]}, channelId = null, selectedId = null, tab = 'articles', sectionId = '', busy = false, editing = null, editingSource = null, profiles = [{key:"default",name:"Default"}], noticeTimer;
let readerMode='chat', mobilePanel=false, previewDraft=null, articleOpening=null;
let articleDetailScroll=0;
function animateMobileReader(from='100%'){
 if(!mobileQuery.matches||$('#intel-app').classList.contains('intel-navigation-instant')||window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
 $('#intel-reader').animate([{transform:'translateX('+from+')'},{transform:'translateX(0)'}],{duration:240,easing:'ease-out'});
}
function showArticleDiscussion(){
 if(readerMode==='article-chat')return;
 if(readerMode==='article')articleDetailScroll=$('#intel-reader').scrollTop;
 mobilePush('reader',()=>{readerMode='article-chat';mobilePanel=true;renderChannelChat();});
 animateMobileReader();
}
function showArticleDetails(){if(mobileQuery.matches&&readerMode==='article-chat'){mobileBack();return;}const restore=readerMode==='article-chat';readerMode='article';renderReader();if(restore)$('#intel-reader').scrollTop=articleDetailScroll;}
const mobileQuery=window.matchMedia('(max-width:850px)');
let mobilePage='channels';
if(window.MobileAppDiagnostics)window.MobileAppDiagnostics.context=()=>({view:mobilePage,tab});
const mobileStack=[];
const mobileMount=new URLSearchParams(location.hash.slice(1));
const mobileHosted=()=>!!window.AI2APPS_MOBILE_SURFACE&&window.parent!==window&&!!mobileMount.get('ai2apps-mount');
let mobileBackPending=false;
const mobileRoutes=[];
function mobileRoute(){return {page:mobilePage,readerMode,selectedId,previewDraft,stack:[...mobileStack],mainScroll:$('.intel-main').scrollTop,scroll:$('#intel-reader').scrollTop};}
function mobileNavigation(type,extra={}){window.parent.postMessage({type,mountToken:mobileMount.get('ai2apps-mount'),instanceId:mobileMount.get('ai2apps-instance'),...extra},location.origin);}
window.addEventListener('message',event=>{
 if(event.source!==window.parent||event.origin!==location.origin||event.data?.mountToken!==mobileMount.get('ai2apps-mount')||event.data.type!=='ai2apps.intelligence.history')return;
 mobileBackPending=false;
 const depth=Number(event.data.depth);
 if(!Number.isInteger(depth)||depth<0)return;
 const instant=event.data.animate!==true,root=$('#intel-app');
 if(instant)root.classList.add('intel-navigation-instant');
 mobileRoutes[mobileStack.length]=mobileRoute();
 if(depth>mobileStack.length&&mobileRoutes[depth]){
  const route=mobileRoutes[depth];mobileStack.splice(0,mobileStack.length,...route.stack);
  mobilePage=route.page;readerMode=route.readerMode;selectedId=route.selectedId;previewDraft=route.previewDraft;
  mobilePanel=mobilePage==='reader';renderReader();syncMobile();$('.intel-main').scrollTop=route.mainScroll;$('#intel-reader').scrollTop=route.scroll;
 }else while(mobileStack.length>depth)mobileBack(true);
 if(instant){root.getBoundingClientRect();requestAnimationFrame(()=>requestAnimationFrame(()=>root.classList.remove('intel-navigation-instant')));}
});
function mobilePush(page,beforeReveal){
 if(!mobileQuery.matches){beforeReveal?.();return;}
 mobileRoutes.length=mobileStack.length+1;
 mobileRoutes[mobileStack.length]=mobileRoute();
 mobileStack.push({page:mobilePage,readerMode,selectedId,previewDraft,mainScroll:$('.intel-main').scrollTop,scroll:$('#intel-reader').scrollTop});
 beforeReveal?.();
 mobilePage=page;syncMobile();
 if(mobileHosted())mobileNavigation('ai2apps.intelligence.push',{depth:mobileStack.length});
}
function mobileBack(fromHistory=false){
 if(!mobileQuery.matches||(!fromHistory&&document.querySelector('dialog[open]')))return;
 if(!mobileStack.length)return;
 if(mobileHosted()&&!fromHistory){if(!mobileBackPending){mobileBackPending=true;mobileNavigation('ai2apps.intelligence.back');}return;}
 const previous=mobileStack.pop();if(!previous)return;
 const leavingArticleChat=readerMode==='article-chat'&&previous.readerMode==='article';
 mobilePage=previous.page;readerMode=previous.readerMode;selectedId=previous.selectedId;previewDraft=previous.previewDraft;
 mobilePanel=mobilePage==='reader';renderReader();syncMobile();$('#intel-reader').scrollTop=previous.scroll;$('.intel-main').scrollTop=previous.mainScroll;
 if(leavingArticleChat)animateMobileReader('-25%');
}
function animateCardFavorite(star,remove=false){
 clearTimeout(star._favoriteTimer);
 star.classList.remove('is-entering','is-leaving','is-pending-enter','is-pending-leave');
 if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){if(remove)star.remove();return;}
 if(mobileQuery.matches&&mobilePage!=='channel'){star.classList.add(remove?'is-pending-leave':'is-pending-enter');return;}
 star.classList.add(remove?'is-leaving':'is-entering');
 star._favoriteTimer=setTimeout(()=>{if(remove)star.remove();else star.classList.remove('is-entering');},320);
}
function syncCardFavorite(card,next){
 const star=card.querySelector('.intel-card-favorite'),wanted=next.querySelector('.intel-card-favorite');
 if(!star&&wanted){card.append(wanted);animateCardFavorite(wanted);}
 else if(star&&!wanted)animateCardFavorite(star,true);
 else if(star&&wanted&&(star.classList.contains('is-leaving')||star.classList.contains('is-pending-leave')))animateCardFavorite(star);
}
let cardMenu=null,cardMenuTrigger=null;
function closeCardMenu(){
 cardMenu?.remove();cardMenu=null;cardMenuTrigger?.setAttribute('aria-expanded','false');cardMenuTrigger=null;
}
function openCardMenu(trigger,point=null){
 const article=state.articles.find(a=>a.id===trigger.dataset.cardMenu);if(!article)return;
 if(cardMenuTrigger===trigger&&!point){closeCardMenu();return;}
 closeCardMenu();cardMenuTrigger=trigger;trigger.setAttribute('aria-expanded','true');
 cardMenu=document.createElement('div');cardMenu.className='intel-card-menu';cardMenu.setAttribute('role','menu');
 cardMenu.innerHTML=it`<button type="button" role="menuitem" data-card-read="${esc(article.id)}">${lt(article.read?'未读':'已读')}</button><button type="button" role="menuitem" data-card-favorite="${esc(article.id)}">${lt(article.favorite?'取消收藏':'收藏文章')}</button>`;
 $('#intel-app').append(cardMenu);
 const box=trigger.getBoundingClientRect(),menu=cardMenu.getBoundingClientRect();
 cardMenu.style.left=Math.max(8,Math.min(point?point.x:box.right-menu.width,window.innerWidth-menu.width-8))+'px';
 cardMenu.style.top=Math.max(8,Math.min(point?point.y:box.top-menu.height-6,window.innerHeight-menu.height-8))+'px';
 cardMenu.querySelector('button').focus({preventScroll:true});
}
document.addEventListener('contextmenu',event=>{
 const card=event.target.closest('.intel-story-compact[data-article]'),trigger=card?.querySelector('[data-card-menu]');
 if(!trigger)return;
 event.preventDefault();
 openCardMenu(trigger,event.clientX||event.clientY?{x:event.clientX,y:event.clientY}:null);
});
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&cardMenu){event.preventDefault();event.stopImmediatePropagation();const trigger=cardMenuTrigger;closeCardMenu();trigger?.focus({preventScroll:true});}else if(cardMenu&&['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();const items=[...cardMenu.querySelectorAll('button')],index=items.indexOf(document.activeElement);items[event.key==='Home'?0:event.key==='End'?items.length-1:(index+(event.key==='ArrowDown'?1:items.length-1))%items.length].focus();}},true);
window.addEventListener('resize',closeCardMenu);
for(const type of ['wheel','touchmove'])document.addEventListener(type,event=>{if(cardMenu&&!cardMenu.contains(event.target))closeCardMenu();},{capture:true,passive:true});
function animateUnreadRibbonEnter(ribbon){
 clearTimeout(ribbon._exitTimer);
 ribbon.classList.remove('is-leaving','is-pending-read','is-entering','is-pending-unread');
 if(window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
 if(mobileQuery.matches&&mobilePage!=='channel'){ribbon.classList.add('is-pending-unread');return;}
 ribbon.classList.add('is-entering');
 ribbon._exitTimer=setTimeout(()=>ribbon.classList.remove('is-entering'),520);
}
function animateUnreadRibbonExit(ribbon){
 clearTimeout(ribbon._exitTimer);
 ribbon.classList.remove('is-pending-read','is-entering','is-pending-unread');
 ribbon.classList.add('is-leaving');
 ribbon._exitTimer=setTimeout(()=>ribbon.remove(),520);
}
let ribbonRevealTimer;
function syncMobile(){
 const app=$('#intel-app'),isMobile=mobileQuery.matches;
 if(!channel()&&mobilePage!=='channels'){mobilePage='channels';mobileStack.length=0;}
 if(mobileHosted()){
  mobileNavigation('ai2apps.shell.set-dock-visible',{visible:!(isMobile&&mobilePage==='reader'&&['article','article-chat'].includes(readerMode))});
  mobileNavigation('ai2apps.shell.set-topbar-visible',{visible:!isMobile||mobilePage==='channels'});
 }
 app.dataset.mobilePage=mobilePage;
 clearTimeout(ribbonRevealTimer);
 if(!isMobile||mobilePage==='channel')ribbonRevealTimer=setTimeout(()=>{
  if(mobileQuery.matches&&mobilePage!=='channel')return;
  document.querySelectorAll('#intel-content .intel-unread-ribbon.is-pending-read').forEach(animateUnreadRibbonExit);
  document.querySelectorAll('#intel-content .intel-unread-ribbon.is-pending-unread').forEach(animateUnreadRibbonEnter);
  document.querySelectorAll('#intel-content .intel-card-favorite.is-pending-enter,#intel-content .intel-card-favorite.is-pending-leave').forEach(star=>animateCardFavorite(star,star.classList.contains('is-pending-leave')));
 },isMobile?320:0);

 for(const [selector,page] of [['.intel-sidebar','channels'],['.intel-main','channel'],['.intel-reader','reader']]){
  const panel=$(selector);panel.inert=isMobile&&mobilePage!==page;
 }
 $('#mobile-channel-name').textContent=channel()?.name||'';
 syncChannelRefreshStatus();
 $('#mobile-category').value=['articles','topics','drafts','runs'].includes(tab)?tab:'articles';
 $('#mobile-reader-name').textContent=readerMode==='chat'?lt('频道对话'):readerMode==='article-chat'?(window.IntelligenceArticleChat?.currentTitle()||window.IntelligenceI18n.format('chat.mini.title',{})):lt('文章详情');
 const a=state.articles.find(a=>a.id===selectedId);
 $('#mobile-article-menu').hidden=readerMode!=='article';
 setHTML($('#mobile-article-actions'),previewDraft?`<button data-draft="${esc(previewDraft.id)}">${lt('打开稿件 / 继续修改')}</button>`:a?`<button data-feedback="more" aria-pressed="${a.feedback==='more'}">👍 ${lt('顶')}</button><button data-feedback="less" aria-pressed="${a.feedback==='less'}">👎 ${lt('踩')}</button><button data-write="article" data-scope-id="${esc(a.id)}"><i data-lucide="square-pen" aria-hidden="true"></i>${lt('撰写稿件')}</button>`:'');
 $('#mobile-update').disabled=$('#collect').disabled;
}
function initMobile(){
 const back=lt('返回'),more=lt('更多');
 $('.intel-main').insertAdjacentHTML('afterbegin',`<header class="intel-mobile-bar"><button class="intel-icon" data-mobile-back aria-label="${back}"><i data-lucide="chevron-left"></i></button><div class="intel-mobile-heading"><div class="intel-mobile-channel-title-row"><small id="mobile-channel-name"></small><span id="mobile-channel-refresh-status" class="intel-refresh-status" role="status" hidden></span></div><select id="mobile-category" aria-label="${lt('切换内容')}"><option value="articles">${lt('文章')}</option><option value="topics">${lt('热点')}</option><option value="drafts">${lt('稿件')}</option></select></div><button id="mobile-chat" aria-label="${lt('频道对话')}"><i data-lucide="messages-square"></i>Chat</button><details class="intel-mobile-menu"><summary aria-label="${more}"><i data-lucide="ellipsis"></i></summary><div><button id="mobile-import">${lt('收录文章')}</button><button data-browse-posts>${lt('逐帖查看')}</button><button id="mobile-update">${lt('更新频道')}</button><button data-write="channel"><i data-lucide="square-pen" aria-hidden="true"></i>${lt('撰写稿件')}</button></div></details></header>`);
 $('#intel-reader').insertAdjacentHTML('afterbegin',`<header class="intel-mobile-bar"><button class="intel-icon" data-mobile-back aria-label="${back}"><i data-lucide="chevron-left"></i></button><strong id="mobile-reader-name"></strong><details id="mobile-article-menu" class="intel-mobile-menu"><summary aria-label="${more}"><i data-lucide="ellipsis"></i></summary><div id="mobile-article-actions"></div></details></header>`);
 $('#mobile-category').onchange=safe(async event=>{window.IntelligencePagination.reset();tab=event.target.value;render();$('.intel-main').scrollTop=0;if(progressiveData())await loadMobileChannel();if(tab==='drafts')await loadDrafts(channelId);});
 $('#mobile-chat').onclick=()=>{mobilePush('reader');selectedId=null;previewDraft=null;readerMode='chat';mobilePanel=true;renderReader();};
 $('#mobile-import').onclick=()=>$('#import-article').click();
 $('#mobile-update').onclick=()=>$('#collect').click();
 document.addEventListener('click',event=>{
  if(event.target.closest('[data-mobile-back]'))mobileBack();
  document.querySelectorAll('.intel-mobile-menu[open]').forEach(menu=>{if(!menu.contains(event.target)||event.target.closest('button'))menu.open=false;});
 });
 document.addEventListener('keydown',event=>{if(event.key==='Escape'){const menus=[...document.querySelectorAll('.intel-mobile-menu[open]')];if(menus.length)menus.forEach(m=>m.open=false);else mobileBack();}});
 // System edge gestures use Shell history. Content swipes exclude horizontal controls.
 let swipe=null;
 const layout=$('.intel-layout');
 layout.addEventListener('touchstart',event=>{const t=event.touches[0],nativeEdge=mobileHosted()&&t.clientX-layout.getBoundingClientRect().left<=24;swipe=!nativeEdge&&mobileQuery.matches&&mobilePage!=='channels'&&event.touches.length===1&&!event.target.closest('.intel-sections,input,textarea,select,.intel-mobile-menu')&&!document.querySelector('dialog[open]')?{x:t.clientX,y:t.clientY}:null;},{passive:true});
 layout.addEventListener('touchend',event=>{if(!swipe)return;const t=event.changedTouches[0],dx=t.clientX-swipe.x,dy=t.clientY-swipe.y;swipe=null;if(dx>72&&dx>Math.abs(dy)*1.5){if(event.cancelable)event.preventDefault();mobileBack();}},{passive:false});
 layout.addEventListener('touchcancel',()=>{swipe=null;},{passive:true});
 mobileQuery.addEventListener('change',()=>{mobileStack.length=0;mobilePage='channels';if(mobileQuery.matches&&!['articles','topics','drafts'].includes(tab))tab='articles';render();safe(refresh)();});
}
const channelChatHost=$('#channel-chat');
const channelChatHelp=channelChatHost.querySelector('.intel-help').textContent;
const channelChatPlaceholder=$('#channel-chat-question').placeholder;
const channelChatSendLabel=$('#send-channel-chat').textContent;
channelChatHost.replaceChildren();
const channelSurface=window.AI2AppsMiniAppChat.createConversationSurface({root:channelChatHost,placeholder:channelChatPlaceholder,sendLabel:channelChatSendLabel});
channelSurface.header.hidden=true;channelSurface.model.disabled=true;
channelSurface.beforeInput.textContent=channelChatHelp;
channelSurface.messages.id='channel-chat-messages';channelSurface.messages.setAttribute('role','log');
channelSurface.form.id='channel-chat-form';channelSurface.input.id='channel-chat-question';channelSurface.input.required=true;
channelSurface.send.id='send-channel-chat';channelSurface.status.id='channel-chat-status';
const channelChatContext=document.createElement('label');channelChatContext.id='channel-chat-context';channelChatContext.htmlFor='channel-chat-question';channelChatContext.className='intel-help';channelSurface.beforeInput.append(channelChatContext);

const conversations=new Map();
const conversationState=id=>{if(!conversations.has(id))conversations.set(id,{turns:[],draft:'',loading:false,loaded:false,sending:false,error:'',requestId:null});return conversations.get(id);};
channelSurface.reset.onclick=async()=>{const id=channelId;if(!id||conversationState(id).sending)return;try{await api('/channels/'+id+'/conversation/reset','POST',{});conversations.delete(id);await loadConversation(id);renderChannelChat();}catch(error){notice(error.message);}};

const channel = () => state.channels.find(c => c.id === channelId);
const inChannel = table => state[table].filter(row => row.channel_id === channelId);
const icons = () => {const pending=[...document.querySelectorAll('i[data-lucide]')];if(!pending.length||!window.lucide)return;for(const node of pending)node.setAttribute('data-intel-new-icon',node.getAttribute('data-lucide'));window.lucide.createIcons({nameAttr:'data-intel-new-icon'});for(const node of document.querySelectorAll('[data-intel-new-icon]'))node.removeAttribute('data-intel-new-icon');};
async function requestJSON(url,options={}){
 const method=options.method||'GET',canRetry=method==='GET',requestId=crypto.randomUUID?.()||Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
 const path=new URL(url,location.origin).pathname;
 for(let attempt=0;;attempt++){
  let response,data;const started=performance.now();
  const headers=new Headers(options.headers||{});headers.set('X-AI2Apps-Request-Id',requestId);headers.set('X-AI2Apps-Request-Attempt',String(attempt));
  try{
   response=await fetch(url,{...options,headers});
   try{data=typeof response.text==='function'?JSON.parse(await response.text()):await response.json();}
   catch(cause){const error=Error(lt('连接中断')+' · '+lt('请稍后重试。'));error.code='invalid_json_response';error.cause=cause;throw error;}
   if(!response.ok){const error=Error(lt(typeof data?.detail==='string'?data.detail:data?.error?.message||it`请求失败 (${response.status})`));error.code=data?.error?.code||'http_error';throw error;}
   if(attempt)window.MobileAppDiagnostics?.record({request_id:requestId,method,path,phase:'recovered',code:'retry_succeeded',status:response.status||200,attempt,elapsed_ms:Math.min(600000,Math.round(performance.now()-started))});
   void window.MobileAppDiagnostics?.flush();
   return data;
  }catch(cause){
   const transient=(cause.code==='invalid_json_response'&&![401,403].includes(response?.status))||[408,502,503,504].includes(response?.status)||(!response&&cause.name==='TypeError');
   window.MobileAppDiagnostics?.record({request_id:requestId,method,path,phase:cause.code==='invalid_json_response'?'app_json':response?'app_http':'network',code:String(cause.code||cause.name||'unknown').replace(/[^A-Za-z0-9_.-]/g,'_').slice(0,80),status:response?.status||0,relay_status:Number(response?.headers?.get('X-AI2Apps-Relay-Status')||0),attempt,elapsed_ms:Math.min(600000,Math.round(performance.now()-started))});
   if(canRetry&&attempt===0&&transient){await new Promise(resolve=>setTimeout(resolve,400));continue;}
   console.warn('Intelligence request failed',{request_id:requestId,method,path,status:response?.status,code:cause.code||cause.name});
   const error=!response&&cause.name==='TypeError'?Error(lt('连接中断')+' · '+lt('请稍后重试。')):cause;
   error.requestId=requestId;error.requestUncertain=transient;
   const operation=path==='/v1/platform/intelligence'?lt('刷新列表'):path.endsWith('/browser-profiles')?lt('信息源'):path.includes('/articles/')?lt('文章详情'):lt('情报中心');
   error.message=operation+' · '+error.message+' ['+requestId.slice(0,8)+']';
   throw error;
  }
 }
}
async function api(path='', method='GET', body){
 const result=await requestJSON('/v1/platform/intelligence'+path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-Intelligence-Language':window.IntelligenceI18n?.locale||'en'},...(body===undefined?{}:{body:JSON.stringify(body)})});
 if(method!=='GET'&&state.progressive)mobileChannelViews.clear();
 if(state.progressive&&method==='PATCH'&&/^\/articles\/[^/?]+$/.test(path)&&result?.id){
  const previous=state.articles.find(a=>a.id===result.id),stats=state.channels.find(c=>c.id===result.channel_id)?.article_stats;
  if(previous&&stats){stats.unread+=Number(!result.read)-Number(!previous.read);stats.favorite+=Number(!!result.favorite)-Number(!!previous.favorite);}
  for(const [scope,entry] of mobileArticleLists)if(JSON.parse(scope)[0]===result.channel_id)entry.revision=null;
  mergeArticle(result);
 }
 return result;
}
function notice(message){$('#intel-notice').textContent=message;$('#intel-notice').hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>$('#intel-notice').hidden=true,12000);}
const safe = fn => async (...args) => {try{return await fn(...args);}catch(error){notice(error.message);}};
function link(url){try{const u=new URL(url,String(url).startsWith('/v1/platform/intelligence/imports/')?location.origin:undefined);return ['https:','http:'].includes(u.protocol)?esc(window.MobileAppResource?window.MobileAppResource(u.href):u.href):'#';}catch(_){return '#';}}
initMobile();
window.IntelligenceEntities.init({api,openOriginal:openEntityOriginal,detailRoot:()=>$('#intel-entity-reader'),showEntity:()=>{readerMode='entity';mobilePanel=true;renderChannelChat();},entityAvailable:available=>{$('#show-entity-detail').hidden=!available;if(!available&&readerMode==='entity')readerMode='chat';renderChannelChat();},viewImage:(id,url)=>{const article=state.articles.find(a=>a.id===id);if(!article)return;const images=articleImages(article),index=images.findIndex(i=>i.url===url);if(index<0)return;imagePreview={article,images,index};renderImagePreview();$('#article-image-dialog').showModal();},state:()=>state,tab:()=>tab,setTab:value=>{tab=value;document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b.dataset.tab===tab);b.setAttribute('aria-selected',String(b.dataset.tab===tab));});},notice,readArticle:async id=>{const a=state.articles.find(a=>a.id===id);if(a)channelId=a.channel_id;await readArticle(id);}});
let refreshInFlight=null,hasSnapshot=false,lastPresentation=null;
const presentationKey=()=>JSON.stringify([channelId,selectedId,tab,sectionId,busy,readerMode,mobilePage,previewDraft]);
function setChannelLoadState(value){
 $('#intel-app').dataset.channelLoad=value;
 $('#channel-list').setAttribute('aria-busy',String(value==='loading'));
 $('#channel-loading').hidden=value==='ready';
 $('#channel-loading-text').textContent=lt(value==='failed'?'频道信息读取失败，请重试。':'正在读取频道信息…');
 $('#channel-loading-retry').hidden=value!=='failed';
}
async function refresh(){
 if(refreshInFlight)return refreshInFlight;
 if(!hasSnapshot)setChannelLoadState('loading');
 refreshInFlight=refreshSnapshot();
 try{return await refreshInFlight;}
 catch(error){if(!hasSnapshot)setChannelLoadState('failed');throw error;}
 finally{refreshInFlight=null;}
}
// Mobile transfers a channel directory first, then only the visible article pages.
const mobileArticleLists=new Map(),mobileChannelViews=new Map();
const progressiveData=()=>!!window.AI2APPS_MOBILE_SURFACE||mobileQuery.matches;
function mobileArticleScope(){return JSON.stringify([channelId,sectionId,$('#search-articles').value.trim(),$('#article-filter').value,$('#article-type-filter')?.value||'all']);}
function mergeArticle(article){
 const index=state.articles.findIndex(a=>a.id===article.id),previous=state.articles[index];
 const next=article._summary&&previous&&!previous._summary&&previous.updated_at===article.updated_at?{...previous,...article,sources:previous.sources,_summary:false}:article;
 if(index<0)state.articles.push(next);else state.articles[index]=next;
 return next;
}
async function ensureArticle(id){
 let article=state.articles.find(a=>a.id===id);
 if(!article||article._summary){article=await api('/articles/'+encodeURIComponent(id));mergeArticle(article);}
 return article;
}
async function loadMobileArticles(more=false){
 if(!state.progressive||!channelId)return;
 const scope=mobileArticleScope(),[id,section,q,status,format]=JSON.parse(scope);
 let entry=mobileArticleLists.get(scope);
 const revision=state.channels.find(c=>c.id===id)?.article_stats?.revision;
 if(entry?.promise)return entry.promise;
 if(!more&&entry?.loaded&&entry.revision===revision)return;
 if(more&&!entry?.next)return;
 if(!entry){entry={ids:[],next:null,loaded:false};mobileArticleLists.set(scope,entry);}
 const desired=more?1:Math.max(1,Math.ceil(entry.ids.length/20));
 entry.error='';
 entry.promise=(async()=>{
  let cursor=more?entry.next:'',ids=more?[...entry.ids]:[],result;
  for(let i=0;i<desired;i++){
   const params=new URLSearchParams({section,q,status,format});if(cursor)params.set('cursor',cursor);
   result=await api('/channels/'+encodeURIComponent(id)+'/articles?'+params);
   if(!Array.isArray(result.items))throw Error(lt('频道信息读取失败，请重试。'));
   result.items.forEach(mergeArticle);ids.push(...result.items.map(a=>a.id));cursor=result.next_cursor;
   if(!cursor)break;
  }
  Object.assign(entry,{ids:[...new Set(ids)],next:cursor,total:result.total,loaded:true,revision});
 })().catch(error=>{entry.error=error.message;throw error;}).finally(()=>{entry.promise=null;if(channelId===id){renderSections();renderContent();icons();}});
 renderContent();
 return entry.promise;
}
async function loadMobileChannel(){
 if(!state.progressive||!channelId||mobilePage==='channels')return;
 const id=channelId,c=channel(),runs=state.runs.filter(r=>r.channel_id===id),history=tab==='runs';
 const run=runs.find(r=>r.status==='running')||runs.slice().sort((a,b)=>(Date.parse(b.started_at)||0)-(Date.parse(a.started_at)||0))[0];
 const key=JSON.stringify([c?.updated_at,run?.id,run?.status,run?.finished_at,history,history||run?.status==='running'?Math.floor(Date.now()/5000):0]);
 if(mobileChannelViews.get(id)!==key){
  const value=await api('/channels/'+encodeURIComponent(id)+'/view?history='+history);
  if(!state.channels.some(c=>c.id===id))return;
  const stats=state.channels.find(c=>c.id===id).article_stats;
  state.channels=state.channels.map(c=>c.id===id?{...value.channel,article_stats:stats}:c);
  state.sources=[...state.sources.filter(s=>s.channel_id!==id),...value.sources];
  state.runs=[...state.runs.filter(r=>r.channel_id!==id),...value.runs];
  mobileChannelViews.set(id,key);
 }
 if(tab==='articles')await loadMobileArticles();
 if(selectedId&&state.articles.find(a=>a.id===selectedId)?._summary)await ensureArticle(selectedId);
 if(channelId===id)render();
}
function mobileFilterChanged(){
 render();
 if(progressiveData())loadMobileArticles().catch(error=>notice(error.message));
}
function initMobilePullRefresh(main,directory=false){
 const indicator=document.createElement('div');
 indicator.className='intel-pull-refresh';indicator.setAttribute('role','status');indicator.setAttribute('aria-live','polite');
 indicator.innerHTML='<div class="intel-pull-refresh-content"><span class="intel-pull-refresh-icon" aria-hidden="true">↓</span><span class="intel-pull-refresh-label"></span></div>';
 main.querySelector(directory?'.intel-section-label':'.intel-mobile-bar').after(indicator);
 const label=indicator.querySelector('.intel-pull-refresh-label');
 let gesture=null,refreshing=false,distance=0,suppressClickUntil=0;
 const eligible=()=>mobileQuery.matches&&(directory?mobilePage==='channels':mobilePage==='channel'&&tab==='articles')&&!document.querySelector('dialog[open]');
 function show(height,text){indicator.style.height=height+'px';indicator.hidden=height===0;if(label.textContent!==(text||''))label.textContent=text||'';}
 function reset(){gesture=null;distance=0;if(!refreshing){indicator.classList.remove('is-pulling','is-ready');show(0);}}
 async function reload(){
  refreshing=true;indicator.classList.remove('is-pulling','is-ready');indicator.classList.add('is-refreshing');main.setAttribute('aria-busy','true');show(56,lt('正在刷新…'));
  const id=channelId,scope=mobileArticleScope();
  try{
   // Join existing work before invalidating, so a polling response cannot erase
   // the user's explicit refresh request. Keep the already loaded page window.
   if(refreshInFlight)await refreshInFlight.catch(()=>{});
   if(directory){await refresh();return;}
   const entry=mobileArticleLists.get(scope);if(entry?.promise)await entry.promise.catch(()=>{});
   if(entry)entry.revision=null;mobileChannelViews.delete(id);
   await refresh();
   if(state.progressive&&channelId===id&&mobileArticleScope()===scope)await loadMobileArticles();
  }catch(error){notice(error.message);}
  finally{refreshing=false;indicator.classList.remove('is-refreshing');main.removeAttribute('aria-busy');reset();}
 }
 show(0);
 main.addEventListener('touchstart',event=>{
  reset();
  if(refreshing||!eligible()||main.scrollTop>1||event.touches.length!==1||event.target.closest('.intel-sections,.intel-mobile-bar,[data-channel-grip]'))return;
  const control=event.target.closest('button,a,input,textarea,select,summary');
  if(control&&!(directory&&control.matches('#channel-list [data-channel]')))return;
  const touch=event.touches[0];gesture={id:touch.identifier,x:touch.clientX,y:touch.clientY,locked:false};
 },{passive:true});
 main.addEventListener('touchmove',event=>{
  if(!gesture)return;
  if(!eligible()||event.touches.length!==1){reset();return;}
  const touch=event.touches[0];if(touch.identifier!==gesture.id){reset();return;}
  const dx=touch.clientX-gesture.x,dy=touch.clientY-gesture.y;
  if(!gesture.locked){
   if(Math.abs(dx)<8&&Math.abs(dy)<8)return;
   if(dy<=0||Math.abs(dx)>dy/1.3||main.scrollTop>1){reset();return;}
   gesture.locked=true;indicator.classList.add('is-pulling');
  }
  if(event.cancelable)event.preventDefault();
  distance=Math.max(0,Math.min(88,dy*.5));
  indicator.classList.toggle('is-ready',distance>=56);
  show(distance,lt(distance>=56?'松开刷新':'下拉刷新'));
 },{passive:false});
 main.addEventListener('touchend',()=>{
  const ready=gesture?.locked&&distance>=56&&eligible();if(gesture?.locked)suppressClickUntil=performance.now()+350;gesture=null;
  if(ready&&!refreshing)void reload();else reset();
 },{passive:true});
 main.addEventListener('touchcancel',reset,{passive:true});
 main.addEventListener('click',event=>{if(performance.now()<suppressClickUntil&&event.target.closest('[data-channel],[data-article]')){event.preventDefault();event.stopImmediatePropagation();}},{capture:true});
}
let unavailableNotificationChannel=false;
async function refreshSnapshot(){const next=await api(progressiveData()?'?view=channels':'');if(channelDrag||channelOrderSaving)return;if(!next||!['channels','sources','articles','runs'].every(key=>Array.isArray(next[key])))throw Error(lt('频道信息读取失败，请重试。'));if(hasSnapshot&&JSON.stringify(next)===JSON.stringify(state)&&lastPresentation===presentationKey()){if(progressiveData())await loadMobileChannel();return;}hasSnapshot=true;const previous=state;state=next;if(next.progressive){state.channels=state.channels.map(c=>({...previous.channels.find(old=>old.id===c.id),...c}));state.articles=previous.articles.filter(a=>state.channels.some(c=>c.id===a.channel_id));state.sources=previous.sources;state.runs=[...previous.runs.filter(r=>!next.runs.some(n=>n.id===r.id)),...next.runs.map(n=>({...previous.runs.find(r=>r.id===n.id),...n}))];}const requestedChannel=mobileMount.get("intelligence-channel");if(requestedChannel){mobileMount.delete("intelligence-channel");if(state.channels.some(c=>c.id===requestedChannel)){channelId=requestedChannel;tab="articles";if(mobileQuery.matches){mobilePage="channel";mobileStack.length=0;}}else {unavailableNotificationChannel=true;channelId=null;mobilePage="channels";notice(lt("频道不存在或无权访问"));}}if(!channel()&&!unavailableNotificationChannel)channelId=state.channels[0]?.id||null;if(!state.articles.some(a=>a.id===selectedId))selectedId=null;render();
 if(progressiveData())await loadMobileChannel();
 const notificationID=mobileMount.get('notification-id');
 if(notificationID){
  mobileMount.delete('notification-id');
  const requestedArticle=mobileMount.get('intelligence-article');
  let valid=!unavailableNotificationChannel&&!!channel();
  if(requestedArticle){
   const article=progressiveData()?await ensureArticle(requestedArticle).catch(()=>null):state.articles.find(a=>a.id===requestedArticle);
   valid=valid&&!!article&&article.channel_id===channelId;
   if(valid){selectedId=requestedArticle;readerMode='article';mobilePanel=true;mobilePush('reader');render();}
  }
  window.parent.postMessage({type:'ai2apps.notification.result',id:notificationID,status:valid?'opened':'failed',mountToken:mobileMount.get('ai2apps-mount')},'*');
 }
}
function syncChannelRefreshStatus(){
 const runs=inChannel('runs'),running=runs.some(r=>r.status==='running');
 const latest=runs.map(r=>r.finished_at||r.started_at).filter(s=>s&&Number.isFinite(Date.parse(s))).sort((a,b)=>Date.parse(b)-Date.parse(a))[0];
 for(const id of ['channel-refresh-status','mobile-channel-refresh-status']){
  const node=$('#'+id);if(!node)continue;
  node.hidden=!channel();node.classList.toggle('is-refreshing',running);
  const date=latest?new Date(latest):null;
  const time=id.startsWith('mobile-')&&date?date.toLocaleString(window.IntelligenceI18n?.locale||'zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}):when(latest);
  node.textContent=running?lt('正在刷新'):latest?lt('上次刷新')+' '+time:lt('尚未刷新');
  node.title=running?lt('正在刷新'):latest?lt('上次刷新')+' '+date.toLocaleString(window.IntelligenceI18n?.locale||'zh-CN'):lt('尚未刷新');
 }
}
function channelRefreshRelativeTime(time){
 const minutes=Math.max(0,Math.floor((Date.now()-Date.parse(time))/60000));
 const days=Math.floor(minutes/1440),hours=Math.floor(minutes/60);
 const formatter=new Intl.RelativeTimeFormat(window.IntelligenceI18n?.locale||'zh-CN',{numeric:'always'});
 const unit=days?'day':hours?'hour':'minute',value=days?Math.min(days,10):hours||minutes;
 const parts=formatter.formatToParts(-value,unit);
 return parts.map(part=>days>10&&part.type==='integer'?part.value+'+':part.value).join('');
}
function channelListRefreshStatus(id,detail=false){
 const runs=(state.runs||[]).filter(r=>r.channel_id===id);
 const stamp=r=>r.finished_at||r.started_at;
 const valid=r=>Number.isFinite(Date.parse(stamp(r)));
 const running=runs.filter(r=>r.status==='running').sort((a,b)=>(Date.parse(b.started_at)||0)-(Date.parse(a.started_at)||0))[0];
 const latest=runs.filter(valid).sort((a,b)=>Date.parse(stamp(b))-Date.parse(stamp(a)))[0];
 const run=running||latest;
 if(!run)return lt('尚未刷新');
 const status=running?lt('正在刷新'):(labels[run.status]||lt('上次刷新'));
 const time=stamp(run);
 if(!detail&&!mobileQuery.matches)return running?lt('正在刷新'):channelRefreshRelativeTime(time);
 return status+(time&&Number.isFinite(Date.parse(time))?' · '+when(time):'');
}
let channelDrag=null,channelOrderSaving=false;
const channelList=$('#channel-list');
async function saveChannelOrder(ids){
 const old=state.channels.map(c=>c.id);
 if(ids.every((id,i)=>id===old[i]))return;
 channelOrderSaving=true;
 const byId=new Map(state.channels.map(c=>[c.id,c]));
 state.channels=ids.map(id=>byId.get(id));
 try{await api('/channels/'+encodeURIComponent(ids[0]),'PUT',{channel_order:ids});}
 catch(error){state.channels=old.map(id=>byId.get(id));notice(error.message);}
 finally{channelOrderSaving=false;render();}
}
channelList.addEventListener('click',event=>{if(event.target.closest('[data-channel-grip]')){event.preventDefault();event.stopPropagation();}},true);
channelList.addEventListener('pointerdown',event=>{
 const grip=event.target.closest('[data-channel-grip]');
 if(!grip||channelOrderSaving||event.button>0)return;
 event.preventDefault();event.stopPropagation();
 const row=grip.closest('[data-channel]');
 channelDrag={row,pointer:event.pointerId,old:[...channelList.children]};
 row.classList.add('is-reordering');channelList.setPointerCapture(event.pointerId);
});
channelList.addEventListener('pointermove',event=>{
 if(!channelDrag||event.pointerId!==channelDrag.pointer)return;
 event.preventDefault();
 const row=channelDrag.row;
 for(const target of channelList.querySelectorAll('[data-channel]')){
  if(target===row)continue;
  const rect=target.getBoundingClientRect();
  if(event.clientY>=rect.top&&event.clientY<=rect.bottom){
   channelList.insertBefore(row,event.clientY<rect.top+rect.height/2?target:target.nextSibling);break;
  }
 }
 const scroll=channelList.closest('.intel-sidebar');
 if(scroll){const box=scroll.getBoundingClientRect();if(event.clientY<box.top+40)scroll.scrollTop-=12;else if(event.clientY>box.bottom-40)scroll.scrollTop+=12;}
});
function finishChannelDrag(event){
 if(!channelDrag||event.pointerId!==channelDrag.pointer)return;
 const drag=channelDrag;channelDrag=null;drag.row.classList.remove('is-reordering');
 if(event.type!=='pointerup'){drag.old.forEach(row=>channelList.append(row));return;}
 saveChannelOrder([...channelList.querySelectorAll('[data-channel]')].map(row=>row.dataset.channel));
}
for(const type of ['pointerup','pointercancel','lostpointercapture'])channelList.addEventListener(type,finishChannelDrag);
channelList.addEventListener('keydown',event=>{
 const grip=event.target.closest('[data-channel-grip]');
 if(!grip||channelOrderSaving||!['ArrowUp','ArrowDown'].includes(event.key))return;
 event.preventDefault();event.stopPropagation();
 const id=grip.closest('[data-channel]').dataset.channel,ids=state.channels.map(c=>c.id),from=ids.indexOf(id),to=from+(event.key==='ArrowUp'?-1:1);
 if(to<0||to>=ids.length)return;
 [ids[from],ids[to]]=[ids[to],ids[from]];
 saveChannelOrder(ids).then(()=>channelList.querySelector('[data-channel="'+CSS.escape(id)+'"] [data-channel-grip]')?.focus());
});
function render(){
 if(hasSnapshot)setChannelLoadState('ready');
 setHTML($('#channel-list'),state.channels.map(c=>it`<button data-channel="${c.id}" class="${c.id===channelId?'active':''}"><span class="intel-channel-symbol intel-channel-grip" data-channel-grip tabindex="0" role="button" aria-label="Reorder channel">⠿</span><span class="channel-info"><span class="channel-label">${esc(c.name)}</span><span class="channel-update-status" title="${esc(channelListRefreshStatus(c.id,true))}">${esc(channelListRefreshStatus(c.id))}</span></span><span class="count">${(state.progressive?c.article_stats?.unread:state.articles.filter(a=>a.channel_id===c.id&&!a.read).length)||''}</span></button>`).join(''));
 const c=channel();$('#channel-controls').hidden=!c;$('#channel-head-actions').hidden=!c;$('#channel-title').textContent=c?.name||lt('捕捉你关心的变化');$('#channel-description').textContent=c?.interests||lt('从一个兴趣开始，建立你的第一条情报频道。');
 $('#collect').disabled=busy||!inChannel('sources').some(s=>s.enabled)||inChannel('runs').some(r=>r.status==='running');$('#recommend').disabled=busy;$('#edit-channel').disabled=busy;
 $('#article-count').textContent=(state.progressive?c?.article_stats?.total:inChannel('articles').length)||'';$('#source-count').textContent=(state.progressive?c?.source_count:inChannel('sources').length)||'';
 document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b.dataset.tab===tab);b.setAttribute('aria-selected',String(b.dataset.tab===tab));});
 $('#search-articles').hidden=tab!=='articles';$('#article-filter').hidden=tab!=='articles';$('#article-type-filter').hidden=tab!=='articles';$('#add-source').hidden=tab!=='sources';$('#recommend').hidden=tab!=='sources';$('#write-channel-draft').hidden=tab!=='drafts';
 $('#channel-controls .intel-filter').hidden=tab==='runs';
 const sync=c?.knowledge_sync||{};setHTML($('#knowledge-sync-status'),sync.failed?it`知识库同步失败 ${sync.failed} 项 <button data-action="sync-knowledge">重试同步</button>${sync.errors?.length?'<p>'+sync.errors.map(esc).join('；')+'</p>':''}`:'');
 renderSections();renderContent();renderReader();syncMobile();icons();lastPresentation=presentationKey();
}
let sectionDrag=null,sectionOrderSaving=false;
const sectionFilters=$('#section-filters');
sectionFilters.addEventListener('dragstart',event=>{
 const button=event.target.closest('[data-section][draggable="true"]');
 if(!button||sectionOrderSaving){event.preventDefault();return;}
 sectionDrag={id:button.dataset.section,channelId};
 event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',button.dataset.section);
 button.classList.add('dragging');
});
function clearSectionDrag(){sectionDrag=null;sectionFilters.querySelectorAll('.dragging,.drop-before,.drop-after').forEach(b=>b.classList.remove('dragging','drop-before','drop-after'));}
sectionFilters.addEventListener('dragend',clearSectionDrag);
sectionFilters.addEventListener('dragover',event=>{
 const button=event.target.closest('[data-section][draggable="true"]');
 if(!button||!sectionDrag||sectionDrag.channelId!==channelId)return;
 event.preventDefault();event.dataTransfer.dropEffect='move';
 sectionFilters.querySelectorAll('.drop-before,.drop-after').forEach(b=>b.classList.remove('drop-before','drop-after'));
 const rect=button.getBoundingClientRect();button.classList.add(event.clientX<rect.left+rect.width/2?'drop-before':'drop-after');
});
sectionFilters.addEventListener('drop',async event=>{
 const button=event.target.closest('[data-section][draggable="true"]'),drag=sectionDrag;
 if(!button||!drag||drag.channelId!==channelId)return;
 event.preventDefault();const target=button.dataset.section,rect=button.getBoundingClientRect(),after=event.clientX>=rect.left+rect.width/2;
 clearSectionDrag();if(target===drag.id)return;
 const c=channel(),ids=c.sections.map(s=>s.id).filter(id=>id!==drag.id);
 ids.splice(ids.indexOf(target)+(after?1:0),0,drag.id);sectionOrderSaving=true;
 try{const saved=await api('/channels/'+drag.channelId+'/sections/order','PUT',{ids});const current=state.channels.find(c=>c.id===drag.channelId);if(current)current.sections=saved.sections;if(channelId===drag.channelId)renderSections();}
 catch(error){notice(error.message||lt('排序保存失败，请重试'));}
 finally{sectionOrderSaving=false;}
});
function sectionName(article){return channel()?.sections?.find(s=>s.id===article.section_id)?.name||lt('待归类');}
function renderSections(){
 const root=$('#section-filters'),sections=channel()?.sections||[];
 root.hidden=tab!=='articles'||!channel();
 if(!sections.some(s=>s.id===sectionId)&&sectionId!=='unassigned'&&sectionId!=='$favorites')sectionId='';
 const articles=inChannel('articles'),stats=state.progressive?channel()?.article_stats:null,unassigned=stats?Object.entries(stats.sections).filter(([id])=>!sections.some(s=>s.id===id)).reduce((n,[,count])=>n+count,0):articles.filter(a=>!sections.some(s=>s.id===a.section_id)).length;
 const filters=[{id:'',name:lt('全部'),description:lt('全部情报')},{id:'$favorites',name:lt('已收藏'),description:lt('已收藏')},...sections,...(unassigned&&sections.length?[{id:'unassigned',name:lt('待归类'),description:lt('尚未归入栏目的历史文章')}]:[])];
 setHTML(root,filters.map(s=>it`<button data-section="${esc(s.id)}" ${s.id&&s.id!=='unassigned'&&s.id!=='$favorites'?'draggable="true"':''} class="${sectionId===s.id?'active':''}" aria-pressed="${sectionId===s.id}" title="${esc(s.description)}">${esc(s.name)} <span>${s.id==='$favorites'?(stats?.favorite??articles.filter(a=>a.favorite).length):s.id==='unassigned'?unassigned:s.id?(stats?stats.sections[s.id]||0:articles.filter(a=>a.section_id===s.id).length):(stats?.total??articles.length)}</span></button>`).join('')+(sectionId&&sectionId!=='$favorites'?it`<button data-write="section" data-scope-id="${esc(sectionId)}"><i data-lucide="square-pen" aria-hidden="true"></i>为此栏目撰写稿件</button>`:'')+(!sections.length?it`<span class="intel-muted">为频道整理专属栏目</span><button data-action="create-sections" ${busy?'disabled':''}>✦ AI 创建栏目</button>`:''));
}
async function createSections(){
 if(busy||!channel())return;const target=channelId;busy=true;render();notice(lt('AI 正在规划栏目，并整理已有情报…'));
 try{await api('/channels/'+target+'/sections','POST');notice(lt('栏目已创建，已有情报已归类'));}
 finally{busy=false;await refresh();}
}
function empty(icon,title,text,actions=''){return it`<div class="intel-empty"><i data-lucide="${icon}"></i><h2>${esc(title)}</h2><p>${esc(text)}</p>${actions}</div>`;}
const failedCovers=new Set();
function coverHTML(a,detail=false){
 const url=articleImages(a)[0]?.url;if(!url||failedCovers.has(url)||link(url)==='#')return '';
 return it`<figure class="intel-cover ${detail?'intel-cover-detail':''}"><img src="${esc(window.IntelligenceCards.imageURL(a,url))}" alt="${esc(a.title)}" loading="lazy" decoding="async" referrerpolicy="no-referrer">${detail?it`<figcaption><a href="${link(articleImages(a)[0]?.source_url)}" target="_blank" rel="noopener noreferrer">图片来自原文 ↗</a></figcaption>`:''}</figure>`;
}
document.addEventListener('error',event=>{const img=event.target;if(img.matches?.('.intel-cover img,.intel-story img')){failedCovers.add(img.src);const figure=img.closest('figure');if(figure)figure.hidden=true;else img.hidden=true;}},true);
async function extractArticleCover(){
 if(busy||!selectedId)return;const article=state.articles.find(a=>a.id===selectedId),id=selectedId;
 const reference=article.sources.find(r=>state.sources.some(s=>s.channel_id===article.channel_id&&(s.id===r.source_id||s.name===r.source_name)));
 if(!reference)throw Error(lt('原信息源已移除，无法确定采集 Profile。'));
 const source=state.sources.find(s=>s.channel_id===article.channel_id&&(s.id===reference.source_id||s.name===reference.source_name));
 let session;busy=true;render();notice(lt('正在从原文提取标题图…'));
 try{session=await browserSession(source.profile_key||'default');const page=await read(session,reference.url);
  if(!page.cover_image?.url)throw Error(lt('未找到合适的标题图，保留文字布局。'));
  failedCovers.delete(page.cover_image.url);
  await api('/articles/'+id+'/cover','PUT',{source_url:reference.url,image_url:page.cover_image.url});notice(lt('标题图已更新'));
 }finally{await closeBrowser(session);busy=false;await refresh();}
}
const topicRequests=new Set();
async function updateTopics(id=channelId){
 if(!id||topicRequests.has(id))return;topicRequests.add(id);if(channelId===id)renderContent();
 try{await api('/channels/'+id+'/topics','POST');await refresh();}
 catch(error){notice(lt('热点整理失败：')+error.message);}
 finally{topicRequests.delete(id);if(channelId===id){renderContent();icons();}}
}
function renderTopics(root){
 const c=channel(),data=c.hot_topics,topicPage=window.IntelligencePagination.page('topics',channelId,window.IntelligencePagination.newest(data?.items||[])),items=topicPage.items,articles=inChannel('articles'),loading=topicRequests.has(c.id);
 const latest=articles.reduce((value,a)=>a.updated_at>value?a.updated_at:value,'');
 const stale=data&&latest>data.generated_at;
 setHTML(root,it`<div class="intel-topics-head"><div><h2>频道热点</h2><p class="intel-help">近 7 天更新的最多 60 篇情报 · 按具体产品、事件聚合 · 至少 2 篇相关文章</p><p class="intel-help">${data?lt('整理于 ')+when(data.generated_at)+lt(' · 分析 ')+data.article_count+lt(' 篇'):''}${stale?lt(' · 有新文章，待更新热点'):''}</p></div><button data-action="update-topics" ${loading?'disabled':''}>${loading?lt('正在整理…'):lt('更新热点')}</button></div>`+
 (items.length?items.map(t=>{const related=t.article_ids.map(id=>articles.find(a=>a.id===id)).filter(Boolean);
 const cover=related.find(a=>a.cover_image);
 return it`<section class="intel-topic">${cover?coverHTML(cover):''}<div class="intel-story-meta">${related.length} 篇相关文章 · 最近进展 ${when(t.updated_at)}</div><h2>${esc(t.title)}</h2><button data-write="topic" data-scope-id="${esc(t.id)}"><i data-lucide="square-pen" aria-hidden="true"></i>撰写稿件</button><p class="intel-topic-summary">${esc(t.summary)}</p><div class="intel-topic-articles">${related.map(a=>it`<button data-article="${esc(a.id)}"><span>${esc(a.title)}</span><small>${when(a.updated_at)}</small></button>`).join('')}</div></section>`;}).join('')+window.IntelligencePagination.button('topics',topicPage.more):
 empty('flame',loading?lt('正在寻找文章之间的关联'):data?lt('暂未形成热点'):lt('把近期情报串成话题'),loading?lt('AI 正在归纳具体事件及相关报道。'):lt('点击更新热点；同一表款、AI 模型或赛事有多篇报道时，会归在一起。'))));
}
function renderContent(){
 const root=$('#intel-content'),scroll=root.closest('.intel-main')||root;
 const preserve=tab==='articles'&&root.classList.contains('intel-article-grid')&&root.dataset.renderScope===String(channelId||'');
 const top=scroll.scrollTop;
 renderContentBody();
 // Restoring inside setHTML is too early: masonry has not measured new cards
 // yet, so the browser clamps scrollTop against a temporarily collapsed grid.
 if(preserve)scroll.scrollTop=top;
}
function renderContentBody(){
 const root=$('#intel-content');window.IntelligenceCards.clearLayout(root,tab==='articles');root.onclick=null;root.onsubmit=null;
 root.classList.toggle('intel-article-grid',tab==='articles'&&!!channel());
 root.classList.toggle('intel-draft-grid',tab==='drafts'&&!!channel());
 if(!['entities','opportunities'].includes(tab)){$('#show-entity-detail').hidden=true;$('#intel-entity-reader').hidden=true;if(readerMode==='entity')readerMode='chat';}
 if(!channel()){setHTML(root,empty('satellite-dish',lt('你的第一条情报频道'),lt('告诉 AI 你关心什么。让分散的网站和话题，汇聚成一份可以追溯来源的情报。'),lt('<div class="intel-starters"><button data-starter="腕表">⌚ 腕表</button><button data-starter="人工智能">✦ 人工智能</button><button data-starter="摄影">◎ 摄影</button></div><p style="margin-top:25px"><button data-action="create" class="intel-primary">＋ 自定义频道</button></p>')));return;}
 if(tab==='entities'||tab==='opportunities'){renderedMarkup.delete(root);window.IntelligenceEntities.render(root,tab,channelId);return;}
 if(tab==='articles'){
  const q=$('#search-articles').value.trim().toLowerCase(),filter=$('#article-filter').value,typeFilter=$('#article-type-filter')?.value||'all';
  const articles=inChannel('articles').filter(a=>(typeFilter==='all'||window.IntelligenceCards.describe(a).formats.includes(typeFilter))&&(!sectionId||(sectionId==='$favorites'?a.favorite:sectionId==='unassigned'?!channel().sections?.some(s=>s.id===a.section_id):a.section_id===sectionId))&&(!q||(a.title+' '+a.summary+' '+a.body).toLowerCase().includes(q))&&(filter!=='unread'||!a.read)&&(filter!=='more'||a.feedback==='more')).sort((a,b)=>b.updated_at.localeCompare(a.updated_at));
  const remote=state.progressive?mobileArticleLists.get(mobileArticleScope()):null;
  if(state.progressive&&(!remote?.loaded||remote.promise&&!remote.ids.length)){setHTML(root,remote?.error?it`<p class="intel-form-error">${esc(remote.error)}</p><button data-mobile-articles-retry>${lt('重试')}</button>`:it`<p class="intel-help" role="status">${lt('正在加载文章…')}</p>`);return;}
  const page=state.progressive?{items:(remote?.ids||[]).map(id=>state.articles.find(a=>a.id===id)).filter(a=>a&&(filter!=='unread'||!a.read)&&(filter!=='more'||a.feedback==='more')&&(sectionId!=='$favorites'||a.favorite)),more:!!remote?.next}:window.IntelligencePagination.page('articles',JSON.stringify([channelId,sectionId,q,filter,typeFilter]),articles);
  setHTML(root,page.items.map(a=>window.IntelligenceCards.render(a,{selected:a.id===selectedId,section:sectionName(a),updated:when(a.updated_at),failedImages:failedCovers,compact:true})).join('')+window.IntelligencePagination.button('articles',page.more)||empty('newspaper',q||filter!=='all'||typeFilter!=='all'||sectionId?sectionId==='$favorites'?lt('暂无收藏的文章'):lt('没有匹配的文章'):lt('等待第一份情报'),sectionId==='$favorites'?lt('点击文章上方的星标即可收藏。'):inChannel('sources').length?lt('点击“立即更新”，读取信息源并整理值得关注的内容。没有新变化时，不会生成重复文章。'):lt('先添加信息源，或让 AI 根据你的兴趣推荐网站。'),lt('<button data-action="sources">管理信息源 →</button>')));
  window.IntelligenceCards.layout(root);
 }else if(tab==='drafts'){
  renderDraftList(root);
 }else if(tab==='topics'){
  renderTopics(root);
 }else if(tab==='sources'){
  const page=window.IntelligencePagination.page('sources',channelId,window.IntelligencePagination.newest(inChannel('sources')));
  setHTML(root,page.items.map(s=>it`<section class="intel-source"><header><h3>${esc(s.name)}</h3><span class="intel-status">${s.enabled?lt('监测中'):lt('已暂停')}</span></header><a href="${link(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.url)} ↗</a><footer><span>${s.kind==='social'?lt('社交账号 / 话题'):lt('网站 / 栏目')} · ${esc(((s.profile_key||'default')==='default'?lt('Default Profile'):profiles.find(p=>p.key===s.profile_key)?.name)||lt('Profile 已删除'))}</span>${s.kind==='social'?it`<span>${s.social_interval_hours===0.25?lt('间隔 15 分钟'):it`间隔 ${s.social_interval_hours||6} 小时`}${s.social_next_at?lt(' · 下次 ')+when(s.social_next_at*1000):''}</span>${s.social_paused?it`<button data-resume-social="${s.id}">已处理验证，恢复采集</button>`:''}`:''}<button data-update-source="${s.id}" ${busy||!s.enabled||inChannel('runs').some(r=>r.status==='running')?'disabled':''}>${inChannel('runs').some(r=>r.status==='running'&&(!r.source_id||r.source_id===s.id))?lt('更新中…'):lt('立即更新')}</button><button data-edit-source="${s.id}" ${busy?'disabled':''}>设置</button><button data-toggle-source="${s.id}" ${busy?'disabled':''}>${s.enabled?lt('暂停'):lt('启用')}</button><button data-delete-source="${s.id}" ${busy?'disabled':''}>移除</button></footer></section>`).join('')+window.IntelligencePagination.button('sources',page.more)||empty('radio',lt('为频道接入信息源'),lt('添加网站栏目、社交账号或话题页。AI 推荐会读取真实搜索结果，供你选择。'),lt('<button data-action="recommend">✦ AI 推荐信息源</button>')));
 }else{
  const page=window.IntelligencePagination.page('runs',channelId,window.IntelligencePagination.newest(inChannel('runs')));
  setHTML(root,lt('<div class="intel-run-actions"><button data-show-filtered>查看已过滤帖子</button></div>')+ (page.items.map(r=>it`<section class="intel-run"><header><h3>${r.scheduled?lt('定时更新'):lt('手动更新')}</h3><span class="intel-status ${['failed','partial','interrupted'].includes(r.status)?'error':''}">${labels[r.status]||esc(r.status)}</span></header><p>${esc(r.status==='interrupted'?lt('上次执行连接中断，可以重新更新。'):systemMessage(r.message))}</p>${renderRecoverySummary(r)}${r.status==='running'?renderRunProgress(r):''}<time>${when(r.started_at)}</time>${r.logs?.length?it`<details><summary>查看 ${r.logs.length} 个信息源的结果</summary>${r.logs.map(l=>it`<p>${esc(l.name)} · ${labels[l.status]} · ${l.pages} 篇<br>${esc(systemMessage(l.message))}</p>`).join('')}</details>`:''}</section>`).join('')+window.IntelligencePagination.button('runs',page.more)||empty('history',lt('每次更新，都有记录'),lt('这里会显示采集结果、生成数量，以及需要登录或人工协助的信息源。'))));
 }
}
function renderRecoverySummary(r){
 const p=r.progress||{};if(!p.cached_pages)return '';
 const fresh=(r.logs||[]).reduce((n,l)=>n+(Number(l.pages)||0),0);
 return `<p class="intel-help">${lt('缓存复用正文')}：${Number(p.cached_pages)||0} · ${lt('补齐缓存情报')}：${Number(p.cache_articles_saved)||0} · ${lt('本轮新读取正文')}：${fresh}</p>`;
}
function renderRunProgress(r){
 const p=r.progress||{};
 const phases={list:lt('读取列表'),article:lt('读取文章'),validation:lt('学习验证'),digest:lt('生成情报'),planning:lt('整理事件'),writing:lt('整理与翻译文章'),saving:lt('保存情报'),finalizing:lt('文章已保存，正在收尾')};
 return `<div class="intel-run-progress" role="status">${p.refresh_stage?`<p>${lt('当前步骤')}：${p.refresh_stage==='cache'?lt('先补齐缓存'):lt('采集最新内容')}</p>`:''}<div>${lt('当前信息源')}：${esc(p.source_name||lt('准备采集'))} · ${esc(p.waiting?lt('等待处理'):phases[p.phase]||lt('准备采集'))}</div>${p.waiting?`<p>${lt('采集已暂停，请到 AI 浏览器任务栏查看并处理；尚未开始整理此信息源。')}</p>`:''}${Array.isArray(p.active_articles)&&p.active_articles.length?`<p>${lt('并行生成')} ${p.active_articles.length} / ${Number(p.article_concurrency)||3} · ${lt('已完成文章')} ${Number(p.events_completed)||0} / ${Number(p.events_total)||0}</p>${p.active_articles.map(a=>`<p>${Number(a.event_index)||0}. ${esc(a.title||'')}<small> · ${lt('第几次调用')} ${Number(a.model_attempt)||1}${a.model_attempt>1?' · '+lt('正在重试'):''}</small></p>`).join('')}`:p.event_title?`<p>${lt('当前文章')} ${Number(p.event_index)||0} / ${Number(p.events_total)||0}：${esc(p.event_title)}</p>`:''}${!p.active_articles?.length&&p.model_attempt?`<small>${lt('等待 AI 返回')} · ${lt('第几次调用')} ${Number(p.model_attempt)}${p.model_attempt>1?' · '+lt('正在重试'):''}</small>`:''}${p.phase_started_at?`<div>${lt('当前阶段耗时')} <b data-run-elapsed="${esc(p.phase_started_at)}"></b></div>`:''}<div class="intel-run-metrics"><span>${lt('已读取页面')} <b>${Number(p.pages_read)||0}</b></span><span>${lt('已提取文章')} <b>${Number(p.articles_extracted)||0}</b></span><span>${lt('已保存情报')} <b>${Number(p.articles_saved)||0}</b></span><span>${lt('已完成信息源')} <b>${Number(p.sources_completed)||0}</b></span><span>${lt('已执行')} <b data-run-elapsed="${esc(r.started_at)}"></b></span></div>${(p.active_pages||[]).map(page=>`<a href="${link(page.url)}" target="_blank" rel="noopener noreferrer"><small>${esc(page.source_name||lt('当前页面'))} · ${esc(page.status==='queued'?lt('等待执行'):page.status==='waiting_input'?lt('执行中'):labels[page.status]||page.status||'')}</small> ${esc(page.url)} ↗</a>`).join('')}</div>`;
}
function updateRunElapsed(){document.querySelectorAll('[data-run-elapsed]').forEach(node=>{const seconds=Math.max(0,Math.floor((Date.now()-Date.parse(node.dataset.runElapsed))/1000));node.textContent=Number.isFinite(seconds)?`${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`:'—';});}
function syncArticleFavorite(){
 const article=state.articles.find(a=>a.id===selectedId);if(!article)return;
 for(const button of document.querySelectorAll('[data-favorite]')){
  if(button.dataset.favorite!==article.id)continue;
  const active=!!article.favorite,tip=lt(active?'取消收藏':'收藏文章');
  button.setAttribute('aria-pressed',String(active));button.setAttribute('aria-label',tip);button.dataset.favoriteTip=tip;
  button.classList.toggle('is-favorite',active);button.querySelector('svg').setAttribute('fill',active?'currentColor':'none');
  button.querySelector('[data-favorite-label]').textContent=lt(active?'已收藏':'未收藏');
 }
}
function eventOtherSources(article){
 const key=s=>{try{const u=new URL(s.url);if(!['http:','https:'].includes(u.protocol))return '';u.hash='';return u.href;}catch(_){return '';}};
 const seen=new Set((article.sources||[]).map(key)),result=[];
 const candidates=[...(article.versions||[]).slice().reverse().flatMap(v=>v.sources||[]),...(article.related_sources||[])];
 for(const source of candidates){const id=key(source);if(id&&!seen.has(id)){seen.add(id);result.push(source);}}
 return result;
}
function eventOtherSourcesHTML(article){
 const sources=eventOtherSources(article);if(!sources.length)return '';
 return it`<section class="intel-citations intel-other-reports"><h3>该事件的其他报道 · ${sources.length}</h3><p class="intel-help">此前版本来源，不作为当前正文的引用依据。</p>${sources.map(s=>it`<a href="${link(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title||s.source_name)} ↗<small>${esc(s.source_name)} · 此前版本来源${s.coverage==='preview'?' · '+lt('不完整预览'):''}${s.access_reason==='login_required'?' · '+lt('需要登录'):s.access_reason==='paywall'?' · '+lt('需要订阅'):s.access_reason==='access_verification_pending'?' · '+lt('访问验证未完成'):''}</small></a>`).join('')}</section>`;
}
function renderReader(){
 renderChannelChat();
 const a=state.articles.find(a=>a.id===selectedId&&a.channel_id===channelId);const root=$('#intel-article-reader');
 if(readerMode==='article'&&selectedId&&articleOpening===selectedId){root.classList.add('open');setHTML(root,it`<div class="intel-article-loading" role="status" aria-live="polite"><p>${lt('正在加载文章…')}</p><div class="intel-loading-title" aria-hidden="true"></div><div class="intel-loading-cover" aria-hidden="true"></div><div class="intel-loading-line" aria-hidden="true"></div><div class="intel-loading-line" aria-hidden="true"></div></div>`);return;}
 if(previewDraft?.channel_id===channelId){renderDraftPreview(root,previewDraft);return;}
 if(!a){root.classList.remove('open');setHTML(root,lt('<div class="intel-reader-empty"><span><i data-lucide="book-open-text"></i></span><h2>每一条情报，都有来处</h2><p>选一篇文章，查看摘要、变化与原始来源。</p><div class="intel-reader-principles"><p>01　只关注与你有关的信息</p><p>02　合并重复报道，保留新进展</p><p>03　阅读文章，也能追溯原文</p></div></div>'));return;}
 root.classList.add('open');setHTML(root,it`<div class="intel-article-head"><span>${esc(sectionName(a))} · ${a.ai_translation?lt('AI 翻译'):a.image_ai_summary?lt('AI 图片总结'):a.manual_import?lt('手动收录'):lt('AI 整理')} · ${when(a.updated_at)}</span><button type="button" class="intel-favorite" data-favorite="${esc(a.id)}" aria-pressed="false"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="m12 3 2.8 5.7 6.3.9-4.55 4.45 1.07 6.28L12 17.36l-5.62 2.97 1.07-6.28L2.9 9.6l6.3-.9Z"/></svg><span data-favorite-label hidden></span></button><button type="button" data-article-chat="${esc(a.id)}" title="${esc(window.IntelligenceI18n.format('chat.mini.title',{}))}" aria-label="${esc(window.IntelligenceI18n.format('chat.mini.title',{}))}" data-action-tip="${esc(window.IntelligenceI18n.format('chat.mini.title',{}))}"><i data-lucide="messages-square" aria-hidden="true"></i></button><button type="button" data-article-chat="${esc(a.id)}" data-article-chat-purpose="research" title="${esc(window.IntelligenceI18n.format('intelligence.article_chat.research_title',{}))}" aria-label="${esc(window.IntelligenceI18n.format('intelligence.article_chat.research_title',{}))}" data-action-tip="${esc(window.IntelligenceI18n.format('intelligence.article_chat.research_title',{}))}"><i data-lucide="telescope" aria-hidden="true"></i></button><button data-write="article" data-scope-id="${esc(a.id)}" title="${esc(lt('撰写稿件'))}" aria-label="${esc(lt('撰写稿件'))}" data-action-tip="${esc(lt('撰写稿件'))}"><i data-lucide="square-pen" aria-hidden="true"></i></button></div>${coverHTML(a,true)}<h1>${esc(a.title)}</h1><div class="intel-lead">${esc(a.summary)}</div>${a.sources.some(s=>s.coverage==='preview')?it`<p class="intel-help">基于部分预览内容整理，可能不完整。请通过下方原始来源查看全文；原站可能要求登录或订阅。</p>`:''}<div class="intel-body">${articleBodyHTML(a)}</div>${a.post_evidence?.length?it`<details class="intel-help"><summary>事件相关帖子 · ${a.post_evidence.length}</summary>${a.post_evidence.map(p=>it`<section><strong>${esc(p.author||p.source_name)} · ${p.role==='supplementary'?lt('补充证据'):lt('主要证据')}</strong><div class="intel-body">${esc(p.text)}</div><a href="${link(p.url)}" target="_blank" rel="noopener noreferrer">查看原帖 ↗</a></section>`).join('')}</details>`:''}${a.original_content?it`<details class="intel-help"><summary>查看原文</summary><h3>${esc(a.original_content.title)}</h3><div class="intel-body">${esc(a.original_content.body)}</div></details>`:''}<section class="intel-citations"><h3>原始来源 · ${a.sources.length}</h3>${a.sources.map((s,i)=>it`<a href="${link(s.url)}" target="_blank" rel="noopener noreferrer">[${i+1}] ${esc(s.title||s.source_name)} ↗<small>${esc(s.source_name)} · 采集于 ${when(s.retrieved_at)}${s.coverage?' · '+(s.coverage==='preview'?lt('不完整预览 · 原文可能需要登录或订阅'):s.coverage==='transcript'?lt('网页文字稿'):lt('仅标题与简介')):''}</small></a>`).join('')}</section>${eventOtherSourcesHTML(a)}${articleImagesHTML(a)}<div class="intel-feedback"><button data-action="extract-images" ${busy?'disabled':''}>提取文章图片</button><button data-action="extract-cover" ${busy?'disabled':''}>${a.cover_image?lt('重新提取标题图'):lt('提取标题图')}</button><button data-feedback="more" class="${a.feedback==='more'?'active':''}" aria-pressed="${a.feedback==='more'}">👍 顶</button><button data-feedback="less" class="${a.feedback==='less'?'active':''}" aria-pressed="${a.feedback==='less'}">👎 踩</button>${a.feedback==='less'?lt('<button data-action="edit-feedback">修改理由</button>'):''}</div>${a.feedback_reasons?.length?it`<p class="intel-help">踩的理由：${a.feedback_reasons.map(esc).join('；')}</p>`:''}<p class="intel-help">反馈保存在本机作为你的偏好，再次点击可撤销。AI 整理可能存在遗漏，关键事实请核对原文。</p>${a.versions?.length?it`<details class="intel-help"><summary>历史版本（${a.versions.length}）</summary>${a.versions.map(v=>it`<p>${when(v.updated_at)} · ${esc(v.title)}</p><div style="white-space:pre-wrap">${esc(v.body)}</div>`).join('<hr>')}</details>`:''}<section id="article-entities" class="intel-article-entities"></section>`);
 syncArticleFavorite();
 window.IntelligenceEntities.renderArticle?.($('#article-entities'),a);
}
function articleImages(article){
 const seen=new Set();return [...(article.cover_image?[{...article.cover_image,alt:article.title}]:[]),...(article.images||[])].filter(i=>i.url&&!window.IntelligenceCards.isAvatar(i.url)&&link(i.url)!=='#'&&!seen.has(i.url)&&seen.add(i.url));
}
function articleContentImages(article){
 const blocks=article.content_blocks;
 if(!['ai2apps.article-content/v1','ai2apps.article-content/v2'].includes(article.content_schema)||!Array.isArray(blocks)||!blocks.length||blocks.length>128)return null;
 const v2=article.content_schema==='ai2apps.article-content/v2',paragraphIds=new Set(),sectionIds=new Set((article.editorial_sections||[]).map(s=>s.id));let lastParagraph=null;
 const paragraphs=String(article.body||'').trim().split(/\n\s*\n/).map(p=>p.trim()).filter(Boolean),text=[],images=new Map(),used=new Set();
 for(const block of blocks){
  if(!block||typeof block!=='object')return null;
  if(block.type==='paragraph'&&typeof block.text==='string'){if(v2&&(!/^p_[a-f0-9]{24}$/.test(block.id)||paragraphIds.has(block.id)||!sectionIds.has(block.section_id)))return null;paragraphIds.add(block.id);lastParagraph=block.id;text.push(block.text);continue;}
  if(block.type!=='image'||used.has(block.image_id)||(v2&&block.paragraph_id!==lastParagraph))return null;
  const image=(article.images||[]).find(i=>i.id===block.image_id);
  if(!image||link(image.url)==='#'||!(article.sources||[]).some(s=>s.url===image.source_url))return null;
  const sourceNumber=article.sources.findIndex(s=>s.url===image.source_url)+1,citations=[...(text[text.length-1]||'').matchAll(/\[(\d+)\]/g)].map(m=>Number(m[1]));
  if(!citations.includes(sourceNumber))return null;
  used.add(block.image_id);images.set(block.image_id,image);
 }
 if(used.size>24||text.length!==paragraphs.length||text.some((p,i)=>p!==paragraphs[i]))return null;
 return images;
}
function articleBodyHTML(article){
 const images=articleContentImages(article);if(!images)return esc(article.body);
 const gallery=articleImages(article),sections=new Map((article.editorial_sections||[]).map(s=>[s.id,s.title]));let lastSection=null;
 return article.content_blocks.map(block=>{
  if(block.type==='paragraph'){const heading=block.section_id!==lastSection?sections.get(block.section_id):'';lastSection=block.section_id;return (heading?'<h3 class="intel-body-section">'+esc(heading)+'</h3>':'')+'<p class="intel-body-paragraph"'+(block.id?' data-paragraph-id="'+esc(block.id)+'"':'')+'>'+esc(block.text)+'</p>';}
  const image=images.get(block.image_id),index=gallery.findIndex(i=>i.url===image.url),sourceIndex=article.sources.findIndex(s=>s.url===image.source_url);
  if(index<0)return '';
  return '<figure class="intel-inline-image"><button type="button" data-image-index="'+index+'" aria-label="'+esc(lt('放大图片')+' '+(index+1))+'"><img src="'+esc(window.IntelligenceCards.imageURL(article,image.url))+'" alt="'+esc(image.alt||'')+'" loading="lazy" referrerpolicy="no-referrer"></button><figcaption>'+esc(image.alt||'')+' <a href="'+link(image.source_url)+'" target="_blank" rel="noopener noreferrer">['+(sourceIndex+1)+'] '+esc(lt('图片来自原文'))+' ↗</a></figcaption></figure>';
 }).join('');
}
function articleImagesHTML(article){
 const images=articleImages(article).map((image,index)=>({image,index}));if(!images.length)return '';
 return it`<section class="intel-article-images"><h3>文章图片 · ${images.length}</h3><div class="intel-image-grid">${images.map(({image,index})=>it`<button data-image-index="${index}" aria-label="放大图片 ${index+1}"><img src="${esc(window.IntelligenceCards.imageURL(article,image.url))}" alt="${esc(image.alt||article.title)}" loading="lazy" referrerpolicy="no-referrer"></button>`).join('')}</div></section>`;
}
function imageSource(article,image){
 const ref=article.sources.find(r=>r.url===image.source_url);
 if(ref?.profile_key)return {name:ref.source_name,profile_key:ref.profile_key};
 const source=ref&&state.sources.find(s=>s.channel_id===article.channel_id&&(ref.source_id?s.id===ref.source_id:s.name===ref.source_name));
 if(!source)throw Error(lt('原信息源已移除，无法确定图片的采集 Profile。'));return source;
}
async function extractArticleImages(){
 if(busy||!selectedId)return;const article=state.articles.find(a=>a.id===selectedId);busy=true;render();let added=0,failures=[];
 try{for(const ref of article.sources){let session;
  try{const source=imageSource(article,{source_url:ref.url});notice(lt('正在提取 ')+source.name+lt(' 的文章图片…'));session=await browserSession(source.profile_key||'default');
   const page=window.IntelligenceSocial.weibo({url:ref.url})?(await read(session,ref.url,{phase:'open'}),await session.client.extractWeiboDetail(ref.url)):await read(session,ref.url);
   await api('/articles/'+article.id+'/images','PUT',{source_url:ref.url,images:page.images||[],image_url:page.cover_image?.url||''});added++;
  }catch(error){failures.push(error.message);}finally{await closeBrowser(session);}
 }notice((added?lt('已更新文章图片'):lt('未提取到图片'))+(failures.length?'；'+failures.join('；'):''));
 }finally{busy=false;await refresh();}
}
function installImageGestures(stage,image,navigate,carousel={}){
 const pointers=new Map();let scale=1,x=0,y=0,gesture=null;
 const clamp=(value,min,max)=>Math.max(min,Math.min(max,value));
 const size=()=>{const r=stage.getBoundingClientRect(),ratio=image.naturalWidth/Math.max(1,image.naturalHeight);let w=r.width,h=r.height;if(ratio>0){w=Math.min(w,h*ratio);h=w/ratio;}return {r,w,h};};
 const paint=()=>{const {r,w,h}=size();scale=clamp(scale,1,5);const maxX=Math.max(0,(w*scale-r.width)/2),maxY=Math.max(0,(h*scale-r.height)/2);x=clamp(x,-maxX,maxX);y=clamp(y,-maxY,maxY);image.style.transform=`translate(${x}px,${y}px) scale(${scale})`;stage.classList.toggle('is-zoomed',scale>1.01);};
 const point=event=>({x:event.clientX,y:event.clientY});
 const begin=()=>{const list=[...pointers.values()];if(list.length>=2){carousel.reset?.();const [a,b]=list;gesture={kind:'pinch',distance:Math.max(1,Math.hypot(a.x-b.x,a.y-b.y)),cx:(a.x+b.x)/2,cy:(a.y+b.y)/2,scale,x,y};}else if(list.length){const a=list[0];gesture={kind:scale>1.01?'pan':'swipe',start:a,last:a,x,y,at:performance.now()};}else gesture=null;};
 stage.addEventListener('pointerdown',event=>{if(event.pointerType==='mouse'&&event.button!==0)return;event.preventDefault();pointers.set(event.pointerId,point(event));stage.setPointerCapture(event.pointerId);begin();});
 stage.addEventListener('pointermove',event=>{if(!pointers.has(event.pointerId)||!gesture)return;event.preventDefault();pointers.set(event.pointerId,point(event));const list=[...pointers.values()],g=gesture;
  if(g.kind==='pinch'&&list.length>=2){const [a,b]=list,cx=(a.x+b.x)/2,cy=(a.y+b.y)/2,{r}=size();scale=clamp(g.scale*Math.hypot(a.x-b.x,a.y-b.y)/g.distance,1,5);const factor=scale/g.scale;x=cx-r.left-r.width/2-(g.cx-r.left-r.width/2-g.x)*factor;y=cy-r.top-r.height/2-(g.cy-r.top-r.height/2-g.y)*factor;paint();}
  else if(g.kind==='pan'){const a=list[0];x=g.x+a.x-g.start.x;y=g.y+a.y-g.start.y;paint();}
  else if(g.kind==='swipe'){g.last=point(event);const dx=g.last.x-g.start.x,dy=g.last.y-g.start.y;carousel.drag?.(Math.abs(dx)>Math.abs(dy)?dx:0);}
 });
 const finish=(event,cancelled)=>{if(!pointers.has(event.pointerId))return;const g=gesture;const last=point(event);pointers.delete(event.pointerId);if(pointers.size){begin();if(gesture?.kind==='swipe')gesture.kind='hold';}else{gesture=null;if(g?.kind==='swipe'){const dx=last.x-g.start.x,dy=last.y-g.start.y;if(!cancelled&&Math.abs(dx)>=50&&Math.abs(dx)>Math.abs(dy)*1.3)navigate(dx<0?1:-1,dx);else carousel.settle?.();}paint();}};
 stage.addEventListener('pointerup',event=>finish(event,false));stage.addEventListener('pointercancel',event=>finish(event,true));stage.addEventListener('lostpointercapture',event=>finish(event,true));
 stage.addEventListener('wheel',event=>{event.preventDefault();const {r}=size(),old=scale;const delta=event.deltaY*(event.deltaMode===1?16:event.deltaMode===2?r.height:1);scale=clamp(scale*Math.exp(-clamp(delta,-160,160)*(event.ctrlKey ? .01 : .002)),1,5);const factor=scale/old;x=event.clientX-r.left-r.width/2-(event.clientX-r.left-r.width/2-x)*factor;y=event.clientY-r.top-r.height/2-(event.clientY-r.top-r.height/2-y)*factor;paint();},{passive:false});
 const reset=()=>{pointers.clear();gesture=null;scale=1;x=0;y=0;carousel.reset?.();paint();};
 image.addEventListener('load',paint);
 if(typeof ResizeObserver!=='undefined')new ResizeObserver(paint).observe(stage);
 return {reset};
}
let imagePreview=null;
function openArticleImage(index){
 const article=state.articles.find(a=>a.id===selectedId),images=article?articleImages(article):[];
 if(!images[index])return;imagePreview={article,images,index};renderImagePreview();$('#article-image-dialog').showModal();
}
function renderImagePreview(){
 imageGestures.reset();
 const preview=imagePreview;if(!preview)return;const item=preview.images[preview.index];
 $('#article-image-large').src=window.IntelligenceCards.imageURL(preview.article,item.url);$('#article-image-large').alt=item.alt||preview.article.title;
 for(const [side,offset] of [['prev',-1],['next',1]]){
  const neighbor=$('[data-image-neighbor='+side+']'),item=preview.images[preview.index+offset];
  if(item){neighbor.src=window.IntelligenceCards.imageURL(preview.article,item.url);neighbor.hidden=false;}
  else{neighbor.hidden=true;neighbor.removeAttribute('src');}
 }
 $('#article-image-caption').textContent=(preview.index+1)+' / '+preview.images.length+' · '+(item.alt||preview.article.title);
 $('#article-image-origin').href=link(item.source_url);$('#article-image-status').textContent='';
 $('#article-image-prev').disabled=preview.index===0;$('#article-image-next').disabled=preview.index===preview.images.length-1;
}
const imageTrack=$('#article-image-dialog .intel-image-track');
let imageSlide=null,imageDrag=0;
function resetImageSlide(){imageSlide?.cancel();imageSlide=null;imageDrag=0;imageTrack.style.transform='translateX(0px)';}
function settleImageSlide(from=imageDrag){
 resetImageSlide();
 if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches)imageSlide=imageTrack.animate([{transform:'translateX('+from+'px)'},{transform:'translateX(0px)'}],{duration:240,easing:'ease-out'});
}
function moveImagePreview(delta,drag){
 if(!imagePreview)return;
 const next=imagePreview.index+delta;
 if(next<0||next>=imagePreview.images.length){settleImageSlide();return;}
 const width=imageTrack.getBoundingClientRect().width;
 imagePreview.index=next;renderImagePreview();settleImageSlide(delta*width+(drag||0));
}
const imageGestures=installImageGestures($('#article-image-dialog .intel-image-stage'),$('#article-image-large'),moveImagePreview,{
 reset:resetImageSlide,settle:settleImageSlide,drag:dx=>{
  imageSlide?.cancel();imageSlide=null;
  const edge=imagePreview&&(dx>0?imagePreview.index===0:imagePreview.index===imagePreview.images.length-1);
  imageDrag=edge?dx*.25:dx;imageTrack.style.transform='translateX('+imageDrag+'px)';
 }
});
$('#article-image-dialog').addEventListener('close',()=>imageGestures.reset());
document.addEventListener('keydown',event=>{if($('#article-image-dialog').open&&(event.key==='ArrowLeft'||event.key==='ArrowRight')){event.preventDefault();moveImagePreview(event.key==='ArrowRight'?1:-1);}});
$('#article-image-prev').onclick=()=>moveImagePreview(-1);
$('#article-image-next').onclick=()=>moveImagePreview(1);
$('#article-image-large').onerror=()=>{$('#article-image-status').textContent=lt('图片加载失败，可查看原文或尝试加入素材库。');};
$('#article-image-save').onclick=async()=>{
 const preview=imagePreview;if(!preview||busy)return;const image=preview.images[preview.index],button=$('#article-image-save');let session,transfer;
 busy=true;button.disabled=true;$('#article-image-status').textContent=lt('正在通过原信息源 Profile 读取图片…');
 try{const source=imageSource(preview.article,image);session=await browserSession(source.profile_key||'default');await read(session,image.source_url);
  try{transfer=await session.client.beginPageResourceTransfer([image.url],32*1024*1024,true);}
  catch(error){
   // Some CDNs omit CORS headers. A dedicated image document keeps the same Profile and permits a same-origin fetch.
   await session.connection.command('browsingContext.navigate',{context:session.context,url:image.url,wait:'complete'});
   transfer=await session.client.beginPageResourceTransfer([image.url],32*1024*1024,true);
  }
  if(!transfer.media_type.startsWith('image/'))throw Error(lt('来源返回的内容不是图片'));
  const parts=[];let offset=0;
  while(offset<transfer.size){const chunk=await session.client.readPageResourceChunk(transfer.token,offset);
   if(chunk.next_offset<=offset)throw Error(lt('图片读取中断，请重试'));parts.push(Uint8Array.from(atob(chunk.base64),c=>c.charCodeAt(0)));offset=chunk.next_offset;
  }
  const form=new FormData();form.append('file',new File(parts,transfer.name,{type:transfer.media_type}));form.append('sourceAppId','ai2apps.intelligence');form.append('sourceRef',image.source_url);
  const response=await fetch('/v1/platform/gallery/assets/import',{method:'POST',credentials:'same-origin',headers:{'X-Intelligence-Language':window.IntelligenceI18n?.locale||'en'},body:form}),result=await response.json();
  if(!response.ok)throw Error(result.error?.message||lt('保存到素材库失败'));
  $('#article-image-status').textContent=result.created?lt('已加入素材库'):lt('素材库中已有这张图片');
 }catch(error){$('#article-image-status').textContent=error.message;}
 finally{if(transfer?.token&&session)await session.client.endPageResourceTransfer(transfer.token).catch(()=>{});await closeBrowser(session);busy=false;button.disabled=false;}
};
const writingKinds={short_post:lt('短 Post'),long_article:lt('长文'),video_script:lt('视频稿'),podcast:lt('播客稿'),newsletter:lt('简报')};
const draftLists=new Map();let writingSession=null;
const draftOffsets=new Map(),draftLoading=new Set();
async function loadDrafts(id,append=false){
 if(!id||draftLoading.has(id))return;
 draftLoading.add(id);
 const offset=append?draftOffsets.get(id):0;
 try{
  const result=await api('/channels/'+id+'/drafts?offset='+offset);
  const items=result.items;
  draftLists.set(id,append?[...draftLists.get(id)||[],...items.filter(d=>!draftLists.get(id)?.some(old=>old.id===d.id))]:items);
  draftOffsets.set(id,result.next_offset??null);
  if(previewDraft?.channel_id===id){previewDraft=await api('/drafts/'+previewDraft.id);renderReader();}
 }catch(error){notice(lt('读取稿件失败：')+error.message);}
 finally{draftLoading.delete(id);if(channelId===id&&tab==='drafts'){renderContent();icons();}}
}

function renderDraftList(root){
 const drafts=draftLists.get(channelId),page=window.IntelligencePagination.page('drafts',channelId,window.IntelligencePagination.newest(drafts||[]));
 setHTML(root,drafts===undefined?lt('<p class="intel-help">正在读取稿件…</p>'):page.items.map(d=>it`<section class="intel-topic intel-draft-card" data-draft-preview="${esc(d.id)}" tabindex="0" role="button">${d.images?.[0]?it`<img class="intel-draft-cover" src="${esc(window.IntelligenceCards.imageURL({id:d.images[0].article_id},d.images[0].url))}" alt="${esc(d.title)}" loading="lazy">`: ''}<div class="intel-story-meta">${esc(writingKinds[d.kind])} · 第 ${d.revision} 版 · ${when(d.updated_at)}</div><h2>${esc(d.title)}</h2><p class="intel-help">${esc(d.scope_label)}</p></section>`).join('')+window.IntelligencePagination.button('drafts',page.more||draftOffsets.get(channelId)!=null)||empty('file-pen-line',lt('从情报写成稿件'),lt('选择文章、栏目、热点或整个频道，填写指导后开始撰写。'),''));
}

async function showDraftPreview(id){
 const targetChannel=channelId,d=await api('/drafts/'+id);
 if(channelId!==targetChannel||d.channel_id!==channelId)return;
 mobilePush('reader');previewDraft=d;selectedId=null;readerMode='article';mobilePanel=true;renderReader();
}
function renderDraftPreview(root,d){
 const parts=writingParagraphs(d),images=d.images||[];
 const group=pos=>images.filter(i=>writingImagePosition(i,parts)===pos).map(i=>it`<figure class="intel-draft-image"><img src="${esc(window.IntelligenceCards.imageURL({id:i.article_id},i.url))}" alt="${esc(i.alt||d.title)}" loading="lazy"></figure>`).join('');
 root.classList.add('open');
 setHTML(root,it`<div class="intel-article-head"><span>${esc(writingKinds[d.kind])} · ${when(d.updated_at)}</span><button data-draft="${esc(d.id)}">打开稿件 / 继续修改</button></div><h1 class="intel-draft-title">${esc(d.current.title)}</h1><div class="intel-draft-preview">${parts.map((p,n)=>group(n)+'<p>'+esc(p)+'</p>').join('')+group(parts.length)}</div><section class="intel-citations">${d.evidence.filter(e=>d.current.evidence_ids.includes(e.evidence_id)).map(e=>it`<button data-writing-article="${esc(e.id)}">[${e.evidence_id}] ${esc(e.title)}</button>`).join('')}</section>`);
}
document.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)&&event.target.matches('[data-draft-preview]')){event.preventDefault();safe(showDraftPreview)(event.target.dataset.draftPreview);}});

function startWriting(scope,scopeId){
 const c=channel();if(!c)return;
 const label=scope==='article'?state.articles.find(a=>a.id===scopeId)?.title:scope==='topic'?c.hot_topics?.items.find(t=>t.id===scopeId)?.title:scope==='section'?(c.sections?.find(s=>s.id===scopeId)?.name||lt('待归类')):c.name;
 writingSession={channelId:c.id,scope,scopeId,label,pending:false,requestId:null,draft:null};
 $('#writing-create-form').reset();$('#writing-error').textContent='';$('#writing-status').textContent='';$('#writing-revision-guidance').value='';renderWriting();$('#writing-dialog').showModal();
}
async function openDraft(id){
 const draft=await api('/drafts/'+id);if(state.progressive)await Promise.all(draft.evidence.map(e=>ensureArticle(e.id)));writingSession={channelId:draft.channel_id,label:draft.scope_label,draft,pending:false,requestId:null};
 $('#writing-error').textContent='';$('#writing-status').textContent='';$('#writing-revision-guidance').value='';renderWriting();$('#writing-dialog').showModal();
}
function writingParagraphs(d){return d.current.content.split(/\n\s*\n/);}
function writingImagePosition(image,parts){return image.before&&parts.includes(image.before)?parts.indexOf(image.before):parts.length;}
function writingOrderedImages(d){
 const parts=writingParagraphs(d);return [...d.images||[]].sort((a,b)=>writingImagePosition(a,parts)-writingImagePosition(b,parts));
}
function reorderWritingImage(d,from,to,after=false){
 const images=writingOrderedImages(d),source=images[from],target=images[to];
 if(!source||!target||source===target)return null;
 const next=images.filter((_,n)=>n!==from),at=next.indexOf(target)+(after?1:0);
 next.splice(at,0,{...source,before:target.before||''});
 return next.every((image,n)=>image.article_id===images[n].article_id&&image.url===images[n].url&&(image.before||'')===(images[n].before||''))?null:next;
}
function renderWritingImages(d){
 const root=$('#writing-content'),parts=writingParagraphs(d),images=writingOrderedImages(d);
 const opened=new Set([...root.querySelectorAll('details[open][data-image-position]')].map(el=>el.dataset.imagePosition));
 const pool=state.articles.filter(a=>d.evidence.some(e=>e.id===a.id)).flatMap(a=>{
  const seen=new Set();return [a.cover_image,...(a.images||[])].filter(i=>i&&link(i.url)!=='#'&&!seen.has(i.url)&&seen.add(i.url)).map(i=>({...i,article_id:a.id,article_title:a.title}));
 });
 const same=(a,b)=>a.article_id===b.article_id&&a.url===b.url;
 const picker=pos=>it`<details class="intel-draft-image-picker" data-image-position="${pos}" ${opened.has(String(pos))?'open':''}><summary>添加图片</summary><p class="intel-help">${lt('勾选后自动插入并保存，取消勾选即可移除。')}</p><div class="intel-draft-image-options">${pool.map((i,n)=>{const order=images.findIndex(image=>same(image,i)&&writingImagePosition(image,parts)===pos);return it`<label><input type="checkbox" data-draft-image-choice value="${n}" ${order>=0?'checked':''} ${writingSession.pending?'disabled':''}><img src="${esc(window.IntelligenceCards.imageURL({id:i.article_id},i.url))}" alt="${esc(i.alt||i.article_title)}" loading="lazy">${order>=0&&window.AI2APPS_MOBILE_SURFACE?it`<span class="intel-image-order" aria-label="${lt('图片顺序')} ${order+1}">（${order+1}）</span>`:''}</label>`;}).join('')||lt('暂无相关图片')}</div></details>`;
 const desktopImages=!window.AI2APPS_MOBILE_SURFACE;
 const group=pos=>images.map((i,n)=>writingImagePosition(i,parts)===pos?it`<figure class="intel-draft-image" data-draft-image-index="${n}"><div class="intel-draft-image-stage ${desktopImages?'intel-draft-image-overlay':''}"><div class="intel-draft-image-toolbar"><button type="button" class="intel-image-drag-handle" data-draft-image-drag="${n}" aria-label="${lt('拖动图片调整顺序，也可使用上下方向键')}" ${writingSession.pending?'disabled':''} data-image-tip="${lt('拖动排序')}">⠿${desktopImages?'':' '+lt('拖动排序')}</button></div><img draggable="false" src="${esc(window.IntelligenceCards.imageURL({id:i.article_id},i.url))}" alt="${esc(i.alt)}"><button type="button" class="intel-image-remove" data-remove-draft-image="${n}" aria-label="${lt('移除图片')}" data-image-tip="${lt('移除图片')}" ${writingSession.pending?'disabled':''}>${desktopImages?'×':lt('移除图片')}</button></div></figure>`:'').join('');
 root.innerHTML=parts.map((p,n)=>(d.kind==='short_post'?'':picker(n))+group(n)+'<p>'+esc(p)+'</p>').join('')+group(parts.length)+picker(parts.length);
 const save=async next=>{
  next=writingOrderedImages({...d,images:next});
  const session=writingSession,previous=session.draft;
  session.pending=true;session.draft={...d,images:next};$('#writing-error').textContent='';$('#writing-status').textContent=lt('正在保存…');renderWriting();
  try{session.draft=await api('/drafts/'+d.id+'/images','PUT',{revision:d.revision,images:next.map(i=>({article_id:i.article_id,url:i.url,before:parts.includes(i.before)?i.before:''}))});await loadDrafts(session.channelId);if(writingSession===session)$('#writing-status').textContent=lt('稿件已保存，可继续提出修改要求');}
  catch(error){session.draft=previous;if(writingSession===session){$('#writing-error').textContent=error.message;$('#writing-status').textContent=lt('图片保存失败，已恢复原有图片。');}}
  finally{session.pending=false;if(writingSession===session)renderWriting();}
 };
 root.onchange=safe(async event=>{
  const input=event.target.closest('input[data-draft-image-choice]');if(!input||writingSession.pending)return;
  const image=pool[Number(input.value)],pos=Number(input.closest('details').dataset.imagePosition);if(!image||!Number.isInteger(pos)||pos<0||pos>parts.length)return;
  const next=images.filter(i=>!(same(i,image)&&writingImagePosition(i,parts)===pos));
  if(input.checked)next.push({...image,before:parts[pos]||''});
  await save(next);
 });
 root.onclick=safe(async event=>{
  const b=event.target.closest('button[data-remove-draft-image]');if(!b||writingSession.pending)return;
  const next=[...images];next.splice(Number(b.dataset.removeDraftImage),1);await save(next);
 });
 let drag=null,frame=null;
 const clearDrag=()=>{
  const current=drag;drag=null;if(frame!==null)cancelAnimationFrame(frame);frame=null;
  root.querySelectorAll('.intel-image-dragging,.intel-image-drop-before,.intel-image-drop-after').forEach(el=>el.classList.remove('intel-image-dragging','intel-image-drop-before','intel-image-drop-after'));
  if(current?.handle.hasPointerCapture?.(current.id))current.handle.releasePointerCapture(current.id);
  return current;
 };
 const hit=()=>{
  if(!drag)return;
  root.querySelectorAll('.intel-image-drop-before,.intel-image-drop-after').forEach(el=>el.classList.remove('intel-image-drop-before','intel-image-drop-after'));
  const target=document.elementFromPoint(drag.x,drag.y)?.closest('[data-draft-image-index]');
  drag.to=null;if(!target||!root.contains(target))return;
  const index=Number(target.dataset.draftImageIndex);if(index===drag.from)return;
  const rect=target.getBoundingClientRect();drag.to=index;drag.after=drag.y>rect.top+rect.height/2;
  target.classList.add(drag.after?'intel-image-drop-after':'intel-image-drop-before');
 };
 const scrollDrag=()=>{
  if(!drag)return;
  if(!root.isConnected||writingSession?.draft?.id!==d.id||root.closest('dialog')?.open===false){clearDrag();return;}
  const scroll=root.closest('.intel-manuscript');if(scroll){const r=scroll.getBoundingClientRect();const delta=drag.y<r.top+36?-12:drag.y>r.bottom-36?12:0;if(delta){scroll.scrollTop+=delta;hit();}}
  frame=requestAnimationFrame(scrollDrag);
 };
 root.onpointerdown=event=>{
  const handle=event.target.closest('[data-draft-image-drag]');if(!handle||writingSession.pending||event.button!==0)return;
  event.preventDefault();drag={from:Number(handle.dataset.draftImageDrag),to:null,after:false,id:event.pointerId,handle,x:event.clientX,y:event.clientY};
  handle.setPointerCapture(event.pointerId);handle.closest('figure').classList.add('intel-image-dragging');frame=requestAnimationFrame(scrollDrag);
 };
 root.onpointermove=event=>{if(!drag||event.pointerId!==drag.id)return;drag.x=event.clientX;drag.y=event.clientY;hit();};
 root.onpointerup=safe(async event=>{
  if(!drag||event.pointerId!==drag.id)return;const current=clearDrag();
  if(current.to===null)return;const next=reorderWritingImage(d,current.from,current.to,current.after);if(next)await save(next);
 });
 root.onpointercancel=root.onlostpointercapture=()=>{if(drag)clearDrag();};
 root.onkeydown=safe(async event=>{
  if(drag&&event.key==='Escape'){event.preventDefault();clearDrag();return;}
  const handle=event.target.closest('[data-draft-image-drag]');if(!handle||writingSession.pending||!['ArrowUp','ArrowDown'].includes(event.key))return;
  event.preventDefault();const from=Number(handle.dataset.draftImageDrag),to=from+(event.key==='ArrowUp'?-1:1),next=reorderWritingImage(d,from,to,to>from);
  if(next){await save(next);root.querySelector(`[data-draft-image-drag="${to}"]`)?.focus();}
 });

}
function writingMarkdown(d){
 const parts=writingParagraphs(d),images=d.images||[];
 const group=pos=>images.filter(i=>writingImagePosition(i,parts)===pos).map(i=>'!['+String(i.alt||'').replace(/[\[\]\r\n]/g,' ')+'](<'+i.url.replace(/>/g,'%3E')+'>)').join('\n\n');
 return d.current.title+'\n\n'+parts.map((p,n)=>[group(n),p].filter(Boolean).join('\n\n')).concat(group(parts.length)).filter(Boolean).join('\n\n');
}

function renderWriting(){
 const session=writingSession;if(!session)return;const draft=session.draft;
 $('#writing-heading').textContent=draft?lt('稿件 · ')+writingKinds[draft.kind]:lt('撰写稿件');
 $('#writing-scope').textContent=lt('资料范围：')+session.label+(draft?lt(' · 已选 ')+draft.evidence.length+' / '+draft.total_articles+lt(' 篇情报'):'');
 $('#writing-create-form').hidden=Boolean(draft);$('#writing-workspace').hidden=!draft;
 $('#writing-create-form button[type=submit]').disabled=session.pending;$('#writing-revise-form button[type=submit]').disabled=session.pending;
 $('#writing-copy').disabled=session.pending||session.editing;
 $('#writing-edit').disabled=session.pending||session.editing;
 $('#writing-text-form').hidden=!session.editing;$('#writing-title').hidden=!!session.editing;$('#writing-content').hidden=!!session.editing;
 $('#writing-text-form button[type=submit]').disabled=session.pending;$('#writing-edit-cancel').disabled=session.pending;
 $('#writing-edit-title').disabled=session.pending;$('#writing-edit-content').disabled=session.pending;
 if(session.editing){$('#writing-revise-form button[type=submit]').disabled=true;$('#writing-revision-guidance').disabled=true;return;}
 $('#writing-guidance').disabled=session.pending;$('#writing-kind').disabled=session.pending;$('#writing-revision-guidance').disabled=session.pending;
 if(!draft)return;
 $('#writing-version').textContent=lt('第 ')+draft.revision+lt(' 版 · 自动保存于 ')+when(draft.updated_at);$('#writing-title').textContent=draft.current.title;renderWritingImages(draft);
 const used=new Set(draft.current.evidence_ids);
 $('#writing-references').innerHTML=draft.evidence.filter(e=>used.has(e.evidence_id)).map(e=>it`<button data-writing-article="${esc(e.id)}">[${e.evidence_id}] ${esc(e.title)}</button>`).join('');
 $('#writing-turns').innerHTML=draft.turns.map(t=>it`<div class="intel-chat-question">${t.kind==='manual'?lt('手动编辑'):esc(t.guidance)}</div><div class="intel-chat-answer">${t.kind==='manual'?lt('手动修改已保存'):esc(t.note)}</div>`).join('');
 $('#writing-turns').scrollTop=$('#writing-turns').scrollHeight;
}
function writingEditDirty(){const s=writingSession;return !!s?.editing&&($('#writing-edit-title').value!==s.draft.current.title||$('#writing-edit-content').value!==s.draft.current.content);}
function discardWritingEdit(){if(writingEditDirty()&&!confirm(lt('放弃尚未保存的文本修改？')))return false;if(writingSession?.pending)return false;if(writingSession)writingSession.editing=false;return true;}
$('#writing-edit').onclick=()=>{const s=writingSession;if(!s?.draft||s.pending)return;s.editing=true;s.editRequestId=null;$('#writing-edit-title').value=s.draft.current.title;$('#writing-edit-content').value=s.draft.current.content;$('#writing-error').textContent='';renderWriting();$('#writing-edit-content').focus();};
$('#writing-edit-cancel').onclick=()=>{if(discardWritingEdit())renderWriting();};
$('#writing-edit-title').oninput=$('#writing-edit-content').oninput=()=>{if(writingSession&&!writingSession.pending)writingSession.editRequestId=null;};
$('#writing-text-form').onsubmit=async event=>{
 event.preventDefault();const s=writingSession;if(!s?.editing||s.pending)return;
 s.editRequestId||=crypto.randomUUID();s.pending=true;$('#writing-error').textContent='';renderWriting();
 try{s.draft=await api('/drafts/'+s.draft.id+'/text','PUT',{request_id:s.editRequestId,revision:s.draft.revision,title:$('#writing-edit-title').value,content:$('#writing-edit-content').value});s.editing=false;s.editRequestId=null;await loadDrafts(s.channelId);if(writingSession===s)$('#writing-status').textContent=lt('手动修改已保存');}
 catch(error){if(writingSession===s)$('#writing-error').textContent=error.message;}
 finally{s.pending=false;if(writingSession===s)renderWriting();}
};
$('#writing-dialog').addEventListener('cancel',event=>{if(!discardWritingEdit())event.preventDefault();});
$('#writing-guidance').oninput=$('#writing-kind').onchange=$('#writing-revision-guidance').oninput=()=>{if(writingSession&&!writingSession.pending)writingSession.requestId=null;};
async function submitWriting(event,revise){
 event.preventDefault();const session=writingSession;if(!session||session.pending||session.editing)return;
 const guidance=$(revise?'#writing-revision-guidance':'#writing-guidance').value.trim();if(!guidance)return;
 session.requestId||=crypto.randomUUID();session.pending=true;$('#writing-error').textContent='';$('#writing-status').textContent=revise?lt('AI 正在修改，原稿保留…'):lt('AI 正在根据所选情报撰写…');renderWriting();
 try{const body={request_id:session.requestId,guidance,...(revise?{revision:session.draft.revision}:{scope:session.scope,scope_id:session.scopeId,kind:$('#writing-kind').value})};
  const result=await api(revise?'/drafts/'+session.draft.id+'/revise':'/channels/'+session.channelId+'/drafts','POST',body);
  if(state.progressive)await Promise.all(result.evidence.map(e=>ensureArticle(e.id)));session.draft=result;session.requestId=null;await loadDrafts(session.channelId);
  if(writingSession===session){$('#writing-status').textContent=lt('稿件已保存，可继续提出修改要求');$('#writing-revision-guidance').value='';}
 }catch(error){if(writingSession===session){$('#writing-error').textContent=error.message;$('#writing-status').textContent=lt('可重试；已有稿件保留。');}}
 finally{session.pending=false;if(writingSession===session)renderWriting();}
}
$('#writing-create-form').onsubmit=event=>submitWriting(event,false);$('#writing-revise-form').onsubmit=event=>submitWriting(event,true);
$('#writing-copy').onclick=safe(async()=>{const d=writingSession?.draft;if(d){await navigator.clipboard.writeText(writingMarkdown(d));$('#writing-status').textContent=lt('已复制稿件');}});
let feedbackDraft=null;
function reasonOptions(reasons, selected=[]){
 return reasons.map(r=>it`<label class="intel-feedback-reason"><input type="checkbox" value="${esc(r)}" ${selected.includes(r)?'checked':''}><span>${esc(r)}</span></label>`).join('');
}
async function dislikeDialog(id){
 const article=state.articles.find(a=>a.id===id);if(!article)return;
 const draft={id,signature:null};feedbackDraft=draft;
 const dialog=$('#feedback-dialog'),submit=$('#feedback-form button[type=submit]');
 $('#feedback-article-title').textContent=article.title;$('#feedback-reasons').textContent=lt('AI 正在生成适合这篇文章的理由…');
 $('#feedback-form .intel-form-error').textContent='';$('#feedback-retry').hidden=true;submit.disabled=true;
 if(!dialog.open)dialog.showModal();
 try{const result=await api('/articles/'+id+'/feedback-reasons','POST');if(feedbackDraft!==draft||!dialog.open)return;
  draft.signature=result.signature;$('#feedback-reasons').innerHTML=reasonOptions(result.reasons,article.feedback_reasons||[]);
  submit.disabled=!$('#feedback-reasons input:checked');
 }catch(error){if(feedbackDraft!==draft||!dialog.open)return;$('#feedback-reasons').textContent=lt('尚未记录反馈');$('#feedback-form .intel-form-error').textContent=error.message;$('#feedback-retry').hidden=false;}
}
$('#feedback-dialog').addEventListener('close',()=>{feedbackDraft=null;});
$('#feedback-reasons').onchange=()=>{$('#feedback-form button[type=submit]').disabled=!feedbackDraft?.signature||!$('#feedback-reasons input:checked');};
$('#feedback-retry').onclick=safe(()=>feedbackDraft&&dislikeDialog(feedbackDraft.id));
$('#feedback-form').onsubmit=async event=>{
 event.preventDefault();const draft=feedbackDraft;if(!draft?.signature)return;
 const reasons=[...document.querySelectorAll('#feedback-reasons input:checked')].map(e=>e.value);if(!reasons.length)return;
 const button=event.submitter;button.disabled=true;
 try{await api('/articles/'+draft.id,'PATCH',{feedback:'less',reasons,reason_signature:draft.signature});
  if(feedbackDraft===draft)$('#feedback-dialog').close();await refresh();notice(lt('已保存踩的理由和用户偏好'));
 }catch(error){if(feedbackDraft===draft){$('#feedback-form .intel-form-error').textContent=error.message;$('#feedback-retry').hidden=false;}}
 finally{button.disabled=false;}
};
let postsChannel=null,postsOffset=null;
async function showPosts(id=channelId,offset=0){
 const result=await api('/channels/'+id+'/posts?offset='+offset);postsChannel=id;postsOffset=result.next_offset;
 const html=result.items.map(p=>it`<section class="intel-run"><h3>${esc(p.author||p.source_name)} · ${when(p.published_at||p.retrieved_at)}</h3><div class="intel-body">${esc(p.text)}</div><p>${p.briefings.length?lt('已关联事件'):lt('补充证据')} ${p.briefings.map(a=>it`<button data-post-article="${esc(a.id)}">${esc(a.title)}</button>`).join('')}</p><a href="${link(p.url)}" target="_blank" rel="noopener noreferrer">查看原帖 ↗</a> <button data-promote-post="${esc(p.id)}">提升为情报</button></section>`).join('')||it`<p>暂无已采集帖子</p>`;
 if(offset)$('#posts-list').insertAdjacentHTML('beforeend',html);else $('#posts-list').innerHTML=html;
 $('#posts-more').hidden=postsOffset===null;if(!$('#posts-dialog').open)$('#posts-dialog').showModal();
}
async function showFilteredPosts(id=channelId){
 const result=await api('/channels/'+id+'/filtered-posts');
 $('#filtered-posts-list').innerHTML=result.items.map(r=>it`<section class="intel-run"><h3>${esc(r.page.title||lt('帖子'))}</h3><a href="${link(r.page.url)}" target="_blank" rel="noopener noreferrer">查看原帖 ↗</a><p>${esc((r.page.text||'').slice(0,600))}</p><p>${r.stage==='list'?lt('列表初筛'):lt('正文判断')} · ${esc(r.reason)}</p><small>${when(r.updated_at)}</small> ${r.status==='restored'?lt('<span>已恢复 · 后续更新处理</span>'):it`<button data-restore-post="${esc(r.id)}" data-channel="${esc(id)}">恢复</button>`}</section>`).join('')||lt('<p>暂无过滤记录。</p>');
 $('#filtered-posts-dialog').showModal();
}
let sectionEdits=[],sectionBaseline=[];
function readSectionEditor(){
 return [...document.querySelectorAll('#channel-sections-preview [data-section-edit]')].map(row=>({id:row.dataset.sectionEdit,name:row.querySelector('[data-section-name]').value.trim(),description:row.querySelector('[data-section-description]').value.trim()}));
}
function renderSectionEditor(){
 const root=$('#channel-sections-preview');
 if(!editing){root.innerHTML=lt('创建时，AI 会根据频道兴趣自动规划 4–8 个专属栏目；创建后可在设置中编辑。');return;}
 root.innerHTML=lt('<div class="intel-section-editor-head"><strong>频道栏目</strong><button type="button" data-add-section>＋ 添加栏目</button></div><p>修改名称和说明会用于后续文章归类。删除栏目会保留文章，并转入待归类；保存频道后生效。</p>')+sectionEdits.map(s=>it`<div class="intel-section-editor-row" data-section-edit="${esc(s.id)}"><label>栏目名称<input data-section-name value="${esc(s.name)}" maxlength="24" required></label><button type="button" data-remove-section="${esc(s.id)}" aria-label="删除栏目 ${esc(s.name)}">删除</button><label class="intel-section-description">归类说明<textarea data-section-description maxlength="240" rows="2" required>${esc(s.description)}</textarea></label></div>`).join('');
}
$('#channel-sections-preview').addEventListener('click',event=>{
 const button=event.target.closest('button');if(!button)return;
 if(button.hasAttribute('data-add-section')){sectionEdits=readSectionEditor();if(sectionEdits.length>=32){notice(lt('最多添加 32 个栏目'));return;}sectionEdits.push({id:crypto.randomUUID(),name:'',description:''});renderSectionEditor();$('#channel-sections-preview [data-section-edit]:last-child input')?.focus();}
 if(button.dataset.removeSection){const row=button.closest('[data-section-edit]'),name=row.querySelector('[data-section-name]').value||lt('未命名栏目');if(!confirm(lt('删除“')+name+lt('”？文章会保留并转到待归类，保存频道后生效。')))return;sectionEdits=readSectionEditor().filter(s=>s.id!==button.dataset.removeSection);renderSectionEditor();}
});
async function channelDialog(c=null,starter=''){
 channelHandoff=null;
 editing=c?.id||null;sectionEdits=(c?.sections||[]).map(s=>({...s}));sectionBaseline=sectionEdits.map(s=>({...s}));renderSectionEditor();$('#channel-dialog-title').textContent=c?lt('频道设置'):lt('创建情报频道');$('#channel-name').value=c?.name||starter;$('#channel-interests').value=c?.interests||({[lt('腕表')]:lt('关注机械腕表新品、独立制表与行业重要动态。'),[lt('人工智能')]:lt('关注人工智能模型、开源项目、产品发布与重要研究。'),[lt('摄影')]:lt('关注相机新品、镜头评测、摄影技术和行业动态。')}[starter]||'');$('#channel-excluded').value=c?.excluded||'';$('#channel-post-filter').value=c?.post_filter_level||'standard';$('#channel-post-guidance').value=c?.post_filter_guidance||'';$('#channel-output-language').value=c?.output_language||window.IntelligenceI18n?.outputLocale?.()||'en';$('#channel-interval').value=c?.interval_hours||0;$('#channel-auto-topics').checked=!!c?.auto_topics;$('#delete-channel').hidden=!c;$('#channel-dialog .intel-form-error').textContent='';$('#channel-dialog').showModal();
 const submit=$('#channel-form button[type=submit]');submit.disabled=true;$('#create-knowledge').disabled=true;$('#knowledge-buckets').textContent=lt('正在读取知识库…');$('#new-knowledge-name').value=(c?.name||starter)?(c?.name||starter)+lt('情报'):'';
 try{
  const {items}=await api('/knowledge/buckets'),selected=new Set(c?.knowledge_bucket_ids||[]);
  $('#knowledge-buckets').innerHTML=items.map(b=>bucketOption(b,selected.has(b.id))).join('')||lt('<p class="intel-help">暂无可选知识库，可以创建一个专用知识库。</p>');
  for(const id of selected)if(!items.some(b=>b.id===id))$('#knowledge-buckets').insertAdjacentHTML('beforeend',bucketOption({id,name:lt('原知识库不可用（取消勾选以解除关联）')},true));
  submit.disabled=false;$('#create-knowledge').disabled=false;
 }catch(error){$('#knowledge-buckets').textContent=lt('读取失败，请关闭后重试');$('#channel-dialog .intel-form-error').textContent=error.message;}

}
function bucketOption(b,selected){return it`<label class="intel-bucket-option"><input type="checkbox" value="${esc(b.id)}" ${selected?'checked':''}><span>${esc(b.name)} <small>${b.visibility==='installation'?lt('本机共享 · 其他本机用户可见'):lt('私有')}</small></span></label>`;}
$('#create-knowledge').onclick=async()=>{
 const button=$('#create-knowledge'),name=$('#new-knowledge-name').value.trim();if(!name){$('#channel-dialog .intel-form-error').textContent=lt('请输入新知识库名称');return;}button.disabled=true;
 try{const response=await fetch('/v1/platform/knowledge/buckets',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,scope:'private',imported:false})});const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:lt('创建知识库失败'));$('#knowledge-buckets').insertAdjacentHTML('beforeend',bucketOption(result,true));$('#new-knowledge-name').value='';$('#channel-dialog .intel-form-error').textContent='';}
 catch(error){$('#channel-dialog .intel-form-error').textContent=error.message;}finally{button.disabled=false;}
};
$('#new-channel').onclick=$('#sidebar-create').onclick=safe(()=>channelDialog());$('#edit-channel').onclick=safe(()=>channelDialog(channel()));
$('#channel-form').onsubmit=async event=>{event.preventDefault();const submit=event.submitter;submit.disabled=true;const originalText=submit.textContent;submit.textContent=editing?lt('正在保存…'):lt('AI 正在规划栏目…');try{const value=await api('/channels'+(editing?'/'+editing:channelHandoff?'?handoff_run='+encodeURIComponent(channelHandoff.run_id)+'&handoff_id='+encodeURIComponent(channelHandoff.interaction_id):''),editing?'PUT':'POST',{...(editing?{sections:readSectionEditor(),expected_sections:sectionBaseline}:{}),name:$('#channel-name').value.trim(),interests:$('#channel-interests').value.trim(),excluded:$('#channel-excluded').value.trim(),post_filter_level:$('#channel-post-filter').value,post_filter_guidance:$('#channel-post-guidance').value.trim(),output_language:$('#channel-output-language').value,interval_hours:Number($('#channel-interval').value),auto_topics:$('#channel-auto-topics').checked,knowledge_bucket_ids:[...document.querySelectorAll('#knowledge-buckets input:checked')].map(e=>e.value)});if(channelHandoff&&appHandoff?.interaction_id===channelHandoff.interaction_id){appHandoff.channel=value;renderHandoff();}channelId=value.id;selectedId=null;sectionId='';tab=mobileQuery.matches?'articles':'sources';if(mobileQuery.matches)mobilePush('channel');$('#channel-dialog').close();await refresh();}catch(error){$('#channel-dialog .intel-form-error').textContent=error.message;}finally{submit.disabled=false;submit.textContent=originalText;}};
$('#delete-channel').onclick=safe(async()=>{if(!confirm(lt('删除此频道及其文章、信息源和更新记录？')))return;await api('/channels/'+editing,'DELETE');$('#channel-dialog').close();selectedId=null;await refresh();});
async function loadProfiles(){profiles=await requestJSON(window.AI2APPS_MOBILE_SURFACE?'/v1/platform/intelligence/browser-profiles':'/v1/platform/client/browser-profiles',{credentials:'same-origin'});}
function profileOptions(selected='default'){return profiles.map(p=>it`<option value="${esc(p.key)}" ${p.key===selected?'selected':''}>${esc(p.is_default?lt('Default Profile'):p.name)}</option>`).join('');}
async function sourceDialog(source=null){await loadProfiles();const agentChoices=await api('/source-agents');editingSource=source?.id||null;$('#source-form').reset();$('#source-dialog-title').textContent=source?lt('信息源设置'):lt('添加信息源');$('#source-form button[type=submit]').textContent=source?lt('保存设置'):lt('加入频道');$('#source-name').value=source?.name||'';$('#source-url').value=source?.url||'';$('#source-kind').value=source?.kind||'website';$('#source-social-interval').value=source?.social_interval_hours||6;$('#source-profile').innerHTML=profileOptions(source?.profile_key||'default');if(source&&!profiles.some(p=>p.key===(source.profile_key||'default'))){$('#source-profile').insertAdjacentHTML('afterbegin',it`<option value="" disabled selected>原 Profile 已删除，请重新选择</option>`);}for(const kind of ['list','article']){const selected=source?.[kind+'_agent_generation_id']||'';const field=$('#source-'+kind+'-agent');field.innerHTML=lt('<option value="">自动生成 / 复用</option>')+agentChoices.agents.map(a=>it`<option value="${esc(a.generation_id)}">${esc(a.name)}</option>`).join('');if(selected&&!agentChoices.agents.some(a=>a.generation_id===selected))field.insertAdjacentHTML('beforeend',it`<option value="${esc(selected)}">原指定版本不可用，请重新选择</option>`);field.value=selected;}$('#source-profile').required=true;$('#source-dialog .intel-form-error').textContent='';initSourceMode();$('#source-dialog').showModal();}
function updateSourceMode(){
 const mode=$('#source-mode').value,isX=mode==='x',custom=mode!=='url'&&!isX;
 let xhs=mode==='xiaohongshu-search';try{const u=new URL($('#source-url').value);xhs ||= mode==='url'&&['xiaohongshu.com','www.xiaohongshu.com'].includes(u.hostname)&&u.pathname.replace(/\/$/,'')==='/search_result';}catch(_){}
 $('#source-xhs-sort-label').hidden=!xhs;
 $('#source-x-fields').hidden=!isX;$('#source-x-values').required=isX;
 for(const id of ['source-url','source-kind','source-list-agent','source-article-agent'])$('#'+id).closest('label').hidden=isX;
 $('#source-list-agent').closest('label').hidden=isX||xhs;
 const xMode=$('#source-x-mode').value;
 $('#source-x-sort-label').hidden=!isX||xMode!=='search';
 $('#source-x-title').textContent=window.t('intelligence.x.'+xMode);
 $('#source-x-help').textContent=window.t(xMode==='lists'?'intelligence.x.lists_help':'intelligence.x.help');
 $('#source-x-values').placeholder=xMode==='lists'?'https://x.com/i/lists/123456789':xMode==='accounts'?'@Formula1\n@F1':'F1 qualifying\nMcLaren';
 if(isX){$('#source-kind').value='social';$('#source-url').value='https://x.com/';}
 $('#source-query-label').hidden=!custom;$('#source-query').required=custom;$('#source-url').readOnly=custom||isX;
 $('#source-query-title').textContent=mode==='weibo-account'?lt('账号主页链接或 UID'):mode.endsWith('topic')?lt('话题标签'):lt('搜索关键词');
 $('#source-query').placeholder=mode==='weibo-account'?lt('例如：https://weibo.com/u/1234567890'):mode==='weibo-topic'?lt('例如：腕表（无需 #）'):mode==='youtube-topic'?lt('例如：watches（无需 #）'):lt('例如：腕表、机械表评测');
 if(custom){$('#source-kind').value='social';try{$('#source-url').value=window.IntelligenceSocial.sourceURL(mode,$('#source-query').value,$('#source-url').value);}catch(_){$('#source-url').value='';}}
}
function initSourceMode(){
 $('#source-mode').value='url';$('#source-query').value='';
 $('#source-xhs-sort').value=state.sources.find(s=>s.id===editingSource)?.xiaohongshu_sort||'latest';
 const existing=state.sources.find(s=>s.id===editingSource);
 $('#source-x-sort').value=existing?.x_sort||'latest';
 $('#source-x-mode').value=existing?.x_mode||'accounts';$('#source-x-values').value=(existing?.x_values||[]).join('\n');
 if(existing?.x_mode){$('#source-mode').value='x';updateSourceMode();return;}
 try{const u=new URL($('#source-url').value);if(['xiaohongshu.com','www.xiaohongshu.com'].includes(u.hostname)&&u.pathname==='/search_result'){$('#source-mode').value='xiaohongshu-search';$('#source-query').value=u.searchParams.get('keyword')||'';}else if(window.IntelligenceSocial.youtube({url:u.href})){
  if(u.pathname==='/results'){$('#source-mode').value='youtube-search';$('#source-query').value=u.searchParams.get('search_query')||'';}
  else if(u.pathname.startsWith('/hashtag/')){$('#source-mode').value='youtube-topic';$('#source-query').value=decodeURIComponent(u.pathname.slice(9));}
 }else if(window.IntelligenceSocial.weibo({url:u.href})){
  if(u.hostname!=='s.weibo.com'){$('#source-mode').value='weibo-account';$('#source-query').value=u.href;}else if(/^#[^#]+#$/.test(u.searchParams.get('q')||'')){$('#source-mode').value='weibo-topic';$('#source-query').value=u.searchParams.get('q').slice(1,-1);}
 }}catch(_){}updateSourceMode();
}
$('#source-url').oninput=updateSourceMode;$('#source-mode').onchange=updateSourceMode;$('#source-x-mode').onchange=updateSourceMode;$('#source-query').oninput=updateSourceMode;
$('#add-source').onclick=safe(()=>sourceDialog());
$('#source-form').onsubmit=async event=>{event.preventDefault();event.submitter.disabled=true;try{await api(editingSource?'/sources/'+editingSource:'/channels/'+channelId+'/sources',editingSource?'PUT':'POST',{x_sort:$('#source-x-sort').value,xiaohongshu_sort:$('#source-xhs-sort').value,x_mode:$('#source-mode').value==='x'?$('#source-x-mode').value:'',x_values:$('#source-mode').value==='x'?$('#source-x-values').value.split(/\r?\n/).map(v=>v.trim()).filter(Boolean):[],name:$('#source-name').value.trim(),url:$('#source-url').value.trim(),kind:$('#source-kind').value,social_interval_hours:Number($('#source-social-interval').value),profile_key:$('#source-profile').value,list_agent_generation_id:$('#source-list-agent').value,article_agent_generation_id:$('#source-article-agent').value,enabled:editingSource?state.sources.find(s=>s.id===editingSource).enabled:true});$('#source-dialog').close();await refresh();}catch(error){$('#source-dialog .intel-form-error').textContent=error.message;}finally{event.submitter.disabled=false;}};
async function loadConversation(id){
 const chat=conversationState(id);if(chat.loading)return;chat.loading=true;
 try{const result=await api('/channels/'+id+'/conversation');chat.turns=result.turns;chat.loaded=true;chat.error='';}
 catch(error){chat.error=error.message;}finally{chat.loading=false;if(channelId===id)renderChannelChat();}
}
function renderChannelChat(){
 syncMobile();
 const c=channel(),chat=c?conversationState(c.id):null;
 $('#intel-reader').classList.toggle('open',mobilePanel);
 $('#intel-entity-reader').hidden=readerMode!=='entity';
 $('#show-entity-detail').classList.toggle('active',readerMode==='entity');
 $('#intel-article-reader').hidden=readerMode!=='article';
 $('#channel-chat').hidden=readerMode!=='chat';
 $('#show-channel-chat').classList.toggle('active',readerMode==='chat');
 $('#show-channel-article').classList.toggle('active',readerMode==='article');
 const articleChat=window.IntelligenceArticleChat;
 articleChat?.setVisible(readerMode==='article-chat');
 const articleChatTab=$('#show-article-chat');
 if(articleChatTab){articleChatTab.textContent=articleChat?.currentTitle()||window.IntelligenceI18n.format('chat.mini.title',{});articleChatTab.hidden=!selectedId||articleChat?.currentArticleId()!==selectedId;articleChatTab.classList.toggle('active',readerMode==='article-chat');}
 $('#intel-reader').classList.toggle('article-chat-visible',readerMode==='article-chat');
 $('#show-channel-article').disabled=!selectedId&&previewDraft?.channel_id!==channelId;
 const input=$('#channel-chat-question');
 if(input.dataset.channel!==channelId){input.value=chat?.sending?'':chat?.draft||'';input.dataset.channel=channelId||'';}
 input.disabled=!c||!!chat?.sending;
 $('#send-channel-chat').disabled=!c||!!chat?.sending||!!chat?.loading||!chat?.loaded;
 const selected=state.articles.find(a=>a.id===selectedId&&a.channel_id===channelId);
 $('#channel-chat-context').textContent=selected?lt('结合当前文章：')+selected.title:lt('向频道提问');
 $('#channel-chat-status').textContent='';$('#channel-chat-status').hidden=true;
 channelSurface.renderTurns(chat?.turns||[],references=>{
  const refs=document.createElement('div');refs.className='intel-chat-refs';
  refs.innerHTML=references.map(r=>r.kind==='knowledge'?it`<details><summary>[${r.number}] 知识库 · ${esc(r.title)}</summary><p>${esc(r.excerpt||'')}</p></details>`:it`<button type="button" data-article="${esc(r.article_id)}">[${r.number}] ${esc(r.title)}</button>`).join('');return refs;
 },chat?.sending?{question:chat.draft,status:lt('正在阅读频道资料并回答…')}:chat?.error?{question:chat.failedQuestion,error:chat.error}:null);
 if(c&&!chat.loaded&&!chat.loading&&!chat.error&&(!progressiveData()||mobilePage==='reader'&&readerMode==='chat'))loadConversation(c.id);
}
$('#channel-chat-question').oninput=()=>{if(channel()){const chat=conversationState(channelId);chat.draft=$('#channel-chat-question').value;chat.requestId=null;chat.requestArticle=undefined;}};
$('#show-entity-detail').onclick=()=>{readerMode='entity';mobilePanel=true;renderChannelChat();};
$('#show-channel-chat').onclick=()=>{readerMode='chat';renderReader();};
$('#show-channel-article').onclick=showArticleDetails;
$('#open-channel-chat').onclick=()=>{readerMode='chat';mobilePanel=true;const chat=conversationState(channelId);if(!chat.loaded&&!chat.loading){chat.error='';loadConversation(channelId);}renderReader();$('#channel-chat-question').focus();};
$('#close-channel-panel').onclick=()=>{mobilePanel=false;renderReader();};
$('#channel-chat-form').onsubmit=async event=>{
 event.preventDefault();const id=channelId,chat=conversationState(id),question=$('#channel-chat-question').value.trim();
 if(!id||!question||chat.sending||!chat.loaded)return;
 chat.draft=question;chat.requestId=chat.requestId||crypto.randomUUID();chat.sending=true;chat.error='';chat.failedQuestion='';$('#channel-chat-question').value='';
 // Keep retry identity and article context stable even if the user navigates while waiting.
 chat.requestArticle=chat.requestArticle===undefined?selectedId:chat.requestArticle;
 renderChannelChat();
 try{const turn=await api('/channels/'+id+'/conversation','POST',{question,request_id:chat.requestId,article_id:chat.requestArticle});
  if(!chat.turns.some(t=>t.id===turn.id))chat.turns.push(turn);
  chat.draft='';chat.requestId=null;chat.requestArticle=undefined;
  if(channelId===id)$('#channel-chat-question').value='';
 }catch(error){chat.error=error.message+lt('；可点击发送重试');chat.failedQuestion=question;if(channelId===id)$('#channel-chat-question').value=question;}
 finally{chat.sending=false;if(channelId===id)renderChannelChat();}
};
async function readArticle(id){
 window.IntelligenceEntities.invalidateArticle?.(id);
 // Save the previous route, then prepare article content before revealing it.
 mobilePush('reader',()=>{previewDraft=null;readerMode='article';mobilePanel=true;selectedId=id;articleOpening=id;document.querySelectorAll('#intel-content .intel-story[data-article]').forEach(card=>card.classList.toggle('selected',card.dataset.article===id));renderReader();});
 try{const article=await api('/articles/'+id,'PATCH',{read:true});if(state.progressive)mergeArticle(article);if(articleOpening===id)articleOpening=null;await refresh();}
 finally{if(articleOpening===id)articleOpening=null;if(selectedId===id&&readerMode==='article')renderReader();}
}
let mobileSearchTimer;$('#search-articles').oninput=()=>{if(!progressiveData()){renderContent();icons();return;}clearTimeout(mobileSearchTimer);mobileSearchTimer=setTimeout(mobileFilterChanged,250);};$('#article-filter').onchange=mobileFilterChanged;$('#article-type-filter').onchange=mobileFilterChanged;$('#refresh-view').onclick=safe(refresh);$('#channel-loading-retry').onclick=safe(refresh);
document.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)&&event.target.matches('[data-article]')){event.preventDefault();safe(readArticle)(event.target.dataset.article);}});
document.addEventListener('click',safe(async event=>{
 if(cardMenu&&!cardMenu.contains(event.target)&&!event.target.closest('[data-card-menu]'))closeCardMenu();
 const b=event.target.closest('button,[data-article],[data-draft-preview]');if(!b||b.disabled)return;
 if(b.dataset.cardMenu){openCardMenu(b);return;}
 if(b.dataset.cardRead||b.dataset.cardFavorite){
  const id=b.dataset.cardRead||b.dataset.cardFavorite,article=state.articles.find(a=>a.id===id);if(!article)return;
  b.disabled=true;const change=b.dataset.cardRead?{read:!article.read}:{favorite:!article.favorite};
  try{const saved=await api('/articles/'+id,'PATCH',change);const current=state.articles.find(a=>a.id===id);if(current)for(const key of Object.keys(change))current[key]=!!saved[key];closeCardMenu();renderSections();renderContent();syncArticleFavorite();icons();}finally{b.disabled=false;}
  return;
 }
 if(cardMenu&&!cardMenu.contains(event.target))closeCardMenu();

 if(b.hasAttribute('data-mobile-articles-retry')){await loadMobileArticles();return;}
 if(b.dataset.listMore){if(state.progressive&&b.dataset.listMore==='articles'){b.disabled=true;try{await loadMobileArticles(true);}finally{b.disabled=false;}return;}if(b.dataset.listMore==='drafts'&&draftOffsets.get(channelId)!=null){b.disabled=true;await loadDrafts(channelId,true);}if(['entities','opportunities','dismissed'].includes(b.dataset.listMore))return;window.IntelligencePagination.more(b.dataset.listMore);renderContent();icons();return;}
 if(b.dataset.action==='reload-article-entities'){window.IntelligenceEntities.invalidateArticle?.(selectedId);renderReader();return;}
 if(b.hasAttribute('data-browse-posts')){await showPosts();return;}
 if(b.id==='posts-more'){await showPosts(postsChannel,postsOffset);return;}
 if(b.dataset.promotePost){b.disabled=true;try{const article=await api('/channels/'+postsChannel+'/posts/'+b.dataset.promotePost+'/promote','POST');await refresh();$('#posts-dialog').close();await readArticle(article.id);}finally{b.disabled=false;}return;}
 if(b.dataset.postArticle){$('#posts-dialog').close();await readArticle(b.dataset.postArticle);return;}
 if(b.hasAttribute('data-show-filtered')){await showFilteredPosts();return;}
 if(b.dataset.restorePost){b.disabled=true;try{await api('/channels/'+b.dataset.channel+'/filtered-posts/'+b.dataset.restorePost+'/restore','POST');await showFilteredPosts(b.dataset.channel);notice(lt('已恢复，将在后续更新处理'));}finally{b.disabled=false;}return;}

 if(b.dataset.close){if(b.dataset.close==='import-dialog'&&importPending)return;if(b.dataset.close==='writing-dialog'&&!discardWritingEdit())return;$('#'+b.dataset.close).close();return;}
 if(b.dataset.channel){unavailableNotificationChannel=false;window.IntelligencePagination.reset();if(mobileQuery.matches){mobilePush('channel');tab='articles';}previewDraft=null;channelId=b.dataset.channel;readerMode='chat';mobilePanel=false;selectedId=null;sectionId='';render();if(progressiveData())await loadMobileChannel();if(tab==='drafts')await loadDrafts(channelId);return;}
 if(b.hasAttribute('data-section')){sectionId=b.dataset.section;selectedId=null;articleOpening=null;previewDraft=null;readerMode='chat';mobilePanel=false;mobileFilterChanged();return;}
 if(b.dataset.action==='sync-knowledge'){b.disabled=true;try{await api('/channels/'+channelId+'/knowledge-sync','POST');await refresh();}finally{b.disabled=false;}return;}
 if(b.dataset.action==='update-topics'){await updateTopics();return;}
 if(b.dataset.imageIndex!==undefined){openArticleImage(Number(b.dataset.imageIndex));return;}
 if(b.dataset.action==='extract-images'){await extractArticleImages();return;}
 if(b.dataset.action==='extract-cover'){await extractArticleCover();return;}
 if(b.dataset.action==='create-sections'){await createSections();return;}
 if(b.dataset.write){startWriting(b.dataset.write,b.dataset.scopeId||'');return;}
 if(b.dataset.draftPreview){await showDraftPreview(b.dataset.draftPreview);return;}
 if(b.dataset.draft){await openDraft(b.dataset.draft);return;}
 if(b.dataset.writingArticle){if(!discardWritingEdit())return;$('#writing-dialog').close();await readArticle(b.dataset.writingArticle);return;}
 if(b.dataset.tab){window.IntelligencePagination.reset();tab=b.dataset.tab;render();if(progressiveData())await loadMobileChannel();if(tab==='drafts')await loadDrafts(channelId);return;}
 if(b.dataset.article){await readArticle(b.dataset.article);return;}
 if(b.dataset.starter){await channelDialog(null,b.dataset.starter);return;}
 if(b.dataset.action==='create')await channelDialog();
 if(b.dataset.action==='sources'){tab='sources';render();}
 if(b.dataset.action==='recommend')await recommend();
 if(b.dataset.action==='close-reader'){previewDraft=null;selectedId=null;readerMode='chat';mobilePanel=false;renderReader();}
 if(b.dataset.resumeSocial){await api('/sources/'+b.dataset.resumeSocial+'/social-resume','POST');await refresh();notice(lt('已恢复采集；仍遵守平台冷却时间'));return;}
 if(b.dataset.updateSource){await collect(channelId,false,b.dataset.updateSource);return;}
 if(b.dataset.editSource){await sourceDialog(state.sources.find(s=>s.id===b.dataset.editSource));return;}
 if(b.dataset.toggleSource){const s=state.sources.find(s=>s.id===b.dataset.toggleSource);await api('/sources/'+s.id,'PUT',{name:s.name,url:s.url,kind:s.kind,x_mode:s.x_mode||'',x_values:s.x_values||[],social_interval_hours:s.social_interval_hours||6,profile_key:s.profile_key||'default',list_agent_generation_id:s.list_agent_generation_id||'',article_agent_generation_id:s.article_agent_generation_id||'',enabled:!s.enabled});await refresh();}
 if(b.dataset.deleteSource){if(!confirm(lt('从频道移除此信息源？已有文章会保留。')))return;await api('/sources/'+b.dataset.deleteSource,'DELETE');await refresh();}
 if(b.dataset.action==='edit-feedback'){await dislikeDialog(selectedId);return;}
 if(b.dataset.favorite){const article=state.articles.find(a=>a.id===b.dataset.favorite);if(!article)return;b.disabled=true;
  try{const saved=await api('/articles/'+article.id,'PATCH',{favorite:!article.favorite});const current=state.articles.find(a=>a.id===article.id);if(current)current.favorite=!!saved.favorite;syncArticleFavorite();renderSections();renderContent();}
  finally{b.disabled=false;}return;
 }
 if(b.dataset.feedback){const a=state.articles.find(a=>a.id===selectedId);if(!a)return;
  if(b.dataset.feedback==='less'&&a.feedback!=='less'){await dislikeDialog(a.id);return;}
  b.disabled=true;try{await api('/articles/'+a.id,'PATCH',{feedback:a.feedback===b.dataset.feedback?'':b.dataset.feedback});await refresh();}finally{b.disabled=false;}
 }
}));
// Each operation owns an explicitly created context, never guesses the user's focused tab.
async function openEntityOriginal(id,sourceUrl){
 const article=state.articles.find(a=>a.id===id);
 if(!article)throw Error(lt('相关文章已移除，请刷新列表。'));
 const reference=sourceUrl?article.sources.find(s=>s.url===sourceUrl):article.sources[0];
 if(!reference||link(reference.url)==='#')throw Error(lt('此文章没有可用的原文地址。'));
 if(window.AI2APPS_MOBILE_SURFACE){const anchor=document.createElement('a');anchor.href=reference.url;anchor.target='_blank';anchor.rel='noopener noreferrer';anchor.click();return;}
 const source=imageSource(article,{source_url:reference.url});
 let session;
 try{
  session=await browserSession(source.profile_key||'default');
  await session.connection.command('browsingContext.navigate',{context:session.context,url:reference.url,wait:'interactive'});
  session.retain=true;
  await session.connection.command('browsingContext.activate',{context:session.context});
 }finally{await closeBrowser(session);}
}
async function savedManualArticle(target,url){
 const result=await api('/channels/'+target+'/import-result?url='+encodeURIComponent(url));return result.article||null;
}
async function submitManualArticle(path,body,target,url){
 try{return await api(path,'POST',body);}
 catch(error){
  if(!error.requestUncertain)throw error;
  // A transport error is an unknown outcome, not permission to replay paid work.
  $('#import-status').textContent=lt('正在确认收录结果…');
  const deadline=Date.now()+180000;
  do{
   try{const article=await savedManualArticle(target,url);if(article)return article;}
   catch(checkError){if(!checkError.requestUncertain)throw checkError;}
   if(Date.now()>=deadline)break;
   await new Promise(resolve=>setTimeout(resolve,2000));
  }while(Date.now()<deadline);
  throw Error(lt('连接中断，尚未确认收录结果；请稍后刷新文章列表查看。'));
 }
}
let importChannelId=null,importPending=false;
$('#import-article').onclick=safe(async()=>{if(importPending)return;await loadProfiles();importChannelId=channelId;$('#import-form').reset();$('#import-profile').innerHTML=profileOptions();$('#import-mode').onchange();$('#import-file').onchange();$('#import-status').textContent='';$('#import-form .intel-form-error').textContent='';$('#import-dialog').showModal();});
$('#import-mode').onchange=()=>{const file=$('#import-mode').value==='file';$('#import-url-fields').hidden=file;$('#import-file-fields').hidden=!file;$('#import-url').required=!file;$('#import-file').required=file;};
$('#import-file').onchange=()=>{const image=/\.(png|jpe?g|webp|gif)$/i.test($('#import-file').files[0]?.name||'');$('#import-image-choice').hidden=!image;document.querySelectorAll('[name="image-summary"]').forEach(input=>{input.required=image&&$('#import-mode').value==='file';input.checked=false;});};
$('#import-mode').addEventListener('change',()=>$('#import-file').onchange());
$('#import-dialog').addEventListener('cancel',event=>{if(importPending)event.preventDefault();});
$('#import-form').onsubmit=async event=>{
 event.preventDefault();if(importPending)return;const target=importChannelId;importPending=true;
 const submit=$('#import-form button[type=submit]');submit.disabled=true;$('#import-form .intel-form-error').textContent='';let session;
 try{
  let result;
  if($('#import-mode').value==='url'){
   const url=$('#import-url').value.trim();if(!/^https?:$/.test(new URL(url).protocol))throw Error(lt('请输入 HTTP 或 HTTPS URL'));
   $('#import-status').textContent=lt('正在通过 AI 浏览器读取网页…');const profile=$('#import-profile').value;
   result=await savedManualArticle(target,url);
   if(!result){
   if(window.AI2APPS_MOBILE_SURFACE){result=await submitManualArticle('/channels/'+target+'/import-link',{url,profile_key:profile},target,url);}
   else{session=await browserSession(profile);const page=await read(session,url,{max_chars:20000});
   $('#import-status').textContent=lt('正在归类并收录…');
   result=await submitManualArticle('/channels/'+target+'/import-url',{profile_key:profile,page:{source_id:'',url:page.url||url,requested_url:url,title:page.title||url,text:page.text,source_blocks:page.source_blocks||[],images:(page.images||[]).slice(0,24),image_url:page.cover_image?.url||'',content_type:'webpage'}},target,url);}
   }
  }else{
   const file=$('#import-file').files[0];if(!file||file.size>20*1024*1024)throw Error(lt('请选择不超过 20MB 的文件'));
   $('#import-status').textContent=lt('正在读取文件并归类…');const form=new FormData();form.append('file',file);form.append('title',$('#import-title').value);form.append('summarize_image',String(!$('#import-image-choice').hidden&&document.querySelector('[name="image-summary"]:checked')?.value==='yes'));
   const response=await fetch('/v1/platform/intelligence/channels/'+target+'/import-file',{method:'POST',credentials:'same-origin',headers:{'X-Intelligence-Language':window.IntelligenceI18n?.locale||'en'},body:form});result=await response.json();if(!response.ok)throw Error(lt(typeof result.detail==='string'?result.detail:lt('收录失败')));
  }
  mergeArticle(result);mobileChannelViews.delete(target);for(const [scope,entry] of mobileArticleLists)if(JSON.parse(scope)[0]===target)entry.loaded=false;
  $('#import-dialog').close();await refresh();if(channelId===target){tab='articles';sectionId='';render();await readArticle(result.id);}notice(lt('文章已收录'));
 }catch(error){$('#import-form .intel-form-error').textContent=error.message;$('#import-status').textContent='';}
 finally{await closeBrowser(session);importPending=false;submit.disabled=false;}
};
async function browserSession(profileKey='default'){
 // Ask the existing actor-bound native lifecycle service for a page in the user's
 // default AI Browser Profile. Shell itself is not a Firefox tabbrowser.
 // The unique requested URL identifies only our newly opened page; never bind by focus/order.
 const marker=location.origin+'/admin/static/favicon.svg#intelligence-'+crypto.randomUUID();
 const launched=await fetch('/v1/platform/client/browser-profiles/'+encodeURIComponent(profileKey)+'/launch',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({initial_url:marker})});
 if(!launched.ok)throw Error(lt('无法启动此信息源的 AI Browser Profile。请在 AI 浏览器 App 中检查该 Profile，或在信息源设置中重新选择。'));
 const launch=await launched.json();
 const connection=new window.AI2AppsBiDi.AI2AppsBiDiConnection();
 let createdContext=null;
 try{
  await connection.connect();let contexts=[];
  for(let attempt=0;attempt<12;attempt++){
   const tree=await connection.command('browsingContext.getTree',{maxDepth:0});
   contexts=(tree.contexts||[]).filter(context=>context.url===marker);
   if(contexts.length)break;
   // Profile launch binds a native container; it need not open initial_url.
   // Create our own explicit tab in that container, never adopt a focused tab.
   if(launch.user_context){
    const reference=(tree.contexts||[]).find(item=>item.userContext===launch.user_context);
    if(reference){
     const created=await connection.command('browsingContext.create',{type:'tab',userContext:launch.user_context,referenceContext:reference.context,background:true});
     createdContext=created.context;
     const verified=await connection.command('browsingContext.getTree',{root:createdContext,maxDepth:0});
     if(verified.contexts?.[0]?.userContext!==launch.user_context)throw Error(lt('采集页面的 Profile 不匹配。'));
     await connection.command('browsingContext.navigate',{context:createdContext,url:marker,wait:'interactive'});
     contexts=[{context:createdContext,url:marker,userContext:launch.user_context}];break;
    }
   }
   await new Promise(resolve=>setTimeout(resolve,250));
  }
  if(contexts.length!==1)throw Error(lt('未找到本次采集专用页面，请稍后重试。'));
  const context=contexts[0].context;
  const client=new window.AI2AppsBiDi.AI2AppsPageClient({bidi_context:context,url:marker});client.connection=connection;client.contextId=context;
  return {client,connection,context,retain:false};
 }catch(error){if(createdContext)await connection.command('browsingContext.close',{context:createdContext}).catch(()=>{});await connection.close();throw error;}
}
async function closeBrowser(session){if(!session)return;try{if(!session.retain)await session.connection.command('browsingContext.close',{context:session.context});}catch(_){}finally{await session.connection.close();}}
async function read(session,url,options={}){
 const result=await session.client.readPage({url,new_tab:false,close_tab:false,delay_ms:1200,max_chars:10000,include_cover:true,include_images:true,...options});
 if(result.outcome!=='success'){
  if(result.outcome==='needs_user'){session.retain=true;await session.connection.command('browsingContext.activate',{context:session.context});}
  const error=Error(result.outcome==='needs_user'?(result.reason==='cookie_consent'?lt('Cookie 对话框尚未关闭，请在保留的 Profile 页面选择 Cookie 偏好后重新更新。'):lt('请在保留的浏览器标签页完成登录或验证，然后重新更新。')):result.reason||lt('网页不可读取'));error.outcome=result.outcome;throw error;
 }
 return result;
}
async function candidatesFrom(session,limit=30){const list=await session.client.extractArticleList(limit);return (list.items||[]).map(item=>({url:item.url||item.href,title:String(item.title||'').slice(0,500),text:String(item.text||item.snippet||item.summary||'').slice(0,1500)})).filter(item=>{try{return ['https:','http:'].includes(new URL(item.url).protocol);}catch(_){return false;}});}
async function recommend(profileKey=null){
 if(busy||!channel())return;
 if(!profileKey){await loadProfiles();$('#recommendations').innerHTML=it`<label>搜索使用的 AI Browser Profile<select id="recommend-profile">${profileOptions()}</select></label><p class="intel-help">将在指定 Profile 中搜索；加入的信息源默认沿用此 Profile，可单独修改。</p><button id="start-recommend" class="intel-primary">开始搜索推荐</button>`;$('#recommend-dialog').showModal();$('#start-recommend').onclick=safe(()=>recommend($('#recommend-profile').value));return;}
busy=true;render();const target=channel();let session;
 $('#recommendations').innerHTML=lt('<p class="intel-help">正在搜索与你的兴趣相关的网站与社交话题…</p>');if(!$('#recommend-dialog').open)$('#recommend-dialog').showModal();
 try{
  session=await browserSession(profileKey);await read(session,'https://www.google.com/search?q='+encodeURIComponent(target.name+' '+target.interests.slice(0,150)+lt(' 新闻 官网 媒体 社交')));
  const searchResults=await candidatesFrom(session,30);if(!searchResults.length)throw Error(lt('未从搜索页读取到结果。可以手动添加信息源，或在 AceFox 中检查搜索页面。'));
  const candidates=[],seen=new Set();
  for(const [index,item] of searchResults.slice(0,6).entries()){
   $('#recommendations').innerHTML=it`<p class="intel-help">正在核对实际网站地址 ${index+1} / ${Math.min(searchResults.length,6)}…</p>`;
   try{
    const page=await read(session,item.url),final=new URL(page.url);
    if(/(^|\.)google\.[a-z.]+$/.test(final.hostname))continue;
    // General publications are monitored at their verified origin. Social pages
    // retain their exact topic/account path; never invent an account handle.
    const social=/(^|\.)(weibo\.com|x\.com|twitter\.com|facebook\.com|instagram\.com|xiaohongshu\.com|reddit\.com|youtube\.com|bilibili\.com)$/i.test(final.hostname);
    const url=social?page.url:final.origin+'/';if(seen.has(url))continue;seen.add(url);
    candidates.push({url,title:item.title,text:(item.text+lt(' 已访问：')+page.title+'；'+page.text.slice(0,800)).slice(0,1500)});
   }catch(error){if(error.outcome==='needs_user')throw error;}
  }
  if(!candidates.length)throw Error(lt('候选页面目前无法读取。请手动添加信息源，或在指定 Profile 中完成登录后重试。'));
  $('#recommendations').innerHTML=lt('<p class="intel-help">已核对实际网站地址，AI 正在筛选推荐…</p>');
  const result=await api('/channels/'+target.id+'/recommend','POST',{candidates});
  const root=$('#recommendations');root.innerHTML=result.sources.map((s,i)=>it`<section class="intel-recommendation"><h3>${esc(s.name)}</h3><p>${esc(s.reason)}</p><a href="${link(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.url)} ↗</a><button data-recommend-index="${i}">＋ 加入频道</button></section>`).join('')||lt('<p class="intel-help">没有找到合适的信息源，请细化频道兴趣或手动添加。</p>');
  root.querySelectorAll('[data-recommend-index]').forEach(button=>button.onclick=async()=>{button.disabled=true;try{const s=result.sources[Number(button.dataset.recommendIndex)];await api('/channels/'+target.id+'/sources','POST',{name:s.name,url:s.url,kind:s.kind,profile_key:profileKey,enabled:true});button.textContent=lt('已加入');await refresh();}catch(error){button.disabled=false;notice(error.message);}});
 }catch(error){$('#recommendations').innerHTML=it`<p class="intel-form-error">${esc(error.message)}</p><p class="intel-help">也可以在“信息源”页直接添加网站或社交话题链接。</p>`;}
 finally{await closeBrowser(session);busy=false;render();}
}
$('#recommend').onclick=safe(()=>recommend());
async function collect(id,scheduled=false,sourceId=null){
 if(busy)return;busy=true;render();
 try{await api('/channels/'+id+'/runs','POST',{scheduled,source_id:sourceId});if(!scheduled){tab='runs';if(!$('#mobile-category')?.querySelector('option[value="runs"]'))$('#mobile-category')?.insertAdjacentHTML('beforeend',`<option value="runs">${lt('更新记录')}</option>`);if(mobileQuery.matches)mobilePage='channel';}}
 finally{busy=false;await refresh();}
}
$('#collect').onclick=safe(()=>collect(channelId));
// One shared actor-scoped SSE connection observes Task and collection events.
let collectionStream=null,refreshQueued=false,refreshFailureNotified=false;
function queueCollectionRefresh(){
 if(refreshQueued)return;refreshQueued=true;
 setTimeout(()=>{refreshQueued=false;refresh().then(()=>{refreshFailureNotified=false;}).catch(error=>{if(!refreshFailureNotified){notice(error.message);refreshFailureNotified=true;}});},150);
}
function observeCollections(){
 // SSE is a prompt, not a durable completion receipt. Reconcile foreground
 // snapshots even when a terminal event is missed or a connection stalls.
 const timer=setInterval(()=>{if(!document.hidden)queueCollectionRefresh();},5000);
 if(window.AI2APPS_MOBILE_SURFACE){collectionStream={close:()=>clearInterval(timer)};return;}
 const stream=new EventSource('/v1/platform/browser-workspace/events',{withCredentials:true});
 collectionStream={close(){clearInterval(timer);stream.close();}};
 stream.addEventListener('intelligence.collection.changed',queueCollectionRefresh);
 stream.addEventListener('browser.workspace.snapshot',queueCollectionRefresh);
 stream.onopen=queueCollectionRefresh;
}
window.addEventListener('pagehide',()=>collectionStream?.close());
window.addEventListener('beforeunload',event=>{if(writingEditDirty()){event.preventDefault();event.returnValue='';}});
window.addEventListener('focus',queueCollectionRefresh);
const runClock=setInterval(updateRunElapsed,1000);
window.addEventListener('pagehide',()=>clearInterval(runClock));

window.IntelligenceArticleChat?.init({api,getArticle:ensureArticle,openArticle:readArticle,notice,panelRoot:$('#intel-reader'),showPanel:showArticleDiscussion,showArticle:showArticleDetails});
if($('#show-article-chat'))$('#show-article-chat').onclick=showArticleDiscussion;
initMobilePullRefresh($('.intel-main'));
initMobilePullRefresh($('.intel-sidebar'),true);
safe(async()=>{observeCollections();if(progressiveData())await refresh();else await Promise.all([refresh(),loadProfiles()]);})();
})();
