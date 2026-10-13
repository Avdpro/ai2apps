const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const visibility=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8');
const source=fs.readFileSync(__dirname+'/../browser/search.py','utf8').split("r'''")[1].split("'''")[0];
function read(provider,entries,{fallback=false,path=provider==='duckduckgo'?'/':'/search',body='',excludeAds=true}={}){
 const host={google:'www.google.com',bing:'www.bing.com',duckduckgo:'duckduckgo.com',brave:'search.brave.com'}[provider];
 const headings=entries.map(([title,href,ad=false,hidden=false])=>({parentElement:hidden?{getAttribute:k=>k==='aria-hidden'?'true':null}:null,innerText:title,getBoundingClientRect:()=>({width:100,height:20}),closest:selector=>selector==='a[href]'?{href}:selector.includes('data-text-ad')&&ad?{}:null,querySelector:()=>null}));
 const context={URL,Uint8Array,TextDecoder,atob,location:{hostname:host,pathname:path,href:`https://${host}${path}`},document:{title:'Search',body:{innerText:body},querySelectorAll:selector=>fallback&&selector!=='h2,h3'?[]:headings},getComputedStyle:()=>({display:'block',visibility:'visible'})};
 return vm.runInNewContext(`${visibility};(${source})`,context)(provider,10,'query',excludeAds);
}
test('Google semantic fallback decodes redirect links and excludes ads, navigation and duplicates',()=>{
 const output=read('google',[
  ['Article','https://www.google.com/url?q=https%3A%2F%2Fexample.org%2Farticle'],
  ['Duplicate','https://example.org/article#section'],
  ['Search','https://www.google.com/search?q=other'],
  ['Sponsored','https://ads.example.org',true]],{fallback:true});
 assert.equal(output.items.length,1);assert.equal(output.items[0].url,'https://example.org/article');assert.equal(output.items[0].title,'Article');
});
test('Bing result redirects decode to direct article URLs',()=>{
 const href='https://www.bing.com/ck/a?u=a1'+Buffer.from('https://example.org/文章').toString('base64url');
 const output=read('bing',[['文章',href]]);assert.equal(output.provider,'bing');assert.equal(output.items.length,1);assert.equal(output.items[0].url,new URL('https://example.org/文章').href);
});
test('unexpected page and empty markup return no valid results',()=>{
 assert.equal(read('google',[],{path:'/sorry/'}).reason,'captcha');
 assert.equal(read('bing',[]).reason,'no_valid_search_results');
});
test('Google opaque signed article redirects remain usable observed links',()=>{
 const url='https://www.google.com/goto?url=CAESsigned';
 const output=read('google',[['Article',url],['Search settings','https://www.google.com/preferences']]);
 assert.equal(output.items.length,1);assert.equal(output.items[0].url,url);
});
test('DuckDuckGo decodes observed uddg destinations and rejects unsafe and internal links',()=>{
 const output=read('duckduckgo',[
  ['Article','https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.org%2Farticle'],
  ['Duplicate','https://example.org/article'],
  ['Settings','https://duckduckgo.com/settings'],
  ['Unsafe','https://duckduckgo.com/l/?uddg=javascript%3Aalert(1)'],
  ['Credential','https://user:pass@example.org/']]);
 assert.equal(output.provider,'duckduckgo');assert.equal(output.items.length,1);assert.equal(output.items[0].url,'https://example.org/article');
});
test('Brave semantic fallback reads external results and excludes its navigation and ads',()=>{
 const output=read('brave',[['Article','https://example.org/article'],['Search','https://search.brave.com/search?q=other'],['Ad','https://ads.example.org',true]],{fallback:true});
 assert.equal(output.provider,'brave');assert.equal(output.items.length,1);assert.equal(output.items[0].title,'Article');
});
test('new engines distinguish verification, genuine empty results, and unrecognized pages',()=>{
 for(const provider of ['duckduckgo','brave']){
  assert.equal(read(provider,[],{body:'Verify you are human'}).classification,'needs_user');
  assert.equal(read(provider,[],{body:'No results found'}).empty,true);
  assert.equal(read(provider,[]).reason,'no_valid_search_results');
  assert.equal(read(provider,[],{path:'/settings'}).reason,'unexpected_search_page');
 }
});

test('ad exclusion is optional and observed ad markers survive when disabled',()=>{
 const entries=[['Article','https://example.org/a'],['Sponsored','https://ads.example.org/a',true]];
 assert.equal(read('google',entries).items.length,1);const kept=read('google',entries,{excludeAds:false});assert.equal(kept.items.length,2);assert.equal(kept.items[1].is_ad,true);
});

for(const provider of ['google','bing','duckduckgo','brave'])test(provider+' ignores hidden duplicate result ancestors before deduplication',()=>{const r=read(provider,[['Hidden','https://example.org/same',false,true],['Visible','https://example.org/same']]);assert.equal(r.items.length,1);assert.equal(r.items[0].title,'Visible');});
test('Google sorry verification page requests human assistance before search-path validation',()=>{
 const value=read('google',[],{path:'/sorry/index',body:'Our systems have detected unusual traffic'});
 assert.equal(value.classification,'needs_user');assert.equal(value.reason,'captcha');assert.equal(value.assistance_kind,'captcha');assert.equal(value.items.length,0);
});
