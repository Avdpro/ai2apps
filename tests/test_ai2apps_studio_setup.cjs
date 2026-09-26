const vm = require('node:vm'), fs = require('node:fs'), assert = require('node:assert/strict');
(async () => {
 const listeners = {}, replies = [], calls = [];
 const source = {postMessage() {}}, frame = {src: 'http://local/frame', contentWindow: source, isConnected: true, addEventListener(){}, removeEventListener(){}};
 let channel;
 const storage = new Map();
 let declared = 'audio.detailed_transcription';
 const context = {window: {addEventListener(k, f) {(listeners[k] ||= []).push(f)}, AI2AppsCapabilities:{appInstanceId:()=> 'instance', ensure:async x => {calls.push(x); return {outcome:'configured',session:{id:'s'}}}, acknowledge:async()=>{}}},
 document:{querySelectorAll:()=>[frame]}, location:{origin:'http://local'}, URL, URLSearchParams,
 localStorage:{setItem:(k,v)=>storage.set(k,v),getItem:k=>storage.get(k),removeItem:k=>storage.delete(k)},
 AbortController, MutationObserver:class{observe(){} disconnect(){}},
 MessageChannel:class{constructor(){channel=this;this.port1={postMessage:v=>replies.push(v),close(){}};this.port2={}}},
 fetch:async url=>({ok:true,json:async()=>url.endsWith('/mini-app-mounts')?{id:'mount',content_url:'/frame',app_instance_id:'provider',resource:'web/transcription.html'}:{items:[{capability:declared,ready:false}]}})};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname, '../ai2apps/web/static/js/studio_mini_apps.js'),'utf8'),context);
 await context.window.AI2AppsStudioMiniApps.mount('ai2apps.readaloud','transcription');
 for(const f of listeners.message)f({data:{type:'ai2apps:studio-connect',version:1},source,origin:'null'});
 await channel.port1.onmessage({data:{id:1,operation:'setup',capability:'audio.detailed_transcription'}});
 assert.equal(calls.length,1);assert.equal(calls[0].appId,'ai2apps.readaloud');assert.equal(calls[0].capability,'audio.detailed_transcription');assert.equal(replies[0].value.outcome,'configured');
 await channel.port1.onmessage({data:{id:2,operation:'setup',capability:'audio.source_separation'}});
 assert.equal(calls.length,1);assert.match(replies[1].error,/not allowed/);
 for (const capability of ['audio.source_separation', 'audio.speaker_voice_replacement', 'media.video_speaker_voice_replacement']) {
  declared = capability;
  await channel.port1.onmessage({data:{id:replies.length + 1,operation:'setup',capability}});
  assert.equal(calls.at(-1).capability,capability);
  assert.equal(replies.at(-1).value.outcome,'configured');
 }
 assert.equal(calls.length,4);
 let clicked = '';
 const outputUrl = '/v1/platform/sessions/session/artifacts/archive/download';
 context.Blob = Blob; context.FormData = FormData;
 context.CustomEvent = class {constructor(type, options){this.type=type;this.detail=options.detail}};
 context.window.dispatchEvent = event => {if(event.type === 'ai2apps:studio-output') assert.equal(event.detail.result.downloadUrl, outputUrl)};
 context.document.body = {append(){}};
 context.document.createElement = () => ({click(){clicked=this.href},remove(){}});
 const oldFetch = context.fetch;
 context.fetch = async (url, options) => url.endsWith('/invoke') ? new Response(JSON.stringify({downloadUrl:outputUrl,tracks:[]}),{headers:{'content-type':'application/json'}}) : oldFetch(url,options);
 declared = 'audio.source_separation';
 await channel.port1.onmessage({data:{id:10,operation:'invoke',capability:declared,fields:[['file',new Blob(['audio'])]]}});
 assert.equal(replies.at(-1).error,undefined);
 await channel.port1.onmessage({data:{id:11,operation:'download',url:outputUrl}});
 assert.equal(clicked,outputUrl);
 await channel.port1.onmessage({data:{id:12,operation:'download',url:'https://example.com/other'}});
 assert.match(replies.at(-1).error,/Unknown Mini-App output/);
 context.TextEncoder = TextEncoder;
 context.fetch = async (url, options) => {
  if (url.endsWith('/exports')) {
   assert.equal(JSON.parse(options.body).filename,'transcript.json');
   assert.equal(JSON.parse(options.body).content,'{"edited":true}');
   return {ok:true,json:async()=>({downloadUrl:outputUrl,filename:'transcript.json'})};
  }
  return oldFetch(url,options);
 };
 clicked='';
 await channel.port1.onmessage({data:{id:13,operation:'export.text',filename:'transcript.json',content:'{"edited":true}'}});
 assert.equal(replies.at(-1).error,undefined);
 assert.equal(clicked,outputUrl);
 const setupOptions = [];
 context.window.AI2AppsCapabilities.ensure = async (request, options) => {
  assert.equal(request.capability, 'audio.source_separation');
  setupOptions.push(options.installMore);
  return {outcome:'configured',session:{id:'s'}};
 };
 const miniApp = {id:'separation', requirements:{capabilities:['audio.source_separation']}};
 await context.window.AI2AppsStudioMiniApps.setup('ai2apps.readaloud',miniApp);
 await context.window.AI2AppsStudioMiniApps.setup('ai2apps.readaloud',miniApp,{installMore:true});
 assert.deepEqual(setupOptions,[false,true]);
 console.log('PASS: declared capability opens host ACPF; undeclared capability rejected');
})().catch(e=>{console.error(e);process.exitCode=1});
