const test=require('node:test'),assert=require('node:assert/strict'),{spawnSync}=require('node:child_process'),path=require('node:path'),{chromium,webkit}=require('playwright');
const root=path.resolve(__dirname,'../..');
const result=spawnSync(path.join(root,'.venv/bin/python'),['-c',"import json;from ai2apps.intelligence.html_export import CSS,CARD_CSS,CARD_SCRIPT;print(json.dumps([CSS,CARD_CSS,CARD_SCRIPT]))"],{cwd:root,encoding:'utf8'});
assert.equal(result.status,0,result.stderr);const [css,cardCSS,script]=JSON.parse(result.stdout);
for(const engine of ['chromium','webkit'])test(engine+' immediate touch feedback, quick tap, scroll and cancel',async()=>{
 const browser=await(engine==='webkit'?webkit.launch():chromium.launch({channel:'chrome'}));
 try{const page=await browser.newPage({viewport:{width:390,height:700},hasTouch:true,isMobile:true});
 await page.setContent('<meta name="viewport" content="width=device-width,initial-scale=1"><style>'+css+cardCSS+'</style><article><details class="article-card no-cover"><summary><span class="read-ribbon"><span class="ribbon-band"><span class="unread">未读</span><span class="read">已读</span></span></span><h2>无图文章标题</h2><p class="card-excerpt">这是一段比较长的文章简介，用来检查折叠卡片的三行省略效果。这是一段比较长的文章简介，用来检查折叠卡片的三行省略效果。这是一段比较长的文章简介，用来检查折叠卡片的三行省略效果。这是一段比较长的文章简介，用来检查折叠卡片的三行省略效果。这是一段比较长的文章简介，用来检查折叠卡片的三行省略效果。这是一段比较长的文章简介，用来检查折叠卡片的三行省略效果。这是一段比较长的文章简介，用来检查折叠卡片的三行省略效果。这是一段比较长的文章简介，用来检查折叠卡片的三行省略效果。这是一段比较长的文章简介，用来检查折叠卡片的三行省略效果。这是一段比较长的文章简介，用来检查折叠卡片的三行省略效果。这是一段比较长的文章简介，用来检查折叠卡片的三行省略效果。这是一段比较长的文章简介，用来检查折叠卡片的三行省略效果。</p></summary><div class="article-content"><p>Article content</p></div></details></article>');await page.addScriptTag({content:script});
 const layout=await page.locator('summary').evaluate(el=>{const h=el.querySelector('h2'),p=el.querySelector('.card-excerpt');return{top:getComputedStyle(el).paddingTop,inset:getComputedStyle(h).paddingLeft,height:p.getBoundingClientRect().height,line:parseFloat(getComputedStyle(p).lineHeight),clamp:getComputedStyle(p).webkitLineClamp,overflow:p.scrollHeight>p.clientHeight};});
 assert.equal(layout.top,'0px');assert.equal(layout.inset,'52px');assert.equal(layout.clamp,'3');assert(layout.height<=layout.line*3+1);assert(layout.overflow);
 await page.screenshot({path:'/tmp/compact-card-'+engine+'.png'});
 const event=async(type,extra={})=>page.evaluate(({type,extra})=>{const summary=document.querySelector('summary');const accepted=summary.dispatchEvent(new PointerEvent(type,{pointerId:1,pointerType:'touch',isPrimary:true,button:0,clientX:80,clientY:80,bubbles:true,cancelable:true,...extra}));return{accepted,pressed:summary.hasAttribute('data-pressed'),background:getComputedStyle(document.querySelector('article')).backgroundColor};},{type,extra});
 let state=await event('pointerdown');assert(state.accepted);assert(state.pressed);assert.equal(state.background,'rgb(241, 244, 248)');
 state=await event('pointerup');assert(state.pressed);await page.waitForFunction(()=>!document.querySelector('summary').hasAttribute('data-pressed'));
 await event('pointerdown');state=await event('pointermove',{clientY:100});assert(!state.pressed);assert.equal(state.background,'rgb(255, 255, 255)');
 await event('pointerdown');state=await event('pointercancel');assert(!state.pressed);
 await page.locator('summary').tap();assert(await page.locator('details').evaluate(e=>e.open));assert(await page.locator('.card-excerpt').isHidden());await page.waitForFunction(()=>!document.querySelector('summary').hasAttribute('data-pressed'));
 await page.locator('summary').tap();assert(!(await page.locator('details').evaluate(e=>e.open)));
 }finally{await browser.close();}
});
