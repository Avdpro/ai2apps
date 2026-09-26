import subprocess
from pathlib import Path


def test_host_bridge_enforces_mount_identity_capability_and_navigation():
    root = Path(__file__).resolve().parents[1]
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const listeners = [];
const store = new Map();
const fetches = [];
const eventSources = [];
const ensures = [];
let transferred;
const source = {postMessage(message, origin, ports) { transferred = ports[0]; }};
const frame = {src:'', contentWindow:source, isConnected:true, dataset:{}, style:{},
  addEventListener(name, fn) { this[name] = fn; }, removeEventListener(name, fn) { if(this[name] === fn) delete this[name]; }};
global.location = {origin:'http://localhost:1234', hash:''};
global.document = {querySelector:()=>null, querySelectorAll:()=>[frame]};
global.window = {AI2AppsCapabilities:{appInstanceId:()=> 'owner',ensure:async (...args)=>{ensures.push(args);return {outcome:'cancelled'};}}, addEventListener:(name, fn)=>listeners.push(fn), dispatchEvent:()=>{}};
global.localStorage = {getItem:key=>store.get(key)||null,setItem:(key,value)=>store.set(key,value),removeItem:key=>store.delete(key)};
global.MutationObserver = class {observe(){} disconnect(){}};
global.MessageChannel = class {constructor(){ this.port1={close(){},postMessage:value=>this.port2.receive(value)}; this.port2={send:value=>this.port1.onmessage({data:value})}; }};
global.EventSource = class {constructor(url) { this.url=url; this.listeners={}; eventSources.push(this); } addEventListener(name, fn) { this.listeners[name]=fn; } close() { this.closed=true; }};
let authorized = true;
global.fetch = async (url, options) => {
 fetches.push([url,options]);
 if(url.endsWith('/mini-app-mounts')) return Response.json({id:'mount',app_instance_id:'provider',resource:'web/a.html',content_url:'/admin/resource?mount_id=mount'});
 if(!authorized) return Response.json({detail:'Signed out'}, {status:401});
 if(url.endsWith('/capabilities')) return Response.json({items:[{capability:'audio.source_separation'},{capability:'media.video_subtitles'},{capability:'media.video_audio_translation'},{capability:'audio.speech_generation'},{capability:'audio.voice_clone'}]});
 if(url.endsWith('/characters')) return Response.json({items:[{id:'voice-1',name:'Narrator',ready:true}]});
 if(url.endsWith('/voice-clone-models')) return Response.json({items:[{id:'clone-1',name:'Clone',ready:true}]});
 if(url.endsWith('/invocations')) return Response.json({id:'0123456789abcdef0123456789abcdef',eventsUrl:'/v1/platform/studios/ai2apps.readaloud/mini-app-mounts/mount/invocations/0123456789abcdef0123456789abcdef/events'});
 return new Response(new Blob(['zip']),{headers:{'content-type':'application/zip'}});
};
vm.runInThisContext(fs.readFileSync('ai2apps/web/static/js/studio_mini_apps.js','utf8'));
(async()=>{
 const mount=await window.AI2AppsStudioMiniApps.mount('ai2apps.readaloud','mini');
 frame.src=new URL(mount.content_url,location.origin).href;
 const connect = event => listeners.forEach(fn=>fn(event));
 connect({source:{},origin:'null',data:{type:'ai2apps:studio-connect',version:1}});
 assert.equal(transferred,undefined);
 connect({source,origin:'https://evil.example',data:{type:'ai2apps:studio-connect',version:1}});
 assert.equal(transferred,undefined);
 connect({source,origin:'null',data:{type:'ai2apps:studio-connect',version:1}});
 assert.ok(transferred);
 let id=0;
 const call = data=>new Promise(resolve=>{transferred.receive=resolve;transferred.send({id:++id,...data});});
 assert.equal((await call({operation:'probe'})).value.items.length,5);
 assert.equal((await call({operation:'characters.list'})).value.items[0].name,'Narrator');
 assert.equal((await call({operation:'voice-clone-models.list'})).value.items[0].id,'clone-1');
 assert.equal((await call({operation:'setup',capability:'audio.voice_clone',installMore:true})).value.outcome,'cancelled');
 assert.equal(ensures.at(-1)[1].installMore,true);
 assert.match((await call({operation:'invoke',capability:'admin.delete',fields:[]})).error,/not allowed/);
 assert.match((await call({operation:'invoke',capability:'audio.source_separation',fields:[['url','https://evil']]})).error,/Invalid/);
 assert.match((await call({operation:'draft.set',value:JSON.stringify({schema:'ai2apps.mini-app-draft/v1',miniApp:'other'})})).error,/Invalid/);
 assert.equal(store.size,0);
 const draft=JSON.stringify({schema:'ai2apps.mini-app-draft/v1',miniApp:'mini'});
 assert.equal((await call({operation:'draft.set',value:draft})).error,undefined);
 assert.equal((await call({operation:'draft.get'})).value,draft);
 authorized=false;
 assert.match((await call({operation:'draft.get'})).error,/Signed out/);
 authorized=true;
 const result=await call({operation:'invoke',capability:'audio.source_separation',fields:[['file',new Blob(['media'])],['profile','vocals_instrumental']]});
 assert.equal(await result.value.body.text(),'zip');
 assert.ok(fetches.at(-1)[0].includes('/mount/capabilities/audio.source_separation/invoke'));
 const subtitles=await call({operation:'invoke',capability:'media.video_subtitles',fields:[['file',new Blob(['video'])],['subtitle_font_size','extra_large'],['subtitle_background','box']]});
 assert.equal(await subtitles.value.body.text(),'zip');
 assert.equal(fetches.at(-1)[1].body.get('subtitle_font_size'),'extra_large');
 assert.equal(fetches.at(-1)[1].body.get('subtitle_background'),'box');
 assert.equal(fetches.at(-1)[1].headers['X-AI2Apps-Invocation-ID'],'0123456789abcdef0123456789abcdef');
 assert.equal(eventSources.length,1);
 eventSources[0].listeners.progress({data:JSON.stringify({invocationId:'0123456789abcdef0123456789abcdef',status:'completed',percent:15})});
 assert.notEqual(eventSources[0].closed,true,'phase completion must keep SSE open');
 eventSources[0].listeners.progress({data:JSON.stringify({invocationId:'0123456789abcdef0123456789abcdef',status:'completed',percent:100})});
 assert.equal(eventSources[0].closed,true,'100% completion closes SSE');
 const dubbing=await call({operation:'invoke',capability:'media.video_audio_translation',fields:[['file',new Blob(['video'])],['target_language','zh'],['voice_profile_id','__original_voice__'],['voice_clone_model_id','clone-1'],['asr_verification','true']]});
 assert.equal(await dubbing.value.body.text(),'zip');
 assert.equal(fetches.at(-1)[1].body.get('voice_profile_id'),'__original_voice__');
 assert.equal(fetches.at(-1)[1].body.get('voice_clone_model_id'),'clone-1');
 assert.equal(fetches.at(-1)[1].body.get('asr_verification'),'true');
 assert.equal(fetches.at(-1)[1].headers['X-AI2Apps-Invocation-ID'],'0123456789abcdef0123456789abcdef');
 assert.equal(eventSources.length,2);
 eventSources[1].listeners.progress({data:JSON.stringify({invocationId:'0123456789abcdef0123456789abcdef',phaseIndex:3,status:'running',percent:60,phasePercent:40})});
 assert.notEqual(eventSources[1].closed,true);
 eventSources[1].listeners.progress({data:JSON.stringify({invocationId:'0123456789abcdef0123456789abcdef',phaseIndex:5,status:'completed',percent:100,phasePercent:100})});
 assert.equal(eventSources[1].closed,true);
 frame.load();
 transferred=undefined;
 connect({source,origin:'null',data:{type:'ai2apps:studio-connect',version:1}});
 assert.equal(transferred,undefined,'navigation cannot reconnect to old mount');
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    subprocess.run(['node', '-e', script], cwd=root, check=True, capture_output=True, text=True)
