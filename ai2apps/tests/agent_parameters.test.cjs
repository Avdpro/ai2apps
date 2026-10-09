const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/../web/static/js/agent_mini.js', 'utf8');
const context = {structuredClone,tr:(key,values={})=>key+JSON.stringify(values)};
vm.runInNewContext(source.slice(source.indexOf('    function parameterValue('),source.indexOf('    function renderParameters(')) +
 source.slice(source.indexOf('    function resolveInput('),source.indexOf('    async function execute(')) +
 '\nglobalThis.convert=parameterValue;globalThis.resolve=resolveInput;globalThis.read=readInputFields;', context);
test('typed values preserve number, integer and boolean', () => {
 assert.equal(context.convert('boolean','false'),false);
 assert.equal(context.convert('integer','0'),0);
 assert.equal(context.convert('number','1.5'),1.5);
 for(const [type,value] of [['integer','1.5'],['number',''],['boolean','yes']]) assert.throws(()=>context.convert(type,value));
});
test('parameter binding resolves typed values and nested arguments', () => {
 const step={arguments:{value:'${input.query}',limit:'${input.limit}'},description:'Search ${input.query}'};
 const result=context.resolve(step,{query:'新的关键词',limit:10});
 assert.equal(result.arguments.value,'新的关键词'); assert.equal(result.arguments.limit,10);
 assert.equal(result.description,'Search 新的关键词');
 assert.equal(step.arguments.value,'${input.query}');
 assert.throws(()=>context.resolve(step,{}));
});
test('runtime form rejects missing required values and preserves false/zero', () => {
 const schema={properties:{enabled:{type:'boolean'},limit:{type:'integer'},query:{type:'string'}},required:['query']};
 const fields=[{dataset:{parameter:'enabled'},value:'false'},{dataset:{parameter:'limit'},value:'0'},{dataset:{parameter:'query'},value:'test'}];
 const container={querySelectorAll:()=>fields};
 const values=context.read(container,schema); assert.equal(values.enabled,false);assert.equal(values.limit,0);
 fields[2].value='';assert.throws(()=>context.read(container,schema));
});
test('search URL parameters are encoded without changing origin', () => {
 const step={arguments:{url:'https://www.google.com/search?q=${input.query}&hl=zh'}};
 const result=context.resolve(step,{query:'中文 &next=https://evil.example'});
 assert.equal(new URL(result.arguments.url).searchParams.get('q'),'中文 &next=https://evil.example');
 assert.equal(new URL(result.arguments.url).hostname,'www.google.com');
 assert.equal(new URL(result.arguments.url).searchParams.has('next'),false);
});
test('file reference remains an object and its URL can be bound separately', () => {
 const file={asset_id:'owned-file',url:'/v1/platform/gallery/assets/owned-file/content',name:'reference.pdf'};
 assert.deepEqual(JSON.parse(JSON.stringify(context.convert('object',JSON.stringify(file)))),file);
 assert.deepEqual(JSON.parse(JSON.stringify(context.resolve('${input.file_1}',{file_1:file}))),file);
 assert.equal(context.resolve('${input.file_1.url}',{file_1:file}),file.url);
 assert.throws(()=>context.convert('object','[]'));
});
