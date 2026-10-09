const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/intelligence.js','utf8');
test('thumbnail gallery includes lead once, escapes captions and binds original source Profile',()=>{
 const env={window:{},URL,state:{sources:[{id:'s',name:'source',channel_id:'c',profile_key:'specific'}]},link:s=>s||'#',esc:s=>String(s||'').replaceAll('<','&lt;').replaceAll('"','&quot;')};Object.assign(env,require('./intelligence_test_env.cjs'));vm.createContext(env);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/intelligence_cards.js','utf8'),env);
 vm.runInContext(source.slice(source.indexOf('function articleImages(article)'),source.indexOf('async function extractArticleImages(')),env);
 const article={channel_id:'c',title:'<title>',sources:[{source_id:'s',url:'https://example.com/a'}],cover_image:{url:'https://cdn.example.com/lead.jpg',source_url:'https://example.com/a'},images:[{url:'https://cdn.example.com/lead.jpg'},{url:'https://cdn.example.com/detail.jpg',alt:'<caption>',source_url:'https://example.com/a'}]};
 assert.equal(env.articleImages(article).length,2);assert.match(env.articleImagesHTML(article),/data-image-index="1"/);assert.match(env.articleImagesHTML(article),/&lt;caption>/);
 assert.equal(env.imageSource(article,article.images[1]).profile_key,'specific');
 assert.throws(()=>env.imageSource(article,{source_url:'https://other.com/a'}));
});
test('exact Gallery transfer imports selected full image instead of lazy placeholder',async()=>{
 const sdk=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');
 const requested='https://cdn.example.com/watch.jpg',placeholder='data:image/svg+xml,placeholder',fetched=[];
 const media={currentSrc:placeholder,src:placeholder,getAttribute:k=>k==='data-src'?requested:null,closest:()=>null};
 const env={URL,Blob,Uint8Array,crypto:{randomUUID:()=> 'transfer'},location:{href:'https://news.example.com/a'},window:{},document:{querySelectorAll:()=>[media]},fetch:async url=>{fetched.push(url);return {ok:true,blob:async()=>new Blob(['image'],{type:url===requested?'image/jpeg':'image/svg+xml'})};}};
 Object.assign(env,require('./intelligence_test_env.cjs'));vm.createContext(env);vm.runInContext('this.client={'+sdk.slice(sdk.indexOf('        async beginPageResourceTransfer('),sdk.indexOf('        async readPageResourceChunk('))+'};',env);
 env.client.callJSON=async(expression,args)=>{env.args=args;return vm.runInContext('('+expression+')(...args)',env);};
 const exact=await env.client.beginPageResourceTransfer([requested],1024,true);
 assert.equal(exact.url,requested);assert.equal(exact.media_type,'image/jpeg');assert.deepEqual(fetched,[requested]);
});
