/* Preparation is shared with Agentic Chat. This UI only observes backend Tasks/Runs. */
(() => {
 'use strict';
 globalThis.SearchAllSharedWorkflow=true;
 const $=id=>document.getElementById(id),zh=()=>document.documentElement.lang.startsWith('zh'),text=(a,b)=>zh()?a:b;
 let preparation=null,ready=false,busy=false,active=false,original='',restoring=false,summarizing=false,chatRequest='',submission=null,quick=null;
 const selected=()=>[...document.querySelectorAll('input[name=source]:checked')].map(n=>n.value);
 const choose=ids=>document.querySelectorAll('input[name=source]').forEach(n=>{n.checked=ids.includes(n.value);});
 const delay=()=>new Promise(resolve=>setTimeout(resolve,800));
 const settings=()=>({query:$('query').value.trim(),mode:$('mode').value,sources:$('mode').value==='fast'?[preparation.fast_source]:selected(),limit:Number($('limit').value),profile:$('profile').value,preparation_id:preparation.id,x_sort:$('x-sort').value,xiaohongshu_sort:$('xhs-sort').value,exclude_ads:$('exclude-ads').checked,retain_pages:$('retain-pages').checked});
 async function askCloud(message,acceptLabel){
  const dialog=document.createElement('dialog'),title=document.createElement('h2'),body=document.createElement('p'),actions=document.createElement('div'),cancel=document.createElement('button'),accept=document.createElement('button');
  title.textContent='DeepSeek Cloud';body.textContent=message;actions.className='dialog-actions';cancel.type=accept.type='button';cancel.textContent=MiniAppI18n.text('Cancel');accept.textContent=acceptLabel;accept.className='primary';actions.append(cancel,accept);dialog.append(title,body,actions);document.body.append(dialog);
  return await new Promise(resolve=>{let decided=false;const finish=value=>{if(decided)return;decided=true;dialog.close();dialog.remove();resolve(value);};cancel.onclick=()=>finish(false);accept.onclick=()=>finish(true);dialog.oncancel=event=>{event.preventDefault();finish(false);};dialog.showModal();cancel.focus();});
 }
 globalThis.SearchAllAskCloud=askCloud;
 async function save(){if(restoring)return;await AI2AppsWebAgent.saveDraft({schema:'ai2apps.mini-app-draft/v1',miniApp:'ai2apps.search-all',workflowSchema:'search-workflow/v1',submission,preparation,ready,active,summarizing,original,query:$('query').value,mode:$('mode').value,sources:selected(),limit:Number($('limit').value),profile:$('profile').value,x_sort:$('x-sort').value,xiaohongshu_sort:$('xhs-sort').value,exclude_ads:$('exclude-ads').checked});}
 function display(){
  const fast=$('mode').value==='fast';$('mode-controls').hidden=!ready;$('mode-controls').dataset.compact='false';
  for(const id of ['source-options','limit-control','custom-settings','custom-hint'])$(id).hidden=!ready||fast;
  $('run-controls').hidden=false;$('run-controls').append($('profile-control'));$('api-settings').hidden=!ready||!fast;
  $('mode-hint').textContent=!ready?text('先优化搜索词，再选择模式和来源。','Optimize search terms, then choose mode and sources.'):fast?text('快速：使用已配置 API，否则使用 Google。点击搜索后执行。','Fast: configured API, otherwise Google. Click Search to execute.'):text('可修改搜索词、增加或减少来源；点击搜索后才执行。','Edit search terms and add or remove sources. Only Search starts execution.');
  if(fast&&globalThis.SearchAllDeepSeekStatus?.deepseek_route==='cloud'&&globalThis.SearchAllDeepSeekStatus?.cloud_offer?.available)$('mode-hint').textContent+=' '+globalThis.MiniAppI18n.template`DeepSeek Cloud: ${globalThis.SearchAllDeepSeekStatus.cloud_offer.points_per_search} Point per successful non-empty search; confirmation required.`;
  $('x-sort-control').hidden=!ready||fast||!selected().includes('x');$('xhs-sort-control').hidden=!ready||fast||!selected().includes('xiaohongshu');
  $('run').textContent=ready?text('搜索','Search'):text('优化搜索词','Optimize search terms');
  $('profile').disabled=busy||active||!!submission||!$('profile').options.length;
  $('run').disabled=busy||active||!$('profile').options.length;
  optimize.disabled=busy||active||!!submission;if(quick){quick.hidden=ready;quick.disabled=busy||active||!!submission;}
  for(const input of document.querySelectorAll('#search input,#search select,#add-source'))if(input.id!=='profile')input.disabled=busy||active||!!submission||input.dataset.unavailable==='true';
  $('profile').disabled=busy||active||!!submission||!$('profile').options.length;
  if(ready)$('strategy').textContent=text('原始需求：','Original request: ')+original+'\n'+preparation.reason;
 }
 async function observePreparation(){
  const deadline=Date.now()+180000;
  while(preparation.status!=='completed'){
   if(['failed','cancelled','interrupted'].includes(preparation.status))throw Error(preparation.message||preparation.status);
   if(Date.now()>deadline)throw Error(text('搜索准备超时，可重新打开后继续。','Search preparation timed out; reopen to continue.'));
   $('notice').textContent=text('正在优化搜索词并推荐来源…','Optimizing search terms and recommending sources…');
   await delay();preparation=await AI2AppsWebAgent.searchPreparation(preparation.id);
  }
  $('query').value=preparation.query;$('limit').value=preparation.limit;$('x-sort').value=preparation.x_sort;$('xhs-sort').value=preparation.xiaohongshu_sort;
  if($('mode').value==='preferred')choose(preparation.sources);
  ready=true;await save();
 }
 async function observeWorkflow(){
  active=true;display();
  for(;;){
   const state=await AI2AppsWebAgent.searchWorkflow(preparation.id);SearchAllWorkflowHost.show(state);display();
   if(state.status==='completed'){active=false;await save();await SearchAllWorkflowHost.afterSearch?.();$('notice').textContent=text('搜索已完成。可点击“帮我总结”读取正文并总结。','Search complete. Choose Summarize for me to read original pages and summarize.');break;}
   if(['failed','cancelled','expired'].includes(state.status)){active=false;await save();throw Error(state.error?.message||state.status);}
   // Read-only status observation; the persistent Agent Run advances every stage.
   await delay();
  }
 }
 $('search').onsubmit=async event=>{
  event.preventDefault();if(busy||active)return;busy=true;display();
  try{
   if(!ready){original=$('query').value.trim();if(!original)return;
    preparation=await AI2AppsWebAgent.prepareSearch({query:original,profile:$('profile').value,locale:document.documentElement.lang,request_id:crypto.randomUUID()});await save();await observePreparation();
   }else{
    if($('mode').value!=='fast'&&!selected().length)throw Error(text('请至少选择一个来源。','Choose at least one source.'));
    if(!submission&&!await SearchAllWorkflowHost.beforeSearch())return;
    if(!submission){
     const values=settings();
     if(values.sources.includes('deepseek')){
      const config=await AI2AppsWebAgent.searchConfig();globalThis.SearchAllDeepSeekStatus=config;
      if(config.deepseek_route==='cloud'){
       const offer=config.cloud_offer;
       if(!offer?.available)throw Error(globalThis.MiniAppI18n.text('Cloud search is unavailable. Check sign-in, balance or organization policy.'));
       const message=globalThis.MiniAppI18n.template`Use DeepSeek Cloud for this search? Up to ${offer.points_per_search} Point for successful non-empty results. Failures, timeouts and empty results are free. Cancellation after dispatch may still be charged.`;
       if(!await askCloud(message,MiniAppI18n.text('Confirm paid search')))return;
       Object.assign(values,{cloud_consent:true,cloud_price_version:offer.price_version,cloud_max_points:offer.points_per_search});
      }
     }
     submission={preparation_id:preparation.id,values,request_id:crypto.randomUUID()};await save();
    }
    const state=await AI2AppsWebAgent.startSearch(submission);
    preparation={...preparation,id:state.preparation_id||preparation.id};submission=null;chatRequest='';active=true;await save();SearchAllWorkflowHost.show(state);await observeWorkflow();
   }
  }catch(error){if(/^HTTP 422\b/.test(error.message)){submission=null;await save();}$('notice').textContent=error.message;}finally{busy=false;display();}
 };
 const oldMode=$('mode').onchange;
 $('mode').onchange=async()=>{oldMode?.();if(preparation&&$('mode').value==='preferred')choose(preparation.sources);if(preparation&&$('mode').value==='fast'){const api=await AI2AppsWebAgent.searchConfig();preparation.fast_source=api.fast_source||(api.configured?'fast_api':'google');}display();void save();};
 $('search').addEventListener('change',event=>{if(event.target.id==='profile'){ready=false;preparation=null;}display();void save();});
 const optimize=document.createElement('button');optimize.type='button';optimize.textContent=text('重新优化 / 新搜索','Optimize again / New search');optimize.onclick=()=>{if(active||busy)return;ready=false;preparation=null;chatRequest='';display();void save();};$('search').append(optimize);
 async function restore(){
  while(!$('profile').options.length)await delay();
  restoring=true;
  try{const saved=await AI2AppsWebAgent.draft();const draft=typeof saved==='string'?JSON.parse(saved||'null'):saved;
   if(draft?.schema==='search-workflow/v1'||(draft?.schema==='ai2apps.mini-app-draft/v1'&&draft.miniApp==='ai2apps.search-all'&&draft.workflowSchema==='search-workflow/v1')){
    submission=draft.submission||null;preparation=draft.preparation;ready=!!draft.ready;active=!!draft.active;summarizing=!!draft.summarizing;original=draft.original||'';
    for(const [id,key] of [['query','query'],['mode','mode'],['limit','limit'],['profile','profile'],['x-sort','x_sort'],['xhs-sort','xiaohongshu_sort']])if(draft[key]!==undefined)$(id).value=draft[key];
    choose(draft.sources||[]);$('exclude-ads').checked=draft.exclude_ads!==false;
    if(preparation)await AI2AppsWebAgent.searchPreparation(preparation.id);

   }
  }catch(error){
   if(/Search Package changed|Search preparation not found/.test(error.message)){ready=false;active=false;summarizing=false;preparation=null;submission=null;}
   $('notice').textContent=error.message;
  }finally{restoring=false;display();}
  if(preparation&&!ready){busy=true;try{await observePreparation();}catch(error){$('notice').textContent=error.message;}finally{busy=false;display();}}
  if(summarizing){try{await observeSummary();}catch(error){$('notice').textContent=error.message;summarizing=false;}}
  if(preparation&&ready&&!active&&!summarizing){
   try{SearchAllWorkflowHost.show(await AI2AppsWebAgent.searchWorkflow(preparation.id));}catch(_){}
   try{const summary=await AI2AppsWebAgent.searchSummary(preparation.id);if(summary.status==='completed')SearchAllWorkflowHost.show(summary);else if(!['failed','cancelled','expired'].includes(summary.status)){summarizing=true;await observeSummary();}}catch(_){}
  }
  if(active){try{await observeWorkflow();}catch(error){$('notice').textContent=error.message;}finally{display();}}
 }
 const label=(a,b)=>globalThis.MiniAppI18n?.text(zh()?a:b)||(zh()?a:b);
 $('summarize').textContent=label('Summarize for me','Summarize for me');
 async function observeSummary(){
  for(;;){const state=await AI2AppsWebAgent.searchSummary(preparation.id);SearchAllWorkflowHost.show(state);$('summarize').disabled=summarizing;
   if(['completed','failed','cancelled','expired'].includes(state.status)){summarizing=false;await save();if(state.status!=='completed')throw Error(state.error?.message||state.status);break;}
   await delay();
  }
 }
 $('summarize').onclick=async()=>{if(!preparation||summarizing)return;summarizing=true;$('summarize').disabled=true;try{await save();const state=await AI2AppsWebAgent.searchSummary(preparation.id,true);SearchAllWorkflowHost.show(state);await observeSummary();}catch(error){$('notice').textContent=error.message;summarizing=false;void save();}finally{$('summarize').disabled=false;}};
 const chat=document.createElement('button');chat.id='continue-chat';chat.type='button';chat.hidden=true;chat.textContent=label('Continue in Chat (Agent)','Continue in Chat (Agent)');
 chat.onclick=async()=>{if(!preparation||chat.disabled)return;chat.disabled=true;try{await AI2AppsWebAgent.searchChat(preparation.id,chatRequest||(chatRequest=crypto.randomUUID()));}catch(error){$('notice').textContent=error.message;}finally{chat.disabled=false;}};
 $('summarize').parentElement.append(chat);
 $('custom-hint').textContent=label('Results appear as each source finishes. Choose Summarize for me to read original pages and summarize.','Results appear as each source finishes. Choose Summarize for me to read original pages and summarize.');
 document.querySelector('[data-text="summaryHint"]').textContent=text('结论仅依据成功读取的正文；未读来源单独报告。','Conclusions use successfully read article bodies; unread sources are reported separately.');
 quick=document.createElement('button');quick.id='fast-prepare';quick.type='button';quick.textContent=MiniAppI18n.text('Fast search (no AI optimization)');
 quick.onclick=async()=>{if(busy||active||submission)return;busy=true;display();try{original=$('query').value.trim();if(!original)return;$('mode').value='fast';preparation=await AI2AppsWebAgent.prepareSearch({query:original,profile:$('profile').value,locale:document.documentElement.lang,request_id:crypto.randomUUID(),fast:true});await save();await observePreparation();}catch(error){$('notice').textContent=error.message;}finally{busy=false;display();}};
 $('search').append(quick);
 display();void restore();
})();
