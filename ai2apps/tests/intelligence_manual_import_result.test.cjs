const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');const root=path.join(__dirname,'..'),read=p=>fs.readFileSync(path.join(root,p),'utf8');
for(const mode of ['existing','committed','pending','unknown'])test(`manual import ${mode} without replay`,async()=>{
 const mobile=mode!=='existing';
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{const page=await browser.newPage({viewport:{width:mobile?390:1440,height:900}});
 const catalog=JSON.parse(read('web/i18n/en.json'));
 const html=read('web/templates/system_apps/intelligence.html').split('{% block content %}')[1].split('{% endblock %}')[0].replace(/\{\{ t\('([^']+)'\) \}\}/g,(_,k)=>catalog[k]||k);
 await page.route('https://intel.test/**',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">'+html}));await page.goto('https://intel.test');
 await page.addStyleTag({content:read('web/static/css/intelligence.css')});
 await page.evaluate(({mobile,catalog,mode})=>{
  window._t=catalog;window.AI2APPS_MOBILE_SURFACE=mobile;window.EventSource=class{addEventListener(){}close(){}};
  const article={id:'a',channel_id:'c',title:'Saved article',summary:'Summary',body:'Entire original [1]',updated_at:'2026-10-25T02:00:00Z',sources:[{url:'https://example.org/article'}],images:[],manual_import:true};
  const state={channels:[{id:'c',name:'Channel',sections:[]}],articles:[],sources:[],runs:[]};
  let submitted=false,lookups=0;window.requests=[];const timer=window.setTimeout;window.setTimeout=(fn,ms,...args)=>timer(fn,ms===2000?1:ms,...args);
  window.fetch=async(url,options={})=>{
   requests.push({url,method:options.method||'GET'});
   let value=state;
   if(url.includes('browser-profiles'))value=[{key:'default',name:'Default'}];
   else if(url.includes('/import-result?')){lookups++;const saved=!mobile||(submitted&&mode!=='unknown'&&(mode!=='pending'||lookups>2));if(saved)state.articles=[article];value={article:saved?article:null};}
   else if(url.endsWith('/import-link')){submitted=true;if(mode==='unknown'){let now=Date.now();Date.now=()=>now+=180001;}throw new TypeError('Network connection lost after commit');}
   else if(url.endsWith('/articles/a'))value=article;
   else if(url.endsWith('/conversation'))value={turns:[]};
   else if(url.endsWith('/entities'))value={items:[]};
   return {ok:true,status:200,json:async()=>JSON.parse(JSON.stringify(value))};
  };
 },{mobile,catalog,mode});
 for(const name of ['mini_app_chat','intelligence_i18n','intelligence_cards','intelligence_entities','intelligence'])await page.addScriptTag({content:read('web/static/js/'+name+'.js')});
 await page.waitForSelector('[data-channel=c]');await page.locator('button[data-channel=c]').click();
 await page.locator('#import-article').evaluate(e=>e.click());await page.waitForSelector('#import-dialog[open]');
 await page.fill('#import-url','https://example.org/article');await page.locator('#import-form button[type=submit]').click();
 if(mode==='unknown'){await page.waitForFunction(()=>document.querySelector('#import-form .intel-form-error').textContent.includes('unconfirmed'));assert.equal(await page.locator('#import-dialog').evaluate(e=>e.open),true);assert.equal((await page.evaluate(()=>requests)).filter(r=>r.method==='POST'&&r.url.endsWith('/import-link')).length,1);return;}
 await page.waitForFunction(()=>!document.querySelector('#import-dialog').open);
 await page.waitForSelector('#intel-article-reader h1');assert.equal(await page.locator('#intel-article-reader h1').innerText(),'Saved article');
 const requests=await page.evaluate(()=>window.requests);
 assert.equal(requests.filter(r=>r.url.endsWith('/import-link')&&r.method==='POST').length,mobile?1:0);
 assert.equal(requests.filter(r=>r.url.endsWith('/import-url')&&r.method==='POST').length,0);
 assert.ok(requests.filter(r=>r.url.includes('/import-result?')).length>=(mobile?2:1));
 assert.equal(await page.locator('#import-form .intel-form-error').innerText(),'');
 }finally{await browser.close();}
});
