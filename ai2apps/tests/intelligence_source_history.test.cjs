const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/intelligence.js'),'utf8');
const ctx={URL};vm.createContext(ctx);vm.runInContext(src.slice(src.indexOf('function eventOtherSources('),src.indexOf('function eventOtherSourcesHTML(')),ctx);
test('historical sources exclude current citations and prefer latest preview metadata',()=>{
 const a={sources:[{url:'https://cnn.com/a'}],versions:[{sources:[{url:'https://nyt.com/a',coverage:''}]},{sources:[{url:'https://cnn.com/a#top'},{url:'https://nyt.com/a#top',coverage:'preview',access_reason:'login_required'}]}],related_sources:[{url:'https://nyt.com/b'},{url:'javascript:alert(1)'}]};
 const result=ctx.eventOtherSources(a);assert.equal(result.length,2);assert.equal(result[0].coverage,'preview');assert.equal(a.sources.length,1);
});
