const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function setup(){
 const context={window:{getComputedStyle:()=>({})},console};vm.createContext(context);
 vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/gallery.js','utf8'),context);
 const app=context.window.galleryApp();app.previewAsset={kind:'image'};
 app.$refs={previewImage:{clientWidth:400,clientHeight:400,naturalWidth:400,naturalHeight:400,parentElement:{clientWidth:400,clientHeight:400},getBoundingClientRect:()=>({left:app.previewPanX, right:400+app.previewPanX,top:app.previewPanY,bottom:400+app.previewPanY})}};
 const captured=new Set(),target={setPointerCapture:id=>captured.add(id),hasPointerCapture:id=>captured.has(id),releasePointerCapture:id=>captured.delete(id)};
 const e=(id,x,y=200)=>({pointerId:id,clientX:x,clientY:y,button:0,currentTarget:target,preventDefault(){}});
 return {app,e,captured};
}
test('pinch scales around fingers, pans, and continues with one finger without jumping',()=>{
 const {app:a,e}=setup();a.startPreviewPan(e(1,150));a.startPreviewPan(e(2,250));
 a.movePreviewPan(e(2,350));assert.equal(a.previewZoom,2);assert.equal(a.previewPanX,50);
 a.endPreviewPan(e(2,350));a.movePreviewPan(e(1,160));assert.equal(a.previewPanX,60);
 a.endPreviewPan(e(1,160));assert.equal(a.previewPanStart,null);
});
test('off-center pinch keeps touched image coordinate anchored',()=>{
 const {app:a,e}=setup();a.startPreviewPan(e(1,200));a.startPreviewPan(e(2,300));a.movePreviewPan(e(2,400));
 assert.equal(a.previewZoom,2);assert.equal(a.previewPanX,0);
 // Original point 250 maps to the new midpoint 300.
 assert.equal(200+(250-200)*a.previewZoom+a.previewPanX,300);
});
test('zoom is bounded and reset ignores old captured pointer moves',()=>{
 const {app:a,e}=setup();a.startPreviewPan(e(1,150));a.startPreviewPan(e(2,250));
 a.movePreviewPan(e(2,3000));assert.equal(a.previewZoom,6);
 a.movePreviewPan(e(2,151));assert.equal(a.previewZoom,.25);
 a.resetPreviewTransform();a.movePreviewPan(e(1,500));assert.equal(a.previewZoom,1);assert.equal(a.previewPanX,0);assert.equal(Object.keys(a.previewPointers).length,0);
});
test('capture loss/cancel is idempotent; mouse still pans; other media is untouched',()=>{
 const {app:a,e,captured}=setup();a.startPreviewPan(e(1,150));a.movePreviewPan(e(1,170));assert.equal(a.previewPanX,20);
 a.endPreviewPan(e(1,170));a.endPreviewPan(e(1,170));assert.equal(captured.size,0);
 a.previewAsset.kind='video';a.startPreviewPan(e(2,100));assert.equal(Object.keys(a.previewPointers).length,0);
});
test('shared viewport owns gestures including capture loss, only images disable browser gestures',()=>{
 const template=fs.readFileSync(__dirname+'/../web/templates/system_apps/_gallery_preview_dialog.html','utf8');
 assert.match(template,/<div class="gallery-preview-media"[^>]*@pointerdown="startPreviewPan/);
 assert.match(template,/@lostpointercapture="endPreviewPan/);
 const css=fs.readFileSync(__dirname+'/../web/static/css/gallery.css','utf8');assert.match(css,/\.gallery-preview-media\.image\{touch-action:none/);
});
