const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict'),test=require('node:test');
async function scenario(close){
 const listeners={},replies=[],requests=[],observers=[],events=[];let channel,accepted,release;
 const acceptedPromise=new Promise(r=>accepted=r),submission=new Promise(r=>release=r);
 const source={postMessage(){}},frame={src:'http://local/frame',contentWindow:source,closest(){return null},isConnected:true,addEventListener(){},removeEventListener(){}};
 const url='/v1/platform/sessions/s/artifacts/a/download';
 const response=value=>({status:200,ok:true,json:async()=>value,headers:{get:()=>null},blob:async()=>new Blob(['video'],{type:'video/mp4'})});
 const context={window:{AI2AppsCapabilities:{appInstanceId:()=> 'host'},addEventListener(k,f){(listeners[k]||=[]).push(f)},dispatchEvent(e){events.push(e)}},document:{documentElement:{lang:'en'},querySelectorAll:()=>[frame]},location:{origin:'http://local'},URL,URLSearchParams,TextEncoder,AbortController,AbortSignal,Blob,FormData,localStorage:{getItem:()=>null,setItem(){},removeItem(){}},CustomEvent:class{constructor(type,options){this.type=type;this.detail=options.detail}},MutationObserver:class{constructor(f){observers.push(f)}observe(){}disconnect(){}},setTimeout:f=>setTimeout(f,0),clearTimeout,MessageChannel:class{constructor(){channel=this;this.port1={postMessage:v=>replies.push(v),close(){}};this.port2={}}},fetch:async(u,o)=>{
  requests.push({u,o});
  if(u.endsWith('/mini-app-mounts'))return response({id:'mount',content_url:'/frame',app_instance_id:'provider',resource:'video.html'});
  if(u.endsWith('/invoke')){assert.equal(o.headers.Prefer,'respond-async');assert(!o.signal);accepted();await submission;return {...response({id:'stjob_v',run_id:'strun_v',status:'queued'}),status:202};}
  if(u.includes('/studio-jobs/'))return response({id:'stjob_v',run_id:'strun_v',status:'succeeded',result:{downloadUrl:url}});
  if(u.includes('/download'))return response({});
  return response({items:[{capability:'media.video_speaker_voice_replacement',ready:true}]});
 }};
 vm.runInNewContext(fs.readFileSync('ai2apps/web/static/js/studio_mini_apps.js','utf8'),context);
 const mount=await context.window.AI2AppsStudioMiniApps.mount('ai2apps.video-studio','package.voice');frame.src=new URL(mount.content_url,'http://local').href;
 for(const fn of listeners.message)fn({data:{type:'ai2apps:studio-connect',version:1},source,origin:'null'});
 const running=channel.port1.onmessage({data:{id:1,operation:'invoke',capability:'media.video_speaker_voice_replacement',fields:[['file',new Blob(['video'],{type:'video/mp4'})],['action','replace']]}});
 await acceptedPromise;
 if(close){frame.isConnected=false;observers.forEach(f=>f());}
 release();await running;
 assert(!requests.some(r=>r.u.endsWith('/cancel')));
 assert(events.some(e=>e.detail?.runId==='strun_v'));
 if(close){assert(!requests.some(r=>r.u.includes('/studio-jobs/')));assert(!replies.some(r=>r.id===1));}
 else {assert.equal(replies.find(r=>r.id===1).value.status,200);assert(events.some(e=>e.detail?.preserveSelection));}
}
test('video submit survives frame disposal without cancelling accepted task',()=>scenario(true));
test('video completion retains binary Package response contract and shared Output',()=>scenario(false));
