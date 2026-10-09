const vm=require('node:vm'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 let stops=0,autoStop,permission;
 const stream=()=>({getTracks:()=>[{stop(){stops++}}]});
 class Recorder {
  static isTypeSupported(type){return type.startsWith('audio/webm')}
  constructor(stream,options){this.mimeType=options.mimeType;this.state='inactive'}
  start(){this.state='recording'}
  stop(){this.state='inactive';this.ondataavailable({data:new Blob(['voice'],{type:this.mimeType})});this.onstop()}
 }
 const ctx={window:{addEventListener(){},removeEventListener(){}},navigator:{mediaDevices:{getUserMedia:async()=>stream()}},MediaRecorder:Recorder,Blob,setTimeout(fn){autoStop=fn;return 1},clearTimeout(){},Date};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../ai2apps/web/static/js/studio_audio_recorder.js'),'utf8'),ctx);
 const C=ctx.window.AI2AppsStudioAudioRecorder;
 let r=new C();assert.equal((await r.start(10)).maxSeconds,10);await assert.rejects(r.start(),/recording_busy/);
 autoStop();let result=await r.stop();assert.equal(result.body.type,'audio/webm;codecs=opus');assert.equal(result.body.size,5);assert.equal(stops,1);
 r.dispose();r=new C();await r.start();r.dispose();assert.equal(stops,2);
 ctx.navigator.mediaDevices.getUserMedia=()=>new Promise(resolve=>permission=resolve);
 r=new C();const pending=r.start();r.dispose();permission(stream());await assert.rejects(pending,/recording_cancelled/);assert.equal(stops,3);
 ctx.navigator.mediaDevices.getUserMedia=async()=>{const e=new Error();e.name='NotAllowedError';throw e};
 await assert.rejects(new C().start(),/recording_permission_denied/);
 ctx.navigator.mediaDevices.getUserMedia=async()=>stream();r=new C();await r.start();r.recorder.onerror();await assert.rejects(r.stop(),/recording_failed/);assert.equal(stops,4);r.dispose();
 console.log('PASS: recording, auto-stop, duplicate start, track release, pending permission cleanup, denial and errors');
})().catch(e=>{console.error(e);process.exitCode=1});
