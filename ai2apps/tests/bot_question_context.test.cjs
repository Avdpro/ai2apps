const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('scheduled Bot parameter questions retain purpose and the original interaction target',()=>{
 function node(tag){return {tag,children:[],dataset:{},append(...v){this.children.push(...v);},replaceChildren(){this.children=[];}};}
 const mounted=[],released=[],window={AI2AppsParameterForms:{mount(...args){mounted.push(args);},release(id){released.push(id);}}},root=node('section');
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/bot_task_feed.js'),'utf8'),{window,document:{documentElement:{lang:'en'},createElement:node}});
 const feed=window.AI2AppsBotTaskFeed.create({bot:{id:'bot'},root,api:()=>assert.fail('no decision on render'),refresh(){},onError:e=>{throw e;},label:(a,b)=>b});
 feed.update({proposals:[],interactions:[{id:'original-form',run_id:'original-background-run',todo_run_id:'original-todo-run',title:'Prepare a report',task_request:'Summarize saved articles',kind:'form',control:'parameter_form',prompt:'Choose the report period',ui_hints:{control:'parameter_form'}}]});
 const text=root.children[0].children.map(n=>n.textContent).join(' ');assert.match(text,/Summarize saved articles/);assert.match(text,/Choose the report period/);
 assert.equal(mounted[0][1].id,'original-background-run');assert.equal(mounted[0][2].id,'original-form');
 feed.update({proposals:[],interactions:[]});assert.deepEqual(released,['original-form']);feed.dispose();
});

test('consultation card requires an explicit origin-conversation decision and never submits on render',async()=>{
 function node(tag){return {tag,children:[],dataset:{},append(...v){this.children.push(...v);},replaceChildren(){this.children=[];}};}
 const root=node('section'),calls=[];
 const window={};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/bot_task_feed.js'),'utf8'),{window,document:{documentElement:{lang:'en'},createElement:node}});
 const feed=window.AI2AppsBotTaskFeed.create({bot:{id:'origin-bot'},root,api:async(...args)=>calls.push(args),refresh(){},onError:e=>{throw e;},label:(a,b)=>b});
 const request={id:'original-request',status:'pending',target_name:'Reviewer',question:'Choose A or B',model:'reviewed-model',review_hash:'exact-review'};
 feed.update({proposals:[],interactions:[],communications:[request]});assert.equal(calls.length,0);
 const card=root.children[0],text=card.children.map(n=>n.textContent).join(' ');assert.match(text,/Reviewer/);assert.match(text,/Choose A or B/);assert.match(text,/No history, memory or App access is shared/);
 const buttons=card.children.filter(n=>n.tag==='button');assert.deepEqual(buttons.map(b=>b.textContent),['Allow Bot access','Do not send']);
 await buttons[0].onclick();assert.equal(calls[0][0],'/messager/bots/origin-bot/communication/original-request/decisions/approve');assert.equal(calls[0][2].review_hash,'exact-review');
 feed.update({proposals:[],interactions:[],communications:[{...request,status:'queued'}]});await root.children[0].children.find(n=>n.tag==='button').onclick();assert.match(calls[1][0],/original-request\/cancel$/);
});

test('delegation approval is available only at its origin and preserves its reviewed identity',async()=>{
 function node(tag){return {tag,children:[],dataset:{},append(...v){this.children.push(...v);},replaceChildren(){this.children=[];}};}
 const root=node('section'),calls=[],window={};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/bot_task_feed.js'),'utf8'),{window,document:{documentElement:{lang:'en'},createElement:node}});
 const feed=window.AI2AppsBotTaskFeed.create({bot:{id:'origin'},root,api:async(...a)=>calls.push(a),refresh(){},onError:e=>{throw e;},label:(a,b)=>b});
 const d={id:'original-delegation',source_bot:'origin',target_name:'Specialist',status:'pending',title:'Make a cover',instructions:'Use supplied facts',model:'reviewed-model',access:[{capability:'arbitrary.create',access:'write'}],review_hash:'bound-hash'};
 feed.update({proposals:[],interactions:[],delegations:[d]});assert.equal(calls.length,0);
 const buttons=root.children[0].children.filter(n=>n.tag==='button');assert.equal(buttons[0].textContent,'Allow Bot access');await buttons[0].onclick();assert.equal(calls[0][0],'/messager/bots/origin/delegations/original-delegation/decisions/approve');assert.equal(calls[0][2].review_hash,'bound-hash');
 feed.update({proposals:[],interactions:[],delegations:[{...d,source_bot:'different-origin'}]});assert.equal(root.children[0].children.filter(n=>n.tag==='button').length,1);
});

test('nested delegation is reviewed at the first Bot and shows its shared bounds',async()=>{
 function node(tag){return {tag,children:[],dataset:{},append(...v){this.children.push(...v);},replaceChildren(){this.children=[];}};}
 const root=node('section'),calls=[],window={};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/bot_task_feed.js'),'utf8'),{window,document:{documentElement:{lang:'en'},createElement:node}});
 const feed=window.AI2AppsBotTaskFeed.create({bot:{id:'first'},root,api:async(...a)=>calls.push(a),refresh(){},onError:e=>{throw e;},label:(a,b)=>b});
 const request={id:'nested-edge',source_bot:'middle',review_bot:'first',target_name:'Leaf',status:'pending',title:'Review result',instructions:'Bounded leaf work',model:'fixture',review_hash:'nested-hash',access:[],graph:{depth:2},allow_subdelegation:false,graph_policy:{max_model_tokens:128000,max_tool_calls:36,timeout_seconds:600,max_edges:8,max_depth:3}};
 feed.update({proposals:[],interactions:[],delegations:[request]});assert.equal(calls.length,0);
 const text=root.children[0].children.map(n=>n.textContent).join(' ');assert.match(text,/128000 model tokens/);assert.match(text,/36 Tool calls/);assert.match(text,/10 minutes/);assert.match(text,/cannot delegate further/);
 await root.children[0].children.find(n=>n.textContent==='Allow Bot access').onclick();
 assert.equal(calls[0][0],'/messager/bots/first/delegations/nested-edge/decisions/approve');assert.equal(calls[0][2].review_hash,'nested-hash');
});

test('reentrant task review explains independent work and the expected deliverable',()=>{
 function node(tag){return {tag,children:[],dataset:{},append(...v){this.children.push(...v);},replaceChildren(){this.children=[];}};}
 const root=node('section'),window={};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/bot_task_feed.js'),'utf8'),{window,document:{documentElement:{lang:'en'},createElement:node}});
 const feed=window.AI2AppsBotTaskFeed.create({bot:{id:'researcher'},root,api:()=>assert.fail('no automatic review'),refresh(){},onError:e=>{throw e;},label:(a,b)=>b});
 feed.update({proposals:[],interactions:[],delegations:[{id:'subtopic',source_bot:'researcher',review_bot:'researcher',target_bot:'researcher',target_name:'Researcher',title:'Subtopic',instructions:'Inspect the narrower source set',deliverable:'Evidence table',model:'fixture',status:'pending',access:[],task_dependency:{source_task:'main',target_task:'subtopic'}}]});
 const text=root.children[0].children.map(n=>n.textContent).join(' ');assert.match(text,/Expected deliverable: Evidence table/);assert.match(text,/independent child task/);assert.match(text,/same Bot may handle different tasks/);
});
