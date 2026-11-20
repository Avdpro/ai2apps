const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const policy=require('../web/static/js/conversation_model_policy.js');
async function resolve({data=[],managed=[],defaults={},apiDefault=null,saved}={}){
 const responses={'/v1/models':{data},'/admin/api/models':{models:managed},'/admin/api/model-manager':{defaults},'/v1/platform/cloud/ai/defaults':{policy:{apiDefault}}};
 const window={AI2AppsConversationModelPolicy:policy};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/bot_model_selection.js','utf8'),{window,document:{documentElement:{lang:'en'}},fetch:async url=>({ok:true,json:async()=>responses[url]})});
 return window.AI2AppsBotModelSelection.resolve(saved);
}
const llm=id=>({id,model_type:'llm',capabilities:['work_standard','tool_calling_reliable']});
test('new Bot inherits Agent default rather than Chat or standard default',async()=>{
 const v=await resolve({data:[llm('chat'),llm('standard'),llm('agent')],defaults:{work_chat:'chat',work_standard:'standard',work_agent:'agent'}});
 assert.equal(v.selected,'agent');
});
test('Bot choices exclude speech, image, video, embedding, helpers and unavailable sources',async()=>{
 const data=[llm('chat'),{id:'vision',model_type:'vlm'},{id:'untyped-image',capabilities:['image_generation']},...['audio_stt','audio_tts','image_generation','video_generation','embedding','reranker'].map(model_type=>({id:model_type,model_type})),{...llm('hidden'),is_hidden:true},{...llm('helper'),is_helper:true},{...llm('missing'),checkpoint_ready:false},{...llm('failed'),load_failed:true},{...llm('cache'),source_type:'hf_cache'}];
 const v=await resolve({data,defaults:{work_agent:'chat'}});assert.deepEqual(Array.from(v.models,m=>m.id),['chat','vision']);assert.ok(v.allModels.some(m=>m.id==='audio_stt'));
});
test('explicit valid Bot choice is preserved; stale non-chat choice returns to Agent default',async()=>{
 const options={data:[llm('agent'),{id:'explicit',model_type:'llm'},{id:'stt',model_type:'audio_stt'}],defaults:{work_agent:'agent'}};
 assert.equal((await resolve({...options,saved:'explicit'})).selected,'explicit');
 assert.equal((await resolve({...options,saved:'stt'})).selected,'agent');
});
test('gateway aliases deduplicate and managed declarations/defaults resolve to stable IDs',async()=>{
 const v=await resolve({data:[{id:'alias'},llm('real')],managed:[{...llm('real'),settings:{model_alias:'alias'},display_name:'Agent display name'}],defaults:{work_agent:'alias'}});
 assert.equal(v.models.length,1);assert.equal(v.models[0].id,'real');assert.equal(v.models[0].name,'Agent display name');assert.equal(v.selected,'real');
});
test('account API default uses Points route, never generic provider or random first model',async()=>{
 const v=await resolve({data:[{id:'cloud/provider-model',model_type:'llm'},llm('other')],apiDefault:{modelId:'provider-model',displayName:'Default provider model'}});
 assert.equal(v.selected,'cloud/ai2apps/provider-model');
 const missing=await resolve({data:[{id:'unqualified',model_type:'llm'}],apiDefault:{modelId:'unavailable'}});assert.equal(missing.selected,'');assert.match(missing.notice,/unavailable/);
});

test('install entry requests the shared conversation ACPF in configure-only mode',async()=>{
 const calls=[],window={AI2AppsCapabilities:{async ensure(request,options){calls.push({request,options});return {status:'ready',session:{id:'setup'}};},async acknowledge(session,owner){calls.push({session,owner});}}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/bot_model_selection.js','utf8'),{window,document:{documentElement:{lang:'en'}},crypto:{randomUUID:()=> 'resume'}});
 await window.AI2AppsBotModelSelection.install();
 assert.equal(calls[0].request.appId,'ai2apps.messager');assert.equal(calls[0].request.capability,'text.chat.local');
 assert.deepEqual(Array.from(calls[0].request.requirements.operations),['conversation']);
 assert.equal(calls[0].request.intent.completionPolicy,'configure_only');
 assert.equal(calls[0].request.intent.returnTo,'/apps/ai2apps.messager');
 assert.equal(calls[0].options.installMore,true);assert.equal(calls[1].owner.appId,'ai2apps.messager');
});
test('cancelled model setup is not acknowledged and restores the selected model immediately',async()=>{
 const window={AI2AppsCapabilities:{ensure:async()=>({status:'cancelled'}),acknowledge(){throw Error('Cancelled session acknowledged');}}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/bot_model_selection.js','utf8'),{window,document:{documentElement:{lang:'en'}},crypto:{randomUUID:()=> 'resume'}});
 assert.equal((await window.AI2AppsBotModelSelection.install()).status,'cancelled');
 const ui={window:{},document:{documentElement:{lang:'en'}},navigator:{language:'en'}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),ui);
 const app=ui.window.messagerApp();let installs=0;app.botAppliedModel='chosen';app.botModel='__install_more__';app.installBotModel=()=>installs++;
 const select={value:'__install_more__'};app.selectBotModel(select);
 assert.equal(app.botModel,'chosen');assert.equal(select.value,'chosen');assert.equal(installs,1);
});
test('Desktop profile persists browser-only choice and server profile wins on another client',async()=>{
 let stored={model_id:null,effective_model:'agent',revision:0};const writes=[];
 const window={AI2AppsConversationModelPolicy:policy};
 const catalog={'/v1/models':{data:[llm('agent'),llm('chosen')]},'/admin/api/models':{models:[]},'/admin/api/model-manager':{defaults:{work_agent:'agent'}},'/v1/platform/cloud/ai/defaults':{}};
 const fetch=async(url,options={})=>{let value;if(url.endsWith('/conversation-model')){if(options.method==='PUT'){const body=JSON.parse(options.body);assert.equal(body.revision,stored.revision);writes.push(body);stored={model_id:body.model_id,effective_model:body.model_id,revision:stored.revision+1};}value={...stored};}else value=catalog[url];return {ok:true,json:async()=>value};};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/bot_model_selection.js','utf8'),{window,document:{documentElement:{lang:'en'}},fetch});
 const first=await window.AI2AppsBotModelSelection.forBot('bot','chosen');assert.equal(first.selected,'chosen');assert.equal(writes.length,1);assert.equal(first.profileRevision,1);
 const phoneChoice=await window.AI2AppsBotModelSelection.save('bot','agent',1);assert.equal(phoneChoice.revision,2);
 const other=await window.AI2AppsBotModelSelection.forBot('bot','chosen');assert.equal(other.selected,'agent');assert.equal(writes.length,2);
});
