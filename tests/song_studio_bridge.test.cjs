const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const listeners={},replies=[],events=[],requests=[],streams=[];let channel,hold=false,started,releaseProbe;
 const source={postMessage(){}},frame={src:'http://local/frame',contentWindow:source,isConnected:true,addEventListener(){},removeEventListener(){}};
 const context={window:{AI2AppsCapabilities:{appInstanceId:()=> 'instance'},addEventListener(k,f){(listeners[k]||=[]).push(f)},dispatchEvent:e=>events.push(e)},document:{documentElement:{lang:'en'},querySelectorAll:()=>[frame]},location:{origin:'http://local'},URL,URLSearchParams,TextEncoder,AbortController,AbortSignal,Blob,FormData,localStorage:{getItem:()=>null,setItem(){},removeItem(){}},CustomEvent:class{constructor(type,options){this.type=type;this.detail=options?.detail;}},MutationObserver:class{observe(){}disconnect(){}},EventSource:class{constructor(){streams.push(this);}addEventListener(name,f){this[name]=f;}close(){this.closed=true;}},setTimeout,clearTimeout,MessageChannel:class{constructor(){channel=this;this.port1={postMessage:v=>replies.push(v),close(){}};this.port2={};}},fetch:async(url,options)=>{
  requests.push({url,options});let value;
  if(url.endsWith('/mini-app-mounts'))value={id:'mount',content_url:'/frame',app_instance_id:'provider',resource:'web/song.html'};
  else if(url.endsWith('/invocations'))value={id:'a'.repeat(32),eventsUrl:url+'/'+'a'.repeat(32)+'/events'};
  else if(url.endsWith('/audio-generation')){
   if(streams.length)streams.at(-1).progress({data:JSON.stringify({invocationId:'a'.repeat(32),phaseIndex:2})});
   if(hold){started();await new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new Error('Aborted')),{once:true}));}
   value={downloadUrl:'/v1/platform/sessions/s/artifacts/a/download',filename:'song.wav',durationSeconds:46.6,reachedLimit:false};
  }else{if(releaseProbe)await new Promise(r=>releaseProbe=r);value={items:[{capability:'audio.song_generation',ready:true}]};}
  return {ok:true,json:async()=>value};
 }};
 vm.runInNewContext(fs.readFileSync('ai2apps/web/static/js/studio_mini_apps.js','utf8'),context);
 const mount=await context.window.AI2AppsStudioMiniApps.mount('ai2apps.readaloud','ai2apps.audio-generation.song');frame.src=new URL(mount.content_url,'http://local').href;
 for(const fn of listeners.message)fn({data:{type:'ai2apps:studio-connect',version:1},source,origin:'null'});
 const req=id=>({data:{id,operation:'audio-generation.generate',capability:'audio.song_generation',payload:{schema:'ai2apps.audio-generation/v2',model:'yue2',prompt:'Piano'}}});
 await channel.port1.onmessage(req(1));assert.equal(replies.find(r=>r.id===1).value.completed,true);assert.equal(streams[0].closed,true);assert(replies.some(r=>r.type==='ai2apps:studio-progress'&&r.progress.phaseIndex===2));assert.equal(requests.find(r=>r.url.endsWith('/audio-generation')).options.headers['X-AI2Apps-Invocation-ID'],'a'.repeat(32));assert.equal(events.filter(e=>e.type==='ai2apps:studio-output').length,1);
 hold=true;const ready=new Promise(r=>started=r),running=channel.port1.onmessage(req(2));await ready;await channel.port1.onmessage({data:{id:3,operation:'audio-generation.cancel'}});await running;assert(replies.find(r=>r.id===2).error);assert.equal(streams.at(-1).closed,true);assert.equal(events.filter(e=>e.type==='ai2apps:studio-output').length,1);assert.equal(events.at(-1).detail.running,false);
 hold=false;releaseProbe=true;const early=channel.port1.onmessage(req(4));await Promise.resolve();await channel.port1.onmessage({data:{id:5,operation:'audio-generation.cancel'}});releaseProbe();releaseProbe=null;await early;assert.match(replies.find(r=>r.id===4).error,/cancelled/);assert.equal(events.filter(e=>e.type==='ai2apps:studio-output').length,1);
 console.log('Song Host bridge: progress, output ownership, cancellation and early cancellation passed');
})();
