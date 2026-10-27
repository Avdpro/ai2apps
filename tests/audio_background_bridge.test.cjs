const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const test=require('node:test');
async function scenario(action){
 const listeners={},replies=[],requests=[],observers=[];let channel,jobStatus='queued',accepted,release;
 const acceptedPromise=new Promise(r=>accepted=r),submission=new Promise(r=>release=r);
 const source={postMessage(){}},frame={src:'http://local/frame',contentWindow:source,closest(){return null;},isConnected:true,addEventListener(){},removeEventListener(){}};
 const result={downloadUrl:'/v1/platform/sessions/s/artifacts/a/download',durationSeconds:1};
 const context={window:{AI2AppsCapabilities:{appInstanceId:()=> 'instance'},addEventListener(k,f){(listeners[k]||=[]).push(f)},dispatchEvent(){}},document:{documentElement:{lang:'en'},querySelectorAll:()=>[frame]},location:{origin:'http://local'},URL,URLSearchParams,TextEncoder,AbortController,AbortSignal,Blob,FormData,localStorage:{getItem:()=>null,setItem(){},removeItem(){}},CustomEvent:class{},MutationObserver:class{constructor(f){observers.push(f)}observe(){}disconnect(){}},setTimeout:f=>setTimeout(f,0),clearTimeout,MessageChannel:class{constructor(){channel=this;this.port1={postMessage:v=>replies.push(v),close(){}};this.port2={};}},fetch:async(url,options)=>{
  requests.push({url,options});let value;
  if(url.endsWith('/mini-app-mounts'))value={id:'mount',content_url:'/frame',app_instance_id:'provider',resource:'web/music.html'};
  else if(url.endsWith('/audio-generation')){assert.equal(options.headers.Prefer,'respond-async');assert(!options.signal);accepted();await submission;value={id:'stjob_audio',status:'queued'};}
  else if(url.endsWith('/cancel')){jobStatus='cancelled';value={id:'stjob_audio',status:jobStatus};}
  else if(url.includes('/studio-jobs/')){jobStatus='succeeded';value={id:'stjob_audio',status:jobStatus,result};}
  else value={items:[{capability:'audio.music_generation',ready:true}]};
  return {ok:true,json:async()=>value};
 }};
 vm.runInNewContext(fs.readFileSync('ai2apps/web/static/js/studio_mini_apps.js','utf8'),context);
 const mount=await context.window.AI2AppsStudioMiniApps.mount('ai2apps.readaloud','ai2apps.audio-generation.music');frame.src=new URL(mount.content_url,'http://local').href;
 for(const fn of listeners.message)fn({data:{type:'ai2apps:studio-connect',version:1},source,origin:'null'});
 const running=channel.port1.onmessage({data:{id:1,operation:'audio-generation.generate',capability:'audio.music_generation',payload:{model:'music',prompt:'Piano'}}});
 await acceptedPromise;
 if(action==='close'){frame.isConnected=false;observers.forEach(f=>f());}
 if(action==='cancel')await channel.port1.onmessage({data:{id:2,operation:'audio-generation.cancel'}});
 release();await running;
 const cancellations=requests.filter(r=>r.url.endsWith('/cancel'));
 if(action==='cancel'){assert.equal(cancellations.length,1);assert.equal(jobStatus,'cancelled');}
 else assert.equal(cancellations.length,0);
 if(action==='close'){assert.equal(jobStatus,'queued');assert(!replies.some(r=>r.id===1));}
 if(action==='complete')assert.equal(replies.find(r=>r.id===1).value.completed,true);
}
test('accepted generation survives frame close without cancellation',()=>scenario('close'));
test('explicit cancellation during submission cancels accepted job',()=>scenario('cancel'));
test('completed persistent job returns shared Output result to Package',()=>scenario('complete'));
