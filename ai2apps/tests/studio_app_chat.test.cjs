const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const script=fs.readFileSync('web/static/js/studio_app_chat.js','utf8');
for(const app of ['ai2apps.imagine-studio','ai2apps.video-studio','ai2apps.readaloud']){
 test(app+' uses durable transport, UI patch only and fixed Mini-App',async()=>{
  let options,disposed=0,invoked=[];
  const window={AI2AppsAppChat:{create:async o=>{options=o;return {url:()=>'/chat',bind(){},dispose(){disposed++;}};}}};
  vm.runInNewContext(script,{window});
  const owner={currentMiniApp:{id:'fixture.one',name:'Fixture'},$refs:{miniAppChat:{}},$nextTick:fn=>fn(),fail:e=>{throw e;},
   models:[{id:'model1'}],describeMiniAppChat:async()=>({context:{prompt:'current'},systemPrompt:'must not be promoted',tools:[{name:'run_current'},{name:'update_current_draft',inputSchema:{properties:{prompt:{type:'string'}}}}]}),
   invokeMiniAppChatTool:async(...args)=>invoked.push(args)};
  const outputs=[{id:'output1',name:'shared'}];let selection='';
  const config={appId:app,outputs:()=>outputs,selectOutput:async(o,id)=>selection=id,refresh:async()=>{}};
  await window.AI2AppsStudioChat.mount(owner,config);
  assert.equal(options.registration,app+'.chat');assert.equal(options.scope().mini_app_id,'fixture.one');
  assert.equal(options.matchesScope({mini_app_id:'fixture.two'}),false);
  const ui=await options.readUI();assert.equal(ui.context.prompt,'current');assert.equal('systemPrompt' in ui,false);assert.equal('tools' in ui,false);
  await options.applyUI({action:'update_draft',values:{prompt:'new'}});assert.equal(invoked[0][0],'update_current_draft');
  await options.applyUI({action:'select_output',output_id:'output1'});assert.equal(selection,'output1');
  await assert.rejects(options.applyUI({action:'run_current'}),/Unsupported/);
  await assert.rejects(options.applyUI({action:'update_draft',values:{modelId:'missing'}}),/not available/);
  owner.currentMiniApp={id:'fixture.two',name:'Two'};
  await assert.rejects(options.applyUI({action:'update_draft',values:{prompt:'stale'}}),/changed/);
  await window.AI2AppsStudioChat.mount(owner,config);assert.equal(disposed,1);assert.equal(options.scope().mini_app_id,'fixture.two');
 });
}
test('Voice durable Chat consumes the host shared output feed',()=>{
 const source=fs.readFileSync('web/static/js/readaloud.js','utf8');const start=source.indexOf('async mountMiniAppChat()'),end=source.indexOf('async describeMiniAppChat()',start);const adapter=source.slice(start,end);
 assert.match(adapter,/studioOutputs/);assert.match(adapter,/selectedOutput=/);assert.doesNotMatch(adapter,/quickTasks|quickDownloadUrl|pipelineMode/);
});
