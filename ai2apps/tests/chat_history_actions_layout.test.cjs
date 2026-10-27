const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
test('Session titles reclaim control space until hover or keyboard focus',async()=>{
 const source=fs.readFileSync(path.join(__dirname,'../web/templates/chat.html'),'utf8');
 const css=source.split('<style>')[1].split('/* CSS Variables')[0];
 assert.match(source,/class="chat-history-row group/);
 assert.match(source,/class="chat-history-actions"/);
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try {
  for(const touch of [false,true]) {
   const context=await browser.newContext({hasTouch:touch,isMobile:touch,viewport:{width:800,height:600}});
   const page=await context.newPage();
   await page.setContent(`<style>${css}.chat-history-row{display:flex;width:260px}.title{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}button{box-sizing:border-box;padding:4px;border:0}</style><div class="chat-history-row"><span class="title">A very long session title that should use all available space</span><div class="chat-history-actions"><button>p</button><button>r</button><button>d</button></div></div>`);
   const width=()=>page.locator('.title').evaluate(n=>n.getBoundingClientRect().width);
   assert.equal(await width(),touch?200:260);
   if(!touch) {
    await page.locator('.chat-history-row').hover();assert.equal(await width(),200);
    await page.mouse.move(700,500);assert.equal(await width(),260);
    await page.keyboard.press('Tab');assert.equal(await width(),200);
    await page.locator('button').first().evaluate(n=>n.blur());assert.equal(await width(),260);
   }
   await context.close();
  }
 }finally{await browser.close();}
});
