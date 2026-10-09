const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/intelligence_site_agents.js','utf8');
function setup({cached=false,drift=false,bad=false}={}){
 const recipe={generation_id:'v1',rule:{},ir:{steps:[{mode:'compiled'}]}};
 const baseline={items:[{url:'https://example.com/a'},{url:'https://example.com/b'}]};let executions=0,learnCalls=0,activations=0,invalidations=0;
 const client={observeExtractionRegions:async()=>({url:'https://example.com/',regions:[{selector:'main',count:2,sample:'headlines'}]}),
 executeExtractionStep:async()=>{executions++;if(drift&&executions===1)throw Error('drift');return bad?{items:[{url:'https://example.com/unrelated'}]}:baseline;}};
 const api=async(path,method,body)=>{if(path.endsWith('learn')){learnCalls++;return recipe;}if(path.endsWith('activate')){activations++;return recipe;}if(path.endsWith('invalidate')){invalidations++;return {}; }return {recipe:cached?recipe:null};};
 const env={window:{},performance:{now:()=>0}};vm.runInNewContext(source,env);
 return {agent:new env.window.IntelligenceSiteAgents({api,source:{id:'source'},client}),baseline,counts:()=>({learnCalls,activations,invalidations})};
}
test('learned rule is validated and reused with zero subsequent learning calls',async()=>{
 const {agent,baseline,counts}=setup();await agent.load();await agent.list(async()=>baseline.items);await agent.list(()=>{throw Error('generic should not run');});
 assert.equal(agent.stats.learned,1);assert.equal(agent.stats.reused,1);assert.equal(counts().learnCalls,1);
});
test('cached drift invalidates and repairs once before reuse',async()=>{
 const {agent,baseline,counts}=setup({cached:true,drift:true});await agent.load();await agent.list(async()=>baseline.items);
 assert.equal(counts().invalidations,1);assert.equal(counts().activations,1);assert.equal(agent.stats.fallback,1);
});
test('unrelated extraction never activates and only learns once per source run',async()=>{
 const {agent,baseline,counts}=setup({bad:true});await agent.load();await agent.list(async()=>baseline.items);await agent.list(async()=>baseline.items);
 assert.equal(counts().activations,0);assert.equal(counts().learnCalls,1);
});
