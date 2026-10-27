/* Shared Todo system-task directory. No execution or scheduling lives here. */
(() => {
'use strict';
const entry=document.getElementById('system-tasks-entry');
if(!entry)return;
const mobile=!!document.getElementById('mobile-todo');
const host=mobile?document.getElementById('mobile-todo'):document.querySelector('.todo-main');
const container=mobile?host:document.getElementById('todo-workspace');
const zh=(document.documentElement.lang||'').startsWith('zh');
const text=(a,b)=>zh?a:b;
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels={running:text('执行中','Running'),waiting_resource:text('等待资源','Waiting for resources'),waiting_user:text('等待处理','Waiting for input'),cancelling:text('正在中断 / 清理','Stopping / cleaning up'),queued:text('排队中','Queued'),completed:text('已完成','Completed'),partial:text('部分完成','Partially completed'),failed:text('失败','Failed'),cancelled:text('已中断','Cancelled'),interrupted:text('需核查后恢复','Verification needed'),scheduled:text('待定时执行','Scheduled'),history:text('历史','History')};
const base=mobile?'/v1/mobile/todo':'/v1/platform/todo';
const panel=document.createElement('section');panel.id='system-task-panel';panel.hidden=true;
host.append(panel);
let historyVisible=20;
let tab='running',data={tasks:[],schedules:[]},busy=false,last='',generation=0,followId=null;
entry.textContent=text('系统任务','System tasks');
entry.setAttribute('aria-controls',panel.id);entry.setAttribute('aria-expanded','false');
const date=n=>n?new Date(n*1000).toLocaleString():'—';
const elapsed=t=>Math.max(0,Math.floor(((t.finished_at||Date.now()/1000)-(t.started_at||t.created_at))/60));
async function api(path,body){const response=await fetch(base+path,{method:body?'POST':'GET',credentials:'same-origin',headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const result=await response.json();if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:result.detail?.message||text('请求失败','Request failed'));return result;}
function appBadge(id){
 const app=data.apps?.[id]||{name:id,icon:'app-window'};
 let icon=/^[a-z0-9-]{1,48}$/.test(app.icon||'')?app.icon:'app-window';
 const key=icon.replace(/(^|-)([a-z0-9])/g,(_,prefix,letter)=>letter.toUpperCase());
 if(window.lucide?.icons&&!window.lucide.icons[key]&&!window.ai2appsIcons?.[key])icon='app-window';
 return `<span class="system-task-app" title="${esc(id)}"><span class="system-task-app-icon" aria-hidden="true"><i data-lucide="${icon}"></i></span><span>${esc(app.name)}</span></span>`;
}
function close(){generation++;followId=null;panel.hidden=true;container.classList.remove('system-tasks-mode');entry.classList.remove('active');entry.setAttribute('aria-expanded','false');}
function render(){
 const expanded=new Map([...panel.querySelectorAll('[data-system-children]:not([hidden])')].map(el=>[el.dataset.systemChildren,el.innerHTML]));
 const tasks=data.tasks.filter(t=>tab==='running'?['running','waiting_resource','waiting_user','cancelling'].includes(t.status):tab==='queued'?t.status==='queued':!['queued','running','waiting_resource','waiting_user','cancelling'].includes(t.status));
 const list=tab==='scheduled'?data.schedules:tab==='history'?tasks.slice(0,historyVisible):tasks;
 panel.innerHTML=`<header class="system-task-heading"><button data-system-close type="button">‹ ${text('返回','Back')}</button><h2>${text('系统任务','System tasks')}</h2><button data-system-refresh type="button">${text('刷新','Refresh')}</button></header><nav class="system-task-tabs" aria-label="${text('任务状态','Task status')}">${['running','queued','scheduled','history'].map(key=>`<button type="button" data-system-tab="${key}" aria-pressed="${tab===key}">${labels[key]}</button>`).join('')}</nav><p class="system-task-help">${tab==='history'?text('保留最近 48 小时内的历史，最多 100 条；按结束时间排序。','History from the last 48 hours, up to 100 tasks, newest finished first.'):text('系统按资源和优先级调度；立即启动仍遵守并发限制。中断不会撤销已保存结果。','Tasks follow resource and priority limits. Starting now respects concurrency limits. Stopping does not undo saved results.')}</p><p id="system-task-notice" role="status"></p><div class="system-task-list">${list.length?list.map(t=>tab==='scheduled'?`<article class="system-task-card"><h3>${esc(t.name)}</h3><small>${appBadge(t.app_id)}</small><p>${text('下次执行','Next run')} ${esc(date(t.next_run))}${t.interval_seconds?` · ${text('间隔','Interval')} ${Math.round(t.interval_seconds/60)} ${text('分钟','min')}`:''}</p>${t.error?`<p>${esc(t.error)}</p>`:''}<button data-system-schedule="${esc(t.id)}" type="button">${text('立即启动','Start now')}</button></article>`:`<article class="system-task-card"><div class="system-task-card-head"><h3>${esc(t.name)}</h3><span class="system-task-status" data-status="${esc(t.status)}">${esc(labels[t.status]||t.status)}</span></div><small>${appBadge(t.app_id)} · ${esc(date(t.finished_at||t.created_at))} · ${text('尝试','Attempt')} ${t.attempt} · <span data-system-elapsed="${t.started_at||t.created_at}" data-system-finished="${t.finished_at||0}">${elapsed(t)}</span> ${text('分钟','min')}</small><p>${esc(t.status==='cancelled'?text('任务已中断，所属资源已清理','Task stopped; owned resources cleaned up'):t.message||(t.status==='queued'?text('等待系统执行名额','Waiting for an execution slot'):''))}</p>${t.progress?.phase?`<p>${esc(t.progress.phase)}${t.progress.source_name?' · '+esc(t.progress.source_name):''}</p>`:''}<div class="system-task-actions">${['queued','completed','partial','failed','cancelled'].includes(t.status)?`<button type="button" data-system-action="start" data-id="${esc(t.id)}">${t.status==='queued'?text('立即启动','Start now'):text('重新执行','Run again')}</button>`:''}${['queued','running','waiting_resource','waiting_user'].includes(t.status)?`<button type="button" data-system-action="cancel" data-id="${esc(t.id)}">${text('中断','Stop')}</button>`:''}${['running','waiting_resource','waiting_user','cancelling'].includes(t.status)?`<button type="button" data-system-action="force" data-id="${esc(t.id)}">${text('强制中断','Force stop')}</button>`:''}<button type="button" data-system-detail="${esc(t.id)}" aria-expanded="false">${text('子任务与执行记录','Subtasks and attempts')}</button></div><div class="system-task-children" data-system-children="${esc(t.id)}" hidden></div></article>`).join(''):`<p>${text('暂无任务','No tasks')}</p>`}</div>${tab==='history'?`<footer class="system-task-pagination"><span>${text('已显示','Showing')} ${list.length} / ${tasks.length}</span>${tasks.length>list.length?`<button type="button" data-system-more>${text('加载更多','Load more')} · 20</button>`:''}</footer>`:''}`;
 window.lucide?.createIcons();
 for(const el of panel.querySelectorAll('[data-system-children]'))if(expanded.has(el.dataset.systemChildren)){el.innerHTML=expanded.get(el.dataset.systemChildren);el.hidden=false;el.previousElementSibling.querySelector('[data-system-detail]')?.setAttribute('aria-expanded','true');}
}
async function load(force=false){if(busy||panel.hidden)return;busy=true;const epoch=generation;try{const next=await api('/system-tasks');if(epoch!==generation||panel.hidden)return;const serialized=JSON.stringify(next);data=next;if(followId){const followed=data.tasks.find(t=>t.id===followId);if(followed)tab=followed.status==='queued'?'queued':['running','waiting_resource','waiting_user','cancelling'].includes(followed.status)?'running':'history';}if(force||serialized!==last){last=serialized;render();}else for(const el of panel.querySelectorAll('[data-system-elapsed]'))el.textContent=String(Math.max(0,Math.floor(((Number(el.dataset.systemFinished)||Date.now()/1000)-Number(el.dataset.systemElapsed))/60)));}catch(error){const notice=panel.querySelector('#system-task-notice');if(notice)notice.textContent=error.message;}finally{busy=false;}}
entry.addEventListener('click',()=>{panel.hidden=false;container.classList.add('system-tasks-mode');entry.classList.add('active');entry.setAttribute('aria-expanded','true');render();load(true);});
if(!mobile)document.addEventListener('click',event=>{if(event.target.closest('[data-directory],[data-aggregate]'))close();},true);
panel.addEventListener('click',async event=>{
 const button=event.target.closest('button');if(!button)return;
 if(button.hasAttribute('data-system-close')){close();return;}
 if(button.hasAttribute('data-system-more')){historyVisible+=20;render();return;}
 if(button.dataset.systemTab){historyVisible=20;followId=null;tab=button.dataset.systemTab;render();return;}
 if(button.hasAttribute('data-system-refresh')){await load(true);return;}
 button.disabled=true;
 try{
  if(button.dataset.systemDetail){const id=button.dataset.systemDetail;const target=[...panel.querySelectorAll('[data-system-children]')].find(el=>el.dataset.systemChildren===id);if(!target.hidden){target.hidden=true;button.setAttribute('aria-expanded','false');return;}const value=await api('/system-tasks/'+encodeURIComponent(id));target.innerHTML=`<ul>${value.children.map(node=>`<li>${esc(node.name)} · ${esc(labels[node.status]||node.status)}</li>`).join('')}</ul><ul>${value.attempts.map(attempt=>`<li>#${attempt.number} · ${esc(labels[attempt.status]||attempt.status)} · ${esc(date(attempt.started_at))}${attempt.error?' · '+esc(attempt.error):''}</li>`).join('')}</ul>`;target.hidden=false;button.setAttribute('aria-expanded','true');return;}
  if(button.dataset.systemSchedule){const started=await api('/system-schedules/'+encodeURIComponent(button.dataset.systemSchedule)+'/start',{});followId=started.id;}
  else if(button.dataset.systemAction){const action=button.dataset.systemAction;const result=await api('/system-tasks/'+encodeURIComponent(button.dataset.id)+'/'+(action==='start'?'start':'cancel'),action==='start'?{}:{force:action==='force'});if(action==='start')followId=result.id;}
  await load(true);
 }catch(error){panel.querySelector('#system-task-notice').textContent=error.message;}
 finally{button.disabled=false;}
});
setInterval(()=>{if(!document.hidden)load();},5000);
})();
