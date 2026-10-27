const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.join(__dirname,'..');
const source=fs.readFileSync(path.join(root,'web/static/js/intelligence.js'),'utf8');
const render=source.slice(source.indexOf('function renderRunProgress('),source.indexOf('function updateRunElapsed('));
test('parallel progress lists independent attempts and escapes titles on Desktop and Mobile',async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{for(const width of [390,1440]){
  const page=await browser.newPage({viewport:{width,height:850}});
  await page.setContent('<meta name="viewport" content="width=device-width,initial-scale=1"><div id="progress"></div>');
  await page.addStyleTag({content:fs.readFileSync(path.join(root,'web/static/css/intelligence.css'),'utf8')});
  await page.addScriptTag({content:`const labels={};const lt=s=>s;const link=s=>s;const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');${render}`});
  await page.evaluate(()=>{document.querySelector('#progress').innerHTML=renderRunProgress({started_at:'2026-10-26T06:40:00Z',progress:{phase:'writing',article_concurrency:3,events_total:8,events_completed:2,active_articles:[{event_index:3,title:'<img src=x onerror=alert(1)>',model_attempt:1},{event_index:4,title:'Independent report',model_attempt:2},{event_index:5,title:'A'.repeat(200),model_attempt:1}]}});});
  const text=await page.locator('#progress').innerText();
  assert.match(text,/并行生成 3 \/ 3/);assert.match(text,/已完成文章 2 \/ 8/);
  assert.match(text,/Independent report/);assert.match(text,/第几次调用 2 · 正在重试/);
  assert.equal(await page.locator('#progress img').count(),0);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.evaluate(()=>{document.querySelector('#progress').innerHTML=renderRunProgress({progress:{phase:'writing',event_index:2,events_total:4,event_title:'Legacy progress',model_attempt:2}});});
  assert.match(await page.locator('#progress').innerText(),/当前文章 2 \/ 4：Legacy progress/);
  await page.close();
 }}finally{await browser.close();}
});
