const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
test('assistance and unread ribbons occupy opposite corners in regular and compact Bot cards',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage({viewport:{width:900,height:500}});const css=fs.readFileSync(__dirname+'/../web/static/css/messager.css','utf8');
 const card='<button class="messager-person messager-bot-card" style="position:relative;width:260px"><span class="sidebar-person-text"><strong>Bot fixture</strong></span><span class="bot-assistance-ribbon" role="img" aria-label="Waiting for your help"><span>!</span></span><span class="bot-unread-ribbon"><span class="bot-unread-ribbon-band">3</span></span></button>';
 await page.setContent('<style>'+css+'</style><div class="messager-sidebar">'+card+'</div><div class="messager-sidebar sidebar-compact">'+card.replace('width:260px','width:64px')+'</div>');
 for(const row of await page.locator('.messager-bot-card').all()){
  const value=await row.evaluate(e=>{const a=e.querySelector('.bot-assistance-ribbon'),u=e.querySelector('.bot-unread-ribbon');return {color:getComputedStyle(a.firstElementChild).backgroundColor,white:getComputedStyle(a.firstElementChild).color,left:u.getBoundingClientRect().left,right:a.getBoundingClientRect().right,width:e.clientWidth,aLeft:a.getBoundingClientRect().left,uRight:u.getBoundingClientRect().right};});
  assert.equal(value.color,'rgb(245, 158, 11)');assert.equal(value.white,'rgb(255, 255, 255)');assert(value.right>value.left+value.width/2);
 }
 await page.screenshot({path:'/tmp/bot-assistance-ribbons.png'});
 }finally{await browser.close();}
});
