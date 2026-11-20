const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
test('fresh Run state and approval render before an unrelated slow work list',async()=>{
 function node(tag){return {value:tag==='textarea'?'new message':'',children:[],dataset:{},prepend(...items){this.children.unshift(...items);},remove(){},classList:{add(){}},append(...items){this.children.push(...items);},insertBefore(item){this.children.push(item);},replaceChildren(...items){this.children=items;},setAttribute(){},addEventListener(){},scrollHeight:100,clientHeight:100,scrollTop:0};}
 let release,entered;const work=new Promise(r=>{release=r;}),waiting=new Promise(r=>{entered=r;});const states=[],rendered=[];
 const today=new Date(),yesterday=new Date(today),older=new Date(today);
 yesterday.setDate(today.getDate()-1);older.setDate(today.getDate()-2);
 for(const date of [today,yesterday,older])date.setHours(9,5,0,0);
 const history=[today,yesterday,older,today].map((date,i)=>({id:'message-'+i,sequence:i+1,role:i===3?'user':'assistant',created_at:date.toISOString(),content:'Message '+i}));
 const pending={id:'approval',kind:'approval',schema:{},prompt:'Allow?',request:{}};
 let disconnected=false,recovering=false;const dialogueReads=[];
 const context={AbortController,setTimeout,clearTimeout,localStorage:{getItem(){return '';},setItem(){}},navigator:{language:'en'},setInterval(){return 1;},clearInterval(){},document:{documentElement:{lang:'en'},hidden:true,addEventListener(){},removeEventListener(){},createElement:node,createDocumentFragment:node},
  window:{AI2AppsBotMaterials:{createFeed(){return {update(){}};},attachments(){},enhance(){}},AI2AppsBotTaskFeed:{create(){return {update(){},dispose(){}};}},AI2AppsMiniAppChat:{bindMessageActions(){return {attach(article){const toolbar=node('div');toolbar.append(node('button'),node('button'));article.append(toolbar);return {toolbar};},dispose(){}};}},AI2AppsBotInteractions:{render(o){rendered.push(o.item);return true;},release(){}},AI2AppsBotModelSelection:{async resolve(){return {allModels:[],models:[],selected:'fixture',notice:''};}},AI2AppsBotComposer:{create(){return {setBusy(){},blocked(){return false;},hasFiles(){return false;},dispose(){}};}}},
  async fetch(url){if(disconnected)return {ok:false,status:503};let value={};if(url.endsWith('/app-chat/sessions'))value={session_id:'session'};else if(url.includes('/messages'))value={items:history,has_more:false};else if(url.includes('/dialogue/state?')){dialogueReads.push(url);value={runs:[recovering?{id:'run',status:'running',interactions:[],progress:{model_recovery:{state:'waiting',retry_at:new Date(Date.now()+8000).toISOString(),attempt:1,max_attempts:3}}}:{id:'run',status:'waiting_capability',text:'Allow?',interactions:[pending]}]};}else if(url.endsWith('/work')){entered();await work;value={};}else if(url.endsWith('/artifacts'))value={items:[]};return {ok:true,async json(){return value;}};}
 };
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/static/js/bot_conversation.js'),'utf8'),context);
 const root=node();const opening=context.window.AI2AppsBotConversation.create({bot:{id:'bot'},root,onState:v=>states.push(v),onError:e=>{throw e;}});
 await waiting;
 const walk=n=>[n,...n.children.flatMap(walk)];
 assert.equal(states.at(-1).runs[0].status,'waiting_capability');
 assert.equal(rendered[0].id,'approval');
 assert.equal(walk(root).find(n=>n.type==='submit').disabled,false);
 release();
 const controller=await opening;
 await new Promise(setImmediate);
 const status=walk(root).find(n=>n.className==='bot-conversation-status');
 const dates=walk(root).filter(n=>n.className==='bot-message-time');
 assert.equal(dates.length,3);
 assert.equal(dates[0].textContent,'09:05');
 assert.equal(dates[1].textContent,'Yesterday 09:05');
 assert.equal(dates[2].textContent,older.toLocaleDateString('en',{year:'numeric',month:'short',day:'numeric'})+' 09:05');
 for(const time of dates)assert.equal(walk(root).find(n=>n.children.includes(time)).children.indexOf(time),2);

 disconnected=true;
 await controller.refresh(true);
 assert.equal(status.textContent,'Reconnecting…');
 disconnected=false;recovering=true;
 await controller.refresh(true);
 assert.match(status.textContent,/Model rate limit.*attempt 2\/3/);
 assert.equal(states.at(-1).runs[0].id,'run');
 assert.equal(new Set(dialogueReads).size,1);
 controller.dispose();
});

test('acknowledged answer stays a receipt through an in-flight stale poll and next question replaces it',async()=>{
 function node(tag){return {tag,prepend(...items){this.children.unshift(...items);},remove(){},isConnected:true,dataset:{},value:'',children:[],classList:{add(){},remove(){}},append(...items){this.children.push(...items);},insertBefore(item){this.children.push(item);},replaceChildren(...items){this.children=items;},setAttribute(){},addEventListener(){},scrollHeight:100,clientHeight:100,scrollTop:0};}
 const question={id:'question',kind:'menu',prompt:'Which Bot?',schema:{properties:{answer:{type:'string'}}}};
 let current=question,runStatus='waiting_input',workResolve,workEntered,holdWork=false,posts=0;const entered=new Promise(r=>workEntered=r);
 const context={AbortController,crypto:{randomUUID:()=> 'stable-id'},setTimeout,clearTimeout,localStorage:{getItem(){return '';},setItem(){}},navigator:{language:'en'},setInterval(){return 1;},clearInterval(){},document:{documentElement:{lang:'en'},hidden:true,addEventListener(){},removeEventListener(){},createElement:node,createDocumentFragment:node},
 window:{AI2AppsBotMaterials:{createFeed(){return {update(){}};}},AI2AppsBotTaskFeed:{create(){return {update(){},dispose(){}};}},AI2AppsMiniAppChat:{bindMessageActions(){return {attach(){},dispose(){}};}},AI2AppsParameterForms:{release(){}},AI2AppsBotModelSelection:{async resolve(){return {allModels:[],models:[],selected:'fixture',notice:''};}},AI2AppsBotComposer:{create(){return {setBusy(){},blocked(){return false;},hasFiles(){return false;},dispose(){}};}}},
 async fetch(url,options){let value={};if(url.endsWith('/respond')){posts++;assert.match(url,/run\/interactions\/(next-)?question\/respond$/);assert.equal(JSON.parse(options.body).response.answer,'Use summary Bot');}else if(url.endsWith('/app-chat/sessions'))value={session_id:'session'};else if(url.includes('/messages'))value={items:[],has_more:false};else if(url.includes('/dialogue/state?'))value={runs:[{id:'run',status:runStatus,interactions:current?[current]:[]}]};else if(url.endsWith('/work')&&holdWork){workEntered();await new Promise(r=>workResolve=r);}return {ok:true,async json(){return value;}};}
 };
 for(const file of ['bot_interactions.js','bot_conversation.js'])vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/static/js',file),'utf8'),context);
 const root=node('host'),controller=await context.window.AI2AppsBotConversation.create({bot:{id:'bot'},root,onState(){},onError:e=>{throw e;}});
 await new Promise(setImmediate);
 const walk=n=>[n,...n.children.flatMap(walk)];const card=walk(root).find(n=>n.className==='bot-interactions bot-interaction-card');
 const form=card.children.find(n=>n.tag==='form'),field=form.children[1].children[0];field.value='Use summary Bot';holdWork=true;const poll=controller.refresh(true);await entered;
 await form.onsubmit({preventDefault(){}});assert.equal(posts,1);assert.equal(card.dataset.interactionState,'submitted');workResolve();await poll;holdWork=false;
 await controller.refresh(true);assert.equal(card.dataset.interactionState,'submitted');assert.equal(card.children.find(n=>n.tag==='form'),form);assert.equal(field.disabled,true);assert.equal(form.children[2].hidden,true);
 current={...question,id:'next-question',prompt:'Which date?'};await controller.refresh(true);assert.equal(card._botInteractionKey,'next-question');assert.equal(card.dataset.interactionState,'waiting');assert.notEqual(card.children.find(n=>n.tag==='form'),form);
 const nextForm=card.children.find(n=>n.tag==='form');nextForm.children[1].children[0].value='Use summary Bot';
 await nextForm.onsubmit({preventDefault(){}});
 runStatus='completed';current=null;await new Promise(setImmediate);await controller.refresh(true);
 assert.equal(card.hidden,true);assert.equal(card.children.length,0);controller.dispose();
});
