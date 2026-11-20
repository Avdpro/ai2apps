const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
const src=fs.readFileSync(__dirname+'/../web/static/js/intelligence.js','utf8');
const code=src.slice(src.indexOf('function initExportOptions(){'),src.indexOf('\ninitBackupTransfer();'));
test('backup preview and confirmation work on desktop and mobile; user content stays text',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{for(const width of [1200,390]){
  const page=await browser.newPage({viewport:{width,height:900}});
  await page.setContent('<header class="intel-top"><button id="refresh-view">Refresh</button></header><details class="intel-mobile-menu"><summary>More</summary><div></div></details>');
  await page.evaluate(()=>{window.$=s=>document.querySelector(s);window.handoffText=(zh,en)=>en;window.safe=fn=>async(...args)=>fn(...args);window.channelId='channel';window.mobileChannelViews=new Map();window.mobileArticleLists=new Map();window.refresh=async()=>{};window.notice=s=>window.lastNotice=s;window.calls=[];window.requestJSON=async(url,options)=>{calls.push({url,expected:options.body.get('expected'),file:options.body.get('file').name});return {expected:'snapshot',create:2,update:0,keep:1,conflict:1,items:[{action:'create',title:'<img src=x onerror="window.injected=true">'}]};};});
  await page.addScriptTag({content:code+'\ninitBackupTransfer();'});
  assert.equal(await page.locator('.intel-backup-menu button').count(),3);
  assert.equal(await page.locator('.intel-mobile-menu button').count(),2);
  await page.locator('input[type=file][accept=".zip,application/zip"]').setInputFiles({name:'backup.zip',mimeType:'application/zip',buffer:Buffer.from('fixture')});
  await page.locator('dialog[open]').waitFor();
  assert.match(await page.locator('.intel-backup-dialog').innerText(),/Create 2, merge 0, keep 1/);
  assert.equal(await page.locator('.intel-backup-dialog img').count(),0);
  await page.getByRole('button',{name:'Import',exact:true}).click();
  assert.equal(await page.locator('dialog[open]').count(),0);
  const calls=await page.evaluate(()=>window.calls);assert.equal(calls.length,2);assert.equal(calls[1].expected,'snapshot');
  assert.equal(await page.evaluate(()=>window.lastNotice),'Channel import complete');
  await page.close();
 }}finally{await browser.close();}
});
