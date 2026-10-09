const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const fn=source.slice(source.indexOf('    async function executeAIStep('),source.indexOf('    async function executeInContext('));
for(const existing of [true,false])test('AI list completion returns items, not page URL; prior result='+existing,async()=>{
 const items={items:[{title:'A',url:'https://example.com/a'}]};let extracts=0;
 const bidi={contextId:'tab',explorationObservation:async()=>({url:'https://example.com'}),relatedWindowObservations:async()=>[],
 pageState:async()=>({url:'https://example.com'}),extractArticleList:async()=>{extracts++;return items;}};
 let calls=0;
 const ctx={client:async()=>bidi,state:{attachments:[]},stepWorkingGoal:step=>step.description,
 api:async()=>existing&&calls++===0?{decision:'act',source_step:{operation:'extract_list'},compiled_step:{operation:'extract_list'}}:{decision:'complete'},
 explorationActionNeedsConfirmation:()=>false,execute:async()=>({outcome:'success',evidence:{result:items}})};
 vm.runInNewContext(fn+'\nglobalThis.run=executeAIStep',ctx);
 const result=await ctx.run({operation:'inspect',authored_operation:'extract_list',description:'Extract article list',arguments:{}},[],[]);
 assert.deepEqual(result.evidence.result,items);assert.equal(extracts,existing?0:1);
});
