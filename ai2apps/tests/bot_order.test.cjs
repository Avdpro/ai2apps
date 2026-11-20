const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('drag order is saved to the server and restored without browser storage',async()=>{
 let items=[{id:'a'},{id:'b'}];const writes=[];
 const context={window:{},document:{documentElement:{lang:'en'}},navigator:{language:'en'},
  localStorage:{getItem(){throw Error('Storage is origin-specific');},setItem(){throw Error('Do not store ordering here');}},
  fetch:async(url,options)=>{if(options.method==='PUT'){writes.push(JSON.parse(options.body));items=writes.at(-1).ids.map(id=>({id}));}return {ok:true,json:async()=>({items})};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),context);
 const app=context.window.messagerApp();app.currentBot={id:'a'};await app.loadBots();
 app.startBotDrag({button:0,pointerType:'mouse',pointerId:1,clientX:0,clientY:0,target:{closest:()=>({dataset:{botOrderId:'a'}})}});
 app.botDragId='a';app.botDropId='b';app.botDropAfter=true;app.trackBotDrag=()=>{};
 await app.dropBot({pointerId:1});assert.deepEqual(writes,[{ids:['b','a']}]);
 const fresh=context.window.messagerApp();fresh.currentBot={id:'a'};await fresh.loadBots();
 assert.deepEqual(Array.from(fresh.bots,b=>b.id),['b','a']);
 items=[...items,{id:'new'}];await fresh.loadBots();assert.equal(fresh.bots.at(-1).id,'new');
});


test('cross-group drop sends one atomic persisted order and membership change',async()=>{
 let items=[{id:'a',group_id:null},{id:'b',group_id:'quick'}];const writes=[];
 const context={window:{},document:{documentElement:{lang:'en'}},navigator:{language:'en'},fetch:async(url,options)=>{if(options.method==='PUT'){const body=JSON.parse(options.body);writes.push(body);items=body.ids.map(id=>({...items.find(b=>b.id===id),...(id===body.move.bot_id?{group_id:body.move.group_id}:{})}));}return {ok:true,json:async()=>({items:url.endsWith('/bot-groups')?[{id:'quick',permanent:true,collapsed:false}]:items})};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),context);
 const app=context.window.messagerApp();app.currentBot={id:'a'};await app.loadBots();
 app.startBotDrag({button:0,pointerType:'mouse',pointerId:1,clientX:0,clientY:0,target:{closest:()=>({dataset:{botOrderId:'a'}})}});
 app.botDragId='a';app.botDropId='b';app.botDropGroup='quick';app.trackBotDrag=()=>{};await app.dropBot({pointerId:1});
 assert.deepEqual(writes,[{ids:['a','b'],move:{bot_id:'a',group_id:'quick'}}]);assert.equal(app.bots[0].group_id,'quick');assert.ok(app.botDragClickUntil>Date.now());
 const fresh=context.window.messagerApp();fresh.currentBot={id:'a'};await fresh.loadBots();assert.equal(fresh.bots[0].group_id,'quick');assert.equal(fresh.groupBots({id:'quick'}).length,2);
});


test('group header drop persists order without changing Bot membership',async()=>{
 const writes=[];let groups=[{id:'quick'},{id:'a'},{id:'b'}];
 const context={window:{},document:{documentElement:{lang:'en'}},navigator:{language:'en'},fetch:async(url,options)=>{writes.push(JSON.parse(options.body));groups=writes.at(-1).ids.map(id=>({id}));return {ok:true,json:async()=>({items:groups})};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),context);
 const app=context.window.messagerApp();app.botGroups=groups;
 app.startGroupDrag({dataTransfer:{setData(){}}},{id:'b'});
 await app.dropGroup({preventDefault(){},clientY:1,currentTarget:{getBoundingClientRect:()=>({top:0,height:40})},dataTransfer:{}},{id:'quick'});
 assert.deepEqual(writes,[{ids:['b','quick','a']}]);assert.equal(app.groupDragId,null);assert.equal(app.groupBusy,false);
});
