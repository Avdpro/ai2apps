const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/intelligence.js','utf8');
function setup(mobile=false){
 const open={dataset:{imagePosition:'1'}},root={innerHTML:'',querySelectorAll:()=>[open]},status={},error={},calls=[];
 const draft={id:'d',kind:'short_post',revision:1,title:'Post',evidence:[{id:'a'}],current:{title:'Post',content:'Body [1]'}};
 const env={state:{articles:[{id:'a',title:'Source',images:[{url:'https://example.com/1.jpg'},{url:'https://example.com/2.jpg'}]}]},writingSession:{channelId:'c',draft,pending:false},window:{AI2APPS_MOBILE_SURFACE:mobile,IntelligenceCards:{imageURL:(a,url)=>url}},Set,Number,lt:s=>s,it:(parts,...v)=>parts.reduce((s,p,i)=>s+p+(v[i]??''),''),esc:s=>String(s??''),link:s=>s||'#',safe:fn=>fn,$:id=>id==='#writing-content'?root:id==='#writing-error'?error:status,loadDrafts:async()=>{},api:async(path,method,body)=>{calls.push({path,method,body});if(env.fail)throw Error('Save failed');return {...env.writingSession.draft,revision:body.revision+1,images:body.images};}};
 vm.createContext(env);vm.runInContext(source.slice(source.indexOf('function writingParagraphs('),source.indexOf('\nfunction renderWriting(){')),env);
 env.renderWriting=()=>env.renderWritingImages(env.writingSession.draft);env.renderWriting();
 const select=async(index,checked)=>{const input={value:String(index),checked,closest:selector=>selector==='details'?{dataset:{imagePosition:'1'}}:input};await root.onchange({target:input});};
 return {env,root,calls,status,error,select};
}
test('checking inserts and saves immediately, retaining open picker and revision',async()=>{
 const t=setup();await t.select(0,true);
 assert.equal(t.calls.length,1);assert.equal(t.calls[0].method,'PUT');assert.equal(t.calls[0].body.images[0].url,'https://example.com/1.jpg');
 assert.equal(t.env.writingSession.draft.revision,2);assert.match(t.root.innerHTML,/data-image-position="1" open/);assert.match(t.root.innerHTML,/value="0" checked/);
 assert.match(t.env.writingMarkdown(t.env.writingSession.draft),/!\[\]\(<https:\/\/example.com\/1.jpg>\)/);
 await t.select(1,true);assert.equal(t.env.writingSession.draft.images.length,2);
 await t.select(0,false);assert.equal(t.env.writingSession.draft.images.length,1);assert.equal(t.env.writingSession.draft.images[0].url,'https://example.com/2.jpg');
 assert(!t.root.innerHTML.includes('data-insert-draft-images'));
});
test('failed save restores persisted selection and reports failure',async()=>{
 const t=setup();await t.select(0,true);t.env.fail=true;await t.select(1,true);
 assert.equal(t.env.writingSession.draft.revision,2);assert.equal(t.env.writingSession.draft.images.length,1);
 assert.match(t.root.innerHTML,/value="0" checked/);assert(!t.root.innerHTML.includes('value="1" checked'));
 assert.equal(t.error.textContent,'Save failed');assert.match(t.status.textContent,/已恢复原有图片/);assert.equal(t.env.writingSession.pending,false);
});
test('selection order, badges and Markdown follow click order; reorder preserves placement',async()=>{
 const t=setup(true);await t.select(1,true);await t.select(0,true);
 let d=t.env.writingSession.draft;
 assert.equal(d.images[0].url,'https://example.com/2.jpg');assert.equal(d.images[1].url,'https://example.com/1.jpg');
 assert.match(t.root.innerHTML,/value="0" checked[\s\S]*?aria-label="图片顺序 2"/);
 const next=t.env.reorderWritingImage(d,1,0,false);assert.equal(next[0].url,'https://example.com/1.jpg');
 const long={...d,kind:'long_article',current:{title:'Post',content:'First\n\nSecond'},images:[{...d.images[0],before:'First'},{...d.images[1],before:''}]};
 const moved=t.env.reorderWritingImage(long,1,0,false);assert.equal(moved[0].before,'First');
 const markdown=t.env.writingMarkdown(d);assert(markdown.indexOf('/2.jpg')<markdown.indexOf('/1.jpg'));
 assert.equal(t.env.reorderWritingImage(d,0,0,false),null);
});

test('order badges exist only inside Mobile selection thumbnails, never inserted figures',async()=>{
 for(const mobile of [true,false]){
  const t=setup(mobile);await t.select(0,true);
  assert.equal(t.root.innerHTML.includes('class="intel-image-order"'),mobile);
  const figures=t.root.innerHTML.match(/<figure[\s\S]*?<\/figure>/g)||[];
  assert.equal(figures.length,1);assert(!figures[0].includes('intel-image-order'));
  assert(figures[0].includes('data-draft-image-drag'));
 }
});
