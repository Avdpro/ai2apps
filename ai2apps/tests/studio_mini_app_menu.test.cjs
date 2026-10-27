const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const placements=['ai2apps.imagine-studio','ai2apps.video-studio','ai2apps.readaloud'];
for(const placement of placements)test(`private customization binds ${placement} to Coder`,async()=>{
 let body,handoff,destination;const context={window:{ai2appsShell:{openEntry:async data=>{destination=data;}}},document:{documentElement:{lang:'en'}},crypto:{randomUUID:()=> 'unique-test'},sessionStorage:{setItem:(key,value)=>{handoff=JSON.parse(value);}},fetch:async(url,options)=>{assert.equal(url,'/v1/platform/coder/projects');body=JSON.parse(options.body);return{ok:true,json:async()=>({id:'private-project'})};}};
 context.window.addEventListener=()=>{};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/capability_provisioning.js','utf8'),context);
 await context.window.AI2AppsCapabilities.createPrivateMiniAppProject({placement,name:'My app',requirements:'Build my tool'});
 assert.equal(body.kind,'ai2apps');assert.equal(body.create_directory,true);assert.match(body.root_path,/^private-mini-app-/);assert.equal(handoff.projectId,'private-project');assert.ok(handoff.prompt.includes(placement));assert.ok(handoff.prompt.includes('do not publish or upload'));assert.equal(destination.appId,'ai2apps.coder');
 if(placement==='ai2apps.readaloud')assert.ok(handoff.prompt.includes('one host-owned Preview & Output based on Quick Read'));
 assert.equal(handoff.prompt.includes('execute WebAgents'),false);
});
test('unsupported hosts and empty requirements cannot create projects',async()=>{
 const context={window:{addEventListener(){}},document:{documentElement:{lang:'en'}}};vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/capability_provisioning.js','utf8'),context);
 await assert.rejects(context.window.AI2AppsCapabilities.createPrivateMiniAppProject({placement:'unknown'}),/Unsupported/);
 await assert.rejects(context.window.AI2AppsCapabilities.createPrivateMiniAppProject({placement:placements[0],name:'x',requirements:' '}),/Enter/);
});
