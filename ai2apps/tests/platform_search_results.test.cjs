const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../browser/search.py','utf8').split("r'''")[1].split("'''")[0];
function read(provider,entries,{fallback=false,path='/search'}={}){
 const host=provider==='google'?'www.google.com':'www.bing.com';
 const headings=entries.map(([title,href,ad=false])=>({innerText:title,getBoundingClientRect:()=>({width:100,height:20}),closest:selector=>selector==='a[href]'?{href}:selector.includes('header')&&ad?{}:null,querySelector:()=>null}));
 const context={URL,Uint8Array,TextDecoder,atob,location:{hostname:host,pathname:path,href:`https://${host}${path}`},document:{title:'Search',querySelectorAll:selector=>fallback&&selector!=='h2,h3'?[]:headings},getComputedStyle:()=>({display:'block',visibility:'visible'})};
 return vm.runInNewContext(`(${source})`,context)(provider,10,'query');
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
 assert.equal(read('google',[],{path:'/sorry/'}).reason,'unexpected_search_page');
 assert.equal(read('bing',[]).reason,'no_valid_search_results');
});
