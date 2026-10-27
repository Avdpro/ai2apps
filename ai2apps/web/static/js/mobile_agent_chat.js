/* Mobile presentation of durable Agent state. Authority always remains server-owned. */
(function(root){'use strict';
const terminal=new Set(['completed','failed','cancelled','interrupted']);
const id=value=>encodeURIComponent(value);
class Client {
 constructor({container,request,enabled,onComplete,onBusy,loadOwners,placeRun,uploadMaterial,forms=root.AI2AppsParameterForms,delay=ms=>new Promise(r=>setTimeout(r,ms))}){
  Object.assign(this,{container,request,enabled,onComplete,onBusy,loadOwners,placeRun,uploadMaterial,forms,delay});this.generation=0;this.runs=new Map();this.cards=new Map();this.responses=new Map();this.inflight=new Set();this.ownerCatalog={apps:[],minis:[]};this.ownersLoaded=false;this.ownersLoading=false;
 }
 stop(){this.generation++;for(const card of this.cards.values())card.remove();this.cards.clear();this.runs.clear();this.container.replaceChildren?.();this.onBusy?.(false);}
 placeCards(){for(const [key,card] of this.cards)this.placeRun?.(card,this.runs.get(key));}
 async restore(thread){this.stop();if(!this.enabled)return;const generation=this.generation;
  try{const payload=await this.request('/v1/mobile/chat/threads/'+id(thread)+'/agent-runs');if(generation!==this.generation)return;
   this.container.replaceChildren();for(const run of payload.items||[]){this.show(run);if(!terminal.has(run.status))this.watch(run,generation);}
  }catch(error){if(generation===this.generation)this.error(error);}
 }
 error(error){let node=this.container.querySelector('[data-agent-error]');if(!node){node=this.container.ownerDocument.createElement('p');node.dataset.agentError='';node.setAttribute('role','alert');this.container.append(node);}node.textContent=error.message;}
 async start(thread,input,agent,key){if(!this.enabled)throw Error('Agent access is unavailable for this connection');
  const run=await this.request('/v1/mobile/chat/threads/'+id(thread)+'/agent-runs',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':key},body:JSON.stringify({agent,input,idempotency_key:key})});
  this.show(run);void this.watch(run,this.generation);return run;
 }
 async watch(run,generation){const watchKey=generation+':'+run.id;if(this.inflight.has(watchKey))return;this.inflight.add(watchKey);
  try{while(generation===this.generation&&!terminal.has(run.status)){await this.delay(1000);if(generation!==this.generation)return;run=await this.request('/v1/mobile/agent-runs/'+id(run.id));if(generation!==this.generation)return;this.show(run);}
   if(generation===this.generation&&terminal.has(run.status))await this.onComplete?.(run);
  }catch(error){if(generation===this.generation){this.error(Error('连接中断，任务状态未确认。重新连接只读取状态，不会重复执行。 '+error.message));this.onBusy?.(false);}}
  finally{this.inflight.delete(watchKey);}
 }
 async refresh(run){const next=await this.request('/v1/mobile/agent-runs/'+id(run.id));this.show(next);return next;}
 async focusInteraction(session,runId,interactionId){
  if(!this.enabled||!runId||!interactionId)throw Error('交互入口不可用');
  const generation=this.generation;
  const check=run=>{
   if(generation!==this.generation)throw Error('当前对话已切换');
   const item=(run.interactions||[]).find(x=>x.id===interactionId&&x.status==='pending');
   if(run.session_id!==session||!['waiting_input','waiting_capability'].includes(run.status)||!item||Date.parse(item.deadline_at)<=Date.now()||Date.parse(run.deadline_at)<=Date.now())throw Error('此步骤已处理、取消或过期，请查看对话当前状态。');
   return item;
  };
  const run=await this.request('/v1/mobile/agent-runs/'+id(runId)),item=check(run);this.show(run);
  const section=[...(this.cards.get(runId)?.querySelectorAll('[data-agent-interaction-id]')||[])].find(n=>n.dataset.agentInteractionId===interactionId);
  if(!section)throw Error('交互未能展示');
  if((item.ui_hints?.control||item.request?.control)==='parameter_form')await new Promise((resolve,reject)=>{
   let timer;const observer=new MutationObserver(inspect);
   function done(error){observer.disconnect();clearTimeout(timer);error?reject(error):resolve();}
   function inspect(){if(!section.isConnected)return done(Error('交互已更新，请重新打开'));if(section.querySelector('form'))return done();if(section.querySelector('[role=alert]'))done(Error('参数表单加载失败'));}
   observer.observe(section,{childList:true,subtree:true});timer=setTimeout(()=>done(Error('参数表单加载超时')),10000);inspect();
  });
  check(await this.request('/v1/mobile/agent-runs/'+id(runId)));
  if(!section.isConnected)throw Error('交互已更新，请重新打开');
  section.tabIndex=-1;section.scrollIntoView?.({block:'center'});section.focus?.({preventScroll:true});
 }
 async respond(run,item,response){const key=run.id+':'+item.id;let saved=this.responses.get(key);
  // Keep the exact response and id across an uncertain network result.
  if(saved&&JSON.stringify(saved.response)!==JSON.stringify(response))throw Error('上次提交结果尚未确认，请刷新任务状态后再操作。');
  if(!saved){saved={response,response_id:root.crypto.randomUUID()};this.responses.set(key,saved);}
  const next=await this.request('/v1/mobile/agent-runs/'+id(run.id)+'/interactions/'+id(item.id)+'/respond',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(saved)});this.show(next);
 }
 async assistance(run,taskId,container,node){
  const path='/v1/mobile/agent-runs/'+id(run.id)+'/browser-tasks/'+id(taskId),key=container.dataset.key;
  try{
   const task=await this.request(path);if(container.dataset.key!==key)return;
   const button=(label,payload)=>{const b=node('button',label);b.type='button';b.onclick=async()=>{
    b.disabled=true;try{await this.request(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...payload,response_id:(this.responses.get(path+':'+payload.action+':'+payload.interaction_id)||(()=>{const value=root.crypto.randomUUID();this.responses.set(path+':'+payload.action+':'+payload.interaction_id,value);return value;})())})});delete container.dataset.key;await this.refresh(run);}
    catch(e){this.error(e);}finally{b.disabled=false;}
   };container.append(b);};
   if(task.requires_user){if((task.interactions||[]).some(i=>i.control!=='agent_budget'))button('在 Desktop 打开问题页面',{action:'open'});
    for(const item of task.interactions||[])button(item.control==='agent_budget'?'继续并重置额度':item.control==='agent_confirmation'?'确认继续':'已处理，继续',{action:'continue',interaction_id:item.id});
   }
   if(!terminal.has(task.status))button('取消任务',{action:'cancel'});
  }catch(e){if(container.dataset.key===key){container.append(node('p','协助入口加载失败：'+e.message));delete container.dataset.key;}}
 }
 async refreshOwners(run){
  if(!this.loadOwners||this.ownersLoaded||this.ownersLoading)return;
  this.ownersLoading=true;
  try{this.ownerCatalog=await this.loadOwners(run);this.ownersLoaded=true;for(const run of this.runs.values())this.show(run);}
  catch(_){/* Recorded identities remain visible when optional directory reads fail. */}
  finally{this.ownersLoading=false;}
 }
 owners(run){
  const records=(run.steps||[]).filter(s=>s.kind==='tool').map(s=>s.output||s.error?.details||{});
  if(run.status_line?.content)records.push(run.status_line.content);
  const result=[],seen=new Set(),catalog=this.ownerCatalog;
  const add=owner=>{const key=owner.kind+':'+owner.id;if(!seen.has(key)){seen.add(key);result.push(owner);}};
  for(let output of records){
   if(output.result?.executed_in_app)output=output.result;
   const mini=catalog.minis.find(m=>m.id===output.mini_app_id);
   const appId=output.app_id||mini?.app_id;
   const app=catalog.apps.find(a=>(a.app_key||a.id)===appId);
   if(appId)add({kind:'App',id:appId,name:app?.display_name||appId,icon:app?.navigation?.icon||app?.icon});
   if(output.mini_app_id)add({kind:'Mini-App',id:output.mini_app_id,name:mini?.displayName||mini?.display_name||mini?.name||mini?.title||output.mini_app_id,icon:mini?.icon});
  }
  return result;
 }
 show(run){if(!this.enabled)return;this.runs.set(run.id,run);this.container.hidden=false;void this.refreshOwners(run);
  this.onBusy?.([...this.runs.values()].some(r=>!terminal.has(r.status)));
  const doc=this.container.ownerDocument,node=(tag,text)=>{const n=doc.createElement(tag);if(text!==undefined)n.textContent=String(text);return n;};
  let card=this.cards.get(run.id);
  if(!card){card=node('section');card.dataset.runId=run.id;card.className='mchat-agent-run';this.cards.set(run.id,card);this.container.append(card);}
  this.placeRun?.(card,run);
  // Repeated snapshots update progress without replacing an in-progress form/draft.
  const pending=(run.interactions||[]).filter(i=>i.status==='pending');const signature=JSON.stringify(pending.map(i=>[i.id,i.revision]));
  let header=card.querySelector('header');if(!header){header=node('header');card.append(header);}header.replaceChildren(node('strong',run.agent_display_name||'Agent'),node('span',(run.status_line?.content?.task_progress?.requires_user?'需要协助':(['waiting_input','waiting_capability'].includes(run.status)&&pending.find(i=>['parameter_form','app_handoff','approval'].includes(i.ui_hints?.control))?window.AI2AppsParameterForms?.prompt(pending.find(i=>['parameter_form','app_handoff','approval'].includes(i.ui_hints?.control))):'')||run.status_line?.text||run.status)));
  const parameterPending=pending.some(item=>item.ui_hints?.control==='parameter_form'||item.request?.control==='parameter_form');
  if(parameterPending){const status=header.querySelector('span');if(status){status.textContent='';status.hidden=true;}}
  const owners=this.owners(run);
  if(owners.length){const badges=node('div');badges.className='mchat-agent-owners';
   for(const owner of owners){const badge=node('span');badge.className='mchat-agent-owner';badge.dataset.ownerId=owner.id;
    const name=typeof owner.name==='string'?owner.name:owner.id;badge.title=owner.kind+' · '+name;badge.setAttribute('role','img');badge.setAttribute('aria-label',badge.title);
    const key=String(owner.icon||'app-window').replace(/(^|-)([a-z])/g,(_,dash,c)=>c.toUpperCase());
    const icon=root.lucide?.icons?.[key]||root.lucide?.icons?.AppWindow;
    if(icon&&root.lucide?.createElement)badge.append(root.lucide.createElement(icon,{width:20,height:20,'stroke-width':1.8,'aria-hidden':'true'}));else badge.textContent='▧';
    badges.append(badge);
   }header.prepend?header.prepend(badges):header.append(badges);
  }
  const taskProgress=run.status_line?.content?.task_progress;
  const detail=node('small',taskProgress?.state==='waiting'?'等待协助':run.status);header.append(detail);
  if(taskProgress){
   for(const metric of taskProgress.metrics||[])header.append(node('p',metric.label+' · '+metric.value+(metric.total==null?'':' / '+metric.total)));
   if(taskProgress.requires_user)header.append(node('p',taskProgress.wait_reason||'此任务需要协助，请在下方处理。'));
  }
  let assistance=card.querySelector('[data-browser-assistance]');
  if(!assistance){assistance=node('div');assistance.dataset.browserAssistance='';card.append(assistance);}
  const taskId=run.status_line?.content?.browser_task_id;
  if(taskProgress?.requires_user&&taskId){
   const key=taskId+':'+taskProgress.wait_reason;
   if(assistance.dataset.key!==key){assistance.dataset.key=key;assistance.replaceChildren();
    void this.assistance(run,taskId,assistance,node);
   }
  }else{assistance.replaceChildren();delete assistance.dataset.key;}

  const progress=node('progress');progress.max=1;if(terminal.has(run.status)){progress.value=run.status==='completed'?1:0;progress.hidden=true;detail.hidden=Boolean(run.status_line?.text);}else if(Number.isFinite(run.status_line?.progress))progress.value=Math.max(0,Math.min(1,run.status_line.progress));header.append(progress);
  if(run.error?.message&&run.error.message.trim()!==(run.status_line?.text||'').trim())header.append(node('p',run.error.message));
  let body=card.querySelector('[data-agent-interactions]');if(!body){body=node('div');body.dataset.agentInteractions='';card.append(body);}
  for(const section of body.querySelectorAll?.('.mchat-agent-interaction')||[]){const item=pending.find(i=>i.id===section.dataset.agentInteractionId);if(item)section._approvalCountdown?.sync(run,item);}
  const button=(text,action)=>{const b=node('button',text);b.type='button';b.onclick=async()=>{if(b.disabled)return;b.disabled=true;try{await action();}catch(e){this.error(e);}finally{b.disabled=false;}};return b;};
  if(card.dataset.signature!==signature){body.replaceChildren();card.dataset.signature=signature;
   for(const item of pending){const section=node('section');section.className='mchat-agent-interaction';section.dataset.agentInteractionId=item.id;const heading=node('p',window.AI2AppsParameterForms?.prompt(item)||item.prompt||'请确认后继续');heading.setAttribute('data-parameter-prompt','');section.append(heading);body.append(section);
    const control=item.ui_hints?.control||item.request?.control;
    if(control==='parameter_form'){
     this.forms.mount(section,run,item,()=>this.refresh(run),{uploadMaterial:this.uploadMaterial,request:(url,options)=>{
      if(!url.startsWith('/v1/platform/agent-runs/'+id(run.id)+'/'))throw Error('此资源需要在目标 App 中访问');
      return this.request(url.replace('/v1/platform/','/v1/mobile/'),options);
     }});continue;
    }
    if(control==='app_handoff'){
     section.append(node('p','此步骤由目标 App 完成。可在桌面打开对应任务；完成后本页自动同步，请勿重复提交。'));
     section.append(button('取消此步骤',()=>this.respond(run,item,{status:'cancelled',result:{}})));continue;
    }
    if(item.kind==='approval'){
     section.append(node('p','仅允许一次：只授权本次请求。记住工具：在发起对话的当前应用中允许此工具访问不同资源，不适用于其他工具或整个 Desktop。'));
     section.append(button('仅允许这一次',()=>this.respond(run,item,{decision:'approve',scope:'once'})));
     if(item.response_schema?.properties?.resource_scope)section.append(button('在当前应用中记住此工具',()=>this.respond(run,item,{decision:'approve',scope:'app',resource_scope:'tool'})));
     section.append(button('拒绝',()=>this.respond(run,item,{decision:'deny'})));this.forms?.mountApproval?.(section,run,item,()=>this.respond(run,item,{decision:'approve',scope:'once'}));continue;
    }
    const properties=item.response_schema?.properties||{};const field=item.response_schema?.required?.[0]||Object.keys(properties)[0]||'value';
    const choices=item.ui_hints?.options||properties[field]?.enum;
    if(Array.isArray(choices)){for(const value of choices)section.append(button(value,()=>this.respond(run,item,{[field]:value})));continue;}
    if(item.kind==='text'||item.kind==='form'){
     const form=node('form'),inputs=new Map();let unsupported=false;for(const [key,schema] of Object.entries(properties)){
      if(!['string','number','integer','boolean'].includes(schema.type)){unsupported=true;section.append(node('p','此交互格式需要在桌面目标 App 完成。'));continue;}
      const label=node('label',schema.title||key),input=node('input');input.name=key;input.type=schema.type==='boolean'?'checkbox':['number','integer'].includes(schema.type)?'number':'text';if(schema.type==='integer')input.step='1';input.required=(item.response_schema.required||[]).includes(key);if(schema.default!==undefined){if(input.type==='checkbox')input.checked=schema.default;else input.value=schema.default;}inputs.set(key,{input,schema});label.append(input);form.append(label);
     }
     const submit=node('button','确认并继续');submit.type='submit';submit.disabled=unsupported;form.append(submit);form.onsubmit=async e=>{e.preventDefault();if(submit.disabled)return;const response={};for(const [key,{input,schema}] of inputs){if(input.type==='checkbox')response[key]=input.checked;else if(input.value!==''||input.required)response[key]=['number','integer'].includes(schema.type)?Number(input.value):input.value;}submit.disabled=true;try{await this.respond(run,item,response);}catch(error){this.error(error);}finally{submit.disabled=false;}};section.append(form);
    }else section.append(node('p','请在桌面完成此交互；本页继续同步状态。'));
   }
  }
  let actions=card.querySelector('[data-agent-actions]');if(!actions){actions=node('div');actions.dataset.agentActions='';card.append(actions);}actions.replaceChildren();
  const seenFiles=new Set();
  for(const step of run.steps||[]){for(const file of step.output?.files||[]){
   if(!file?.artifact_id||seenFiles.has(file.artifact_id))continue;seenFiles.add(file.artifact_id);
   if(root.AI2AppsAgentConnection?.downloadFile)actions.append(button('下载 '+(file.filename||'结果文件'),()=>root.AI2AppsAgentConnection.downloadFile(run.id,file.artifact_id,file.filename)));
  }}
  if(!terminal.has(run.status)&&!(taskProgress?.requires_user&&taskId))actions.append(button('取消任务',async()=>{const next=await this.request('/v1/mobile/agent-runs/'+id(run.id)+'/cancel',{method:'POST'});this.show(next);}));
  if(terminal.has(run.status)&&run.output?.aaat_views&&!run.output?.message_id){let views=card.querySelector('[data-run-views]');if(!views){views=node('div');views.dataset.runViews='';card.append(views);}root.AI2AppsResultViews?.render(views,run.output.aaat_views);}
 }
}
root.AI2AppsMobileAgentChat={Client,terminal};if(typeof module!=='undefined')module.exports={Client,terminal};
})(typeof window==='undefined'?globalThis:window);
