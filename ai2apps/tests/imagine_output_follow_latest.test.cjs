const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
test('Studio follows arriving outputs only when already viewing latest; explicit refresh selects latest',async()=>{
 let items=[{id:'old',artifacts:[]}];
 const context={window:{},document:{documentElement:{lang:'en'}},structuredClone,fetch:async()=>({ok:true,json:async()=>({items})})};
 vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/imagine_studio.js','utf8'),context);
 const app=context.window.imagineStudioApp();app.appInstanceId=()=> 'owner-instance';app.historyHeaders=()=>({});app.icons=()=>{};app.outputRecoveryDone=true;
 await app.refreshRuns();assert.equal(app.selectedRunId,'old');
 items=[{id:'new',artifacts:[]},...items];await app.refreshRuns();assert.equal(app.selectedRunId,'new');
 app.selectRun(items[1]);items=[{id:'newer',artifacts:[]},...items];await app.refreshRuns();assert.equal(app.selectedRunId,'old');
 await app.refreshRuns(true);assert.equal(app.selectedRunId,'newer');
});
for(const status of [404,405,401,403,500])test('recovery status '+status+' preserves output loading and auth failures',async()=>{
 const calls=[];const context={window:{},document:{documentElement:{lang:'en'}},structuredClone,fetch:async url=>{
 calls.push(url);return url.includes('recover-session-results')?{status,ok:false,json:async()=>({detail:'failure'})}:{ok:true,status:200,json:async()=>({items:[{id:'saved',artifacts:[]}]})};}};
 vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/imagine_studio.js','utf8'),context);
 const app=context.window.imagineStudioApp();app.appInstanceId=()=> 'owner-instance';app.historyHeaders=()=>({});app.icons=()=>{};
 if([404,405].includes(status)){await app.refreshRuns();assert.equal(app.selectedRunId,'saved');await app.refreshRuns();assert.equal(calls.filter(x=>x.includes('recover-session')).length,1);}
 else{await assert.rejects(()=>app.refreshRuns());assert.equal(calls.length,1);assert.equal(app.outputRecoveryDone,false);}
 assert.equal(app.outputRefreshing,false);
});
