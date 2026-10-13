const test=require('node:test'),assert=require('node:assert/strict');
require('../../packages/ai2apps-search-all/web/presentation.js');
const {reviewInput,applyReview,groups,imageURL}=global.SearchAllPresentation;
const items=[{kind:'web',title:'Original',url:'https://example.org/a',summary:'Snippet',sources:[{source:'google'}]},{kind:'post',title:'Post',content:'Full post',url:'https://x.com/a/status/1',like_count:'10',sources:[{source:'x'}]}];
test('AI ordering and translation retain observed links, sources and post metrics',()=>{
 const result=applyReview(items,{items:[{id:'r1',title:'Invented post',summary:'Invented body',reason:'Relevant'},{id:'r0',title:'Translated',summary:'Translated snippet',reason:'Original source'}]});
 assert.equal(result[0].title,'Post');assert.equal(result[0].content,'Full post');assert.equal(result[0].like_count,'10');assert.equal(result[1].title,'Translated');assert.equal(result[1].url,items[0].url);assert.deepEqual(result[1].sources,items[0].sources);
});
test('AI omissions, duplicates and unknown identities are rejected without losing originals',()=>{
 for(const ids of [['r0'],['r0','r0'],['r0','new']])assert.throws(()=>applyReview(items,{items:ids.map(id=>({id,title:'Title',summary:'Summary',reason:'Reason'}))}));assert.equal(items[0].title,'Original');
});
test('review evidence is bounded; groups preserve model ordering within category',()=>{
 const input=reviewInput([{...items[0],summary:'x'.repeat(10000)}]);assert.equal(input[0].summary.length,500);assert.equal(input[0].id,'r0');
 const output=groups([...items,...items,{kind:'video'}]);assert.deepEqual(output.map(g=>g.kind),['web','post','video']);assert.equal(output[0].items.length,2);
});
test('thumbnail URLs reject credentials and non-HTTPS schemes',()=>{assert.equal(imageURL('javascript:alert(1)'),null);assert.equal(imageURL('https://secret@e.org/a'),null);assert.equal(imageURL('http://e.org/a'),null);assert.equal(imageURL('https://e.org/a'),'https://e.org/a');});
test('missing snippets cannot become invented article facts from AI',()=>{
 const original={kind:'web',title:'Article',url:'https://e.org',summary:'',sources:[]};
 const result=applyReview([original],{items:[{id:'r0',title:'翻译标题',summary:'Invented facts',reason:'Relevant'}]});assert.equal(result[0].summary,'翻译标题');
});
test('ad filtering preserves identity validation and keeps all results when disabled',()=>{
 const review={items:items.map((_,i)=>({id:'r'+i,title:'Title',summary:'Summary',reason:'Reason',is_ad:i===0}))};
 assert.equal(applyReview(items,review,true).length,1);assert.equal(applyReview(items,review,false).length,2);
 assert.throws(()=>applyReview(items,{items:review.items.map(({is_ad,...row})=>row)},true));
});
require('../../packages/ai2apps-search-all/web/diagnostics.js');
test('failure reasons provide actionable bilingual guidance',()=>{
 assert.match(global.SearchAllDiagnostics.explain('authentication',true),/Sign in/);
 assert.match(global.SearchAllDiagnostics.explain('provider_unavailable',false),/稍后重试/);
 assert.match(global.SearchAllDiagnostics.explain('unknown',false),/运行记录/);
});
test('post translations preserve original body and observed metrics',()=>{
 const result=applyReview([items[1]],{items:[{id:'r0',title:'Post',summary:'',reason:'有用',source_language:'en',translated:true,translated_content:'完整帖子译文'}]});
 assert.equal(result[0].content,'Full post');assert.equal(result[0].translated_content,'完整帖子译文');assert.equal(result[0].translated,true);assert.equal(result[0].like_count,'10');
 assert.throws(()=>applyReview([items[1]],{items:[{id:'r0',title:'Post',summary:'',reason:'',source_language:'en',translated:true,translated_content:''}]}));
});

test('preview DataURLs allow bounded raster images and reject executable or oversized payloads',()=>{
 assert.equal(imageURL('data:image/jpeg;base64,/9j/AAAA'),'data:image/jpeg;base64,/9j/AAAA');
 assert.equal(imageURL('data:image/svg+xml;base64,PHN2Zz4='),null);
 assert.equal(imageURL('data:text/html;base64,AAAA'),null);
 assert.equal(imageURL('data:image/jpeg;base64,'+'A'.repeat(400001)),null);
 const source={kind:'post',title:'Note',url:'https://www.xiaohongshu.com/explore/abc',content:'Body',image_data_url:'data:image/jpeg;base64,/9j/AAAA'};
 assert.equal(applyReview([source],{items:[{id:'r0',title:'Note',summary:'Body',reason:'Useful'}]})[0].image_data_url,source.image_data_url);
});
