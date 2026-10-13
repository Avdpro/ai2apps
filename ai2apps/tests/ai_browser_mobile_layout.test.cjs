const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
test('Mobile library, Mini-App and tasks fit phone viewport and retain frame state',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage({viewport:{width:390,height:844},hasTouch:true});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const html=fs.readFileSync(path.join(__dirname,'../web/templates/mobile_ai_browser.html'),'utf8').split('{% block content %}')[1].split('{% endblock %}')[0];
 const css=fs.readFileSync(path.join(__dirname,'../web/static/css/ai_browser.css'),'utf8');await page.setContent('<style>[x-cloak]{display:none!important}body{margin:0}'+css+'</style>'+html);
 await page.evaluate((locale)=>{window.crypto.randomUUID=()=> 'test';window.AI2APPS_MOBILE_SURFACE=true;window.t=k=>locale[k]||k;window.fetch=async url=>({ok:true,json:async()=>url.includes('browser-profiles')?[{key:'default',name:'Default',is_default:true}]:{tasks:[],settings:{global_limit:4},domains:[]}});window.EventSource=class{addEventListener(){}close(){}};window.AI2AppsStudioMiniApps={list:async()=>({items:[{id:'search',name:'Search All',description:'Search several sources',source:'package',web_agent:{},provider:{digest:'1'}},{id:'shopping',name:'Shopping Pro',description:'Gifts and replenishment',source:'package',web_agent:{},provider:{digest:'1'}}]}),mount:async()=>({content_url:'data:text/html,<input id="query" value="retained">'})};},JSON.parse(fs.readFileSync(path.join(__dirname,'../web/i18n/zh.json'),'utf8')));
 await page.addScriptTag({path:path.join(__dirname,'../web/static/js/lucide.min.js')});await page.addScriptTag({path:path.join(__dirname,'../web/static/js/ai_browser.js')});await page.addScriptTag({path:path.join(__dirname,'../web/static/js/alpine.min.js')});
 await page.waitForTimeout(300);assert.deepEqual(errors,[]);await page.waitForSelector('.aib-mini-app-card');assert.equal(await page.locator('.aib-nav').isVisible(),true);assert.equal(await page.locator('.aib-main').isVisible(),false);
 await page.getByText('Search All',{exact:true}).click();await page.waitForSelector('iframe');await page.waitForTimeout(50);assert.equal(await page.locator('.aib-main').isVisible(),true);
 const bounds=await page.locator('iframe').boundingBox();assert(bounds.width<=390&&bounds.height>400&&bounds.y+bounds.height<845,JSON.stringify(bounds));
 await page.getByRole('button',{name:'任务',exact:true}).click();await page.waitForSelector('.aib-tasks',{state:'visible'});await page.getByRole('button',{name:'关闭',exact:true}).click();await page.waitForSelector('iframe',{state:'visible'});assert.equal(await page.locator('iframe').count(),1);assert.equal(await page.frameLocator('iframe').locator('#query').inputValue(),'retained');
 await page.getByRole('button',{name:'返回',exact:true}).click();await page.screenshot({path:'/private/tmp/ai-browser-mobile-library.png'});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
