/* Host-reviewed Bot task proposals and relay to original durable Run interactions. */
(function(){
 'use strict';
 function create({bot,root,api,refresh,onError,label}){
  let signature='',disposed=false,delegationDetails=new Map();const responses=new Map(),forms=new Set(),accessChoices=new Map();
  function releaseForms(){for(const id of forms)window.AI2AppsParameterForms?.release?.(id);forms.clear();}
  const base='/messager/bots/'+encodeURIComponent(bot.id);
  function node(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
  function button(text,fn){const b=node('button',text,'messager-button');b.type='button';b.onclick=async()=>{b.disabled=true;try{await fn();window.dispatchEvent?.(new CustomEvent('ai2apps:bot-app-access-changed',{detail:{botId:bot.id}}));signature='';await refresh();}catch(e){onError(e);}finally{b.disabled=false;}};return b;}
  function localScheduleTime(stamp, zone) {
   try {
    return new Intl.DateTimeFormat(document.documentElement.lang || 'en', {
     dateStyle:'medium', timeStyle:'short', timeZone:zone,
    }).format(new Date(stamp)) + ' · ' + zone;
   } catch (_) {
    return stamp + ' · ' + zone;
   }
  }
  function schedule(s){if(s.frequency==='off')return label('立即执行一次','Run once now');if(s.frequency==='once')return localScheduleTime(s.once_at,s.timezone);
   const frequencies={hourly:label('每小时','Hourly'),daily:label('每天','Daily'),weekly:label('每周','Weekly'),monthly:label('每月','Monthly')};return (frequencies[s.frequency]||s.frequency)+' '+(s.frequency==='weekly'?label('星期','weekday ')+(s.weekday+1)+' ':s.frequency==='monthly'?s.day+label('日 ',' day '):'')+(s.frequency==='hourly'?'':String(s.hour).padStart(2,'0')+':')+String(s.minute).padStart(2,'0')+' · '+s.timezone;}
  function planSchedule(s){return s.frequency==='off'?label('无自动执行计划','No automatic schedule'):schedule(s);}
  function nextDue(card, stamp, zone) {
   if (!stamp) return;
   card.append(node('p', label('预计下次执行 · ','Next execution · ') + localScheduleTime(stamp, zone)));
  }
  async function respond(pending,response){const key=JSON.stringify(response),old=responses.get(pending.id);const value=old?.key===key?old:{key,id:crypto.randomUUID()};responses.set(pending.id,value);
   return api(base+'/task-runs/'+pending.todo_run_id+'/interactions/'+pending.id+'/respond','POST',{review_hash:pending.review_hash,response_id:value.id,response});}
  function accessReview(card,preflight,reviewKey){
   if(!preflight)return ()=>({});
   if(preflight.schema==='ai2apps.bot-task-preflight/v2'){
    const section=node('fieldset',undefined,'bot-plan-access');
    const saved=accessChoices.get(reviewKey);
    section.append(node('legend',label('Bot 访问权限','Bot access')),
     node('p',label('每次执行都继承 Bot 当时的访问权限。可在这里为 Bot 追加授权，特殊操作仍逐次确认。','Each run inherits the Bot’s access at start. You can grant additional access here. Special operations still require confirmation.')));
    const extra=node('details');
    extra.append(node('summary',label('追加 App、Mini-App 或 Bot 权限','Grant additional App, Mini-App or Bot access')));
    const apps=[],bots=[];
    function choice(container,list,id,name,checked,required){
     const row=node('label'),input=node('input');input.type='checkbox';input.checked=checked;input.disabled=required;
     list.push([input,id]);row.append(input,node('span',name));container.append(row,node('br'));
    }
    for(const app of preflight.apps){
     const name=(app.names?.[document.documentElement.lang]||app.name)+(app.kind==='mini-app'?' · Mini-App':'');
     if(app.current_access){if(app.predicted)section.append(node('p',name+label(' · 已有权限',' · Inherited')));continue;}
     choice(app.predicted?section:extra,apps,app.app_id,name,app.required||!!saved?.access_apps.includes(app.app_id),!!app.required);
    }
    for(const bot of preflight.bots||[]){
     if(bot.enabled)continue;
     choice(extra,bots,bot.id,bot.name+' · Bot',!!saved?.access_bots.includes(bot.id),false);
    }
    if(extra.childNodes.length>1)section.append(extra);card.append(section);
    function remember(){
     const selected=list=>list.filter(([input])=>input.checked).map(([,id])=>id);
     const value={access_mode:'inherit',access_apps:selected(apps),access_bots:selected(bots)};
     accessChoices.set(reviewKey,value);if(accessChoices.size>40)accessChoices.delete(accessChoices.keys().next().value);return value;
    }
    for(const [input] of [...apps,...bots])input.onchange=remember;return remember;
   }
   const section=node('fieldset',undefined,'bot-plan-access'),legend=node('legend',label('授予 Bot 的 App 权限','App access for this Bot')),mode=node('select');
   for(const [value,text] of [['fixed',label('现在设定，运行时固定','Configure now; fixed at runtime')],['auto',label('运行时自动获取批准范围内的权限','Acquire automatically within the approved scope')]]){const option=node('option',text);option.value=value;mode.append(option);}
   const saved=accessChoices.get(reviewKey);if(saved)mode.value=saved.access_mode;
   section.append(legend,mode,node('p',label('仅检查能力声明，不试运行任务。批准的访问权限保存到 Bot，后续对话与任务也可使用；本任务仍冻结执行范围。动态步骤可能遗漏；范围外的能力需要修改并重新确认计划。','Checks declarations without executing the task. Approved access is saved on the Bot for later conversations and tasks; this task retains its scope ceiling. Dynamic steps may be missed; capabilities outside this scope require a new plan review.')));
   if(!preflight.requirements_declared)section.append(node('p',label('Bot 尚未列出具体能力需求；请核对范围或取消后让 Bot 补充，不能据此认定预检完整。','The Bot has not listed concrete requirements. Review the scope or cancel and ask for a more complete proposal.')));
   section.append(node('p',label('选择一个目标，将允许其当前声明中的全部普通 AaAT；App 与 Mini-App 独立。','Selecting a target allows all its currently declared ordinary AaAT operations. Apps and Mini-Apps are independent.')));
   const choices=[];const extras=node('details');extras.append(node('summary',label('其他已安装 App / Mini-App（可选）','Other installed Apps / Mini-Apps (optional)')));
   for(const app of preflight.apps){const row=node('label'),input=node('input');input.type='checkbox';input.checked=!!app.required||(saved?saved.access_apps.includes(app.app_id):!!app.predicted);input.disabled=!!app.required;input.dataset.accessApp=app.app_id;choices.push([input,app.app_id]);const lang=document.documentElement.lang||'en',name=app.names?.[lang]||app.names?.[lang.split('-')[0]]||app.name;row.append(input,node('span',name+(app.kind==='mini-app'?' · Mini-App':'')));if(app.reasons?.length)row.append(node('small',' — '+app.reasons.map(reason=>reason==='Existing background access'?label('已具备的后台权限','Existing background access'):reason==='Previously reviewed plan access; review again for this amendment'?label('原计划已批准，本次修改请重新核对','Previously approved; review again for this amendment'):reason.startsWith('Related owner declaration: ')?label('声明建议的关联能力','Related capability from its declaration'):reason).join('；')));if(app.special_count)row.append(node('small',label('；特殊操作仍逐次确认','; special operations still ask each time')));(app.predicted?section:extras).append(row,node('br'));}
   section.append(extras,node('p',label('两种模式都不会自动批准付款、敏感或声明要求确认的操作；新安装或声明变更的能力不自动加入。','Neither mode auto-approves payments, sensitive or explicitly confirmed operations. Newly installed or changed capabilities are excluded.')));card.append(section);
   function remember(){const value={access_mode:mode.value,access_apps:choices.filter(([input])=>input.checked).map(([,id])=>id)};accessChoices.set(reviewKey,value);if(accessChoices.size>40)accessChoices.delete(accessChoices.keys().next().value);return value;}
   mode.onchange=remember;for(const [input] of choices)input.onchange=remember;return remember;
  }
  function update(work){const next=JSON.stringify(work);if(disposed||next===signature)return;signature=next;releaseForms();root.replaceChildren();
   for(const plan of work.collaboration_plans||[]){const v=plan.value,card=node('article',undefined,'bot-task-card');card.dataset.collaborationPlanId=plan.id;
    card.append(node('strong',label('协作计划：','Collaboration plan: ')+v.title));
    card.append(node('p',label('确认计划也允许发起 Bot 长期使用所列参与 Bot；后台计划和敏感操作授权仍独立生效。','Approving also allows the initiating Bot to use the listed participants. Background-plan and sensitive-operation authorizations remain separate.')));
    if(v.replaces_plan_id)card.append(node('p',label('确认后替换原计划，后续新执行使用此版本；已经准入的执行保留原规则。','Replaces the original plan for future admissions; admitted batches keep their original rules.')));
    for(const participant of v.participants){const details=node('details');details.append(node('summary',v.identities[participant.bot_id].name),node('p',participant.instructions));const rights=Object.keys(participant.allowed);details.append(node('p',label('冻结的后台能力：','Frozen background capabilities: ')+(rights.length?rights.join('、'):label('仅文本','Text only'))));card.append(details);}
    card.append(node('p',v.trigger==='schedule'?schedule(v.schedule):v.trigger==='event'?label('事件：','Event: ')+v.event.event_type+' · '+JSON.stringify(v.event):label('立即协作一次','Collaborate once now')));
    card.append(node('p',label('模型：','Model: ')+v.model),node('p',v.aggregation==='all_success'?label('全部成功才算完成','Requires all participants to succeed'):label('允许部分结果，明确列出缺失','Allows partial results with explicit gaps')),node('p',label('共享上限：10分钟 / 36次工具调用 / 48000模型tokens','Shared limit: 10 minutes / 36 tool calls / 48000 model tokens')),node('small',label('授权有效至：','Authorized until: ')+new Date(plan.expires*1000).toLocaleString()));
    card.append(node('p',label('每计划每天最多24次新执行；事件执行至少间隔60秒，原 Hook 更严格的限制继续生效。','At most 24 new batches per plan per day; event batches are at least 60 seconds apart and retain stricter Hook limits.')));
    card.append(node('p',label('仅使用发起方与执行方后台权限的交集；特殊、敏感和付费操作仍逐项询问。审批回到此对话。计划修改需重新审阅；停用会停止未完成协作，已完成操作保留。','Uses the intersection of both Bots’ background rights. Special, sensitive and paid actions still ask here. Changes require review. Disabling stops unfinished collaboration; completed effects remain.')));
    if(plan.status==='pending'||plan.status==='approving')card.append(button(label('确认协作计划','Allow collaboration plan'),()=>api(base+'/collaboration-plans/'+plan.id+'/decisions/approve','POST',{review_hash:plan.review_hash})),button(label('不启用','Dismiss'),()=>api(base+'/collaboration-plans/'+plan.id+'/decisions/reject','POST',{review_hash:plan.review_hash})));
    else card.append(button(label('停用协作计划','Disable collaboration plan'),()=>api(base+'/collaboration-plans/'+plan.id+'/pause','POST',{})));
    root.append(card);
   }
   const previousDetails=delegationDetails;delegationDetails=new Map();
   for(const request of work.delegations||[]){
    const card=node('article',undefined,'bot-task-card'),details=node('details'),pending=request.status==='pending';
    const key=request.id+':'+(pending?'review':'active');
    const canReview=pending&&(request.review_bot||request.source_bot)===bot.id;
    card.dataset.delegationId=request.id;
    details.open=previousDetails.get(key)?.open??false;delegationDetails.set(key,details);
    if(pending)card.append(node('strong',label('委派给「'+request.target_name+'」：','Delegate to '+request.target_name+': ')+request.title));
    details.append(node('summary',pending?label('查看任务与权限','Review task and access'):label('协作详情：','Collaboration details: ')+request.target_name+' · '+request.title));
    if(request.instructions)details.append(node('pre',request.instructions));
    if(request.deliverable)details.append(node('p',label('预期产物：','Expected deliverable: ')+request.deliverable));
    if(request.model)details.append(node('p',label('执行模型：','Execution model: ')+request.model));
    if(request.source_name)details.append(node('p',label('调用方：','Caller: ')+request.source_name));
    if(request.graph&&request.graph_policy){
     const p=request.graph_policy;
     details.append(node('p',label('协作限额：','Collaboration limits: ')+label(
      `共享 ${p.max_model_tokens} tokens、${p.max_tool_calls} 次工具调用、${Math.round(p.timeout_seconds/60)} 分钟；最多 ${p.max_edges} 次委派、${p.max_depth} 层。`,
      `${p.max_model_tokens} shared model tokens, ${p.max_tool_calls} tool calls, ${Math.round(p.timeout_seconds/60)} minutes, ${p.max_edges} assignments, ${p.max_depth} levels.`)));
     if(p.round_model_tokens)details.append(node('p',label(`每轮最多 ${p.round_model_tokens} tokens。`,`Up to ${p.round_model_tokens} model tokens per round.`)));
     details.append(node('p',request.allow_subdelegation?label('允许继续分工；未授权的目标仍需在原对话批准。','Further delegation is allowed; unapproved targets still need approval in the original conversation.'):label('此 Bot 不能继续委派。','This Bot cannot delegate further.')));
    }else if(request.budget)details.append(node('p',label('每轮限额：','Limits per round: ')+Math.round(request.budget.timeout_seconds/60)+label(' 分钟，',' minutes, ')+request.budget.max_model_tokens+' model tokens'));
    const grants=(request.access||[]).map(grant=>grant.capability+' · '+grant.access);
    details.append(node('p',label('子任务可用能力：','Available child task capabilities: ')+(grants.length?grants.join('、'):label('仅文本','Text only'))));
    if(canReview)card.append(node('p',label('允许后，调用方可继续使用此 Bot。子任务只使用双方已授权且本次允许的能力，敏感操作仍单独确认。','Approval lets the caller keep using this Bot. The child uses only existing access allowed for this task. Sensitive actions still require separate confirmation.')));
    if(pending&&!canReview)card.append(node('p',label('等待在发起对话中批准。','Awaiting approval in the originating conversation.')));
    if(!pending)details.append(button(label('停止协作','Stop collaboration'),()=>api(base+'/delegations/'+request.id+'/cancel','POST',{})));
    card.append(details);
    if(canReview)card.append(button(label('允许此 Bot 使用目标 Bot','Allow Bot access'),()=>api(base+'/delegations/'+request.id+'/decisions/approve','POST',{review_hash:request.review_hash})),button(label('不委派','Do not delegate'),()=>api(base+'/delegations/'+request.id+'/decisions/reject','POST',{review_hash:request.review_hash})));
    if(pending)card.append(button(label('停止协作','Stop collaboration'),()=>api(base+'/delegations/'+request.id+'/cancel','POST',{})));
    root.append(card);
   }
   for(const request of work.communications||[]){const card=node('article',undefined,'bot-task-card');card.dataset.communicationId=request.id;
    card.append(node('strong',label('咨询 Bot：','Consult Bot: ')+request.target_name),node('p',request.question),node('p',label('回复模型：','Reply model: ')+request.model));
    if(request.status==='pending'){
     card.append(node('p',label('批准后会保存此 Bot 对目标 Bot 的长期使用授权，后续普通调用不再询问。','Approval saves ongoing directed Bot use; later ordinary calls do not ask again.')));
     card.append(node('p',label('确认后只发送以上文字，并使用所示模型回答一次。不会共享历史、记忆或 App 权限；可能产生模型用量。回复将回到当前 Bot 对话。','Send only the text above and answer once using the shown model. No history, memory or App access is shared; model usage may be incurred. The answer returns to this Bot conversation.')));
     card.append(button(label('允许此 Bot 使用目标 Bot','Allow Bot access'),()=>api(base+'/communication/'+request.id+'/decisions/approve','POST',{review_hash:request.review_hash})),button(label('不发送','Do not send'),()=>api(base+'/communication/'+request.id+'/decisions/reject','POST',{review_hash:request.review_hash})));
    }else{card.append(node('p',label('已发送，正在等待咨询回复；你可以继续聊天。','Sent; waiting for a reply. You can keep chatting.')),button(label('取消咨询','Cancel consultation'),()=>api(base+'/communication/'+request.id+'/cancel','POST',{})));}
    root.append(card);
   }
   for(const proposal of work.configurations||[]){const value=proposal.value,before=proposal.before,card=node('article',undefined,'bot-task-card');
    const titles={identity:label('修改 Bot 身份职责','Change Bot identity and duty'),memory:label('保存长期记忆','Save long-term memory'),pause_schedule:label('停用原执行计划','Disable the original schedule')};
    card.append(node('strong',label('设置待确认：','Review configuration: ')+titles[value.kind]));
    if(value.kind==='identity'){card.append(node('p',label('原名称：','Previous name: ')+before.name),node('p',label('新名称：','New name: ')+value.name),node('p',label('原职责：','Previous duty: ')+before.duty),node('p',label('新职责：','New duty: ')+value.duty),node('p',label('适用于后续对话，已确认任务保持原快照；相关 Hook 需要重新审阅。','Applies to future turns. Approved tasks retain their snapshot; related Hooks require renewed review.')));}
    else if(value.kind==='memory')card.append(node('p',value.text),node('p',label('确认后作为用户保存的长期记忆；不授予 App 权限。','Saved as a user-confirmed long-term note; it grants no App access.')));
    else card.append(node('p',before.title),node('p',schedule(before.schedule)),node('p',label('将停用此 Todo 的后续执行计划。已启动或已入队的执行不受影响；恢复需重新确认新计划。','Disables future execution slots for this Todo. Admitted or running executions remain unchanged; resuming requires a new reviewed plan.')));
    card.append(node('small',label('审阅有效期：','Review expires: ')+new Date(proposal.expires_at).toLocaleString()));
    card.append(button(proposal.status==='applying'?label('核对并完成原确认','Resolve original confirmation'):label('确认保存变更','Confirm these changes'),async()=>{const result=await api(base+'/configurations/'+proposal.id+'/approve','POST',{review_hash:proposal.review_hash});window.dispatchEvent(new CustomEvent('ai2apps:bot-configuration-applied',{detail:{botId:bot.id,kind:value.kind,status:result.status}}));}));
    card.append(button(label('取消变更','Dismiss change'),()=>api(base+'/configurations/'+proposal.id+'/reject','POST',{review_hash:proposal.review_hash})));root.append(card);
   }
   for(const proposal of work.plan_changes||[]){const value=proposal.value,before=proposal.before,card=node('article',undefined,'bot-task-card');
    card.append(node('strong',label('原计划修改待确认：','Review changes to the existing plan: ')+(before.title||value.title)));
    if(before.title&&before.title!==value.title)card.append(node('p',label('新标题：','Revised title: ')+value.title));
    card.append(node('p',label('原规则：','Previous instructions: ')+before.description),node('p',label('新规则：','Revised instructions: ')+value.prompt),node('p',label('原执行时间：','Previous schedule: ')+planSchedule(before.schedule)),node('p',label('新执行时间：','Revised schedule: ')+planSchedule(value.schedule)));
    nextDue(card, proposal.next_due, value.schedule.timezone);
    card.append(node('p',label('确认后从下一次新执行生效，当前已启动或已入队的执行保持原规则。删除、付费及敏感操作仍需相应授权，确认计划不会批准这些操作。','Changes apply to future runs. Runs already started or queued keep the prior rules. Deletion, paid and sensitive operations still require their own authorization.')));
    const accessChoice=accessReview(card,value.access_preflight,proposal.id+':'+proposal.review_hash);
    card.append(button(label('确认更新原计划','Confirm plan update'),()=>api(base+'/plan-changes/'+proposal.id+'/approve','POST',{review_hash:proposal.review_hash,...accessChoice()})),button(label('保留原计划','Keep existing plan'),()=>api(base+'/plan-changes/'+proposal.id+'/reject','POST',{review_hash:proposal.review_hash})));root.append(card);
   }
   for(const proposal of work.proposals){const value=proposal.proposal,card=node('article',undefined,'bot-task-card');card.append(node('strong',label('任务待确认：','Review task: ')+value.title),node('p',value.prompt),node('p',schedule(value.schedule)),node('small',label('执行模型：','Execution model: ')+value.model));
    nextDue(card, proposal.next_due, value.schedule.timezone);
    card.append(node('p',label('保存位置：Todo 收件箱','Save to: Todo Inbox')));
    if(value.identity?.long_term_memory?.length){const details=node('details');details.append(node('summary',label('本任务的记忆快照','Memory snapshot for this task')));for(const note of value.identity.long_term_memory)details.append(node('p',note.text));card.append(details);}
    if(!value.access_preflight)card.append(node('p',label('后台允许操作：','Allowed background operations: ')+(proposal.access.length?proposal.access.map(p=>label(p.zh,p.en)).join('、'):label('仅任务文本，不读取 App','Task text only; no App reads'))));
    card.append(node('p',value.notify?label('结束后在此对话及站内提醒告知结果','Report the result here and in the notification Inbox'):label('成功时保持安静，失败仍报告','Stay quiet on success; report failures')));
    card.append(node('small',label('失败或等待回复时，按 Bot 的提醒策略发出站内提醒。','Failures and required responses follow this Bot’s notification settings.')));
    const accessChoice=accessReview(card,value.access_preflight,proposal.id+':'+proposal.review_hash);
    card.append(button(value.schedule.frequency==='off'?label('确认并启动','Confirm and start'):label('确认执行计划','Confirm schedule'),()=>api(base+'/task-proposals/'+proposal.id+'/approve','POST',{review_hash:proposal.review_hash,...accessChoice()})));
    card.append(button(proposal.status==='pending'?label('不创建','Dismiss'):label('取消尚未完成的确认','Cancel unfinished confirmation'),()=>api(base+'/task-proposals/'+proposal.id+'/reject','POST',{review_hash:proposal.review_hash})));
    root.append(card);
   }
   for(const pending of work.interactions){const card=node('article',undefined,'bot-task-card');card.dataset.todoRunId=pending.todo_run_id;card.tabIndex=-1;card.append(node('strong',label('任务需要你回复：','Task needs your reply: ')+pending.title),node('p',label('正在做：','Working on: ')+(pending.task_request||pending.title)),node('p',(pending.kind==='approval'?label('需要你确认：','Please confirm: '):label('需要你明确：','Please clarify: '))+pending.prompt));
    if(pending.control==='parameter_form'&&window.AI2AppsParameterForms){const host=node('div');card.append(host);root.append(card);forms.add(pending.id);window.AI2AppsParameterForms.mount(host,{id:pending.run_id},{id:pending.id,kind:pending.kind,status:'pending',prompt:pending.prompt,ui_hints:pending.ui_hints},refresh);continue;}
    if(pending.kind==='approval'&&pending.task_tree_approval&&window.AI2AppsBotInteractions){
     const host=node('div');card.append(host);root.append(card);
     window.AI2AppsBotInteractions.render({root:host,run:{id:pending.run_id},item:{id:pending.id,kind:pending.kind,prompt:pending.prompt,request:pending.operation,schema:pending.schema,ui_hints:pending.ui_hints},botId:bot.id,api,label,onError,refresh,respond:response=>respond(pending,response).then(refresh)});
     continue;
    }
    if(pending.control){card.append(node('p',label('请在原 App 中处理这项请求，原任务会等待结果。','Complete this request in its owning App. The task will wait for its result.')));card.append(button(label('停止任务','Stop task'),()=>api(base+'/task-runs/'+pending.todo_run_id+'/cancel','POST',{})));root.append(card);continue;}
    if(pending.kind==='approval'){
     if(Object.keys(pending.operation||{}).length){const details=node('details');details.append(node('summary',label('操作详情','Operation details')),node('pre',JSON.stringify(pending.operation,null,2)));card.append(details);}
     const schema=pending.schema,required=schema.required||[];
     if(required.some(k=>!['decision','scope','resource_scope'].includes(k))){card.append(node('p',label('此请求需要在原 App 审阅。','Review this request in its owning App.')));root.append(card);continue;}
     const risk=window.AI2AppsParameterForms?.mountRiskChoice(card,schema,pending.ui_hints?.unknown_tool_risk);
     card.append(button(label('同意本次操作','Approve this operation'),()=>{const value={decision:'approve',...risk?.()};if(schema.properties?.scope)value.scope='once';if(schema.properties?.resource_scope)value.resource_scope='current';return respond(pending,value);}));
     card.append(button(label('拒绝','Deny'),()=>respond(pending,{decision:'deny'})));
    }else{
     const form=node('form'),fields=[];let supported=true;
     for(const [key,schema] of Object.entries(pending.schema?.properties||{})){
      if(!['string','boolean','integer','number'].includes(schema.type)){supported=false;break;}
      const field=document.createElement(schema.enum?'select':schema.type==='boolean'?'input':'textarea');if(schema.enum)for(const value of schema.enum)field.add(new Option(String(value),String(value)));if(schema.type==='boolean')field.type='checkbox';field.required=pending.schema.required?.includes(key)||false;
      const l=node('label',schema.title||label('回复','Reply'));l.append(field);form.append(l);fields.push([key,schema,field]);
     }
     if(supported){const submit=node('button',label('回复任务','Reply to task'),'messager-button');submit.type='submit';form.append(submit);form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{const response={};for(const [key,schema,field] of fields)response[key]=schema.type==='boolean'?field.checked:['integer','number'].includes(schema.type)?Number(field.value):field.value;await respond(pending,response);signature='';await refresh();}catch(e){onError(e);}finally{submit.disabled=false;}};card.append(form);}else card.append(node('p',label('请在原 App 中补充所需信息。','Provide the required information in its owning App.')));
    }
    card.append(button(label('停止任务','Stop task'),()=>api(base+'/task-runs/'+pending.todo_run_id+'/cancel','POST',{})));root.append(card);
   }
  }
  return {update,dispose(){disposed=true;releaseForms();accessChoices.clear();root.replaceChildren();}};
 }
 window.AI2AppsBotTaskFeed={create};
})();
