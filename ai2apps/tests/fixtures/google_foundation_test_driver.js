const panel=document.createElement('section'); panel.innerHTML='<button id=run>运行 Google 基础能力测试</button><pre id=status style="white-space:pre-wrap"></pre>';document.body.prepend(panel);
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
  const source={site_scope:['https://www.google.com/**','https://developer.mozilla.org/**'],variables:{type:'object',properties:{index:{type:'integer',default:0},items:{type:'array',default:[]},current:{type:'string',default:''},articles:{type:'array',default:[]}}},steps:[
   {name:'search',operation:'open',arguments:{url:'https://www.google.com/search?q=site%3Adeveloper.mozilla.org+WebDriver+BiDi'},on:{success:'results',failed:'failed'}},
   {name:'results',operation:'agent.call',arguments:{agent_id:'builtin:web:extract-list',capability:'web.extract-list',generation_id:'web-foundations/1',parameters:{limit:5}},on:{success:'initialize',failed:'failed'}},
   {name:'initialize',operation:'assign',arguments:{assignments:[{variable:'items',expression:'steps.results.output.items'}]},on:{success:'check',failed:'failed'}},
   {name:'check',operation:'condition',arguments:{expression:'vars.index < min(3, len(vars.items))'},on:{true:'select',false:'done',failed:'failed'}},
   {name:'select',operation:'assign',arguments:{assignments:[{variable:'current',expression:'vars.items[vars.index].url'}]},on:{success:'read',failed:'failed'}},
   {name:'read',operation:'agent.call',arguments:{agent_id:'builtin:web:read-page',capability:'web.read-page',generation_id:'web-foundations/1',parameters:{url:'${vars.current}',new_tab:true,close_tab:true,delay_ms:3000}},on:{success:'advance',failed:'failed'}},
   {name:'advance',operation:'assign',arguments:{assignments:[{variable:'articles',expression:'vars.articles + [steps.read.output]'},{variable:'index',expression:'vars.index + 1'}]},on:{success:'check',failed:'failed'}}]};
  const draft=await api('/agent-drafts',{name:'Google 基础能力循环测试 2026-10-07',description:'真实 Google 搜索、局部变量循环、独立标签页阅读与关闭；测试驱动通过原生 BiDi 执行浏览器交互。',site_scope:source.site_scope,source});report.draft_id=draft.id;report.query='site:developer.mozilla.org WebDriver BiDi';report.capabilities=(await api('/agent-capabilities?url=about%3Ablank')).items?.filter(x=>x.agent_id.startsWith('builtin:web:')).map(x=>x.name);
  const generation=await api('/agent-drafts/'+draft.id+'/compile',{});report.compile_status=generation.status;
  const run=await api('/agent-drafts/'+draft.id+'/runs',{browser_context:{bidi_context:search,url:'about:blank'}});report.run_id=run.id;event('运行已创建');
  for(let poll=0;poll<240;poll++){
   const current=await api('/agent-draft-runs/'+run.id);report.status=current.status;report.started_at=current.started_at;report.finished_at=current.finished_at;
   if(['completed','failed','cancelled'].includes(current.status)){
    report.error=current.error;report.variables=current.output?.variables;
    report.evidence=(current.output?.evidence||[]).map(e=>({step:e.step_id,outcome:e.outcome}));
    if(report.variables?.articles)report.variables.articles=report.variables.articles.map(p=>({url:p.url,title:p.title,characters:p.text.length,extraction_method:p.extraction_method,tab_closed:p.tab_closed}));
    delete report.variables?.items;delete report.variables?.current;break;
   }
   const interaction=current.interactions.find(i=>i.status==='pending');
   if(!interaction){await pause(1000);continue;}
   if(interaction.request.control!=='browser_bidi_action')throw Error('Unexpected interaction: '+interaction.request.control);
   const step=interaction.request.step;let result;
   event('执行 '+step.id+' '+step.operation);await pause(2500);
   if(step.operation==='open'){await connection.command('browsingContext.navigate',{context:search,url:step.arguments.url,wait:'complete'},30000);await pause(3000);result=await client.pageState();}
   else if(step.operation==='extract_list'){const items=await client.extractArticleList(5);result=items;report.search_results=items.items?.map(p=>({url:p.url,title:p.title}));event('提取 '+(items.items?.length||0)+' 条搜索结果');if(!items.items?.length)throw Error('No Google search results extracted');}
   else if(step.operation==='read_page'){
    result=await client.readPage(step.arguments);
    report.pages.push({url:result.url,title:result.title,characters:result.text?.length,extraction_method:result.extraction_method,tab_closed:result.tab_closed});
    if(result.outcome!=='success')throw Error('Reading failed: '+JSON.stringify(result));event('基础能力已读取并关闭临时标签页');
   }else throw Error('Unsupported test action: '+step.operation);
   await api('/agent-draft-runs/'+run.id+'/interactions/'+interaction.id+'/respond',{response_id:crypto.randomUUID(),response:{outcome:'success',evidence:{operation:step.operation,result}}});
  }
  const finalTree=await connection.command('browsingContext.getTree',{maxDepth:0});report.remaining_test_pages=finalTree.contexts.filter(x=>!report.initial_contexts.includes(x.context)&&x.context!==search).map(x=>x.url);
  event('测试结束，保留 Google 搜索标签页');
 }catch(error){report.error=String(error.message||error);event('测试出错');}
 finally{write();if(connection)await connection.close();fragment.delete("agent_context_lock");history.replaceState(null,"",location.pathname+location.search+"#"+fragment);}
};
