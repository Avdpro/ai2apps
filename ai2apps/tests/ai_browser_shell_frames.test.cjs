const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/mobile.js','utf8');
function fixture(appId='ai2apps.ai-browser'){
 const list={src:'https://device.test/mobile/app-content/browser#ai2apps-mount=t&ai2apps-instance=i',contentWindow:{},hidden:false};
 const record={frame:list,token:'t',instanceId:'i',renderer:'trusted'},children=[],states=[];
 const c={window:{},URL,URLSearchParams,location:{href:'https://device.test/mobile#app=ai2apps.ai-browser',origin:'https://device.test'},frames:new Map([[appId,record]]),activeAppId:appId,document:{createElement:()=>({contentWindow:{},remove(){this.removed=true}})},frameHost:{appendChild:f=>children.push(f)},history:{state:{appId:'ai2apps.ai-browser'},pushState(s){this.state=s;states.push(s)},back(){states.push('back')}},loading:{},errorView:{}};
 c.pendingAppNavigation=null;vm.createContext(c);const a=source.indexOf('    function mobileMiniAppNavigation(');vm.runInContext(source.slice(a,source.indexOf('    // Todo-only',a)),c);
 const b=source.indexOf("        const browserRecord=frames.get(appId);");vm.runInContext('function pop(event){const appId=event.state.appId;'+source.slice(b,source.indexOf("        const intelRecord=",b))+'}',c);
 return {c,list,record,children,states,nav:(action,id,sender=list.contentWindow,token='t')=>(appId!=='ai2apps.ai-browser'?c.window.ai2appsMobileStudioNavigation:c.window.ai2appsMobileBrowserNavigation)(sender,token,'i',action,id,appId)};
}
test('Shell sibling frame retains library; native back/forward only changes outer visibility',()=>{
 const f=fixture();assert.equal(f.nav('open','search-all'),true);const detail=f.record.browserDetail.frame;
 assert.equal(f.list.hidden,true);assert.equal(detail.hidden,false);assert.equal(f.states[0].browserMiniApp,'search-all');assert.equal(new URLSearchParams(new URL(detail.src).hash.slice(1)).get('ai2apps-browser-detail'),'search-all');
 f.c.pop({state:{appId:'ai2apps.ai-browser'}});assert.equal(f.list.hidden,false);assert.equal(detail.hidden,true);
 f.c.pop({state:{appId:'ai2apps.ai-browser',browserMiniApp:'search-all'}});assert.equal(f.list.hidden,true);assert.equal(detail.hidden,false);assert.equal(f.children.length,1);
 f.nav('back',null,detail.contentWindow);f.nav('back',null,detail.contentWindow);assert.equal(f.states.filter(x=>x==='back').length,1);
});
test('bridge rejects unbound frames, wrong tokens and sandbox; only library may open',()=>{
 const f=fixture();assert.equal(f.nav('open','search',{}),false);assert.equal(f.nav('open','search',f.list.contentWindow,'wrong'),false);f.record.renderer='sandbox';assert.equal(f.nav('open','search'),false);f.record.renderer='trusted';f.nav('open','search');assert.equal(f.nav('open','other',f.record.browserDetail.frame.contentWindow),false);assert.equal(f.children.length,1);
});
test('detail budget is one retained frame; replacing Mini-App removes old frame',()=>{
 const f=fixture();f.nav('open','first');const old=f.record.browserDetail.frame;f.c.pop({state:{appId:'ai2apps.ai-browser'}});f.nav('open','second');assert.equal(old.removed,true);assert.equal(f.record.browserDetail.id,'second');
});

test('Imagine Studio has a distinct Shell detail layer and returns to its retained library',()=>{
 const f=fixture('ai2apps.imagine-studio');assert.equal(f.nav('open','text-to-image'),true);
 assert.equal(f.states[0].appId,'ai2apps.imagine-studio');assert.equal(f.list.hidden,true);
 f.c.pop({state:{appId:'ai2apps.imagine-studio'}});assert.equal(f.list.hidden,false);assert.equal(f.record.browserDetail.frame.hidden,true);
 f.c.pop({state:{appId:'ai2apps.imagine-studio',browserMiniApp:'text-to-image'}});assert.equal(f.record.browserDetail.frame.hidden,false);
});
test('cold detail shows loading immediately; late ready cannot reopen a returned detail',()=>{
 const f=fixture('ai2apps.imagine-studio');f.nav('open','text-to-image');
 assert.equal(f.c.loading.hidden,false);assert.equal(f.list.hidden,true);
 const detail=f.record.browserDetail.frame;
 assert.equal(f.nav('ready',null,f.list.contentWindow),false);assert.equal(f.c.loading.hidden,false);
 f.c.pop({state:{appId:'ai2apps.imagine-studio'}});assert.equal(f.c.loading.hidden,true);
 assert.equal(f.nav('ready',null,detail.contentWindow),true);assert.equal(detail.hidden,true);assert.equal(f.list.hidden,false);
 f.nav('open','text-to-image');assert.equal(f.c.loading.hidden,true);assert.equal(f.children.length,1);
});
test('current detail ready removes loading only after the selected workspace is ready',()=>{
 const f=fixture();f.nav('open','search');const frame=f.record.browserDetail.frame;
 assert.equal(f.c.loading.hidden,false);f.nav('ready',null,frame.contentWindow);assert.equal(f.c.loading.hidden,true);
});
test('successful Gallery drag adopts the live Studio without recreating its file input',()=>{
 const f=fixture('ai2apps.imagine-studio'),surfaces=[];
 const file={name:'retained.png'};f.list.contentWindow.files=[file];f.list.contentWindow.ai2appsRestoreStudioSurface=s=>surfaces.push(s);
 assert.equal(f.nav('adopt-drag','image-edit'),true);assert.equal(f.states.length,1);assert.equal(f.states[0].studioInline,true);assert.equal(f.children.length,0);
 f.nav('adopt-drag','image-edit');assert.equal(f.states.length,1);
 f.c.pop({state:{appId:'ai2apps.imagine-studio'}});assert.equal(surfaces.at(-1),'library');assert.equal(f.list.hidden,false);
 f.c.pop({state:{appId:'ai2apps.imagine-studio',browserMiniApp:'image-edit',studioInline:true}});assert.equal(surfaces.at(-1),'create');assert.equal(f.list.contentWindow.files[0],file);
});
test('Shell does not swallow a back button with no detail history',()=>{
 const f=fixture('ai2apps.imagine-studio');assert.equal(f.nav('back'),false);assert.equal(f.states.length,0);
 assert.equal(f.nav('adopt-drag','image-edit'),false);assert.equal(f.states.length,0);
});

for(const appId of ['ai2apps.video-studio','ai2apps.readaloud']){
 test(appId+' keeps library on open/back and records Gallery inline navigation',()=>{
  const f=fixture(appId);assert.equal(f.nav('open','chosen'),true);
  assert.equal(f.states[0].appId,appId);assert.equal(f.list.hidden,true);
  f.c.pop({state:{appId}});assert.equal(f.list.hidden,false);
  const restored=[];f.list.contentWindow.ai2appsRestoreStudioSurface=page=>restored.push(page);
  assert.equal(f.nav('adopt-drag','chosen'),true);
  assert.equal(f.states.at(-1).studioInline,true);
  f.c.pop({state:{appId}});assert.equal(restored.at(-1),'library');
  f.c.pop({state:{appId,browserMiniApp:'chosen',studioInline:true}});assert.equal(restored.at(-1),'create');
 });
}
