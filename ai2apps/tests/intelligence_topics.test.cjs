const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/intelligence.js','utf8');
test('hot topic lists only its linked channel articles and escapes model text',()=>{
 const root={},articles=[{id:'a',title:'Model X release',updated_at:'2026-10-07'},{id:'b',title:'Model X review',updated_at:'2026-10-06'},{id:'c',title:'unrelated',updated_at:'2026-10-05'}];
 const env={channel:()=>({id:'c',hot_topics:{generated_at:'2026-10-07',article_count:3,items:[{title:'<Model X>',summary:'<summary>',article_ids:['a','b'],updated_at:'2026-10-07'}]}}),
 inChannel:()=>articles,when:s=>s,esc:s=>String(s).replaceAll('<','&lt;'),coverHTML:()=>'',empty:()=>'',channelId:'c'};
 Object.assign(env,require('./intelligence_test_env.cjs'));vm.createContext(env);vm.runInContext(source.slice(source.indexOf('const topicRequests='),source.indexOf('function renderContent()')),env);
 env.renderTopics(root);
 assert.match(root.innerHTML,/&lt;Model X>/);
 assert.match(root.innerHTML,/data-article="a"/);
 assert.match(root.innerHTML,/data-article="b"/);
 assert.doesNotMatch(root.innerHTML,/unrelated/);
});
