const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const visibility=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8');
const script=fs.readFileSync(__dirname+'/../browser/search.py','utf8').split("SITE_SEARCH_RESULTS_SCRIPT = r'''")[1].split("'''")[0];
function read(provider,entries=[],text='',path='/search',query=''){
 const hosts={wikipedia:'zh.wikipedia.org',x:'x.com',weibo:'s.weibo.com',xiaohongshu:'www.xiaohongshu.com',youtube:'www.youtube.com',bilibili:'search.bilibili.com'};
 const links=entries.map(([title,href,hidden=false])=>({parentElement:hidden?{getAttribute:k=>k==='aria-hidden'?'true':null}:null,href,innerText:title,textContent:title,getBoundingClientRect:()=>({width:10,height:10}),closest:s=>s.includes('header')?null:{querySelector:selector=>['.searchresult','[data-testid="tweetText"]','.txt','.title','#description-text','.bili-video-card__info--tit,.title'].includes(selector)?{innerText:title}:null}}));
 return vm.runInNewContext(`${visibility};(${script})`,{URL,decodeURIComponent,location:{hostname:hosts[provider],pathname:path,href:`https://${hosts[provider]}${path}`},document:{title:'Search',body:{innerText:text},querySelectorAll:s=>s.includes('dialog')?[]:links},getComputedStyle:()=>({display:'block',visibility:'visible'})})(provider,10,query);
}
test('site readers restrict result URLs to real articles or posts',()=>{
 for(const [source,url,bad] of [['wikipedia','https://zh.wikipedia.org/wiki/机械腕表','https://zh.wikipedia.org/wiki/Special%3ASearch'],['x','https://x.com/user/status/123','https://x.com/user'],['weibo','https://weibo.com/123/Abcd','https://weibo.com/123'],['xiaohongshu','https://www.xiaohongshu.com/explore/abc?xsec_token=keep','https://www.xiaohongshu.com/user/profile/abc']]){
 const output=read(source,[['Found',url],['Not article',bad],['Untrusted','https://other.org/article']]);assert.equal(output.items.length,1);assert.equal(output.items[0].url,new URL(url).href);
 }
});
test('empty, sign-in and verification are distinguishable from markup failure',()=>{
 assert.equal(read('x',[],'','/i/flow/login').classification,'needs_user');assert.equal(read('weibo',[],'安全验证').reason,'captcha');assert.equal(read('wikipedia',[],'There were no results').empty,true);assert.equal(read('xiaohongshu',[]).reason,'search_page_not_loaded');
});

test('X excludes unrelated timeline suggestions on a search URL',()=>{
 const output=read('x',[['Other topic','https://x.com/a/status/123'],['机械腕表新品','https://x.com/b/status/124']],'','/search','机械腕表');
 assert.equal(output.items.length,1);assert.equal(output.items[0].title,'机械腕表新品');
});

test('video readers retain distinct video identities and only observed metadata',()=>{
 const youtube=read('youtube',[['Video A','https://www.youtube.com/watch?v=aaa'],['Video B','https://www.youtube.com/watch?v=bbb'],['Channel','https://www.youtube.com/@name']]);
 assert.equal(youtube.items.length,2);assert.equal(youtube.items[0].kind,'video');assert.equal(youtube.items[0].like_count,null);
 const bili=read('bilibili',[['Video','https://www.bilibili.com/video/BVabc123/'],['Profile','https://space.bilibili.com/123']]);assert.equal(bili.items.length,1);assert.equal(bili.items[0].kind,'video');
});
test('rich post extraction retains full observed body and engagement',()=>{
 const card={querySelector:s=>s==='[data-testid="tweetText"]'?{innerText:'A detailed watch review'}:s.includes('like')?{innerText:'123'}:s.includes('retweet')?{innerText:'12'}:null,querySelectorAll:()=>[]};
 const a={href:'https://x.com/user/status/123',innerText:'timestamp',getBoundingClientRect:()=>({width:10,height:10}),closest:s=>s.includes('header')?null:card};
 const output=vm.runInNewContext(`${visibility};(${script})`,{URL,decodeURIComponent,location:{hostname:'x.com',pathname:'/search',href:'https://x.com/search'},document:{title:'Search',body:{innerText:''},querySelectorAll:s=>s.includes('dialog')?[]:[a]},getComputedStyle:()=>({display:'block',visibility:'visible'})})('x',10,'watch');
 assert.equal(output.items[0].content,'A detailed watch review');assert.equal(output.items[0].like_count,'123');assert.equal(output.items[0].repost_count,'12');assert.equal(output.items[0].comment_count,null);assert.equal(output.items[0].duration,null);
});

test('Bilibili thumbnail counters never replace the observed video title',()=>{
 const card={querySelector:s=>s==='.bili-video-card__info--tit,.title'?{innerText:'机械腕表指南'}:s==='img'?{src:'https://i.example.org/preview.jpg'}:s.includes('duration')?{innerText:'12:34'}:null,querySelectorAll:()=>[]};
 const a={href:'https://www.bilibili.com/video/BV123abc/',innerText:'288 0 12:34',getBoundingClientRect:()=>({width:10,height:10}),closest:s=>s.includes('header')?null:card};
 const result=vm.runInNewContext(`${visibility};(${script})`,{URL,decodeURIComponent,location:{hostname:'search.bilibili.com',pathname:'/all',href:'https://search.bilibili.com/all'},document:{title:'Search',body:{innerText:''},querySelectorAll:s=>s.includes('dialog')?[]:[a]},getComputedStyle:()=>({display:'block',visibility:'visible'})})('bilibili',10,'机械腕表');
 assert.equal(result.items[0].title,'机械腕表指南');assert.equal(result.items[0].image_url,'https://i.example.org/preview.jpg');assert.equal(result.items[0].duration,'12:34');assert.equal(result.items[0].like_count,null);
});
test('X multiword queries match independent terms, not contiguous phrases',()=>{
 const result=read('x',[['model : NVIDIA Nemotron ASR streaming','https://x.com/a/status/123']],'','/search','ASR Model');assert.equal(result.items.length,1);
 assert.equal(read('x',[['ASR Model','https://x.com/a/status/123']],'','/home','ASR Model').items.length,0);
 assert.equal(read('x',[],'Something went wrong. Try reloading.').reason,'provider_unavailable');
});

test('Xiaohongshu empty search login placeholder requests assistance rather than markup failure',()=>{
 const input={getBoundingClientRect:()=>({width:300,height:40}),getAttribute:k=>k==='placeholder'?'登录探索更多内容':null};
 const result=vm.runInNewContext(`${visibility};(${script})`,{URL,decodeURIComponent,location:{hostname:'www.xiaohongshu.com',pathname:'/search_result',href:'https://www.xiaohongshu.com/search_result?keyword=watch'},document:{title:'搜索',body:{innerText:'全部 图文 视频'},querySelectorAll:s=>s==='input[placeholder]'?[input]:[]},getComputedStyle:()=>({display:'block',visibility:'visible'})})('xiaohongshu',10,'watch');
 assert.equal(result.classification,'needs_user');assert.equal(result.reason,'authentication');assert.equal(result.assistance_kind,'authentication');
});

test('Xiaohongshu detail targets retain refreshed observed links for the same note',()=>{
 const targetScript=fs.readFileSync(__dirname+'/../browser/search.py','utf8').split("XHS_NOTE_TARGET_SCRIPT = r'''")[1].split("'''")[0];
 const observed='https://www.xiaohongshu.com/search_result/abc?xsec_token=new';
 const anchor={href:observed,scrollIntoView:()=>{},getBoundingClientRect:()=>({width:10,height:10,toJSON:()=>({width:10,height:10})})};
 const target=vm.runInNewContext(`${visibility};(${targetScript})`,{URL,getComputedStyle:()=>({display:'block',visibility:'visible'}),document:{querySelectorAll:()=>[{...anchor,getBoundingClientRect:()=>({width:0,height:0})},anchor]}});
 assert.equal(target('https://www.xiaohongshu.com/search_result/abc?xsec_token=old').url,observed);
 assert.equal(target('https://www.xiaohongshu.com/search_result/def'),null);
 assert.equal(target('https://other.example/search_result/abc'),null);
});

for(const [provider,url] of [['wikipedia','https://zh.wikipedia.org/wiki/Test'],['x','https://x.com/user/status/123'],['weibo','https://weibo.com/123/Abcd'],['xiaohongshu','https://www.xiaohongshu.com/explore/abc'],['youtube','https://www.youtube.com/watch?v=test'],['bilibili','https://www.bilibili.com/video/BV123456/']])test(provider+' ignores hidden duplicate results before deduplication',()=>{const r=read(provider,[['Hidden',url,true],['Visible',url]]);assert.equal(r.items.length,1);assert.equal(r.items[0].title,'Visible');});
