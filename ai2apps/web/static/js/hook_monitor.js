/* Host-only system Event/Hook controls. Text is rendered through x-text. */
(function(){
 'use strict';
 async function api(path,options={}){
  const r=await fetch('/v1/platform'+path,{credentials:'same-origin',cache:'no-store',...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});
  const value=await r.json();if(!r.ok)throw new Error(value.detail?.message||value.detail||'Request failed');return value;
 }
 window.ai2appsHookMonitoring=()=>({
  hookMonitor:null,hookNotices:[],hookActionCatalog:[],hookSteps:null,hookError:'',hookBusy:false,hookForm:false,hookPreview:null,hookEnableRequest:'',
  packageHookRequests:[],packageHookGrants:[],
  hookConsentText(key){return window.AI2AppsHookConsent?.text(key)||({pending:'Pending Package requests',grants:'Package event permissions',review:'Review permissions',revoke:'Revoke permission',until:'Permission expires'}[key]||key);},
  async hooksReviewPackage(item){try{await window.AI2AppsHookConsent.review(item.id);await this.hooksLoad();}catch(e){this.hookError=String(e.message);}},
  async hooksRevokePackage(item){try{await api('/package-hooks/grants/'+item.id+'/revoke',{method:'POST'});await this.hooksLoad();}catch(e){this.hookError=String(e.message);}},
  hookChannels:[],hookModels:[],hookDraft:{bot:'',channel:'',model:'',prompt:'',todo:false,notify:true,urgent:false,title:'',hours:24},
  async hooksLoad(){
   try{const [status,notices,actions,requests,grants]=await Promise.all([api('/hooks/monitor'),api('/hooks/notices'),api('/hooks/actions'),api('/package-hooks/requests'),api('/package-hooks/grants')]);this.hookMonitor=status;this.hookNotices=notices.items;this.hookActionCatalog=actions.items;this.packageHookRequests=(requests.items||[]).filter(x=>x.state==='pending');this.packageHookGrants=grants.items||[];this.hookError='';}
   catch(e){this.hookError=String(e.message);}
  },
  async hooksForm(){
   this.hookForm=!this.hookForm;this.hookPreview=null;if(!this.hookForm)return;
   try{
    const [intel,models,manager]=await Promise.all([api('/intelligence?view=channels'),fetch('/v1/models',{credentials:'same-origin'}).then(r=>r.json()),fetch('/admin/api/model-manager',{credentials:'same-origin'}).then(r=>r.json())]);
    this.hookChannels=intel.channels||[];this.hookModels=(models.data||[]).filter(x=>!x.id.includes('image'));
    this.hookDraft.bot=this.currentBot?.id||this.bots[0]?.id||'';this.hookDraft.channel=this.hookChannels[0]?.id||'';
    this.hookDraft.model=manager.defaults?.work_standard||'';
   }catch(e){this.hookError=String(e.message);}
  },
  hookRuleName(rule){const bot=this.bots.find(x=>x.id===rule.consumer?.binding?.bot_id);return bot?.name||rule.consumer?.binding?.display_name||rule.consumer?.registration||'';},
  hookActionName(id){return this.hookActionCatalog.find(x=>x.registration===id)?.title||id;},
  hookState(state){return this.tr('messager.hooks.state.'+state);},
  async hooksChange(rule,action){
   this.hookBusy=true;
   try{await api('/hooks/'+rule.id+'/'+action,{method:'POST',body:JSON.stringify({expected_revision:rule.revision,request_id:crypto.randomUUID()})});await this.hooksLoad();}
   catch(e){this.hookError=String(e.message);}finally{this.hookBusy=false;}
  },
  async hooksPreviewPlan(){
   this.hookBusy=true;this.hookError='';
   try{
    const d=this.hookDraft;const actions=[];
    if(d.todo)actions.push({registration:'todo.create',arguments:{title:d.title||this.tr('messager.hooks.todo_title'),directory_id:null,include_review:true}});
    if(d.notify)actions.push({registration:'notification.local',arguments:{title:this.tr('messager.hooks.notice_title'),include_review:true}});
    this.hookPreview=await api('/hooks/preview',{method:'POST',body:JSON.stringify({consumer:{registration:'messager.bot.observe',binding:{bot_id:d.bot}},event_type:'intelligence.channel.refresh_finished',subjects:[d.channel],filters:[{field:'status',op:'eq',value:'completed'},{field:'added_count',op:'gt',value:0}],execution:{settings:{model:d.model,prompt:d.prompt||this.tr('messager.hooks.default_prompt'),actions,review:d.urgent?'urgency':'summary'},expires_in:Number(d.hours)*3600}})});this.hookEnableRequest=crypto.randomUUID();
   }catch(e){this.hookError=String(e.message);}finally{this.hookBusy=false;}
  },
  async hooksEnable(){
   if(!this.hookPreview)return;this.hookBusy=true;
   try{await api('/hooks',{method:'POST',body:JSON.stringify({preview_ref:this.hookPreview.preview_ref,request_id:this.hookEnableRequest})});this.hookPreview=null;this.hookForm=false;await this.hooksLoad();}
   catch(e){this.hookError=String(e.message);}finally{this.hookBusy=false;}
  },
  async hooksInspect(delivery){try{this.hookSteps=(await api('/hooks/deliveries/'+delivery.id+'/steps')).items;}catch(e){this.hookError=String(e.message);}},
  async hooksRead(notice){try{await api('/hooks/notices/'+notice.id+'/read',{method:'POST'});await this.hooksLoad();}catch(e){this.hookError=String(e.message);}},
 });
})();
