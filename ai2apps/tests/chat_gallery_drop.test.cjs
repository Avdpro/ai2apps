const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {File}=require('node:buffer');
const html=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');
function setup(fetch){
 const notices=[],images=[],calls=[];
 const context={window:{t:k=>k},fetch:async(...args)=>{calls.push(args);return fetch(...args);},File,Date,Math,alert:m=>notices.push(m)};
 vm.createContext(context);
 vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/gallery_picker.js','utf8'),context);
 const source=html.slice(html.indexOf('    async handleDrop(event)'),html.indexOf('    handleImageSelect(event)'));
 const methods=vm.runInContext('({'+source+'})',context);
 const app={...methods,uploadDocuments:[],chatSettings:{maxImageSizeMb:10},hasVisionSupport:()=>true,loadImageFile:f=>images.push(f)};
 return {app,images,notices,calls};
}
const metadata={id:'img1',name:'real.png',media_type:'image/png',size_bytes:3};
const response=async url=>url.endsWith('/content')?{ok:true,blob:async()=>new Blob(['png'])}:{ok:true,json:async()=>metadata};
const drop=ids=>({dataTransfer:{files:[],getData:t=>t==='application/x-ai2apps-gallery-assets'?JSON.stringify(ids):t==='text/uri-list'?'https://untrusted.invalid/image':''}});
test('Gallery ID-only image drops enter the existing vision flow once with trusted metadata',async()=>{
 const {app,images,calls,notices}=setup(response);
 await app.handleDrop(drop(['img1','img1']));
 assert.equal(images.length,1);assert.equal(images[0].name,'real.png');assert.equal(images[0].type,'image/png');
 assert.equal(app.uploadDocuments.length,0);assert.equal(notices.length,0);
 assert.deepEqual(calls.map(c=>c[0]),['/v1/platform/gallery/assets/img1','/v1/platform/gallery/assets/img1/content']);
 assert.ok(calls.every(c=>c[1].credentials==='same-origin'));
});
test('loading is pending and removing or changing drafts does not resurrect an attachment',async()=>{
 for(const cancel of [a=>a.uploadDocuments.splice(0),a=>a.uploadDocuments=[]]){
  let release;const {app,images,calls}=setup(url=>new Promise(done=>{release=()=>done({ok:true,json:async()=>metadata});}));
  const pending=app.handleDrop(drop(['img1']));assert.equal(app.uploadDocuments[0]._pending,true);
  cancel(app);release();await pending;assert.equal(images.length,0);assert.equal(calls.length,1);assert.equal(app.uploadDocuments.length,0);
 }
});
test('denied, malformed and oversized references report an error without a stale pending item',async()=>{
 for(const fetch of [async()=>({ok:false,status:403}),async()=>({ok:true,json:async()=>({...metadata,size_bytes:20*1024**2})})]){
  const {app,images,notices,calls}=setup(fetch);await app.handleDrop(drop(['img1']));
  assert.equal(images.length,0);assert.equal(app.uploadDocuments.length,0);assert.equal(notices.length,1);assert.equal(calls.length,1);
 }
 const {app,notices,calls}=setup(response);await app.handleDrop({dataTransfer:{getData:()=>'{broken',files:[]}});
 assert.equal(notices.length,1);assert.equal(calls.length,0);
});
test('normal file drops remain supported; non-vision models keep Gallery images as file references',async()=>{
 const {app,images}=setup(response);await app.handleDrop({dataTransfer:{files:[new File(['x'],'local.png',{type:'image/png'})],getData:()=>''}});assert.equal(images.length,1);
 app.hasVisionSupport=()=>false;await app.handleDrop(drop(['img1']));
 assert.equal(images.length,1);assert.equal(app.uploadDocuments.length,1);assert.equal(app.uploadDocuments[0].file.name,'real.png');
});
