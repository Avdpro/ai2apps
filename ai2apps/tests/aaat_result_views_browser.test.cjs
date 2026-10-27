const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const {chromium}=require('playwright');
test('shared views display real images, fit mobile, and restore history without network actions',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage({viewport:{width:390,height:844}});let writes=0;
 const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZ1kAAAAASUVORK5CYII=','base64');
 await page.route('https://fixture.test/**',route=>{if(route.request().method()!=='GET')writes++;return route.fulfill({contentType:'text/html',body:'<main id="result"></main>'});});
 await page.route('https://images.test/**',route=>route.fulfill({contentType:'image/png',body:png}));
 await page.goto('https://fixture.test');
 const base=path.resolve(__dirname,'../web/static');
 async function mount(){await page.addStyleTag({path:base+'/css/aaat_result_views.css'});await page.addScriptTag({path:base+'/js/aaat_result_views.js'});}
 await mount();
 const records=['table','cards'].map(layout=>({provider:'arbitrary.'+layout,view:{schema:'ai2apps.aaat-view/v1',id:layout,layout,title:'Owned result',columns:[{key:'status',label:'Status'}],items:[{id:'original',title:'Untrusted <script> window.compromised=true </script>',url:'https://source.test/original',image:{url:'https://images.test/observed.png'},summary:'Evidence summary',fields:{status:'partial'}}]}}));
 await page.evaluate(records=>{localStorage.setItem('saved',JSON.stringify(records));window.AI2AppsResultViews.render(document.getElementById('result'),records);},records);
 await page.waitForFunction(()=>[...document.images].length===2&&[...document.images].every(i=>i.complete&&i.naturalWidth>0));
 assert.equal(await page.locator('table tbody tr').count(),1);assert.equal(await page.locator('.aaat-view-card').count(),1);
 assert.equal(await page.evaluate(()=>window.compromised),undefined);
 assert.equal(await page.locator('.aaat-view-card a').getAttribute('href'),'https://source.test/original');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.reload();await mount();await page.evaluate(()=>window.AI2AppsResultViews.render(document.getElementById('result'),JSON.parse(localStorage.getItem('saved'))));
 assert.equal(await page.locator('.aaat-result-view').count(),2);assert.equal(writes,0);
 await page.setViewportSize({width:1280,height:900});assert.equal(await page.locator('.aaat-view-card').count(),1);
 }finally{await browser.close();}
});

test('missing, unsafe and failed images collapse in cards and tables on desktop and mobile',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();const base=path.resolve(__dirname,'../web/static');
 await page.route('https://images.test/broken',r=>r.abort());
 await page.setContent('<main id="result"></main>');
 await page.addStyleTag({path:base+'/css/aaat_result_views.css'});await page.addScriptTag({path:base+'/js/aaat_result_views.js'});
 for(const width of [390,1280]){
  await page.setViewportSize({width,height:900});
  for(const layout of ['cards','table']){
   await page.evaluate(layout=>window.AI2AppsResultViews.render(document.getElementById('result'),[{provider:'fixture.other',view:{schema:'ai2apps.aaat-view/v1',id:'missing',layout,title:'Results',columns:[],items:[{id:'none',title:'No image'},{id:'unsafe',title:'Unsafe image',image:{url:'javascript:bad'}},{id:'broken',title:'Broken image',image:{url:'https://images.test/broken'}}]}}]),layout);
   await page.waitForFunction(()=>[...document.querySelectorAll('.aaat-view-image')].every(n=>n.hidden));
   assert.deepEqual(await page.locator('.aaat-view-image').evaluateAll(ns=>ns.map(n=>n.getBoundingClientRect().height)),[0,0,0]);
   if(layout==='cards')assert.ok(await page.locator('.aaat-view-card').first().evaluate(n=>n.getBoundingClientRect().height<100));
   assert.equal(await page.locator('a,strong').count(),3);
  }
 }
 }finally{await browser.close();}
});

test('long card metadata is at most two lines with full hover text',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage({viewport:{width:390,height:844}}),base=path.resolve(__dirname,'../web/static');await p.setContent('<main id="result"></main>');
 await p.addStyleTag({path:base+'/css/aaat_result_views.css'});await p.addScriptTag({path:base+'/js/aaat_result_views.js'});
 await p.evaluate(()=>AI2AppsResultViews.render(document.querySelector('#result'),[{provider:'arbitrary.sources',view:{schema:'ai2apps.aaat-view/v1',id:'example',layout:'cards',title:'News',columns:[{key:'origin',label:''}],items:[{id:'a',title:'Article',fields:{origin:'www.cnn.com · '.repeat(30)}}]}}]));
 const d=p.locator('dd');assert.equal(await p.locator('dt').count(),0);assert.equal(await d.evaluate(n=>getComputedStyle(n).textAlign),'right');assert.equal(await d.getAttribute('title'),'www.cnn.com · '.repeat(30));assert.ok(await d.evaluate(n=>n.getBoundingClientRect().height<=parseFloat(getComputedStyle(n).lineHeight)*2+1));assert.equal(await d.evaluate(n=>getComputedStyle(n).webkitLineClamp),'2');
 }finally{await browser.close();}
});

test('masonry packs natural-height cards and reflows in result order on mobile',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const p=await browser.newPage({viewport:{width:760,height:1100}}),base=path.resolve(__dirname,'../web/static');
 await p.setContent('<main id="result"></main>');await p.addStyleTag({path:base+'/css/aaat_result_views.css'});await p.addScriptTag({path:base+'/js/aaat_result_views.js'});
 await p.evaluate(()=>{window.records=[{provider:'arbitrary.news',view:{schema:'ai2apps.aaat-view/v1',id:'masonry',layout:'cards',title:'Articles',columns:[{key:'source',label:''},{key:'date',label:''}],items:Array.from({length:6},(_,i)=>({id:String(i),title:'Article '+i,url:'https://example.com/'+i,summary:i===0?Array(20).fill('Long preview line').join('\n'):'Short preview',fields:{source:'example.com',date:'2026-10-26'}}))}}];AI2AppsResultViews.render(document.querySelector('#result'),records);});
 await p.waitForFunction(()=>[...document.querySelectorAll('.aaat-view-card')].every(n=>n.style.gridRowEnd.startsWith('span ')));
 const rects=()=>p.locator('.aaat-view-card').evaluateAll(ns=>ns.map(n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,bottom:r.bottom,height:r.height};}));
 let r=await rects();assert.ok(r[0].height>r[1].height+60);assert.equal(r[2].x,r[1].x);assert.ok(r[2].y<r[0].bottom);assert.ok(r[2].y>=r[1].bottom+11);
 assert.deepEqual(await p.locator('.aaat-view-card>a').allTextContents(),Array.from({length:6},(_,i)=>'Article '+i));
 await p.setViewportSize({width:390,height:1100});
 await p.waitForFunction(()=>{const ns=[...document.querySelectorAll('.aaat-view-card')];return ns.every((n,i)=>!i||n.getBoundingClientRect().top>=ns[i-1].getBoundingClientRect().bottom+11);});
 r=await rects();assert.ok(r.every(n=>n.x===r[0].x));assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await p.evaluate(()=>AI2AppsResultViews.render(document.querySelector('#result'),records));
 await p.waitForFunction(()=>document.querySelector('.aaat-view-card')?.style.gridRowEnd.startsWith('span '));
 assert.equal(await p.locator('.aaat-view-card').count(),6);
 }finally{await browser.close();}
});
