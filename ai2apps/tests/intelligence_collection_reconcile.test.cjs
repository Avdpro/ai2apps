const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const src=fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/intelligence.js'),'utf8');
for(const mobile of [false,true])test(`foreground reconciliation survives missing events (mobile=${mobile})`,()=>{
 let tick,refreshes=0,cleared=false,closed=false;
 const c={window:{AI2APPS_MOBILE_SURFACE:mobile},document:{hidden:false},queueCollectionRefresh(){refreshes++},setInterval(fn,ms){assert.equal(ms,5000);tick=fn;return 1},clearInterval(){cleared=true},EventSource:class{addEventListener(){}close(){closed=true}},collectionStream:null};
 vm.createContext(c);vm.runInContext(src.slice(src.indexOf('function observeCollections(){'),src.indexOf("window.addEventListener('pagehide',()=>collectionStream")),c);
 c.observeCollections();tick();assert.equal(refreshes,1);c.document.hidden=true;tick();assert.equal(refreshes,1);c.collectionStream.close();assert.ok(cleared);assert.equal(closed,!mobile);
});
