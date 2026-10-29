/* Hide uninitialized content until required application data is ready. */
(function(g){'use strict';
const lt=globalThis.MiniAppI18n?.text||(s=>s),it=globalThis.MiniAppI18n?.template||((parts,...values)=>parts.reduce((s,p,i)=>s+p+(i<values.length?values[i]:''),''));
 const zh=globalThis.MiniAppI18n?globalThis.MiniAppI18n.locale==='zh':/^zh/i.test(new URLSearchParams(location.search).get('locale')||document.documentElement.lang||'en');
 const panel=document.getElementById('startup'),message=document.getElementById('startup-message'),spinner=document.getElementById('startup-spinner'),retry=document.getElementById('startup-retry'),content=document.getElementById('app-content');
 let state='loading';
 message.textContent=zh?lt('正在加载一搜到底…'):lt('Loading Search All…');retry.textContent=zh?lt('重试'):lt('Retry');
 content.setAttribute('aria-busy','true');
 const timer=g.setTimeout(()=>fail(new Error(zh?lt('初始化超时，请重试。'):lt('Initialization timed out. Please retry.'))),45000);
 function fail(error){if(state!=='loading')return;state='failed';g.clearTimeout(timer);spinner.hidden=true;retry.hidden=false;message.textContent=(zh?lt('无法完成初始化：'):lt('Could not initialize: '))+(error?.message||String(error));}
 retry.onclick=()=>{retry.disabled=true;g.parent.postMessage({type:'ai2apps:mini-app-retry',version:1},'*');};
 g.addEventListener('error',event=>fail(event.error||new Error(zh?lt('启动脚本加载失败。'):lt('A startup script could not load.'))),true);
 g.addEventListener('unhandledrejection',event=>fail(event.reason));
 g.SearchAllStartup=Object.freeze({complete(){if(state!=='loading')return false;state='ready';g.clearTimeout(timer);content.removeAttribute('inert');content.setAttribute('aria-busy','false');content.hidden=false;panel.hidden=true;return true;},fail});
})(window);
