const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = {window:{}};
vm.runInNewContext(fs.readFileSync('web/static/js/mini_app_chat.js','utf8'),context);
test('repeated provider tool call IDs remain stable across argument deltas',()=>{
 const calls=new Map(); const merge=context.window.AI2AppsMiniAppChat.mergeToolCallChunks;
 merge(calls,[{index:0,id:'call_123',function:{name:'create_project',arguments:'{"title":'}}]);
 merge(calls,[{index:0,id:'call_123',function:{name:'create_project',arguments:'"Task"}'}}]);
 assert.equal(calls.get(0).id,'call_123');
 assert.equal(calls.get(0).function.name,'create_project');
 assert.deepEqual(JSON.parse(calls.get(0).function.arguments),{title:'Task'});
});
test('parallel streamed calls keep separate arguments',()=>{
 const calls=new Map(),merge=context.window.AI2AppsMiniAppChat.mergeToolCallChunks;
 merge(calls,[{index:0,id:'a',function:{name:'read_project',arguments:'{"id":"a"}'}},{index:1,id:'b',function:{name:'read_project',arguments:'{"id":"b"}'}}]);
 assert.equal(calls.size,2);assert.equal(calls.get(1).id,'b');
});
test('host context lifecycle is bound to the registered frame and channel',async()=>{
 let handler,selected='project-a',snapshot=null;
 const win={location:{origin:'http://localhost'},addEventListener:(_,cb)=>handler=cb,removeEventListener(){}};
 const sandbox={window:win,URLSearchParams};vm.runInNewContext(fs.readFileSync('web/static/js/mini_app_chat.js','utf8'),sandbox);
 const controller=win.AI2AppsMiniAppChat.createStudioController({begin:()=>snapshot=selected,end:()=>snapshot=null});
 const replies=[],frame={postMessage:m=>replies.push(m)};controller.bind({contentWindow:frame});
 const channel=new URLSearchParams(controller.url().split('#')[1]).get('mini_app_chat_channel');
 const send=(method,source=frame)=>handler({origin:'http://localhost',source,data:{type:'ai2apps.mini-app-chat.request',channel,id:method,method}});
 await send('begin',{});assert.equal(snapshot,null);
 await send('begin');selected='project-b';assert.equal(snapshot,'project-a');
 await send('end');assert.equal(snapshot,null);assert.equal(replies.length,2);
});

function todoChatHarness(){
 const source=fs.readFileSync('web/static/js/todo.js','utf8');
 let controller,write;
 const tasks=[{id:'selected',directory_id:'dir',title:'Selected',highlight:'',schedule:{frequency:'off'},revision:2},{id:'green',directory_id:'dir',title:'Green',highlight:'lime',schedule:{frequency:'off'},revision:3},{id:'other',directory_id:'elsewhere',title:'Other',highlight:'lime',schedule:{}}];
 const sandbox={window:{AI2AppsMiniAppChat:{SCHEMA:'test',createStudioController:c=>{controller=c;return {url:()=>'',bind(){}};}}},$:()=>({}),state:{tasks,directories:[{id:'dir'}],runs:[]},directoryId:'dir',selectedId:'selected',aggregateId:null,chatScope:null,zh:true,tr:x=>x,dirty:false,isActiveTask:()=>true,descendants:id=>new Set([id]),matchesAggregate:()=>true,TextEncoder,refresh:async()=>{},taskBody:t=>({...t}),api:async(path,method,body)=>{write={path,method,body};return body;},projectStatuses:['not_started'],priorities:['U','S','A','B','C','D']};
 vm.runInNewContext(source.slice(source.indexOf('function setupChat()'),source.indexOf('\nlocalize();icons();'))+'\nsetupChat();',sandbox);
 return {controller,sandbox,getWrite:()=>write};
}
test('Mini-Chat exposes persistent highlight and directory lookup without expanding default scope',async()=>{
 const {controller}=todoChatHarness();const d=controller.describe();
 assert.equal(d.context.projects.length,1);
 const update=d.tools.find(t=>t.name==='update_project');assert.ok(update.inputSchema.properties.highlight.enum.includes(''));
 const list=await controller.invoke('list_projects',{scope:'directory'});
 assert.equal(list.projects.length,2);assert.equal(list.projects.find(t=>t.id==='green').highlight,'lime');
});
test('directory highlight update preserves task data and does not persist scope',async()=>{
 const {controller,getWrite}=todoChatHarness();
 await assert.rejects(controller.invoke('update_project',{id:'green',highlight:''}),/outside/);
 await controller.invoke('update_project',{id:'green',scope:'directory',highlight:''});
 const write=getWrite();assert.equal(write.body.highlight,'');assert.equal(write.body.title,'Green');assert.equal(write.body.revision,3);assert.equal(write.body.schedule.frequency,'off');assert.equal('scope' in write.body,false);
 await assert.rejects(controller.invoke('update_project',{id:'other',scope:'directory',highlight:''}),/outside/);
});
test('aggregate view cannot expand to a hidden directory',async()=>{
 const {controller,sandbox}=todoChatHarness();sandbox.aggregateId='urgent';
 await assert.rejects(controller.invoke('list_projects',{scope:'directory'}),/source directory/);
});

test('new host channel changes document URL, not only fragment',()=>{
 const win={location:{origin:'http://localhost'},addEventListener(){},removeEventListener(){}};
 let id=0;const sandbox={window:win,URLSearchParams,crypto:{randomUUID:()=>`channel-${++id}`}};
 vm.runInNewContext(fs.readFileSync('web/static/js/mini_app_chat.js','utf8'),sandbox);
 const make=()=>new URL(win.AI2AppsMiniAppChat.createStudioController({}).url(),'http://localhost');
 const first=make(),second=make();
 assert.notEqual(first.search,second.search);
 assert.equal(second.searchParams.get('mini_app_chat_channel'),new URLSearchParams(second.hash.slice(1)).get('mini_app_chat_channel'));
});
test('host follows bound iframe window replacement and rejects stale window',async()=>{
 let handler,count=0;const replies=[];
 const win={location:{origin:'http://localhost'},addEventListener:(_,cb)=>handler=cb,removeEventListener(){}};
 vm.runInNewContext(fs.readFileSync('web/static/js/mini_app_chat.js','utf8'),{window:win,URLSearchParams});
 const controller=win.AI2AppsMiniAppChat.createStudioController({begin:()=>count++});
 const old={postMessage:()=>assert.fail('stale window response')},fresh={postMessage:m=>replies.push(m)};
 const iframe={contentWindow:old};controller.bind(iframe);iframe.contentWindow=fresh;
 const channel=new URLSearchParams(controller.url().split('#')[1]).get('mini_app_chat_channel');
 const send=source=>handler({origin:win.location.origin,source,data:{type:'ai2apps.mini-app-chat.request',channel,id:'1',method:'begin'}});
 await send(old);assert.equal(count,0);await send(fresh);assert.equal(count,1);assert.equal(replies.length,1);
});
