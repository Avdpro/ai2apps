const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const root=__dirname+'/../web/static/js/';
function client(){
 const events={},messages=[],timers=new Map();let sequence=0;
 const parent={postMessage:message=>messages.push(message)};
 const window={parent,document:{readyState:'complete'},crypto:{randomUUID:()=> 'request-1'},console,
 addEventListener:(name,fn)=>events[name]=fn,setTimeout:(fn,delay)=>{if(delay===0){fn();return 0;}const id=++sequence;timers.set(id,fn);return id;},clearTimeout:id=>timers.delete(id)};
 vm.runInNewContext(fs.readFileSync(root+'web_agent_mini_app_sdk.js','utf8'),{window});
 return {window,events,messages,timers,parent};
}
test('SDK accepts only the parent connection and sends explicit capability and profile',async()=>{
 const c=client(),sent=[],port={postMessage:m=>sent.push(m),start(){}};
 c.events.message({source:{},data:{type:'ai2apps:studio-connected',version:1},ports:[port]});
 assert.equal(port.onmessage,undefined);
 c.events.message({source:c.parent,data:{type:'ai2apps:studio-connected',version:1},ports:[port]});
 const promise=c.window.AI2AppsWebAgent.submit('list',{url:'https://example.com'},{profile:'work'});
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(sent[0].operation,'web-agent.submit');assert.equal(sent[0].capability,'list');assert.equal(sent[0].profile,'work');assert.equal(sent[0].requestId,'request-1');
 port.onmessage({data:{id:sent[0].id,value:{id:'task',status:'queued'}}});
 assert.equal((await promise).status,'queued');assert.equal(c.timers.size,0);
 const tasks=[];const off=c.window.AI2AppsWebAgent.onTask(task=>tasks.push(task));
 port.onmessage({data:{type:'ai2apps:web-agent-task',task:{id:'task',status:'completed'}}});
 assert.equal(tasks[0].status,'completed');off();
 port.onmessage({data:{type:'ai2apps:web-agent-task',task:{id:'other'}}});assert.equal(tasks.length,1);
});
test('SSE refresh coalesces concurrent signals and preserves a final transition',async()=>{
 const source=fs.readFileSync(root+'studio_mini_apps.js','utf8');
 const fragment=source.slice(source.indexOf('        const watchWebTask ='),source.indexOf('        const startWebEvents'));
 const responses=[],messages=[];let calls=0;
 const context={active:()=>true,webTasks:new Set(['task']),webTaskRefresh:new Map(),webTaskVersions:new Map(),base:'/mount',abort:{signal:{}},channel:{port1:{postMessage:m=>messages.push(m)}},payload:async r=>r,fetch:()=>{calls++;return new Promise(resolve=>responses.push(resolve));}};
 vm.runInNewContext(fragment+'\nglobalThis.watch=watchWebTask;',context);
 const first=context.watch('task');context.watch('task');assert.equal(calls,1);
 responses.shift()({status:'running'});await new Promise(resolve=>setImmediate(resolve));
 assert.equal(calls,2);responses.shift()({status:'completed'});await first;
 assert.equal(messages[1].task.status,'completed');assert.equal(context.webTaskRefresh.size,0);
});
test('Mini-App navigation preserves frame; Package removal revokes only its UI',async()=>{
 const frame={style:{},removed:false,remove(){this.removed=true;}};
 const window={t:k=>k,AI2AppsStudioMiniApps:{list:async()=>({items:[]})}};
 const context={window,crypto:{randomUUID:()=> 'id'},Map,URL,URLSearchParams,console,document:{getElementById:()=>({classList:{toggle(){}}})}};
 vm.runInNewContext(fs.readFileSync(root+'ai_browser.js','utf8'),context);const app=context.aiBrowserApp();
 app.frames.set('mini-app:reader',{frame,miniAppId:'reader',digest:'v1'});app.miniAppId='reader';app.view='mini-app';app.updateFrames();assert.equal(frame.style.display,'block');
 app.view='domain';app.updateFrames();assert.equal(frame.style.display,'none');assert.equal(frame.removed,false);
 await app.refreshMiniApps();assert.equal(frame.removed,true);assert.equal(app.frames.size,0);
});
test('SDK serializes host operations while SSE stays independent',async()=>{
 const c=client(),sent=[],port={postMessage:m=>sent.push(m),start(){}};
 c.events.message({source:c.parent,data:{type:'ai2apps:studio-connected',version:1},ports:[port]});
 const first=c.window.AI2AppsWebAgent.retainedTasks(),second=c.window.AI2AppsWebAgent.profiles();
 await new Promise(resolve=>setImmediate(resolve));assert.equal(sent.length,1);assert.equal(sent[0].operation,'web-agent.retained-tasks');
 port.onmessage({data:{id:sent[0].id,value:[]}});await first;await new Promise(resolve=>setImmediate(resolve));assert.equal(sent.length,2);assert.equal(sent[1].operation,'web-agent.profiles');
 port.onmessage({data:{id:sent[1].id,value:[]}});await second;
 const focus=c.window.AI2AppsWebAgent.pages('task','focus');await new Promise(resolve=>setImmediate(resolve));assert.equal(sent[2].taskId,'task');assert.equal(sent[2].action,'focus');port.onmessage({data:{id:sent[2].id,value:{pages:[]}}});await focus;
});
test('polling delivers completion even without SSE and stops for terminal tasks',async()=>{
 const source=fs.readFileSync(root+'studio_mini_apps.js','utf8');
 const fragment=source.slice(source.indexOf('        const watchWebTask ='),source.indexOf('        const startWebEvents'));
 const messages=[],timers=[];
 const context={webPollTimer:null,active:()=>true,webTasks:new Set(['task']),webTaskRefresh:new Map(),webTaskVersions:new Map(),base:'/mount',abort:{signal:{}},channel:{port1:{postMessage:m=>messages.push(m)}},payload:async r=>r,fetch:async()=>({status:'completed',result:{items:[{title:'Result'}]}}),setTimeout:fn=>{timers.push(fn);return timers.length;}};
 vm.runInNewContext(fragment+'\nglobalThis.poll=startWebPolling;',context);
 context.poll();assert.equal(timers.length,1);await timers[0]();
 assert.equal(messages[0].task.result.items[0].title,'Result');assert.equal(context.webTasks.size,0);assert.equal(timers.length,1);
});
test('unchanged polling snapshots do not notify or redraw Mini-App',async()=>{
 const source=fs.readFileSync(root+'studio_mini_apps.js','utf8');
 const fragment=source.slice(source.indexOf('        const watchWebTask ='),source.indexOf('        const startWebEvents'));
 const messages=[];
 const context={webPollTimer:null,active:()=>true,webTasks:new Set(['task']),webTaskRefresh:new Map(),webTaskVersions:new Map(),base:'/mount',abort:{signal:{}},channel:{port1:{postMessage:m=>messages.push(m)}},payload:async r=>r,fetch:async()=>({status:'running',message:'',updated_at:Date.now()}),setTimeout:()=>1};
 vm.runInNewContext(fragment+'\nglobalThis.watch=watchWebTask;',context);
 await context.watch('task');await context.watch('task');assert.equal(messages.length,1);
 context.fetch=async()=>({status:'completed',result:{items:[]}});await context.watch('task');assert.equal(messages.length,2);
});
test('Mobile opening accepts only observed HTTPS results without rewriting access tokens',()=>{
 const source=fs.readFileSync(root+'studio_mini_apps.js','utf8');
 const fragment=source.slice(source.indexOf('    function mobileResultURL'),source.indexOf('    function showMobileResult'));
 const context={URL};vm.runInNewContext(fragment+'\nglobalThis.validate=mobileResultURL;',context);
 const url='https://www.rednote.com/explore/abc?xsec_token=observed';
 assert.equal(context.validate({result:{items:[{url}]}},url).href,url);
 assert.throws(()=>context.validate({result:{items:[{url}]}},'https://example.com/'));
 assert.throws(()=>context.validate({result:{items:[{url:'javascript:alert(1)'}]}},'javascript:alert(1)'));
});
test('XHS mobile targets keep token and host, use note detail path and documented native scheme',()=>{
 const source=fs.readFileSync(root+'studio_mini_apps.js','utf8');
 const fragment=source.slice(source.indexOf('    function mobileResultTargets'),source.indexOf('    function normalizedLocale'));
 const context={URL};vm.runInNewContext(fragment+'\nglobalThis.targets=mobileResultTargets;',context);
 const id='683d2d260000000001101dd5';const value=context.targets(new URL('https://www.rednote.com/search_result/'+id+'?xsec_token=abc%2Bdef&xsec_source=web'));
 assert.equal(new URL(value.web).pathname,'/explore/'+id);assert.equal(new URL(value.web).hostname,'www.rednote.com');assert.equal(new URL(value.web).searchParams.get('xsec_token'),'abc+def');
 assert.equal(new URL(value.app).protocol,'xhsdiscover:');assert.equal(new URL(value.app).pathname,'/'+id);
 assert.equal(context.targets(new URL('https://example.com/search_result/'+id)).app,null);
});
test('Mobile dialog uses roomy native new-tab links without timers or blank-page redirects',()=>{
 const source=fs.readFileSync(root+'studio_mini_apps.js','utf8');
 const fragment=source.slice(source.indexOf('    function showMobileResult'),source.indexOf('    function normalizedLocale'));
 const nodes=[];const make=tag=>{const n={tag,style:{},children:[],append(...v){this.children.push(...v);},addEventListener(){},showModal(){},close(){},remove(){}};nodes.push(n);return n;};
 const context={URL,document:{documentElement:{lang:'zh'},body:{append(){}},createElement:make}};
 vm.runInNewContext(fragment+'\nglobalThis.show=showMobileResult;',context);
 const dialog=context.show(new URL('https://www.rednote.com/search_result/683d2d260000000001101dd5?xsec_token=token'));
 const links=nodes.filter(n=>n.tag==='a');assert.equal(links.length,2);assert(links.every(n=>n.target==='_blank'&&n.onclick===undefined));
 assert(links[0].href.startsWith('xhsdiscover://item/'));assert(links[1].href.startsWith('https://www.rednote.com/explore/'));
 assert(dialog.style.cssText.includes('padding:24px'));assert(dialog.style.cssText.includes('max-width:460px'));
});

test('Mobile cart accepts only completed verified Amazon cart routes and preserves store parameters',()=>{
 const source=fs.readFileSync(root+'studio_mini_apps.js','utf8');
 const fragment=source.slice(source.indexOf('    function mobileCartURLs'),source.indexOf('    function showMobileResult'));
 const context={URL};vm.runInNewContext(fragment+'\nglobalThis.carts=mobileCartURLs;',context);
 const fresh='https://www.amazon.com/alm/cart?almBrandId=FreshObserved';
 const task={status:'completed',capability:'prepare_cart',result:{recognized:true,stores:[{channel:'fresh',page_url:fresh},{channel:'whole_foods',page_url:'https://www.amazon.com/alm/cart?almBrandId=WholeFoodsObserved'}]}};
 assert.equal(context.carts(task)[0].url.href,fresh);
 assert.equal(context.carts(task).length,2);
 assert.throws(()=>context.carts({...task,status:'running'}));
 for(const page_url of ['https://evil.test/cart/','https://www.amazon.com/checkout/','https://www.amazon.com/cart/%63heckout','javascript:alert(1)','https://user:pass@www.amazon.com/cart/'])
  assert.throws(()=>context.carts({...task,result:{recognized:true,page_url}}));
});

test('Mobile cart focus opens phone dialog and does not focus desktop browser',async()=>{
 const source=fs.readFileSync(root+'studio_mini_apps.js','utf8');
 const start=source.indexOf("                        if(request.action==='focus'&&(window.AI2APPS_MOBILE_SURFACE");
 const end=source.indexOf('                        reply({value:await payload(await fetch(`${base}/web-agent/tasks/${encodeURIComponent(request.taskId)}/pages/',start);
 const fetched=[],replies=[],dialogs=[];
 const context={request:{action:'focus',taskId:'cart'},window:{AI2APPS_MOBILE_SURFACE:true},frame:{closest:()=>false},binding:{miniAppId:'ai2apps.shopping-pro'},base:'/mount',abort:{signal:{}},payload:async r=>r,fetch:async url=>{fetched.push(url);return {status:'completed',capability:'prepare_cart'};},mobileCartURLs:()=>[{url:new URL('https://www.amazon.com/alm/cart?almBrandId=Fresh'),channel:'fresh'}],showMobileResult:(url,options)=>{dialogs.push(options);return {addEventListener(){}};},mobileDialogs:new Set(),reply:r=>replies.push(r)};
 vm.runInNewContext('globalThis.run=async()=>{'+source.slice(start,end)+'};',context);await context.run();
 assert.deepEqual(fetched,['/mount/web-agent/tasks/cart']);assert.equal(dialogs[0].cart,true);assert.equal(replies[0].value.opened_on,'mobile');
});

test('Phone cart dialog offers native new-tab links for every prepared store',()=>{
 const source=fs.readFileSync(root+'studio_mini_apps.js','utf8');
 const fragment=source.slice(source.indexOf('    function showMobileResult'),source.indexOf('    function normalizedLocale'));
 const nodes=[];const make=tag=>{const n={tag,style:{},children:[],append(...items){this.children.push(...items);},addEventListener(){},showModal(){},close(){},remove(){}};nodes.push(n);return n;};
 const context={URL,document:{documentElement:{lang:'zh'},body:{append(){}},createElement:make}};
 vm.runInNewContext(fragment+'\nglobalThis.show=showMobileResult;',context);
 const fresh=new URL('https://www.amazon.com/alm/cart?almBrandId=Fresh');
 const whole=new URL('https://www.amazon.com/alm/cart?almBrandId=WholeFoods');
 context.show(fresh,{cart:true,stores:[{url:fresh,channel:'fresh'},{url:whole,channel:'whole_foods'}]});
 const links=nodes.filter(n=>n.tag==='a');assert.equal(links.length,2);assert.equal(links[0].href,fresh.href);assert.equal(links[1].href,whole.href);
 assert(links.every(n=>n.target==='_blank'&&n.rel==='noopener noreferrer'));
 assert(nodes.some(n=>n.textContent==='查看亚马逊购物车'));assert(nodes.some(n=>n.textContent?.includes('相同的亚马逊账号')));
});

test('notification SDK sends only through the bound host channel',async()=>{
 const c=client(),sent=[],port={postMessage:m=>sent.push(m),start(){}};
 c.events.message({source:c.parent,data:{type:'ai2apps:studio-connected',version:1},ports:[port]});
 const notification={event_id:'stable-business-id',content:{title:'A < B',body:'Text'},target:{type:'https_url',app_id:'example.app',url:'https://example.com/news'}};
 const result=c.window.AI2AppsNotifications.send(notification);
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(sent.length,1);assert.equal(sent[0].operation,'notifications.send');
 assert.equal(sent[0].notification,notification);assert.equal(sent[0].mountId,undefined);
 port.onmessage({data:{id:sent[0].id,value:{event_id:'stable-business-id',status:'queued'}}});
 assert.equal((await result).status,'queued');
});
