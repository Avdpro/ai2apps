const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
for(const width of [390,1100])test('Progressive search, manual grounded summary and Chat handoff at width '+width,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const base=path.resolve(__dirname,'../../packages/ai2apps-search-all/web');
  await page.setContent(fs.readFileSync(base+'/index.html','utf8').replace(/<script[\s\S]*?<\/script>/g,''));
  await page.evaluate(()=>{
   const rows=[{title:'SQLite WAL',url:'https://sqlite.org/wal.html',snippet:'Search snippet',search_source:'bing',browser_task_id:'search-task'},{title:'Backup',url:'https://sqlite.org/backup.html',snippet:'Backup snippet',search_source:'bing',browser_task_id:'search-task'}];
   window.crypto.randomUUID=()=> 'request';window.stage=0;window.starts=[];let draft=null;
   const preparation={id:'prep',status:'completed',query:'SQLite WAL backup checkpoint',sources:['google','wikipedia'],limit:5,x_sort:'top',xiaohongshu_sort:'general',reason:'Choose primary documentation',fast_source:'google'};
   window.AI2AppsWebAgent={startup:async()=>({profiles:[{key:'default',name:'Default',is_default:true}],sources:[]}),onTask:()=>()=>{},retainedTasks:async()=>[],searchConfig:async()=>({configured:false}),draft:async()=>draft,saveDraft:async v=>{if(v.schema!=='ai2apps.mini-app-draft/v1'||v.miniApp!=='ai2apps.search-all')throw Error('Invalid Mini-App draft');draft=JSON.stringify(v);},prepareSearch:async()=>preparation,searchPreparation:async()=>preparation,startSearch:async body=>{window.starts.push(body);return {status:'queued',text:'开始搜索'};},searchChat:async()=>{window.chatOpened=true;return {session_id:'new-chat'};},searchWorkflow:async()=>window.stage===0?{status:'running',text:'Bing completed; waiting for another source',content:{results:rows,source_statuses:[{source:'bing',status:'completed',count:2},{source:'google',status:'waiting_input',count:0}]}}:{status:'completed',text:'Search complete',output:{query:'edited by user',results:rows}},searchSummary:async(preparationId,start)=>window.stage===0?{status:'running',text:'搜索中 · Bing',content:{}}:window.stage===1?{status:'running',text:'正在阅读 1/2 · SQLite WAL',content:{results:rows,completed:0,total:2}}:{status:'completed',text:'完成',output:{query:'edited by user',results:rows,articles:[{url:rows[0].url,text:'Actual body'}],read_failures:[],citations:[{id:'1',title:'SQLite WAL',url:rows[0].url}],summary:{overview:'Based on original article bodies.',points:[{text:'WAL conclusion from the article.',source_ids:['1']}],limitations:'One article read.'}}},openResult:async()=>({})};
  });
  for(const name of ['i18n.js','startup.js','merge.js','presentation.js','diagnostics.js','modes.js','summary.js','search.js','workflow.js'])await page.addScriptTag({path:base+'/'+name});
  await page.waitForSelector('#app-content',{state:'visible'});await page.waitForFunction(()=>!document.getElementById('run').disabled);assert.equal(await page.locator('#notice').textContent(),'');await page.fill('#query','SQLite WAL?');await page.click('#run');
  await page.waitForFunction(()=>document.getElementById('query').value==='SQLite WAL backup checkpoint');
  assert.equal(await page.evaluate(()=>window.starts.length),0);
  assert.equal(await page.locator('#source-options').isVisible(),true);
  await page.fill('#query','edited by user');await page.locator('input[name=source]').evaluateAll(nodes=>nodes.forEach(n=>n.checked=n.value==='bing'));
  await page.click('#run');await page.waitForFunction(()=>window.starts.length===1);
  assert.deepEqual(await page.evaluate(()=>window.starts[0].values.sources),['bing']);assert.equal(await page.evaluate(()=>window.starts[0].values.query),'edited by user');
  await page.waitForFunction(()=>document.querySelectorAll('.result-card').length===2);
  assert.equal(await page.locator('#continue-chat').isVisible(),true);
  await page.evaluate(()=>window.stage=1);await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('搜索已完成'));
  await page.click('#summarize');await page.waitForFunction(()=>document.getElementById('notice').textContent.includes('正在阅读'));
  assert.equal(await page.locator('.result-card').count(),2);
  await page.screenshot({path:'/private/tmp/search-all-shared-reading.png',fullPage:true});
  await page.evaluate(()=>window.stage=2);await page.waitForFunction(()=>document.getElementById('summary-report').textContent.includes('WAL conclusion'));
  assert.equal(await page.locator('#summary-report a').getAttribute('href'),'https://sqlite.org/wal.html');await page.click('#continue-chat');assert.equal(await page.evaluate(()=>window.chatOpened),true);assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});

test('Agentic search form optimizes first and submits only edited user-confirmed parameters',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:1000,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<html lang="zh"><head><style>*{box-sizing:border-box}.agent-interaction-input{width:100%;margin-top:8px;padding:8px}</style></head><body><div id="form"></div></body></html>');
  await page.evaluate(()=>{
   window.submissions=[];let revision=0;
   const values={query:'Original WAL question',mode:'preferred',profile:'default',limit:5};
   const fields=[{key:'query',label:'搜索词',type:'text'},{key:'mode',label:'模式',type:'select',options:[{value:'preferred',label:'优选'},{value:'custom',label:'自定义'},{value:'fast',label:'快速'}]},{key:'sources',label:'来源',type:'multiselect',options:[{value:'google',label:'Google'},{value:'bing',label:'Bing'},{value:'wikipedia',label:'Wikipedia'},{value:'bilibili',label:'B站'}]},{key:'exclude_ads',label:'剔除广告',type:'boolean'},{key:'retain_pages',label:'保留搜索结果页面',type:'boolean'},{key:'profile',label:'分身',type:'select',options:[{value:'default',label:'Default'}]}];
   window.fetch=async(url,options={})=>{let value={};if(options.method==='PUT'){revision++;value={revision};}else if(url.endsWith('/search/prepare'))value={id:'prep',status:'completed',query:'Optimized WAL terms',sources:['google','wikipedia'],limit:5,x_sort:'top',xiaohongshu_sort:'general',reason:'Primary documentation',fast_source:'google'};else if(url.endsWith('/submit')){window.submissions.push(JSON.parse(options.body));value={status:'completed'};}else if(url.includes('/parameters'))value={revision,values,descriptor:{capability:'web.search',provider:'ai2apps.search-all.search',app_id:'ai2apps.ai-browser',mini_app_id:'ai2apps.search-all',fields,schema:{required:['query','sources']}},alternatives:[],search_workflow:true,configure_only:true,submit_label:'搜索 / Search',fast_source:'google'};else value={items:[]};return {ok:true,json:async()=>value};};
  });
  await page.addScriptTag({path:path.resolve(__dirname,'../web/static/js/agent_parameter_forms.js')});
  await page.evaluate(()=>window.AI2AppsParameterForms.mount(document.getElementById('form'),{id:'run',agent_key:'research'},{id:'interaction'},async()=>{}));
  await page.waitForFunction(()=>document.getElementById('parameter-interaction-query')?.value==='Optimized WAL terms');
  assert.equal(await page.evaluate(()=>window.submissions.length),0);
  for(const width of [1000,360]){
   await page.setViewportSize({width,height:900});
   const layout=await page.evaluate(()=>{
    const options=document.querySelector('.agent-parameter-options'),title=options.previousElementSibling;
    const booleans=['exclude_ads','retain_pages'].map(key=>{const box=document.getElementById('parameter-interaction-'+key),b=box.getBoundingClientRect(),r=box.parentElement.getBoundingClientRect();return {width:b.width,delta:Math.abs(b.y+b.height/2-r.y-r.height/2),fullWidth:box.classList.contains('agent-interaction-input')};});
    const bsite=[...options.children].find(n=>n.textContent==='B站'),range=document.createRange();range.selectNodeContents(bsite.lastChild);
    return {below:options.getBoundingClientRect().y>=title.getBoundingClientRect().bottom,booleans,textLines:range.getClientRects().length};
   });
   assert.equal(layout.below,true);assert.equal(layout.textLines,1);for(const row of layout.booleans){assert.equal(row.width,16);assert.ok(row.delta<=1);assert.equal(row.fullWidth,false);}
  }
  await page.setViewportSize({width:1000,height:900});

  await page.locator('#parameter-interaction-query').fill('Edited final query');await page.locator('#parameter-interaction-query').blur();
  await page.locator('label').filter({hasText:/^Google$/}).locator('input').uncheck();await page.locator('label').filter({hasText:/^Bing$/}).locator('input').check();
  await page.locator('button[type=submit]').click();await page.waitForFunction(()=>window.submissions.length===1);
  const result=await page.evaluate(()=>window.submissions[0].values);assert.equal(result.query,'Edited final query');assert.deepEqual(result.sources,['wikipedia','bing']);assert.equal(result.preparation_id,'prep');assert.deepEqual(errors,[]);
  await page.screenshot({path:'/private/tmp/agentic-shared-search-form.png',fullPage:true});
 }finally{await browser.close();}
});
