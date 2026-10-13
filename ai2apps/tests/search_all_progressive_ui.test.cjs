const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
test('partial lists render immediately, update one card, and fold only after final review',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const base=path.resolve(__dirname,'../../packages/ai2apps-search-all/web');
  await page.setContent(fs.readFileSync(base+'/index.html','utf8').replace(/<script[\s\S]*?<\/script>/g,''));
  await page.evaluate(()=>{
   window.crypto.randomUUID=()=> 'request';const listeners=new Set();window.emit=t=>listeners.forEach(fn=>fn(t));
   window.AI2AppsWebAgent={startup:async()=>({profiles:[{key:'default',name:'Default',is_default:true}],sources:[]}),onTask:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},retainedTasks:async()=>[],searchConfig:async()=>({configured:false}),watch:async id=>({id,status:'running'}),submit:async(capability,parameters)=>capability==='review'?{id:'review',status:'completed',result:{items:parameters.items.map(row=>({...row,reason:'Relevant',is_ad:false}))}}:{id:'source',status:'running'},openResult:async()=>({})};
  });
  for(const name of ['i18n.js','startup.js','merge.js','presentation.js','diagnostics.js','modes.js','summary.js','search.js'])await page.addScriptTag({path:base+'/'+name});
  await page.waitForSelector('#app-content',{state:'visible'});await page.selectOption('#mode','custom');
  await page.locator('input[name=source]').evaluateAll(nodes=>nodes.forEach(n=>n.checked=n.value==='xiaohongshu'));
  await page.fill('#query','recipe');await page.click('#run');
  assert.deepEqual(errors,[]);
  const items=Array.from({length:4},(_,i)=>({title:'Note '+i,url:'https://www.rednote.com/explore/'+String(i).padStart(24,'0'),kind:'post',content_status:'list_only'}));
  await page.evaluate(items=>window.emit({id:'source',status:'running',result:{partial:true,items}}),items);
  assert.equal(await page.locator('.result-card').count(),4);assert.equal(await page.locator('#results details').count(),0);
  await page.evaluate(()=>window.unchangedCard=document.querySelectorAll('.result-card')[1]);
  items[0]={...items[0],content:'Full recipe',content_status:'detail_read'};
  await page.evaluate(items=>window.emit({id:'source',status:'running',result:{partial:true,items}}),items);
  assert.equal(await page.evaluate(()=>window.unchangedCard===document.querySelectorAll('.result-card')[1]),true);
  assert.equal(await page.getByText('Full recipe',{exact:true}).count(),1);
  await page.evaluate(items=>window.emit({id:'source',status:'completed',result:{items}}),items);
  await page.waitForSelector('#results details');assert.equal(await page.locator('#results details').isVisible(),true);assert.equal(await page.locator('#results details').getAttribute('open'),null);
  assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
