/* Sandbox App SDK: all authority remains in the current Shell mount. */
(function(root){
 'use strict';
 function client({timeout=120000}={}){
  const fragment=new URLSearchParams(root.location.hash.slice(1));
  const mountToken=fragment.get('ai2apps-mount'),instanceId=fragment.get('ai2apps-instance');
  if(!mountToken||!instanceId||root.parent===root)throw Error('Open this Package in the AI2Apps Shell');
  const pending=new Map(),watchers=new Set();let disposed=false;
  function receive(event){const m=event.data||{};if(event.source!==root.parent||m.type!=='ai2apps.host.response'||m.mountToken!==mountToken||m.instanceId!==instanceId)return;
   const p=pending.get(m.requestId);if(!p)return;pending.delete(m.requestId);clearTimeout(p.timer);m.ok?p.resolve(m.result):p.reject(Error(m.error||'Event request failed'));}
  root.addEventListener('message',receive);
  function call(operation,data={}){if(disposed)return Promise.reject(Error('Event client closed'));const requestId=crypto.randomUUID();return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>{pending.delete(requestId);reject(Error('Event request timed out; check permissions in Settings → Event/Hook'));},timeout);pending.set(requestId,{resolve,reject,timer});
   root.parent.postMessage({type:'ai2apps.shell.events.'+operation,mountToken,instanceId,requestId,...data},'*');});}
  return Object.freeze({request:proposal=>call('request',{proposal}),list:()=>call('list'),details:deliveryId=>call('details',{deliveryId}),ack:deliveryId=>call('ack',{deliveryId}),
   watch(onDelivery,{signal,onError=()=>{},interval=2000}={}){
    let closed=false,timer;const seen=new Set();
    const stop=()=>{closed=true;clearTimeout(timer);watchers.delete(stop);signal?.removeEventListener('abort',stop);};
    async function poll(){if(closed||disposed)return;try{const value=await call('list');for(const item of value.items||[]){if(closed||disposed)break;if(seen.has(item.delivery_id))continue;
      await onDelivery(item);if(closed||disposed)break;await call('ack',{deliveryId:item.delivery_id});seen.add(item.delivery_id);if(seen.size>1000)seen.delete(seen.values().next().value);
     }}catch(e){onError(e);}if(!closed&&!disposed)timer=setTimeout(poll,Math.max(1000,Number(interval)||2000));}
    watchers.add(stop);if(signal?.aborted)stop();else{signal?.addEventListener('abort',stop,{once:true});timer=setTimeout(poll,0);}return stop;
   },
   close(){disposed=true;for(const stop of [...watchers])stop();root.removeEventListener('message',receive);for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('Event client closed'));}pending.clear();}});
 }
 root.AI2AppsPackageEvents=Object.freeze({client});
})(globalThis);
