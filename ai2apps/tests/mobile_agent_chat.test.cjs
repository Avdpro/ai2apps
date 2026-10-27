const test=require('node:test'),assert=require('node:assert/strict');
const {Client}=require('../web/static/js/mobile_agent_chat.js');
globalThis.crypto ||= require('node:crypto').webcrypto;
test('closed client never discovers, starts or resumes a run',async()=>{
 let requests=0;const client=new Client({container:{},request:async()=>requests++,enabled:false});
 await client.restore('thread');await assert.rejects(client.start('thread',{},'agent','key'),/unavailable/);assert.equal(requests,0);
});
test('restoration only reads saved runs; waiting state never creates another task',async()=>{
 const calls=[],seen=[];const client=new Client({container:{replaceChildren(){}},enabled:true,request:async url=>{calls.push(url);return {items:[{id:'run',status:'waiting_input'}]};}});
 client.show=run=>seen.push(run);client.watch=()=>{};await client.restore('thread');
 assert.deepEqual(calls,['/v1/mobile/chat/threads/thread/agent-runs']);assert.equal(seen[0].status,'waiting_input');
});
test('uncertain response keeps payload and response ID, a different choice cannot replace it',async()=>{
 const calls=[];let fail=true;const client=new Client({container:{},enabled:true,request:async(url,opts)=>{calls.push(JSON.parse(opts.body));if(fail)throw Error('lost');return {status:'running'};}});client.show=()=>{};
 const run={id:'r'},item={id:'i'};await assert.rejects(client.respond(run,item,{decision:'approve'}));fail=false;
 await assert.rejects(client.respond(run,item,{decision:'deny'}),/尚未确认/);await client.respond(run,item,{decision:'approve'});
 assert.equal(calls.length,2);assert.deepEqual(calls[0],calls[1]);
});
test('late response from previous thread cannot replace current thread',async()=>{
 let resolve;const client=new Client({container:{replaceChildren(){}},enabled:true,request:()=>new Promise(r=>resolve=r)});let shows=0;client.show=()=>shows++;
 const restoring=client.restore('old');client.stop();resolve({items:[{id:'old',status:'completed'}]});await restoring;assert.equal(shows,0);
});
test('terminal poll reports actual partial output without creating a new run',async()=>{
 const calls=[],done=[];const client=new Client({container:{},enabled:true,delay:async()=>{},request:async url=>{calls.push(url);return {id:'r',status:'completed',output:{partial:true}};},onComplete:r=>done.push(r)});client.show=()=>{};
 await client.watch({id:'r',status:'running'},0);assert.deepEqual(calls,['/v1/mobile/agent-runs/r']);assert.equal(done[0].output.partial,true);
});
test('restore read failure exposes an error without retrying effectful requests',async()=>{
 const calls=[],errors=[];const client=new Client({container:{},enabled:true,request:async(url,options)=>{calls.push([url,options]);throw Error('offline');}});client.error=e=>errors.push(e.message);
 await client.restore('thread');assert.equal(calls.length,1);assert.equal(calls[0][1],undefined);assert.deepEqual(errors,['offline']);
});

test('owner icons follow recorded execution and declared Mini-App ownership across infrastructure steps',()=>{
 const c=new Client({container:{},enabled:true});c.ownerCatalog={apps:[{app_key:'arbitrary.app',display_name:'Example App',navigation:{icon:'palette'}}],minis:[{id:'arbitrary.mini',app_id:'arbitrary.app',displayName:'Example Mini',icon:'users'}]};
 const owners=c.owners({steps:[{kind:'tool',input:{app_id:'wrong.requested.app'},output:{mini_app_id:'arbitrary.mini'}},{kind:'tool',output:{app_id:'arbitrary.app'}},{kind:'tool',output:{text:'infrastructure read'}}]});
 assert.deepEqual(owners.map(o=>[o.kind,o.id,o.icon]),[['App','arbitrary.app','palette'],['Mini-App','arbitrary.mini','users']]);
 assert.equal(c.owners({steps:[{kind:'tool',input:{app_id:'invented.app'},output:{}}]}).length,0);
 assert.equal(c.owners({status_line:{content:{app_id:'arbitrary.app'}}})[0].name,'Example App');
});
test('missing optional metadata keeps recorded identity with a generic icon',()=>{
 const c=new Client({container:{},enabled:true});
 assert.deepEqual(c.owners({steps:[{kind:'tool',output:{app_id:'unlisted.app'}}]}).map(o=>o.id),['unlisted.app']);
});
