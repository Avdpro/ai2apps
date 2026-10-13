const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const app=fs.readFileSync(path.join(__dirname,'../web/static/js/intelligence.js'),'utf8');
const host=fs.readFileSync(path.join(__dirname,'../web/static/js/mobile.js'),'utf8');
test('Shell back returns one level once and forward restores the article without a reload',()=>{
 let listener;const sent=[];
 const c={URLSearchParams,location:{hash:'#ai2apps-mount=token&ai2apps-instance=instance',origin:'https://device.test'},window:{AI2APPS_MOBILE_SURFACE:true,parent:{postMessage:m=>sent.push(m)},addEventListener:(_,fn)=>listener=fn},mobileQuery:{matches:true},document:{querySelector:()=>null},$:()=>({scrollTop:25,classList:{add(){},remove(){}},getBoundingClientRect(){return {};}}),syncMobile(){},renderReader(){},requestAnimationFrame:fn=>fn()};
 vm.createContext(c);vm.runInContext("let mobilePage='channels',readerMode='chat',selectedId=null,previewDraft=null,mobilePanel=false;"+app.slice(app.indexOf('const mobileStack=[];'),app.indexOf('function syncMobile(){')),c);
 vm.runInContext("mobilePush('channel');mobilePush('reader');selectedId='article';mobileBack();mobileBack();",c);
 assert.equal(sent.filter(m=>m.type.endsWith('.back')).length,1);
 const deliver=depth=>listener({source:c.window.parent,origin:c.location.origin,data:{type:'ai2apps.intelligence.history',mountToken:'token',depth}});
 deliver(1);assert.equal(vm.runInContext('mobilePage',c),'channel');
 deliver(2);assert.equal(vm.runInContext('mobilePage',c),'reader');assert.equal(vm.runInContext('selectedId',c),'article');
 deliver(0);assert.equal(vm.runInContext('mobilePage',c),'channels');
});
test('Mobile host validates mount identity and adds same-document history for Intel only',()=>{
 const updates=[];const frameWindow={};const record={frame:{contentWindow:frameWindow},token:'token',instanceId:'instance',renderer:'trusted'};
 const c={frames:new Map([['ai2apps.intelligence',record]]),activeAppId:'ai2apps.intelligence',window:{location:{origin:'https://device.test'}},location:{href:'https://device.test/mobile#app=ai2apps.intelligence'},history:{state:{appId:'ai2apps.intelligence'},pushState(state){this.state=state;updates.push(state)},back(){updates.push('back')}}};
 vm.createContext(c);const start=host.indexOf('        const record = Array.from(frames.values()).find');const end=host.indexOf("        if (message.type === 'ai2apps.shell.ready')",start);
 vm.runInContext('function message(event){'+host.slice(start,end)+'}',c);
 const event={source:frameWindow,origin:'https://device.test',data:{mountToken:'wrong',instanceId:'instance',type:'ai2apps.intelligence.push',depth:1}};
 c.message(event);assert.equal(updates.length,0);
 event.data.mountToken='token';c.message(event);assert.equal(c.history.state.intelDepth,1);
 event.data.type='ai2apps.intelligence.back';c.message(event);c.message(event);assert.equal(updates.filter(x=>x==='back').length,1);
});
test('native popstate skips the App animation while a button back keeps it',()=>{
 const sent=[],record={token:'token',frame:{contentWindow:{postMessage:m=>sent.push(m)}}};
 const c={frames:new Map([['ai2apps.intelligence',record]]),activeAppId:'ai2apps.intelligence',location:{origin:'https://device.test'},loading:{},errorView:{}};
 vm.createContext(c);const start=host.indexOf("        const intelRecord=frames.get('ai2apps.intelligence');"),end=host.indexOf("        if(todoDetail&&activeAppId==='ai2apps.todo'){",start);
 vm.runInContext('function pop(event){const appId=event.state.appId;'+host.slice(start,end)+'}',c);
 c.pop({state:{appId:'ai2apps.intelligence',intelDepth:1}});assert.equal(sent[0].animate,false);
 record.intelBackPending=true;c.pop({state:{appId:'ai2apps.intelligence',intelDepth:0}});assert.equal(sent[1].animate,true);assert.equal(record.intelBackPending,false);
});
