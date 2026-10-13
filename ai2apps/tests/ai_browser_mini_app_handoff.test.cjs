const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
test('custom Mini-App creates a local project and hands user requirements only to Coder',async()=>{
 let request,stored,opened;
 const context={crypto:{randomUUID:()=> 'unique-id'},window:{t:k=>k,ai2appsShell:{openEntry:v=>opened=v}},document:{},Map,URL,URLSearchParams,setTimeout,clearTimeout,sessionStorage:{setItem:(key,value)=>stored={key,value:JSON.parse(value)}},fetch:async(url,options)=>{request={url,body:JSON.parse(options.body)};return {ok:true,json:async()=>({id:'private-project'})};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/ai_browser.js','utf8'),context);
 const app=context.aiBrowserApp();app.customMiniAppName='Private search';app.customMiniAppRequest='Combine two public search sources';
 await app.customizeMiniApp();
 assert.equal(request.url,'/v1/platform/coder/projects');assert.equal(request.body.kind,'ai2apps');assert.equal(request.body.root_path,'private-browser-mini-app-unique-id');
 assert.equal(stored.value.projectId,'private-project');assert.match(stored.value.prompt,/ai2apps.ai-browser/);assert.match(stored.value.prompt,/do not publish or upload/);assert.match(stored.value.prompt,/Combine two public search sources/);assert.equal(opened.appId,'ai2apps.coder');
});
