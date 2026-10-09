const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const env={window:{},URL};vm.createContext(env);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/intelligence_cards.js','utf8'),env);const cards=env.window.IntelligenceCards;
const article=(ref,extra={})=>({id:'a',title:'Test <script>',summary:'Summary & text',sources:[ref],...extra});
test('legacy content types use source evidence and explicit type wins',()=>{
 for(const [url,type] of [['https://example.com/news','webpage'],['https://youtube.com/watch?v=abc','video'],['https://weibo.com/123/abc','post'],['https://www.reddit.com/r/watches/comments/a','post'],['https://example.com/threads/123','post'],['https://example.com/report.PDF?download=1','document'],['https://example.com/podcast.mp3','audio'],['https://example.com/album.jpg','image']])assert.equal(cards.typeOf({url}),type);
 assert.equal(cards.typeOf({url:'https://example.com/page',content_type:'audio'}),'audio');
 assert.equal(cards.typeOf({url:'https://youtube.com.attacker.test/page'}),'webpage');
});
test('all six formats render distinct cards and retain article keyboard entry',()=>{
 for(const kind of Object.keys(cards.types)){
  const html=cards.render(article({content_type:kind,url:'https://example.com/',author:'Author'}));
  assert.match(html,new RegExp('intel-story-'+kind));assert.match(html,/data-article="a"/);assert.match(html,/tabindex="0" role="button"/);assert.match(html,/AI 摘要/);assert.doesNotMatch(html,/<script>/);
 }
});
test('post photos deduplicate covers, cap nine, and escape author',()=>{
 const photos=Array.from({length:11},(_,i)=>({url:`https://example.com/${i}.jpg`}));
 const html=cards.render(article({platform:'weibo',author:'<img onerror=alert(1)>',url:'https://weibo.com/123/abc'},{cover_image:photos[0],images:photos}));
 assert.equal((html.match(/<img /g)||[]).length,9);assert.match(html,/\+2/);assert.match(html,/&lt;img onerror/);
});
test('video coverage and unavailable metadata are not invented',()=>{
 const html=cards.render(article({platform:'youtube',coverage:'description',url:'https://youtu.be/a'}));
 assert.match(html,/仅标题与简介/);assert.doesNotMatch(html,/class="intel-duration"/);assert.doesNotMatch(html,/<video|<iframe|<button/);
 const timed=cards.render(article({platform:'youtube',coverage:'transcript',duration_seconds:125,url:'https://youtu.be/a'}));assert.match(timed,/2:05/);assert.match(timed,/已读取网页文字稿/);
});
test('mixed sources use synthesis presentation and remain filterable by each format',()=>{
 const a=article({}, {sources:[{url:'https://youtube.com/watch?v=a'},{url:'https://weibo.com/123/abc'}]});
 const info=cards.describe(a);assert.equal(info.mixed,true);assert(info.formats.includes('video'));assert(info.formats.includes('post'));
 const html=cards.render(a);assert.match(html,/混合来源/);assert.match(html,/AI 综合/);assert.doesNotMatch(html,/intel-post-author|intel-video-cover/);
});
test('unsafe and failed images are excluded',()=>{
 const html=cards.render(article({content_type:'image'}, {images:[{url:'javascript:alert(1)'},{url:'https://example.com/broken.jpg'}]}),{failedImages:new Set(['https://example.com/broken.jpg'])});
 assert.doesNotMatch(html,/<img /);assert.match(html,/尚未提取图片/);
});
test('Weibo avatars are excluded and actual images use authorized article endpoint',()=>{
 const avatar='https://tvax4.sinaimg.cn/crop.0.0/a.jpg?Expires=1',image='https://wx4.sinaimg.cn/orj480/photo.jpg';
 const a=article({platform:'weibo'},{cover_image:{url:avatar},images:[{url:avatar},{url:image}]});
 const html=cards.render(a);assert(!html.includes('tvax4'));assert(html.includes('/articles/a/image?url='));
 assert.equal(cards.imageURL(a,'https://wx4.sinaimg.cn.attacker.test/a.jpg'),'https://wx4.sinaimg.cn.attacker.test/a.jpg');
});
