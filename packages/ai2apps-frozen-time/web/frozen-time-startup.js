(() => {
 'use strict';
 let timer, currentStage='connecting';
 const get=id=>document.getElementById(id);
 const messages={
  connecting:['正在连接创意画坊…','Connecting to Imagine Studio…'],
  restoring:['正在恢复设置…','Restoring settings…'],
  models:['正在检查模型…','Checking models…'],
  failed:['启动未完成，请重试。','Startup could not complete. Please retry.']
 };
 function stage(name){currentStage=name;const labels=messages[name]||messages.connecting;get('startup-zh').textContent=labels[0];get('startup-en').textContent=labels[1];}
 function fail(error){clearTimeout(timer);if(!get('startup'))return;const failedStage=currentStage;stage('failed');let detail=get('startup-detail');if(!detail){detail=document.createElement('p');detail.id='startup-detail';detail.style.cssText='max-width:100%;padding:0 20px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px';get('startup').appendChild(detail);}detail.textContent=(messages[failedStage]||messages.connecting).join(' / ')+'\n'+String(error?.message||error||'连接超时 / Connection timed out').slice(0,500);get('startup').classList.add('failed');get('startup-retry').hidden=false;get('startup').setAttribute('aria-busy','false');}
 function ready(){clearTimeout(timer);get('app-ui').hidden=false;get('startup').hidden=true;window.dispatchEvent(new Event('frozen-curve-change-view'));}
 window.frozenStartup={stage,fail,ready};
 document.addEventListener('DOMContentLoaded',()=>{get('startup-retry').onclick=()=>location.reload();timer=setTimeout(()=>fail(),30000);});
 // Keep uninitialized controls hidden even when a required script fails to load.
 window.addEventListener('error',event=>{if(get('app-ui')?.hidden)fail(event?.error||'脚本或资源加载失败 / Script or resource failed to load');});
})();
