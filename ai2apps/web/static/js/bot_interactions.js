/* Bot-owned presentation of durable Agent approvals; execution stays in the original owner. */
(function(){
 'use strict';
 function render({root,run,item,botId,api,respond,refresh,onError,label}){
  root._botInteractionKey=item.id;root.hidden=false;root.classList.add('bot-interaction-card');
  const live=()=>root.isConnected&&root._botInteractionKey===item.id;
  const control=item.ui_hints?.control||item.request?.control;
  const collaborationBudget=item.kind==='menu'&&item.request?.collaboration_budget===true;
  const supported=collaborationBudget||['approval','parameter_form','app_handoff'].includes(control)||item.kind==='approval';
  let actions;
  function button(text,action,secondary=false){if(!actions){actions=document.createElement('div');actions.className='bot-interaction-actions';root.append(actions);}const b=document.createElement('button');b.type='button';b.className='messager-button'+(secondary?' secondary':'');b.textContent=text;b.onclick=async()=>{if(b.disabled||!live())return;const controls=[...root.querySelectorAll('button'),...root.querySelectorAll('input, select')];controls.forEach(x=>x.disabled=true);try{await action();}catch(e){if(live())onError(e);}finally{if(live()&&root.dataset.interactionState!=='access-submitted')controls.forEach(x=>x.disabled=false);}};actions.append(b);return b;}
  function context(){const c=run.task_context;if(!c)return;const box=document.createElement('div');box.className='bot-question-context';box.append(text('strong',label('正在处理：','Task: ')+c.task),text('p',label('当前步骤：','Current step: ')+c.step));if(c.request&&c.request!==c.step)box.append(text('p',label('你的要求：','Your request: ')+c.request));root.append(box);}
  function clear(){root.replaceChildren();actions=null;context();}
  function text(tag,value,className){const node=document.createElement(tag);node.textContent=value;if(className)node.className=className;return node;}
  function appHeader(app){const header=document.createElement('header');header.className='bot-interaction-identity';const iconWrap=document.createElement('span');iconWrap.className='bot-interaction-icon';const icon=document.createElement('i');icon.setAttribute('data-lucide',/^[a-z0-9-]+$/i.test(app?.icon||'')?app.icon:'shield-check');icon.setAttribute('aria-hidden','true');iconWrap.append(icon);const info=document.createElement('div');const names=app?.names||{},name=label(names.zh||app?.name,names.en||app?.name)||label('访问授权','Access request');info.append(text('small',app?(app.kind==='mini-app'?'Mini-App':'App')+((app.hosts||[]).length?' · '+app.hosts.join(' · '):''):label('需要你的确认','Your confirmation is needed')),text('h3',name));header.append(iconWrap,info);root.append(header);window.lucide?.createIcons();}
  function details(){const d=document.createElement('details'),summary=text('summary',label('查看操作详情','View operation details')),preview=text('pre',JSON.stringify(item.request?.action_preview||item.request,null,2),'bot-approval-preview');d.append(summary,preview);root.append(d);}
  function operation(app,special=false){clear();appHeader(app);root.dataset.interactionState='confirmation';root.append(text('h4',special?label('此操作需要单独确认','Confirm this operation'):label('确认本次操作','Confirm operation')),text('p',special?label('访问权限已授予；本次交易付款、敏感或特殊操作需要你另外确认。','Access is granted. Confirm this purchase, payment, sensitive or special operation separately.'):window.AI2AppsParameterForms.prompt(item)));details();const risk=window.AI2AppsParameterForms?.mountRiskChoice(root,item.response_schema||item.schema,item.ui_hints?.unknown_tool_risk);button(label('确认本次操作','Confirm this operation'),()=>respond({decision:'approve',scope:'once',...risk?.()}));button(label('拒绝','Deny'),()=>respond({decision:'deny'}),true);}
  clear();if(!supported)return false;
  if(collaborationBudget){
   const [continueAnswer,stopAnswer]=item.schema.properties.answer.enum;
   const used=Number(item.request.used_tokens).toLocaleString(document.documentElement.lang||undefined);
   const extra=Number(item.request.additional_tokens).toLocaleString(document.documentElement.lang||undefined);
   root.append(text('h4',label('协作已用完本轮额度','Collaboration reached its token allowance')),
    text('p',label(`本轮已使用 ${used} tokens。可以追加 ${extra} tokens 继续，或结束并保留已有结果。`,
     `This round used ${used} tokens. Add ${extra} tokens to continue, or finish and keep the results so far.`)));
   button(label('继续协作','Continue collaboration'),()=>respond({answer:continueAnswer}));
   button(label('结束并保留结果','Finish and keep results'),()=>respond({answer:stopAnswer}),true);
   return true;
  }
  if(control==='parameter_form'){root.append(text('p',window.AI2AppsParameterForms.prompt(item)));const host=document.createElement('div');root.append(host);window.AI2AppsParameterForms.mount(host,run,item,refresh);return true;}
  if(control==='app_handoff'){appHeader();root.append(text('p',window.AI2AppsParameterForms.prompt(item)));button(label('前往 App 完成','Continue in App'),async()=>{if(!window.ai2appsShell?.openHandoff)throw Error(label('请在 AI2Apps 桌面中继续','Continue in AI2Apps Desktop'));await window.ai2appsShell.openHandoff(run.id,item.id,false);});button(label('取消交接','Cancel handoff'),()=>respond({status:'cancelled',result:{}}),true);return true;}
  if(run.task_tree_approval&&run.task_tree_review_here===false){
   appHeader(item.owner_app);
   root.append(text('p',label('请在发起此任务的 Bot 对话中确认。','Review this request in the Bot conversation that started the task.')));
   return true;
  }
  if(!botId||!api){operation(item.owner_app);return true;}
  const path='/messager/bots/'+encodeURIComponent(botId)+'/app-access/requests/'+encodeURIComponent(run.id)+'/'+encodeURIComponent(item.id);
  let serial=0;
  async function load(){const token=++serial;clear();appHeader();root.append(text('p',label('正在读取目标应用和请求权限…','Loading the requested App and access…')));root.dataset.interactionState='loading';
   try{const value=await api(path);if(!live()||serial!==token)return;
    if(!value.eligible){clear();appHeader();root.append(text('h4',label('无法确定授权对象','Cannot identify the access target')),text('p',label('此操作所属的应用未能确定，尚未执行。重新加载不能解决此问题；请取消本次操作后重新说明任务。','The App for this operation could not be identified. The operation has not executed. Reloading cannot resolve this issue; cancel this operation and clarify the task.')));details();button(label('取消本次操作','Cancel this operation'),()=>respond({decision:'deny'}),true);root.dataset.interactionState='unavailable';return;}
    if(value.access_granted&&value.special){operation(value.app,true);return;}
    if(value.access_granted){
     try{await api(path,'POST',{request_hash:value.request_hash,existing_access_only:true});}
     catch(error){await refresh();if(!live()||serial!==token)return;throw error;}
     if(!live()||serial!==token)return;
     root.dataset.interactionState='access-submitted';await refresh();return;
    }
    clear();appHeader(value.app);root.classList.add('bot-app-access-card');root.dataset.interactionState='access';
    if(value.task_tree){
     root.append(text('h4',label('允许此任务访问？','Allow this task to access this app?')),text('p',label('此次批准适用于整个任务及其子任务。交易付款、敏感及特殊操作仍需单独确认。','This approval applies to this task and its subtasks. Purchases, payments, sensitive and special operations still require separate confirmation.')));
    }else root.append(text('h4',label('允许此 Bot 使用此应用？','Allow this bot to use this '+(value.app.kind==='mini-app'?'Mini-App':'App')+'?')),text('p',label('权限仅保存在这个 Bot。交易付款、敏感及特殊操作仍需单独确认；AI/API 用量遵循模型配置与预算。','Access is saved for this Bot. Purchases, payments, sensitive and special operations still require separate confirmation. AI/API usage follows model settings and budgets.')));
    details();
    button(value.task_tree?label('允许此次任务访问','Allow for this task'):label('允许此 Bot 访问','Allow this bot access'),async()=>{
     let result;try{result=await api(path,'POST',{request_hash:value.request_hash});}catch(error){if(live())await load();throw error;}
     if(!live())return;if(!value.task_tree)window.dispatchEvent(new CustomEvent('ai2apps:bot-app-access-changed',{detail:{botId}}));
     if(result.requires_confirmation){operation(value.app,true);return;}
     root.dataset.interactionState='access-submitted';root.append(text('p',label('已批准，正在继续…','Access approved. Continuing…'),'bot-interaction-result'));await refresh();
    });button(label('拒绝','Deny'),()=>respond({decision:'deny'}),true);
   }catch(error){if(!live()||serial!==token)return;clear();appHeader();root.append(text('p',label('授权信息加载失败，操作尚未执行。可以重新加载授权信息或取消本次操作。','Access information could not be loaded. The operation has not executed. Reload access information or cancel this operation.')));button(label('重新加载授权信息','Reload access information'),load);button(label('取消本次操作','Cancel this operation'),()=>respond({decision:'deny'}),true);onError(error);}
  }
  load();return true;
 }
 function release(root,itemId){delete root.dataset.interactionState;root._botInteractionKey=null;root.hidden=true;root.classList?.remove?.('bot-app-access-card');if(itemId)window.AI2AppsParameterForms?.release(itemId);root.replaceChildren();}
 function answerForm({root,item,label,submit,onSubmitted,onError}){
  root.dataset.interactionState='waiting';
  const form=document.createElement('form'),prompt=document.createElement('p');prompt.textContent=item.prompt;form.append(prompt);
  const responseSchema=item.schema||item.response_schema||{};
  const choices=item.ui_hints?.options;
  const answerChoices=Array.isArray(choices)&&choices.length&&responseSchema.properties?.answer?.type==='string'&&!responseSchema.properties.answer.enum;
  const optionButtons=[];let answerField;
  if(answerChoices){const list=document.createElement('div');list.className='bot-question-options';list.setAttribute('role','group');list.setAttribute('aria-label',label('选择一个选项','Choose an option'));for(const value of choices){const choice=document.createElement('button');choice.type='button';choice.className='bot-question-option';choice.textContent=value;choice.setAttribute('aria-pressed','false');choice.onclick=()=>{if(busy||done)return;answerField.value=value;for(const b of optionButtons)b.setAttribute('aria-pressed',String(b===choice));};list.append(choice);optionButtons.push(choice);}form.append(list);}
  const fields=[];for(const [name,schema] of Object.entries(responseSchema.properties||{})){
   const wrapper=document.createElement('label');wrapper.textContent=name==='answer'?label(answerChoices?'或输入其他回答':'你的回答',answerChoices?'Or enter another answer':'Your answer'):(schema.title||name);
   const field=document.createElement(schema.enum?'select':schema.type==='boolean'?'input':'textarea');
   if(schema.enum)for(const value of schema.enum)field.add(new Option(String(value),String(value)));
   if(schema.type==='boolean')field.type='checkbox';field.required=responseSchema.required?.includes(name)||false;
   if(name==='answer'){answerField=field;field.oninput=()=>optionButtons.forEach(b=>b.setAttribute('aria-pressed','false'));}if(field.tagName==='TEXTAREA'){field.rows=3;field.style.resize='none';}
   wrapper.append(field);form.append(wrapper);fields.push([name,schema,field]);
  }
  const button=document.createElement('button');button.type='submit';button.textContent=label('提交回答','Submit answer');
  const status=document.createElement('p');status.setAttribute('role','status');form.append(button,status);root.append(form);
  let busy=false,done=false,attempt=null;
  form.onsubmit=async event=>{
   event.preventDefault();if(busy||done||!root.isConnected)return;
   const response={};for(const [name,schema,field] of fields)response[name]=schema.type==='boolean'?field.checked:['integer','number'].includes(schema.type)?Number(field.value):field.value;
   const signature=JSON.stringify(response);if(!attempt||attempt.signature!==signature)attempt={signature,id:crypto.randomUUID()};
   busy=true;button.disabled=true;[...fields.map(([, ,field])=>field),...optionButtons].forEach(field=>field.disabled=true);root.dataset.interactionState='submitting';button.textContent=label('正在提交…','Submitting…');status.textContent='';
   try{
    await submit(response,attempt.id);done=true;onSubmitted?.(item.id);
    if(!root.isConnected||root._botInteractionKey!==item.id)return;
    root.dataset.interactionState='submitted';button.hidden=true;
    [...fields.map(([, ,field])=>field),...optionButtons].forEach(field=>field.disabled=true);
    status.textContent=label('已收到回复，任务将继续处理。','Reply received. The task will continue.');
   }catch(error){if(root.isConnected&&root._botInteractionKey===item.id){root.dataset.interactionState='error';status.textContent=label('回复未确认送达，请重试。','Delivery was not confirmed. Please retry.');button.textContent=label('重试提交','Retry submission');button.disabled=false;[...fields.map(([, ,field])=>field),...optionButtons].forEach(field=>field.disabled=false);onError(error);}}
   finally{busy=false;}
  };
  return form;
 }
 window.AI2AppsBotInteractions={render,release,answerForm};
})();
