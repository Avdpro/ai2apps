const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('plan changes present before/after and confirm the original reviewed identity',async()=>{
 function node(tag,text){return {tag,textContent:text,children:[],append(...v){this.children.push(...v);},replaceChildren(){this.children=[];}};}
 const root=node('section'),calls=[];const window={};const document={documentElement:{lang:'en'},createElement:node};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/bot_task_feed.js'),'utf8'),{window,document});
 const feed=window.AI2AppsBotTaskFeed.create({bot:{id:'bot'},root,api:async(...args)=>calls.push(args),refresh:async()=>{},onError:e=>{throw e;},label:(zh,en)=>en});
 const schedule={frequency:'daily',hour:0,minute:0,timezone:'Asia/Shanghai'};
 feed.update({proposals:[],interactions:[],plan_changes:[{id:'change-original',review_hash:'review-original',next_due:'2026-11-08T22:00:00Z',before:{title:'Cleanup at midnight',description:'old rule',schedule},value:{title:'Cleanup at six',prompt:'old rule and new rule',schedule:{...schedule,hour:6}}}]});
 const card=root.children[0],text=card.children.map(n=>n.textContent).join(' ');
 assert.match(text,/Previous instructions: old rule/);assert.match(text,/Revised instructions: old rule and new rule/);assert.match(text,/Runs already started or queued keep the prior rules/);
 assert.match(text,/Review changes to the existing plan: Cleanup at midnight/);assert.match(text,/Revised title: Cleanup at six/);
 assert.match(text,/Next execution · Nov 9, 2026.*6:00\s*AM · Asia\/Shanghai/);
 const buttons=card.children.filter(n=>n.tag==='button');assert.deepEqual(buttons.map(n=>n.textContent),['Confirm plan update','Keep existing plan']);
 await buttons[0].onclick();assert.equal(calls[0][0],'/messager/bots/bot/plan-changes/change-original/approve');assert.equal(calls[0][2].review_hash,'review-original');
 await buttons[1].onclick();assert.equal(calls[1][0],'/messager/bots/bot/plan-changes/change-original/reject');feed.dispose();
});
test('plan Access review defaults fixed, locks required targets and posts explicit selection',async()=>{
 function node(tag,text){return {tag,textContent:text,children:[],dataset:{},append(...v){this.children.push(...v);if(tag==='select'&&!this.value)this.value=v[0].value;},replaceChildren(){this.children=[];}};}
 const root=node('section'),calls=[],window={},document={documentElement:{lang:'en'},createElement:node};
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/bot_task_feed.js'),'utf8'),{window,document});
 const feed=window.AI2AppsBotTaskFeed.create({bot:{id:'bot'},root,api:async(...v)=>calls.push(v),refresh:async()=>{},onError:e=>{throw e;},label:(z,e)=>e});
 const work={interactions:[],proposals:[{id:'proposal',review_hash:'hash',access:[],proposal:{title:'Future fixture',prompt:'Work',model:'fixture',schedule:{frequency:'off'},access_preflight:{apps:[{app_id:'one',name:'One',kind:'app',required:true,predicted:true,reasons:['Required work']},{app_id:'two',name:'Two',kind:'mini-app',required:false,predicted:false,reasons:[]}]}}}]};feed.update(work);
 function walk(n){return [n,...n.children.flatMap(walk)];}const all=walk(root),mode=all.find(n=>n.tag==='select'),inputs=all.filter(n=>n.tag==='input');
 assert.equal(mode.value,'fixed');assert.equal(inputs[0].checked,true);assert.equal(inputs[0].disabled,true);assert.equal(inputs[1].checked,false);
 mode.value='auto';mode.onchange();inputs[1].checked=true;inputs[1].onchange();feed.update({...work,refresh_marker:1});assert.equal(walk(root).find(n=>n.tag==='select').value,'auto');assert.equal(walk(root).filter(n=>n.tag==='input')[1].checked,true);await walk(root).find(n=>n.tag==='button'&&n.textContent==='Confirm and start').onclick();
 assert.equal(calls[0][2].access_mode,'auto');assert.deepEqual(Array.from(calls[0][2].access_apps),['one','two']);assert.equal(calls[0][2].review_hash,'hash');feed.dispose();
});

test('approved task authority alone leaves the conversation feed empty',()=>{
 function node(tag){return {tag,children:[],append(...v){this.children.push(...v);},replaceChildren(){this.children=[];}};}
 const window={},document={createElement:node},root=node('div');
 vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/bot_task_feed.js'),'utf8'),{window,document});
 const feed=window.AI2AppsBotTaskFeed.create({bot:{id:'bot'},root,api:async()=>{throw Error('No action expected');},refresh:async()=>{},onError:e=>{throw e;},label:(z,e)=>e});
 feed.update({proposals:[],interactions:[],access_policies:[{id:'old',status:'approved',title:'Retained plan',targets:[],mode:'fixed'}]});
 assert.equal(root.children.length,0);feed.dispose();
});
