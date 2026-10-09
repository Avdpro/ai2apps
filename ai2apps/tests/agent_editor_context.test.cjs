const test=require('node:test'), assert=require('node:assert/strict'), vm=require('node:vm'), fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const pin=source.slice(source.indexOf('    function setContextPinned('),source.indexOf('    let noticeTimer'));
const mode=source.slice(source.indexOf('    function switchMode('),source.indexOf('    function fileReference('));
function setup() {
 const state={contextPinned:false,executionContextPinned:false,editorContextPinned:false}, applied=[], nodes={};
 const location={hash:'#bidi_context=original&url=https%3A%2F%2Fexample.com',pathname:'/agent-mini',search:''};
 const ctx={state,location,URLSearchParams,history:{state:null,replaceState:(_,__,url)=>{location.hash=url.includes('#')?'#'+url.split('#')[1]:'';}},
 document:{documentElement:{classList:{remove(){}}}},updateRunHandoff(){},
 $:s=>nodes[s] ||= {hidden:true,scrollIntoView:()=>{}},applyBrowserContext:async detail=>applied.push(detail)};
 vm.runInNewContext(pin+mode+';globalThis.pin=setContextPinned;globalThis.mode=switchMode',ctx);
 return {ctx,state,location,applied,nodes};
}
test('opening editor acquires a lease and preserves the original tab binding',()=>{
 const {ctx,location,nodes}=setup();ctx.mode('build');
 const hash=new URLSearchParams(location.hash.slice(1));
 assert.equal(hash.get('agent_context_lock'),'1');assert.equal(hash.get('bidi_context'),'original');
 assert.equal(nodes['#agent-build-panel'].hidden,false);
 ctx.pin(false);assert.equal(new URLSearchParams(location.hash.slice(1)).get('agent_context_lock'),'1');
});
test('closing editor during testing keeps execution lease; completion releases and applies latest pending tab',()=>{
 const {ctx,state,location,applied}=setup();ctx.mode('build');ctx.pin(true);ctx.mode('run');
 assert.equal(state.contextPinned,true);state.pendingBrowserContext={bidi_context:'new-tab'};
 ctx.pin(false);assert.equal(state.contextPinned,false);assert.equal(new URLSearchParams(location.hash.slice(1)).has('agent_context_lock'),false);
 assert.equal(applied[0].bidi_context,'new-tab');assert.equal(state.pendingBrowserContext,null);
});
test('context events cannot clear the editor, exploration or run while pinned',async()=>{
 const start=source.indexOf('    async function applyBrowserContext('),end=source.indexOf('        const previousKey',start);
 const ctx={state:{contextPinned:true,run:{id:'run'},exploration:{status:'running'}}};
 vm.runInNewContext(source.slice(start,end)+'}\nglobalThis.apply=applyBrowserContext',ctx);
 await ctx.apply({bidi_context:'next'});assert.equal(ctx.state.run.id,'run');assert.equal(ctx.state.exploration.status,'running');assert.equal(ctx.state.pendingBrowserContext.bidi_context,'next');
});
