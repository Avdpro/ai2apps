const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture(){
 let focus=0;const document={body:{style:{overflow:'auto'}},activeElement:{focus(options){assert.equal(options.preventScroll,true);focus++;}}};
 const window={location:{origin:'https://local.fixture'},lucide:{createIcons(){}}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/gallery.js','utf8'),{document,window,URL});
 const app=window.galleryResultViewer();app.$nextTick=fn=>fn();app.$refs={previewDialog:{focus(){}}};app.init();
 return {app,document,focused:()=>focus};
}
test('result sequence selects exact attachment, navigates duplicate resources and restores focus without importing',()=>{
 const {app,document,focused}=fixture();
 app.openResults([{id:'same',previewUrl:'/one',kind:'image'},{id:'same',previewUrl:'/one',kind:'image'},{previewUrl:'/audio',kind:'audio'}],1);
 assert.equal(app.previewPosition,'2 / 3');app.movePreview(1);assert.equal(app.previewAsset.kind,'audio');
 app.closePreview();assert.equal(document.body.style.overflow,'auto');assert.equal(focused(),1);assert.equal(app.assets.length,0);
});
test('untrusted, malformed and executable URLs cannot open the shared viewer',()=>{
 const {app}=fixture();
 for(const previewUrl of ['https://evil.invalid/x','javascript:alert(1)','http://[invalid','data:image/svg+xml;base64,PHN2Zz4=']){
  app.openResults([{previewUrl,kind:'image'}],0);assert.equal(app.previewAsset,null);
 }
 app.openResults([{previewUrl:'data:image/png;base64,YQ==',kind:'image'}],0);assert.equal(app.previewAsset.kind,'image');
 app.closePreview();app.openResults([{previewUrl:'https://evil.invalid/x'},{previewUrl:'/safe'}],0);assert.equal(app.previewAsset,null);
});
