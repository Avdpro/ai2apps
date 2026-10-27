const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const feature={schemaVersion:'ai2apps.capability-content.v1',endpoint:'/v1/registry/content',query:'discovery',value:'capabilities-v1'};
const target={packageId:'publisher/fixture',version:'1.0.0',manifestSha256:'a'.repeat(64),artifactSha256:'b'.repeat(64)};
function card(status='unverified'){return {cardKey:status,contentKind:'app',identity:'main',displayName:'Fixture',description:'<script>untrusted</script>',release:{...target},installationTarget:{...target},publisher:{displayName:'Fixture'},compatibility:{},permissions:[],agent_support:'unverified',match:{status,reasons:[],exclusions:status==='excluded'?[{code:'PLATFORM_MISMATCH'}]:[],unknown:[]},processing:'unknown',pricing:'unknown',license:'unknown',downloadBytes:42};}
function setup(handler){const calls=[];const context={URLSearchParams,document:{documentElement:{lang:'en'}},requestAnimationFrame:f=>f(),window:{t:k=>k,setTimeout:f=>f(),AI2AppsCapabilities:{createTransferMeter:()=>()=>'',formatDownloadProgress:()=>''}},fetch:async(url,options)=>{calls.push([url,options]);return {ok:true,json:async()=>handler(new URL(url,'http://local'),options)};}};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/static/js/discover.js'),'utf8'),context);return {app:context.window.discoverApp(),calls,context};}
test('negotiated cards keep excluded separate and details cannot substitute the latest version',async()=>{
 const {app,calls}=setup(url=>url.pathname.endsWith('/capabilities')?{capabilityCatalog:feature}:{schemaVersion:feature.schemaVersion,catalogSnapshot:'snapshot',outcome:'unverified_candidates',counts:{match:0,unverified:1,excluded:1},items:[card(),card('excluded')],nextCursor:null});
 await app.loadCatalogPage(false,true);assert.equal(app.items.length,2);assert.equal(app.visibleItems.length,1);app.showExcluded=true;assert.equal(app.visibleItems.length,2);assert.ok(app.capabilityContent);assert.equal(app.canInstall(app.items[1]),false);assert.match(app.capabilityLabel(app.items[0]),/unverified/);
 const query=new URL(calls.at(-1)[0],'http://local');assert.ok(query.pathname.endsWith('/capabilities-content'));assert.equal(query.searchParams.has('sort'),false);
 const before=calls.length;await app.openDetails(app.items[0]);assert.equal(calls.length,before);assert.equal(app.selected.version,'1.0.0');assert.equal(app.cloudVersion(app.items[0]),'1.0.0');assert.equal(app.selected.installationTarget.manifestSha256,target.manifestSha256);
});
test('explicit install forwards exact reviewed digests and retains post-install rediscovery status',async()=>{
 const {app,calls}=setup(()=>({status:'completed',result:{capabilityDiscovery:{status:'adapter_required',callable:false}}}));
 app.loadCatalog=async()=>{};const item={packageId:target.packageId,version:target.version,displayName:'Fixture',packageType:'app',installationTarget:target};
 await app.install(item,false);const request=calls.find(([url])=>url.endsWith('/install-operations'));assert.ok(request);const body=JSON.parse(request[1].body);assert.deepEqual(body.installationTarget,target);assert.equal(body.version,'1.0.0');assert.equal(app.lastCapabilityDiscovery.callable,false);
});

test('installation handoff restores exact target without installing and verifies before returning',async()=>{
 const {app,calls,context}=setup(url=>url.pathname.endsWith('/handoff')?{target:{app_id:'ai2apps.discover'},status:'pending',run_id:'run-a',interaction_id:'interaction-a',parameters:{installation_target:target}}:url.pathname.endsWith('/capabilities-content')?{items:[card()]}:{status:'completed',result:{business_executed:false}});
 const returned=[];context.window.ai2appsShell={openHandoff:async(...args)=>returned.push(args)};
 await app.openPackageHandoff({runId:'run-a',interactionId:'interaction-a'});
 assert.equal(app.selected.version,'1.0.0');assert.deepEqual({...app.selected.installationTarget},target);
 assert.equal(calls.some(([url])=>url.includes('/install-operations')),false);
 await app.returnPackageTask(true);
 assert.ok(calls.some(([url,options])=>url.endsWith('/parameters/handoff/complete')&&options.method==='POST'));
 assert.deepEqual(returned,[['run-a','interaction-a',true]]);assert.equal(app.packageHandoff,null);
});
test('failed install verification keeps the original handoff and does not return or retry installation',async()=>{
 const {app,calls,context}=setup(()=>({}));const returned=[];
 context.fetch=async()=>({ok:false,json:async()=>({detail:'Selected exact release is not active'})});
 context.window.ai2appsShell={openHandoff:async(...args)=>returned.push(args)};
 app.packageHandoff={run_id:'run-a',interaction_id:'i',base:'/original'};
 await app.returnPackageTask(true);
 assert.equal(app.packageHandoff.run_id,'run-a');assert.equal(returned.length,0);assert.match(app.message,/not active/);
});
