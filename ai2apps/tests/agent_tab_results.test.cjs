const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const helper=source.slice(source.indexOf('    function runMatchesContext('),source.indexOf('    function contextIsWebPage('));
const context={};vm.runInNewContext(helper+'\nglobalThis.matches=runMatchesContext;',context);
test('results belong to a Tab, even when multiple Tabs share a URL',()=>{
 const run={input:{parameters:{browser_context:{bidi_context:'tab-a',url:'https://example.com'}}}};
 assert.equal(context.matches(run,{bidi_context:'tab-a',url:'https://example.com/next'}),true);
 assert.equal(context.matches(run,{bidi_context:'tab-b',url:'https://example.com'}),false);
 assert.equal(context.matches(run,{bidi_context:'new-tab',url:'about:newtab'}),false);
 assert.equal(context.matches({input:{}},{bidi_context:'tab-a'}),false);
 assert.equal(context.matches(run,{}),false);
});
