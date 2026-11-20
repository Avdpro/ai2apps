/* Bot conversations share Chat's Agent suitability/default policy and catalog sources. */
(function(root){
 'use strict';
 async function resolve(saved,{signal}={}){
  async function read(url,required=false){try{const r=await fetch(url,{credentials:'same-origin',cache:'no-store',signal});if(!r.ok)throw Error('Model catalog unavailable');return await r.json();}catch(e){if(required||signal?.aborted)throw e;return {};}}
  const [catalog,admin,manager,cloud]=await Promise.all([read('/v1/models',true),read('/admin/api/models'),read('/admin/api/model-manager'),read('/v1/platform/cloud/ai/defaults')]);
  const policy=root.AI2AppsConversationModelPolicy,managed=admin.models||[],aliases=new Map();
  for(const m of managed){const alias=m.settings?.model_alias||m.model_alias;if(alias)aliases.set(alias,m.id);}
  const candidates=[...(catalog.data||[])];const ids=new Set(candidates.map(m=>m.id));
  for(const m of managed)if(['cloud','fusion'].includes(m.source_type)&&!ids.has(m.id))candidates.push(m);
  const merged=new Map();
  for(const item of candidates){const id=aliases.get(item.id)||item.id,owner=managed.find(m=>m.id===id),m={...item,...owner,id,
    name:owner?.identity?.displayName||owner?.display_name||item.identity?.displayName||item.display_name||item.name||id,
    model_type:owner?.model_type||item.model_type||'',
    checkpoint_ready:owner?.checkpoint_ready!==false&&item.checkpoint_ready!==false,
    capabilities:owner?.capabilities??item.capabilities??[],
    agent_capability_declaration:owner?.agent_capability_declaration??item.agent_capability_declaration??null};
   if(!merged.has(id))merged.set(id,m);
  }
  const api=cloud.policy?.apiDefault,apiId=api?.modelId?'cloud/ai2apps/'+api.modelId:null;
  if(apiId&&!merged.has(apiId)){const source=merged.get('cloud/'+api.modelId);if(source)merged.set(apiId,{...source,id:apiId,name:(api.displayName||source.name)+' (API Default)'});}
  const allModels=[...merged.values()];
  // Same model classes/readiness as Chat Agent; declarations rank options but do not
  // erase explicit user choices merely because capabilities are undeclared.
  const nonConversation=new Set(['audio_generation','image_generation','video_generation','speech_to_text','text_to_speech','text_to_video','image_to_video','synchronized_audio','embedding','reranking']);
  const models=policy.agentOptions(allModels.filter(m=>{
   if(m.load_failed)return false;
   // Chat also uses declared endpoint capabilities when older catalogs omit type.
   if(Array.isArray(m.capabilities)){
    const caps=m.capabilities.map(v=>String(v).toLowerCase());
    if(!caps.some(v=>['conversation','chat','chat_completions'].includes(v))&&caps.some(v=>nonConversation.has(v)))return false;
   }
   return true;
  }));
  const normalize=id=>aliases.get(id)||id;
  const defaults=manager.defaults||{};
  const preferred=policy.agentDefault(models,normalize(defaults.work_agent),[normalize(defaults.work_standard),normalize(defaults.work_complex)],apiId);
  const explicit=normalize(saved),selected=models.some(m=>m.id===explicit)?explicit:preferred||'';
  const notice=selected?policy.agentNotice(models.find(m=>m.id===selected),{explicit:selected===explicit,language:document.documentElement.lang}):
    ((document.documentElement.lang||'').startsWith('zh')?'默认 Agent 对话模型不可用，请选择对话模型。':'The default Agent conversation model is unavailable. Choose a conversation model.');
  return {models,selected,allModels,notice};
 }
 async function profile(bot,options={}){
  const r=await fetch('/v1/platform/messager/bots/'+encodeURIComponent(bot)+'/conversation-model',{credentials:'same-origin',signal:options.signal});
  if(!r.ok)throw Error('Bot model profile unavailable');return r.json();
 }
 async function save(bot,model,revision,options={}){
  const r=await fetch('/v1/platform/messager/bots/'+encodeURIComponent(bot)+'/conversation-model',{method:'PUT',credentials:'same-origin',signal:options.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify({model_id:model,revision,...(options.reasoningEffort===undefined?{}:{reasoning_effort:options.reasoningEffort})})});
  const value=await r.json();if(!r.ok)throw Error(value.error?.message||value.detail||'Bot model changed; reload before saving');return value;
 }
 async function forBot(bot,saved,options={}){
  let current=await profile(bot,options);
  const result=await resolve(current.model_id||saved||current.effective_model,options);
  if(current.model_id&&result.selected!==current.model_id){result.selected=current.model_id;result.notice='';}
  if(result.selected&&!result.models.some(m=>m.id===result.selected))result.models.push({id:result.selected,name:result.selected,display_name:result.selected});
  if(!current.model_id&&result.selected){try{current=await save(bot,result.selected,current.revision,options);}catch(e){current=await profile(bot,options);if(!current.model_id)throw e;result.selected=current.model_id;}}
  return {...result,profileRevision:current.revision,reasoningEffort:current.reasoning_effort,supportedReasoningEfforts:current.supported_reasoning_efforts};
 }
 async function install(){
  if(!root.AI2AppsCapabilities?.ensure)throw Error((document.documentElement.lang||'').startsWith('zh')?'模型配置暂时不可用，请重新打开消息。':'Model setup is unavailable. Reopen Messager.');
  const result=await root.AI2AppsCapabilities.ensure({appId:'ai2apps.messager',capability:'text.chat.local',actionId:'install-bot-conversation-model',requirements:{operations:['conversation']},intent:{returnTo:'/apps/ai2apps.messager',resumeToken:crypto.randomUUID(),completionPolicy:'configure_only'}},{installMore:true});
  if(result?.status==='ready'&&result?.session?.id)await root.AI2AppsCapabilities.acknowledge(result.session,{appId:'ai2apps.messager'});
  return result;
 }
 root.AI2AppsBotModelSelection={resolve,install,profile,save,forBot};
})(window);
