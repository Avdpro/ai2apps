const test=require('node:test');const assert=require('node:assert/strict');
const {MessageChannel}=require('node:worker_threads');
require('../web/static/js/mini_app_events.js');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function until(fn){for(let i=0;i<100;i++){if(fn())return;await sleep(5);}throw Error('Timed out');}
const message={type:'ai2apps:event-deliveries',version:1,items:[{delivery_id:'one',result:{details:{title:'Owned detail'}}}]};
test('actual MessageChannel wakes client; acknowledges only after consumption and deduplicates in-flight deliveries',async()=>{
 const {port1,port2}=new MessageChannel();const abort=new AbortController();let calls=0,release;const ack=[];
 const pending=new Promise(r=>release=r);
 try{
  const close=await globalThis.AI2AppsMiniAppEvents.watch(port2,async(op,p)=>{if(op==='events.ack')ack.push(p.deliveryId);},async item=>{calls++;assert.equal(item.result.details.title,'Owned detail');await pending;},{signal:abort.signal});
  port1.postMessage(message);port1.postMessage(message);await until(()=>calls===1);assert.equal(ack.length,0);
  release();await until(()=>ack.length===1);assert.equal(calls,1);
  abort.abort();close();port1.postMessage(message);await sleep(20);assert.equal(calls,1);
 }finally{release();port1.close();port2.close();}
});
test('failed consumption remains unacknowledged and is redelivered',async()=>{
 const {port1,port2}=new MessageChannel();let calls=0,acks=0;
 try{
  const close=await globalThis.AI2AppsMiniAppEvents.watch(port2,async op=>{if(op==='events.ack')acks++;},async()=>{calls++;if(calls===1)throw Error('retry on next delivery');});
  port1.postMessage(message);await until(()=>calls===1);assert.equal(acks,0);
  port1.postMessage(message);await until(()=>acks===1);assert.equal(calls,2);close();
 }finally{port1.close();port2.close();}
});
