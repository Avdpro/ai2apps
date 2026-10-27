const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
function pager(){const context={window:{},URL};vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/static/js/intelligence_cards.js'),'utf8'),context);return context.window.IntelligencePagination;}
test('list pages start at twenty, advance by twenty, reset filters and retain polling depth',()=>{
 const p=pager(),items=Array.from({length:45},(_,id)=>({id:String(id),updated_at:String(id).padStart(2,'0')}));
 for(const kind of ['articles','entities','drafts','runs','topics','sources','opportunities']){
  const sorted=p.newest(items);assert.equal(sorted[0].id,'44');
  assert.equal(p.page(kind,'channel/filter',sorted).items.length,20);
  p.more(kind);assert.equal(p.page(kind,'channel/filter',sorted).items.length,40);
  assert.equal(p.page(kind,'channel/filter',[...sorted]).items.length,40);
  p.more(kind);const last=p.page(kind,'channel/filter',sorted);assert.equal(last.items.length,45);assert.equal(last.more,false);
  assert.equal(p.page(kind,'channel/other-filter',sorted).items.length,20);
 }
 p.reset();assert.equal(p.page('articles','channel/filter',items).items.length,20);
 assert.equal(p.button('articles',false),'');assert.match(p.button('articles',true),/data-list-more="articles"/);
});
