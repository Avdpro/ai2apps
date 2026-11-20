const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

test('temporary task startup failure preserves tasks and clears after polling succeeds',async()=>{
 const replies=[];
 const context={window:{},document:{documentElement:{lang:'en'}},navigator:{language:'en'},
  fetch:async()=>replies.shift()};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),context);
 const app=context.window.messagerApp(),bot={id:'fixture'};
 app.currentBot=bot;app.bots=[bot];app.botTasks=[{id:'existing'}];
 const failures=[];app.fail=e=>failures.push(e);app.taskActive=()=>false;
 replies.push({ok:false,status:503,json:async()=>({detail:'Todo tasks unavailable'})});
 await app.loadBotTasks();
 assert.equal(app.botTasksUnavailable,true);
 assert.equal(app.botTasks[0].id,'existing');assert.equal(failures.length,0);
 replies.push({ok:true,json:async()=>({items:[{id:'fresh'}],has_more:false})});
 await app.loadBotTasks();
 assert.equal(app.botTasksUnavailable,false);assert.equal(app.botTasks[0].id,'fresh');
 replies.push({ok:false,status:403,json:async()=>({detail:'Denied'})});
 await app.loadBotTasks();assert.equal(failures.length,1);
});

test('task response from previous Bot cannot change the current Bot startup state',async()=>{
 let resolve;
 const context={window:{},document:{documentElement:{lang:'en'}},navigator:{language:'en'},fetch:()=>new Promise(r=>resolve=r)};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),context);
 const app=context.window.messagerApp();app.currentBot={id:'old'};
 const pending=app.loadBotTasks();app.currentBot={id:'new'};
 resolve({ok:false,status:503,json:async()=>({detail:'Todo tasks unavailable'})});
 await pending;assert.equal(app.botTasksUnavailable,false);
});
