const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const {chromium}=require('playwright');
const css=fs.readFileSync(path.resolve(__dirname,'../web/static/css/mobile_chat.css'),'utf8');
for(const width of [320,390,768])test('User bubble content sizing at '+width+'px',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width,height:844}});
  await page.setContent('<style>'+css+'</style><main class="mchat"><div class="mchat-list"><div class="mchat-message user" id="short"><span class="mchat-message-meta">Agent</span><div>再试试</div></div><div class="mchat-message assistant">Assistant response</div><div class="mchat-message user" id="long"><div></div></div><div class="mchat-message user" id="url"><div></div><span class="mchat-file-note">📎 attachment-with-a-very-long-filename.png</span></div></div></main>');
  await page.locator('#long>div').evaluate(n=>n.textContent='这是一段较长的用户消息，用来验证自然换行与最大宽度，同时不影响普通助手消息的布局。'.repeat(5));
  await page.locator('#url>div').evaluate(n=>n.textContent='https://example.com/'+ 'unbroken'.repeat(50));
  const layout=await page.evaluate(()=>{
   const rect=id=>{const n=document.getElementById(id),r=n.getBoundingClientRect();return {width:r.width,height:r.height,right:r.right,overflow:n.scrollWidth>n.clientWidth+1};};
   const list=document.querySelector('.mchat-list'),style=getComputedStyle(list),r=list.getBoundingClientRect();
   return {short:rect('short'),long:rect('long'),url:rect('url'),available:list.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight),right:r.right-parseFloat(style.paddingRight),label:getComputedStyle(document.querySelector('.mchat-message-meta')).display,pageOverflow:document.documentElement.scrollWidth>innerWidth};
  });
  assert.ok(layout.short.width<115);assert.ok(layout.short.height<46);
  assert.ok(Math.abs(layout.short.right-layout.right)<1);assert.equal(layout.label,'none');
  for(const bubble of [layout.long,layout.url]){assert.ok(bubble.width<=layout.available*.85+1);assert.ok(!bubble.overflow);}
  assert.ok(layout.long.height>layout.short.height);assert.ok(!layout.pageOverflow);
  if(width===390)await page.screenshot({path:'/tmp/ai2apps-mobile-user-bubbles.png'});
 }finally{await browser.close();}
});
