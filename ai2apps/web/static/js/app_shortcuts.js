/* ASC-Bot consumer of App-State: capture metadata and restore through the one binding. */
(()=>{
 'use strict';
 const sdk=window.AI2AppsAppState;if(!sdk)return;
 const text=(zh,en)=>(document.documentElement.lang||'').startsWith('zh')?zh:en;
 const mount=new URLSearchParams(location.hash.slice(1)),pending=new Map();let context=null,processing=false;
 async function api(path,method='GET',body){const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),15000);try{const response=await fetch('/v1/platform/app-shortcuts'+path,{method,signal:abort.signal,credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const value=await response.json();if(!response.ok)throw Error(value.detail?.message||value.detail||'Shortcut unavailable');return value;}finally{clearTimeout(timer);}}

 function host(method,detail={}){
  if(window.ai2appsShell?.openEntry&&method==='open-entry')return window.ai2appsShell.openEntry(detail);
  if(window.parent===window)throw Error(text('请在 AI2Apps 宿主内打开快捷入口','Open this shortcut inside the AI2Apps host'));
  const message={type:'ai2apps.shell.'+method,mountToken:mount.get('ai2apps-mount'),instanceId:mount.get('ai2apps-instance'),...detail};
  if(method!=='open-entry'){window.parent.postMessage(message,location.origin);return;}
  message.requestId=crypto.randomUUID();return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(message.requestId);reject(Error('Host request timed out'));},30000);pending.set(message.requestId,{resolve,reject,timer});window.parent.postMessage(message,location.origin);});
 }
 window.addEventListener('message',event=>{
  const m=event.data;if(event.source!==window.parent||event.origin!==location.origin||m?.mountToken!==mount.get('ai2apps-mount')||m.instanceId!==mount.get('ai2apps-instance'))return;
  if(m.type==='ai2apps.host.response'&&pending.has(m.requestId)){const p=pending.get(m.requestId);clearTimeout(p.timer);pending.delete(m.requestId);m.ok===false?p.reject(Error(m.error?.message||m.error||'Host rejected shortcut')):p.resolve(m.result);}
  if(m.type==='ai2apps.host.context'&&!window.ai2appsShell)receive(m);
 });
 function element(tag,value){const e=document.createElement(tag);if(value)e.textContent=value;return e;}
 function dialog(title){const d=element('dialog');d.className='app-state-dialog';d.append(element('h2',title));document.body.append(d);d.onclose=()=>d.remove();return d;}
 async function capture(binding,{name:initialName=''}={}){
  const packet=await binding.export(),d=dialog(text('创建快捷 Bot','Create shortcut Bot')),name=element('input'),notice=element('p');
  d.classList.add('app-shortcut-create');
  name.maxLength=64;name.required=true;name.value=initialName.trim().slice(0,64);
  name.placeholder=text('快捷 Bot 名称','Shortcut Bot name');name.setAttribute('aria-label',name.placeholder);
  const nameField=element('label',text('名称','Name'));nameField.className='asc-name-field';nameField.append(name);
  const avatar=element('fieldset'),legend=element('legend',text('Bot头像','Bot Avatar'));
  const preview=element('img'),summary=element('div'),selectedName=element('span');
  preview.alt=text('头像预览','Avatar preview');preview.className='asc-avatar-preview';
  summary.className='asc-avatar-summary';summary.append(preview,selectedName);
  const icons=element('div'),colors=element('div');
  icons.className='asc-avatar-icons';colors.className='asc-avatar-colors';
  icons.setAttribute('role','group');icons.setAttribute('aria-label',text('头像图标','Avatar icon'));
  colors.setAttribute('role','group');colors.setAttribute('aria-label',text('头像颜色','Avatar color'));
  let preset='spark',color='#6366f1';
  const iconButtons=new Map(),colorButtons=new Map();
  const customColor=element('input');customColor.type='color';customColor.value=color;
  customColor.setAttribute('aria-label',text('自定义头像颜色','Custom avatar color'));
  function paint(){
   const url=window.AI2AppsBotAvatars.url({avatar:{kind:'preset',preset,color}});
   preview.src=url;selectedName.textContent=iconButtons.get(preset).label;
   for(const [id,item] of iconButtons){
    item.button.setAttribute('aria-pressed',String(id===preset));
    item.image.src=window.AI2AppsBotAvatars.url({avatar:{kind:'preset',preset:id,color}});
   }
   for(const [value,button] of colorButtons)button.setAttribute('aria-pressed',String(value===color));
   customColor.value=color;
  }
  for(const [id,zh,en] of [
   ['spark','星星','Star'],['robot','机器人','Robot'],['orbit','轨道','Orbit'],['flower','花朵','Flower'],
   ['sun','太阳','Sun'],['moon','月亮','Moon'],['cat','猫','Cat'],['owl','猫头鹰','Owl'],
   ['leaf','叶子','Leaf'],['rocket','火箭','Rocket'],['compass','指南针','Compass'],['heart','爱心','Heart'],
  ]){
   const button=element('button'),image=element('img'),label=text(zh,en);
   button.type='button';button.setAttribute('aria-label',label);image.alt='';
   button.append(image);button.onclick=()=>{if(!busy){preset=id;paint();}};
   iconButtons.set(id,{button,image,label});icons.append(button);
  }
  for(const [value,zh,en] of [
   ['#6366f1','紫色','Purple'],['#2563eb','蓝色','Blue'],['#0891b2','青色','Cyan'],['#059669','绿色','Green'],
   ['#d97706','橙色','Orange'],['#db2777','粉色','Pink'],['#262626','深灰色','Charcoal'],
  ]){
   const button=element('button');button.type='button';button.style.backgroundColor=value;
   button.setAttribute('aria-label',text(zh,en));button.onclick=()=>{if(!busy){color=value;paint();}};
   colorButtons.set(value,button);colors.append(button);
  }
  customColor.oninput=()=>{if(!busy){color=customColor.value;paint();}};
  const custom=element('label',text('自定义','Custom'));custom.className='asc-custom-color';custom.append(customColor);colors.append(custom);
  avatar.append(legend,summary,icons,colors);
  d.append(element('p',text('给这套常用设置起个名字，再选一个头像。','Name your shortcut and choose an avatar.')),nameField,avatar,notice);
  const save=element('button',text('创建 Bot','Create Bot')),cancel=element('button',text('取消','Cancel'));const requestId=crypto.randomUUID();let snapshot=null,busy=false;
  cancel.onclick=()=>{if(!busy)d.close();};save.onclick=async()=>{if(busy||!name.reportValidity())return;if(!snapshot)snapshot={source_instance_id:binding.instanceId,packet,name:name.value.trim(),avatar:{kind:'preset',preset,color},request_id:requestId};busy=true;save.disabled=cancel.disabled=true;name.disabled=avatar.disabled=true;try{await api('/bots','POST',snapshot);notice.textContent=text('已创建，可在 Messager 的 Bot 列表中打开。','Created. Open it from the Bot list in Messager.');save.hidden=true;cancel.textContent=text('关闭','Close');}catch(e){notice.textContent=text('创建结果未确认，可重试确认同一次创建：','Creation is unconfirmed; retry to confirm the same request: ')+e.message;}finally{busy=false;cancel.disabled=false;save.disabled=false;}};
  const actions=element('div');actions.className='asc-create-actions';save.className='asc-create-primary';actions.append(cancel,save);
  d.addEventListener('cancel',e=>{if(busy)e.preventDefault();});d.append(actions);paint();d.showModal();name.focus();name.setSelectionRange(name.value.length,name.value.length);
 }
 async function open(botId){const launch=await api('/bots/'+encodeURIComponent(botId)+'/launch','POST',{request_id:crypto.randomUUID()});return host('open-entry',{appId:launch.target.app_id,appStateLaunch:launch.id});}
 let seen=new Set();
 function receive(value){if(value?.appStateLaunch&&value.instanceId){context=value;void consume();}}
 async function consume(){
  if(processing||!context||seen.has(context.appStateLaunch))return;const intent=context;const targets=sdk.targets().filter(t=>t.instanceId===intent.instanceId);if(!targets.length)return;
  processing=true;seen.add(intent.appStateLaunch);
  let binding=null,packet=null;
  try{
   const value=await api('/launches/'+encodeURIComponent(intent.appStateLaunch)+'/claim','POST',{instance_id:intent.instanceId});packet=value.packet;
   binding=sdk.binding(intent.instanceId,packet.target);if(!binding)throw Error(text('当前界面不支持这个快捷设置','This view does not support this shortcut target'));
   await binding.activate();await binding.restore(packet,{requestId:'asc-'+intent.appStateLaunch+'-'+crypto.randomUUID(),confirmConflict:sdk.confirmConflict});
   host('ack-app-state',{launchId:intent.appStateLaunch});
  }catch(error){
   const d=dialog(text('快捷入口需要处理','Shortcut needs attention')),message=element('p',error.message),close=element('button',text('关闭','Close'));close.onclick=()=>d.close();d.append(message);
   if(binding?.configureDependencies&&error.code==='dependency_unavailable'){const setup=element('button',text('配置所需能力','Set up capabilities'));setup.onclick=async()=>{setup.disabled=true;d.close();let result=text('配置后请重试；仍将检查原来的模型和设置。','Retry after setup. The original model and settings will still be checked.');try{await binding.configureDependencies();}catch(e){result=e.message;}const follow=dialog(text('继续快捷入口','Continue shortcut')),again=element('button',text('重试恢复','Retry restore')),dismiss=element('button',text('关闭','Close'));again.onclick=()=>{seen.delete(intent.appStateLaunch);follow.close();context=intent;void consume();};dismiss.onclick=()=>follow.close();follow.append(element('p',result),again,dismiss);follow.showModal();};d.append(setup);}
   const retry=element('button',text('重试恢复','Retry restore'));retry.onclick=()=>{seen.delete(intent.appStateLaunch);d.close();context=intent;void consume();};d.append(retry,close);d.showModal();
  }finally{processing=false;if(context!==intent)void consume();}
 }
 window.addEventListener('ai2apps:host-context',e=>receive(e.detail));window.addEventListener('ai2apps:app-state-registered',()=>{void consume();});
 window.AI2AppsAppShortcuts=Object.freeze({capture,open});
 // Mobile trusted App templates may not load the desktop bridge.
 if(window.parent!==window)host('ready');
})();
