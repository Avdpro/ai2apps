const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');
function reader(){let now=0;const env={URL,Map,Date:{now:()=>now},setTimeout:(fn,ms)=>{now+=ms;fn();}};
vm.runInNewContext('globalThis.Reader=class{'+source.slice(source.indexOf('        async waitForStability('),source.indexOf('        async extractArticleList('))+'}',env);
const client=new env.Reader(),commands=[];client.contextId='root';client.createdContexts=new Map();client.connection={command:async(method,args)=>{commands.push({method,args});return method==='browsingContext.create'?{context:'child'}:{}}};
client.pageState=async()=>({url:'https://example.com/a',fingerprint:'stable'});client.handlePageAccess=async()=>({classification:'none'});client.readabilitySource='/* fixture */';client.callJSON=async()=>null;client.snapshot=async()=>({url:'https://example.com/a',title:'Fallback',text:'DOM article'});
return {client,commands};}
test('Readability meaningful text preferred, empty/throwing extraction falls back to cleaned DOM',async()=>{
const {client}=reader();client.callJSON=async()=>({url:'https://example.com/a',title:'Article',text:'x'.repeat(150)});
let result=await client.extractRenderedPage();assert.equal(result.extraction_method,'readability');assert.equal(result.text.length,150);
client.callJSON=async()=>null;result=await client.extractRenderedPage();assert.equal(result.extraction_method,'webdriver-bidi-cleaned-dom');assert.equal(result.text,'DOM article');
let calls=0;client.callJSON=async()=>{if(!calls++)throw Error('parser failed');return ''};result=await client.extractRenderedPage();assert.equal(result.fallback_reason,'parser failed');
});
test('read-page waits, reads, closes exactly created context and restores original',async()=>{
const {client,commands}=reader();const result=await client.readPage({url:'https://example.com/a',delay_ms:1500});
assert.equal(result.outcome,'success');assert.equal(result.tab_closed,true);assert.equal(client.contextId,'root');assert.equal(client.createdContexts.size,0);
assert.equal(commands.filter(x=>x.method==='browsingContext.close').length,1);assert.equal(commands.at(-1).method,'browsingContext.activate');
});
test('retained tab remains explicitly tracked; failed read closes temporary context',async()=>{
const {client,commands}=reader();let result=await client.readPage({url:'https://example.com/a',close_tab:false});assert.equal(result.context,'child');assert.equal(result.tab_closed,false);assert.equal(client.createdContexts.get('child'),'root');
assert.ok(!commands.some(x=>x.method==='browsingContext.close'));
const second=reader();second.client.extractRenderedPage=async()=>{throw Error('read failed')};await assert.rejects(()=>second.client.readPage({url:'https://example.com/a'}),/read failed/);assert.equal(second.client.contextId,'root');assert.ok(second.commands.some(x=>x.method==='browsingContext.close'));
});
test('CAPTCHA preserves a tab for assistance; paywall remains restricted without payment',async()=>{
const {client,commands}=reader();client.handlePageAccess=async()=>({classification:'needs_user',reason:'captcha'});let result=await client.readPage({url:'https://example.com/a'});assert.equal(result.outcome,'needs_user');assert.equal(result.context,'child');assert.ok(!commands.some(x=>x.method==='browsingContext.close'));
const second=reader();second.client.handlePageAccess=async()=>({classification:'restricted',reason:'paywall'});result=await second.client.readPage({url:'https://example.com/a'});assert.equal(result.outcome,'restricted');assert.ok(second.commands.some(x=>x.method==='browsingContext.close'));
});
test('invalid/private destinations never navigate',async()=>{for(const url of ['file:///etc/passwd','http://127.0.0.1/','https://user:secret@example.com/']){const {client,commands}=reader();await assert.rejects(()=>client.readPage({url}),/public_http_url_required/);assert.equal(commands.length,0);}});
test('wait-state polls presence and times out without performing actions',async()=>{
const {client,commands}=reader();let n=0;client.findTarget=async()=>++n>=3?{ref:'e1'}:null;let result=await client.waitState('Ready',true,5000);assert.equal(result.ready,true);assert.equal(n,3);
client.findTarget=async()=>null;result=await client.waitState('Ready',true,1000);assert.equal(result.reason,'state_timeout');assert.equal(commands.length,0);
});
test('SDK uses the exact existing licensed Readability source',()=>assert.equal(fs.readFileSync(__dirname+'/../web/static/js/readability.js','utf8'),fs.readFileSync(__dirname+'/../browser/readability.js','utf8')));

test('redirected private destination is rejected and temporary tab cleaned',async()=>{const {client,commands}=reader();client.pageState=async()=>({url:'http://127.0.0.1/internal',fingerprint:'stable'});await assert.rejects(()=>client.readPage({url:'https://example.com/a'}),/public_http_url_required/);assert.equal(client.contextId,'root');assert.ok(commands.some(x=>x.method==='browsingContext.close'));});

test('phased read retains tab for child cleanup then reads and closes without navigating again',async()=>{
 const {client,commands}=reader();const opened=await client.readPage({url:'https://example.com/a',phase:'open'});
 assert.equal(opened.context,'child');assert.ok(!commands.some(x=>x.method==='browsingContext.close'));
 client.contextId=opened.context;
 const result=await client.readPage({phase:'finish',opened,close_tab:true});assert.equal(result.outcome,'success');assert.equal(result.tab_closed,true);
 assert.equal(commands.filter(x=>x.method==='browsingContext.navigate').length,1);
 assert.equal(client.contextId,'root');
});
test('phased cleanup failure can close its own retained tab without extracting content',async()=>{
 const {client,commands}=reader();const opened=await client.readPage({url:'https://example.com/a',phase:'open'});client.contextId=opened.context;
 client.extractRenderedPage=()=>{throw Error('must not read')};await client.readPage({phase:'close',opened});
 assert.ok(commands.some(x=>x.method==='browsingContext.close'));assert.equal(client.createdContexts.size,0);
});
test('compiled extraction is guarded by page access and drifts back to generic reading',async()=>{
 const {client}=reader();let compiled=0;
 client.executeExtractionStep=async()=>{compiled++;throw Error('drift');};
 client.extractRenderedPage=async()=>({url:'https://example.com/a',text:'generic',title:'Generic'});
 const page=await client.readPage({url:'https://example.com/a',site_extraction:{selector:'article'}});
 assert.equal(page.extraction_fallback,true);assert.equal(page.text,'generic');assert.equal(compiled,1);
 client.handlePageAccess=async()=>({classification:'needs_user',reason:'captcha'});
 assert.equal((await client.readPage({url:'https://example.com/a',site_extraction:{}})).outcome,'needs_user');assert.equal(compiled,1);
});
test('compiled DOM extraction rejects malformed steps and short/absent results',async()=>{
 const {client}=reader();
 await assert.rejects(()=>client.executeExtractionStep({mode:'interpreted'}),/invalid_extraction/);
 const step={mode:'compiled',operation:'read_page',arguments:{site_extraction:{schema:'ai2apps.site-extraction/v1',kind:'article',selector:'article'}}};
 client.callJSON=async(script,args)=>{new Function('return ('+script+')');assert.equal(args[0].selector,'article');return {text:'short'};};
 await assert.rejects(()=>client.executeExtractionStep(step),/site_rule_drift/);
});

test('adaptive and compiled extraction share the same validated list rule; interpreted stays excluded',async()=>{
 const {client}=reader();let calls=0;
 const rule={schema:'ai2apps.site-extraction/v1',kind:'list',selector:'#content',origin:'https://example.com',path:'/archives/'};
 client.callJSON=async(_script,args)=>{calls++;assert.equal(args[0].selector,'#content');return {items:[{url:'https://example.com/article',title:'Article title'}]};};
 for(const mode of ['compiled','adaptive']){
  const result=await client.executeExtractionStep({mode,operation:'extract_list',arguments:{site_extraction:rule}});
  assert.equal(result.items.length,1);
 }
 assert.equal(calls,2);
 await assert.rejects(()=>client.executeExtractionStep({mode:'interpreted',operation:'extract_list',arguments:{site_extraction:rule}}),/invalid_extraction_step/);
 await assert.rejects(()=>client.executeExtractionStep({mode:'adaptive',operation:'read_page',arguments:{site_extraction:rule}}),/invalid_extraction_step/);
 assert.equal(calls,2);
});

test('site extraction uses current page for empty scope and independently enforces supplied scope',async()=>{
 const {client}=reader();
 const anchor={href:'https://example.com/article',innerText:'An article title',getAttribute:()=>null,closest:()=>null,getBoundingClientRect:()=>({width:100,height:20})};
 const root={...anchor,querySelectorAll:()=>[anchor]};
 const env={URL,Set,location:{origin:'https://example.com',pathname:'/current/',href:'https://example.com/current/'},document:{querySelectorAll:()=>[root]},getComputedStyle:()=>({visibility:'visible',display:'block'})};
 client.callJSON=async(script,args)=>vm.runInNewContext('('+script+')',env)(args[0]);
 const run=scope=>client.executeExtractionStep({mode:'compiled',operation:'extract_list',arguments:{site_extraction:{schema:'ai2apps.site-extraction/v1',kind:'list',selector:'#content',...scope}}});
 for(const scope of [{},{origin:null,path:null},{origin:'',path:''},{origin:'  ',path:'  '},{origin:'https://example.com'},{path:'/current/'}]){
  const result=await run(scope);assert.equal(result.url,env.location.href);assert.equal(result.items.length,1);
 }
 for(const scope of [{origin:'https://other.com'},{path:'/archives/'},{origin:'https://example.com',path:'/wrong/'}])await assert.rejects(()=>run(scope),/site_rule_drift/);
});
