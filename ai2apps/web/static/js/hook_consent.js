/* Trusted host review. Packages receive a decision, never the preview or grant authority. */
(function(){
 'use strict';
 const zh=(document.documentElement.lang||navigator.language||'').startsWith('zh');
 const words={title:['允许事件订阅？','Allow event subscription?'],publisher:['发布者','Publisher'],version:['版本','Version'],scope:['范围','Scope'],all:['当前及以后属于你的此类项目','Your current and future items of this type'],listen:['接收以下事件','Receive this event'],details:['通过 AaAT 读取该事件关联的详情','Read event details through AaAT'],metadata:['仅接收事件摘要','Receive event metadata only'],background:['界面关闭后继续由宿主处理','Continue host processing when the view is closed'],foreground:['仅在打开界面时接收','Receive in the open view'],actions:['执行以下固定动作','Run these fixed actions'],none:['无后续动作','No follow-up actions'],until:['授权有效至','Permission expires'],approve:['同意并启用','Allow and enable'],deny:['拒绝','Deny'],later:['稍后处理','Review later'],pending:['待处理的 Package 订阅申请','Pending Package requests'],grants:['Package 订阅授权','Package event permissions'],review:['审阅权限','Review permissions'],revoke:['撤销授权','Revoke permission'],notice:['可在设置的事件/响应页面暂停或撤销。安装 Package 本身不会获得此权限。','Pause or revoke in Settings → Event/Hook. Installation alone does not grant this permission.'],filters:['筛选条件（全部满足）','Filters (all must match)']};
 function text(key){return words[key]?.[zh?0:1]||key;}
 async function api(path,method='GET',body){const r=await fetch('/v1/platform/package-hooks'+path,{method,credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const v=await r.json();if(!r.ok)throw Error(v.detail?.message||v.detail||'Request failed');return v;}
 let active=null;
 async function review(id){
  if(active)return {status:'pending',request_id:id};
  const value=await api('/requests/'+encodeURIComponent(id));
  if(value.state!=='pending')return {status:value.state,request_id:id};
  if(active)return {status:'pending',request_id:id};
  const dialog=document.createElement('dialog');active=dialog;dialog.className='ai2apps-hook-consent';
  dialog.style.cssText='max-width:600px;width:calc(100% - 48px);max-height:85vh;overflow:auto;border:1px solid #8886;border-radius:16px;padding:24px;background:var(--bg-primary,#fff);color:var(--text-primary,#222);box-shadow:0 16px 60px #0005';
  function line(tag,label,content){const e=document.createElement(tag);e.textContent=label+(content===undefined?'':': '+content);e.style.whiteSpace='pre-wrap';e.style.overflowWrap='anywhere';dialog.append(e);return e;}
  line('h2',text('title'));line('h3',value.consumer);line('p',text('publisher'),value.publisher);line('p',text('version'),value.version);line('p',text('listen'),value.event);
  line('p',text('scope'),value.scope==='owned_collection'?text('all'):value.subjects.join(', '));
  if(value.filters.length)line('p',text('filters'),value.filters.map(x=>`${x.field} ${x.op} ${Array.isArray(x.value)?x.value.join(', '):String(x.value)}`).join('\n'));
  line('p',text(value.read_details?'details':'metadata'));line('p',text(value.background?'background':'foreground'));
  line('p',text('actions'),value.actions.length?value.actions.map(a=>a.title||a.registration).join(', '):text('none'));
  for(const action of value.actions){line('p',action.registration,Object.entries(action.arguments).map(([k,v])=>`${k}: ${String(v)}`).join('; '));}
  line('p',text('until'),new Date(value.grant_expires*1000).toLocaleString());line('p',text('notice'));
  const error=line('p','');error.setAttribute('role','alert');
  document.body.append(dialog);const decisionKey=crypto.randomUUID();
  return await new Promise(resolve=>{
   let finished=false,busy=false;
   function done(result){if(finished)return;finished=true;dialog.close();dialog.remove();active=null;resolve(result);}
   const controls=document.createElement('div');controls.style.cssText='display:flex;gap:12px;flex-wrap:wrap;margin-top:20px';dialog.append(controls);
   for(const choice of ['later','deny','approve']){const b=document.createElement('button');b.type='button';b.textContent=text(choice);b.style.cssText='padding:9px 16px;border-radius:8px;cursor:pointer';controls.append(b);b.addEventListener('click',async()=>{
    if(busy)return;if(choice==='later'){done({status:'pending',request_id:id});return;}
    busy=true;for(const button of controls.children)button.disabled=true;
    try{done(await api('/requests/'+encodeURIComponent(id)+'/'+choice,'POST',{review_hash:value.review_hash,request_id:decisionKey}));}
    catch(e){error.textContent=String(e.message);busy=false;for(const button of controls.children)button.disabled=false;}
   });}
   dialog.addEventListener('cancel',e=>{e.preventDefault();if(!busy)done({status:'pending',request_id:id});});dialog.showModal();controls.firstChild.focus();
  });
 }
 let manager=null;
 async function manage(){
  if(manager){manager.focus();return;}
  const dialog=document.createElement('dialog');manager=dialog;dialog.style.cssText='max-width:700px;width:calc(100% - 48px);max-height:85vh;overflow:auto;border-radius:16px;padding:24px;background:var(--bg-primary,#fff);color:var(--text-primary,#222)';
  const h=document.createElement('h2');h.textContent=text('grants');dialog.append(h);
  const content=document.createElement('div'),error=document.createElement('p');error.setAttribute('role','alert');dialog.append(content,error);
  function button(parent,label,fn){const b=document.createElement('button');b.textContent=label;b.type='button';b.style.cssText='padding:8px 12px;margin:8px;cursor:pointer';b.addEventListener('click',async()=>{b.disabled=true;try{await fn();}catch(e){error.textContent=String(e.message);}finally{b.disabled=false;}});parent.append(b);}
  function close(){dialog.close();dialog.remove();manager=null;}
  async function load(){
   const [requests,grants]=await Promise.all([api('/requests'),api('/grants')]);content.replaceChildren();
   const title=document.createElement('h3');title.textContent=text('pending');content.append(title);
   for(const item of requests.items.filter(x=>x.state==='pending')){const row=document.createElement('p');row.textContent=item.consumer+' · '+item.event;content.append(row);button(row,text('review'),async()=>{close();await review(item.id);await manage();});}
   for(const item of grants.items){const row=document.createElement('section');row.style.cssText='border-top:1px solid #8886;padding:12px 0';content.append(row);
    const label=document.createElement('strong');label.textContent=item.consumer+' · '+item.state+' · '+item.accepted_release.version;row.append(label);
    const p=item.permissions;const summary=document.createElement('p');summary.style.whiteSpace='pre-wrap';summary.textContent=[p.event_type,p.scope==='owned_collection'?text('all'):p.subjects.join(', '),text(p.read_details?'details':'metadata'),text(p.background?'background':'foreground'),text('actions')+': '+(p.actions.map(a=>a.registration).join(', ')||text('none')),text('until')+': '+new Date(item.expires*1000).toLocaleString()].join('\n');row.append(summary);
    if(['active','paused'].includes(item.state))button(row,item.state==='active'?(zh?'暂停':'Pause'):(zh?'恢复':'Resume'),async()=>{await api('/grants/'+item.id+'/control/'+(item.state==='active'?'pause':'resume'),'POST',{expected_revision:item.revision,request_id:crypto.randomUUID()});await load();});
    if(!['revoked','expired','deleted'].includes(item.state))button(row,text('revoke'),async()=>{await api('/grants/'+item.id+'/revoke','POST',{});await load();});
   }
  }
  button(dialog,zh?'刷新':'Refresh',load);button(dialog,zh?'关闭':'Close',close);dialog.addEventListener('cancel',e=>{e.preventDefault();close();});document.body.append(dialog);dialog.showModal();
  try{await load();}catch(e){error.textContent=String(e.message);}
 }
 window.AI2AppsHookConsent=Object.freeze({review,manage,text});
})();
