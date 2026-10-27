/* Intelligence-owned explanation and research adapters for the shared Mini-Chat. */
(()=>{'use strict';
const t=k=>window.IntelligenceI18n.format(k==='title'?'chat.mini.title':'intelligence.article_chat.'+k,{});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
let host,panel,controller,entry,article=null,state=null,serial=0,status='',preparation=null,suggestionsVisible=true;
let purpose='explain',models=[],selectedModel='';
const title=()=>t(purpose==='research'?'research_title':'title');
const endpoint=id=>'/articles/'+encodeURIComponent(id)+'/chat';
const changed=()=>controller?.changed();
function describe(){
 const messages=(state?.turns||[]).flatMap((turn,index)=>[
  {id:'question-'+index,role:'user',content:turn.question},
  {id:'answer-'+index,role:'assistant',format:'markdown',content:turn.answer,references:(turn.references||[]).map(r=>({id:String(r.id||r.number),url:r.url,title:r.title,label:'['+r.number+'] '+r.title}))}
 ]);
 if(state?.pending_search)messages.push({id:'search-question',role:'user',content:state.pending_search.question},{id:'search-request',role:'assistant',content:t('review')});
 return {binding:{sessionId:state?.thread||'loading',contextId:article?.id||'none',revision:'1'},title:title(),subtitle:article?.title||'',
  intro:state?.turns.length||state?.topic_style!==purpose?'':state?.analysis||'',suggestions:state?.topic_style===purpose?state?.questions||[]:[],suggestionsVisible,
  models,model:selectedModel,messages,scopeNote:t('scope'),busy:!state||!!state.busy,status,placeholder:t('placeholder'),sendLabel:t('send'),
  actions:[{id:'confirm',visible:!!preparation}],
  interaction:preparation?{actionId:'confirm',fields:[
   {id:'query',label:t('query'),type:'text',value:preparation.query,required:true,maxLength:1024},
   {id:'source',label:t('source'),type:'select',value:preparation.fast_source,options:[{value:preparation.fast_source,label:preparation.choices.find(c=>c.id===preparation.fast_source)?.name||preparation.fast_source}]}
   ,...(preparation.fast_source==='deepseek'&&preparation.cloud_offer?.available?[{id:'cloud_consent',label:t('cloud_consent').replace('{points}',preparation.cloud_offer.points_per_search),type:'select',value:'false',options:[{value:'false',label:t('cloud_decline')},{value:'true',label:t('cloud_allow')}]}]:[])
  ]}:null};
}
async function reload(version,id){const next=await host.api(endpoint(id)+(purpose==='research'?'?purpose=research':''));if(version!==serial)return;state=next;preparation=state.pending_search||null;changed();}
async function observe(requestId,version,id){
 while(version===serial){
  const result=await host.api(endpoint(id)+'/actions/'+encodeURIComponent(requestId));if(version!==serial)return;
  if(result.args?.mode==='answer')suggestionsVisible=false;
  status=result.progress||t(result.args?.confirmation_id?'researching':result.args?.mode==='answer'?'answering':'analyzing');changed();
  if(['completed','failed','cancelled'].includes(result.status)){
   await reload(version,id);if(version!==serial)return;
   status=result.status==='completed'?'':String(result.error||'').includes('Summary failed source validation')?t('search_summary_failed'):result.error||t('failed');changed();
   if(result.status!=='completed')throw Error(status);return;
  }
  await sleep(1200);
 }
}
async function act(mode,question='',confirmationId=null,requestId=crypto.randomUUID()){
 if(!state||state.busy)throw Error(t('working'));
 const version=serial,id=article.id,thread=state.thread;
 if(mode==='answer')suggestionsVisible=false;status=t('working');changed();
 try{
  await host.api(endpoint(id)+'/actions','POST',{thread,request_id:requestId,mode,question,confirmation_id:confirmationId,...(selectedModel?{model:selectedModel}:{})});if(version!==serial)return;
  state.busy=requestId;changed();await observe(requestId,version,id);
  if(mode==='followup'&&version===serial)suggestionsVisible=true;
 }catch(error){if(version===serial){status=error.message;await reload(version,id).catch(()=>{});}throw error;}
 finally{if(version===serial)changed();}
}
async function open(value,nextPurpose='explain'){
 if(!['explain','research'].includes(nextPurpose))throw Error(t('failed'));
 ensureEntry();
 if(article?.id===value.id&&purpose===nextPurpose&&state){host.showPanel();return;}
 const version=++serial;purpose=nextPurpose;article=value;state=null;preparation=null;status=t('loading');suggestionsVisible=true;host.showPanel();changed();
 try{const catalog=await host.api(endpoint(value.id)+'/models').catch(()=>({models:[]}));if(version!==serial)return;models=catalog.models||[];if(!models.some(m=>m.id===selectedModel))selectedModel=catalog.default||models[0]?.id||'';await reload(version,value.id);if(version!==serial)return;suggestionsVisible=!state.turns.length;status='';changed();
  if(state.busy)await observe(state.busy,version,value.id);else if(state.topic_style!==purpose||!state.turns.length&&!state.questions.length)await act('suggest');
 }catch(error){if(version===serial){status=error.message;changed();}}
}
function ensureEntry(){
 if(entry)return;
 if(window.AI2AppsMiniAppChat?.EXTENSION_SCHEMA!=='ai2apps.app-chat/v1'||!window.AI2AppsMiniAppChat?.mount)throw Error(t('failed'));
 panel=document.createElement('section');panel.className='intel-article-chat';panel.hidden=true;host.panelRoot.append(panel);
 try{
 controller=window.AI2AppsMiniAppChat.createController({identity:{appId:'ai2apps.intelligence',providerId:'intelligence.article-chat',version:'1'},describe,
  send:ctx=>act('answer',ctx.text,null,ctx.requestId),
  selectModel:ctx=>{selectedModel=ctx.model;changed();},
  openReference:ctx=>host.openArticle(ctx.reference.id),
  actions:[
   {id:'reset',hook:'reset',label:t('reset'),tip:t('reset_tip'),placement:'toolbar',order:2,allowWhileBusy:true},
   {id:'confirm',hook:'confirm',label:t('confirm'),placement:'content'}
  ],hooks:{
   reset:async()=>{if(!state)return;const thread=state.thread,id=article.id,version=++serial;const next=await host.api(endpoint(id)+'/reset','POST',{thread});if(version!==serial)return;state=next;preparation=null;suggestionsVisible=true;status='';changed();await act('suggest');},
   confirm:async ctx=>{if(!preparation||!state)return;const version=serial,id=article.id,prepared=preparation;
    const receipt=await host.api(endpoint(id)+'/search/confirm','POST',{thread:state.thread,preparation_id:prepared.id,query:ctx.values.query,source:ctx.values.source,cloud_consent:ctx.values.cloud_consent==='true',cloud_price_version:prepared.cloud_offer?.price_version||'',cloud_max_points:prepared.cloud_offer?.points_per_search||''});
    if(version!==serial)return;preparation=null;changed();await act('answer',prepared.question,receipt.confirmation_id,ctx.requestId);
   }
  }});
 entry=window.AI2AppsMiniAppChat.mount({root:panel,transport:controller,labels:{placeholder:t('placeholder'),send:t('send')}});
 }catch(error){controller?.dispose();controller=null;panel.remove();panel=null;throw error;}
}
let researchLaunch=null;
function openChatThread(chatSeed){
 if(window.parent===window)throw Error(t('chat_unavailable'));
 const hash=new URLSearchParams(location.hash.slice(1)),requestId=crypto.randomUUID();
 return new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>{window.removeEventListener('message',receive);reject(Error(t('chat_unavailable')));},45000);
  function receive(event){const m=event.data||{};if(event.source!==window.parent||event.origin!==location.origin||m.type!=='ai2apps.host.response'||m.requestId!==requestId||m.mountToken!==hash.get('ai2apps-mount'))return;clearTimeout(timer);window.removeEventListener('message',receive);m.ok?resolve(m.result):reject(Error(m.error?.message||t('chat_unavailable')));}
  window.addEventListener('message',receive);
  window.parent.postMessage({type:'ai2apps.shell.open-chat-context',chatSeed,requestId,mountToken:hash.get('ai2apps-mount'),instanceId:hash.get('ai2apps-instance')},location.origin);
 });
}
async function launchResearch(value){
 if(researchLaunch)return;
 const token={closed:false};researchLaunch=token;
 const dialog=document.createElement('dialog');dialog.className='intel-dialog intel-research-wait';
 const heading=document.createElement('h2');heading.textContent=t('research_title');
 const progress=document.createElement('p');progress.setAttribute('role','status');progress.textContent=t('research_wait');
 const close=document.createElement('button');close.type='button';close.textContent=t('close');
 const dismiss=()=>{token.closed=true;dialog.close();dialog.remove();if(researchLaunch===token)researchLaunch=null;};
 close.onclick=dismiss;dialog.addEventListener('cancel',event=>{event.preventDefault();dismiss();});dialog.append(heading,progress,close);document.body.append(dialog);dialog.showModal();
 try{
  const base=endpoint(value.id);let research=await host.api(base+'?purpose=research');
  if(!research.busy){
   const request_id=crypto.randomUUID();await host.api(base+'/actions','POST',{thread:research.thread,request_id,mode:'suggest',question:'',confirmation_id:null});research.busy=request_id;
  }
  const deadline=Date.now()+300000;
  while(research.busy&&!token.closed){
   if(Date.now()>deadline)throw Error(t('failed'));
   const action=await host.api(base+'/actions/'+encodeURIComponent(research.busy));
   if(['failed','cancelled'].includes(action.status))throw Error(action.error||t('failed'));
   if(action.status==='completed')research=await host.api(base+'?purpose=research');else await sleep(1200);
  }
  if(token.closed)return;
  const target=await host.api(base+'/research-handoff','POST',{thread:research.thread,request_id:crypto.randomUUID()});
  if(token.closed)return;
  progress.textContent=t('opening_chat');await openChatThread(target.chat_seed);dismiss();
 }catch(error){if(!token.closed){progress.textContent=error.message;researchLaunch=null;}}
}

function init(options){
 host=options;
 document.addEventListener('click',event=>{const button=event.target.closest('[data-article-chat]');if(button){event.preventDefault();event.stopPropagation();host.getArticle(button.dataset.articleChat).then(article=>button.dataset.articleChatPurpose==='research'?launchResearch(article):open(article)).catch(error=>host.notice(error.message));}});
}
window.IntelligenceArticleChat={init,open,launchResearch,currentArticleId:()=>article?.id,currentTitle:title,setVisible:visible=>{if(panel)panel.hidden=!visible;}};
})();
