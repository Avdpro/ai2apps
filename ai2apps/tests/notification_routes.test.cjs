const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
test('Mobile notification route forwards only its mount and verifies source/token/id before acknowledgement',()=>{
 const source=fs.readFileSync(__dirname+'/../web/static/js/mobile.js','utf8');
 const code=source.slice(source.indexOf('    const notificationParams ='),source.indexOf('    function trimFrames()',source.indexOf('    const notificationParams =')));
 const events={},child={},wrong={},window={location:{origin:'https://device-public-slug.ai2apps.com'},addEventListener:(name,fn)=>events[name]=fn};
 const frames=new Map([['ai2apps.intelligence',{frame:{contentWindow:child},token:'bound-token'}]]);
 const context={window,location:{hash:'#app=ai2apps.intelligence&intelligence-channel=channel&intelligence-article=article&notification-id=notice'},frames,activeAppId:'ai2apps.intelligence',URL,URLSearchParams};
 vm.createContext(context);vm.runInContext(code,context);
 const url=vm.runInContext("framedUrl('/admin/app-content/ai2apps.intelligence','bound-token',{app_key:'ai2apps.intelligence',app_instance_id:'instance',id:'mount'})",context);
 assert.ok(url.includes('notification-id=notice'));assert.ok(url.includes('intelligence-article=article'));
 const message={type:'ai2apps.notification.result',id:'notice',status:'opened',mountToken:'bound-token'};
 for(const e of [{source:wrong,data:message},{source:child,data:{...message,mountToken:'wrong'}},{source:child,data:{...message,id:'other'}},{source:child,data:{...message,status:'execute'}}])events.message(e);
 assert.equal(window.__ai2appsNotificationStatus,undefined);
 events.message({source:child,data:message});assert.equal(window.__ai2appsNotificationStatus.status,'opened');
 const other=vm.runInContext("framedUrl('/other','other-token',{app_key:'other.app',app_instance_id:'other',id:'other'})",context);
 assert.ok(!other.includes('notification-id='));
});
