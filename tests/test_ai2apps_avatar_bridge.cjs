const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
(async () => {
  const listeners = {}, replies = [];
  const source = {postMessage() {}};
  const frame = {src:'http://local/frame',contentWindow:source,isConnected:true,addEventListener(){},removeEventListener(){}};
  let channel;
  const requests = [];
  const context = {
    window:{AI2AppsCapabilities:{appInstanceId:()=> 'instance'},addEventListener(k,f){(listeners[k] ||= []).push(f)},dispatchEvent(){}},
    document:{documentElement:{lang:'en'},querySelectorAll:()=>[frame]}, location:{origin:'http://local'},
    URL, URLSearchParams, TextEncoder, AbortController, AbortSignal, Blob, FormData,
    localStorage:{getItem:()=>null,setItem(){},removeItem(){}},
    CustomEvent:class {}, MutationObserver:class{observe(){} disconnect(){}},
    EventSource:class{addEventListener(){} close(){}}, setTimeout, clearTimeout,
    MessageChannel:class{constructor(){channel=this;this.port1={postMessage:v=>replies.push(v),close(){}};this.port2={}}},
    fetch:async (url, options) => {
      requests.push({url, method:options?.method});
      if(url === '/v1/platform/gallery/assets/image1') return {ok:true,json:async()=>({kind:'image',name:'photo.png'})};
      if(url === '/v1/platform/gallery/assets/audio1') return {ok:true,json:async()=>({kind:'audio',name:'voice.wav'})};
      if(url.includes('/gallery/assets/') && url.endsWith('/content')) return new Response('media', {headers:{'content-type':url.includes('image1')?'image/png':'audio/wav'}});
      if(url === '/v1/platform/readaloud/outputs') return {ok:true,json:async()=>({items:[{downloadUrl:'/v1/platform/sessions/ses1/artifacts/art1/download',mediaType:'audio/wav',title:'Speech'}]})};
      if(url.endsWith('/ses1/artifacts/art1/download')) return new Response('audio',{headers:{'content-type':'audio/wav'}});
      if(url === '/v1/platform/imagine-studio/runs?limit=100') return {ok:true,json:async()=>({items:[{artifacts:[{id:'image-result',name:'image.png',previewUrl:'/v1/platform/imagine-studio/results/isr_'+'a'.repeat(32)+'/content?appInstanceId=appi_image'}]}]})};
      if(url.includes('/imagine-studio/results/')) return new Response('image',{headers:{'content-type':'image/png'}});
      if(url.endsWith('/invoke')) return {ok:true,status:202,headers:{get:()=>null},blob:async()=>new Blob([JSON.stringify({id:'strun_job',status:'queued'})])};
      if(url.endsWith('/avatar/jobs/strun_job/cancel')) return {ok:true,json:async()=>({id:'strun_job',status:'cancelled'})};
      if(url.endsWith('/avatar/jobs')) return {ok:true,json:async()=>({items:[{id:'strun_job',status:'running'}]})};
      const value=url.endsWith('/mini-app-mounts')?{id:'mount',content_url:'/frame',app_instance_id:'provider',resource:'web/photo-speaking.html'}:
        url.endsWith('/invocations')?{id:'a'.repeat(32),eventsUrl:url+'/'+'a'.repeat(32)+'/events'}:{items:[{capability:'video.avatar_generation',ready:true}]};
      return {ok:true,json:async()=>value};
    }
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../ai2apps/web/static/js/studio_mini_apps.js'),'utf8'),context);
  const mount = await context.window.AI2AppsStudioMiniApps.mount('ai2apps.video-studio','ai2apps.avatar.photo-speaking');
  frame.src = new URL(mount.content_url, 'http://local').href;
  for(const listener of listeners.message) listener({data:{type:'ai2apps:studio-connect',version:1},source,origin:'null'});
  await channel.port1.onmessage({data:{id:1,operation:'avatar.cancel',jobId:'../escape'}});
  assert.match(replies.at(-1).error,/Invalid avatar job/);
  await channel.port1.onmessage({data:{id:2,operation:'invoke',capability:'video.avatar_generation',fields:[['file',new Blob(['audio'])],['reference',new Blob(['portrait'])],['profile','standard'],['avatar_model_id','chosen'],['avatar_resolution','512x512']]}});
  assert.equal(replies.find(x=>x.id===2).value.status,202);
  await channel.port1.onmessage({data:{id:3,operation:'avatar.jobs'}});
  assert.equal(replies.find(x=>x.id===3).value.items[0].status,'running');
  await channel.port1.onmessage({data:{id:4,operation:'avatar.cancel',jobId:'strun_job'}});
  assert.equal(replies.find(x=>x.id===4).value.status,'cancelled');
  assert(requests.some(x=>x.url.endsWith('/avatar/jobs/strun_job/cancel')&&x.method==='POST'));
  assert(!requests.some(x=>x.url.includes('/invocations')));
  let next = 10;
  async function read(kind, reference) {
    const id = next++;
    await channel.port1.onmessage({data:{id,operation:'avatar.input.read',kind,reference}});
    return replies.find(item=>item.id===id);
  }
  assert.equal((await read('image',{source:'gallery',assetId:'image1'})).value.body.type,'image/png');
  assert.equal((await read('audio',{source:'gallery',assetId:'audio1'})).value.name,'voice.wav');
  assert.equal((await read('audio',{source:'audio-output',sessionId:'ses1',artifactId:'art1'})).value.body.type,'audio/wav');
  assert.equal((await read('image',{source:'image-output',appInstanceId:'appi_image',artifactId:'image-result'})).value.body.type,'image/png');
  assert.match((await read('audio',{source:'gallery',assetId:'image1'})).error,/类型/);
  assert.match((await read('image',{source:'gallery',assetId:'../escape'})).error,/不支持/);
  assert.match((await read('audio',{source:'audio-output',sessionId:'other',artifactId:'art1'})).error,/不可用/);
  assert.match((await read('image',{source:'image-output',appInstanceId:'appi_other',artifactId:'image-result'})).error,/不可用/);
  assert(!requests.some(item=>item.url.includes('../escape')));
  console.log('PASS: avatar jobs use the authorized mount, reject traversal and cancel explicitly');
})().catch(error=>{console.error(error);process.exitCode=1});

// A durable job has no download URL until it finishes, but must still refresh Host Runs.
{
  const context = {window:{}, URL, crypto:require('node:crypto').webcrypto};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../ai2apps/web/static/js/video_studio.js'),'utf8'),context);
  const studio = context.window.videoStudioApp();
  let refreshed = 0;
  studio.refresh = () => { refreshed++; };
  studio.handlePackageOutput({detail:{studioId:'another-studio'}});
  assert.equal(refreshed,0);
  studio.handlePackageOutput({detail:{studioId:'ai2apps.video-studio',miniAppId:'ai2apps.avatar.photo-speaking'}});
  assert.equal(refreshed,1);
  assert.equal(studio.packageOutputUrl,'');
}
