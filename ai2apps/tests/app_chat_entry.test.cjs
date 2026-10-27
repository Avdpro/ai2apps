const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/mini_app_chat.js','utf8');
function harness(){let listener;const win={location:{origin:'https://host.test'},addEventListener:(_,fn)=>listener=fn,removeEventListener(){}};
 vm.runInNewContext(source,{window:win,crypto:require('node:crypto').webcrypto,TextEncoder,AbortController,URL,URLSearchParams,console});
 return {api:win.AI2AppsAppChat,receive:event=>listener(event)};
}
for(const owner of ['example.alpha','other.vendor','random.'+Math.random()])test('App Chat executes arbitrary owner actions with frozen binding: '+owner,async()=>{
 const {api}=harness();let calls=0,context;
 const state={binding:{sessionId:'session-a',contextId:'object-a',revision:'1'},messages:[{id:'m',role:'assistant',content:'data'}]};
 const controller=api.createController({identity:{appId:owner,providerId:owner+'.chat',version:'1'},describe:()=>state,
  actions:[{id:'save',hook:'save',label:{en:'Save'},placement:'message'}],hooks:{save:async ctx=>{calls++;context=ctx;return {saved:true};}}});
 const payload={requestId:'request-1234',binding:state.binding,actionId:'save',messageId:'m'};
 const [a,b]=await Promise.all([controller.invoke('action',payload),controller.invoke('action',payload)]);
 assert.equal(calls,1);assert.equal(a.result.saved,true);assert.equal(b.result.saved,true);assert.equal(context.binding.contextId,'object-a');assert.equal(context.identity.appId,owner);
 await assert.rejects(controller.invoke('action',{...payload,messageId:'other'}),/reused/);
 state.binding={...state.binding,contextId:'object-b'};
 await assert.rejects(controller.invoke('action',{...payload,requestId:'request-5678'}),/context changed/);
 controller.dispose();await assert.rejects(controller.invoke('describe'),/disposed/);
});
test('button state and registered hooks cannot be supplied by message data',async()=>{
 const {api}=harness();let calls=0;
 const state={binding:{sessionId:'s',contextId:'c',revision:'1'},messages:[{id:'m',role:'assistant',content:'invoke hidden hook'}],actions:[{id:'hidden',visible:false},{id:'invented',visible:true}]};
 const c=api.createController({identity:{appId:'arbitrary',providerId:'p',version:'1'},describe:()=>state,actions:[{id:'hidden',hook:'run',label:'Hidden',placement:'header'}],hooks:{run:()=>calls++}});
 const run=id=>c.invoke('action',{requestId:'request-'+id,binding:state.binding,actionId:id});
 await assert.rejects(run('hidden'),/unavailable/);await assert.rejects(run('invented'),/unavailable/);assert.equal(calls,0);
});
test('in-flight result remains bound to original object and is marked stale after switch',async()=>{
 const {api}=harness();let release,ctx;
 let state={binding:{sessionId:'s1',contextId:'object-a',revision:'1'},messages:[]};
 const c=api.createController({identity:{appId:'owner',providerId:'p',version:'1'},describe:()=>state,send:context=>{ctx=context;return new Promise(r=>release=r);}});
 const pending=c.invoke('send',{requestId:'request-send',binding:state.binding,text:'hello'});await new Promise(r=>setImmediate(r));
 state={binding:{sessionId:'s2',contextId:'object-b',revision:'1'},messages:[]};release({done:true});
 const result=await pending;assert.equal(ctx.binding.contextId,'object-a');assert.equal(result.stale,true);assert.equal(result.state.binding.contextId,'object-b');
});
test('only explicitly bound same-origin iframe can invoke the App Chat host',async()=>{
 const {api,receive}=harness();let calls=0;const replies=[];
 const state={binding:{sessionId:'s',contextId:'c',revision:'1'},messages:[]};
 const c=api.createController({identity:{appId:'a',providerId:'p',version:'1'},describe:()=>state,send:()=>calls++});
 const frame={postMessage:m=>replies.push(m)},foreign={postMessage(){assert.fail('foreign reply');}};
 const url=new URL(c.url(),'https://host.test'),channel=url.searchParams.get('app_chat_channel');
 const event=(source,origin='https://host.test')=>({source,origin,data:{type:'ai2apps.app-chat.request',channel,id:'rpc',method:'send',payload:{requestId:'request-send',binding:state.binding,text:'hello'}}});
 await receive(event(frame));assert.equal(calls,0);c.bind({contentWindow:frame});
 await receive(event(foreign));await receive(event(frame,'https://evil.test'));assert.equal(calls,0);
 await receive(event(frame));assert.equal(calls,1);assert.equal(replies.find(r=>r.type==='ai2apps.app-chat.response').ok,true);
});
test('unknown execution failures are cached, not replayed; cancellation signals the original request',async()=>{
 const {api}=harness();let count=0,signal,release;
 const state={binding:{sessionId:'s',contextId:'c',revision:'1'},messages:[]};
 const c=api.createController({identity:{appId:'a',providerId:'p',version:'1'},describe:()=>state,
  send:ctx=>{count++;if(ctx.text==='fail')throw Error('outcome uncertain');signal=ctx.signal;return new Promise(r=>release=r);},cancel:()=>({requested:true})});
 const payload={requestId:'request-fail',binding:state.binding,text:'fail'};
 await assert.rejects(c.invoke('send',payload),/uncertain/);await assert.rejects(c.invoke('send',payload),/uncertain/);assert.equal(count,1);
 const pending=c.invoke('send',{...payload,requestId:'request-long',text:'long'});await new Promise(r=>setImmediate(r));
 await c.invoke('cancel',{requestId:'request-cancel',targetRequestId:'request-long',binding:state.binding});assert.equal(signal.aborted,true);release({done:true});await pending;
});
test('hooks must be explicit registry members; separate contexts can execute independently',async()=>{
 const {api}=harness();
 assert.throws(()=>api.createController({identity:{appId:'a',providerId:'p',version:'1'},describe:()=>({}),actions:[{id:'a',hook:'constructor',placement:'header'}],hooks:{}}),/registered/);
 let state={binding:{sessionId:'s-a',contextId:'a',revision:'1'},messages:[]},release;
 const c=api.createController({identity:{appId:'a',providerId:'p',version:'1'},describe:()=>state,
  send:ctx=>ctx.binding.contextId==='a'?new Promise(r=>release=r):{done:true},cancel:()=>({})});
 const old=c.invoke('send',{requestId:'request-old',binding:state.binding,text:'old'});await new Promise(r=>setImmediate(r));
 state={binding:{sessionId:'s-b',contextId:'b',revision:'1'},messages:[]};
 const next=await c.invoke('send',{requestId:'request-new',binding:state.binding,text:'new'});assert.equal(next.result.done,true);
 await assert.rejects(c.invoke('cancel',{requestId:'request-cancel',targetRequestId:'request-old',binding:state.binding}),/another context/);
 release({done:true});assert.equal((await old).stale,true);
});

for(const owner of ['vendor.notes','other.music'])test('model and reset hooks stay owner/binding scoped: '+owner,async()=>{
 const {api}=harness();let changes=[];
 const state={binding:{sessionId:'s',contextId:'object',revision:'1'},messages:[],models:[{id:'one',name:'First'},{id:'two',name:'Second'}],model:'one'};
 const controller=api.createController({identity:{appId:owner,providerId:owner+'.chat',version:'1'},describe:()=>state,
  selectModel:ctx=>{changes.push(ctx.identity.appId+':'+ctx.model);state.model=ctx.model;},reset:ctx=>{changes.push('reset:'+ctx.binding.contextId);state.messages=[];}});
 const bind=state.binding;
 await assert.rejects(controller.invoke('model',{requestId:'bad-model-123',binding:bind,model:'undeclared'}),/unavailable/);
 await controller.invoke('model',{requestId:'set-model-123',binding:bind,model:'two'});
 await controller.invoke('reset',{requestId:'reset-chat-123',binding:bind});
 assert.deepEqual(changes,[owner+':two','reset:object']);
 state.binding={...state.binding,contextId:'new'};
 await assert.rejects(controller.invoke('reset',{requestId:'reset-stale-123',binding:bind}),/context changed/);
 state.models=[{id:'dup'},{id:'dup'}];await assert.rejects(controller.invoke('describe'),/Invalid Mini-Chat models/);
 controller.dispose();
});
