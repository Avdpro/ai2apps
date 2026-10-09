const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const helpers=source.slice(source.indexOf('    function windowObservationSignature('),source.indexOf('    async function startExploration('));
test('assistance monitor returns changed window evidence to AI without inferring authentication',async()=>{
 const callbacks=[], calls=[];
 const exploration={goal:'发布微博',status:'needs_user',attachments:['asset'],attempts:[{outcome:'success'}]};
 let page={fingerprint:'before',url:'https://weibo.com/home',control_count:2,controls:[{name:'发布'}]};
 const context={state:{exploration,busy:false},URL,Date,clearTimeout(){},setTimeout(fn){callbacks.push(fn);return callbacks.length;},
  client:async()=>({explorationObservation:async()=>page,relatedWindowObservations:async()=>[]}),withBusy:async fn=>fn(),startExploration:async(...args)=>calls.push(args)};
 vm.runInNewContext(helpers+'\nglobalThis.watch=watchLoginAssistance;',context);
 context.watch({fingerprint:'before',url:'https://weibo.com/newlogin',controls:[{name:'扫码登录'}]},'请扫码登录');
 page={...page,url:'https://other.example/home'};await callbacks.shift()();assert.equal(calls.length,0);
 page={...page,url:'https://weibo.com/home',controls:[{type:'password',name:'密码'}]};await callbacks.shift()();assert.equal(calls.length,0);
 page={...page,fingerprint:'changed',controls:[{name:'发布'}]};await callbacks.shift()();assert.deepEqual(calls,[['发布微博',true]]);
 assert.equal(context.state.exploration,exploration);assert.equal(exploration.attachments[0],'asset');
});
test('cancelled assistance cannot resume',async()=>{
 const callbacks=[],exploration={status:'needs_user',cancelled:true};
 const context={state:{exploration},URL,Date,clearTimeout(){},setTimeout(fn){callbacks.push(fn);},client:async()=>{throw Error('must not inspect');}};
 vm.runInNewContext(helpers+'\nglobalThis.watch=watchLoginAssistance;',context);
 context.watch({url:'https://weibo.com/',controls:[{name:'登录'}]},'登录');await callbacks[0]();
});
