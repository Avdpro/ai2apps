const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function imagine(){
 const ctx={window:{ImagineAdjustEngine:{clone:structuredClone}},document:{documentElement:{lang:'en'}},structuredClone,console,FormData,Blob};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('ai2apps/web/static/js/imagine_studio.js','utf8'),ctx);
 return {ctx,a:ctx.window.imagineStudioApp()};
}
test('Mobile batch freezes files and settings without requiring native paths',async()=>{
 const {a}=imagine();a.clientEnvironment='mobile';a.adjustmentBatchSource='files';a.adjustmentBatchOutputMode='save-as';
 a.adjustmentBatchFiles=[new Blob(['one'],{type:'image/png'}),new Blob(['two'],{type:'image/png'})];a.adjustmentBatchFiles.forEach((f,i)=>f.name=i+'.png');
 a.adjustState={rotation:90};a.$refs={};a.dismissNotice=()=>{};a.icons=()=>{};a.fail=e=>{throw e};
 let submission;a.submitAdjustment=async(items,state)=>{submission={items,state};a.miniAppId='another';};
 await a.runAdjustmentBatch();assert.equal(submission.items.length,2);assert.equal(submission.items[0].target,null);
 assert.notEqual(submission.state,a.adjustState);assert.equal(submission.state.rotation,90);assert.equal(a.adjustmentBatchBusy,false);assert.equal(a.adjustmentBatchOpen,false);
});
test('Adjustment submission returns on acceptance and uploads original file, no canvas required',async()=>{
 const {a,ctx}=imagine();let form;
 ctx.fetch=async(url,options)=>{assert.match(url,/runs\/r1\/adjust$/);form=options.body;return {ok:true,json:async()=>({id:'r1',status:'queued'})}};
 a.saveDraft=async()=>{};a.draftPayload=()=>({miniAppId:'adjust'});a.createRun=async()=>({id:'r1'});a.runs=[];a.selectRun=()=>{};
 a.historyHeaders=()=>({});a.refreshRuns=async()=>{};let opened=false;a.openMobileOutput=()=>opened=true;
 const file=new Blob(['original'],{type:'image/png'});file.name='input.png';
 await a.submitAdjustment([{file,name:'result.png',mediaType:'image/png'}],{rotation:90});
 assert.equal(await form.get('files').text(),'original');assert.equal(JSON.parse(form.get('spec')).state.rotation,90);assert.equal(opened,true);
});
