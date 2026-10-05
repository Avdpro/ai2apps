const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/static/js/todo.js'),'utf8');
const start=source.indexOf('async function attachGalleryAsset('),end=source.indexOf('function galleryDropTarget',start);
function setup({status=200,size=3}={}){
 const calls=[],uploads=[],revealed=[];
 const context=vm.createContext({File,encodeURIComponent,Number,Error,fieldSavePending:0,selectedId:'target-project',revealProjectAttachments:id=>{revealed.push(id);return true;},zh:true,tr:k=>k,notice(){},
 fetch:async url=>{calls.push(url);return {ok:status===200,json:async()=>({name:'asset.png',size_bytes:size}),blob:async()=>new Blob(['abc'],{type:'image/png'})};},
 upload:async(files,id)=>uploads.push({files,id})});
 vm.runInContext(source.slice(start,end),context);
 return {calls,uploads,context,revealed};
}
test('Gallery drop copies content into captured project, using only asset ID',async()=>{
 const h=setup();await h.context.attachGalleryAsset('asset/a','target-project');
 assert.deepEqual(h.calls,['/v1/platform/gallery/assets/asset%2Fa','/v1/platform/gallery/assets/asset%2Fa/content']);
 assert.deepEqual(h.revealed,['target-project','target-project']);assert.equal(h.uploads[0].id,'target-project');assert.equal(h.uploads[0].files[0].name,'asset.png');
 assert.equal(await h.uploads[0].files[0].text(),'abc');
});
test('Gallery forbidden or oversized asset never reaches attachment upload',async()=>{
 for(const config of [{status:403},{size:33*1024*1024}]){const h=setup(config);await assert.rejects(h.context.attachGalleryAsset('asset','target'));assert.equal(h.calls.length,1);assert.equal(h.uploads.length,0);}
});
test('declining a project switch does not import; later navigation is not overridden',async()=>{
 const cancelled=setup();cancelled.context.revealProjectAttachments=()=>false;
 await cancelled.context.attachGalleryAsset('asset','target-project');assert.equal(cancelled.calls.length,0);
 const moved=setup();moved.context.upload=async()=>{moved.context.selectedId='another-project';};
 await moved.context.attachGalleryAsset('asset','target-project');assert.deepEqual(moved.revealed,['target-project']);
});
