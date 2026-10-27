const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const read=f=>fs.readFileSync(path.join(__dirname,'..',f),'utf8'),source=read('web/templates/chat.html');
const inputMarkup=source.slice(source.indexOf('<span class="chat-agent-budget-field">'),source.indexOf('</label>{% endif %}',source.indexOf('<span class="chat-agent-budget-field">')));
const methods=source.slice(source.indexOf('    defaultAgentTokenBudget()'),source.indexOf('    async setConversationMode('));
const css=source.slice(source.indexOf('    .chat-agent-select {'),source.indexOf('    .agent-parameter-panel {'));
test('budget controls align right, change exactly 10K and stay hidden on mobile',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  const page=await browser.newPage();
  await page.route('https://budget.test/**',route=>route.fulfill({contentType:'text/html',body:`<style>${css}</style><div id="budget" x-data="budgetFixture()"><label class="chat-agent-budget-control">${inputMarkup}</label></div>`}));
  for(const direction of [1,-1]) {
   await page.goto('https://budget.test/');
   await page.addScriptTag({content:`window.budgetFixture=()=>({${methods}availableAgents:[{agent_key:'a',manifest:{max_total_model_tokens:500000}}],currentAgentKey:'a',agentModelTokenBudget:null});`});
   await page.addScriptTag({content:read('web/static/js/alpine.min.js')});
   const input=page.locator('input');
   await page.waitForFunction(()=>document.querySelector('input').placeholder==='500000');
   assert.equal(await input.inputValue(),'');
   const box=await input.boundingBox();
   const button=page.getByRole('button',{name:direction===1?'Increase budget by 10K':'Decrease budget by 10K'});
   const buttonBox=await button.boundingBox();assert.ok(Math.abs(box.x+box.width-buttonBox.x-buttonBox.width)<=4);
   await button.click();
   assert.equal(await input.inputValue(),String(500000+direction*10000));
   assert.equal(await page.evaluate(()=>localStorage.getItem('ai2apps.agentTokenBudget')),String(500000+direction*10000));
   await input.fill('');await input.press(direction===1?'ArrowUp':'ArrowDown');
   assert.equal(await input.inputValue(),String(500000+direction*10000));
  }
  const input=page.locator('input');
  await input.fill('501234');await input.press('ArrowDown');assert.equal(await input.inputValue(),'491234');
  await input.fill('42');await input.press('ArrowDown');assert.equal(await input.inputValue(),'1');
  await page.evaluate(()=>{const data=Alpine.$data(document.querySelector('#budget'));data.agentModelTokenBudget=null;data.availableAgents[0].manifest.max_total_model_tokens=600000;});
  await input.press('ArrowUp');assert.equal(await input.inputValue(),'610000');
  await page.evaluate(()=>{const data=Alpine.$data(document.querySelector('#budget'));data.agentModelTokenBudget=null;data.availableAgents[0].manifest.max_total_model_tokens=0;});
  await input.press('ArrowDown');assert.equal(await input.inputValue(),'490000');
  await page.setViewportSize({width:390,height:844});assert.equal(await input.isVisible(),false);
  await page.setViewportSize({width:1000,height:800});assert.equal(await input.isVisible(),true);
  const touch=await browser.newContext({hasTouch:true,viewport:{width:1024,height:768}});
  const touchPage=await touch.newPage();await touchPage.setContent(`<style>${css}</style><label class="chat-agent-budget-control">Budget</label>`);
  assert.equal(await touchPage.locator('label').isVisible(),false);await touch.close();
  assert.ok(!read('web/templates/mobile_chat_content.html').includes('Agent token budget'));
 } finally {await browser.close();}
});
