const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function fixture(){
 const mounted=[],responses=[],opened=[];
 function node(tag){return {tag,isConnected:true,classList:{add(){}},setAttribute(k,v){this[k]=v;},children:[],dataset:{},append(...items){this.children.push(...items);},replaceChildren(){this.children=[];},querySelectorAll(tag){const all=[];function visit(n){for(const c of n.children||[]){if(c.tag===tag)all.push(c);visit(c);}}visit(this);return all;}};}
 const window={dispatchEvent(){},AI2AppsParameterForms:{prompt:i=>i.prompt,mount:(...a)=>mounted.push(a),release:id=>mounted.push(['released',id])},ai2appsShell:{openHandoff:async(...a)=>opened.push(a)}};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/bot_interactions.js'),'utf8'),{window,CustomEvent:function(type,options){this.type=type;this.detail=options.detail;},document:{createElement:node,documentElement:{lang:'en'}}});
 const root=node('section'),options={root,run:{id:'original-run'},respond:async r=>responses.push(r),refresh(){},onError:e=>{throw e;},label:(zh,en)=>en};
 return {window,root,options,mounted,responses,opened};
}
test('approval offers explicit bounded grants and preserves original response route',async()=>{
 const f=fixture();const item={id:'original-interaction',kind:'approval',prompt:'Allow fixture output?',request:{tool_name:'arbitrary.create',arguments:{title:'fixture'}},response_schema:{properties:{scope:{enum:['once','run','session','agent','app']}}}};
 assert.equal(f.window.AI2AppsBotInteractions.render({...f.options,item}),true);
 const buttons=f.root.querySelectorAll('button');assert.deepEqual(buttons.map(b=>b.textContent),['Confirm this operation','Deny']);
 assert.equal(f.responses.length,0);await buttons[0].onclick();assert.equal(f.responses[0].decision,'approve');assert.equal(f.responses[0].scope,'once');
 await buttons.at(-1).onclick();assert.equal(f.responses[1].decision,'deny');
});
test('parameter form delegates full original interaction to shared renderer and releases it',()=>{
 const f=fixture(),item={id:'form-id',prompt:'Complete inputs',ui_hints:{control:'parameter_form'},request:{capability:'other.compose'}};
 f.window.AI2AppsBotInteractions.render({...f.options,item});assert.equal(f.mounted[0][1],f.options.run);assert.equal(f.mounted[0][2],item);assert.equal(f.responses.length,0);
 f.window.AI2AppsBotInteractions.release(f.root,item.id);assert.equal(f.mounted[1][1],item.id);assert.equal(f.root.children.length,0);
});
test('App handoff uses host-bound original run and interaction, never a model URL',async()=>{
 const f=fixture(),item={id:'handoff-id',prompt:'Continue',ui_hints:{control:'app_handoff'},request:{url:'https://untrusted.invalid'}};
 f.window.AI2AppsBotInteractions.render({...f.options,item});await f.root.querySelectorAll('button')[0].onclick();assert.deepEqual(f.opened,[['original-run','handoff-id',false]]);
});

test('Bot App card shows identity and a single explicit allow action without permission switches',async()=>{
 const f=fixture(),calls=[];
 const review={eligible:true,app:{name:'Fixture Studio',icon:'palette'},request_hash:'review'};
 const api=async(path,method,body)=>{calls.push({path,method,body});return method==='POST'?{continued:true}:review;};
 f.window.AI2AppsBotInteractions.render({...f.options,botId:'bot',api,item:{id:'interaction',kind:'approval',prompt:'Allow?',request:{}}});
 await new Promise(setImmediate);
 const inputs=f.root.querySelectorAll('input');assert.equal(inputs.length,0);
 assert.equal(f.root.querySelectorAll('h3')[0].textContent,'Fixture Studio');
 const button=f.root.querySelectorAll('button')[0];assert.equal(button.textContent,'Allow this bot access');assert.equal(calls.length,1);
 await button.onclick();assert.deepEqual({...calls[1].body},{request_hash:'review'});assert.equal(f.responses.length,0);
});

test('App grant never implicitly confirms a paid or special operation',async()=>{
 const f=fixture();
 f.window.AI2AppsBotInteractions.render({...f.options,botId:'bot',api:async(p,m)=>m==='POST'?{requires_confirmation:true}:{eligible:true,app:{name:'Paid Studio',icon:'palette'},request_hash:'review'},item:{id:'paid',kind:'approval',prompt:'Paid call',request:{effects:['billing']}}});
 await new Promise(setImmediate);await f.root.querySelectorAll('button')[0].onclick();
 assert.equal(f.responses.length,0);assert.equal(f.root.querySelectorAll('h4')[0].textContent,'Confirm this operation');
 assert.equal(f.root.querySelectorAll('button')[0].textContent,'Confirm this operation');
});

test('ordinary existing access keeps the Allow this bot card and stale lookup cannot repaint a released interaction',async()=>{
 const f=fixture();let resolve;const api=()=>new Promise(done=>resolve=done);const item={id:'stale',kind:'approval',prompt:'Allow?',request:{}};
 f.window.AI2AppsBotInteractions.render({...f.options,botId:'bot',api,item});f.window.AI2AppsBotInteractions.release(f.root,item.id);resolve({eligible:true,app:{name:'Late App',icon:'box'},request_hash:'x'});await new Promise(setImmediate);assert.equal(f.root.children.length,0);assert.equal(f.root.hidden,true);
 const g=fixture();g.window.AI2AppsBotInteractions.render({...g.options,botId:'bot',api:async()=>({eligible:true,access_granted:true,app:{name:'Ready Mini',kind:'mini-app',icon:'music'},request_hash:'x'}),item:{...item,id:'ordinary'}});await new Promise(setImmediate);assert.equal(g.root.querySelectorAll('button')[0].textContent,'Allow this bot access');assert.equal(g.root.querySelectorAll('input').length,0);
});

test('every Bot question keeps task and step context outside the parameter renderer',()=>{
 const f=fixture();f.options.run.task_context={task:'Panda artwork',step:'Add a hat',request:'Use the prior image'};
 const item={id:'context-form',kind:'form',prompt:'Choose the source image',ui_hints:{control:'parameter_form'}};
 assert.equal(f.window.AI2AppsBotInteractions.render({...f.options,item}),true);
 assert.ok(f.root.querySelectorAll('strong').some(n=>n.textContent==='Task: Panda artwork'));
 assert.ok(f.root.querySelectorAll('p').some(n=>n.textContent==='Current step: Add a hat'));
 assert.notEqual(f.mounted[0][0],f.root); // Form refresh cannot erase the explanation.
 assert.equal(f.mounted[0][1].id,'original-run');assert.equal(f.mounted[0][2].id,'context-form');
 f.window.AI2AppsBotInteractions.render({...f.options,item:{id:'plain-question',kind:'text',prompt:'Which deadline do you mean?',ui_hints:{control:'text'}}});
 assert.ok(f.root.querySelectorAll('strong').some(n=>n.textContent==='Task: Panda artwork'));
});

test('unresolved access offers cancellation, never a meaningless retry or grant',async()=>{
 const f=fixture();
 f.window.AI2AppsBotInteractions.render({...f.options,botId:'bot',api:async()=>({eligible:false,reason:'provider_ambiguous'}),item:{id:'unresolved',kind:'approval',prompt:'Allow?',request:{}}});
 await new Promise(setImmediate);
 assert.deepEqual(f.root.querySelectorAll('button').map(b=>b.textContent),['Cancel this operation']);
 assert.match(f.root.querySelectorAll('p').at(-1).textContent,/has not executed/);
 assert.equal(f.responses.length,0);await f.root.querySelectorAll('button')[0].onclick();assert.equal(f.responses[0].decision,'deny');
});
test('transient access lookup failure labels reload precisely without granting or retrying execution',async()=>{
 const f=fixture();let requests=0;f.options.onError=()=>{};
 f.window.AI2AppsBotInteractions.render({...f.options,botId:'bot',api:async()=>{requests++;throw Error('offline');},item:{id:'offline',kind:'approval',prompt:'Allow?',request:{}}});
 await new Promise(setImmediate);
 assert.deepEqual(f.root.querySelectorAll('button').map(b=>b.textContent),['Reload access information','Cancel this operation']);
 await f.root.querySelectorAll('button')[0].onclick();assert.equal(requests,2);assert.equal(f.responses.length,0);
});

test('collaboration budget shows explicit decisions for the original interaction',async()=>{
 const f=fixture(),item={id:'budget-id',kind:'menu',request:{collaboration_budget:true,used_tokens:65000,additional_tokens:64000},
  schema:{properties:{answer:{enum:['continue-token-budget','stop-token-budget']}}}};
 assert.equal(f.window.AI2AppsBotInteractions.render({...f.options,item}),true);
 assert.match(f.root.querySelectorAll('p')[0].textContent,/65,000.*64,000/);
 const buttons=f.root.querySelectorAll('button');
 assert.deepEqual(buttons.map(b=>b.textContent),['Continue collaboration','Finish and keep results']);
 assert.equal(f.responses.length,0);
 await buttons[0].onclick();
 assert.deepEqual({...f.responses[0]},{answer:'continue-token-budget'});
});
