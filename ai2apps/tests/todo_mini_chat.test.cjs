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
