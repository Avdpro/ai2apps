/* Host-owned portable UI configuration. No DOM extraction or business execution. */
(()=>{
 'use strict';
 const bindings=new Map(),clone=v=>JSON.parse(JSON.stringify(v));
 const label=(zh,en)=>(document.documentElement.lang||'').startsWith('zh')?zh:en;
 function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
 async function hash(v){const bytes=new TextEncoder().encode(typeof v==='string'?v:canonical(v));return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');}
 function error(code,message){return Object.assign(Error(message),{code});}
 async function request(url,method='GET',body){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);try{const response=await fetch(url,{method,credentials:'same-origin',cache:'no-store',signal:controller.signal,headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const value=await response.json();if(!response.ok)throw error(value.detail?.code||'state_failed',value.detail?.message||value.detail||'App-State failed');return value;}finally{clearTimeout(timer);}}
 function register(owner){
  const {target,instanceId,capture,validate,apply,revision}=owner;
  if(!instanceId||!target?.app_id||![capture,validate,apply,revision].every(f=>typeof f==='function'))throw error('invalid_owner','Explicit App-State owner callbacks required');
  const key=instanceId+':'+target.app_id+':'+(target.mini_app_id||'');if(bindings.has(key))throw error('duplicate_owner','App-State owner already mounted');
  const base='/v1/platform/app-state/instances/'+encodeURIComponent(instanceId),query='?app_id='+encodeURIComponent(target.app_id)+(target.mini_app_id?'&mini_app_id='+encodeURIComponent(target.mini_app_id):'');
  let contract=null,busy=false,disposed=false,last=null;const attempts=new Map();
  async function describe(){if(disposed)throw error('unmounted','App-State owner unmounted');const current=await request(base+'/contract'+query);if(current.contract_version!==target.contract_version)throw error('unsupported_version','App-State UI contract version changed');contract=current;return current;}
  function packet(values){return {schema:'ai2apps.app-state/v1',target:clone(target),values:clone(values)};}
  function closed(values,c){const keys=Object.keys(values||{}),allowed=Object.keys(c.schema.properties);if(keys.length!==allowed.length||keys.some(k=>!allowed.includes(k)))throw error('invalid_fields','Only explicitly declared portable fields may be exported');}
  async function exportState(){const c=await describe(),values=clone(capture());closed(values,c);await validate(values);return (await request(base+'/validate','POST',{packet:packet(values)})).packet;}
  async function restore(state,{requestId=crypto.randomUUID(),confirmConflict=async()=>false}={}){
   if(disposed)throw error('unmounted','App-State owner unmounted');
   const signature=canonical(state),prior=attempts.get(requestId);
   if(prior){if(prior.signature!==signature)throw error('request_conflict','Restore request changed');return prior.promise;}
   if(busy)throw error('busy',label('另一个状态操作尚未完成','Another state operation is pending'));
   busy=true;const attempt={signature};attempts.set(requestId,attempt);
   attempt.promise=(async()=>{
    const c=await describe();
    if(canonical(state.target)!==canonical(target))throw error('target_not_open',label('请先打开预设指定的 App/Mini-App','Open the preset target App/Mini-App first'));
    const normalized=await request(base+'/validate','POST',{packet:state});
    if(normalized.contract_digest!==c.contract_digest)throw error('contract_changed','App-State contract changed during review');
    closed(normalized.packet.values,c);const before=await hash(revision());await validate(clone(normalized.packet.values));
    if(disposed)throw error('unmounted','App-State owner unmounted');
    if(!owner.needsApply?.()&&canonical(capture())===canonical(normalized.packet.values))return {status:'unchanged'};
    if(!owner.needsApply?.()&&last&&last.signature===signature&&last.after===await hash(revision()))return last.result;
    if(owner.dirty?.()&&!(await confirmConflict()))throw error('draft_conflict',label('已保留当前编辑内容，没有恢复预设','Current edits were retained; preset was not restored'));
    if(before!==await hash(revision()))throw error('draft_changed',label('页面在确认期间发生变化，请重新操作','Page changed during review; try again'));
    const ready=await request(base+'/applications','POST',{packet:normalized.packet,request_id:requestId,base_revision:before,contract_digest:normalized.contract_digest});
    if(ready.status!=='prepared')throw error('application_closed','Restore was already acknowledged; it will not be applied again');
    let applied=false;
    try{
     if(disposed||before!==await hash(revision()))throw error('draft_changed','Page changed before restore');
     owner.setBusy?.(true);
     // Owner must commit atomically, without business/auto-submit effects.
     await apply(clone(normalized.packet.values));applied=true;const after=await hash(revision());owner.setBusy?.(false);
     const result=await request(base+'/applications/'+ready.id+'/complete','POST',{packet:normalized.packet,status:'ui_applied'});
     last={signature,after,result};return result;
    }catch(e){
     if(!applied)await request(base+'/applications/'+ready.id+'/complete','POST',{packet:normalized.packet,status:'failed'}).catch(()=>{});
     if(applied)throw error('acknowledgement_unknown',label('设置已恢复，但回执尚未确认；不会自动重试','Settings restored, but acknowledgement is unconfirmed; no automatic retry'));
     throw e;
    }finally{owner.setBusy?.(false);}
   })().finally(()=>{busy=false;});
   return attempt.promise;
  }
  const binding=Object.freeze({target:clone(target),instanceId,describe,export:exportState,restore,activate:()=>owner.activate?.(),configureDependencies:owner.configureDependencies?()=>owner.configureDependencies():null,
   async save(name){const value=await exportState();return request(base+'/presets','POST',{name,packet:value,request_id:crypto.randomUUID()});},
   async presets(){await describe();return request(base+'/presets'+query);},
   dispose(){disposed=true;bindings.delete(key);},
  });bindings.set(key,binding);Promise.resolve().then(()=>window.dispatchEvent?.(new CustomEvent('ai2apps:app-state-registered',{detail:{instanceId,target:clone(target)}})));return binding;
 }
 function dialog(title){const root=document.createElement('dialog');root.className='app-state-dialog';const h=document.createElement('h2');h.textContent=title;root.append(h);document.body.append(root);return root;}
 function button(text,action){const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=action;return b;}
 async function confirmConflict({message}={}){return new Promise(resolve=>{const d=dialog(label('恢复设置预设？','Restore settings preset?'));const p=document.createElement('p');p.textContent=message||label('当前页面有编辑内容。恢复会替换预设声明的设置，文字和素材保留；不会启动任务。','The page has edits. Only declared settings will be replaced; text and materials remain. No task will start.');d.append(p,button(label('保留当前设置','Keep current settings'),()=>{d.close();}),button(label('恢复这些设置','Restore these settings'),()=>{d.returnValue='restore';d.close();}));d.onclose=()=>{const ok=d.returnValue==='restore';d.remove();resolve(ok);};d.showModal();});}
 async function panel(binding){
  const d=dialog(label('状态预设','State presets')),name=document.createElement('input'),status=document.createElement('p'),rows=document.createElement('div');
  name.placeholder=label('预设名称','Preset name');name.setAttribute('aria-label',name.placeholder);name.maxLength=80;
  const c=await binding.describe().catch(e=>{d.remove();throw e;});const hint=document.createElement('p');hint.textContent=c.name+' · '+label('仅保存设置，不包含文字、素材、权限或任务。','Settings only; excludes text, materials, permissions and tasks.');d.append(hint,name);
  const act=async fn=>{d.querySelectorAll('button').forEach(b=>b.disabled=true);try{await fn();status.textContent=label('已完成','Done');}catch(e){status.textContent=e.message;}finally{d.querySelectorAll('button').forEach(b=>b.disabled=false);}};
  async function load(){rows.replaceChildren();for(const item of (await binding.presets()).items){const row=document.createElement('div');row.append(button(item.name,()=>act(()=>binding.restore(item.packet,{confirmConflict}))));rows.append(row);}}
  if(window.AI2AppsAppShortcuts)d.append(button(label('创建快捷 Bot','Create shortcut Bot'),()=>act(()=>window.AI2AppsAppShortcuts.capture(binding,{name:name.value}))));
  d.append(button(label('保存当前设置','Save current settings'),()=>act(async()=>{await binding.save(name.value);await load();})),rows,status,button(label('关闭','Close'),()=>d.close()));
  d.onclose=()=>d.remove();await load().catch(e=>{d.remove();throw e;});d.showModal();
 }
 window.AI2AppsAppState=Object.freeze({register,panel,confirmConflict,targets:()=>[...bindings.values()].map(b=>({target:clone(b.target),instanceId:b.instanceId})),binding:(instance,target)=>bindings.get(instance+':'+target.app_id+':'+(target.mini_app_id||''))});
})();
