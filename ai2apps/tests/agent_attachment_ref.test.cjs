const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const branch=source.slice(source.indexOf('            const assetIds = Array.isArray(step.arguments?.asset_ids)'),source.indexOf('            const target = await bidi.findTarget',source.indexOf('            const assetIds = Array.isArray(step.arguments?.asset_ids)')));
test('planner file-input ref survives execution when multiple upload controls exist',async()=>{
 const calls=[];const context={state:{attachments:[{asset_id:'asset-a'}]},attachmentIds:[],before:{},op:'input',step:{target:{ref:'e168',intent:'微博发布框图片附件'},arguments:{asset_ids:['asset-a']}},intent:s=>s.target.intent,api:async()=>({path:'/tmp/cover.png'}),bidi:{setAttachmentFiles:async(ref,paths)=>{calls.push({ref,paths});return ref==='e168'?{file_count:1}:null;},pageState:async()=>({})}};
 vm.runInNewContext('globalThis.run=async()=>{'+branch+'}',context);
 const result=await context.run();assert.equal(result.outcome,'success');assert.equal(calls[0].ref,'e168');assert.equal(calls[0].paths[0],'/tmp/cover.png');
});
