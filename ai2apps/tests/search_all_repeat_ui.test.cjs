const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const base=path.resolve(__dirname,'../web/static/builtin_mini_apps/search-all/web');
for(const width of [390,1100])test('Completed search changes mode and survives lost response '+width,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(5000);
  await page.setContent(fs.readFileSync(base+'/index.html','utf8').replace(/<script[\s\S]*?<\/script>/g,''));
  await page.evaluate(()=>{
   document.documentElement.lang='en';let uuid=0,draft=null,lose=false;const runs=new Map();window.calls=[];window.planCalls=0;
   crypto.randomUUID=()=> 'request-'+(++uuid);
   const prep={id:'plan',status:'completed',query:'DeepSeek DeepInfra',sources:['google'],limit:5,x_sort:'top',xiaohongshu_sort:'general',reason:'Original plan',fast_source:'google'};
   const done=id=>({id:'run-'+id,preparation_id:id,status:'completed',output:{query:'DeepSeek DeepInfra',results:[],source_statuses:[]}});
   window.AI2AppsWebAgent={startup:async()=>({profiles:[{key:'default',name:'Default',is_default:true}],sources:[]}),onTask:()=>()=>{},retainedTasks:async()=>[],searchConfig:async()=>({configured:false,fast_source:'google'}),draft:async()=>draft,saveDraft:async v=>{draft=JSON.stringify(v);window.saved=v;},prepareSearch:async()=>{window.planCalls++;return prep;},searchPreparation:async()=>prep,startSearch:async body=>{
    window.calls.push(JSON.parse(JSON.stringify(body)));
    const key=body.preparation_id+':'+body.request_id;
    if(!runs.has(key))runs.set(key,done('receipt-'+runs.size));
    window.runCount=runs.size;
    if(window.loseNext&&!lose){lose=true;throw Error('Response lost');}
    return runs.get(key);
   },searchWorkflow:async id=>done(id),searchSummary:async()=>({status:'failed'})};
  });
  for(const file of ['i18n.js','startup.js','modes.js','merge.js','summary.js','presentation.js','diagnostics.js','search.js','workflow.js'])await page.addScriptTag({path:base+'/'+file});
  await page.waitForFunction(()=>!document.querySelector('#run').disabled);
  await page.fill('#query','DeepSeek DeepInfra');await page.click('#run');await page.waitForFunction(()=>!document.querySelector('#mode-controls').hidden);
  await page.click('#run');await page.waitForFunction(()=>window.saved?.active===false&&window.runCount===1);
  await page.selectOption('#mode','fast');await page.evaluate(()=>window.loseNext=true);await page.click('#run');
  await page.waitForFunction(()=>document.querySelector('#notice').textContent==='Response lost');
  assert.equal(await page.locator('#mode').isDisabled(),true);
  assert.equal(await page.evaluate(()=>window.saved.submission.request_id),await page.evaluate(()=>window.calls[1].request_id));
  await page.click('#run');await page.waitForFunction(()=>window.saved?.active===false&&!window.saved?.submission&&window.calls.length===3);
  const got=await page.evaluate(()=>({calls,runCount,planCalls,id:window.saved.preparation.id}));
  assert.equal(got.planCalls,1);assert.equal(got.runCount,2);assert.equal(got.id,'receipt-1');
  assert.equal(got.calls[1].preparation_id,'receipt-0');assert.equal(got.calls[1].values.mode,'fast');
  assert.deepEqual(got.calls[1],got.calls[2]);assert.equal(await page.locator('#mode').isDisabled(),false);
  assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
