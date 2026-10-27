const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/mobile.js'),'utf8');
function setup(){
 const events={},children=[],messages=[];
 const record={token:'list-token',instanceId:'instance',renderer:'trusted',loaded:true,frame:{hidden:false,src:'https://device/mobile/todo#ai2apps-mount=list-token&ai2apps-instance=instance',classList:{add(){}},contentWindow:{postMessage(m){messages.push(m)}}}};
 const c={URL,URLSearchParams,activeAppId:'ai2apps.todo',frames:new Map([['ai2apps.todo',record]]),location:{origin:'https://device',href:'https://device/mobile#app=ai2apps.todo',hash:'#app=ai2apps.todo'},
 window:{addEventListener:(n,f)=>events[n]=f},crypto:{randomUUID:()=> 'detail-token'},document:{documentElement:{lang:'zh'},createElement:()=>({children:[],append(...nodes){this.children.push(...nodes)},setAttribute(){},hidden:false,contentWindow:{mobileTodoCanLeave:()=>true,postMessage(m){messages.push(m)}},remove(){this.removed=true}})},frameHost:{appendChild:f=>children.push(f)},history:{state:{appId:'ai2apps.todo'},pushState(s){this.state=s},back(){this.backCalled=true}},loading:{hidden:true},errorView:{hidden:true},stage:{hidden:false},showToast(){},openApp(){throw Error('must not reopen App')},showHome(){}};
 c.pendingAppNavigation=null;vm.createContext(c);
 vm.runInContext(source.slice(source.indexOf('    // Todo-only'),source.indexOf('    function sendBridgeResponse(')),c);
 const a=source.indexOf("    window.addEventListener('popstate',");vm.runInContext(source.slice(a,source.indexOf('    async function boot()',a)),c);
 const send=(frame,token,type,extra={})=>events.message({origin:'https://device',source:frame.contentWindow,data:{type,mountToken:token,instanceId:'instance',...extra}});
 return {c,events,children,record,send,messages};
}
test('Shell owns detail history and switches preloaded frames on back/forward',()=>{
 const f=setup();f.send(f.record.frame,'list-token','ai2apps.todo.open-detail',{taskId:'one',directoryId:'folder'});
 const detail=f.children[0].children[0];assert.equal(detail.hidden,false);assert.equal(f.children[0].children[1].hidden,false);assert.equal(f.c.history.state.todoDetail,true);
 assert.equal(new URL(detail.src).searchParams.get('todo_task'),'one');
 f.send(detail,'detail-token','ai2apps.todo.detail-ready');assert.equal(detail.hidden,false);assert.equal(f.record.frame.hidden,true);assert.equal(f.c.history.state.todoDetail,true);
 f.events.popstate({state:{appId:'ai2apps.todo'}});assert.equal(detail.hidden,true);assert.equal(f.record.frame.hidden,false);assert.equal(f.children.length,1);
 f.events.popstate({state:{appId:'ai2apps.todo',todoDetail:true}});assert.equal(detail.hidden,false);
 f.send(detail,'detail-token','ai2apps.todo.changed');assert.equal(f.messages.at(-1).type,'ai2apps.todo.refresh');
});
test('foreign messages and rejected unsaved changes cannot switch frames',()=>{
 const f=setup();f.send(f.record.frame,'wrong','ai2apps.todo.open-detail');assert.equal(f.children.length,0);
 f.send(f.record.frame,'list-token','ai2apps.todo.open-detail');const detail=f.children[0].children[0];f.send(detail,'detail-token','ai2apps.todo.detail-ready');
 detail.contentWindow.mobileTodoCanLeave=()=>false;f.events.popstate({state:{appId:'ai2apps.todo'}});assert.equal(detail.hidden,false);assert.equal(f.c.history.state.todoDetail,true);
});

test('prewarmed detail remains hidden, then reuses its document with current list data',()=>{
 const f=setup();f.send(f.record.frame,'list-token','ai2apps.todo.open-detail',{warm:true});
 const detail=f.children[0].children[0];f.send(detail,'detail-token','ai2apps.todo.detail-ready');
 assert.equal(detail.hidden,true);assert.equal(f.record.frame.hidden,false);assert.equal(f.c.history.state.todoDetail,undefined);
 const snapshot={tasks:[{id:'two',title:'Fresh'}],directories:[],runs:[]};
 f.send(f.record.frame,'list-token','ai2apps.todo.open-detail',{taskId:'two',snapshot});
 assert.equal(f.children.length,1);assert.equal(f.messages[0].type,'ai2apps.todo.initialize-detail');assert.equal(f.messages[0].snapshot,snapshot);
 f.send(detail,'detail-token','ai2apps.todo.detail-ready');assert.equal(detail.hidden,false);
});
test('click during prewarm waits for initialization with the clicked project',()=>{
 const f=setup();f.send(f.record.frame,'list-token','ai2apps.todo.open-detail',{warm:true});const detail=f.children[0].children[0];
 f.send(f.record.frame,'list-token','ai2apps.todo.open-detail',{taskId:'latest',snapshot:{tasks:[]}});
 f.send(detail,'detail-token','ai2apps.todo.detail-ready');assert.equal(f.children[0].children[1].hidden,false);assert.equal(f.messages[0].taskId,'latest');
 f.send(detail,'detail-token','ai2apps.todo.detail-ready');assert.equal(detail.hidden,false);assert.equal(f.children.length,1);
});

test('detail slides in and button Back slides out; native Back has no extra animation',async()=>{
 const f=setup();f.send(f.record.frame,'list-token','ai2apps.todo.open-detail',{warm:true});const detail=f.children[0].children[0],animations=[];
 f.children[0].animate=(frames,options)=>{let finish;const a={frames,options,finished:new Promise(resolve=>finish=resolve),cancel(){},finish:()=>finish()};animations.push(a);return a;};
 f.send(detail,'detail-token','ai2apps.todo.detail-ready');f.send(f.record.frame,'list-token','ai2apps.todo.open-detail');assert.equal(animations[0].frames[0].transform,'translateX(100%)');assert.equal(f.record.frame.hidden,false);
 animations[0].finish();await Promise.resolve();assert.equal(f.record.frame.hidden,true);
 f.send(detail,'detail-token','ai2apps.todo.detail-back');f.events.popstate({state:{appId:'ai2apps.todo'}});
 assert.equal(animations[0].options.duration,240);assert.equal(animations[1].options.duration,360);assert.equal(animations[1].frames[1].transform,'translateX(100%)');assert.equal(detail.hidden,false);assert.equal(f.record.frame.hidden,false);
 animations[1].finish();await Promise.resolve();assert.equal(detail.hidden,true);
 f.events.popstate({state:{appId:'ai2apps.todo',todoDetail:true}});f.events.popstate({state:{appId:'ai2apps.todo'}});
 assert.equal(animations.length,2);assert.equal(detail.hidden,true);
});
test('reduced motion switches frames without sliding',()=>{
 const f=setup();f.c.window.matchMedia=()=>({matches:true});f.send(f.record.frame,'list-token','ai2apps.todo.open-detail');const detail=f.children[0].children[0];
 detail.animate=()=>{throw Error('must respect reduced motion')};f.send(detail,'detail-token','ai2apps.todo.detail-ready');assert.equal(detail.hidden,false);assert.equal(f.record.frame.hidden,true);
});
test('late content readiness after returning cannot reopen the detail shell',()=>{
 const f=setup();f.send(f.record.frame,'list-token','ai2apps.todo.open-detail');const surface=f.children[0],detail=surface.children[0];
 assert.equal(surface.hidden,false);assert.equal(surface.children[1].hidden,false);
 f.events.popstate({state:{appId:'ai2apps.todo'}});assert.equal(surface.hidden,true);
 f.send(detail,'detail-token','ai2apps.todo.detail-ready');assert.equal(surface.hidden,true);assert.equal(f.record.frame.hidden,false);
});
