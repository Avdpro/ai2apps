const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
test('shared workflow article progress updates changed cards without recreating unchanged ones',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const base=path.resolve(__dirname,'../../packages/ai2apps-search-all/web');
  await page.setContent(fs.readFileSync(base+'/index.html','utf8').replace(/<script[\s\S]*?<\/script>/g,''));
  await page.evaluate(()=>{window.SearchAllSharedWorkflow=true;window.AI2AppsWebAgent={startup:async()=>({profiles:[{key:'default',name:'Default',is_default:true}],sources:[]}),searchConfig:async()=>({configured:false,deepseek_available:false}),onTask:()=>()=>{},retainedTasks:async()=>[],openResult:async()=>({})};});
  for(const name of ['i18n.js','startup.js','merge.js','presentation.js','diagnostics.js','modes.js','summary.js','search.js'])await page.addScriptTag({path:base+'/'+name});
  await page.waitForSelector('#app-content',{state:'visible'});
  const rows=Array.from({length:4},(_,i)=>({title:'Article '+i,url:'https://example.com/'+i,snippet:'Search snippet',search_source:'bing',browser_task_id:'search-task'}));
  await page.evaluate(results=>SearchAllWorkflowHost.show({status:'running',text:'Reading 1/4',content:{results}}),rows);
  assert.equal(await page.locator('.result-card').count(),4);
  await page.evaluate(()=>window.unchangedCard=document.querySelectorAll('.result-card')[1]);
  rows[0].snippet='Updated observed snippet';
  await page.evaluate(results=>SearchAllWorkflowHost.show({status:'running',text:'Reading 2/4',content:{results}}),rows);
  assert.equal(await page.evaluate(()=>window.unchangedCard===document.querySelectorAll('.result-card')[1]),true);
  assert.equal(await page.getByText('Updated observed snippet',{exact:true}).count(),1);
  assert.match(await page.locator('#notice').textContent(),/Reading 2\/4/);
  assert.equal(await page.getByText('AI 排序与翻译 · 已完成',{exact:true}).count(),0);
  assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
