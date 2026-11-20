const {chromium}=require('playwright'),fs=require('fs'),assert=require('node:assert/strict');
const root=require('node:path').resolve(__dirname,'../web/static/builtin_mini_apps/share-works/web');
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});for(const width of [1440,390]){
 const page=await browser.newPage({viewport:{width,height:1000}});
 await page.route('https://fixture.test/**',route=>{const file=new URL(route.request().url()).pathname.split('/').pop()||'index.html';let body=fs.readFileSync(root+'/'+file);if(file==='index.html')body=body.toString().replace('<script src="host.js"></script>','');return route.fulfill({body,contentType:file.endsWith('.js')?'text/javascript':'text/html'});});
 await page.addInitScript(()=>{window.checkStarted=false;window.ShareHost={request:async(action,fields)=>{
 if(action==='preferences')return{targets:{hf:{repo:'alice/hf',application_url:'https://alice-hf.static.hf.space/'},ms:{repo:'alice/ms',application_url:'https://alice-ms.ms.show/'}}};
 if(action==='history')return{items:[]};
 if(action==='check'){window.checkStarted=true;await new Promise(resolve=>setTimeout(resolve,200));return{account:'alice',repo:fields.repo,application_url:'https://official-resolved.static.hf.space/'};}
 }};});
 await page.goto('https://fixture.test/index.html?locale=zh');await page.waitForFunction(()=>document.querySelector('#repo').value==='alice/hf');assert.equal(await page.inputValue('#application_url'),'https://alice-hf.static.hf.space/');
 await page.selectOption('#provider','ms');assert.equal(await page.inputValue('#repo'),'alice/ms');assert.equal(await page.inputValue('#application_url'),'https://alice-ms.ms.show/');await page.selectOption('#provider','hf');assert.equal(await page.inputValue('#repo'),'alice/hf');
 await page.fill('#repo','alice/new');await page.waitForFunction(()=>document.querySelector('#application_url').value==='https://official-resolved.static.hf.space/');
 await page.evaluate(()=>window.checkStarted=false);await page.fill('#repo','alice/other');await page.waitForFunction(()=>window.checkStarted);await page.fill('#application_url','https://custom.static.hf.space');await page.waitForTimeout(250);assert.equal(await page.inputValue('#application_url'),'https://custom.static.hf.space');
 await page.reload();await page.waitForFunction(()=>document.querySelector('#repo').value==='alice/hf');assert.equal(await page.inputValue('#application_url'),'https://alice-hf.static.hf.space/');await page.close();
}await browser.close();console.log('Desktop/Mobile target restoration, provider isolation, metadata autofill, manual override race and reload fixtures passed.');})();
