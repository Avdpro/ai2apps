const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/intelligence_social.js','utf8');
function env(){const e={window:{},URL,URLSearchParams,setTimeout:fn=>fn()};vm.createContext(e);vm.runInContext(source,e);return e.window.IntelligenceSocial;}
test('YouTube skips already collected videos before opening and limits detail reads',async()=>{
 const social=env(),visited=[];
 const options={source:{id:'s',url:'https://youtube.com/@OpenAI/videos'},session:{client:{scroll:async()=>{},handlePageAccess:async()=>({}),extractYouTubeFeed:async()=>({items:[]})}},channelId:'c',seenURLs:[],onProgress:()=>{},
 api:async(_,__,body)=>({candidates:body.candidates.slice(1),skipped:1}),
 read:async(_,url,opts)=>{visited.push(url);return opts.youtube==='feed'?{items:Array.from({length:24},(_,i)=>({url:'https://youtube.com/watch?v='+i,title:'video'+i}))}:{url,title:'video',text:'description',coverage:'description'};}};
 const result=await social.collectYouTube(options);assert.equal(result.pages.length,2);assert.equal(visited.length,3);assert.equal(result.skipped,1);assert(!visited.includes('https://youtube.com/watch?v=0'));
});
test('YouTube challenge stops without visiting remaining videos',async()=>{
 const social=env(),visited=[];
 const result=await social.collectYouTube({source:{id:'s',url:'https://youtube.com/watch?v=abcdefghijk'},session:{},channelId:'c',seenURLs:[],onProgress:()=>{},api:async()=>({candidates:[{url:'one'},{url:'two'}],skipped:0}),read:async(_,url)=>{visited.push(url);const e=Error('captcha');e.outcome='needs_user';throw e;}});
 assert.equal(result.status,'needs_user');assert.equal(visited.length,1);assert.equal(result.pages.length,0);
});
test('feed extractor emits stable watch URLs and ignores duplicate and non-video links',async()=>{
 const sdk=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');
 const links=['/watch?v=abcdefghijk&list=foo','/shorts/abcdefghijk','/watch?v=ZYXWVUTSRQP','/watch?v=bad'].map(href=>({href,getAttribute:()=> 'Video',innerText:'Video',closest:()=>null}));
 const e={URL,location:{hostname:'www.youtube.com',href:'https://www.youtube.com/@OpenAI/videos'},document:{title:'OpenAI',querySelector:()=>({querySelectorAll:()=>links})}};
 vm.createContext(e);vm.runInContext('this.client={'+sdk.slice(sdk.indexOf('        async extractYouTubeFeed()'),sdk.indexOf('        async extractYouTubeVideo()'))+'}',e);
 e.client.callJSON=async code=>vm.runInContext('('+code+')()',e);
 const result=await e.client.extractYouTubeFeed();assert.equal(result.items.length,2);assert.equal(result.items[0].url,'https://www.youtube.com/watch?v=abcdefghijk');
});
test('YouTube waits for delayed SPA cards without reloading the source',async()=>{
 const sdk=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');
 const e={URL,setTimeout:fn=>fn()};vm.createContext(e);
 vm.runInContext('this.client={'+sdk.slice(sdk.indexOf('        async readPage(options={})'),sdk.indexOf('        async submitSocialSearch('))+'}',e);
 let navigations=0,reads=0;
 Object.assign(e.client,{contextId:'c',connection:{command:async method=>{if(method==='browsingContext.navigate')navigations++;}},waitForStability:async()=>({stable:true,page:{url:'https://www.youtube.com/@OpenAI/videos'}}),handlePageAccess:async()=>({classification:'ready'}),extractYouTubeFeed:async()=>({url:'https://www.youtube.com/@OpenAI/videos',text:++reads===3?'Video':'',items:reads===3?[{title:'Video'}]:[]})});
 const result=await e.client.readPage({url:'https://www.youtube.com/@OpenAI/videos',new_tab:false,youtube:'feed'});
 assert.equal(result.outcome,'success');assert.equal(navigations,1);assert.equal(reads,3);
});
test('search source builder encodes keywords and preserves selected filters',()=>{
 const social=env();const url=new URL(social.sourceURL('youtube-search','腕表 评测','https://youtube.com/results?search_query=old&sp=CAI%3D'));
 assert.equal(url.searchParams.get('search_query'),'腕表 评测');assert.equal(url.searchParams.get('sp'),'CAI=');
 assert.equal(social.sourceURL('youtube-topic','#watches'),'https://www.youtube.com/hashtag/watches');
 assert.throws(()=>social.sourceURL('youtube-search',' '));assert.throws(()=>social.sourceURL('youtube-topic','two words'));
});
test('search results follow the same pending-video dedup path, never digest the search page',async()=>{
 const social=env(),readURLs=[];const sourceURL='https://www.youtube.com/results?search_query=watches';
 const result=await social.collectYouTube({source:{id:'s',url:sourceURL},session:{client:{scroll:async()=>{},handlePageAccess:async()=>({}),extractYouTubeFeed:async()=>({items:[]})}},channelId:'c',seenURLs:[],onProgress:()=>{},read:async(_,url)=>{readURLs.push(url);return {items:[{url:'https://www.youtube.com/watch?v=abcdefghijk',title:'watch'}]};},api:async(_,__,body)=>{assert.equal(body.candidates.length,1);return {candidates:[],skipped:1};}});
 assert.equal(result.pages.length,0);assert.equal(result.skipped,1);assert.deepEqual(readURLs,[sourceURL]);
});
test('Weibo source input supports stable account IDs and topic queries',()=>{
 const social=env();assert.equal(social.sourceURL('weibo-account','1938210792'),'https://weibo.com/u/1938210792');
 assert.equal(social.sourceURL('weibo-account','https://weibo.com/1938210792'),'https://weibo.com/u/1938210792');
 assert.equal(new URL(social.sourceURL('weibo-topic','腕表')).searchParams.get('q'),'#腕表#');
 assert.throws(()=>social.sourceURL('weibo-account','https://example.com/1938210792'));
 assert.throws(()=>social.sourceURL('weibo-topic','#'));
});
test('Weibo topic types search then clicks only pending posts and returns to list',async()=>{
 const social=env(),events=[],url='https://s.weibo.com/weibo?q=%23腕表%23';
 const client={contextId:'list',readPage:async o=>{events.push(['open',o.url]);return {outcome:'success'};},handlePageAccess:async()=>({classification:'ready'}),submitSocialSearch:async q=>events.push(['search',q]),pageState:async()=>({url}),extractWeiboPosts:async()=>({items:Array.from({length:12},(_,i)=>({url:'https://weibo.com/123456/'+i,title:'Post'}))}),clickSocialPost:async u=>{events.push(['click',u]);return {context:'list'};},extractWeiboDetail:async u=>({url:u,title:'Post',text:'Weibo content',platform:'weibo'}),returnFromSocialPost:async()=>events.push(['back'])};
 const result=await social.collectWeibo({source:{id:'s',url},session:{client},api:async(path,__,b)=>path.includes('/post-candidates/')?({candidates:b.candidates,filtered:0}):({candidates:b.candidates.slice(1),skipped:1}),channelId:'c',seenURLs:[],onProgress:()=>{}});
 assert.equal(result.pages.length,2);assert.equal(result.skipped,1);assert.deepEqual(events.map(e=>e[0]),['open','search','click','back','click','back']);assert.equal(events[0][1],'https://s.weibo.com/');assert.equal(events[1][1],'#腕表#');assert(!events.some(e=>e[1]==='https://weibo.com/123456/0'));
});
test('Weibo native post click binds its new tab and closes it on return without URL navigation',async()=>{
 const sdk=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8'),commands=[];
 const e={URL,Set,setTimeout:fn=>fn()};vm.createContext(e);
 vm.runInContext('this.client=new (class {'+sdk.slice(sdk.indexOf('        async clickSocialPost('),sdk.indexOf('        async extractWeiboPosts()'))+'})()',e);
 let clicked=false;
 Object.assign(e.client,{contextId:'list',pageState:async()=>({url:'https://s.weibo.com/weibo?q=watch'}),callJSON:async()=>({ready:true,rect:{x:1,y:1,width:10,height:10}}),naturalPointer:async()=>{clicked=true;},connection:{command:async(method,args)=>{commands.push(method);return {contexts:[{context:'list',url:'https://s.weibo.com/weibo?q=watch'},...(clicked?[{context:'post',url:'https://weibo.com/123456/ABCdef123?refer=search'}]:[])]};}}});
 const origin=await e.client.clickSocialPost('https://weibo.com/123456/ABCdef123');assert.equal(e.client.contextId,'post');await e.client.returnFromSocialPost(origin);assert.equal(e.client.contextId,'list');assert(commands.includes('browsingContext.close'));assert(!commands.includes('browsingContext.navigate'));
});
test('Weibo account stays in its UID scope and never turns an empty feed into an article',async()=>{
 const social=env();let reads=0;
 const client={contextId:'list',readPage:async o=>{assert.equal(o.url,'https://weibo.com/u/1938210792');return {outcome:'success'};},handlePageAccess:async()=>({classification:'ready'}),pageState:async()=>({url:'https://weibo.com/u/1938210792'}),extractWeiboPosts:async()=>{reads++;return {items:[]};},scroll:async()=>{}};
 const result=await social.collectWeibo({source:{id:'s',url:'https://weibo.com/u/1938210792'},session:{client},api:async()=>assert.fail('empty feed must not be committed'),channelId:'c',seenURLs:[],onProgress:()=>{}});
 assert.equal(result.status,'failed');assert.equal(result.pages.length,0);assert.equal(reads,3);
});
test('Weibo stops before clicking search when typed input differs',async()=>{
 const sdk=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');const e={URL,setTimeout:fn=>fn()};vm.createContext(e);
 vm.runInContext('this.client={'+sdk.slice(sdk.indexOf('        async submitSocialSearch('),sdk.indexOf('        async clickSocialPost('))+'}',e);
 let calls=0,clicks=0;Object.assign(e.client,{callJSON:async()=>++calls===1?{rect:{}}:'wrong',naturalPointer:async()=>clicks++,typeText:async()=>{}});
 await assert.rejects(e.client.submitSocialSearch('#腕表#'),/输入与目标话题不一致/);assert.equal(clicks,1);
});
