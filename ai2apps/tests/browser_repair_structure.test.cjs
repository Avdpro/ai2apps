const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
const snapshot=fs.readFileSync(__dirname+'/../web/static/js/browser_snapshot.js','utf8');
const visible=fs.readFileSync(__dirname+'/../web/static/js/browser_dom_visibility.js','utf8');
async function probe(page,maxItems=600){return page.evaluate(({snapshot,visible,maxItems})=>{
 const fn=new Function('ai2appsDOMVisible','options','return ('+snapshot+')(options)');
 return fn(new Function('return ('+visible+')')(),{maxItems,maxText:1000,maxHtml:10000,htmlMode:'visible'});
},{snapshot,visible,maxItems});}
test('real DOM structure identity ignores geometry but changes with wrappers; bounded completeness',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{const page=await browser.newPage();await page.setContent('<main><span role="button">Preview</span><button>Cancel</button></main>');
 const first=await probe(page);assert.equal(first.controls_truncated,false);assert.ok(first.items[0].structure);
 await page.locator('main').evaluate(n=>n.style.marginTop='100px');
 const moved=await probe(page);assert.equal(first.items[0].structure,moved.items[0].structure);assert.notDeepEqual(first.items[0].rect,moved.items[0].rect);
 await page.locator('span').evaluate(n=>{const wrap=document.createElement('section');n.before(wrap);wrap.append(n);});
 const wrapped=await probe(page);assert.notEqual(first.items[0].structure,wrapped.items[0].structure);
 const partial=await probe(page,1);assert.equal(partial.controls_truncated,true);
 await page.setContent('<div>'.repeat(40)+'<button>Deep</button>'+'</div>'.repeat(40));
 const deep=await probe(page);assert.equal(deep.items[0].structure,null);
 }finally{await browser.close();}
});
