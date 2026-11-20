/* Bot-owned view over the durable App Chat contract. Display cursors do not change Agent context. */
(function(){
 'use strict';
 const caches=new WeakMap();
 function cacheFor(host){let cache=caches.get(host);if(!cache){cache=new Map();caches.set(host,cache);}return cache;}
 function invalidate(host,id){const cache=caches.get(host);if(id)cache?.delete(id);else cache?.clear();}
 function messageTime(value, now=new Date()){
  if(!value)return null;
  const date=new Date(value);
  if(!Number.isFinite(date.getTime()))return null;
  const zh=(document.documentElement.lang||'').startsWith('zh'),locale=zh?'zh-CN':'en';
  const yesterday=new Date(now);yesterday.setDate(now.getDate()-1);
  const day=date.toDateString();
  const clock=date.toLocaleTimeString(locale,{hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
  const calendar=day===now.toDateString()?'':day===yesterday.toDateString()?(zh?'昨天':'Yesterday'):
   date.toLocaleDateString(locale,{year:'numeric',month:'short',day:'numeric'});
  return {text:calendar?calendar+' '+clock:clock,dateTime:date.toISOString(),title:date.toLocaleString(locale)};
 }
 const terminal=new Set(['completed','failed','cancelled','timed_out','interrupted']);
 function composerReferences({input,form,label,searchTasks,sessions,bots,onError}){
  const hint=document.createElement('div');
  hint.className='bot-task-reference-hint';hint.hidden=true;
  const hintText=document.createElement('span');
  const remove=document.createElement('button');
  remove.type='button';remove.textContent='×';
  remove.setAttribute('aria-label',label('移除续接引用','Remove continuation reference'));
  hint.append(hintText,remove);
  const choices=document.createElement('div');
  choices.className='bot-reference-choices';choices.hidden=true;
  choices.setAttribute('role','group');
  form.insertBefore(hint,input);
  form.insertBefore(choices,input);
  const leading=/^\s*(?:继续|续接|continue)\s+\/#("[^"\n]+"|[^\s"<>，。！？：；、（）【】,.!?:;()\[\]]+)\s*/i;
  const atCursor=/(?:^|[^A-Za-z0-9_/\\])\/([#@])("(?:[^"\\\n]|\\["\\])*"?|[^\s"<>/`，。！？：；、（）【】,.!?:;()\[\]]*)$/;
  let timer=null, revision=0, buttons=[], active=-1;
  const known=new Map();
  function close(){
   clearTimeout(timer);revision++;buttons=[];active=-1;choices.replaceChildren();choices.hidden=true;
  }
  function updateHint(){
   const prefix=leading.exec(input.value);
   hint.hidden=!prefix;
   if(!prefix)return;
   const token=prefix[1].replace(/^"|"$/g,'');
   const task=known.get(token)||sessions().find(entry=>entry.id===token);
   hintText.textContent=label('继续任务 · ','Continue task · ')+(task?.title||token);
  }
  function edit(value,start,end){
   if(input.readOnly||input.disabled)return;
   if(input.value.length-end+start+value.length>input.maxLength){
    onError(Error(label('草稿太长，无法插入引用。','The draft is too long to insert a reference.')));return;
   }
   input.setRangeText(value,start,end,'end');
   input.focus({preventScroll:true});
   input.dispatchEvent(new Event('input',{bubbles:true}));
   close();
  }
  remove.onclick=()=>{
   const prefix=leading.exec(input.value);
   if(prefix)edit('',0,prefix[0].length);
  };
  function showChoices(items,{symbol,start,end,draft}){
   const botReference=symbol==='@';
   choices.setAttribute('aria-label',botReference?label('可引用的 Bot','Bots to reference'):label('可引用的任务','Tasks to reference'));
   for(const entry of items){
    const button=document.createElement('button');
    button.type='button';
    button.textContent=entry.title;
    button.title=entry.id;
    button.onmousedown=event=>event.preventDefault();
    button.onclick=()=>{
     if(input.value!==draft||input.selectionStart!==end||input.selectionEnd!==end){close();return;}
     const name=entry.name;
     const displayName=name&&(/[/@`"()（）\r\n]/.test(name)?JSON.stringify(name):name);
     const reference=botReference?'/@'+displayName+'(`'+entry.id+'`)':'/#'+entry.id;
     edit(reference+' ',start,end);
    };
    choices.append(button);buttons.push(button);
   }
   if(!buttons.length)choices.textContent=botReference?label('没有匹配的 Bot','No matching Bots'):label('没有匹配的任务','No matching tasks');
   choices.hidden=false;
  }
  function update(){
   close();updateHint();
   if(input.selectionStart!==input.selectionEnd||input.readOnly||input.disabled)return;
   const draft=input.value,end=input.selectionStart,match=atCursor.exec(draft.slice(0,end));
   if(!match)return;
   const [,symbol,raw]=match;
   const query=raw.replace(/^"|"$/g,'').replace(/\\(["\\])/g,'$1');
   const range={symbol,start:end-raw.length-2,end,draft};
   if(symbol==='@'){
    const entries=bots().filter(entry=>!entry.definition?.execution_mode||entry.definition.execution_mode==='agent');
    if(entries.some(entry=>entry.id===query))return;
    const needle=query.toLowerCase();
    const matches=entries.filter(entry=>entry.name.toLowerCase().includes(needle)||entry.id.toLowerCase().includes(needle));
    showChoices(matches.map(entry=>({
     id:entry.id,
     name:entry.name,
     title:entries.some(other=>other.id!==entry.id&&other.name===entry.name)?entry.name+' · '+entry.id.slice(0,8):entry.name,
    })),range);
    return;
   }
   if(known.has(query)||sessions().some(entry=>entry.id===query))return;
   const request=revision;
   timer=setTimeout(async()=>{
    try{
     const {items}=await searchTasks(query);
     if(request!==revision||input.value!==draft||input.selectionStart!==end||input.selectionEnd!==end)return;
     for(const entry of items)known.set(entry.id,entry);
     showChoices(items.map(entry=>({...entry,title:entry.title+(entry.archived?label(' · 已归档',' · Archived'):'')})),range);
    }catch(error){if(request===revision)onError(error);}
   },150);
  }
  input.addEventListener('input',event=>{if(!event.isComposing)update();});
  input.addEventListener('compositionstart',close);
  input.addEventListener('compositionend',update);
  input.addEventListener('click',update);
  input.addEventListener('keyup',event=>{
   if(!event.isComposing&&['ArrowLeft','ArrowRight','Home','End'].includes(event.key))update();
  });
  input.addEventListener('blur',()=>{close();});
  input.addEventListener('keydown',event=>{
   if(event.isComposing||event.keyCode===229||choices.hidden)return;
   if(event.key==='Escape'){event.preventDefault();close();return;}
   if(!buttons.length)return;
   if(event.key==='ArrowDown'||event.key==='ArrowUp'){
    event.preventDefault();
    active=(active<0?(event.key==='ArrowDown'?0:buttons.length-1):active+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length;
    buttons.forEach((button,index)=>button.classList.toggle('active',index===active));
    buttons[active].scrollIntoView({block:'nearest'});
   }else if(event.key==='Enter'&&!event.shiftKey){
    event.preventDefault();event.stopImmediatePropagation();buttons[Math.max(0,active)].click();
   }
  },true);
  return {
   continue(entry){
    known.set(entry.id,entry);
    edit(label('继续 ','Continue ')+'/#'+entry.id+' ',0,leading.exec(input.value)?.[0].length||0);
   },
   updateHint,close,
  };
 }
 async function create({bot,root:host,onState,onError,onPendingMemories,bots=()=>[],focusFrom,isActive=()=>true}){
  const cache=cacheFor(host),cached=cache.get(bot.id);if(cached){cache.delete(bot.id);cache.set(bot.id,cached);}else while(cache.size>=5)cache.delete(cache.keys().next().value);
  const flash=bot.definition?.execution_mode==='flash';
  const root=document.createElement('div');root.classList.add('bot-conversation');
  let preview=null;
  if(cached){
   preview=cached.view.cloneNode(true);preview.setAttribute('aria-busy','true');
   preview.querySelectorAll('button,input,select').forEach(e=>e.disabled=true);
   preview.querySelectorAll('textarea').forEach(e=>{e.readOnly=true;e.value=cached.draft||'';});
   preview.querySelectorAll('.bot-interactions,.bot-task-feed,.bot-conversation-status').forEach(e=>e.remove());
   host.replaceChildren(preview);preview.querySelector('.bot-message-stream').scrollTop=cached.scrollTop;
  }else host.replaceChildren(root);

  const abort=new AbortController();let disposed=false,polling=false,olderBusy=false,hasOlder=false,oldest=null,newest=0,model='',models=[],snapshot={runs:[]},sending=false,pendingSend=null,pendingPoke=null,pokeAwaitingReceipt=null,composer=null,references=null,allModels=[],modelNotice='',profileRevision=0,reasoningEffort=null,supportedReasoningEfforts=[],profileSaving=false, reconnecting=false,realtime=null;
  const zh=(document.documentElement.lang||'').startsWith('zh'),label=(a,b)=>zh?a:b;
  function clockHeaders(){return {'X-AI2Apps-Timezone':Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC'};}
  async function api(path,method='GET',body,headers={}){
   let response;
   try{
    response=await fetch(path.startsWith('/v1/')?path:'/v1/platform'+path,{method,credentials:'same-origin',signal:abort.signal,headers:{'Content-Type':'application/json',...headers},...(body?{body:JSON.stringify(body)}:{})});
   }catch(error){
    if(error?.name==='TypeError')error.connectionInterrupted=true;
    throw error;
   }
   if(method==='GET'&&[502,503,504].includes(response.status)){
    const error=new Error('Connection interrupted');error.connectionInterrupted=true;throw error;
   }
   const value=await response.json();
   if(!response.ok){const error=Error(value.detail?.message||value.error?.message||value.message||(typeof value.detail==='string'?value.detail:null)||'Request failed');error.status=response.status;throw error;}
   return value;
  }
  // Present a stable loading surface before any session/catalog round trip.
  root.replaceChildren();root.classList.add('chat-shell','bot-conversation');
  const loading=document.createElement('div');loading.className='bot-conversation-loading';loading.setAttribute('role','status');loading.textContent=label('正在读取对话…','Loading conversation…');root.append(loading);
  // Speech discovery must never gate fixed workflow execution or owner dialogue.
  const speechCatalog=flash?fetch('/admin/api/models',{credentials:'same-origin',signal:abort.signal}).then(response=>{if(!response.ok)throw Error('Speech model catalog unavailable');return response.json();}).catch(()=>({models:[]})):null;
  const modelReady=flash?Promise.resolve({selected:'fixed-workflow-no-model',models:[],allModels:[],notice:''}):(window.AI2AppsBotModelSelection.forBot?window.AI2AppsBotModelSelection.forBot(bot.id,localStorage.getItem('ai2apps.bot.model.'+bot.id),{signal:abort.signal}):window.AI2AppsBotModelSelection.resolve(localStorage.getItem('ai2apps.bot.model.'+bot.id),{signal:abort.signal})).catch(error=>{if(isActive())onError(error);return null;});
  let opened;
  try{opened=await api('/app-chat/sessions','POST',{registration:'ai2apps.messager.bots',scope:{bot_id:bot.id},ui:{},include_messages:false});}
  catch(error){cache.delete(bot.id);if(isActive())host.replaceChildren();throw error;}
  if(disposed||!isActive())return {dispose(){}};const base='/app-chat/sessions/'+encodeURIComponent(opened.session_id);
  root.replaceChildren();root.classList.add('chat-shell','bot-conversation');
  const stream=document.createElement('div');stream.className='bot-message-stream';stream.setAttribute('role','log');stream.setAttribute('aria-label',label('Bot 对话','Bot conversation'));
  const older=document.createElement('button');older.className='bot-load-older';older.textContent=label('加载更早消息','Load older messages');older.hidden=true;
  const messages=document.createElement('div');messages.className='bot-message-list';const taskFeed=document.createElement('div');taskFeed.className='bot-task-feed';stream.append(older,messages,taskFeed);
  const streamShell=document.createElement('div');streamShell.className='bot-stream-shell';
  const jumpBottom=document.createElement('button');jumpBottom.type='button';jumpBottom.className='bot-jump-bottom';jumpBottom.hidden=true;jumpBottom.title=label('滚动到消息末尾','Scroll to latest message');jumpBottom.setAttribute('aria-label',jumpBottom.title);
  jumpBottom.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14m-6-6 6 6 6-6"/></svg>';
  streamShell.append(stream,jumpBottom);
  const status=document.createElement('div');status.className='bot-conversation-status';status.setAttribute('role','status');
  const sendStatus=document.createElement('div');sendStatus.className='bot-conversation-status';sendStatus.setAttribute('role','status');sendStatus.hidden=true;
  const interactions=document.createElement('article');interactions.className='bot-interactions bot-interaction-card';interactions.setAttribute('aria-live','polite');
  const form=document.createElement('form');form.className='bot-composer';const input=document.createElement('textarea');input.rows=2;input.maxLength=flash&&!bot.definition?.config?.plan?512:16000;input.placeholder=flash?bot.definition?.config?.plan?.usage||label('数学表达式，例如 (2 + 3) * 4','Expression, e.g. (2 + 3) * 4'):label('发消息…','Message…');input.setAttribute('aria-label',input.placeholder);
  const send=document.createElement('button');send.type='submit';send.disabled=true;send.textContent=label('发送','Send');const cancel=document.createElement('button');cancel.type='button';cancel.textContent=label('停止','Stop');cancel.hidden=true;form.append(input,cancel,send);root.append(streamShell,status,sendStatus,form);interactions.hidden=true;messages.append(interactions);
  const memoryFeed=window.AI2AppsBotKnowledge?.createFeed({botId:bot.id,sessionId:opened.session_id,root:messages,onError,onPending:onPendingMemories});
  const tasks=window.AI2AppsBotTaskFeed.create({bot,root:taskFeed,api,refresh:poll,onError,label});
  const messageActions=window.AI2AppsMiniAppChat.bindMessageActions({icons:true,compactSpeech:true,onSpeechError:options=>window.AI2AppsBotVoice.offerSetup({...options,operation:'speech_generation'}),resolveSpeech:(signal,options)=>window.AI2AppsBotVoice.resolve(bot.id,signal,options)});
  let taskAccessPolicies=[];const seen=new Set(),loadedItems=[];let interactionKey='',interactionRunId=null,readState={unread_count:0},initialReady=false,reading=false,readTimer=null,scrollResize=null;
  const unreadBase='/messager/bots/'+encodeURIComponent(bot.id);
  const unreadReady=api(unreadBase+'/unread?session_id='+encodeURIComponent(opened.session_id)).then(v=>{readState=v;return v;});
  function bottom(){return stream.scrollHeight-stream.scrollTop-stream.clientHeight<32;}
  function publishRead(){onState({models,model,modelNotice,reasoningEffort,supportedReasoningEfforts,profileSaving,accessPolicies:taskAccessPolicies,runs:snapshot.runs,taskSessions:snapshot.task_sessions||[],sessionId:opened.session_id,unreadCount:readState.unread_count||0});}
  function updateJump(){jumpBottom.hidden=stream.scrollHeight-stream.scrollTop-stream.clientHeight<=32;}
  jumpBottom.onclick=()=>{stream.scrollTop=stream.scrollHeight;updateJump();scheduleRead();};
  stream.addEventListener('load',updateJump,true);
  function scheduleRead(){updateJump();clearTimeout(readTimer);readTimer=setTimeout(async()=>{
   if(!initialReady||disposed||!isActive()||document.hidden||!root.isConnected||!bottom()||reading||newest<=(readState.read_sequence||0))return;
   reading=true;try{const value=await api(unreadBase+'/read','POST',{session_id:opened.session_id,through_sequence:newest});if(disposed||!isActive())return;readState=value;publishRead();if(!value.unread_count)messages.querySelector('.bot-unread-divider')?.remove();}catch(e){if(!disposed)onError(e);}finally{reading=false;}
  },250);}
  function unreadDivider(){if(!readState.first_unread_sequence)return null;const target=messages.querySelector('[data-message-sequence="'+readState.first_unread_sequence+'"]');if(!target)return null;let divider=messages.querySelector('.bot-unread-divider');if(!divider){divider=document.createElement('div');divider.className='bot-unread-divider';divider.textContent=label('以下是未读消息','Unread messages');target.before(divider);}return divider;}
  document.addEventListener('visibilitychange',scheduleRead);

  let timestampDay=new Date().toDateString();
  function updateTimestamp(element,value,now){
   const time=messageTime(value,now);
   if(!time)return false;
   element.dateTime=time.dateTime;element.title=time.title;element.textContent=time.text;
   return true;
  }
  function refreshTimestamps(){
   const now=new Date(),day=now.toDateString();
   if(day===timestampDay)return;
   timestampDay=day;
   for(const element of messages.querySelectorAll('.bot-message-time'))updateTimestamp(element,element.dateTime,now);
  }
  let conversationRevision=cached?.conversationRevision;
  const outgoing = new Map();
  function removeOutgoing(requestId,acknowledged=false) {
   outgoing.get(requestId)?.remove();
   outgoing.delete(requestId);
   if(pokeAwaitingReceipt===requestId){pokeAwaitingReceipt=null;if(acknowledged)pendingPoke=null;composer?.setPokeBusy?.(false);sendStatus.hidden=true;}
  }
  function showOutgoing({request_id, text}) {
   if (loadedItems.some(item => item.client_request_id === request_id)) return;
   const article = document.createElement('article');
   article.className = 'user-message';
   article.dataset.pendingRequestId = request_id;
   const bubble = document.createElement('div');
   bubble.className = 'user-message-bubble';
   bubble.textContent = text;
   article.append(bubble);
   outgoing.set(request_id, article);
   messages.insertBefore(article, interactions);
   stream.scrollTop = stream.scrollHeight;
   updateJump();
  }
  function append(items,prepend=false){const fragment=document.createDocumentFragment();for(let item of items){if(item.role==='user'&&item.client_request_id)removeOutgoing(item.client_request_id,true);if(seen.has(item.id))continue;seen.add(item.id);if(!['user','assistant'].includes(item.role))continue;loadedItems.push(item);if(!prepend)realtime?.messages([item]);
   const article=document.createElement('article');article.dataset.messageId=item.id;article.dataset.messageSequence=item.sequence;article.className=item.role==='user'?'user-message':'assistant-message';const body=document.createElement('div');if(flash&&item.content?.startsWith('执行未完成 / Execution did not complete:'))item={...item,content:label('工作流未能完成。请查看下方错误详情；预设参数不匹配时需重新生成并审阅工作流。','The workflow did not finish. See error details below; invalid settings need regeneration and review.')};body.className=item.role==='user'?'user-message-bubble':'message-body';
   if(item.format==='markdown'&&window.DOMPurify&&window.marked)body.innerHTML=window.DOMPurify.sanitize(window.marked.parse(item.content||''));else body.textContent=item.content||'';
   article.append(body);window.AI2AppsBotMaterials.attachments(article,item.attachments,opened.session_id);window.AI2AppsBotMaterials.outputs?.(article,item.artifacts);window.AI2AppsBotMaterials.enhance(body);const actions=messageActions.attach(article,body,item.content);
   if(item.role==='assistant'&&actions?.toolbar)window.AI2AppsConversationTrim?.attach({toolbar:actions.toolbar,botId:bot.id,sessionId:opened.session_id,item,previewText:body.textContent,
    request:(path,method,body)=>api('/messager'+path,method,body),label,refresh:reloadHistory,onError});
   if(item.role==='assistant'&&item.created_at&&actions?.toolbar){
    const stamp=document.createElement('time');stamp.className='bot-message-time';
    if(updateTimestamp(stamp,item.created_at)){
     actions.toolbar.append(stamp);
     // A result can have media without any copyable or speakable text.
     if(actions.toolbar.hidden)article.append(stamp);
    }
   }
   fragment.append(article);}
   if(prepend)messages.prepend(fragment);else messages.insertBefore(fragment,outgoing.values().next().value||interactions);
  }
  function resetHistory(){
   window.AI2AppsBotMaterials.dispose?.(messages);
   messages.querySelectorAll('[data-message-id],.bot-unread-divider').forEach(node=>node.remove());
   seen.clear();loadedItems.length=0;newest=0;oldest=null;hasOlder=false;cache.delete(bot.id);
  }
  function historyChanged(page){
   const revision=page.conversation_revision??0;
   if(conversationRevision!==undefined&&conversationRevision!==revision){conversationRevision=revision;resetHistory();return true;}
   conversationRevision=revision;return false;
  }
  async function reloadHistory(result){conversationRevision=result?.conversation_revision??conversationRevision;for(const id of result?.retired_request_ids||[])removeOutgoing(id,true);resetHistory();await poll(true);}
  function cursors(page){for(const i of page.items){oldest=oldest===null?i.sequence:Math.min(oldest,i.sequence);newest=Math.max(newest,i.sequence);}}
  async function loadOlder(){if(olderBusy||!hasOlder||oldest===null||disposed)return;olderBusy=true;older.disabled=true;const height=stream.scrollHeight,top=stream.scrollTop;
   try{const page=await api(base+'/messages?before='+oldest);if(disposed||!isActive())return;if(historyChanged(page)){void poll(true);return;}append(page.items,true);cursors(page);hasOlder=page.has_more;older.hidden=!hasOlder;stream.scrollTop=top+stream.scrollHeight-height;}catch(e){if(!disposed)onError(e);}finally{olderBusy=false;older.disabled=false;}}
  older.onclick=loadOlder;stream.addEventListener('scroll',()=>{if(stream.scrollTop<80)loadOlder();scheduleRead();});
  function updateFlashError(run){
   if(!flash)return;
   let details=root.querySelector('.flash-error-details');
   if(!run?.error_details){details?.remove();return;}
   if(!details){
    details=document.createElement('details');
    details.className='flash-error-details';
    const summary=document.createElement('summary');
    summary.textContent=label('错误详情','Error details');
    details.append(summary,document.createElement('pre'));
    status.after(details);
   }
   if(details.dataset.runId!==run.id){
    details.open=false;
    details.dataset.runId=run.id;
   }
   details.querySelector('pre').textContent=JSON.stringify(run.error_details,null,2);
  }
  function recoveryText(run){
   const retry=run?.progress?.model_recovery;
   if(retry?.state==='waiting'){
    const seconds=Math.max(0,Math.ceil((Date.parse(retry.retry_at)-Date.now())/1000));
    if(Number.isFinite(seconds))return label(
     `模型服务限流，约 ${seconds} 秒后重试（第 ${retry.attempt+1}/${retry.max_attempts} 次尝试）`,
     `Model rate limit. Retrying in about ${seconds}s (attempt ${retry.attempt+1}/${retry.max_attempts}).`);
   }
   if(run?.progress?.task_progress?.stage==='model_rate_limit'){
    return label('模型服务限流，正在等待重试','Waiting to retry after a model rate limit');
   }
   return run?.text;
  }
  const submittedInteractions=new Set();
  function state(value){value={...value,runs:value.runs.map(run=>({...run,interactions:(run.interactions||[]).filter(item=>!submittedInteractions.has(item.id))}))};snapshot=value;const active=value.runs.find(r=>!terminal.has(r.status)&&r.interactions?.length)||value.runs.find(r=>!terminal.has(r.status)&&!r.dialogue)||value.runs.find(r=>!terminal.has(r.status));const latest=value.runs.at(-1);const activeTitle=active?.task_context?.step||active?.title;const activeText=recoveryText(active);
   status.textContent=reconnecting?label('正在恢复连接…','Reconnecting…'):
    active?.interactions?.length?'':(activeText&&activeTitle?activeTitle+' · '+activeText:activeText)||(!flash?(latest?.error?.message||(typeof latest?.error==='string'?latest.error:'')):'');
   updateFlashError(active ? null : latest);
   realtime?.sync();realtime?.observe(value.runs);references?.updateHint();cancel.hidden=!active;send.disabled=sending||profileSaving||!model||!!composer?.blocked()||(!input.value.trim()&&!composer?.hasFiles());
   const pending=active?.interactions?.[0];const key=pending?.id||'';
   // Keep a submitted answer visible while its own run continues. An access
   // card can close as soon as the server stops listing its approval.
   const keepAnswerReceipt=!pending&&interactions.dataset.interactionState==='submitted'
    &&value.runs.some(run=>run.id===interactionRunId&&!terminal.has(run.status));
   if(key!==interactionKey&&!keepAnswerReceipt){window.AI2AppsBotInteractions.release(interactions,interactionKey);interactionKey=key;interactionRunId=pending?active.id:null;if(pending){const handled=window.AI2AppsBotInteractions.render({root:interactions,run:active,item:pending,botId:active.delegation_id&&!active.task_tree_review_here?null:bot.id,api,label,onError,refresh:poll,respond:async response=>{await api('/agent-runs/'+active.id+'/interactions/'+pending.id+'/respond','POST',{response_id:crypto.randomUUID(),response});await poll();}});if(!handled)window.AI2AppsBotInteractions.answerForm({root:interactions,item:pending,label,onError,
     submit:(response,responseId)=>api('/agent-runs/'+active.id+'/interactions/'+pending.id+'/respond','POST',{response_id:responseId,response}),
     onSubmitted:id=>{submittedInteractions.add(id);void poll(true);}});}}

   onState({models,model,modelNotice,reasoningEffort,supportedReasoningEfforts,profileSaving,accessPolicies:taskAccessPolicies,runs:value.runs,taskSessions:value.task_sessions||[],sessionId:opened.session_id,unreadCount:readState.unread_count||0});
  }
  async function poll(force=false){if(disposed||!isActive()||polling||(!force&&document.hidden))return;polling=true;try{refreshTimestamps();const nearBottom=bottom();let more=true,passes=0;
    while(more&&passes++<4){const page=await api(base+'/messages?after='+newest);if(disposed||!isActive())return;if(historyChanged(page)){more=true;continue;}append(page.items);cursors(page);more=page.has_more;}
    const value=await api('/messager/bots/'+encodeURIComponent(bot.id)+'/dialogue/state?session_id='+encodeURIComponent(opened.session_id));if(disposed||!isActive())return;reconnecting=false;state(value);const work=await api('/messager/bots/'+encodeURIComponent(bot.id)+'/work');if(disposed||!isActive())return;taskAccessPolicies=(work.access_policies||[]).filter(p=>p.status==='approved');tasks.update(work);void memoryFeed?.refresh();readState=await api(unreadBase+'/unread?session_id='+encodeURIComponent(opened.session_id));if(disposed||!isActive())return;publishRead();if(nearBottom)stream.scrollTop=stream.scrollHeight;else unreadDivider();scheduleRead();
   }catch(error){
    if(disposed||!isActive())return;
    if(error.connectionInterrupted){
     reconnecting=true;
     status.textContent=label('正在恢复连接…','Reconnecting…');
    }else onError(error);
   }finally{polling=false;}}
  const refreshConnected=()=>void poll(true);
  form.onsubmit=async e=>{
   e.preventDefault();
   if(sending||profileSaving||(!input.value.trim()&&!composer?.hasFiles())||composer?.blocked()||!model)return;
   const submittedDraft=input.value;
   const text=submittedDraft.trim()||label('请查看附件','Please review the attachments'),attachments=composer?.ids()||[];
   if(!pendingSend||pendingSend.text!==text||JSON.stringify(pendingSend.attachments)!==JSON.stringify(attachments)||pendingSend.model!==model)pendingSend={request_id:crypto.randomUUID(),text,model,attachments,language:document.documentElement.lang||'en'};
   const submission = pendingSend;
   sending=true;send.disabled=true;
   showOutgoing(submission);
   sendStatus.textContent=flash
    ?label('正在提交给 Flash-Bot…','Sending to Flash-Bot…')
    :label('正在发送…','Sending…');
   sendStatus.hidden=false;
   try{
    composer?.setBusy(true);
    const response=await api('/messager/bots/'+encodeURIComponent(bot.id)+'/dialogue/turns','POST',{...submission,session_id:opened.session_id},clockHeaders());
    if(disposed||!isActive())return;
    pendingSend=null;
    if(input.value===submittedDraft)input.value='';
    references?.close();composer?.clear();
    // Draft review is ready as soon as the submission returns; history refresh
    // can run independently of the review and of subsequent sends.
    void poll(true);
    if(response.kind==='workflow_review'){
     sendStatus.hidden=true;
     const updated=await window.AI2AppsBotCreation.reviewConversation({response,botId:bot.id,sessionId:opened.session_id,request:(path,method,body)=>api('/messager'+path,method,body)});
     if(updated&&!disposed&&isActive()){Object.assign(bot,updated);input.placeholder=bot.definition?.config?.plan?.usage||label('发消息…','Message…');}
     void poll(true);
    }
   }catch(error){if(!disposed&&isActive()){if(pendingSend===submission)removeOutgoing(submission.request_id);onError(error);}}
   finally{
    sending=false;sendStatus.hidden=true;
    if(!disposed&&isActive()){composer?.setBusy(false);state(snapshot);}
   }
  };
  async function pokeBot(){if(flash||sending||pokeAwaitingReceipt||profileSaving||!model||composer?.blocked())return;pendingPoke=pendingPoke||{request_id:crypto.randomUUID(),model,language:document.documentElement.lang||'en'};
   const submission=pendingPoke;pokeAwaitingReceipt=submission.request_id;composer?.setPokeBusy?.(true);
   showOutgoing({...submission,text:'👋 Poke'});
   sendStatus.textContent=label('正在发送…','Sending…');sendStatus.hidden=false;
   try{await api('/messager/bots/'+encodeURIComponent(bot.id)+'/poke','POST',{...submission,session_id:opened.session_id},clockHeaders());void poll(true);}catch(e){if(!disposed){removeOutgoing(submission.request_id);onError(e);}}finally{sendStatus.hidden=!pokeAwaitingReceipt;if(!disposed)state(snapshot);}}
  cancel.onclick=async()=>{const active=snapshot.runs.find(r=>!r.dialogue&&!terminal.has(r.status))||snapshot.runs.find(r=>!terminal.has(r.status));if(active)try{await api(active.delegation_id?'/messager/bots/'+encodeURIComponent(bot.id)+'/delegations/'+active.delegation_id+'/cancel':active.job_id?'/messager/bots/'+encodeURIComponent(bot.id)+'/dialogue/jobs/'+active.job_id+'/cancel':'/agent-runs/'+active.id+'/cancel','POST',{});await poll();}catch(e){onError(e);}};
  // Mount the complete composer immediately; catalog loading must not show a raw form.
  composer=window.AI2AppsBotComposer.create({form,input,send,cancel,inputPolicy:{},sessionId:opened.session_id,dropTarget:root,models:[],label,onError,onPoke:flash?null:pokeBot,onChange:()=>state(snapshot)});
  references=flash?null:composerReferences({
   input,form,label,onError,bots,sessions:()=>snapshot.task_sessions||[],
   searchTasks:query=>api('/messager/bots/'+encodeURIComponent(bot.id)+'/task-sessions?session_id='+encodeURIComponent(opened.session_id)+'&query='+encodeURIComponent(query))
  });
  if(!flash&&window.AI2AppsBotRealtime)realtime=window.AI2AppsBotRealtime.create({botId:bot.id,sessionId:opened.session_id,composer,form,getModel:()=>model,request:api,onAccepted:()=>void poll(true),label,onError});
  if(speechCatalog)void speechCatalog.then(catalog=>{if(!disposed&&isActive()){allModels=catalog.models||[];composer.setModels?.(allModels);}});
  composer.setBusy(true);input.addEventListener('input',()=>state(snapshot));
  loading.className='bot-conversation-loading';stream.prepend(loading);
  const reusable=cached&&cached.sessionId===opened.session_id;
  if(reusable){append(cached.items);cursors({items:cached.items});hasOlder=cached.hasOlder;input.value=cached.draft||'';}
  const pageReady=unreadReady.then(v=>api(base+'/messages'+(v.unread_count?'?after='+Math.max(0,v.first_unread_sequence-1):'')));
  function applyProfile(selected){
   profileRevision=selected.profileRevision??profileRevision;
   reasoningEffort=selected.reasoningEffort??null;
   supportedReasoningEfforts=selected.supportedReasoningEfforts||[];
  }
  async function saveProfile(value, effort){
   if(profileSaving||disposed||!models.some(m=>m.id===value))return;
   if(realtime?.active())await realtime.stop();
   profileSaving=true;state(snapshot);
   try{
    const saved=await window.AI2AppsBotModelSelection.save(bot.id,value,profileRevision,{signal:abort.signal,reasoningEffort:effort});
    if(disposed||!isActive())return;
    applyProfile({profileRevision:saved.revision,reasoningEffort:saved.reasoning_effort,supportedReasoningEfforts:saved.supported_reasoning_efforts});
    model=value;
    modelNotice=window.AI2AppsConversationModelPolicy.agentNotice(models.find(m=>m.id===value),{explicit:true,language:document.documentElement.lang});
    localStorage.setItem('ai2apps.bot.model.'+bot.id,model);
   }catch(e){if(!disposed&&isActive())onError(e);}
   finally{profileSaving=false;if(!disposed&&isActive())state(snapshot);}
  }
  const setupModels=async()=>{const selected=await modelReady;if(!isActive())return;if(selected){applyProfile(selected);allModels=selected.allModels;models=selected.models;model=selected.selected;modelNotice=selected.notice;composer.setModels?.(allModels);}composer.setBusy(false);state(snapshot);};
  const setupHistory=async()=>{try{const page=await pageReady;if(!isActive())return;const position=stream.scrollTop;if(reusable&&(!page.items.length||Math.max(...page.items.map(i=>i.sequence))<newest)){messages.replaceChildren(...outgoing.values(),interactions);seen.clear();loadedItems.length=0;oldest=null;newest=0;hasOlder=false;cache.delete(bot.id);}const changed=historyChanged(page);append(page.items);cursors(page);if(changed)hasOlder=page.has_more;else if(readState.unread_count)hasOlder=(page.items[0]?.sequence||1)>1;else if(!reusable)hasOlder=page.has_more;older.hidden=!hasOlder;stream.scrollTop=reusable?position:stream.scrollHeight;}catch(error){if(isActive())onError(error);}finally{loading.remove();}};
  // Only the session identity gates editing. Slow catalogs/history must never
  // strand the user on the read-only cache preview or overwrite a new draft.
  if(preview){const position=preview.querySelector('.bot-message-stream').scrollTop;host.replaceChildren(root);stream.scrollTop=reusable?position:stream.scrollHeight;preview=null;}
  if(focusFrom&&(document.activeElement===focusFrom||document.activeElement===document.body)){
   input.setSelectionRange(input.value.length,input.value.length);
   input.focus({preventScroll:true});
  }
  await Promise.all([setupModels(),setupHistory()]);
  if(!isActive()){window.AI2AppsBotMaterials.dispose?.(root);composer.dispose();abort.abort();return {dispose(){}};}
  if(readState.unread_count){const divider=unreadDivider();if(divider)stream.scrollTop=divider.offsetTop-stream.offsetTop;}else if(!reusable)stream.scrollTop=stream.scrollHeight;
  initialReady=true;publishRead();scheduleRead();
  if(typeof ResizeObserver!=='undefined'){scrollResize=new ResizeObserver(updateJump);scrollResize.observe(stream);scrollResize.observe(messages);scrollResize.observe(taskFeed);}
  void poll(true);
  const timer=setInterval(poll,1500);
  window.addEventListener?.('online',refreshConnected);
  return {async refreshModels(){const selected=await (window.AI2AppsBotModelSelection.forBot?window.AI2AppsBotModelSelection.forBot(bot.id,model,{signal:abort.signal}):window.AI2AppsBotModelSelection.resolve(model,{signal:abort.signal}));if(disposed||!isActive())return;applyProfile(selected);allModels=selected.allModels;models=selected.models;model=selected.selected;modelNotice=selected.notice;composer.setModels?.(allModels);state(snapshot);},continueTask(entry){if(!sending)references?.continue(entry);},focusTaskInteraction(entry){
   const waiting=new Set((entry.runs||[]).map(run=>run.worker_run));
   const run=snapshot.runs.find(run=>waiting.has(run.id)&&run.interactions?.some(item=>item.id===interactionKey));
   if(!run||interactions.hidden||!interactions.childNodes.length)return false;
   interactions.tabIndex=-1;interactions.scrollIntoView({block:'center'});interactions.focus({preventScroll:true});return true;
  },refresh:poll,focusTaskRun(id){if(!id)return;const card=Array.from(taskFeed.querySelectorAll('[data-todo-run-id]')).find(e=>e.dataset.todoRunId===id);if(card){card.scrollIntoView({block:'center'});card.focus();}},dispose({discard=false,skipCache=false}={}){
   references?.close();
   window.AI2AppsBotMaterials.dispose?.(root);
   if(!disposed&&root.cloneNode&&!discard&&!skipCache){
    const view=root.cloneNode(true);
    view.querySelectorAll('[data-pending-request-id]').forEach(node=>node.remove());
    cache.delete(bot.id);cache.set(bot.id,{view,scrollTop:stream.scrollTop,items:loadedItems.slice().sort((a,b)=>a.sequence-b.sequence),hasOlder,draft:input.value,sessionId:opened.session_id,conversationRevision});
    while(cache.size>5)cache.delete(cache.keys().next().value);
   }else if(discard)cache.delete(bot.id);
   disposed=true;scrollResize?.disconnect();clearTimeout(readTimer);document.removeEventListener('visibilitychange',scheduleRead);window.removeEventListener?.('online',refreshConnected);window.AI2AppsBotInteractions.release(interactions,interactionKey);messageActions.dispose();realtime?.dispose();composer?.dispose();tasks.dispose();memoryFeed?.dispose();abort.abort();clearInterval(timer);if(isActive())root.replaceChildren();},setModel(value){return saveProfile(value);},setReasoningEffort(value){if(value===null||supportedReasoningEfforts.includes(value))return saveProfile(model,value);}};
 }
 window.AI2AppsBotConversation={create,invalidate};
})();
