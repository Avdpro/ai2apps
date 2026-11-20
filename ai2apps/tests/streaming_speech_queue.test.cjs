const {test}=require('node:test'),assert=require('node:assert/strict');
const {StreamingTextSegmenter,playSegments}=require('../web/static/js/streaming_tts.js');
const flush=()=>new Promise(r=>setImmediate(r));
test('first short segment plays before remaining synthesis finishes; prefetch is bounded and ordered',async()=>{
 const segmenter=new StreamingTextSegmenter({minChars:8,softChars:24,maxChars:56}),segments=[...segmenter.append('这是一段较长的消息，需要尽早开始朗读。'.repeat(20)),...segmenter.finish()];assert.ok(segments.length>3);
 const generated=[],played=[];let release;
 const task=playSegments({segments,synthesize:async text=>{generated.push(text);return text;},play:async text=>{played.push(text);await new Promise(r=>release=r);},maxPrepared:2});
 await flush();assert.equal(played.length,1);assert.ok(generated.length<segments.length);assert.ok(generated.length<=4);
 while(played.length<segments.length){release();await flush();}release();await task;assert.deepEqual(played,segments);
});
test('stop releases capacity waiters without synthesizing queued text',async()=>{const controller=new AbortController();let synthesized=0,release;const task=playSegments({segments:Array(20).fill('text'),signal:controller.signal,synthesize:async()=>++synthesized,play:async()=>new Promise(r=>release=r)});await flush();controller.abort();release();await assert.rejects(task,{name:'AbortError'});const count=synthesized;await flush();assert.equal(synthesized,count);assert.ok(count<=4);});
test('synthesis failure propagates once and does not wait for missing playback',async()=>{await assert.rejects(playSegments({segments:['one'],synthesize:async()=>{throw Error('failed')},play:async()=>{throw Error('must not play')}}),/failed/);});
