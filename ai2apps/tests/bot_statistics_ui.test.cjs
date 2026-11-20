const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
test('time-range requests carry timezone and a stale response cannot replace a newer selection',async()=>{
 const pending=[],urls=[];const env={window:{},document:{documentElement:{lang:'en'}},navigator:{language:'en'},fetch:(url)=>{urls.push(url);return new Promise(resolve=>pending.push(value=>resolve({ok:true,json:async()=>value})));}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),env);const app=env.window.messagerApp();app.currentBot={id:'owned'};app.statisticsTimezone='Asia/Shanghai';
 const a=app.loadBotStatistics(true);app.statisticsPeriod='7d';const b=app.loadBotStatistics(true);app.statisticsPeriod='today';const c=app.loadBotStatistics(true);
 pending[2]({period:'today',tokens:30});await c;pending[0]({period:'today',tokens:10});await a;pending[1]({period:'7d',tokens:20});await b;
 assert.equal(app.botStatistics.tokens,30);assert.equal(app.statisticsBusy,false);assert.match(urls[0],/period=today&timezone_name=Asia%2FShanghai/);assert.match(urls[1],/period=7d/);
});
test('linked task opens statistics only for its exact Todo ID',async()=>{
 const urls=[],env={window:{},document:{documentElement:{lang:'en'}},navigator:{language:'en'},fetch:async url=>{urls.push(url);return {ok:true,json:async()=>({executions:2,usage:{input_tokens:7}})}}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),env);const app=env.window.messagerApp();app.currentBot={id:'owned'};await app.inspectBotTask({id:'todo-1',linked:{id:'todo-1'}});assert.match(urls[0],/statistics\?todo_task_id=todo-1$/);assert.equal(app.botTaskSessionDetail.statistics.executions,2);
});
test('task breakdown keeps unknown, partial, and explicitly reported zero distinct',()=>{
 const env={window:{},document:{documentElement:{lang:'en'}},navigator:{language:'en'}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager_usage.js','utf8'),env);
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),env);
 const app=env.window.messagerApp();
 const rows=app.taskUsageRows({task:{tokens:40},aaat:{points:'0'},delegated:{tokens:null},total:{tokens:null,known_tokens:40}});
 assert.equal(rows.map(r=>r.label).join(', '),'Task itself, AaAT, Delegated Bots, Total');
 assert.equal(app.taskUsageValue(rows[1].points,null),'0');
 assert.equal(app.taskUsageValue(rows[2].tokens,null),'Unk.');
 assert.equal(app.taskUsageValue(rows[3].tokens,rows[3].known_tokens),'>40');
 assert.equal(app.taskUsageValue(null,3201),'>3.2K');
 assert.equal(app.taskUsageValue(null,3299),'>3.2K');
 assert.equal(app.taskUsageValue('0.000000',null),'0');
 assert.equal(app.taskUsageValue('12.010000',null),'12.01');
 assert.equal(app.formatUsageAmount(132300),'132.3K');
 assert.equal(app.formatUsageAmount(20900000),'20.9M');
 assert.equal(app.formatUsageAmount('1000000000.000000'),'1.0G');
 assert.equal(app.formatUsageAmount(999950),'1.0M');
 assert.equal(app.formatUsageAmount(999950,true),'999.9K');
});
