const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
test('Gallery accepts scoped Imagine Studio artifact references for MP4 without fetching arbitrary URL',async()=>{
 const requests=[];const context={window:{},console,fetch:async(url,options)=>{requests.push({url,options});return {ok:true}}};vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/static/js/gallery.js'),'utf8'),context);
 const app=context.window.galleryApp();app.loadCollections=async()=>{};app.loadAssets=async()=>{};app.fail=error=>{throw error};app.selectedCollectionId='recent';
 const ref={studioId:'ai2apps.imagine-studio',artifactId:'sta_test',appInstanceId:'appi_test'};
 await app.dropFiles({dataTransfer:{getData:type=>type==='application/x-ai2apps-studio-artifact'?JSON.stringify(ref):''}});
 assert.equal(requests.length,1);assert.match(requests[0].url,/imagine-studio\/artifacts\/sta_test\/gallery$/);assert.equal(requests[0].options.headers['X-AI2Apps-App-Instance'],'appi_test');assert.equal(app.busy,false);
});
