const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});
for(const width of [1440,390])for(const provider of ['hf','ms'])for(const target of ['share','space']){
 console.log(width,provider,target);const page=await browser.newPage({viewport:{width,height:900}});
 await page.context().route('https://**/*',route=>route.fulfill({body:'<!doctype html><html lang="zh"><body>Published fixture</body></html>',contentType:'text/html'}));
 await page.goto('https://fixture.test');
 await page.addScriptTag({content:fs.readFileSync(__dirname+'/../web/static/js/share_works_host.js','utf8')});
 await page.evaluate(async({provider,target})=>{
  window.fetch=async()=>({ok:true,json:async()=>({provider,repo:'alice/site',snapshot_id:'a'.repeat(32),result:{url:provider==='hf'?'https://alice-site.hf.space/shares/id/index.html':'https://modelscope.cn/studios/alice/site?mode=full&app_path=%2Fshares%2F'+'a'.repeat(32)+'%2Findex.html'}})});
  await window.AI2AppsMiniAppBridges.get('ai2apps.share-works')({action:'open',request_id:'r'.repeat(16),target},{base:'/fixture'});
 },{provider,target});
 assert(await page.locator('dialog').isVisible());assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 const popupPromise=page.waitForEvent('popup');await page.locator('dialog a').click();const popup=await popupPromise;await popup.waitForURL(target==='space'?(provider==='hf'?'https://huggingface.co/spaces/alice/site':'https://modelscope.cn/studios/alice/site'):(provider==='hf'?'https://alice-site.hf.space/shares/id/index.html':'https://modelscope.cn/studios/alice/site?mode=full&app_path=%2Fshares%2F'+'a'.repeat(32)+'%2Findex.html'),{timeout:8000,waitUntil:'domcontentloaded'});
 assert(popup.url().startsWith(target==='space'?(provider==='hf'?'https://huggingface.co/spaces/alice/site':'https://modelscope.cn/studios/alice/site'):(provider==='hf'?'https://alice-site.hf.space/':'https://modelscope.cn/studios/alice/site?mode=full')));
 await popup.close();await page.locator('dialog button').click();await page.locator('dialog').waitFor({state:'detached'});await page.close();
}
await browser.close();console.log('8 Desktop/Mobile HF/MS host-owned share/space link fixtures passed.');})();
