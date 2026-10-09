const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const helper=source.slice(source.indexOf('    function inputValue('),source.indexOf('    function resolveInput('));
const context={};vm.runInNewContext(helper+'\nglobalThis.value=inputValue;',context);
test('ordinary compose text preserves canonical and provider alias payloads',()=>{
 for(const key of ['value','text','content'])assert.equal(context.value({arguments:{[key]:'上手数字人制作'},description:'输入文案'}),'上手数字人制作');
 assert.equal(context.value({arguments:{value:'正确',text:'别的'},description:'输入文案'}),'正确');
});
test('missing input payload is a failed action for planner repair, not a human challenge',()=>{
 assert.match(source,/if \(!value && !submitSearch\) return \{outcome: 'failed', evidence: \{reason: 'input_value_required'/);
});
