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

async function todoChatHarness(){
 const source=fs.readFileSync('web/static/js/todo.js','utf8');let options;
 const elements={'#search':{value:''},'#filter':{value:'all',options:[{value:'all'},{value:'open'}]},'#todo-chat':{}};
 const sandbox={window:{AI2AppsAppChat:{create:async c=>{options=c;return {url:()=>'/chat',bind(){}};}}},$:s=>elements[s]||{},
 state:{tasks:[{id:'selected',directory_id:'dir',title:'Selected',revision:2},{id:'other',directory_id:'elsewhere'}]},
 directoryId:'dir',selectedId:'selected',aggregateId:null,chatController:null,zh:true,tr:x=>x,dirty:false,
 isActiveTask:()=>true,current:()=>sandbox.state.tasks.find(t=>t.id===sandbox.selectedId),refresh:async()=>{},notice:()=>{},setColumn(){},renderTree(){},renderDirectory(){},renderDetail(){},collapsed:new Set(),lastTaskFilter:'all'};
 vm.runInNewContext(source.slice(source.indexOf('async function setupChat()'),source.indexOf('\nlocalize();icons();'))+'\nwindow.ready=setupChat();',sandbox);
 await sandbox.window.ready;return {options,sandbox,elements};
}
test('Todo uses durable owner transport and fixes directory scope',async()=>{
 const {options,sandbox}=await todoChatHarness();assert.equal(options.registration,'ai2apps.todo.chat');assert.equal(options.scope().directory_id,'dir');
 sandbox.directoryId='elsewhere';assert.equal(options.scope().directory_id,'dir');
 await assert.rejects(options.applyUI({action:'select_project',task_id:'other'}),/changed/);
});
test('Todo UI actions preserve business data and reject dirty or foreign context',async()=>{
 const {options,sandbox,elements}=await todoChatHarness();
 await options.applyUI({action:'set_search',query:'Requested'});assert.equal(elements['#search'].value,'Requested');
 await assert.rejects(options.applyUI({action:'select_project',task_id:'other'}),/outside/);
 sandbox.dirty=true;await assert.rejects(options.applyUI({action:'set_search',query:'overwrite'}),/unsaved/);
 assert.equal(elements['#search'].value,'Requested');
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
