const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
function fixture({dirty=false,failAck=false,onPrepare=null,appId='arbitrary.app',needsApply=false}={}){
 let state={mode:'compact'},privateDraft='PRIVATE PROMPT',applied=0,busy=false;const requests=[];
 const target={app_id:appId,mini_app_id:null,contract_version:1},schema={type:'object',properties:{mode:{type:'string','x-app-state':'portable'}},required:['mode'],additionalProperties:false};
 const context={TextEncoder,AbortController,setTimeout,clearTimeout,crypto:webcrypto,window:{},document:{documentElement:{lang:'en'}},fetch:async(url,opts={})=>{const body=opts.body?JSON.parse(opts.body):null;requests.push({url,body});let result={};
  if(url.includes('/contract?'))result={...target,schema,contract_digest:'a'.repeat(64)};
  else if(url.endsWith('/validate'))result={packet:body.packet,contract_digest:'a'.repeat(64)};
  else if(url.endsWith('/applications')){onPrepare?.(()=>{privateDraft='CHANGED';});result={id:'application',status:'prepared'};}
  else if(url.endsWith('/complete')){if(failAck)throw Error('lost acknowledgement');result={status:body.status,id:'application'};}
  return {ok:true,json:async()=>result};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/app_state.js','utf8'),context);
 const binding=context.window.AI2AppsAppState.register({target,instanceId:'owned',capture:()=>({...state}),needsApply:()=>needsApply,revision:()=>JSON.stringify({state,privateDraft}),dirty:()=>dirty,validate(v){if(!['compact','full'].includes(v.mode))throw Error('unsupported mode');},apply(v){state={...v};applied++;},setBusy:v=>busy=v});
 return {binding,target,requests,packet:{schema:'ai2apps.app-state/v1',target,values:{mode:'full'}},get applied(){return applied;},get busy(){return busy;},get state(){return state;},set state(v){state=v;}};
}
test('portable export excludes private draft and restore uses one UI receipt',async()=>{
 const f=fixture();await f.binding.export();const result=await f.binding.restore(f.packet,{requestId:'restore-001'});assert.equal(result.status,'ui_applied');assert.equal(f.applied,1);await f.binding.restore(f.packet,{requestId:'restore-001'});assert.equal(f.applied,1);assert.equal(f.busy,false);assert(!JSON.stringify(f.requests).includes('PRIVATE PROMPT'));
});
test('dirty edits are retained by default and invalid values never apply',async()=>{
 const f=fixture({dirty:true});await assert.rejects(f.binding.restore(f.packet),/retained/);assert.equal(f.applied,0);assert(!f.requests.some(r=>r.url.endsWith('/applications')));
 await assert.rejects(f.binding.restore({...f.packet,values:{mode:'bad'}}),/unsupported/);assert.equal(f.applied,0);
});
test('explicit conflict confirmation applies settings only',async()=>{
 const f=fixture({dirty:true});await f.binding.restore(f.packet,{confirmConflict:async()=>true});assert.equal(f.applied,1);assert.deepEqual(f.state,{mode:'full'});
});
test('edits during asynchronous preparation invalidate the entire application',async()=>{
 const f=fixture({onPrepare:change=>change()});await assert.rejects(f.binding.restore(f.packet),/changed/);assert.equal(f.applied,0);assert.equal(f.busy,false);
});
test('lost receipt never causes a second UI commit on retry',async()=>{
 const f=fixture({failAck:true}),options={requestId:'same-request'};await assert.rejects(f.binding.restore(f.packet,options),/unconfirmed/);await assert.rejects(f.binding.restore(f.packet,options),/unconfirmed/);assert.equal(f.applied,1);assert.equal(f.busy,false);
});
test('export rejects accidental undeclared private fields before sending any values',async()=>{
 const f=fixture();f.state={mode:'compact',token:'SECRET'};await assert.rejects(f.binding.export(),/declared/);assert(!JSON.stringify(f.requests).includes('SECRET'));
});
test('another target cannot be applied to the mounted owner',async()=>{
 const f=fixture();await assert.rejects(f.binding.restore({...f.packet,target:{...f.target,app_id:'another.app'}}),/target/);assert.equal(f.applied,0);
});

for(const appId of ['unrelated.alpha','different.beta'])test('owner content transitions cannot be skipped merely because configuration matches: '+appId,async()=>{
 const f=fixture({appId,needsApply:true});
 await f.binding.restore(f.packet,{requestId:'first-content'});await f.binding.restore(f.packet,{requestId:'second-content'});
 assert.equal(f.applied,2);assert(!JSON.stringify(f.requests).includes('needsApply'));
});
