/* Actual getUserMedia/Web Locks/AudioWorklet, with a synthetic input device. */
const {test}=require('node:test'),assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{chromium}=require('playwright');
test('real capture worklet emits bounded utterances and shares exclusive microphone ownership',{timeout:20000},async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'bot-realtime-capture-')),file=path.join(dir,'input.wav');
 const rate=48000,tone=Float32Array.from({length:rate},(_,i)=>.15*Math.sin(2*Math.PI*220*i/rate));
 const blob=require('../web/static/js/bot_realtime_audio.js').wav([tone,new Float32Array(rate*2)],rate);fs.writeFileSync(file,Buffer.from(await blob.arrayBuffer()));
 const server=http.createServer((req,res)=>{const name=new URL(req.url,'http://localhost').pathname.split('/').at(-1);if(['studio_audio_recorder.js','bot_realtime_audio.js','bot_realtime_processor.js'].includes(name)){res.setHeader('content-type','application/javascript');res.end(fs.readFileSync(path.join(__dirname,'../web/static/js',name)));}else{res.setHeader('content-type','text/html; charset=utf-8');res.end('<script src="/admin/static/js/studio_audio_recorder.js"></script><script src="/admin/static/js/bot_realtime_audio.js"></script><button id="start">Start fixture capture</button>');}});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));let browser;
 try{browser=await chromium.launch({headless:true,channel:'chrome',args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--use-file-for-fake-audio-capture='+file]});const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:'+server.address().port);
  await page.evaluate(()=>{window.events=[];window.control=new AbortController();document.querySelector('#start').onclick=async()=>{try{window.device=await AI2AppsBotRealtimeAudio.capture(e=>events.push({type:e.type,size:e.audio?.size,turn:e.turn}),control.signal);}catch(e){window.failure=e.message;}};});
  await page.click('#start');await page.waitForFunction(()=>events.some(e=>e.type==='final')||window.failure,{},{timeout:12000});
  assert.equal(await page.evaluate(()=>window.failure),undefined);
  const events=await page.evaluate(()=>events);assert.ok(events.some(e=>e.type==='start'));const final=events.find(e=>e.type==='final');assert.ok(final.size>44&&final.size<48000*4*2+44);
  const result=await page.evaluate(async()=>{const recorder=new AI2AppsStudioAudioRecorder();let locked=false;try{await recorder.start(.3);}catch(e){locked=e.message.includes('microphone_busy');}control.abort();await device.close();await recorder.start(.3);await recorder.result;const recorded=await recorder.stop();recorder.dispose();return {locked,recorded:recorded.body.size};});
  assert.equal(result.locked,true);assert.ok(result.recorded>0);assert.deepEqual(errors,[]);
 }finally{await browser?.close();await new Promise(r=>server.close(r));fs.rmSync(dir,{recursive:true,force:true});}
});
