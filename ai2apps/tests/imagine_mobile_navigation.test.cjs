const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function app(){const context={window:{innerWidth:390,location:{origin:'http://localhost'}},document:{documentElement:{lang:'zh'}},URL,Blob,console,structuredClone};vm.createContext(context);vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/imagine_studio.js'),'utf8'),context);const a=context.window.imagineStudioApp();a.icons=()=>{};return a;}
test('mobile starts with Mini-App list and ignores desktop panel collapse',()=>{const a=app();assert.equal(a.mobileSurface,'library');a.leftCollapsed=true;a.rightCollapsed=true;assert.equal(a.mobileVisible('library'),true);assert.equal(a.mobileVisible('create'),false);a.mobileViewport=false;assert.equal(a.mobileVisible('create'),true);});
test('shared Output returns to the origin without resetting inputs or results',()=>{const a=app();a.prompt='保留输入';a.runs=[{id:'run'}];a.mobileSurface='create';a.openMobileOutput();assert.equal(a.mobileSurface,'output');a.openMobileOutput();a.mobileBack();assert.equal(a.mobileSurface,'create');assert.equal(a.prompt,'保留输入');assert.equal(a.runs[0].id,'run');a.mobileBack();assert.equal(a.mobileSurface,'library');a.openMobileOutput();a.mobileBack();assert.equal(a.mobileSurface,'library');});
test('reopening active Mini-App while generating does not remount or clear draft',async()=>{const a=app();a.miniAppId='ai2apps.imagine.text-to-image';a.generating=true;a.prompt='Keep';a.saveDraft=()=>assert.fail('must not save/remount');await a.selectMiniApp(a.miniAppId);assert.equal(a.mobileSurface,'create');assert.equal(a.prompt,'Keep');assert.equal(a.generating,true);});
test('cold mobile library does not preload Package or Chat frames; selection mounts once',async()=>{
 const a=app();Object.defineProperty(a,'currentMiniApp',{value:{id:'package',source:'package'}});let mounts=0,chats=0;
 a.mountPackageMiniApp=async()=>{mounts++;a.packageMiniAppId='package';a.packageMiniAppUrl='/package';};a.setupMiniAppChat=()=>chats++;
 await a.initializeMiniAppFrames();assert.equal(mounts,0);assert.equal(chats,0);
 a.miniAppId='package';await a.selectMiniApp('package');assert.equal(mounts,1);assert.equal(a.mobileSurface,'create');
 await a.selectMiniApp('package');assert.equal(mounts,1);
});
test('desktop retains initial Package and Chat loading',async()=>{
 const a=app();a.mobileViewport=false;Object.defineProperty(a,'currentMiniApp',{value:{id:'package',source:'package'}});let mounts=0,chats=0;
 a.mountPackageMiniApp=async()=>mounts++;a.setupMiniAppChat=()=>chats++;
 await a.initializeMiniAppFrames();assert.equal(mounts,1);assert.equal(chats,1);
});

test('empty embedded frame routes remove src rather than navigating to an empty address',()=>{
 const html=fs.readFileSync(require('node:path').join(__dirname,'../web/templates/system_apps/imagine_studio.html'),'utf8');
 for(const key of ['galleryMiniUrl','chatMiniUrl','packageMiniAppUrl']){assert.ok(html.includes(':src="'+key+' || null"'));assert.ok(!html.includes(':src="'+key+'"'));}
});

test('mobile starts without an active Mini-App and rejects Gallery drop without selecting one',async()=>{
 const a=app();assert.equal(a.miniAppId,'');assert.equal(a.hasActiveMiniApp,false);assert.equal(a.currentMiniApp.id,'');assert.equal(a.currentMiniAppReady,false);assert.equal(a.canGenerate,false);
 let touched=false;const event={preventDefault(){touched=true},get dataTransfer(){throw Error('must not read or materialize Gallery data')}};
 a.handleWorkspaceDrag(event);await a.handleGalleryDrop(event);assert.equal(touched,false);assert.equal(a.miniAppId,'');
});
