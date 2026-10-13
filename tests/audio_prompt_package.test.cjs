const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const context={window:{}};vm.runInNewContext(fs.readFileSync('packages/ai2apps-audio-generation-suite/web/prompt.js','utf8'),context);
(async()=>{
let request;const call=async(op,data)=>{request={op,data};return {text:'{"prompt":"Solo piano"}'}};
assert.equal(await context.window.AudioPrompt.prepare(call,'钢琴','privacy'),'Solo piano');
assert.equal(request.op,'llm.complete');assert.equal(request.data.payload.profile,'privacy');assert.equal(request.data.payload.complexity,'simple');
for(const text of ['not json','{}','{"prompt":""}',JSON.stringify({prompt:'x'.repeat(2001)})])await assert.rejects(()=>context.window.AudioPrompt.prepare(async()=>({text}),'text'));
await assert.rejects(()=>context.window.AudioPrompt.prepare(async()=>{throw Error('offline')},'text'));
console.log('Package prompt translation: routing, validation and failure propagation passed');
})();
