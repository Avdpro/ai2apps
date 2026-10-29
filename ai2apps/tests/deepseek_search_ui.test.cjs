const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const base=path.resolve(__dirname,'../web/static/builtin_mini_apps/search-all/web');
for(const width of [390,1100])for(const available of [true,false])test(`DeepSeek source availability and fast routing ${width} ${available}`,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 page.setDefaultTimeout(5000);
 await page.setContent(fs.readFileSync(base+'/index.html','utf8').replace(/<script[\s\S]*?<\/script>/g,''));
 await page.evaluate(available=>{
  window.crypto.randomUUID=()=> 'request';document.documentElement.lang='en';document.querySelector('#app-content').hidden=false;window.starts=[];
  const prep={id:'prep',status:'completed',query:'test query',sources:['google'],limit:5,x_sort:'top',xiaohongshu_sort:'general',reason:'test',fast_source:available?'deepseek':'google'};
  const done={status:'completed',output:{query:'test query',results:[],source_statuses:[]}};
  window.AI2AppsWebAgent={startup:async()=>({profiles:[{key:'default',name:'Default',is_default:true}],sources:[]}),onTask:()=>()=>{},retainedTasks:async()=>[],searchConfig:async()=>({configured:available,deepseek_available:available,fast_source:prep.fast_source}),draft:async()=>null,saveDraft:async()=>{},prepareSearch:async()=>prep,searchPreparation:async()=>prep,startSearch:async body=>{window.starts.push(body);return done;},searchWorkflow:async()=>done,searchSummary:async()=>({status:'failed'})};
 },available);
 for(const file of ['i18n.js','startup.js','modes.js','merge.js','summary.js','presentation.js','diagnostics.js','search.js','workflow.js'])await page.addScriptTag({path:base+'/'+file});
 await page.waitForFunction(()=>document.querySelector('#profile').options.length>0&&!document.querySelector('#run').disabled&&document.querySelector('#run').textContent==='Prepare fast search');
 assert.equal(await page.locator('#mode').inputValue(),'fast');
 const source=page.locator('input[name=source][value=deepseek]');assert.equal(await source.isDisabled(),!available);
 assert.match(await page.locator('#deepseek-hint').textContent(),available?/official DeepSeek BYOK/:/Cloud search is unavailable/);
 await page.locator('#query').fill('test');await page.locator('#run').click();
 await page.waitForFunction(()=>!document.querySelector('#mode-controls').hidden).catch(async e=>{throw Error(e.message+' NOTICE: '+await page.locator('#notice').textContent()+' ERRORS: '+errors.join(','));});
 await page.locator('#mode').selectOption('fast');await page.locator('#run').click();
 await page.waitForFunction(()=>window.starts.length===1);
 assert.deepEqual(await page.evaluate(()=>window.starts[0].values.sources),[available?'deepseek':'google']);
 assert.equal(await source.isDisabled(),!available);
 assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
test('DeepSeek hints localized in every supported locale',()=>{
 const vm=require('node:vm');
 for(const locale of ['zh','zh-TW','ja','ko','fr','es','ru','pt-BR']){
  const g={location:{search:'?locale='+locale},document:{documentElement:{lang:locale}},URLSearchParams};g.globalThis=g;
  vm.runInNewContext(fs.readFileSync(base+'/i18n.js','utf8'),g);
  const key='Configure official DeepSeek BYOK. Unavailable in privacy mode; Cloud search is coming soon.';
  assert.notEqual(g.MiniAppI18n.text(key),key,locale);
 }
});
