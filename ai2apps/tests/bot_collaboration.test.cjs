const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
function fixture(){function node(tag,text){return {tag,textContent:text,children:[],dataset:{},append(...x){this.children.push(...x)},replaceChildren(){this.children=[]}};}const root=node('section'),window={},calls=[];vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/static/js/bot_task_feed.js'),'utf8'),{window,document:{documentElement:{lang:'en'},createElement:node}});return {root,calls,feed:window.AI2AppsBotTaskFeed.create({bot:{id:'origin'},root,api:async(...x)=>calls.push(x),refresh:async()=>{},onError:e=>{throw e},label:(zh,en)=>en})};}
function value(status='pending'){return {proposals:[],interactions:[],collaboration_plans:[{id:'exact-plan',status,review_hash:'exact-review',expires:1800000000,value:{title:'Reviews',participants:[{bot_id:'specialist',instructions:'Review supplied facts',allowed:{'fixture.provider':'1'}}],identities:{specialist:{name:'Reviewer'}},trigger:'event',event:{event_type:'arbitrary.record.finished',subjects:['record'],filters:[]},model:'fixture',aggregation:'allow_partial',replaces_plan_id:'old-plan'}}]};}
test('collaboration review names participants and trigger, and sends only the original review',async()=>{const {root,calls,feed}=fixture();feed.update(value());assert.equal(calls.length,0);const card=root.children[0],text=JSON.stringify(card);assert.match(text,/Reviewer/);assert.match(text,/arbitrary.record.finished/);assert.match(text,/admitted batches keep their original rules/);assert.match(text,/partial results/);const buttons=card.children.filter(x=>x.tag==='button');assert.deepEqual(buttons.map(x=>x.textContent),['Allow collaboration plan','Dismiss']);await buttons[0].onclick();assert.equal(calls[0][0],'/messager/bots/origin/collaboration-plans/exact-plan/decisions/approve');assert.equal(calls[0][2].review_hash,'exact-review');feed.dispose();});
test('an active plan offers disabling without implicitly replaying or changing it',async()=>{const {root,calls,feed}=fixture();feed.update(value('active'));const buttons=root.children[0].children.filter(x=>x.tag==='button');assert.deepEqual(buttons.map(x=>x.textContent),['Disable collaboration plan']);assert.equal(calls.length,0);await buttons[0].onclick();assert.equal(calls[0][0],'/messager/bots/origin/collaboration-plans/exact-plan/pause');feed.dispose();});
test('delegation review keeps approval visible and active details start collapsed',async()=>{
 const {root,calls,feed}=fixture();
 const request={id:'exact-delegation',source_bot:'origin',target_name:'Reviewer',title:'Review facts',instructions:'Private task instructions',access:[],review_hash:'review'};
 const update=(status,extra={})=>feed.update({proposals:[],interactions:[],delegations:[{...request,status,...extra}]});
 const card=()=>root.children[0], details=()=>card().children.find(x=>x.tag==='details');
 update('pending');
 assert.equal(details().open,false);
 assert.match(JSON.stringify(details()),/Private task instructions/);
 const approve=card().children.find(x=>x.textContent==='Allow Bot access');
 assert.ok(approve);
 await approve.onclick();
 assert.equal(calls[0][0],'/messager/bots/origin/delegations/exact-delegation/decisions/approve');
 details().open=true;
 update('running');
 assert.equal(details().open,false);
 assert.equal(card().children.length,1);
 assert.match(details().children[0].textContent,/Reviewer · Review facts/);
 details().open=true;
 update('running',{child_task_id:'child'});
 assert.equal(details().open,true);
 await details().children.find(x=>x.textContent==='Stop collaboration').onclick();
 assert.equal(calls[1][0],'/messager/bots/origin/delegations/exact-delegation/cancel');
 feed.dispose();
});
