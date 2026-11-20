const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),{webcrypto}=require('node:crypto');
const audioApi=require('../web/static/js/bot_realtime_audio.js');
global.crypto=webcrypto;
const flush=()=>new Promise(r=>setImmediate(r));
test('bounded VAD produces one final per utterance and emits partial WAV without draft writes',async()=>{
 const events=[],vad=new audioApi.Vad(16000,e=>events.push(e));
 for(let i=0;i<30;i++)vad.push(new Float32Array(320));
 assert.equal(events.filter(e=>e.type==='start').length,0);
 for(let i=0;i<100;i++)vad.push(new Float32Array(320).fill(.08));
 for(let i=0;i<40;i++)vad.push(new Float32Array(320));
 assert.equal(events.filter(e=>e.type==='start').length,1);assert.ok(events.some(e=>e.type==='partial'));
 const final=events.filter(e=>e.type==='final');assert.equal(final.length,1);assert.equal(final[0].audio.type,'audio/wav');
 const bytes=await final[0].audio.arrayBuffer(),view=new DataView(bytes);assert.equal(view.getUint32(24,true),16000);assert.equal(view.getUint32(40,true),bytes.byteLength-44);assert.ok(bytes.byteLength<16000*3*2+44);
});
test('long utterances are bounded; mute reset cannot submit pre-mute audio',()=>{
 const events=[],vad=new audioApi.Vad(16000,e=>events.push(e));
 for(let i=0;i<950;i++)vad.push(new Float32Array(320).fill(.1));
 assert.equal(events.filter(e=>e.type==='final').length,1);assert.ok(events.find(e=>e.type==='final').audio.size<=18.1*16000*2+44);
 vad.reset();const count=events.filter(e=>e.type==='final').length;for(let i=0;i<50;i++)vad.push(new Float32Array(320));assert.equal(events.filter(e=>e.type==='final').length,count);
});
function fixture(options={}){
 class El{constructor(tag){this.tagName=tag;this.children=[];this.hidden=false;this.attributes={};this.dataset={};this.listeners={};this.style={setProperty(){}};this.classes=new Set();this.classList={add:x=>this.classes.add(x),remove:x=>this.classes.delete(x)};}append(...x){this.children.push(...x);}setAttribute(k,v){this.attributes[k]=v;}addEventListener(k,f){this.listeners[k]=f;}removeEventListener(k){delete this.listeners[k];}}
 const windowListeners={},docListeners={},calls=[],requests=[],errors=[];let emit,deviceClosed=0,deviceMuted=false,leased=false;
 const composer={draft:'keep this draft',files:[],active:false,canStartRealtime:()=>true,hasFiles(){return !!this.files.length;},blocked:()=>false,ids(){return this.files.slice();},removeIds(ids){this.files=this.files.filter(x=>!ids.includes(x));},mountRealtime(button,panel){this.button=button;this.panel=panel;},setRealtimeActive(v){this.active=v;}};
 const config={configured:true,ready:true,revision:1,stt_model_id:'asr',tts_model_id:'tts',voice:'one'};
 const document={hidden:false,documentElement:{lang:'zh'},createElement:t=>new El(t),createTextNode:text=>({textContent:text}),addEventListener:(n,f)=>docListeners[n]=f,removeEventListener:n=>delete docListeners[n]};
 const window={addEventListener:(n,f)=>windowListeners[n]=f,removeEventListener:n=>delete windowListeners[n],AI2AppsStreamingTTS:require('../web/static/js/streaming_tts.js'),AI2AppsBotRealtimeAudio:{capture:async(callback,signal)=>{emit=callback;if(options.captureDelay)await options.captureDelay;leased=true;return {close(){deviceClosed++;leased=false;},mute(v){deviceMuted=v;}};}}};
 const request=async(url,method,body)=>{requests.push({url,method,body});if(url.endsWith('/settings'))return config;if(url.endsWith('/sessions'))return {id:'voice-one',settings:config};if(url.endsWith('/inputs')){if(options.submitFailure)throw Error('connection lost');return {state:'accepted',dialogue_run_id:'run-one'};}return {};};
 const fetch=async(url,opts)=>{calls.push({url,opts});if(url.includes('transcriptions')){if(options.asr) return options.asr(url,opts);return {ok:true,json:async()=>({text:'整理这些资料'})};}return {ok:true,json:async()=>({})};};
 const form=new El('form');const env={window,document,crypto:webcrypto,fetch,AbortController,DOMException,Blob,FormData,Event,URL,setTimeout,clearTimeout,setInterval,clearInterval};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/bot_realtime.js','utf8'),env);
 const api=window.AI2AppsBotRealtime.create({botId:'bot-one',sessionId:'session-one',composer,form,getModel:()=> 'bot-model',request,onAccepted:v=>calls.push({accepted:v}),label:(zh,en)=>en,onError:e=>errors.push(e.message)});
 return {api,composer,form,calls,requests,errors,config,docListeners,window,emit:e=>emit(e),get closed(){return deviceClosed;},get leased(){return leased;},get muted(){return deviceMuted;}};
}
test('configured button starts one real-owner turn; partial is a bubble, not a submission or editable draft',async()=>{
 const f=fixture();await flush();assert.equal(f.composer.button.hidden,false);f.composer.button.onclick();await flush();assert.equal(f.composer.active,true);
 f.emit({type:'start',turn:'u-one'});f.emit({type:'partial',turn:'u-one',audio:new Blob(['wav'])});await flush();
 const bubble=f.composer.panel.children[0];assert.equal(bubble.hidden,false);assert.equal(bubble.children[0].textContent,'整理这些资料');assert.equal(f.requests.filter(r=>r.url.endsWith('/inputs')).length,0);assert.equal(f.composer.draft,'keep this draft');
 f.emit({type:'final',turn:'u-one',audio:new Blob(['wav'])});await flush();assert.equal(f.requests.filter(r=>r.url.endsWith('/inputs')).length,1);assert.equal(f.requests.at(-1).body.turn_id,'u-one');assert.equal(f.composer.draft,'keep this draft');
 await f.api.stop();assert.equal(f.composer.active,false);assert.equal(f.closed,1);assert.equal(f.composer.panel.hidden,true);assert.ok(f.calls.some(c=>c.url?.endsWith('/close')));f.api.dispose();
});
test('late transcription after close cannot submit or reopen the ball',async()=>{
 let resolve;const response=new Promise(r=>resolve=r);const f=fixture({asr:()=>response});await flush();f.composer.button.onclick();await flush();f.emit({type:'start',turn:'late'});f.emit({type:'final',turn:'late',audio:new Blob(['wav'])});await flush();await f.api.stop();resolve({ok:true,json:async()=>({text:'late'})});await flush();assert.equal(f.requests.filter(r=>r.url.endsWith('/inputs')).length,0);assert.equal(f.composer.panel.hidden,true);f.api.dispose();
});
test('microphone mute keeps an already-final utterance in processing',async()=>{
 let resolve;const response=new Promise(r=>resolve=r),f=fixture({asr:()=>response});await flush();f.composer.button.onclick();await flush();f.emit({type:'start',turn:'final-before-mute'});f.emit({type:'final',turn:'final-before-mute',audio:new Blob(['wav'])});await flush();f.composer.panel.children[2].onclick();assert.equal(f.muted,true);resolve({ok:true,json:async()=>({text:'already finished speaking'})});await flush();assert.equal(f.requests.filter(r=>r.url.endsWith('/inputs')).length,1);f.api.dispose();
});
test('failed delivery pauses capture, retains text, and explicit retry uses the same turn id',async()=>{
 const options={submitFailure:true},f=fixture(options);await flush();f.composer.button.onclick();await flush();f.emit({type:'start',turn:'stable'});f.emit({type:'final',turn:'stable',audio:new Blob(['wav'])});await flush();assert.equal(f.muted,true);const retry=f.composer.panel.children[0].children[2];assert.equal(retry.hidden,false);options.submitFailure=false;retry.onclick();await flush();const sends=f.requests.filter(r=>r.url.endsWith('/inputs'));assert.equal(sends.length,2);assert.equal(sends[0].body.turn_id,sends[1].body.turn_id);f.api.dispose();
});
test('closing during pending device permission releases late device without resurrecting the session',async()=>{
 let resolve;const f=fixture({captureDelay:new Promise(r=>resolve=r)});await flush();f.composer.button.onclick();await flush();await f.api.stop();resolve();await flush();assert.equal(f.closed,1);assert.equal(f.leased,false);assert.equal(f.composer.active,false);assert.equal(f.composer.panel.hidden,true);f.api.dispose();
});
test('only explicit attachment checkbox binds files to speech; closing keeps draft and files',async()=>{
 const f=fixture();f.composer.files=['owned-file'];await flush();f.composer.button.onclick();await flush();f.composer.panel.children.at(-1).children[0].checked=true;f.emit({type:'start',turn:'with-file'});f.emit({type:'final',turn:'with-file',audio:new Blob(['wav'])});await flush();assert.deepEqual(Array.from(f.requests.find(r=>r.url.endsWith('/inputs')).body.attachments),['owned-file']);assert.equal(f.composer.files.length,0);f.composer.files=['new-draft-file'];await f.api.stop();assert.deepEqual(f.composer.files,['new-draft-file']);assert.equal(f.composer.draft,'keep this draft');f.api.dispose();
});

test('read replies off keeps voice ingress and excludes replies and approval notices from speech',async()=>{
 const f=fixture();await flush();f.composer.button.onclick();await flush();
 const toggle=f.composer.panel.children.find(x=>x.className==='bot-realtime-read').children[0];
 assert.equal(toggle.checked,true);toggle.checked=false;toggle.onchange();
 let speeches=0;f.window.AI2AppsStreamingTTS={...f.window.AI2AppsStreamingTTS,playSegments:async()=>{speeches++;}};
 f.api.messages([{id:'silent',role:'assistant',content:'Completed.'}]);f.api.observe([{id:'job',status:'waiting_capability'}]);await flush();assert.equal(speeches,0);
 f.emit({type:'start',turn:'input-only'});f.emit({type:'final',turn:'input-only',audio:new Blob(['wav'])});await flush();
 assert.equal(f.requests.filter(x=>x.url.endsWith('/inputs')).length,1);assert.equal(f.muted,false);assert.equal(f.leased,true);
 toggle.checked=true;toggle.onchange();f.api.messages([{id:'silent',role:'assistant',content:'Completed.'}]);await flush();assert.equal(speeches,0);
 f.api.messages([{id:'new',role:'assistant',content:'New reply.'}]);await flush();assert.equal(speeches,1);f.api.dispose();
});
test('turning reading off aborts current synthesis and discards queued speech',async()=>{
 const f=fixture();await flush();f.composer.button.onclick();await flush();let resolve,signal,calls=0;
 f.window.AI2AppsStreamingTTS={...f.window.AI2AppsStreamingTTS,playSegments:async opts=>{calls++;signal=opts.signal;await new Promise(r=>resolve=r);}};
 f.api.messages([{id:'one',role:'assistant',content:'First.'},{id:'two',role:'assistant',content:'Second.'}]);await flush();
 const toggle=f.composer.panel.children.find(x=>x.className==='bot-realtime-read').children[0];toggle.checked=false;toggle.onchange();assert.equal(signal.aborted,true);resolve();await flush();assert.equal(calls,1);assert.equal(f.leased,true);f.api.dispose();
});

test('ASR-only sessions disable automatic readout and continue original Bot input',async()=>{
 const f=fixture();f.config.speech_ready=false;f.config.tts_model_id=null;await flush();f.composer.button.onclick();await flush();
 const toggle=f.composer.panel.children.find(x=>x.className==='bot-realtime-read').children[0];assert.equal(toggle.checked,false);assert.equal(toggle.disabled,true);
 let spoken=0;f.window.AI2AppsStreamingTTS={...f.window.AI2AppsStreamingTTS,playSegments:async()=>{spoken++;}};f.api.messages([{id:'silent',role:'assistant',content:'No automatic speech'}]);
 f.emit({type:'start',turn:'only-asr'});f.emit({type:'final',turn:'only-asr',audio:new Blob(['wav'])});await flush();assert.equal(spoken,0);assert.equal(f.requests.filter(x=>x.url.endsWith('/inputs')).length,1);f.api.dispose();
});
