const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('Package UI bridge reads declared fields, validates before mutation and cannot run work',async()=>{
 const fields={prompt:{value:'before',type:'text',tagName:'TEXTAREA',dispatchEvent(){}},model:{value:'one',type:'select-one',tagName:'SELECT',options:[{value:'one',textContent:'One'},{value:'two',textContent:'Two'}],dispatchEvent(){}}};
 let listener;const window={addEventListener:(n,fn)=>listener=fn,removeEventListener(){}};
 const context={window,document:{getElementById:id=>fields[id]},parent:{},location:{origin:'http://local'},Event:class{},TextEncoder};
 vm.runInNewContext(fs.readFileSync('web/static/js/package_mini_chat.js','utf8'),context);
 const bridge=window.AI2AppsPackageChat.install({miniAppId:'arbitrary.mini',fields:{prompt:{type:'string',maxLength:20},model:{type:'string'}}});
 assert.equal((await bridge.context()).values.prompt,'before');
 await assert.rejects(bridge.invoke('run_current',{}),/cannot execute/);
 await assert.rejects(bridge.invoke('update_current_draft',{prompt:'changed',model:'unknown'}),/Unavailable/);
 assert.equal(fields.prompt.value,'before');
 await bridge.invoke('update_current_draft',{prompt:'changed'});assert.equal(fields.prompt.value,'changed');
 fields.prompt.disabled=true;await assert.rejects(bridge.invoke('update_current_draft',{prompt:'again'}),/busy/);
 let replies=[];context.parent.postMessage=x=>replies.push(x);
 await listener({source:context.parent,origin:'http://evil',data:{type:'ai2apps.mini-app-chat.provider-request',id:'i',channel:'c',method:'context'}});assert.equal(replies.length,0);
});

test('Package context request retries through slow startup; UI invocation never retries',async()=>{
 let listener,posts=[],intervals=new Map(),serial=0;
 const window={addEventListener:(n,fn)=>{if(n==='message')listener=fn;},removeEventListener(){},location:{origin:'https://fixture.test'}};
 const target={postMessage:m=>posts.push(m)};
 const ctx={window,console,crypto:{randomUUID:()=> 'fixture-channel'},setTimeout,clearTimeout,setInterval:fn=>{intervals.set(++serial,fn);return serial;},clearInterval:id=>intervals.delete(id),TextEncoder,URL,URLSearchParams};
 vm.runInNewContext(fs.readFileSync('web/static/js/mini_app_chat.js','utf8'),ctx);
 const bridge=window.AI2AppsMiniAppChat.createPackageBridge(()=>({contentWindow:target}),{system_prompt:'fixture',help:{resource:'help.md'},tools:[]});
 const read=bridge.describe({id:'arbitrary.mini'});assert.equal(posts.length,1);
 intervals.values().next().value();assert.equal(posts.length,2);assert.equal(posts[0].id,posts[1].id);
 listener({source:target,origin:'https://fixture.test',data:{type:'ai2apps.mini-app-chat.provider-response',channel:'fixture-channel',id:posts[0].id,ok:true,result:{prompt:'ready'}}});
 assert.equal((await read).context.prompt,'ready');assert.equal(intervals.size,0);
 const write=bridge.invoke('update_current_draft',{prompt:'new'});assert.equal(intervals.size,0);
 const m=posts.at(-1);listener({source:target,origin:'https://fixture.test',data:{type:'ai2apps.mini-app-chat.provider-response',channel:'fixture-channel',id:m.id,ok:true,result:{updated:true}}});
 assert.equal((await write).updated,true);bridge.dispose();
});
