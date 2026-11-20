/* Settings owns the global Event/Hook view; the existing owner APIs retain authority. */
(function(){
 'use strict';
 window.AI2AppsEventHooksLabel=(document.documentElement.lang||navigator.language||'').startsWith('zh')?'事件/响应':'Event/Hook';
 window.ai2appsSettingsEventHooks=()=>({
  ...window.ai2appsHookMonitoring(),bots:[],hookActive:false,hookPoll:null,
  tr(key){return typeof window.t==='function'?window.t(key):key;},
  formatTime(value){return value?new Date(value).toLocaleString():'';},
  async hooksLoadBots(){
   try{const r=await fetch('/v1/platform/messager/bots',{credentials:'same-origin',cache:'no-store'});if(r.ok)this.bots=(await r.json()).items||[];}
   catch(_){/* Bot labels are optional; App/Mini-App rules still render. */}
  },
  hooksSetActive(active){
   if(this.hookActive===active)return;
   this.hookActive=active;clearInterval(this.hookPoll);this.hookPoll=null;
   if(active){this.hooksLoadBots();this.hooksLoad();this.hookPoll=setInterval(()=>{if(!document.hidden)this.hooksLoad();},5000);}
  },
  destroy(){clearInterval(this.hookPoll);this.hookPoll=null;},
 });
})();
