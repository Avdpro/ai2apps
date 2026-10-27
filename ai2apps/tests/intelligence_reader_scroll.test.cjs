const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function reader(){
 const source=fs.readFileSync(__dirname+'/../web/static/js/intelligence.js','utf8');
 const code=source.slice(source.indexOf('const renderedMarkup='),source.indexOf('\nconst esc ='));
 const scroll={scrollTop:0},root={id:'intel-article-reader',dataset:{},scrollLeft:0,innerHTML:'',closest:()=>scroll,querySelectorAll:()=>[]};
 const context={channelId:'channel',selectedId:'a',previewDraft:null};vm.createContext(context);vm.runInContext(code,context);
 return {context,root,scroll,render:html=>context.setHTML(root,html)};
}
test('new article starts at top, including identical authored content',()=>{
 const r=reader();r.render('article A');r.scroll.scrollTop=600;
 r.context.selectedId='b';r.render('article B');assert.equal(r.scroll.scrollTop,0);
 r.scroll.scrollTop=450;r.context.selectedId='c';r.render('article B');assert.equal(r.scroll.scrollTop,0);
});
test('same-article polling preserves position and unchanged markup does not redraw',()=>{
 const r=reader();r.render('article A');r.scroll.scrollTop=600;
 assert.equal(r.render('article A'),false);assert.equal(r.scroll.scrollTop,600);
 r.render('article A with new evidence');assert.equal(r.scroll.scrollTop,600);
});
test('draft and article identities cannot share scroll state; history can restore synchronously',()=>{
 const r=reader();r.render('article A');r.scroll.scrollTop=600;
 r.context.previewDraft={id:'a'};r.render('draft A');assert.equal(r.scroll.scrollTop,0);
 r.context.previewDraft=null;r.render('article A');r.scroll.scrollTop=600;
 assert.equal(r.render('article A'),false);assert.equal(r.scroll.scrollTop,600);
});
