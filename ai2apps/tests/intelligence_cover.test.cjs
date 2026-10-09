const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const sdk=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');
const method=sdk.slice(sdk.indexOf('        async extractLeadImage()'),sdk.indexOf('        async observeExtractionRegions('));
async function extract(metadata={},images=[]){
 const root={querySelectorAll:()=>images};
 const env={URL,location:{href:'https://news.example.com/article'},document:{body:root,querySelector:()=>root,querySelectorAll:s=>(metadata[s]||[]).map(content=>({content}))},getComputedStyle:()=>({display:'block',visibility:'visible'})};
 vm.createContext(env);vm.runInContext('this.client={'+method+'};',env);
 env.client.callJSON=async expression=>vm.runInContext('('+expression+')()',env);
 return env.client.extractLeadImage();
}
function img(url,w=1000,h=700){return {currentSrc:url,naturalWidth:w,naturalHeight:h,closest:()=>null,getBoundingClientRect:()=>({width:w,height:h}),getAttribute:()=>''};}
test('metadata cover resolves relative URLs and preserves signed CDN query',async()=>{
 const r=await extract({'meta[property="og:image"]':['/photo.jpg?sig=a%2Fb&width=1200']},[img('/fallback.jpg')]);
 assert.equal(r.url,'https://news.example.com/photo.jpg?sig=a%2Fb&width=1200');assert.equal(r.method,'metadata');
});
test('unsafe and logo metadata fall back to large article image',async()=>{
 const r=await extract({'meta[property="og:image"]':['http://127.0.0.1/x','/logo.png','data:image/png,foo']},[img('/pixel.gif',1,1),img('/hero.jpg')]);
 assert.equal(r.url,'https://news.example.com/hero.jpg');
});
test('tiny and banner images do not become covers',async()=>{
 assert.equal((await extract({},[img('/tiny.jpg',80,80),img('/banner.jpg',1800,200)])).url,'');
});
test('cover failures cannot fail successful page reads and compiled extraction shares the mechanism',()=>{
 const read=sdk.slice(sdk.indexOf('        async readPage('),sdk.indexOf('        async extractLeadImage('));
 assert(read.indexOf('options.include_cover||options.include_images')>read.indexOf('if(options.site_extraction)'));
 assert.match(read,/try\{page.cover_image=await this.extractLeadImage\(\);[^}]*\}catch/);
});

test('article image gallery includes cover, deduplicates and excludes tiny/ad images',async()=>{
 const r=await extract({'meta[property="og:image"]':['/hero.jpg']},[img('/hero.jpg'),img('/detail.jpg'),img('/detail.jpg'),img('/icon.jpg',30,30),{...img('/ad.jpg'),closest:()=>({})}]);
 assert.deepEqual(Array.from(r.images,i=>i.url),['https://news.example.com/hero.jpg','https://news.example.com/detail.jpg']);
});
test('article image gallery keeps lazy images and caps its size',async()=>{
 const lazy={...img('/placeholder.gif',1,1),getBoundingClientRect:()=>({width:800,height:600}),getAttribute:k=>k==='data-src'?'/real.jpg':''};
 const r=await extract({},[lazy,...Array.from({length:30},(_,i)=>img('/photo'+i+'.jpg'))]);
 assert.equal(r.images.length,24);assert(r.images.some(i=>i.url.endsWith('/real.jpg')));
});
