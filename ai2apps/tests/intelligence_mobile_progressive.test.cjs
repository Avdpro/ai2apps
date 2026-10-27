const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {webkit}=require('playwright');
const root=path.join(__dirname,'..'),read=f=>fs.readFileSync(path.join(root,f),'utf8');
test('Mobile loads directory counts, then 20 cards per page and article detail on demand',async()=>{
 const browser=await webkit.launch({headless:true});
 try{
 const page=await browser.newPage({viewport:{width:390,height:850},hasTouch:true});
 const pageErrors=[];page.on('pageerror',error=>pageErrors.push(error.message));
 const catalog=JSON.parse(read('web/i18n/en.json'));
 const html=read('web/templates/system_apps/intelligence.html').split('{% block content %}')[1].split('{% endblock %}')[0].replace(/\{\{ t\('([^']+)'\) \}\}/g,(_,k)=>catalog[k]||k);
 await page.route('https://intel.test/**',r=>r.fulfill({contentType:'text/html',body:'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+html+'</html>'}));
 await page.goto('https://intel.test');await page.addStyleTag({content:read('web/static/css/intelligence.css')});
 await page.evaluate(catalog=>{
 window._t=catalog;window.AI2APPS_MOBILE_SURFACE=true;window.requests=[];window.revision=0;
 const channels=[{id:'c',name:'AI',sections:[{id:'s',name:'Section'}]},{id:'other',name:'Other',sections:[]}];
 const articles=Array.from({length:45},(_,i)=>({id:'a'+i,channel_id:'c',section_id:'s',title:'Article '+i,summary:'Summary '.repeat(12),body:'FULL BODY '+i,read:false,favorite:i===44,sources:[],updated_at:'2026-10-18T01:00:'+String(59-i).padStart(2,'0')+'Z'}));
 window.articleGate=new Promise(resolve=>window.releaseArticles=resolve);
 const json=value=>new Response(JSON.stringify(value),{headers:{'content-type':'application/json'}});
 window.fetch=async(input,options={})=>{
  const url=new URL(input,location.origin);requests.push({path:url.pathname,query:url.search,method:options.method||'GET'});
  if(url.pathname==='/v1/platform/intelligence'&&window.failPull)return new Response('<html>Unavailable</html>',{status:503});
  if(url.pathname==='/v1/platform/intelligence'&&window.holdDirectory)await window.directoryGate;
  if(url.pathname==='/v1/platform/intelligence')return json({progressive:true,channels:channels.map(c=>({...c,article_stats:{total:c.id==='c'?45:2,unread:c.id==='c'?(window.directoryUnread??articles.filter(a=>!a.read).length):2,favorite:c.id==='c'?1:0,sections:c.id==='c'?{s:45}:{},revision:String(revision)}})),articles:[],sources:[],runs:window.directoryRuns||[]});
  if(url.pathname.endsWith('/view'))return json({channel:channels.find(c=>url.pathname.includes('/'+c.id+'/')),sources:[],runs:window.channelRuns||[]});
  if(url.pathname.endsWith('/articles')){
   await articleGate;if(window.holdRefresh)await window.refreshGate;let list=articles;
   if(url.searchParams.get('section')==='$favorites')list=list.filter(a=>a.favorite);
   const q=url.searchParams.get('q');if(q)list=list.filter(a=>a.title.includes(q)||a.body.includes(q));
   if(url.searchParams.get('status')==='unread')list=list.filter(a=>!a.read);
   const offset=Number(url.searchParams.get('cursor')||0);
   return json({items:list.slice(offset,offset+20).map(({body,...a})=>({...a,_summary:true})),total:list.length,next_cursor:list.length>offset+20?String(offset+20):null});
  }
  if(/\/articles\/a\d+$/.test(url.pathname)){
   const article=articles.find(a=>url.pathname.endsWith('/'+a.id));
   if(options.method==='PATCH'){Object.assign(article,JSON.parse(options.body));revision++;}
   return json(article);
  }
  return json(url.pathname.endsWith('/entities')?{items:[]}:url.pathname.endsWith('/conversation')?{turns:[]}:[]);
 };
 },catalog);
 for(const name of ['mini_app_chat','intelligence_i18n','intelligence_cards','intelligence_entities','intelligence_article_chat','intelligence'])await page.addScriptTag({content:read('web/static/js/'+name+'.js')});
 await page.waitForFunction(()=>document.querySelector('#intel-app').dataset.channelLoad==='ready');
 assert.equal(await page.locator('[data-channel="c"] .count').innerText(),'45');
 assert.equal(await page.locator('[data-channel="other"] .count').innerText(),'2');
 assert.deepEqual(await page.evaluate(()=>requests.map(r=>r.path+r.query)),['/v1/platform/intelligence?view=channels']);
 // Channel-directory pull reloads only summary metadata, even when begun on a card.
 await page.evaluate(()=>{
  window.directoryTouch=(type,x,y,count=1)=>{
   const event=new Event(type,{bubbles:true,cancelable:true}),touch={identifier:7,clientX:x,clientY:y};
   Object.defineProperty(event,'touches',{value:type==='touchend'?[]:Array.from({length:count},()=>touch)});
   Object.defineProperty(event,'changedTouches',{value:[touch]});document.querySelector('#channel-list [data-channel="c"] .channel-label').dispatchEvent(event);
  };
  window.directoryBefore=requests.length;
  directoryTouch('touchstart',150,200);directoryTouch('touchmove',150,240);directoryTouch('touchend',150,240);
  directoryTouch('touchstart',150,200);directoryTouch('touchmove',0,210);directoryTouch('touchend',0,210);
 });
 assert.equal(await page.evaluate(()=>requests.length),await page.evaluate(()=>directoryBefore));
 await page.evaluate(()=>{
  directoryUnread=46;directoryRuns=[{id:'refresh',channel_id:'c',status:'running',started_at:'2026-10-20T02:00:00Z'}];
  holdDirectory=true;window.directoryGate=new Promise(resolve=>window.releaseDirectory=resolve);
  directoryTouch('touchstart',150,200);directoryTouch('touchmove',150,350);
 });
 assert.equal(await page.locator('.intel-sidebar .intel-pull-refresh-label').innerText(),'Release to refresh');
 await page.evaluate(()=>directoryTouch('touchend',150,350));
 await page.waitForFunction(()=>document.querySelector('.intel-sidebar .intel-pull-refresh').classList.contains('is-refreshing'));
 await page.evaluate(()=>{
  directoryTouch('touchstart',150,200);directoryTouch('touchmove',150,350);directoryTouch('touchend',150,350);
  // A click generated by the consumed pull must not open the channel.
  document.querySelector('#channel-list [data-channel="c"]').click();
  holdDirectory=false;releaseDirectory();
 });
 await page.waitForFunction(()=>document.querySelector('.intel-sidebar .intel-pull-refresh').hidden);
 assert.equal(await page.locator('#intel-app').getAttribute('data-mobile-page'),'channels');
 assert.equal(await page.locator('[data-channel="c"] .count').innerText(),'46');
 assert.match(await page.locator('[data-channel="c"] .channel-update-status').innerText(),/Refreshing/i);
 assert.equal(await page.evaluate(()=>requests.slice(directoryBefore).every(r=>r.path==='/v1/platform/intelligence'&&r.query==='?view=channels'&&r.method==='GET')),true);
 assert.equal(await page.evaluate(()=>requests.length-directoryBefore),1);
 await page.waitForTimeout(360);
 await page.evaluate(()=>{
  directoryUnread=45;directoryRuns=[{id:'refresh',channel_id:'c',status:'completed',started_at:'2026-10-20T02:00:00Z',finished_at:'2026-10-20T02:05:00Z'}];
  directoryTouch('touchstart',150,200);directoryTouch('touchmove',150,350);directoryTouch('touchend',150,350);
 });
 await page.waitForFunction(()=>document.querySelector('.intel-sidebar .intel-pull-refresh').hidden);
 assert.match(await page.locator('[data-channel="c"] .channel-update-status').getAttribute('title'),/2026|10\/20|Oct 20/);
 assert.doesNotMatch(await page.locator('[data-channel="c"] .channel-update-status').innerText(),/Refreshing/i);
 await page.evaluate(()=>{delete window.directoryUnread;delete window.directoryRuns;});
 await page.waitForTimeout(360);
 await page.locator('#channel-list [data-channel="c"]').click();
 await page.waitForFunction(()=>requests.some(r=>r.path.endsWith('/articles')));
 assert.equal(await page.locator('#intel-content [data-article]').count(),0);
 await page.locator('#intel-content [role="status"]').waitFor({state:'visible'});
 await page.evaluate(()=>releaseArticles());
 await page.waitForFunction(()=>document.querySelectorAll('#intel-content [data-article]').length===20);
 assert.equal(await page.locator('#article-count').innerText(),'45');
 assert.equal(await page.locator('[data-section="$favorites"] span').innerText(),'1');
 await page.locator('[data-list-more="articles"]').scrollIntoViewIfNeeded();
 await page.evaluate(()=>{window.firstCard=document.querySelector('#intel-content [data-article]');window.beforeScroll=document.querySelector('.intel-main').scrollTop;});
 await page.locator('[data-list-more="articles"]').click();
 await page.waitForFunction(()=>document.querySelectorAll('#intel-content [data-article]').length===40);
 assert.equal(await page.evaluate(()=>firstCard===document.querySelector('#intel-content [data-article]')),true);
 assert.equal(await page.evaluate(()=>document.querySelector('.intel-main').scrollTop>beforeScroll-10),true);
 await page.locator('#intel-content [data-article="a20"]').scrollIntoViewIfNeeded();
 await page.locator('#intel-content [data-article="a20"]').click();
 await page.waitForFunction(()=>document.querySelector('#intel-article-reader').textContent.includes('FULL BODY 20'));
 assert.equal(await page.evaluate(()=>requests.some(r=>r.path.endsWith('/articles/a20')&&r.method==='PATCH')),true);
 assert.equal(await page.locator('.intel-article-head .intel-favorite + [data-article-chat]').count(),1);
 assert.equal(await page.locator('#mobile-article-actions [data-article-chat-purpose=research]').count(),0);
 const articleChat=page.locator('.intel-article-head [data-article-chat]:not([data-article-chat-purpose])');
 const favorite=page.locator('.intel-article-head .intel-favorite');
 await articleChat.waitFor({state:'visible'});
 assert.equal(await favorite.locator('[data-favorite-label]').isVisible(),false);
 const [chatBox,favoriteBox]=await page.evaluate(()=>['[data-article-chat]','.intel-favorite'].map(selector=>document.querySelector('.intel-article-head '+selector).getBoundingClientRect().toJSON()));
 assert.ok(chatBox.x+chatBox.width<=favoriteBox.x);
 assert.ok(chatBox.height>=44&&favoriteBox.height>=44);
 const researchButton=page.locator('.intel-article-head [data-article-chat-purpose=research]');
 assert.equal(await researchButton.isVisible(),true);
 assert.equal(await researchButton.locator('[data-lucide=telescope]').count(),1);
 assert.equal(await page.evaluate(()=>requests.filter(r=>r.path==='/v1/platform/intelligence').every(r=>r.query==='?view=channels')),true);
 // A stale/incomplete Mini-Chat SDK must fail locally without blocking reading.
 await page.evaluate(()=>{window.savedMiniMount=AI2AppsMiniAppChat.mount;delete AI2AppsMiniAppChat.mount;});
 await articleChat.click();
 await page.waitForTimeout(100);
 assert.deepEqual(pageErrors,[]);
 assert.equal(await page.locator('#intel-app').getAttribute('data-channel-load'),'ready');
 assert.match(await page.locator('#intel-article-reader').innerText(),/FULL BODY 20/);
 assert.equal(await page.locator('.intel-article-chat').count(),0);
 // Read count includes unloaded pages and is refreshed without downloading all articles.
 assert.equal(await page.locator('[data-channel="c"] .count').innerText(),'44');
 // Article chat is a nested reader route: both button and swipe return to article.
 await page.evaluate(()=>{AI2AppsMiniAppChat.mount=window.savedMiniMount;});
 await articleChat.click();
 await page.waitForSelector('.intel-article-chat:not([hidden])');
 assert.equal(await page.locator('#intel-app').getAttribute('data-mobile-page'),'reader');
 await page.locator('#intel-reader [data-mobile-back]').click();
 assert.equal(await page.locator('#intel-app').getAttribute('data-mobile-page'),'reader');
 assert.equal(await page.locator('#intel-article-reader').isVisible(),true);
 assert.match(await page.locator('#intel-article-reader').innerText(),/FULL BODY 20/);
 await articleChat.click();
 await page.waitForSelector('.intel-article-chat:not([hidden])');
 await page.evaluate(()=>{
  for(const [type,x] of [['touchstart',80],['touchend',240]]){
   const event=new Event(type,{bubbles:true,cancelable:true}),touch={clientX:x,clientY:250};
   Object.defineProperty(event,'touches',{value:type==='touchend'?[]:[touch]});
   Object.defineProperty(event,'changedTouches',{value:[touch]});
   document.querySelector('.intel-layout').dispatchEvent(event);
  }
 });
 assert.equal(await page.locator('#intel-app').getAttribute('data-mobile-page'),'reader');
 assert.equal(await page.locator('#intel-article-reader').isVisible(),true);
 // Return to the list and select a saved article outside the first 40 cards.
 await page.locator('#intel-reader [data-mobile-back]').click();
 // Pull refresh reloads the current loaded window even when the revision is unchanged.
 await page.evaluate(()=>{
  window.pullEvent=(type,x,y,count=1)=>{
   const event=new Event(type,{bubbles:true,cancelable:true}),touch={identifier:1,clientX:x,clientY:y};
   Object.defineProperty(event,'touches',{value:type==='touchend'?[]:Array.from({length:count},()=>touch)});
   Object.defineProperty(event,'changedTouches',{value:[touch]});document.querySelector('#intel-content').dispatchEvent(event);
  };
  window.refreshBaseline=requests.filter(r=>r.path.endsWith('/articles')).length;
  document.querySelector('.intel-main').scrollTop=120;
  pullEvent('touchstart',150,200);pullEvent('touchmove',150,350);pullEvent('touchend',150,350);
 });
 assert.equal(await page.locator('.intel-main .intel-pull-refresh').isVisible(),false);
 await page.evaluate(()=>{
  document.querySelector('.intel-main').scrollTop=0;
  pullEvent('touchstart',150,200);pullEvent('touchmove',150,240);pullEvent('touchend',150,240);
  pullEvent('touchstart',150,200);pullEvent('touchmove',0,220);pullEvent('touchend',0,220);
  pullEvent('touchstart',150,200);pullEvent('touchmove',150,350,2);pullEvent('touchend',150,350);
 });
 assert.equal(await page.evaluate(()=>requests.filter(r=>r.path.endsWith('/articles')).length),await page.evaluate(()=>refreshBaseline));
 await page.evaluate(()=>{
  holdRefresh=true;window.refreshGate=new Promise(resolve=>window.releaseRefresh=resolve);
  pullEvent('touchstart',150,200);pullEvent('touchmove',150,350);
 });
 assert.equal(await page.locator('.intel-main .intel-pull-refresh-label').innerText(),'Release to refresh');
 await page.evaluate(()=>pullEvent('touchend',150,350));
 await page.waitForFunction(()=>document.querySelector('.intel-main .intel-pull-refresh').classList.contains('is-refreshing'));
 assert.equal(await page.locator('.intel-main .intel-pull-refresh-label').innerText(),'Refreshing…');
 await page.evaluate(()=>{pullEvent('touchstart',150,200);pullEvent('touchmove',150,350);pullEvent('touchend',150,350);holdRefresh=false;releaseRefresh();});
 await page.waitForFunction(()=>document.querySelector('.intel-main .intel-pull-refresh').hidden);
 assert.equal(await page.locator('#intel-content [data-article]').count(),40);
 assert.equal(await page.evaluate(()=>requests.filter(r=>r.path.endsWith('/articles')).length),await page.evaluate(()=>refreshBaseline+2));
 assert.equal(await page.evaluate(()=>requests.some(r=>r.method==='POST'&&r.path.endsWith('/runs'))),false);
 await page.evaluate(()=>{failPull=true;document.querySelector('.intel-main').scrollTop=0;pullEvent('touchstart',150,200);pullEvent('touchmove',150,350);pullEvent('touchend',150,350);});
 await page.waitForFunction(()=>document.querySelector('.intel-notice:not([hidden])')||!document.querySelector('#intel-notice').hidden);
 await page.waitForFunction(()=>document.querySelector('.intel-main .intel-pull-refresh').hidden);
 assert.equal(await page.locator('.intel-main').getAttribute('aria-busy'),null);
 assert.equal(await page.locator('#intel-content [data-article]').count(),40);
 await page.evaluate(()=>failPull=false);

 await page.locator('[data-section="$favorites"]').scrollIntoViewIfNeeded();
 await page.locator('[data-section="$favorites"]').click();
 await page.waitForFunction(()=>document.querySelector('#intel-content [data-article="a44"]'));
 assert.equal(await page.locator('#intel-content [data-article]').count(),1);
 await page.evaluate(()=>{const input=document.querySelector('#search-articles');input.value='FULL BODY 44';input.dispatchEvent(new Event('input'));});
 await page.waitForFunction(()=>requests.some(r=>r.query.includes('q=FULL+BODY+44')));
 assert.equal(await page.locator('#intel-content [data-article="a44"]').count(),1);
 // History may put an old terminal run before the current summary during merge.
 await page.evaluate(()=>{
  window.directoryRuns=[{id:'live',channel_id:'c',status:'running',started_at:'2026-10-20T03:00:00Z'}];
  window.channelRuns=[{...directoryRuns[0],message:'Collecting',progress:{phase:'article',pages_read:1}},
   {id:'old',channel_id:'c',status:'completed',started_at:'2026-10-19T03:00:00Z',message:'Done'}];
  const select=document.querySelector('#mobile-category');select.insertAdjacentHTML('beforeend','<option value="runs">Runs</option>');
  select.value='runs';select.dispatchEvent(new Event('change'));
 });
 await page.waitForFunction(()=>document.querySelector('.intel-run-progress')?.textContent.includes('1'));
 const beforeViews=await page.evaluate(()=>requests.filter(r=>r.path.endsWith('/view')).length);
 await page.evaluate(()=>{channelRuns[0].progress.pages_read=8;channelRuns[0].message='Progress eight';});
 await page.waitForFunction(()=>document.querySelector('.intel-run')?.textContent.includes('Progress eight'),{},{timeout:12000});
 assert.ok(await page.evaluate(()=>requests.filter(r=>r.path.endsWith('/view')).length)>beforeViews);
 await page.evaluate(()=>{directoryRuns[0].status='completed';channelRuns[0].status='completed';channelRuns[0].message='Finished latest';});
 await page.waitForFunction(()=>document.querySelector('.intel-run')?.textContent.includes('Finished latest'),{},{timeout:12000});
 assert.equal(await page.locator('.intel-run-progress').count(),0);
 // Opening the topic tab only reads existing results; model work needs a button.
 await page.selectOption('#mobile-category','topics');
 await page.waitForTimeout(100);
 assert.equal(await page.evaluate(()=>requests.some(r=>r.path.endsWith('/topics')&&r.method==='POST')),false);
 assert.equal(await page.locator('#channel-auto-topics').count(),1);
 await page.close();
 }finally{await browser.close();}
});
