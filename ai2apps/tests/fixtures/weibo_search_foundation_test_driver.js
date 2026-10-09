const panel=document.createElement('section'); panel.innerHTML='<button id=run>运行微博搜索测试</button><pre id=status style="white-space:pre-wrap"></pre>';document.body.prepend(panel);
const report={events:[],pages:[]};
const write=()=>document.querySelector('#status').textContent=JSON.stringify({status:report.status,error:report.error,variables:report.variables,pages:report.pages,run_id:report.run_id,...report},null,2);
const api=async(path,body)=>{const response=await fetch('/v1/platform'+path,{credentials:'same-origin',headers:{'Content-Type':'application/json'},...(body===undefined?{}:{method:'POST',body:JSON.stringify(body)})});const value=await response.json();if(!response.ok)throw Error(response.status+' '+JSON.stringify(value));return value;};
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const event=text=>{report.events.push(new Date().toISOString()+' '+text);write();};
document.querySelector('#run').onclick=async()=>{
 document.querySelector('#run').disabled=true;
 let connection,search;
 const fragment=new URLSearchParams(location.hash.slice(1));fragment.set("agent_context_lock","1");history.replaceState(null,"",location.pathname+location.search+"#"+fragment);await pause(1000);
 try {
  connection=await new window.AI2AppsBiDi.AI2AppsBiDiConnection().connect();
  const initial=await connection.command('browsingContext.getTree',{maxDepth:0});
  report.initial_contexts=initial.contexts.map(x=>x.context);
  search=(await connection.command('browsingContext.create',{type:'tab',background:false})).context;
  const client=new window.AI2AppsBiDi.AI2AppsPageClient({bidi_context:search});client.connection=connection;client.contextId=search;
  window.__foundationLiveBind(client,{bidi_context:search,url:'about:blank'});
  const source={site_scope:['https://weibo.com/**','https://s.weibo.com/**','https://passport.weibo.com/**'],steps:[
   {name:'open',operation:'open',arguments:{url:'https://weibo.com/'},on:{success:'search',failed:'failed'}},
   {name:'search',operation:'agent.call',arguments:{agent_id:'builtin:web:light-explore',capability:'web.light-explore',generation_id:'web-foundations/2',parameters:{goal:'在微博中进行全站搜索“数字人”（不要使用仅搜索关注人的首页高级搜索）。在当前网站的搜索框输入关键词并打开搜索结果，读取前三条相关微博的作者、正文摘要和可观察到的链接。只搜索和读取，不发布、不点赞；如搜索确实需要登录，请说明具体登录阻挡。'}},on:{success:'done',failed:'failed'}}]};
  const draft=await api('/agent-drafts',{name:'微博搜索基础能力 v2 测试 2026-10-07',description:'真实微博搜索与轻探索；通过产品执行器和原生 BiDi 执行 AI 规划的交互。',site_scope:source.site_scope,source});report.draft_id=draft.id;report.query='数字人';report.capabilities=(await api('/agent-capabilities?url=about%3Ablank')).items?.filter(x=>x.agent_id.startsWith('builtin:web:')).map(x=>x.name);
  const generation=await api('/agent-drafts/'+draft.id+'/compile',{});report.compile_status=generation.status;
  const run=await api('/agent-drafts/'+draft.id+'/runs',{browser_context:{bidi_context:search,url:'about:blank'}});report.run_id=run.id;event('运行已创建');
  for(let poll=0;poll<240;poll++){
   const current=await api('/agent-draft-runs/'+run.id);report.status=current.status;report.started_at=current.started_at;report.finished_at=current.finished_at;
   if(['completed','failed','cancelled'].includes(current.status)){
    report.error=current.error;report.variables=current.output?.variables;report.answer=current.output?.result;
    report.evidence=(current.output?.evidence||[]).map(e=>({step:e.step_id,outcome:e.outcome}));
    if(report.variables?.articles)report.variables.articles=report.variables.articles.map(p=>({url:p.url,title:p.title,characters:p.text.length,extraction_method:p.extraction_method,tab_closed:p.tab_closed}));
    delete report.variables?.items;delete report.variables?.current;break;
   }
   const interaction=current.interactions.find(i=>i.status==='pending');
   if(!interaction){await pause(1000);continue;}
   if(interaction.request.control!=='browser_bidi_action')throw Error('Unexpected interaction: '+interaction.request.control);
   const step=interaction.request.step;let result;
   event('执行 '+step.id+' '+step.operation);await pause(2500);
   const execution=await window.__foundationLiveExecute(step,false,interaction.request.site_scope||source.site_scope,[]);
   if(['needs_user','restricted'].includes(execution.outcome)){report.status=execution.outcome;report.assistance=execution.evidence;write();throw Error('用户协助或限制: '+JSON.stringify(execution.evidence));}
   result=execution.evidence?.result;
   await api('/agent-draft-runs/'+run.id+'/interactions/'+interaction.id+'/respond',{response_id:crypto.randomUUID(),response:execution});
  }
  const finalTree=await connection.command('browsingContext.getTree',{maxDepth:0});report.remaining_test_pages=finalTree.contexts.filter(x=>!report.initial_contexts.includes(x.context)&&x.context!==search).map(x=>x.url);
  event('微博搜索测试结束');
 }catch(error){report.error=String(error.message||error);event('测试出错');}
 finally{write();if(connection)await connection.close();fragment.delete("agent_context_lock");history.replaceState(null,"",location.pathname+location.search+"#"+fragment);}
};
