const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
function setup(win={},result={path:'/Selected/Test.pvt'}){
 const requests=[];
 const context={window:{innerWidth:1000,location:{origin:'http://localhost'},...win},document:{documentElement:{lang:'zh'}},URL,Blob,console,structuredClone,fetch:async(url,options)=>{requests.push({url,options});return {ok:true,status:200,json:async()=>result};}};
 vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/static/js/imagine_studio.js'),'utf8'),context);
 const app=context.window.imagineStudioApp();app.historyHeaders=()=>({});app.success=()=>{};app.fail=error=>{throw error};
 app.runs=[{id:'run',artifacts:[{id:'pvt',runId:'run',name:'LivePhoto.pvt.zip',metadata:{miniAppId:'ai2apps.imagine.frozen-time'}}]}];app.selectedRunId='run';app.selectedArtifactId='pvt';
 return {app,requests};
}
for(const [name,win,environment] of [['desktop',{},'desktop'],['App Shell iframe',{parent:{ai2appsShell:{}}},'browser']])test(name+' saves native PVT instead of downloading ZIP',async()=>{
 const {app,requests}=setup(win);app.clientEnvironment=environment;let prevented=false;
 await app.downloadArtifact({preventDefault(){prevented=true}},'/output/LivePhoto.pvt.zip');
 assert.equal(prevented,true);assert.equal(requests.length,1);assert.match(requests[0].url,/runs\/run\/save-live-photo$/);assert.equal(requests[0].options.method,'POST');
});
test('cancelled native Save As does not report a saved path',async()=>{
 const {app}=setup({}, {cancelled:true});app.clientEnvironment='desktop';
 let successes=0;app.success=()=>successes++;
 await app.downloadArtifact({preventDefault(){}},'/output/LivePhoto.pvt.zip');
 assert.equal(successes,0);assert.equal(app.activeArtifact.savingPvt,false);
});
