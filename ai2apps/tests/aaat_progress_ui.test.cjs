const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
test('owner progress metrics update and restore without business-specific renderer',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  const page=await browser.newPage();
  const html=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');
  const start=html.indexOf('<div x-show="run.status_line?.content?.task_progress"');
  const fragment=html.slice(start,html.indexOf('<div x-show="run.status_line?.content?.workflow_run_id"',start));
  const initial={schema:'ai2apps.task-progress/v1',state:'running',metrics:[{label:'任意计数',value:3,total:9}]};
  async function mount(snapshot) {
   await page.setContent(`<div x-data='${JSON.stringify({run:{status_line:{content:{task_progress:snapshot}}}})}'>${fragment}</div>`);
   await page.addScriptTag({path:__dirname+'/../web/static/js/alpine.min.js'});
  }
  await mount(initial);
  await page.waitForFunction(()=>document.querySelector('[aria-label="Tool progress metrics"]').textContent.includes('3 / 9'));
  await page.evaluate(()=>{Alpine.$data(document.querySelector('[x-data]')).run.status_line.content.task_progress.metrics[0].value=7;});
  await page.waitForFunction(()=>document.querySelector('[aria-label="Tool progress metrics"]').textContent.includes('7 / 9'));
  await page.goto('about:blank');
  await mount({...initial,state:'waiting',requires_user:true,wait_reason:'需要登录',metrics:[]});
  await page.waitForFunction(()=>document.querySelector('[aria-label="Tool progress metrics"]').textContent.includes('需要登录'));
  assert.equal(await page.locator('[aria-label="Tool progress metrics"]').isVisible(),true);
 } finally {await browser.close();}
});
