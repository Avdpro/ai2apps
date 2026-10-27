const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const base=path.resolve(__dirname,'../../packages/ai2apps-search-all/web');
for(const width of [390,1100])test(`Cloud paid consent and no-charge cancellation ${width}`,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 page.setDefaultTimeout(5000);
 await page.setContent(fs.readFileSync(base+'/index.html','utf8').replace(/<script[\s\S]*?<\/script>/g,''));
 await page.evaluate(()=>{const available=true;
  window.crypto.randomUUID=()=> 'request';document.documentElement.lang='en';document.querySelector('#app-content').hidden=false;window.starts=[];
  const prep={id:'prep',status:'completed',query:'test query',sources:['google'],limit:5,x_sort:'top',xiaohongshu_sort:'general',reason:'test',fast_source:available?'deepseek':'google'};
  const done={status:'completed',output:{query:'test query',results:[],source_statuses:[]}};
  window.AI2AppsWebAgent={startup:async()=>({profiles:[{key:'default',name:'Default',is_default:true}],sources:[]}),onTask:()=>()=>{},retainedTasks:async()=>[],searchConfig:async()=>({configured:true,deepseek_available:true,fast_source:'deepseek',deepseek_route:'cloud',cloud_offer:{available:true,price_version:'v1',points_per_search:'1'}}),draft:async()=>null,saveDraft:async()=>{},prepareSearch:async()=>prep,searchPreparation:async()=>prep,startSearch:async body=>{window.starts.push(body);return done;},searchWorkflow:async()=>done,searchSummary:async()=>({status:'failed'})};
 });
 for(const file of ['i18n.js','startup.js','modes.js','merge.js','summary.js','presentation.js','diagnostics.js','search.js','workflow.js'])await page.addScriptTag({path:base+'/'+file});
 await page.waitForFunction(()=>document.querySelector('#profile').options.length>0&&!document.querySelector('#run').disabled&&document.querySelector('#run').textContent==='Optimize search terms');
 const source=page.locator('input[name=source][value=deepseek]');assert.equal(await source.isDisabled(),false);
 assert.match(await page.locator('#deepseek-hint').textContent(),/Points confirmation/);
 await page.locator('#query').fill('test');await page.locator('#run').click();
 await page.waitForFunction(()=>!document.querySelector('#mode-controls').hidden).catch(async e=>{throw Error(e.message+' NOTICE: '+await page.locator('#notice').textContent()+' ERRORS: '+errors.join(','));});
 await page.locator('#mode').selectOption('fast');await page.locator('#run').click();
 await page.waitForSelector('dialog[open]');assert.match(await page.locator('dialog[open]').textContent(),/Up to 1 Point/);
 await page.locator('dialog[open] button').first().click();assert.equal(await page.evaluate(()=>window.starts.length),0);
 await page.locator('#run').click();await page.waitForSelector('dialog[open]');await page.getByRole('button',{name:'Confirm paid search',exact:true}).click();
 await page.waitForFunction(()=>window.starts.length===1);
 assert.deepEqual(await page.evaluate(()=>window.starts[0].values.sources),['deepseek']);
 assert.equal(await source.isDisabled(),false);
 const body=await page.evaluate(()=>window.starts[0].values);assert.equal(body.cloud_consent,true);assert.equal(body.cloud_price_version,'v1');assert.equal(body.cloud_max_points,'1');
 assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
