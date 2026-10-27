const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const read=f=>fs.readFileSync(path.join(__dirname,'..',f),'utf8');
test('Chat focus and keyboard dismissal reclaim dock space without changing App preferences',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  const page=await browser.newPage({viewport:{width:390,height:850}});
  await page.setContent('<div id="ai2apps-mobile" class="mobile-shell"><main class="mobile-main"><section id="chat"><textarea data-mobile-chat-input></textarea></section><button id="other">Other</button></main><nav class="mobile-dock">Apps</nav></div>');
  await page.addStyleTag({content:read('web/static/css/mobile.css')});
  await page.evaluate(()=>{const v=new EventTarget();v.height=850;Object.defineProperty(window,'visualViewport',{value:v});window.resizeKeyboard=h=>{v.height=h;v.dispatchEvent(new Event('resize'));};});
  await page.addScriptTag({content:read('web/static/js/mobile_chat_keyboard.js')});
  const dock=page.locator('.mobile-dock'),input=page.locator('textarea');
  const before=await page.locator('main').boundingBox();
  await input.focus();assert.equal(await dock.isVisible(),false);
  assert.ok((await page.locator('main').boundingBox()).height-before.height>=78);
  await page.evaluate(()=>resizeKeyboard(500));assert.equal(await dock.isVisible(),false);
  await page.evaluate(()=>resizeKeyboard(850));assert.equal(await dock.isVisible(),true);
  assert.equal(await input.evaluate(n=>n===document.activeElement),true);
  await page.evaluate(()=>resizeKeyboard(500));assert.equal(await dock.isVisible(),false);
  await page.locator('#other').focus();assert.equal(await dock.isVisible(),true);
  await page.evaluate(()=>resizeKeyboard(850));
  await input.focus();
  await page.locator('#chat').evaluate(n=>n.hidden=true);assert.equal(await dock.isVisible(),true);
  await page.locator('#chat').evaluate(n=>n.hidden=false);
  await input.focus();
  await page.locator('#ai2apps-mobile').evaluate(n=>n.classList.add('mobile-dock-hidden'));
  await page.locator('#other').focus();assert.equal(await dock.isVisible(),false);
  await page.locator('#ai2apps-mobile').evaluate(n=>n.classList.remove('mobile-dock-hidden'));
  assert.equal(await dock.isVisible(),true);
 } finally {await browser.close();}
});
