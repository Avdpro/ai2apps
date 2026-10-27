const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require('playwright');
const root=path.join(__dirname,'..'),visibility=fs.readFileSync(path.join(root,'web/static/js/browser_dom_visibility.js'),'utf8');
const articleDocument=fs.readFileSync(path.join(root,'web/static/js/browser_article_document.js'),'utf8');
const helper=JSON.parse(fs.readFileSync(path.join(root,'browser/dom_helpers.json'),'utf8'))['executeExtractionStep:0'];
test('scoped article reads exclude noscript/template and hidden DOM, honor budget and expose truncation',async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{const page=await browser.newPage();
  for(const selector of ['article','.story']){
   const text='Visible article paragraph with facts and context. '.repeat(270);
   await page.setContent('<article class="story"><h1>Article title</h1><p>'+text+'</p><noscript><img src="backup.jpg" srcset="large.jpg 2000w"></noscript><template><p>template-secret</p></template><div style="display:none">hidden-secret</div><div style="opacity:0">transparent-secret</div><pre><code>&lt;img example&gt;</code></pre></article>');
   const run=limit=>page.evaluate(({visibility,articleDocument,helper,selector,limit})=>new Function(visibility+';'+articleDocument+';return ('+helper+')(arguments[0],arguments[1])')({kind:'article',selector},limit),{visibility,articleDocument,helper,selector,limit});
   const full=await run(20000);
   assert.ok(full.text.includes(text));assert.ok(full.text.includes('<img example>'));
   assert.doesNotMatch(full.text,/backup.jpg|srcset|template-secret|hidden-secret|transparent-secret/);
   assert.ok(full.non_content_nodes_removed>=4);assert.ok(full.text.length>10000);assert.equal(full.truncated,false);assert.equal(full.extracted_chars,full.text.length);
   const short=await run(1000);assert.equal(short.text.length,1000);assert.equal(short.truncated,true);assert.equal(short.extracted_chars,full.text.length);assert.equal(short.extraction_limit,1000);
  }
 }finally{await browser.close();}
});
test('shared source document preserves paragraph/image adjacency for Readability output',async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{const page=await browser.newPage();await page.goto('about:blank');
  const blocks=await page.evaluate(({source})=>{return new Function(source+';return ai2appsArticleDocument(arguments[0],1000)')({content:'<h2>Movement</h2><p>Calibre detail.</p><figure><img src="https://cdn.example.org/movement.jpg" alt="Movement"><figcaption>Original caption</figcaption></figure><p>Wrist comfort.</p><img src="data:image/svg+xml,placeholder" data-lazy-src="https://cdn.example.org/wrist.jpg"><noscript><img src="bad.jpg"></noscript>'});},{source:articleDocument});
  assert.deepEqual(blocks.map(b=>b.type),['paragraph','paragraph','image','paragraph','paragraph','image']);
  assert.equal(blocks[2].paragraph_id,blocks[1].id);assert.equal(blocks[5].paragraph_id,blocks[4].id);
  assert.equal(blocks[2].alt,'Movement');assert.equal(blocks[3].text,'Original caption');
 }finally{await browser.close();}
});
