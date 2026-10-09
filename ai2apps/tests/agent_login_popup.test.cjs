const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');
const method=source.slice(source.indexOf('        async relatedWindowObservations('),source.indexOf('        async extractRenderedPage('));
const ctx={};vm.runInNewContext('globalThis.Client=class{'+method+'}',ctx);
test('cleaned observations include opener descendants and exclude unrelated tabs',async()=>{
 const c=new ctx.Client();c.contextId='root';c.connection={command:async()=>({contexts:[{context:'root'},{context:'child',originalOpener:'root'},{context:'grandchild',originalOpener:'child'},{context:'unrelated'}]})};
 c.explorationObservation=async function(){return {url:'https://example.com',title:this.contextId,controls:[],control_count:0}};
 const windows=await c.relatedWindowObservations();
 assert.deepEqual(Array.from(windows,w=>w.context),['child','grandchild']);
 assert.equal(windows[0].title,'child');assert.equal(c.contextId,'root');
});
test('loading or closed popup produces evidence without changing original context',async()=>{
 const c=new ctx.Client();c.contextId='root';c.connection={command:async()=>({contexts:[{context:'popup',originalOpener:'root',url:'about:blank'}]})};
 c.explorationObservation=async()=>{throw Error('loading')};
 const windows=await c.relatedWindowObservations();assert.equal(windows[0].error,'window_not_ready');assert.equal(c.contextId,'root');
});
test('AI-selected context is validated and original binding restored after errors',async()=>{
 const agent=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
 const wrapper=agent.slice(agent.indexOf('    async function execute('),agent.indexOf('    async function executeInContext('));
 const bidi={contextId:'root',relatedWindowObservations:async()=>[{context:'popup'}]};
 const sandbox={client:async()=>bidi,executeInContext:async()=>{assert.equal(bidi.contextId,'popup');throw Error('action failed')}};
 vm.runInNewContext(wrapper+'\nglobalThis.executeStep=execute;',sandbox);
 const denied=await sandbox.executeStep({browser_context:'unrelated'});assert.equal(denied.evidence.reason,'unrelated_or_closed_window');
 await assert.rejects(sandbox.executeStep({browser_context:'popup'}),/action failed/);assert.equal(bidi.contextId,'root');
});
