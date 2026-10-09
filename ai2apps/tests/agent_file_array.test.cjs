const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const context={tr:()=> 'invalid',structuredClone};
vm.runInNewContext(source.slice(source.indexOf('    function parameterValue('),source.indexOf('    function readParameterDefinitions('))+'globalThis.parse=parameterValue;',context);
vm.runInNewContext(source.slice(source.indexOf('    function resolveInput('),source.indexOf('    async function execute('))+'globalThis.resolve=resolveInput;',context);
test('file array binding keeps variable count and file metadata',()=>{
 const files=[{asset_id:'a',name:'first.png'},{asset_id:'b',name:'second.png'}];
 const step=context.resolve({arguments:{asset_ids:'${input.attachments}'}},{attachments:files});
 assert.deepEqual(step.arguments.asset_ids,files);
 assert.notEqual(step.arguments.asset_ids,files);
 assert.equal(context.resolve('${input.attachments}',{attachments:[]}).length,0);
});
test('array editor values are arrays rather than stringified lists',()=>{
 assert.equal(context.parse('array','[1,2]').length,2);
 assert.throws(()=>context.parse('array','{}'));
});
