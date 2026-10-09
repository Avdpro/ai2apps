const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const script=fs.readFileSync(__dirname+'/../web/static/js/intelligence.js','utf8');
const code=script.slice(script.indexOf('async function browserSession('),script.indexOf('\nasync function closeBrowser'));
test('source Profile launch binds only the unique requested page',async()=>{
 let requested,closed=false;
 class Connection{async connect(){} async close(){closed=true;} async command(method){assert.equal(method,'browsingContext.getTree');return {contexts:[{context:'unrelated',url:'https://example.com/'},{context:'owned-context',url:requested.url}]};}}
 const context={location:{origin:'http://127.0.0.1:18080'},crypto:{randomUUID:()=> 'unique'},window:{AI2AppsBiDi:{AI2AppsBiDiConnection:Connection,AI2AppsPageClient:class{}}},fetch:async(url,options)=>{requested={endpoint:url,url:JSON.parse(options.body).initial_url};return {ok:true,json:async()=>({})};}};
 Object.assign(context,require('./intelligence_test_env.cjs'));vm.createContext(context);vm.runInContext(code+'\nthis.openSession=browserSession',context);
 const result=await context.openSession('a'.repeat(32));
 assert.equal(requested.endpoint,'/v1/platform/client/browser-profiles/'+'a'.repeat(32)+'/launch');
 assert.equal(result.context,'owned-context');assert.equal(result.client.contextId,'owned-context');assert.equal(closed,false);
});
test('ambiguous bootstrap page fails closed without using focused tab',async()=>{
 let marker,closed=false;
 class Connection{async connect(){} async close(){closed=true;} async command(){return {contexts:[{context:'one',url:marker},{context:'two',url:marker}]};}}
 const context={location:{origin:'http://127.0.0.1:18080'},crypto:{randomUUID:()=> 'unique'},window:{AI2AppsBiDi:{AI2AppsBiDiConnection:Connection}},fetch:async(url,options)=>{marker=JSON.parse(options.body).initial_url;return {ok:true,json:async()=>({})};}};
 Object.assign(context,require('./intelligence_test_env.cjs'));vm.createContext(context);vm.runInContext(code+'\nthis.openSession=browserSession',context);
 await assert.rejects(context.openSession('default'),/未找到/);assert.equal(closed,true);
});

test('collection only submits a durable background job and refreshes once',async()=>{
 const calls=[],env={busy:false,render(){},refresh:async()=>calls.push('refresh'),notice(){},api:async(...args)=>calls.push(args)};
 Object.assign(env,require('./intelligence_test_env.cjs'));vm.createContext(env);vm.runInContext(script.slice(script.indexOf('async function collect('),script.indexOf("\n$('#collect').onclick"))+'\nthis.collect=collect;',env);
 await env.collect('channel');assert.deepEqual(JSON.parse(JSON.stringify(calls)),[['/channels/channel/runs','POST',{scheduled:false}],'refresh']);
 assert.equal(env.busy,false);
});
test('collection observes shared SSE without frontend scheduling or browser execution',()=>{
 const body=script.slice(script.indexOf('async function collect('),script.indexOf("\n$('#collect').onclick"));
 assert.doesNotMatch(body,/browserSession|\/finish|setInterval/);
 assert.match(script,/EventSource\('\/v1\/platform\/browser-workspace\/events'/);
 assert.doesNotMatch(script,/async function tick/);
});

test('section navigation filters articles with search and unread status and escapes names',()=>{
 const nodes={'#section-filters':{},'#intel-content':{},'#search-articles':{value:''},'#article-filter':{value:'all'},'#article-type-filter':{value:'all'}};
 const sections=[{id:'new',name:'新品 <发布>',description:'New releases'},{id:'review',name:'上手体验',description:'Reviews'}];
 const articles=[{id:'a',section_id:'new',title:'New watch',summary:'Summary',body:'Body',read:false,updated_at:'2026-10-07',sources:[]},
 {id:'b',section_id:'review',title:'Review',summary:'Summary',body:'Body',read:true,updated_at:'2026-10-07',sources:[]},
 {id:'c',title:'Legacy',summary:'Summary',body:'Body',read:false,updated_at:'2026-10-07',sources:[]}];
 const env={URL,window:{},document:{addEventListener(){}},channel:()=>({sections}),inChannel:t=>t==='articles'?articles:[],sectionId:'new',selectedId:null,tab:'articles',busy:false,
 readerMode:'chat',failedCovers:new Set(),
 $:s=>nodes[s] ||= {},when:s=>s,esc:s=>String(s??'').replaceAll('<','&lt;').replaceAll('>','&gt;')};
 Object.assign(env,require('./intelligence_test_env.cjs'));vm.createContext(env);
 vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/intelligence_cards.js','utf8'),env);
 vm.runInContext(script.slice(script.indexOf('function sectionName'),script.indexOf('function renderReader')),env);
 env.renderSections();env.renderContent();
 assert.match(nodes['#section-filters'].innerHTML,/新品 &lt;发布&gt;/);
 assert.match(nodes['#section-filters'].innerHTML,/待归类/);
 assert.match(nodes['#intel-content'].innerHTML,/New watch/);
 assert.doesNotMatch(nodes['#intel-content'].innerHTML,/data-article="b"/);
 env.sectionId='review';nodes['#article-filter'].value='unread';env.renderContent();
 assert.match(nodes['#intel-content'].innerHTML,/没有匹配/);
 env.sectionId='unassigned';env.renderContent();assert.match(nodes['#intel-content'].innerHTML,/Legacy/);
 nodes['#search-articles'].value='missing';env.renderContent();assert.match(nodes['#intel-content'].innerHTML,/没有匹配/);
});


test('container-only Profile launch creates an isolated tab with matching userContext',async()=>{
 const calls=[];
 class Connection{
  async connect(){} async close(){}
  async command(method,args){calls.push([method,args]);
   if(method==='browsingContext.getTree')return {contexts:[args.root?{context:'new',userContext:'profile'}:{context:'reference',url:'https://unrelated.example',userContext:'profile'}]};
   if(method==='browsingContext.create')return {context:'new'};
   return {};
  }
 }
 const context={location:{origin:'http://localhost'},crypto:{randomUUID:()=> 'unique'},window:{AI2AppsBiDi:{AI2AppsBiDiConnection:Connection,AI2AppsPageClient:class{}}},fetch:async()=>({ok:true,json:async()=>({user_context:'profile'})})};
 Object.assign(context,require('./intelligence_test_env.cjs'));vm.createContext(context);vm.runInContext(code+'\nthis.openSession=browserSession',context);
 const session=await context.openSession('default');assert.equal(session.context,'new');
 const create=calls.find(c=>c[0]==='browsingContext.create')[1];
 assert.equal(create.userContext,'profile');assert.equal(create.referenceContext,'reference');
 assert.equal(calls.find(c=>c[0]==='browsingContext.navigate')[1].context,'new');
});
