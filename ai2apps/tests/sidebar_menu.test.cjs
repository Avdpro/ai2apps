const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../browser/sidebar_menu.js'), 'utf8');
function harness({scheme='https', confirmed=true, failed=0}={}) {
  const calls=[];
  const context = vm.createContext({
    topWindow:{gBrowser:{selectedBrowser:{currentURI:{scheme}}}},
    window:{}, console,
    sidebarStrings:{deleteData:'Delete',deleteDataConfirm:'Clear {domain}',deleteDataSuccess:'Done {domain}',deleteDataFailed:'Failed'},
    Services:{eTLD:{getSchemelessSite:()=> 'example.test'},prompt:{confirm:()=>confirmed,alert:(_w,_t,message)=>calls.push(['alert',message])},clearData:{deleteDataFromSite:(...args)=>{calls.push(['clear',...args.slice(0,4)]);args[4](failed);}}},
    Ci:{nsIClearDataService:{CLEAR_COOKIES_AND_SITE_DATA:1,CLEAR_ALL_CACHES:2}},
    refreshContext:async()=>calls.push(['refresh']),
  });
  vm.runInContext(source,context);
  return {context,calls};
}
test('native clear is scoped and refreshes only after successful cleanup',async()=>{
 const {context,calls}=harness(); await vm.runInContext('clearSidebarSiteData("example.test")',context);
 assert.equal(calls[0][1],'example.test'); assert.equal(calls[0][3],true);assert.equal(calls[0][4],3);
 assert.equal(calls[1][0],'refresh');assert.deepEqual(calls[2],['alert','Done example.test']);
});
test('internal pages, changed sites and cancelled requests never delete data',async()=>{
 for(const options of [{scheme:'about'}, {confirmed:false}]){
  const {context,calls}=harness(options);await vm.runInContext('clearSidebarSiteData("example.test")',context);assert.equal(calls.length,0);
 }
 const {context,calls}=harness();await vm.runInContext('clearSidebarSiteData("other.test")',context);assert.equal(calls.length,0);
});
test('partial failures are reported without claiming success',async()=>{
 const {context,calls}=harness({failed:1});await vm.runInContext('clearSidebarSiteData("example.test")',context);
 assert.equal(calls.some(c=>c[0]==='refresh'),false);assert.deepEqual(calls.at(-1),['alert','Failed']);
});
