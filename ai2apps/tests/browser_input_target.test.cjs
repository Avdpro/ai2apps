const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');
const method=source.slice(source.indexOf('        async findTarget('),source.indexOf('        async naturalPointer('));
function node(tag,name){return {tagName:tag.toUpperCase(),type:tag==='textarea'?'textarea':'',name:'',id:'',autocomplete:'',innerText:name,
 getBoundingClientRect:()=>({width:100,height:30,x:1,y:1}),getAttribute:()=>null,
 matches:selector=>selector==='input[type=password]'?false:tag==='textarea'};}
test('input target skips search links and buttons',async()=>{
 const nodes=[node('a','Search'),node('button','Google Search'),node('textarea','Search')];
 const context={document:{querySelectorAll:()=>nodes},getComputedStyle:()=>({visibility:'visible',display:'block',opacity:'1'})};
 vm.runInNewContext('globalThis.Target=class{'+method+'}',context);
 const client=new context.Target();client.snapshot=async()=>({items:nodes.map((item,index)=>({ref:'e'+index,tag:item.tagName.toLowerCase(),text:item.innerText,editable:item.tagName==='TEXTAREA',rect:[1,1,100,30]}))});
 assert.equal((await client.findTarget('Search',{operation:'input'})).tag,'textarea');
 assert.equal((await client.findTarget('Search',{operation:'click'})).tag,'a');
});
test('search input replaces prior text and submits with native BiDi Enter',async()=>{
 const method=source.slice(source.indexOf('        async typeText('),source.indexOf('        async scroll('));
 const context={navigator:{platform:'MacIntel'}};
 vm.runInNewContext('globalThis.Keyboard=class{'+method+'}',context);
 const client=new context.Keyboard();client.interactionSettings=async()=>({interaction_mode:'natural'});client.interactionPause=async()=>{};const calls=[];
 client.contextId='bound-tab';client.connection={command:async(method,params)=>calls.push({method,params})};
 await client.typeText('新关键词',{replace:true,submit:true});
 assert.equal(calls[0].method,'input.performActions');assert.equal(calls[0].params.context,'bound-tab');
 const actions=calls[0].params.actions[0].actions;
 assert.equal(actions[0].value,'\uE03D');assert.equal(actions[1].value,'a');
 assert.equal(actions.at(-2).value,'\uE007');assert.equal(actions.at(-1).type,'keyUp');
});
test('Enter-only search submission preserves existing query text',async()=>{
 const method=source.slice(source.indexOf('        async typeText('),source.indexOf('        async scroll('));
 const context={navigator:{platform:'MacIntel'}};
 vm.runInNewContext('globalThis.Keyboard=class{'+method+'}',context);
 const client=new context.Keyboard();client.interactionSettings=async()=>({interaction_mode:'natural'});client.interactionPause=async()=>{};let params;
 client.contextId='bound-tab';client.connection={command:async(_,p)=>params=p};
 await client.typeText('',{submit:true});
 assert.equal(params.actions[0].actions.length,2);
 assert.equal(params.actions[0].actions[0].value,'\uE007');
});
test('Agent executes an Enter-only search step without requiring an input value',async()=>{
 const agent=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
 const calls=[];
 const bidi={relatedWindowObservations:async()=>[],pageState:async()=>({url:'https://www.google.com/search?q=existing'}),findTarget:async()=>({tag:'textarea'}),naturalPointer:async()=>{},typeText:async(value,options)=>calls.push({value,options})};
 const context={URL,currentCapability:()=>null,state:{exploration:{goal:'用Google搜索'},draft:null,loginHandoffs:new Map()},client:async()=>bidi,scopeAllows:()=>true,intent:s=>s.target.intent,interactionPolicy:()=>null,inputValue:()=>''};
 const code=agent.slice(agent.indexOf('    function requestedSearchInteraction('),agent.indexOf('    function explorationActionNeedsConfirmation('))+agent.slice(agent.indexOf('    async function execute('),agent.indexOf('    async function saveEvidence('));
 vm.runInNewContext(code+'\nglobalThis.executeStep=execute;',context);
 const result=await context.executeStep({operation:'input',description:'在搜索框按回车提交搜索',target:{intent:'Search box'},arguments:{}});
 assert.equal(result.outcome,'success');assert.equal(calls[0].value,'');assert.equal(calls[0].options.submit,true);assert.equal(calls[0].options.replace,false);
});
