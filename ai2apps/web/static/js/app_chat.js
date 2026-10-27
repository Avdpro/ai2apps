/* Durable App Chat transport. Display is the shared Mini-Chat surface; all
 * model/tool execution and history belong to Local, never the owning page. */
(function(){
'use strict';
async function create(options){
 const sdk=window.AI2AppsMiniAppChat,mount=crypto.randomUUID();
 let snapshot=null,model='',models=[],disposed=false,polling=false,uiBusy=false,lastError='';
 const done=new Set();
 async function request(path,method='GET',body){
  const response=await fetch('/v1/platform'+path,{method,credentials:'same-origin',cache:'no-store',
   headers:{'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const value=await response.json();if(!response.ok)throw Error(typeof value.detail==='string'?value.detail:value.error?.message||'App Chat request failed');return value;
 }
 const restoreKey='ai2apps.app-chat.last.'+options.registration;
 const previous=localStorage.getItem(restoreKey);
 if(previous&&options.restoreLast!==false){
  try{const saved=await request('/app-chat/sessions/'+encodeURIComponent(previous));if(saved.owner===options.registration&&(!options.matchesScope||options.matchesScope(saved.scope))){snapshot=saved;await options.onRestore?.(saved.scope);}}catch(_){localStorage.removeItem(restoreKey);}
 }
 if(!snapshot)snapshot=await request('/app-chat/sessions','POST',{registration:options.registration,scope:options.scope(),ui:await options.readUI()});
 localStorage.setItem(restoreKey,snapshot.session_id);
 const sid=snapshot.session_id,base='/app-chat/sessions/'+encodeURIComponent(sid);
 try{
  const r=await fetch('/v1/models',{credentials:'same-origin'}),catalog=await r.json();
  const selection=await sdk.resolveModelSelection((catalog.data||[]).map(m=>({...m,name:m.name||m.id})),localStorage.getItem('ai2apps.app-chat.model.v1'));
  models=selection.models;model=selection.selected||models[0]?.id||'';
 }catch(_){/* The send path reports an unavailable model explicitly. */}
 const active=()=>snapshot.runs.find(r=>!['completed','failed','cancelled','timed_out','interrupted'].includes(r.status));
 const actions=[{id:'respond',hook:'respond',placement:'composer',label:{zh:'提交回答',en:'Submit answer'},allowWhileBusy:true}];
 const controller=sdk.createController({identity:{appId:options.appId,providerId:options.registration,version:snapshot.version},actions,
  describe:()=>{
   const run=active(),pending=run?.interactions?.[0],props=pending?.schema?.properties||{};
   return {binding:{sessionId:sid,contextId:options.registration,revision:snapshot.version},title:options.title,
    subtitle:options.subtitle||'',messages:snapshot.messages,models,model,busy:!!run,
    status:lastError||run?.text||snapshot.runs.at(-1)?.error?.message||'',
    scopeNote:options.scopeNote||'',actions:[{id:'respond',visible:!!pending}],
    interaction:pending?{id:pending.id,actionId:'respond',title:pending.prompt,
     fields:Object.entries(props).map(([name,s])=>({id:name,label:s.title||name,type:s.enum?'select':s.type==='boolean'?'checkbox':'text',options:s.enum?.map(v=>({value:v,label:v})),required:pending.schema.required?.includes(name)}))}:null};
  },
  send:async ctx=>{
   if(!model)throw Error('Select an available model');
   snapshot=await request(base+'/ui','PUT',{mount,ui:await options.readUI()});
   await request(base+'/turns','POST',{request_id:ctx.requestId,text:ctx.text,model});
   await poll();
  },
  selectModel:ctx=>{model=ctx.model;localStorage.setItem('ai2apps.app-chat.model.v1',model);},
  cancel:async()=>{const run=active();if(run)await request('/agent-runs/'+run.id+'/cancel','POST',{});await poll();},
  hooks:{respond:async ctx=>{
   const run=active(),pending=run?.interactions?.[0];if(!pending)throw Error('Interaction is no longer pending');
   await request('/agent-runs/'+run.id+'/interactions/'+pending.id+'/respond','POST',{response_id:ctx.requestId,response:ctx.values||ctx.fields||{}});await poll();
  }}
 });
 async function poll(){
  if(disposed||polling||document.hidden)return;polling=true;
  try{
   const ui=await options.readUI();
   snapshot=await request(base);
   // A command is validated before any UI effect, against mount and snapshot.
   for(const command of snapshot.commands){
    if(done.has(command.id))continue;
    const key='ai2apps.app-chat.ui.'+command.id;
    let applied=false,result={reason:'UI context changed or a previous application has an unknown acknowledgement'};
    const matches=command.mount===mount&&command.revision===snapshot.ui_revision&&JSON.stringify(ui)===JSON.stringify(snapshot.ui);
    if(matches&&!sessionStorage.getItem(key)&&!uiBusy){
     sessionStorage.setItem(key,'attempted');uiBusy=true;
     try{result=await options.applyUI(command.arguments);applied=true;}catch(error){result={reason:error.message};}
     finally{uiBusy=false;}
    }
    await request(base+'/ui/'+command.id,'POST',{mount,revision:command.revision,applied,result});done.add(command.id);
   }
   snapshot=await request(base+'/ui','PUT',{mount,ui:await options.readUI()});lastError='';
   if(!active())await options.onSettled?.();
  }catch(error){lastError=error.message;}
  finally{polling=false;controller.changed();}
 }
 const timer=setInterval(poll,1200);await poll();
 const dispose=()=>{disposed=true;clearInterval(timer);controller.dispose();};
 window.addEventListener('pagehide',dispose,{once:true});
 return {...controller,dispose,sessionId:sid};
}
window.AI2AppsAppChat={schema:'ai2apps.app-chat/v2',create};
})();
