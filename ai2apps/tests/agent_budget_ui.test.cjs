const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
test('completed search citations remain visible while parent waits or fails',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  const source=fs.readFileSync(path.join(__dirname,'../web/templates/chat.html'),'utf8');
  const start=source.indexOf('<template x-if="child.status === \'completed\' && child.agent_key === \'ai2apps.search-workflow\'');
  assert.ok(start>0);const fragment=source.slice(start,source.indexOf('</template>',start)+11);
  await page.setContent(`<html lang="zh"><body><div x-data="reportState">${fragment}</div></body></html>`);
  await page.addScriptTag({path:path.join(__dirname,'../web/static/js/marked.umd.js')});
  await page.addScriptTag({path:path.join(__dirname,'../web/static/js/purify.min.js')});
  await page.evaluate(()=>{window.reportState={run:{status:'waiting_input'},child:{status:'completed',agent_key:'ai2apps.search-workflow',output:{markdown:'正文总结 [小红书](https://www.xiaohongshu.com/explore/test) [B站](https://www.bilibili.com/video/test)'}},renderMarkdown(text){return DOMPurify.sanitize(marked.parse(text));}};});
  await page.addScriptTag({path:path.join(__dirname,'../web/static/js/alpine.min.js')});
  const report=page.locator('[aria-label="Completed search report"]');await report.waitFor({state:'visible'});
  assert.equal(await report.locator('a').count(),2);
  await page.evaluate(()=>{Alpine.$data(document.querySelector('[x-data]')).run.status='failed';});
  assert.ok(await report.isVisible());assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
