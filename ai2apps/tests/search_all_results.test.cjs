const test=require('node:test'),assert=require('node:assert/strict');
require('../web/static/builtin_mini_apps/search-all/web/merge.js');
const {merge,canonical}=global.SearchAllResults;
test('merge removes tracking for comparison and retains each original origin URL',()=>{
 const a='https://example.org/a?utm_source=google',b='https://example.org/a#part';
 const result=merge([{source:'google',provider:'bing',items:[{title:'Article',url:a}]},{source:'wikipedia',items:[{title:'Article',url:b}]}]);
 assert.equal(result.length,1);assert.equal(result[0].url,a);assert.deepEqual(result[0].sources,[{source:'google',provider:'bing',url:a},{source:'wikipedia',provider:'wikipedia',url:b}]);
});
test('independent Google and Bing results deduplicate while retaining both sources',()=>{
 const result=merge([{source:'google',provider:'google',items:[{title:'Article',url:'https://example.org/a?utm_source=google'}]},{source:'bing',provider:'bing',items:[{title:'Article',url:'https://example.org/a'}]}]);
 assert.equal(result.length,1);
 assert.deepEqual(result[0].sources.map(s=>[s.source,s.provider]),[['google','google'],['bing','bing']]);
});
test('round robin retains same-title different pages and rejects dangerous links',()=>{
 const result=merge([{source:'google',items:[{title:'Same',url:'https://e.org/1'},{title:'Same',url:'https://e.org/2'},{title:'bad',url:'javascript:alert(1)'}]},{source:'x',items:[{title:'Other',url:'https://x.com/a/status/123'}]}]);
 assert.deepEqual(result.map(i=>i.url),['https://e.org/1','https://x.com/a/status/123','https://e.org/2']);
 assert.equal(canonical('https://user:password@example.org'),null);
});
test('social identity links deduplicate across share parameters without destroying access tokens',()=>{
 const token='https://www.xiaohongshu.com/explore/ABC123?xsec_token=private&xsec_source=pc_search';
 const result=merge([{source:'xiaohongshu',items:[{title:'Note',url:token},{title:'Note',url:'https://www.xiaohongshu.com/search_result/ABC123?xsec_token=other'}]}]);
 assert.equal(result.length,1);assert.equal(result[0].url,token);
 assert.equal(canonical('https://twitter.com/a/status/123'),canonical('https://x.com/b/status/123'));
});
test('video identities merge across engines and retain video metadata',()=>{
 const result=merge([{source:'google',items:[{title:'Watch video',url:'https://youtu.be/abc'}]},{source:'youtube',items:[{kind:'video',title:'Watch video',url:'https://www.youtube.com/watch?v=abc&feature=search',duration:'12:34',image_url:'https://i.ytimg.com/vi/abc/hqdefault.jpg',view_count:'1000'}]}]);
 assert.equal(result.length,1);assert.equal(result[0].kind,'video');assert.equal(result[0].duration,'12:34');assert.equal(result[0].sources.length,2);assert.equal(result[0].view_count,'1000');
});
