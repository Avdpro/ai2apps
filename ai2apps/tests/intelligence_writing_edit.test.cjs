const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/intelligence.js','utf8');
function setup(){
 const nodes=new Map(),calls=[];let id=0;
 const env={writingSession:{draft:{id:'d',revision:1,current:{title:'Old',content:'Old body'}},channelId:'c',pending:false},crypto:{randomUUID:()=>`request-${++id}`},lt:s=>s,confirm:()=>false,renderWriting:()=>{},loadDrafts:async()=>{},$:selector=>{if(!nodes.has(selector))nodes.set(selector,{value:'',textContent:'',focus(){},addEventListener(){}});return nodes.get(selector);},api:async(path,method,body)=>{calls.push(body);if(env.fail)throw Error('Conflict');return {...env.writingSession.draft,revision:body.revision+1,current:{title:body.title,content:body.content}};}};
 vm.createContext(env);vm.runInContext(source.slice(source.indexOf('function writingEditDirty('),source.indexOf("$('#writing-guidance').oninput=")),env);
 env.$('#writing-edit').onclick();return {env,calls};
}
test('manual edit saves exact user text and returns to reading',async()=>{
 const {env,calls}=setup();env.$('#writing-edit-title').value='My title';env.$('#writing-edit-content').value='My text\n\n[1]';
 assert.equal(env.writingEditDirty(),true);assert.equal(env.discardWritingEdit(),false);
 await env.$('#writing-text-form').onsubmit({preventDefault(){}});
 assert.equal(calls[0].content,'My text\n\n[1]');assert.equal(env.writingSession.editing,false);assert.equal(env.writingSession.draft.revision,2);
});
test('failed manual save retains input and retry identity; cancel requires consent',async()=>{
 const {env,calls}=setup();env.$('#writing-edit-content').value='Keep my writing';env.fail=true;
 await env.$('#writing-text-form').onsubmit({preventDefault(){}});
 assert.equal(env.$('#writing-edit-content').value,'Keep my writing');assert.equal(env.writingSession.editing,true);assert.equal(env.writingSession.pending,false);
 env.fail=false;await env.$('#writing-text-form').onsubmit({preventDefault(){}});assert.equal(calls[0].request_id,calls[1].request_id);
 env.$('#writing-edit').onclick();env.$('#writing-edit-content').value='Unsaved';env.confirm=()=>true;assert.equal(env.discardWritingEdit(),true);
 assert.equal(env.writingSession.draft.current.content,'Keep my writing');
});
