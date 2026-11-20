/* Draft-only creation UI shared by Desktop sidebar and Mobile. */
(()=>{
'use strict';
const label=(zh,en)=>(document.documentElement.lang||'').startsWith('zh')?zh:en;
function node(tag,text,cls){const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;}
function menu(anchor,{onChoose,onClose,onAddGroup,below=false,grouped=false}){
 const root=node('div',null,'bc-type-menu'+(below?' below':''));root.setAttribute('role','menu');root.setAttribute('aria-label',label('选择 Bot 类型','Choose Bot type'));
 for(const [id,name,description] of [['standard',label('标准 Bot','Standard Bot'),label('对话与任务助手','Conversation and task assistant')],['research',label('研究 Bot','Research Bot'),label('从网页研究模板创建','Start with the web research template')],['flash','Flash-Bot',label('固定输入与工作流','Fixed input and workflow')],['asc','ASC-Bot',label('App / Mini-App 快捷入口','App / Mini-App shortcut')],['outlet','Outlet-Bot',label('外部会话代理','External conversation proxy')],['mirror','Mirror-Bot',label('远端 Bot 映射','Remote Bot mirror')]]){
  if (grouped && !['standard','research','flash'].includes(id)) continue;
  const b=node('button');b.type='button';b.setAttribute('role','menuitem');b.disabled=!['standard','research','flash','asc'].includes(id);b.append(node('strong',name),node('small',description+(['standard','research','flash','asc'].includes(id)?'':label(' · 暂未开放',' · Coming later'))));b.onclick=()=>{close.dispose();onChoose(id);};root.append(b);
 }
 if(onAddGroup){const b=node('button',label('新建分组','New group'));b.type='button';b.setAttribute('role','menuitem');b.className='bc-group-menu-item';b.onclick=()=>{close.dispose();onAddGroup();};root.append(b);}
 const close = showMenu(anchor, root, onClose, grouped);
 return close;
}
function groupMenu(anchor, {onCreate, onRename, onDelete, onClose}) {
 return actionMenu(anchor, label('分组操作', 'Group actions'), [
  [label('在此分组创建新Bot', 'Create Bot in this group'), onCreate],
  [label('重新命名分组', 'Rename group'), onRename],
  [label('删除分组', 'Delete group'), onDelete],
 ], onClose);
}
function shortcutMenu(anchor, {onRename, onDelete, onClose}) {
 return actionMenu(anchor, label('快捷 Bot 操作', 'Shortcut Bot actions'), [
  [label('改名', 'Rename'), onRename],
  [label('删除', 'Delete'), onDelete],
 ], onClose, ' bc-shortcut-menu');
}
function actionMenu(anchor, title, actions, onClose, extraClass='') {
 const root = node('div', null, 'bc-type-menu below'+extraClass);
 root.setAttribute('role', 'menu');
 root.setAttribute('aria-label', title);
 for (const [title, action] of actions) {
  const item = node('button', title);
  item.type = 'button';
  item.setAttribute('role', 'menuitem');
  item.onclick = () => { close.dispose(); anchor.focus({preventScroll:true}); action(); };
  root.append(item);
 }
 root.addEventListener('keydown', event => {
  const items = [...root.querySelectorAll('[role="menuitem"]')];
  const current = items.indexOf(event.target);
  const next = {ArrowDown:(current+1)%items.length,ArrowUp:(current+items.length-1)%items.length,
   Home:0,End:items.length-1}[event.key];
  if (next === undefined) return;
  event.preventDefault();
  items[next].focus({preventScroll:true});
 });
 const close = showMenu(anchor, root, onClose, true);
 return close;
}
function showMenu(anchor, root, onClose, floating) {
 if (floating) {
  const bounds = anchor.getBoundingClientRect();
  Object.assign(root.style, {position:'fixed', left:'auto', right:'auto', top:'0', bottom:'auto'});
  document.body.append(root);
  const {width,height} = root.getBoundingClientRect();
  root.style.left = Math.max(6, bounds.right - width) + 'px';
  root.style.top = Math.max(6, bounds.bottom + 6 + height <= window.innerHeight
   ? bounds.bottom + 6 : bounds.top - height - 6) + 'px';
 } else {
  anchor.parentElement.append(root);
 }
 anchor.setAttribute('aria-expanded','true');
 const outside=e=>{if(!root.contains(e.target)&&!anchor.contains(e.target))dispose();},key=e=>{if(e.key==='Escape'){dispose();anchor.focus();}};
 document.addEventListener('pointerdown',outside);document.addEventListener('keydown',key);
 if (floating) document.addEventListener('scroll',dispose,true);
 root.querySelector('button').focus({preventScroll:true});
 function dispose(){root.remove();anchor.setAttribute('aria-expanded','false');document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',key);document.removeEventListener('scroll',dispose,true);onClose?.();}
 return {dispose};
}
function mount(host,{request,models,onCancel,onCreated,botType='standard'}){
 if(botType==='asc'){
  const box=node('section',null,'bc-create bc-shortcut-guide');
  const header=node('header'),body=node('div',null,'bc-body'),footer=node('footer');
  header.append(node('h2',label('创建快捷 Bot','Create shortcut Bot')),
   node('p',label('保存常用设置，下次一键打开。','Save your settings for quick access.')));
  const steps=node('ol',null,'bc-shortcut-steps');
  for(const [title,description] of [
   [label('打开目标 App','Open an App'),label('进入你要使用的 App 或 Mini-App。','Go to the App or Mini-App you want to use.')],
   [label('调好常用设置','Configure your settings'),label('选好模型和其他参数。','Choose your model and other settings.')],
   [label('保存为快捷 Bot','Save as a shortcut Bot'),label('打开“状态预设”，选择“创建快捷 Bot”。','Open State presets and choose Create shortcut Bot.')],
  ]){
   const step=node('li');
   step.append(node('strong',title),node('p',description));
   steps.append(step);
  }
  body.append(steps,node('p',label('创建后，它会出现在 Bot 列表中。','Your shortcut will appear in the Bot list.'),'bc-shortcut-note'));
  const back=node('button',label('返回 Bot 列表','Back to Bots'));
  back.type='button';back.onclick=onCancel;footer.append(back);
  if(window.ai2appsShell?.openLauncher){
   const open=node('button',label('选择 App','Choose an App'),'bc-primary');
   open.type='button';
   open.onclick=()=>window.ai2appsShell.openLauncher();
   footer.append(open);
  }
  box.append(header,body,footer);host.replaceChildren(box);
  return {dispose(){host.replaceChildren();}};
 }
 const research=botType==='research',flash=botType==='flash';if(!['standard','research','flash'].includes(botType))throw Error('Bot type unavailable');
 let disposed=false,options=null,choices=new Set(),busy=false,pending=null,compiled=null,initialized=false,modelTouched=false,dutyTouched=false;
 const requestId=crypto.randomUUID(),form=node('form',null,'bc-create'),header=node('header'),body=node('fieldset',null,'bc-body'),footer=node('footer'),notice=node('p',null,'bc-error');notice.setAttribute('role','status');
 header.append(node('h2',flash?label('创建 Flash-Bot','Create Flash-Bot'):research?label('创建研究 Bot','Create Research Bot'):label('创建标准 Bot','Create standard Bot')),node('p',flash?label('描述固定工作流，生成并审阅后启用。','Describe a fixed workflow, then generate and review it.'):research?label('已预填研究职责和权限，你可以按需要修改。','Customize the suggested research Role and access.'):label('设置身份、模型和可访问的 App。','Set its profile, model and App access.')));
 const avatar=node('img',null,'bc-avatar'),preset=node('select'),color=node('input');color.type='color';color.value='#6366f1';preset.setAttribute('aria-label',label('头像样式','Avatar style'));color.setAttribute('aria-label',label('头像颜色','Avatar color'));
 for(const id of ['spark','robot','orbit','flower','sun','moon','cat','owl','leaf','rocket','compass','heart'])preset.add(new Option(id==='spark'?'Star':id[0].toUpperCase()+id.slice(1),id));
 const avatarRow=node('div',null,'bc-avatar-row');avatarRow.append(avatar,preset,color);const paint=()=>avatar.src=window.AI2AppsBotAvatars.url({avatar:{kind:'preset',preset:preset.value,color:color.value}});preset.onchange=color.oninput=paint;paint();
 const name=node('input'),duty=node('textarea'),model=node('select');name.required=true;name.maxLength=64;name.autocomplete='off';duty.required=true;duty.maxLength=600;duty.rows=4;model.add(new Option(label('使用默认模型','Use default model'),''));model.onchange=()=>{modelTouched=true;compiled=null;};
 const field=(title,input)=>{const l=node('label',title,'bc-field');l.append(input);body.append(l);};field(label('Bot头像','Bot Avatar'),avatarRow);field(label('名字','Name'),name);field(label('职责','Role'),duty);field(flash?label('执行模型','Execution model'):label('对话模型','Conversation model'),model);
 const workflow=node('select');workflow.setAttribute('aria-label',label('固定工作流','Fixed workflow'));if(flash){field(label('固定工作流','Fixed workflow'),workflow);workflow.add(new Option(label('自定义工作流（根据职责生成）','Custom workflow from Role'),'custom'));}
 const chooseWorkflow=()=>{compiled=null;duty.readOnly=false;model.disabled=flash&&workflow.value!=='custom';access.hidden=flash&&workflow.value!=='custom';if(workflow.value==='custom'){duty.placeholder=label('例如：把输入文本翻译成日文，只返回译文。','For example: translate input into Japanese and return only the translation.');updateCreate();return;}const w=options?.flash_workflows?.find(w=>w.id===workflow.value);if(w){if(!name.value.trim())name.value=label(w.name,w.name_en);duty.value=w.description;updateCreate();}};workflow.onchange=chooseWorkflow;
 const access=node('section',null,'bc-access'),search=node('input'),rows=node('div'),reload=node('button',label('重新加载权限目录','Reload access catalog'),'bc-link');search.type='search';search.placeholder=label('搜索 App / Mini-App','Search Apps / Mini-Apps');search.setAttribute('aria-label',search.placeholder);reload.type='button';access.append(node('h3','App Access'),node('p',label('选择此 Bot 可访问的 App 和 Mini-App。特殊操作仍需确认。','Choose allowed Apps and Mini-Apps. Special operations still require confirmation.')),search,rows,reload);body.append(access);
 const cancel=node('button',label('取消创建','Cancel'),'bc-cancel'),create=node('button',label('创建 Bot','Create Bot'),'bc-primary');cancel.type='button';create.type='submit';create.disabled=true;cancel.onclick=()=>{if(!busy&&!pending)onCancel();};footer.append(cancel,create);form.append(header,body,notice,footer);host.replaceChildren(form);
 function updateCreate(){create.disabled=busy||(!pending&&(!options||!name.value.trim()||!duty.value.trim()));}name.oninput=updateCreate;duty.oninput=()=>{dutyTouched=true;compiled=null;if(flash&&workflow.value!=='custom'){workflow.value='custom';model.disabled=false;access.hidden=false;}updateCreate();};
 function renderAccess(){rows.replaceChildren();if(!options)return;const q=search.value.trim().toLowerCase();for(const kind of ['app','mini-app','unavailable']){const entries=options.access.items.filter(a=>a.kind===kind&&(!q||(a.name+' '+(a.owner_name||'')).toLowerCase().includes(q)));if(!entries.length)continue;rows.append(node('h4',kind==='mini-app'?'Mini-App':kind==='unavailable'?label('暂不可用','Unavailable'):'App'));for(const app of entries){const row=node('label',null,'bc-access-row'),check=node('input'),text=node('span');check.type='checkbox';check.checked=choices.has(app.app_id);check.disabled=!app.available&&!app.enabled&&!choices.has(app.app_id);check.onchange=()=>{compiled=null;if(check.checked)choices.add(app.app_id);else{choices.delete(app.app_id);if(!app.available&&!app.enabled)check.disabled=true;}};text.append(node('strong',app.name),node('small',app.kind==='mini-app'?app.owner_name||'':!app.available?label('暂不可用','Unavailable'):''));row.append(check,text);rows.append(row);}}}
 search.oninput=renderAccess;
 async function load(){reload.disabled=true;try{const v=await request('/options');if(disposed)return;const template=research?v.templates?.find(x=>x.id==='research'):null;if(research&&!template)throw Error(label('研究模板暂不可用，请重新加载。','Research template unavailable. Reload to try again.'));options=v;if(!initialized){if(template){if(!name.value.trim())name.value=label(template.name.zh,template.name.en);if(!dutyTouched)duty.value=label(template.role.zh,template.role.en);preset.value=template.avatar.preset;color.value=template.avatar.color;paint();}choices=new Set(flash?[]:template?template.app_ids:v.access.items.filter(a=>a.selected&&a.enabled).map(a=>a.app_id));if(flash){for(const w of v.flash_workflows||[])workflow.add(new Option(label(w.name,w.name_en),w.id));workflow.value='custom';chooseWorkflow();}if(!flash&&!research&&!dutyTouched)duty.value=v.default_duty;initialized=true;}else choices=new Set([...choices].filter(id=>v.access.items.some(a=>a.app_id===id)));renderAccess();updateCreate();notice.textContent='';}catch(e){if(!disposed)notice.textContent=e.message;}finally{reload.disabled=false;}}
 reload.onclick=()=>load();void load();
 void Promise.resolve().then(()=>models?.()).then(v=>{if(disposed||!v)return;for(const m of v.models||[])model.add(new Option(m.name||m.display_name||m.id,m.id));if(v.selected&&!modelTouched&&!pending&&!busy)model.value=v.selected;}).catch(()=>{});
 form.onsubmit=async event=>{event.preventDefault();if(busy||!options||!form.reportValidity())return;
  if(flash&&workflow.value==='custom'&&!compiled){try{busy=true;create.disabled=true;notice.textContent=label('正在生成固定工作流…','Generating workflow…');body.disabled=true;compiled=await reviewWorkflow({request,role:duty.value.trim(),model:model.value,apps:[...choices].sort().map(app_id=>({app_id,enabled:true}))});if(!compiled)return;}catch(e){notice.textContent=e.message;return;}finally{busy=false;body.disabled=false;updateCreate();}}
  if(!pending)pending={request_id:requestId,bot_type:research?'standard':botType,...(research?{template_id:'research'}:{}),...(flash?{definition:{schema_version:1,execution_mode:'flash',audience:'owner',location:'local',config:compiled?.config||{workflow_id:workflow.value,workflow_version:options.flash_workflows.find(w=>w.id===workflow.value).version}}}:{}),name:name.value.trim(),duty:duty.value.trim(),avatar:{kind:'preset',preset:preset.value,color:color.value},model_id:flash&&workflow.value!=='custom'?null:model.value||null,apps:[...(flash&&workflow.value!=='custom'?[]:choices)].sort().map(app_id=>({app_id,enabled:true})),access_review_hash:options.access.review_hash};
  busy=true;body.disabled=true;cancel.disabled=true;create.disabled=true;create.textContent=label('正在创建…','Creating…');notice.textContent='';
  try{const result=await request('/submit','POST',pending);if(disposed)return;pending=null;onCreated(result);}catch(e){if(disposed)return;const known=e.status>=400&&e.status<500;if(known){pending=null;body.disabled=false;cancel.disabled=false;}notice.textContent=known?e.message:label('创建结果暂未确认，请重试以确认同一次创建。','Creation result is unconfirmed. Retry to confirm the same request.');create.textContent=known?label('创建 Bot','Create Bot'):label('重试确认','Retry');create.disabled=false;}finally{busy=false;if(!disposed)updateCreate();}
 };
 queueMicrotask(()=>{if(!disposed)name.focus();});return {dispose({preserveDOM=false}={}){disposed=true;if(!preserveDOM)host.replaceChildren();}};
}

async function reviewWorkflow({request,role,model,apps,draft:preparedDraft,previousPlan}){
 if(!model)throw Error(label('请选择执行模型','Choose an execution model'));
 const draft=preparedDraft||await request('/flash-workflows/compile','POST',{role,model,apps});
 const dialog=node('dialog',null,'bc-review');dialog.setAttribute('aria-label',label('审阅固定工作流','Review fixed workflow'));
 const header=node('header'),mark=node('span',null,'bc-review-mark'),intro=node('div');
 const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');icon.setAttribute('viewBox','0 0 24 24');icon.setAttribute('width','26');icon.setAttribute('height','26');icon.setAttribute('fill','none');icon.setAttribute('stroke','currentColor');icon.setAttribute('stroke-width','1.8');icon.setAttribute('aria-hidden','true');const bolt=document.createElementNS('http://www.w3.org/2000/svg','path');bolt.setAttribute('d','M13 2 4 14h7l-1 8 10-12h-7z');icon.append(bolt);mark.append(icon);
 intro.append(node('small','FLASH-BOT'),node('h2',draft.plan.name||label('审阅固定工作流','Review fixed workflow')),node('p',label('确认每次输入后将执行的固定流程。','Review what runs each time you submit input.')));header.append(mark,intro);
 const body=node('div',null,'bc-review-body'),overview=node('section',null,'bc-review-overview');overview.append(node('h3',label('这个 Bot 会做什么','What this Bot does')),node('p',draft.plan.usage));body.append(overview);
 if(previousPlan){const changes=node('section',null,'bc-review-overview');changes.append(node('h3',label('本次修改','Proposed changes')),node('p',label('原流程：','Current: ')+previousPlan.usage),node('p',label('修改后的职责：','Revised Role: ')+role));body.append(changes);}
 const inputNames={text:label('文本','Text'),expression:label('数学表达式','Math expression'),files:label('附件文件','Files'),text_files:label('文本和附件','Text and files')};
 const badge=node('div',null,'bc-review-input');badge.append(node('span',label('输入','Input')),node('strong',inputNames[draft.plan.input_kind]||draft.plan.input_kind));body.append(badge);
 body.append(node('h3',label('执行步骤','Workflow steps')));
 const list=node('ol',null,'bc-review-steps');for(const [i,step] of draft.plan.steps.entries()){
  const item=node('li'),number=node('span',String(i+1),'bc-review-number'),card=node('div',null,'bc-review-step');
  const display=draft.review_steps?.[i]?.name;const stepName=typeof display==='string'?display:display?.[(document.documentElement.lang||'').startsWith('zh')?'zh':'en'];
  card.append(node('strong',stepName||(step.kind==='ai'?label('AI 处理','AI transformation'):step.kind==='calculate'?label('计算结果','Calculate'):label('应用操作','App operation'))));
  card.append(node('p',step.instruction||(i?label('接收上一步结果，按预设参数继续处理。','Process the previous result using the fixed settings.'):label('使用本次输入，按预设参数处理。','Process this input using the fixed settings.'))));
  const details=node('details'),summary=node('summary',label('查看操作与参数','View operation and settings')),pre=node('pre');pre.textContent=JSON.stringify({...(step.capability?{capability:step.capability}:{}),...(step.provider?{provider:step.provider}:{}),arguments:step.arguments||{}},null,2);details.append(summary,pre);card.append(details);item.append(number,card);list.append(item);
 }body.append(list);
 if(draft.plan.adapt_input)body.append(node('p',label('输入不匹配时，先由 AI 尝试转换，再重新校验。','Mismatched input is adapted by AI, then validated again.'),'bc-review-note'));
 body.append(node('p',label('特殊操作仍需确认；AI 用量按所选模型计费。启用后仅影响新提交，已排队和正在执行的任务保持原版本。','Special operations still need confirmation. AI usage follows the selected model. Existing queued and running tasks keep their version.'),'bc-review-note'));
 const footer=node('footer'),cancel=node('button',label('返回修改','Edit'),'bc-review-secondary'),accept=node('button',label('确认工作流','Confirm workflow'),'bc-review-primary');cancel.type=accept.type='button';footer.append(cancel,accept);dialog.append(header,body,footer);document.body.append(dialog);dialog.showModal();
 return await new Promise(resolve=>{const finish=v=>{dialog.close();dialog.remove();resolve(v);};cancel.onclick=()=>finish(null);dialog.oncancel=e=>{e.preventDefault();finish(null);};accept.onclick=()=>finish({review_id:draft.review_id,config:{workflow_id:'custom',workflow_version:draft.review_id.slice(0,32),plan:draft.plan,model,review_id:draft.review_id}});});
}
async function reviewConversation({response,botId,sessionId,request}){
 if(response.kind!=='workflow_review')return null;
 const draft=response.draft;
 const accepted=await reviewWorkflow({request,...draft,draft,previousPlan:response.previous_plan});
 if(!accepted)return null;
 const definition=await request('/bots/'+encodeURIComponent(botId)+'/flash-workflow','POST',{role:draft.role,model:draft.model,apps:draft.apps,review_id:draft.review_id,expected_revision:response.expected_revision,session_id:sessionId});
 return {definition,duty:draft.role};
}
window.AI2AppsBotCreation={menu,groupMenu,shortcutMenu,mount,reviewWorkflow,reviewConversation};
})();
