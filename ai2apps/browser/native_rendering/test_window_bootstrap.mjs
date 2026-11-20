// Run the actual generic native opener method with controlled chrome windows.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=fs.readFileSync(process.argv[2]+'/remote/shared/WindowManager.sys.mjs','utf8');
const start=source.indexOf('  async openBrowserWindow(options = {}) {');
const method=source.slice(start,source.indexOf('\n  }',start)+4);
const browserWindow={kind:'browser'},chromeWindow={kind:'chrome'},opened={kind:'opened'};
for(const normal of [browserWindow,null]){
 const calls=[];
 const instance=vm.runInNewContext(`new(class {${method}\nasync focusWindow(w){calls.push(['focus',w]);} async waitForChromeWindowLoaded(w){calls.push(['ready',w]);}})`,{
  calls,Services:{wm:{getMostRecentBrowserWindow:()=>normal,getMostRecentWindow:()=>chromeWindow}},
  lazy:{AppInfo:{name:'Firefox'},error:{UnsupportedOperationError:Error},
   UserContextManager:{getInternalIdById:id=>id},URILoadingHelper:{openTrustedLinkIn(opener,url,where,options){calls.push(['open',opener,url,where,options.userContextId]);options.resolveOnContentBrowserCreated({documentGlobal:opened});}}}
 });
 assert.equal(await instance.openBrowserWindow({userContextId:'owned-context'}),opened);
 assert.equal(calls[0][1],normal||chromeWindow);assert.equal(calls[0][4],'owned-context');
 assert.equal(calls[1][1],normal||chromeWindow);assert.equal(calls[2][1],opened);
}
console.log('Native window opener checks passed: ordinary browser preference / chrome-only cold host / context preservation');
