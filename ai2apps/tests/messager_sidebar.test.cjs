const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function setup({saved=null,available=1400,right=300,side='left'}={}){
 const events={},windowEvents={},attrs={},storage=new Map(saved===null?[]:[[side==='right'?'ai2apps.messager.right-sidebar-width.v1':'ai2apps.messager.sidebar-width.v1',saved]]),classes=new Set(),widths=[];
 const handle={addEventListener:(k,v)=>events[k]=v,removeEventListener:k=>delete events[k],setAttribute:(k,v)=>attrs[k]=v,setPointerCapture(id){this.captured=id;},hasPointerCapture(id){return this.captured===id;},releasePointerCapture(){this.captured=null;},focus(){this.focused=true;}};
 const shell={getBoundingClientRect:()=>({width:available})};const window={addEventListener:(k,v)=>windowEvents[k]=v,removeEventListener:k=>delete windowEvents[k]};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager_sidebar.js','utf8'),{window,document:{documentElement:{classList:{add:k=>classes.add(k),remove:k=>classes.delete(k)}}},localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)}});
 const api=window.AI2AppsMessagerSidebar.mount({handle,shell,side,rightWidth:()=>right,onWidth:w=>widths.push(w)});
 const event=(props={})=>({button:0,isPrimary:true,pointerId:9,clientX:260,preventDefault(){this.prevented=true;},...props});
 return {api,events,windowEvents,attrs,storage,classes,handle,widths,event,resize:(w)=>{available=w;windowEvents.resize();},setRight:w=>{right=w;api.refresh();}};
}
test('pointer capture enforces minimum and maximum; cancel releases capture and persists chosen width',()=>{
 const t=setup();assert.equal(t.widths.at(-1),260);t.events.pointerdown(t.event());assert.equal(t.handle.captured,9);assert.ok(t.classes.has('messager-resizing'));
 t.events.pointermove(t.event({clientX:-100}));assert.equal(t.widths.at(-1),88);
 t.events.pointermove(t.event({pointerId:10,clientX:1000}));assert.equal(t.widths.at(-1),88);
 t.events.pointermove(t.event({clientX:1000}));assert.equal(t.widths.at(-1),480);
 t.events.pointercancel(t.event());assert.equal(t.handle.captured,null);assert.equal(t.classes.size,0);assert.equal(t.storage.get('ai2apps.messager.sidebar-width.v1'),'480');t.api.dispose();assert.equal(Object.keys(t.events).length,0);
});
test('keyboard resizing, reset and restoration preserve width while responsive clamping protects conversation',()=>{
 const t=setup({saved:'420'});assert.equal(t.widths.at(-1),420);
 t.events.keydown(t.event({key:'Home'}));assert.equal(t.widths.at(-1),88);
 t.events.keydown(t.event({key:'ArrowRight'}));assert.equal(t.widths.at(-1),104);
 t.events.dblclick();assert.equal(t.widths.at(-1),260);
 t.events.keydown(t.event({key:'End'}));assert.equal(t.widths.at(-1),480);
 t.resize(900);assert.equal(t.widths.at(-1),240);assert.equal(t.storage.get('ai2apps.messager.sidebar-width.v1'),'480');
 t.resize(1600);assert.equal(t.widths.at(-1),480);t.api.expand();assert.equal(t.widths.at(-1),260);t.api.dispose();
});
test('invalid stored preference is safe; mobile and secondary button do not start resizing',()=>{
 for(const saved of ['NaN','Infinity','bad']){const t=setup({saved});assert.equal(t.widths.at(-1),260);t.events.pointerdown(t.event({button:2}));assert.equal(t.handle.captured,undefined);t.api.dispose();}
 const small=setup({available:600});small.events.pointerdown(small.event());assert.equal(small.handle.captured,undefined);small.api.dispose();
});
test('compact cards keep actual unread counters without treating task completion as unread',()=>{
 const window={},context={window,document:{documentElement:{lang:'en'}},navigator:{language:'en'}};vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),context);const app=window.messagerApp();
 app.localNotices=[{bot_id:'preview',read_at:null}];assert.equal(app.sidebarUnread({id:'preview',unread_count:0}),0);assert.equal(app.sidebarUnread({unreadCount:4}),4);assert.equal(app.sidebarBadge({unread_count:140}),'99+');assert.equal(app.sidebarUnread({hasUnread:true}),1);assert.equal(app.sidebarBadge({hasUnread:true}),'•');assert.equal(app.sidebarUnread({last_status:'completed'}),0);assert.equal(app.sidebarUnread({unreadCount:-1}),0);
});

test('right panel grows leftward, keeps original minimum, persists independently and resets',()=>{
 const t=setup({side:'right',right:260});assert.equal(t.widths.at(-1),300);
 t.events.pointerdown(t.event());t.events.pointermove(t.event({clientX:60}));assert.equal(t.widths.at(-1),500);
 t.events.pointerup(t.event());assert.equal(t.storage.get('ai2apps.messager.right-sidebar-width.v1'),'500');
 t.events.keydown(t.event({key:'ArrowLeft'}));assert.equal(t.widths.at(-1),516);
 t.events.keydown(t.event({key:'ArrowRight'}));assert.equal(t.widths.at(-1),500);
 t.resize(900);assert.equal(t.widths.at(-1),280);t.resize(1400);assert.equal(t.widths.at(-1),500);
 t.events.keydown(t.event({key:'Home'}));assert.equal(t.widths.at(-1),300);
 t.events.pointerdown(t.event());t.events.pointermove(t.event({clientX:900}));assert.equal(t.widths.at(-1),300);t.events.pointercancel(t.event());
 t.events.keydown(t.event({key:'End'}));assert.equal(t.widths.at(-1),720);t.events.dblclick();assert.equal(t.widths.at(-1),300);t.api.dispose();
 const restored=setup({side:'right',saved:'500'});assert.equal(restored.widths.at(-1),500);restored.api.dispose();
 const narrow=setup({side:'right',available:1000,right:260});assert.equal(narrow.widths.at(-1),250);assert.equal(narrow.attrs['aria-valuemin'],'250');narrow.api.dispose();
});

test('Bot activity separates replies and tasks, including concurrent work and terminal states',()=>{
 const window={};vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),{window,document:{documentElement:{lang:'en'}},navigator:{language:'en'}});const app=window.messagerApp();
 const bot={reply_status:'running',task_status:'running'};
 assert.equal(app.sidebarReply(bot),true);assert.equal(app.sidebarTask(bot),true);assert.equal(app.sidebarTaskLabel(bot),'Running task');
 bot.reply_status='completed';assert.equal(app.sidebarReply(bot),false);assert.equal(app.sidebarTask(bot),true);
 bot.task_status='waiting_input';assert.equal(app.sidebarTaskLabel(bot),'Task waiting for input');assert.equal(app.sidebarTask(bot),false);assert.equal(app.sidebarAssistance(bot),true);
 bot.reply_status='waiting_capability';assert.equal(app.sidebarReply(bot),false);bot.reply_status='running';assert.equal(app.sidebarReply(bot),true);
 bot.task_status='queued';assert.equal(app.sidebarTaskLabel(bot),'Task queued');
 bot.task_status='completed';assert.equal(app.sidebarTask(bot),false);
 assert.equal(app.sidebarAssistance({}),false);assert.equal(app.sidebarAssistance({needs_user_assistance:true,task_status:'running'}),true);assert.equal(app.sidebarReply({}),false);assert.equal(app.sidebarTask({}),false);
});

test('task overview shows active runs, upcoming schedules and finished runs in order',()=>{
 const window={},context={window,document:{documentElement:{lang:'en'}},navigator:{language:'en'}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8'),context);
 const app=window.messagerApp();
 app.botTasks=[
  {id:'daily',title:'Daily watch report',scheduled:true,next_due:'2026-11-18T07:00:00Z',
   run:{id:'new',status:'running',started_at:'2026-11-17T07:00:00Z'},
   previous_finished_run:{id:'previous',status:'completed',finished_at:'2026-11-16T07:00:00Z'}},
  {id:'archived',scheduled:true,archived_at:'2026-11-01'},
  {id:'once',scheduled:true,next_due:null,run:{status:'completed',finished_at:'2026-11-15T07:00:00Z'}},
  {id:'already-in-session',scheduled:false,task_session_id:'session-1'},
 ];
 app.botTaskSessions=Array.from({length:5},(_,i)=>({id:'session-'+i,status:'completed',updated_at:'2026-11-1'+i}));
 const [active,scheduled,ended]=app.taskOverview();
 assert.equal(active.entries[0].linked.run.id,'new');
 assert.equal(scheduled.entries.map(task=>task.id).join(','),'daily');
 assert.equal(ended.entries.map(task=>task.id).join(','),'daily,once,session-4');
 assert.equal(ended.entries[0].linked.run.id,'previous');
 const next=app.botTasks[0].next_due;
 const nearlyOneDay=Date.parse(next)-86_399_999;
 assert.match(app.nextTaskRunLabel(next,nearlyOneDay),/^\d{2}:\d{2}$/);
 assert.match(app.nextTaskRunLabel(next,nearlyOneDay-1),/^[A-Z][a-z]{2} \d{1,2}$/);
});
