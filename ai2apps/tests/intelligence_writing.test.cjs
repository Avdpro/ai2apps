const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/intelligence.js','utf8');
test('saved manuscripts list escapes titles and shows scope and revision',()=>{
 const root={},env={channelId:'c',draftLists:new Map([['c',[{id:'d',title:'<draft>',scope_label:'<topic>',kind:'video_script',revision:2,updated_at:'now'}]]]),writingKinds:{video_script:'视频稿'},when:s=>s,esc:s=>String(s).replaceAll('<','&lt;'),empty:()=>''};
 Object.assign(env,require('./intelligence_test_env.cjs'));vm.createContext(env);vm.runInContext(source.slice(source.indexOf('function renderDraftList('),source.indexOf('function startWriting(')),env);
 env.renderDraftList(root);assert.match(root.innerHTML,/&lt;draft>/);assert.match(root.innerHTML,/&lt;topic>/);assert.match(root.innerHTML,/第 2 版/);assert.match(root.innerHTML,/data-draft="d"/);
});
