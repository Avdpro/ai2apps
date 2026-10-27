/* Trusted descriptors only; values and ACPF intent survive Local restarts. */
(() => {
'use strict';
const mounted=new Map(),approvalMounted=new Map();
const zh=()=>document.documentElement.lang.startsWith('zh');
const label=(a,b)=>zh()?a:b;
// Owner text may be a legacy string or an optional {zh, en} translation map.
const ownerText=(value,fallback='')=>typeof value==='string'?value:(value&&typeof value==='object'?(value[zh()?'zh':'en']||value.en||fallback):fallback);
if(document.head){const style=document.createElement('style');style.textContent=`
.agent-parameter-form{container-type:inline-size;--form-line:var(--border-normal,var(--border-color,#dce2eb));}
.agent-parameter-required::before{content:"*";}
.agent-parameter-required{color:#dc2626;margin-left:4px;}
.agent-parameter-field[data-empty-required=true] .agent-interaction-input{background:#fff1f2;}
.dark .agent-parameter-field[data-empty-required=true] .agent-interaction-input,[data-theme=dark] .agent-parameter-field[data-empty-required=true] .agent-interaction-input{background:#3b2027;}
.dark .agent-parameter-required,[data-theme=dark] .agent-parameter-required{color:#f87171;}
.agent-parameter-countdown{font-size:13px;font-weight:400;margin-left:8px;}
.agent-parameter-countdown-cancel{font:inherit;font-size:12px;margin-left:8px;background:none;border:0;color:var(--text-secondary,#64748b);text-decoration:underline;cursor:pointer;}
.agent-parameter-title{margin:0 0 10px;font-size:15px;font-weight:700;line-height:1.45;}
.agent-parameter-fields{display:flex;flex-wrap:wrap;align-items:flex-start;gap:16px 20px;margin:20px 0;}
.agent-parameter-field{flex:1 1 260px;min-width:0;max-width:100%;}
.agent-parameter-field[data-width=compact]{flex:0 1 132px;}
.agent-parameter-field[data-width=full]{flex-basis:100%;}
.agent-parameter-field>label{display:block;margin-bottom:7px;font-size:13px;font-weight:600;line-height:1.45;}
.agent-parameter-form .agent-interaction-input{box-sizing:border-box;width:100%;min-width:0;min-height:42px;padding:9px 12px;border:1px solid var(--form-line);border-radius:10px;background:var(--bg-primary,#fff);color:inherit;font:inherit;}
.agent-parameter-form .agent-interaction-input:focus-visible{outline:2px solid var(--accent-color,#4285ed);outline-offset:2px;}
.agent-parameter-form .agent-interaction-button{min-height:40px;border-radius:10px;padding:8px 13px;}
.agent-parameter-actions{display:flex;flex-wrap:wrap;gap:8px;border-top:1px solid var(--form-line);padding-top:16px;margin-top:16px;}
.agent-records-wrap{overflow-x:auto;margin:8px 0 10px;}
.agent-records-table{width:100%;table-layout:fixed;border-collapse:collapse;}
.agent-records-table th{text-align:left;font-size:12px;font-weight:600;opacity:.75;padding:0 8px 8px 0;}
.agent-records-table td{padding:5px 8px 5px 0;vertical-align:middle;}
.agent-records-table th:last-child,.agent-records-table td:last-child{padding-right:0;}
.agent-records-table col[data-type=number]{width:112px;}
.agent-records-table col[data-type=action]{width:80px;}
.agent-parameter-error:empty{display:none;}
.agent-parameter-error{font-size:13px;color:var(--danger-color,#bd3535);overflow-wrap:anywhere;}
@container (max-width:480px){
 .agent-parameter-fields{gap:14px 12px;margin:16px 0;}
 .agent-parameter-field{flex-basis:100%;}
 .agent-parameter-field[data-width=compact]{flex:1 1 112px;max-width:calc(50% - 6px);}
 .agent-records-table col[data-type=number]{width:76px;}
 .agent-records-table col[data-type=action]{width:64px;}
 .agent-records-table td{padding-right:6px;}
 .agent-records-table .agent-interaction-button{padding:8px;}
 .agent-parameter-form .agent-interaction-input{font-size:16px;min-height:44px;}
}
`;document.head.append(style);}
async function request(url,options={}) {
 const r=await fetch(url,{credentials:'same-origin',...options});const data=await r.json().catch(()=>({}));
 if(!r.ok){const error=new Error(typeof data.detail==='object'?JSON.stringify(data.detail):data.detail||data.error?.message||`HTTP ${r.status}`);error.status=r.status;throw error;}return data;
}
class FormView {
 constructor(root,run,item,onDone,options={}){this.request=options.request||request;this.uploadMaterial=options.uploadMaterial;this.root=root;this.run=run;this.item=item;this.onDone=onDone;this.url=`/v1/platform/agent-runs/${encodeURIComponent(run.id)}/interactions/${encodeURIComponent(item.id)}/parameters`;this.busy=false;this.recorder=null;this.values={};this.inputs=[];this.chain=Promise.resolve();this.observer=new MutationObserver(()=>{if(!root.isConnected){this.cancelAutoSubmit();this.recorder?.dispose();this.recorder=null;this.observer.disconnect();document.removeEventListener('visibilitychange',this.visibilityChanged);window.removeEventListener('pagehide',this.pageLeaving);window.removeEventListener('aaat:setup-return',this.setupReturn);if(mounted.get(item.id)===root)mounted.delete(item.id);}});this.visibilityChanged=()=>{if(document.hidden)this.cancelAutoSubmit();};document.addEventListener('visibilitychange',this.visibilityChanged);this.pageLeaving=()=>this.cancelAutoSubmit();window.addEventListener('pagehide',this.pageLeaving);this.observer.observe(document.body,{childList:true,subtree:true});this.setupReturn=event=>{if(event.detail?.interactionId===this.item.id)this.refreshForm().catch(error=>this.error(error));};window.addEventListener('aaat:setup-return',this.setupReturn);this.init();}
 request(url,options){return request(url,options);}
 async init(){try{this.state=await this.request(this.url);this.values={...this.state.values};for(const f of this.state.descriptor.fields){if(!(f.key in this.values)&&f.default!==undefined)this.values[f.key]=f.default;}await this.loadIdentity();await this.loadMaterials();this.render();if(this.state.search_workflow){if(!this.values.preparation_ready)await this.perform(()=>this.prepareSearch());else if(this.values.preparation_id)this.searchPreparation=await this.request(this.url+'/search/'+encodeURIComponent(this.values.preparation_id));}await this.resume();this.armAutoSubmit();}catch(e){this.error(e);}}
 error(e){this.cancelAutoSubmit();if(!this.errorNode){this.errorNode=document.createElement('p');this.root.append(this.errorNode);}this.errorNode.textContent=e.message;this.errorNode.setAttribute('role','alert');}
 button(text,action){const b=document.createElement('button');b.type='button';b.className='agent-interaction-button';b.textContent=text;b.onclick=()=>this.perform(action);this.inputs.push(b);return b;}
 async perform(action){this.cancelAutoSubmit();if(this.busy)return;this.busy=true;this.inputs.forEach(i=>i.disabled=true);try{this.errorNode.textContent='';await action();}catch(e){this.error(e);}finally{this.busy=false;this.inputs.forEach(i=>i.disabled=i.dataset?.persistentDisabled==='true');}}
 save(){this.cancelAutoSubmit();const values=JSON.parse(JSON.stringify(this.values));this.chain=this.chain.catch(()=>{}).then(async()=>{const d=await this.request(this.url,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:this.state.revision,values})});this.state.revision=d.revision;for(const key of ['required_fields','missing','invalid'])if(key in d)this.state[key]=d[key];this.updateRequiredPresentation?.();});return this.chain;}
 requiredKeys(){return this.state.required_fields||this.state.descriptor.schema.required||[];}
 emptyValue(value){return value==null||(typeof value==='string'&&!value.trim())||(Array.isArray(value)&&!value.length)||(typeof value==='object'&&!Array.isArray(value)&&!Object.keys(value).length);}
 updateRequiredPresentation(){
  if(!this.form)return;const required=new Set(this.requiredKeys());
  for(const group of this.form.querySelectorAll('[data-parameter-key]')){
   const key=group.dataset.parameterKey,needed=required.has(key);let value=this.values[key];
   const control=group.querySelector('.agent-interaction-input');
   if(control&&!['json','asset'].includes(group.dataset.parameterType)&&control.tagName!=='SELECT'&&control.type!=='checkbox')value=control.value;
   group.dataset.emptyRequired=String(needed&&this.emptyValue(value));
   const star=group.querySelector('.agent-parameter-required');if(star)star.hidden=!needed;
   for(const input of group.querySelectorAll('input,select,textarea'))input.setAttribute('aria-required',String(needed));
  }
 }
 cancelAutoSubmit(){this.autoCancelled=true;clearTimeout(this.autoTimer);this.autoTimer=null;if(this.countdown)this.countdown.hidden=true;if(this.countdownCancel)this.countdownCancel.hidden=true;}
 autoSubmitReady(){
  const state=this.state,schema=state.descriptor.schema;
  if(!state.configure_only||state.auto_submit_allowed===false||state.waiting_app||state.configuration_required||state.search_workflow||this.setupRoot||this.recorder||this.busy)return false;
  if((schema.allOf||schema.if||schema.dependentRequired||schema.dependentSchemas)&&!Array.isArray(state.required_fields))return false;
  if((state.missing||[]).length||(state.invalid||[]).length||this.requiredKeys().some(key=>this.emptyValue(this.values[key])))return false;
  // A required affirmative declaration is an explicit human confirmation.
  if(this.requiredKeys().some(key=>{const spec=schema.properties?.[key]||{};return spec.const===true||(spec.enum?.length===1&&spec.enum[0]===true);}))return false;
  return !!this.submitButton&&!this.submitButton.disabled;
 }
 armAutoSubmit(){
  if(this.autoConsidered)return;this.autoConsidered=true;
  // One opportunity per interaction in this tab: reloads never restart a timer.
  try{const key='aaat:auto-submit:'+this.item.id;if(sessionStorage.getItem(key))return;sessionStorage.setItem(key,'seen');}catch(_){return;}
  if(this.autoCancelled||!this.root.isConnected||document.hidden||!this.autoSubmitReady())return;
  this.autoDeadline=Date.now()+60000;this.tickAutoSubmit();
 }
 tickAutoSubmit(){
  if(this.autoCancelled||!this.root.isConnected||document.hidden||!this.autoSubmitReady()){this.cancelAutoSubmit();return;}
  const seconds=Math.max(0,Math.ceil((this.autoDeadline-Date.now())/1000));
  this.countdown.hidden=false;this.countdownCancel.hidden=false;
  this.countdown.textContent=label(' · '+seconds+' 秒后自动提交',' · Auto-submit in '+seconds+'s');
  if(!seconds){this.cancelAutoSubmit();this.form.requestSubmit(this.submitButton);return;}
  clearTimeout(this.autoTimer);this.autoTimer=setTimeout(()=>this.tickAutoSubmit(),1000);
 }
 records(group,field){
  const columns=field.columns||[],rows=Array.isArray(this.values[field.key])?this.values[field.key]:[];
  const table=document.createElement('table');table.className='agent-records-table';const colgroup=document.createElement('colgroup');for(const column of columns){const col=document.createElement('col');col.dataset.type=column.type;colgroup.append(col);}const actionCol=document.createElement('col');actionCol.dataset.type='action';colgroup.append(actionCol);table.append(colgroup);const head=document.createElement('tr');
  for(const column of columns){const cell=document.createElement('th');cell.textContent=ownerText(column.label,column.key);head.append(cell);}head.append(document.createElement('th'));table.append(head);
  rows.forEach((row,index)=>{const line=document.createElement('tr');
   for(const column of columns){const cell=document.createElement('td');let input;
    if(column.type==='select'){input=document.createElement('select');for(const option of column.options||[]){const opt=document.createElement('option');opt.value=option.value;opt.textContent=ownerText(option.label,String(option.value));input.append(opt);}if(!(column.options||[]).some(o=>o.value===row[column.key])){const opt=document.createElement('option');opt.value=row[column.key]||'';opt.textContent=row[column.key]||label('请选择','Choose');input.prepend(opt);}}
    else{input=document.createElement('input');input.type=column.type==='number'?'number':'text';if(column.minimum!==undefined)input.min=column.minimum;if(column.maximum!==undefined)input.max=column.maximum;if(column.type==='number')input.step='1';}
    input.className='agent-interaction-input';input.style.cssText='width:100%;min-width:0';input.setAttribute('aria-label',ownerText(column.label,column.key)+' '+(index+1));input.required=true;input.value=row[column.key]??'';input.onchange=()=>{rows[index]={...rows[index],[column.key]:column.type==='number'?Number(input.value):input.value};this.values[field.key]=rows;this.save().catch(e=>this.error(e));};this.inputs.push(input);cell.append(input);line.append(cell);
   }
   const action=document.createElement('td');action.append(this.button(label('移除','Remove'),async()=>{this.values[field.key]=rows.filter((_,i)=>i!==index);await this.save();this.render();}));line.append(action);table.append(line);
  });const wrap=document.createElement('div');wrap.className='agent-records-wrap';wrap.append(table);group.append(wrap);
  if(!rows.length){const empty=document.createElement('p');empty.textContent=label('请选择项目并填写数量','Choose items and quantities');group.append(empty);}
  const add=this.button(label('添加项目','Add item'),async()=>{const row={};for(const column of columns){const option=(column.options||[]).find(o=>column!==columns[0]||!rows.some(r=>r[column.key]===o.value));row[column.key]=column.type==='select'?(option?.value||''):column.type==='number'?(column.minimum??1):'';}this.values[field.key]=[...rows,row];await this.save();this.render();});
  add.disabled=rows.length>=(field.maxItems||20);if(add.disabled)add.dataset.persistentDisabled='true';group.append(add);
 }
 optionPreview(group,input,options){
  const preview=document.createElement('div');preview.style.cssText='display:flex;gap:10px;align-items:flex-start;margin-top:10px;font-size:13px;overflow-wrap:anywhere';group.append(preview);
  const safe=value=>{try{const url=new URL(value);return url.protocol==='https:'&&!url.username&&!url.password?url.href:'';}catch(_){return '';}};
  const update=()=>{preview.replaceChildren();const selected=options.find(o=>o.value===input.value);if(!selected)return;
   const src=safe(selected.image);if(src){const image=document.createElement('img');image.src=src;image.alt=ownerText(selected.label,'');image.referrerPolicy='no-referrer';image.style.cssText='width:44px;height:44px;border-radius:50%;object-fit:cover';preview.append(image);}
   const info=document.createElement('div');if(selected.description){const text=document.createElement('p');text.style.margin='0';text.textContent=ownerText(selected.description);info.append(text);}
   const href=safe(selected.url);if(href){const link=document.createElement('a');link.href=href;link.target='_blank';link.rel='noopener noreferrer';link.textContent=href;info.append(link);}preview.append(info);
  };input.addEventListener('change',update);update();
 }
 async loadModels(){const latest=await this.request(this.url);this.state=latest;await this.loadMaterials();this.render();}
 async provision(result){await this.loadModels();if(result?.status==='ready'&&result.session){await window.AI2AppsCapabilities.acknowledge(result.session.id,{appId:this.state.install.appId});}}
 async resume(){
  if(!this.state.install||typeof window.AI2AppsCapabilities?.runSession!=='function')return;
  const result=await this.request(this.url+'/setup/session');
  if(result.session)void this.showSetup(result.session).catch(error=>{if(error.code!=='view_detached')this.error(error);});
 }
 async showSetup(session){
  if(this.setupRoot?.isConnected)return;
  const root=document.createElement('div');this.setupRoot=root;this.root.append(root);
  const send=async(path,options={})=>{
   const action=path.match(/\/provisioning\/sessions\/[^/]+(?:\/(.*))?$/)?.[1];
   const result=await this.request(this.url+'/setup/session'+(action?'/'+action:''),{...options,headers:{'Content-Type':'application/json'}});
   return action==='select-profile'?(result.session||result):action?result:result.session;
  };
  try{
   const completed=await window.AI2AppsCapabilities.runSession(session,this.state.install.appId,{root,request:send,readOnly:!!window.AI2APPS_MOBILE_SURFACE});
   if(completed.session&&!window.AI2APPS_MOBILE_SURFACE)await send('/provisioning/sessions/'+session.id+'/acknowledge-return',{method:'POST',body:'{}'});
   await this.refreshForm();
  }finally{root.remove();this.setupRoot=null;}
 }
 async install(){
  await this.save();
  if(window.AI2APPS_MOBILE_SURFACE){this.errorNode.textContent=label('请到 Desktop 配置。参数和附件已保存，已有配置进度会显示在这里。','Configure on Desktop. Parameters and attachments are saved; existing setup progress is shown here.');await this.resume();return;}
  if(!window.AI2AppsCapabilities)throw Error(label('配置组件尚未加载，请刷新页面','Setup component is unavailable; refresh the page'));
  const result=await this.request(this.url+'/setup/session',{method:'POST'});
  if(result.session)void this.showSetup(result.session).catch(error=>{if(error.code!=='view_detached')this.error(error);});
  else if(result.status==='ready')await this.refreshForm();
  else throw Error((result.reasons||[]).join('; ')||'Setup unavailable');
 }
 async audio(file){const data=new FormData();data.append('file',file,file.name||'recording.webm');const result=await this.request(this.url+'/audio',{method:'POST',body:data});this.values.audio=result.asset.id;await this.save();this.assetName=result.asset.name;this.render();}
 async drop(event){event.preventDefault();if(this.busy)return;await this.perform(async()=>{const file=event.dataTransfer?.files?.[0];if(file){await this.audio(file);return;}const id=event.dataTransfer?.getData('application/x-ai2apps-gallery-asset');if(!id)return;const r=await this.request(this.url+'/gallery',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({asset_id:id})});this.values.audio=r.asset.id;await this.save();this.assetName=r.asset.name;this.render();});}

 async refreshForm(){this.state=await this.request(this.url);this.values={...this.state.values};for(const f of this.state.descriptor.fields){if(!(f.key in this.values)&&f.default!==undefined)this.values[f.key]=f.default;}await this.loadIdentity();await this.loadMaterials();this.render();}
 async prepareSearch(){
  delete this.values.confirmation_id;
  this.values.mode=this.values.mode||'preferred';this.values.profile=this.values.profile||'default';this.values.limit=this.values.limit||5;
  let prepared;
  if(this.values.preparation_id)prepared=await this.request(this.url+'/search/'+encodeURIComponent(this.values.preparation_id));
  else{await this.save();prepared=await this.request(this.url+'/search/prepare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:this.state.revision,values:this.values})});this.values.preparation_id=prepared.id;this.values.preparation_ready=false;await this.save();}
  const deadline=Date.now()+180000;
  while(prepared.status!=='completed'){
   if(['failed','cancelled','interrupted'].includes(prepared.status))throw Error(prepared.message||prepared.status);
   if(Date.now()>deadline)throw Error(label('搜索准备超时，可重试或重新打开表单','Search preparation timed out; retry or reopen the form'));
   this.errorNode.textContent=label('正在优化搜索词并推荐来源…','Optimizing search terms and recommending sources…');
   await new Promise(resolve=>setTimeout(resolve,800));if(!this.root.isConnected)return;
   prepared=await this.request(this.url+'/search/'+encodeURIComponent(prepared.id));
  }
  this.searchPreparation=prepared;this.values.query=prepared.query;this.values.limit=prepared.limit;
  this.values.x_sort=prepared.x_sort;this.values.xiaohongshu_sort=prepared.xiaohongshu_sort;
  this.values.sources=this.values.mode==='fast'?[prepared.fast_source]:this.values.mode==='custom'?(this.values.sources||[]):prepared.sources;
  this.values.cloud_price_version=prepared.cloud_offer?.price_version||'';this.values.cloud_max_points=prepared.cloud_offer?.points_per_search||'';this.values.cloud_consent=false;
  this.values.preparation_ready=true;await this.save();this.render();
 }
 async searchModeChanged(mode){const previous=this.values.mode;if(previous!=='fast')this.searchSourceDraft=[...(this.values.sources||[])];this.values.mode=mode;if(mode==='fast')this.values.sources=[this.state.fast_source];else if(mode==='preferred'&&this.searchPreparation)this.values.sources=[...this.searchPreparation.sources];else if(previous==='fast')this.values.sources=this.searchSourceDraft||[];await this.save();this.render();}

 async switchProvider(provider){await this.save();await this.request(this.url+'/switch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:this.state.revision,provider})});await this.refreshForm();}
 async continueInApp(){if(!window.ai2appsShell?.openHandoff)throw Error(label('\u8bf7\u5728 AI2Apps Shell \u4e2d\u6253\u5f00','Open this form in AI2Apps Shell'));if(!this.state.waiting_app){await this.save();await this.request(this.url+'/handoff',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:this.state.revision,values:this.values})});this.state.waiting_app=true;this.render();}await window.ai2appsShell.openHandoff(this.run.id,this.item.id,false);}
 async completeInApp(){await this.request(this.url+'/handoff/complete',{method:'POST'});await this.onDone();}
 renderAlternatives(form){const choices=this.state.alternatives||[];if(this.state.waiting_app||choices.length<2)return;const details=document.createElement('details');details.style.cssText='margin:12px 0;padding:10px;border:1px solid var(--border-normal,#ddd);border-radius:10px';const summary=document.createElement('summary');summary.textContent=label('\u66f4\u6362 Tool / App / Mini-App','Choose another Tool / App / Mini-App');details.append(summary);for(const choice of choices){const row=document.createElement('div');row.style.cssText='margin-top:10px;padding-top:8px;border-top:1px solid var(--border-normal,#ddd)';const name=document.createElement('strong');const declaredName=choice.display_name;name.textContent=(typeof declaredName==='object'&&declaredName?(declaredName[zh()?'zh':'en']||declaredName.en):declaredName)||(choice.mini_app_id||choice.app_id||choice.provider);name.title=choice.capability+' / '+choice.provider;const mini=(this.availableMinis||[]).find(m=>m.id===choice.mini_app_id);const iconKey=String(mini?.icon||'app-window').replace(/(^|-)([a-z])/g,(_,dash,c)=>c.toUpperCase());const icon=window.lucide?.icons?.[iconKey]||window.lucide?.icons?.AppWindow;if(icon&&window.lucide?.createElement){const svg=window.lucide.createElement(icon,{width:20,height:20});svg.style.verticalAlign='middle';row.append(svg);}const description=document.createElement('p');description.textContent=typeof choice.description==='object'?(choice.description[zh()?'zh':'en']||choice.description.en||''):(choice.description||'');description.style.cssText='font-size:12px;overflow-wrap:anywhere';const current=choice.provider===this.state.descriptor.provider;const button=this.button(current?label('\u5f53\u524d\u9009\u9879','Current choice'):label('\u5207\u6362\u5230\u6b64\u9009\u9879','Use this option'),()=>this.switchProvider(choice.provider));button.disabled=current;if(current)button.dataset.persistentDisabled='true';row.append(name,description,button);details.append(row);}form.append(details);}
 async loadIdentity(){
  const d=this.state.descriptor;this.identity=[{kind:'Tool',id:d.capability,name:d.capability},{kind:'Agent',id:this.run.agent_key,name:this.run.agent_display_name||this.run.agent_key||'Agent'}];
  try{const apps=await this.request('/admin/api/shell/apps');const app=(apps.items||[]).find(a=>(a.app_key||a.id||a.app_id)===d.app_id);this.identity.push({kind:'App',id:d.app_id,name:app?.display_name||app?.name||d.app_id,icon:app?.icon||app?.navigation?.icon||'app-window'});}catch(_){if(d.app_id)this.identity.push({kind:'App',id:d.app_id,name:d.app_id,icon:'app-window'});}
  if(d.mini_app_id){let mini;try{const data=await this.request('/v1/platform/studios/'+encodeURIComponent(d.app_id)+'/mini-apps');this.availableMinis=data.items||[];mini=this.availableMinis.find(m=>m.id===d.mini_app_id);}catch(_){}this.identity.push({kind:'Mini-App',id:d.mini_app_id,name:d.display_name||mini?.displayName||mini?.name||mini?.title||d.mini_app_id,icon:mini?.icon||'app-window'});}
 }
 renderExplanation(form){const text=document.createElement('p');text.style.cssText='margin:0 0 12px;line-height:1.6';const display=owner=>typeof owner.name==='object'?(owner.name[zh()?'zh':'en']||owner.name.en||owner.id):owner.name;const owners=(this.identity||[]).filter(owner=>owner.kind==='App'||owner.kind==='Mini-App');const target=owners.map(owner=>display(owner)).join(' / ')||this.state.descriptor.capability;const fields=[...(this.state.missing||[]),...(this.state.invalid||[]).map(item=>item.field).filter(Boolean)];const names=[...new Set(fields)].map(key=>ownerText(this.state.descriptor.fields.find(field=>field.key===key)?.label,key));text.textContent=label('接下来将调用「'+target+'」。','Next, I will use '+target+'. ')+(names.length?label('请补充或修正：'+names.join('、')+'；其余参数已预填，可一并调整。','Please complete or correct '+names.join(', ')+'. Other values are prefilled and editable. '):label('调用参数已预填，请检查并按需调整。','The call parameters are prefilled; please review and adjust them. '))+label('提交后才会继续调用；取消则不会执行。','The call continues after submission; cancelling will not execute it.');form.append(text);}
 renderIdentity(form){const header=document.createElement('div');header.style.cssText='display:flex;flex-wrap:wrap;gap:8px 16px;margin-bottom:16px';for(const owner of this.identity||[]){const row=document.createElement('span');row.style.cssText='display:inline-flex;align-items:center;gap:6px';row.title=owner.id||'';if(owner.icon){const key=String(owner.icon).replace(/(^|-)([a-z])/g,(_,dash,c)=>c.toUpperCase());const icon=window.lucide?.icons?.[key]||window.lucide?.icons?.AppWindow;if(icon&&window.lucide?.createElement)row.append(window.lucide.createElement(icon,{width:20,height:20,'stroke-width':1.8}));}const text=document.createElement('span');const name=typeof owner.name==='object'?(owner.name[zh()?'zh':'en']||owner.name.en||owner.id):owner.name;text.textContent=({Tool:label('工具','Tool'),Agent:label('智能体','Agent'),App:label('应用','App'),'Mini-App':label('小应用','Mini-App')}[owner.kind]||owner.kind)+' · '+name;row.append(text);header.append(row);}form.append(header);}
 async loadMaterials(){this.materials=this.materials||{};await Promise.all(this.state.descriptor.fields.filter(f=>f.type==='asset'&&f.storage==='artifact').map(async f=>{const data=await this.request(this.url+'/materials?field='+encodeURIComponent(f.key));this.materials[f.key]=data.items||[];}));}
 assetIds(f){const value=this.values[f.key];return f.multiple?(Array.isArray(value)?value:[]):(typeof value==='string'&&value?[value]:[]);}
 async addMaterials(f,assets){const ids=f.multiple?[...new Set([...this.assetIds(f),...assets.map(a=>a.id)])]:assets.map(a=>a.id);if(ids.length>(f.multiple?f.maxItems||20:1))throw Error(label('素材数量超过此字段限制','Too many materials for this field'));this.values[f.key]=f.multiple?ids:ids[0];await this.save();await this.loadMaterials();this.render();}
 async importMaterials(f,{files=[],galleryIds=[]}){const count=files.length+galleryIds.length;if(!count)return;if(count>(f.multiple?(f.maxItems||20)-this.assetIds(f).length:1))throw Error(label('素材数量超过此字段限制','Too many materials for this field'));const assets=[];for(const file of files){if(window.AI2APPS_MOBILE_SURFACE&&f.references){if(!this.uploadMaterial)throw Error(label('请先用 Chat 附件按钮上传素材，再在此表单选择','Upload with the Chat attachment button, then select it in this form'));assets.push(await this.uploadMaterial(file,this.run,f));continue;}let path='';try{path=String(file.mozAI2AppsFullPath||'');}catch(_){}if(path&&f.references){assets.push((await this.request(this.url+'/materials/reference?field='+encodeURIComponent(f.key),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_path:path,filename:file.name,media_type:file.type})})).asset);}else{const data=new FormData();data.append('file',file,file.name);assets.push((await this.request(this.url+'/materials/upload?field='+encodeURIComponent(f.key),{method:'POST',body:data})).asset);}}for(const asset_id of galleryIds){assets.push((await this.request(this.url+'/materials/gallery',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({field:f.key,asset_id})})).asset);}await this.addMaterials(f,assets);}
 materialPreview(asset){const card=document.createElement('div');const type=asset.media_type||'';const width=type.startsWith('audio/')||type.startsWith('video/')?180:132;card.style.cssText=`display:flex;flex-direction:column;align-items:stretch;gap:6px;min-width:0;width:${width}px;max-width:100%`;if(asset.preview_url&&!(window.AI2APPS_MOBILE_SURFACE&&asset.storage==='reference')&&(type.startsWith('image/')||type.startsWith('audio/')||type.startsWith('video/'))){const media=document.createElement(type.startsWith('image/')?'img':type.startsWith('audio/')?'audio':'video');media.src=asset.preview_url;if(media.tagName==='IMG'){media.alt=asset.name||'';media.loading='lazy';media.style.cssText='width:100%;height:108px;object-fit:contain;border-radius:8px;background:var(--bg-secondary,#eee)';}else{media.controls=true;media.preload='metadata';media.style.cssText='width:100%;max-width:100%';}card.append(media);}const name=document.createElement('span');name.textContent=asset.name||asset.id;name.tabIndex=0;name.style.cssText='display:block;width:100%;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';const tip=document.createElement('span');tip.textContent=name.textContent;tip.setAttribute('role','tooltip');tip.setAttribute('popover','manual');tip.hidden=true;tip.style.cssText='position:fixed;inset:auto;margin:0;box-sizing:border-box;max-width:calc(100vw - 16px);width:max-content;padding:7px 10px;border:0;border-radius:6px;background:#111;color:#fff;font-size:12px;line-height:1.5;white-space:normal;overflow-wrap:anywhere;text-align:left;box-shadow:0 3px 12px #0003;pointer-events:none;z-index:2147483647';const hide=()=>{if(tip.hidePopover&&tip.matches(':popover-open'))tip.hidePopover();tip.hidden=true;};const show=()=>{tip.hidden=false;if(tip.showPopover)tip.showPopover();const anchor=name.getBoundingClientRect(),bounds=tip.getBoundingClientRect();tip.style.left=Math.max(8,Math.min(anchor.left,window.innerWidth-bounds.width-8))+'px';tip.style.top=Math.max(8,anchor.top-bounds.height-6)+'px';};name.onmouseenter=show;name.onmouseleave=hide;name.onfocus=show;name.onblur=hide;name.onkeydown=e=>{if(e.key==='Escape')hide();};card.append(name,tip);return card;}
 artifactSlot(group,f){const ids=this.assetIds(f);group.setAttribute('role','group');group.setAttribute('aria-label',ownerText(f.label,f.key));group.style.cssText='margin:12px 0;padding:12px;border:1px dashed var(--text-tertiary,#9ca3af);border-radius:12px';const hint=document.createElement('p');hint.textContent=(f.multiple?label('多素材','Multiple materials')+` (${ids.length}/${f.maxItems||20})`+(f.minItems?label('，至少 '+f.minItems+' 个','; minimum '+f.minItems):''):label('单素材','Single material'))+' · '+label('拖入文件或 Gallery 素材','Drop files or Gallery materials');group.append(hint);group.ondragover=e=>{e.preventDefault();if(e.dataTransfer)e.dataTransfer.dropEffect='copy';};group.ondrop=e=>{e.preventDefault();e.stopPropagation();if(!this.busy)this.perform(()=>this.importMaterials(f,{files:[...(e.dataTransfer?.files||[])],galleryIds:window.AI2AppsGalleryPicker.droppedAssetIds(e.dataTransfer)}));};
 const current=document.createElement('div');current.style.cssText='display:flex;flex-wrap:wrap;gap:12px;margin:8px 0';for(const [index,id] of ids.entries()){const asset=(this.materials[f.key]||[]).find(a=>a.id===id)||{id,name:label('素材不可用：','Unavailable material: ')+id};const item=document.createElement('div');item.style.cssText='padding:8px;border:1px solid var(--border-color,#ddd);border-radius:10px;max-width:100%';item.append(this.materialPreview(asset));item.append(this.button(label('移除','Remove'),async()=>{const remaining=this.assetIds(f).filter(x=>x!==id);if(f.multiple)this.values[f.key]=remaining;else delete this.values[f.key];await this.save();this.render();}));if(f.multiple&&index>0)item.append(this.button(label('前移','Move earlier'),async()=>{const next=[...this.assetIds(f)];[next[index-1],next[index]]=[next[index],next[index-1]];this.values[f.key]=next;await this.save();this.render();}));current.append(item);}group.append(current);
 const file=document.createElement('input');file.type='file';file.accept=f.accept||'';file.multiple=!!f.multiple;file.hidden=true;file.onchange=()=>this.perform(()=>this.importMaterials(f,{files:[...file.files]}));this.inputs.push(file);group.append(file,this.button(label('上传素材','Upload material'),()=>file.click()),this.button(label('从素材库选择','Choose from Gallery'),async()=>{const selected=await window.AI2AppsGalleryPicker.open({multiple:!!f.multiple,maxSelection:f.multiple?Math.max(1,(f.maxItems||20)-ids.length):1,kind:f.accept?.startsWith('image/')?'image':undefined});await this.importMaterials(f,{galleryIds:selected.map(a=>a.id)});}));
 const choices=document.createElement('details');const summary=document.createElement('summary');summary.textContent=label('选择本对话素材','Choose materials from this conversation');choices.append(summary);const grid=document.createElement('div');grid.style.cssText='display:flex;gap:8px;flex-wrap:wrap;padding-top:8px';for(const asset of this.materials[f.key]||[]){if(ids.includes(asset.id))continue;const b=document.createElement('button');b.type='button';b.style.cssText='border:1px solid var(--border-color,#ddd);border-radius:8px;padding:8px;max-width:240px';b.append(this.materialPreview(asset));b.onclick=()=>this.perform(()=>this.addMaterials(f,[asset]));this.inputs.push(b);grid.append(b);}choices.append(grid);group.append(choices);
 }
 async record(){if(this.recorder){const recorder=this.recorder;this.recorder=null;let audio;try{audio=await recorder.stop();}finally{recorder.dispose();}await this.audio(new File([audio.body],audio.name,{type:audio.body.type}));return;}this.recorder=new window.AI2AppsStudioAudioRecorder();try{let timer;try{await Promise.race([this.recorder.start(600),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error(label('麦克风权限请求超时，请检查系统与浏览器权限','Microphone permission timed out; check system and browser permissions'))),15000);})]);}finally{clearTimeout(timer);}this.render();}catch(e){this.recorder?.dispose();this.recorder=null;throw e;}}
 render(){if(this.state.prompt_labels){this.item.ui_hints={...this.item.ui_hints,prompt_labels:this.state.prompt_labels};const heading=this.root.closest?.('.agent-interaction-card,.mchat-agent-interaction')?.querySelector('[data-parameter-prompt]');if(heading)heading.textContent=ownerText(this.state.prompt_labels);}this.root.replaceChildren();this.inputs=[];const form=document.createElement('form');form.className='agent-parameter-form';this.form=form;for(const event of ['input','change','focusin','pointerdown'])form.addEventListener(event,e=>{if(e.target.closest('input,select,textarea,button,[contenteditable]'))this.cancelAutoSubmit();this.updateRequiredPresentation();},true);form.onsubmit=e=>{e.preventDefault();this.cancelAutoSubmit();this.perform(async()=>{if(this.state.search_workflow&&!this.values.preparation_ready)throw Error(label('请先完成搜索准备','Complete search preparation first'));if(this.recorder)throw Error(label('请先停止录音','Stop recording first'));await this.save();await this.request(this.url+'/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:this.state.revision,values:this.values})});await this.onDone();});};this.root.append(form);const title=document.createElement('h3');title.className='agent-parameter-title';title.textContent=ownerText(this.state.prompt_labels,(this.state.missing?.length||this.state.invalid?.length)?label('补充调用参数','Complete call parameters'):label('确认调用参数','Confirm call parameters'));this.countdown=document.createElement('span');this.countdown.className='agent-parameter-countdown';this.countdown.hidden=true;this.countdownCancel=document.createElement('button');this.countdownCancel.type='button';this.countdownCancel.className='agent-parameter-countdown-cancel';this.countdownCancel.textContent=label('取消自动提交','Cancel auto-submit');this.countdownCancel.hidden=true;this.countdownCancel.onclick=()=>this.cancelAutoSubmit();title.append(this.countdown,this.countdownCancel);form.append(title);if(this.setupRoot)this.root.append(this.setupRoot);for(const warning of this.state.warnings||[]){const note=document.createElement('p');note.textContent=ownerText(warning);form.append(note);}if(!this.state.waiting_app)this.renderExplanation(form);this.renderIdentity(form);this.renderAlternatives(form);
 if(this.state.waiting_app){const waiting=document.createElement('p');waiting.textContent=label('\u7b49\u5f85 App / Mini-App \u5b8c\u6210\uff0c\u7136\u540e\u53d6\u56de\u7ed3\u679c\u8fd4\u56de\u539f Agent\u3002','Waiting for the App / Mini-App. Retrieve the result when finished to resume the original Agent.');form.append(waiting);this.errorNode=document.createElement('p');this.errorNode.setAttribute('role','alert');form.append(this.errorNode,this.button(label('\u56de\u5230 App','Return to App'),()=>this.continueInApp()),this.button(label('\u5df2\u5b8c\u6210\uff0c\u53d6\u56de\u7ed3\u679c','Completed - retrieve result'),()=>this.completeInApp()));return;}
 if(this.state.search_workflow){const hint=document.createElement('p');hint.textContent=label('搜索前可修改搜索词与来源；点击搜索后才执行。','Edit search terms and sources; execution starts only when you click Search.')+(this.searchPreparation?' '+this.searchPreparation.reason:'');form.append(hint);form.append(this.button(label('重新优化搜索词','Optimize search terms again'),async()=>{delete this.values.preparation_id;this.values.preparation_ready=false;await this.prepareSearch();}));}
 const fields=document.createElement('div');fields.className='agent-parameter-fields';form.append(fields);
 for(const f of this.state.descriptor.fields){if(this.state.search_workflow&&f.key==='sources'&&this.values.mode==='fast')continue;const group=document.createElement('div');group.className='agent-parameter-field';group.dataset.parameterKey=f.key;group.dataset.parameterType=f.type;group.dataset.width=['compact','medium','full'].includes(f.width)?f.width:(['json','asset','multiselect'].includes(f.type)?'full':f.type==='number'||f.type==='boolean'?'compact':'medium');const title=document.createElement('label');title.style.display='block';title.textContent=ownerText(f.label,f.key);const star=document.createElement('span');star.className='agent-parameter-required';star.setAttribute('aria-hidden','true');star.hidden=!this.requiredKeys().includes(f.key);title.append(star);group.append(title);fields.append(group);
 if(f.type==='multiselect'){const options=document.createElement('div');options.className='agent-parameter-options';options.style.cssText='display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:8px';for(const option of f.options||[]){const row=document.createElement('label'),box=document.createElement('input');box.type='checkbox';box.style.cssText='width:16px;height:16px;margin:0;flex:0 0 16px';box.checked=(this.values[f.key]||[]).includes(option.value);box.onchange=()=>{const selected=new Set(this.values[f.key]||[]);box.checked?selected.add(option.value):selected.delete(option.value);this.values[f.key]=[...selected];this.save().catch(e=>this.error(e));};this.inputs.push(box);row.append(box,document.createTextNode(ownerText(option.label,String(option.value))));row.style.cssText='display:inline-flex;align-items:center;gap:6px;white-space:nowrap;cursor:pointer';options.append(row);}group.append(options);continue;}
 if(f.type==='boolean'){const box=document.createElement('input');box.type='checkbox';box.id=`parameter-${this.item.id}-${f.key}`;box.style.cssText='width:16px;height:16px;margin:0;flex:0 0 16px';box.checked=!!this.values[f.key];box.onchange=()=>{this.values[f.key]=box.checked;this.save().catch(e=>this.error(e));};title.htmlFor=box.id;title.style.cssText='display:inline-flex;align-items:center;gap:8px;cursor:pointer';title.prepend(box);this.inputs.push(box);continue;}
 if(f.type==='json'&&f.presentation==='records'){this.records(group,f);continue;}
 if(f.type==='asset'&&f.storage==='artifact'){this.artifactSlot(group,f);continue;}
 if(f.type==='asset'){group.ondragover=e=>e.preventDefault();group.ondrop=e=>this.drop(e);group.style.border='1px dashed currentColor';group.style.padding='12px';const info=document.createElement('p');info.textContent=this.values[f.key]?(this.assetName||this.values[f.key]):label('拖入音频或从素材库拖入','Drop audio from files or Gallery');group.append(info);const input=document.createElement('input');input.type='file';input.accept=f.accept;input.onchange=()=>{if(input.files[0])this.perform(()=>this.audio(input.files[0]));};this.inputs.push(input);group.append(input,this.button(this.recorder?label('停止录音','Stop recording'):label('录音','Record'),()=>this.record()));continue;}
 let input;if(f.type==='select'||f.type==='model'){input=document.createElement('select');const options=f.type==='model'?[{value:'',label:label('选择模型','Select model')},...this.state.models.filter(m=>m.ready).map(m=>({value:m.id,label:m.label}))]:f.options;for(const o of options){const opt=document.createElement('option');opt.value=o.value;opt.textContent=ownerText(o.label,String(o.value));input.append(opt);}}else{input=document.createElement('input');input.type=f.type==='boolean'?'checkbox':f.type==='number'?'number':'text';if(f.type==='number')input.step=this.state.descriptor.schema?.properties?.[f.key]?.type==='integer'?'1':'any';}
 input.id=`parameter-${this.item.id}-${f.key}`;title.htmlFor=input.id;input.className='agent-interaction-input';if(input.tagName==='SELECT' && this.values[f.key] && !Array.from(input.options).some(o=>o.value===this.values[f.key])){const invalid=document.createElement('option');invalid.value=this.values[f.key];invalid.textContent=this.values[f.key]+' — '+label('当前模型不支持，请重选','Unsupported for current model; select again');input.append(invalid);}input.value=f.type==='json'?JSON.stringify(this.values[f.key]??null):this.values[f.key]??'';if(f.type==='boolean')input.checked=!!this.values[f.key];input.onchange=()=>{if(this.state.search_workflow&&f.key==='mode'){void this.perform(()=>this.searchModeChanged(input.value));return;}if(this.state.search_workflow&&f.key==='profile'){delete this.values.preparation_id;this.values.preparation_ready=false;}try{this.values[f.key]=f.type==='json'?JSON.parse(input.value):f.type==='boolean'?input.checked:f.type==='number'?Number(input.value):input.value;if(input.value===''&&['model','number'].includes(f.type))delete this.values[f.key];this.save().then(()=>{if(f.type==='model')return this.loadModels();}).catch(e=>this.error(e));}catch(e){this.error(e);}};this.inputs.push(input);group.append(input);if(f.type==='select'&&(f.options||[]).some(o=>o.description||o.url||o.image))this.optionPreview(group,input,f.options);if(f.type==='model'){if(!this.state.models.some(m=>m.ready)){const note=document.createElement('p');note.textContent=label('等待模型配置：当前没有可用模型。参数和附件会保留。','Waiting for model setup: no ready model. Parameters and attachments are preserved.');group.append(note);}if(this.state.install){group.append(this.button(window.AI2APPS_MOBILE_SURFACE?label('查看 Desktop 配置说明','Desktop setup instructions'):label('配置所需能力','Set up required capability'),()=>this.install()),this.button(label('重新检查','Recheck'),()=>this.refreshForm()));}}}
 if(this.state.configure_only){const constraints=document.createElement('pre');constraints.style.whiteSpace='pre-wrap';constraints.textContent=JSON.stringify(this.state.descriptor.constraints,null,2);form.append(constraints);}this.errorNode=document.createElement('p');this.errorNode.className='agent-parameter-error';this.errorNode.setAttribute('role','alert');form.append(this.errorNode);const actions=document.createElement('div');actions.className='agent-parameter-actions';form.append(actions);const submit=document.createElement('button');submit.type='submit';submit.className='agent-interaction-button agent-interaction-button--primary';submit.textContent=ownerText(this.state.submit_label)||(this.state.configure_only?label('确认参数，返回 Agent','Confirm parameters and return to Agent'):label('提交','Submit'));if(this.state.configuration_required||this.state.descriptor.fields.some(f=>f.type==='model'&&(this.state.descriptor.schema?.required||[]).includes(f.key))&&!this.state.models.some(m=>m.ready)){submit.disabled=true;submit.dataset.persistentDisabled='true';}this.submitButton=submit;this.inputs.push(submit);actions.append(submit);if(this.state.install&&!this.state.descriptor.fields.some(f=>f.type==='model')){actions.append(this.button(window.AI2APPS_MOBILE_SURFACE?label('查看 Desktop 配置说明','Desktop setup instructions'):label('配置所需能力','Set up required capability'),()=>this.install()),this.button(label('重新检查','Recheck'),()=>this.refreshForm()));}if(this.state.can_continue_in_app)actions.append(this.button(label('\u5728 App \u4e2d\u7ee7\u7eed','Continue in App'),()=>this.continueInApp()));actions.append(this.button(label('取消','Cancel'),async()=>{this.recorder?.dispose();this.recorder=null;await this.request(this.url.replace('/parameters','/respond'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({response_id:'form-cancel:'+this.item.id,response:{status:'cancelled',result:{}}})});await this.onDone();}));this.updateRequiredPresentation();if(this.autoDeadline&&!this.autoCancelled)this.tickAutoSubmit();
 }
}
class ApprovalCountdown {
 constructor(root,run,item,approve){
  Object.assign(this,{root,run,item,approve});this.cancelled=false;
  this.status=document.createElement('span');this.status.className='agent-parameter-countdown';
  this.cancelButton=document.createElement('button');this.cancelButton.type='button';this.cancelButton.className='agent-parameter-countdown-cancel';this.cancelButton.textContent=label('取消自动批准','Cancel auto-approval');
  this.status.hidden=this.cancelButton.hidden=true;this.cancelButton.onclick=()=>this.cancel();
  const line=document.createElement('div');line.className='agent-approval-countdown';line.style.cssText='margin:6px 0;display:flex;align-items:center;flex-wrap:wrap';line.append(this.status,this.cancelButton);const heading=root.querySelector('[data-parameter-prompt]');if(heading)heading.after(line);else root.append(line);
  this.edit=()=>this.cancel();for(const event of ['pointerdown','focusin','keydown','input','change'])root.addEventListener(event,this.edit,true);
  this.visibility=()=>{if(document.hidden)this.cancel();};document.addEventListener('visibilitychange',this.visibility);
  this.leaving=()=>this.cancel();window.addEventListener('pagehide',this.leaving);
  this.observer=new MutationObserver(()=>{if(!root.isConnected)this.dispose();});this.observer.observe(document.body,{childList:true,subtree:true});
  queueMicrotask(()=>this.start());
 }
 eligible(){
  const {run,item}=this,properties=item.response_schema?.properties||{};
  if(item.kind!=='approval'||item.ui_hints?.control!=='approval'||item.ui_hints.auto_approve_seconds!==60||!item.request?.tool_name||item.status!=='pending'||!['waiting_input','waiting_capability'].includes(run.status))return false;
  if(!properties.decision?.enum?.includes('approve')||!properties.scope?.enum?.includes('once')||(item.response_schema.required||[]).some(key=>!['decision','scope'].includes(key)))return false;
  for(const value of [run.deadline_at,item.deadline_at])if(value&&(!Number.isFinite(Date.parse(value))||Date.parse(value)<=Date.now()))return false;
  return true;
 }
 visible(){const rect=this.root.getBoundingClientRect();return !document.hidden&&this.root.isConnected&&rect.width>0&&rect.height>0&&rect.bottom>0&&rect.top<window.innerHeight;}
 start(){
  try{const key='aaat:auto-approval:'+this.item.id;if(sessionStorage.getItem(key))return;sessionStorage.setItem(key,'seen');}catch(_){return;}
  if(this.cancelled||!this.eligible()||!this.visible())return;
  this.deadline=Date.now()+60000;this.tick();
 }
 sync(run,item){this.run=run;this.item=item;if(!this.eligible())this.cancel();}
 cancel(){this.cancelled=true;clearTimeout(this.timer);this.timer=null;this.status.hidden=this.cancelButton.hidden=true;}
 tick(){
  if(this.cancelled||!this.eligible()||!this.visible()){this.cancel();return;}
  const seconds=Math.max(0,Math.ceil((this.deadline-Date.now())/1000));
  this.status.textContent=label(seconds+' 秒后仅允许这一次',seconds+'s until Allow once');this.status.hidden=this.cancelButton.hidden=false;
  if(!seconds){this.cancel();Promise.resolve().then(()=>this.approve()).catch(error=>{const note=document.createElement('p');note.className='agent-parameter-error';note.setAttribute('role','alert');note.textContent=error.message;this.root.append(note);});return;}
  this.timer=setTimeout(()=>this.tick(),1000);
 }
 dispose(){this.cancel();this.observer.disconnect();document.removeEventListener('visibilitychange',this.visibility);window.removeEventListener('pagehide',this.leaving);for(const event of ['pointerdown','focusin','keydown','input','change'])this.root.removeEventListener(event,this.edit,true);if(approvalMounted.get(this.item.id)===this.root)approvalMounted.delete(this.item.id);}
}

window.AI2AppsParameterForms={mountApproval(root,run,item,approve){if(root._approvalCountdown){root._approvalCountdown.sync(run,item);return;}const existing=approvalMounted.get(item.id);if(existing?.isConnected)return;approvalMounted.set(item.id,root);root._approvalCountdown=new ApprovalCountdown(root,run,item,approve);},release(id){const root=mounted.get(id);const view=root?._parameterForm;if(view){view.cancelAutoSubmit();view.recorder?.dispose();view.observer?.disconnect();document.removeEventListener('visibilitychange',view.visibilityChanged);window.removeEventListener('pagehide',view.pageLeaving);window.removeEventListener('aaat:setup-return',view.setupReturn);delete root._parameterForm;}mounted.delete(id);},prompt(item){const tool=item.request?.tool_name;if((item.ui_hints?.control==='approval'||item.kind==='approval')&&tool)return ownerText(item.ui_hints?.prompt_labels,label('允许调用工具 '+tool+'？','Allow tool '+tool+'?'));return ownerText(item.ui_hints?.prompt_labels,item.prompt||'');},mount(root,run,item,onDone,options){if(root._parameterForm)return;const existing=mounted.get(item.id);if(existing?.isConnected){root.textContent=label('请在本任务上方的参数表单填写','Use the parameter form above for this task');return;}mounted.set(item.id,root);root._parameterForm=new FormView(root,run,item,onDone,options);}};
})();
