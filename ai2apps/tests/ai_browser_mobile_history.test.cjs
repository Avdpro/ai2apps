const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function fixture(mobile=true){
 const events={},entries=[{other:'preserved'}];let index=0,resolveMount;
 const history={get state(){return entries[index]},replaceState(s){entries[index]=s},pushState(s){entries.splice(++index);entries[index]=s},back(){if(index>0)events.popstate({state:entries[--index]})},forward(){if(index+1<entries.length)events.popstate({state:entries[++index]})}};
 const element={append(){},classList:{toggle(){}}};
 const context={history,crypto:{randomUUID:()=> 'id'},window:{AI2APPS_MOBILE_SURFACE:mobile,innerWidth:1000,addEventListener:(k,f)=>events[k]=f,AI2AppsStudioMiniApps:{mount:()=>new Promise(resolve=>resolveMount=resolve)}},document:{getElementById:()=>element,createElement:()=>({style:{}})},Map};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/ai_browser.js','utf8'),context);
 const app=context.aiBrowserApp();app.miniApps=[{id:'search-all',name:'Search'}];
 return {app,history,entries,finish:()=>resolveMount({content_url:'/mini-app/search'})};
}
test('Mini-App records a list entry before asynchronous mount; native history restores both surfaces',async()=>{
 const f=fixture(),opening=f.app.openMiniApp(f.app.miniApps[0]);
 assert.equal(f.entries.length,2);assert.equal(f.entries[0].aiBrowserMiniApp,null);assert.equal(f.entries[1].other,'preserved');
 f.history.back();assert.equal(f.app.mobileSurface,'apps');
 f.history.forward();assert.equal(f.app.mobileSurface,'workspace');
 f.history.back();f.finish();await opening;
 assert.equal(f.app.mobileSurface,'apps');assert.equal(f.app.frames.get('mini-app:search-all').frame.style.display,'none');
 f.history.forward();assert.equal(f.app.mobileSurface,'workspace');assert.equal(f.app.frames.size,1);
 f.app.mobileBack();assert.equal(f.app.mobileSurface,'apps');assert.equal(f.entries.length,2);
});
test('warm Mini-App reopening adds one entry; refresh does not add duplicates',async()=>{
 const f=fixture(),opening=f.app.openMiniApp(f.app.miniApps[0]);f.finish();await opening;
 await f.app.openMiniApp(f.app.miniApps[0]);assert.equal(f.entries.length,2);
 f.app.mobileBack();await f.app.openMiniApp(f.app.miniApps[0]);assert.equal(f.entries.length,2);assert.equal(f.app.mobileSurface,'workspace');
});
test('desktop Mini-App navigation does not change browser history',async()=>{
 const f=fixture(false),opening=f.app.openMiniApp(f.app.miniApps[0]);f.finish();await opening;assert.equal(f.entries.length,1);assert.equal(f.app.mobileHistoryReady,false);
});

test('hosted Mini-App opening delegates to Shell without mutating the library',async()=>{
 const f=fixture();let requested;
 f.app.shellBrowserNavigation=(action,id)=>{requested={action,id};return true;};
 await f.app.openMiniApp(f.app.miniApps[0]);
 assert.deepEqual(requested,{action:'open',id:'search-all'});assert.equal(f.app.mobileSurface,'apps');assert.equal(f.entries.length,1);assert.equal(f.app.frames.size,0);
 f.app.mobileSurface='workspace';f.app.mobileBack();assert.equal(requested.action,'back');
});
