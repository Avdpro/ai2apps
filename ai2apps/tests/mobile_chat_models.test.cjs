const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/mobile_chat.js'),'utf8');
const loader = source.slice(source.indexOf('    async function loadModels()'),source.indexOf('    async function loadAgents()'));
test('mixed capability formats exclude non-chat declarations and require explicit selection',async()=>{
    const model = {innerHTML:''};
    const fixture = [
        {id:'chat-array',capabilities:['conversation']},
        {id:'cloud-text',capabilities:{text:true}},
        {id:'cloud-image',model_type:'llm',capabilities:{text:false,imageGeneration:true}},
        {id:'tts',capabilities:['audio_generation']},
        {id:'typed-tts',model_type:'audio_tts',capabilities:{text:true}},
        {id:'typed-stt',model_type:'audio_stt',capabilities:['conversation']},
        {id:'typed-embedding',model_type:'embedding',capabilities:['conversation']},
        {id:'hidden-chat',model_type:'llm',is_hidden:true},
        {id:'legacy-chat',model_type:'llm'},
    ];
    const context=vm.createContext({apiDefaultModel:"",model,request:async()=>({data:fixture}),escapeHtml:x=>x,notify:message=>assert.fail(message)});
    await vm.runInContext(loader+'\nloadModels()',context);
    assert.match(model.innerHTML,/value="" selected/);
    for(const id of ['chat-array','cloud-text','legacy-chat']) assert.ok(model.innerHTML.includes('value="'+id+'"'));
    for(const id of ['cloud-image','tts','typed-tts','typed-stt','typed-embedding','hidden-chat']) assert.ok(!model.innerHTML.includes('value="'+id+'"'));
});
const selection = source.slice(source.indexOf('    function chooseModel('),source.indexOf('    async function loadContent('));
test('conversation model, inherited model, then API Default; unavailable models are skipped',()=>{
    const context=vm.createContext({model:{options:[{value:''},{value:'saved'},{value:'inherited'},{value:'cloud/default'}]},apiDefaultModel:'cloud/default'});
    vm.runInContext(selection,context);
    assert.equal(context.chooseModel('saved','inherited'),'saved');
    assert.equal(context.chooseModel('','inherited'),'inherited');
    assert.equal(context.chooseModel('removed','inherited'),'inherited');
    assert.equal(context.chooseModel('removed',''),'cloud/default');
    assert.equal(context.chooseModel('',''),'cloud/default');
    context.apiDefaultModel='unavailable';
    assert.equal(context.chooseModel('',''),'');
});
test('opening a conversation restores its saved model instead of the previous conversation',async()=>{
    const load = source.slice(source.indexOf('    async function loadContent('),source.indexOf('    async function refreshThreads('));
    const context=vm.createContext({model:{options:[{value:'saved'},{value:'cloud/default'}],value:'previous'},apiDefaultModel:'cloud/default',lastActiveModel:'previous',threadModels:new Map(),busy:false,
        title:{},drawer:{classList:{remove(){}},setAttribute(){}},renderThreads(){},working(){},idle(){},renderMessages(){},
        request:async()=>({thread:{id:'one'},session_metadata:{mobile_model_id:'saved'}})});
    vm.runInContext(selection+load,context);
    await context.loadContent({id:'one'});
    assert.equal(context.model.value,'saved');
    assert.equal(context.lastActiveModel,'saved');
    context.request=async()=>({thread:{id:'two'},session_metadata:{mobile_model_id:'unavailable'}});
    await context.loadContent({id:'two'});
    assert.equal(context.model.value,'cloud/default');
});
test('managed fusion and work-only LLM remain selectable with favorites and default alias',async()=>{
 const model={innerHTML:''};
 const context=vm.createContext({apiDefaultModel:'cloud/ai2apps/default',model,request:async()=>({data:[
 {id:'fusion/team',source_type:'fusion',display_name:'Team'},
 {id:'llm',model_type:'llm',capabilities:['work'],display_name:'Local',is_favorite:true},
 {id:'cloud/default',model_type:'llm',display_name:'Default'},
 {id:'bad',model_type:'llm',checkpoint_ready:false},
 ]}),escapeHtml:x=>x,notify:message=>assert.fail(message)});
 await vm.runInContext(loader+'\nloadModels()',context);
 for(const id of ['fusion/team','llm','cloud/ai2apps/default']) assert.ok(model.innerHTML.includes('value="'+id+'"'));
 assert.ok(!model.innerHTML.includes('value="bad"'));
 assert.ok(model.innerHTML.indexOf('value="llm"')<model.innerHTML.indexOf('value="fusion/team"'));
});
