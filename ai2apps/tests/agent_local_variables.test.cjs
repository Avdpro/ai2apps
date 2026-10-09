const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const helpers=source.slice(source.indexOf('    function readVariableDefinitions('),source.indexOf('    function renderVariables('))+
source.slice(source.indexOf('    function readLocalArguments('),source.indexOf('    function renderLocalArguments('));
const row=fields=>({_schema:{},querySelector:selector=>({value:fields[selector]})});
function context(rows){const ctx={$$:()=>rows,tr:k=>k,JSON};vm.runInNewContext(helpers+'\nglobalThis.h={readVariableDefinitions,readLocalArguments}',ctx);return ctx.h;}
test('editor persists typed defaults and expression initialization',()=>{
 const h=context([row({'[data-variable=name]':'count','[data-variable=type]':'integer','[data-variable=title]':'计数','[data-variable=description]':'循环次数','[data-variable=initial]':'0','[data-variable=mode]':'fixed'}),
 row({'[data-variable=name]':'items','[data-variable=type]':'array','[data-variable=title]':'项目','[data-variable=description]':'','[data-variable=initial]':'input.items','[data-variable=mode]':'expression'})]);
 const schema=h.readVariableDefinitions();assert.equal(schema.properties.count.default,0);assert.equal(schema.properties.items.initial,'input.items');assert.equal(schema.properties.count.description,'循环次数');
});
test('editor rejects duplicate or unsafe variable names',()=>{
 const fields={'[data-variable=name]':'counter','[data-variable=type]':'integer','[data-variable=title]':'','[data-variable=description]':'','[data-variable=initial]':'0','[data-variable=mode]':'fixed'};
 assert.throws(()=>context([row(fields),row(fields)]).readVariableDefinitions());
 assert.throws(()=>context([row({...fields,'[data-variable=name]':'__proto__'})]).readVariableDefinitions());
});
test('dedicated assignment and condition forms serialize arguments',()=>{
 const h=context([]);const node={querySelectorAll:()=>[{querySelector:q=>({value:q==='[data-assignment-variable]'?'index':'vars.index + 1'})}],querySelector:()=>({value:' vars.index < len(input.items) '})};
 assert.equal(h.readLocalArguments(node,{operation:'assign'}).assignments[0].expression,'vars.index + 1');
 assert.equal(h.readLocalArguments(node,{operation:'condition'}).expression,'vars.index < len(input.items)');
});
test('single-step bindings preserve arrays, local state and previous output types',()=>{
 const code=source.slice(source.indexOf('    function resolveInput('),source.indexOf('    async function execute(',source.indexOf('    function resolveInput(')));
 const ctx={structuredClone,tr:k=>k};vm.runInNewContext(code+'\nglobalThis.bind=resolveInput;',ctx);
 const value=ctx.bind({files:'${vars.files}',index:'${vars.index}',last:'${steps.fetch.output.value}',url:'https://x.test/?q=${vars.text}'},{},{files:[{url:'a'}],index:0,text:'a b'},{fetch:{output:{value:false}}});
 assert.equal(value.files[0].url,'a');assert.equal(value.index,0);assert.equal(value.last,false);assert.equal(value.url,'https://x.test/?q=a%20b');
 assert.throws(()=>ctx.bind('${vars.missing}',{},{}));
});
