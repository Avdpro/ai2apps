const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function setup(fetch){const notices=[];const context={window:{location:{origin:'http://localhost:56743'}},document:{querySelectorAll:()=>[{contentWindow:{postMessage:(...x)=>notices.push(x)}}]},URL,fetch,FormData,console};vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/chat_image_actions.js','utf8'),context);return {actions:context.window.AI2AppsChatImages,context,notices};}
test('Gallery button imports original Session artifact without fetching image bytes or temporary display URL',async()=>{
 const calls=[];const {actions,notices}=setup(async(url,options)=>{calls.push({url,options});return {ok:true};});
 await actions.addToGallery('/v1/platform/sessions/ses_one/artifacts/art_one/download','key');
 assert.equal(calls.length,1);assert.equal(calls[0].url,'/v1/platform/gallery/assets/import-artifact/ses_one/art_one');assert.equal(JSON.parse(calls[0].options.body).sourceAppId,'ai2apps.general-chat');assert.equal(notices.length,1);
});
test('drag carries only scoped artifact reference and Gallery imports into selected collection',async()=>{
 const {actions}=setup();const data={};actions.drag({dataTransfer:{clearData(){},setData:(k,v)=>data[k]=v}},'/v1/platform/sessions/ses_one/artifacts/art_one/download');
 assert.equal(JSON.parse(data['application/x-ai2apps-session-artifact']).artifactId,'art_one');
 const calls=[];const ctx={window:{},console,FormData,fetch:async(url,options)=>{calls.push({url,options});return {ok:true,json:async()=>({})};}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/gallery.js','utf8'),ctx);const gallery=ctx.window.galleryApp();gallery.selectedCollectionId='col_selected';gallery.loadCollections=async()=>{};gallery.loadAssets=async()=>{};gallery.fail=e=>{throw e;};
 await gallery.dropFiles({dataTransfer:{getData:k=>data[k]||''}});
 assert.equal(calls.length,1);assert.equal(calls[0].url,'/v1/platform/gallery/assets/import-artifact/ses_one/art_one');assert.equal(JSON.parse(calls[0].options.body).collectionId,'col_selected');assert.equal(gallery.busy,false);
});
test('foreign lookalike URLs never become local artifact references or receive API credentials',async()=>{
 const calls=[];const {actions}=setup(async(url,options)=>{calls.push({url,options});return {ok:false,status:403,json:async()=>({error:{message:'denied'}})};});
 assert.equal(actions.reference('https://foreign.example/v1/platform/sessions/a/artifacts/b/download'),null);
 await assert.rejects(()=>actions.save('https://foreign.example/photo.png','private-key'),/denied/);assert.equal(Object.keys(calls[0].options.headers).length,0);assert.equal(calls[0].options.credentials,'omit');
 let prevented=false;actions.drag({preventDefault(){prevented=true;},dataTransfer:{clearData(){},setData(){}}},'blob:http://localhost:56743/expired');assert.equal(prevented,true);
});
test('import errors retain backend reason and do not refresh Gallery',async()=>{
 const {actions,notices}=setup(async()=>({ok:false,status:403,json:async()=>({error:{message:'Session access denied'}})}));
 await assert.rejects(()=>actions.addToGallery('/v1/platform/sessions/s/artifacts/a/download','key'),/Session access denied/);assert.equal(notices.length,0);
});
test('save downloads authenticated original bytes and cleans up its temporary URL',async()=>{
 const calls=[];const {actions,context}=setup(async(url,options)=>{calls.push({url,options});return {ok:true,blob:async()=>({type:'image/png'})};});
 let clicked=false,removed=false,revoked='';const link={click(){clicked=true;},remove(){removed=true;}};
 context.document.body={append(value){assert.equal(value,link);}};context.document.createElement=()=>link;context.URL=class extends URL {static createObjectURL(){return 'blob:download';}static revokeObjectURL(value){revoked=value;}};
 let cleanup;context.setTimeout=fn=>cleanup=fn;
 await actions.save('/v1/platform/sessions/s/artifacts/a/download','local-key');
 assert.equal(calls[0].options.headers.Authorization,'Bearer local-key');assert.equal(link.download,'chat-image.png');assert.equal(clicked,true);assert.equal(removed,true);cleanup();assert.equal(revoked,'blob:download');
});
