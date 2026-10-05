const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/static/js/todo.js'),'utf8');
function setup(){
 const task=(id,parent_id,priority='U',extra={})=>({id,parent_id,priority,directory_id:'d1',title:id,description:'',position:0,completed:false,...extra});
 const state={runs:[],directories:[{id:'d1',title:'First'},{id:'d2',title:'Second'}],tasks:[task('parent',null),task('urgent-child','parent'),task('ordinary','parent','A'),task('bridge','parent','B'),task('nested','bridge'),task('done',null,'U',{completed:true}),task('archived',null,'U',{archived_at:'now'}),task('deleted',null,'U',{deleted_at:'now'}),task('other',null,'U',{directory_id:'d2'})]};
 const search={value:''},context=vm.createContext({state,aggregateId:'urgent',active:s=>['queued','running','planning','waiting_input','waiting_capability'].includes(s),collapsed:new Set(),$:()=>search,isActiveTask:t=>!t.archived_at&&!t.deleted_at});
 vm.runInContext(source.slice(source.indexOf('function isUrgent('),source.indexOf('function inTaskView('))+source.slice(source.indexOf('function aggregateRows('),source.indexOf('function visibleRows(')),context);
 return {state,context,search,rows:()=>context.aggregateRows()};
}
test('urgent closure groups origins and includes only necessary ancestors without duplicates',()=>{
 const h=setup(),rows=h.rows(),tasks=rows.filter(r=>r.t);
 assert.deepEqual(Array.from(tasks,r=>r.t.id),['parent','urgent-child','bridge','nested','other']);
 assert.equal(tasks.find(r=>r.t.id==='bridge').contextOnly,true);
 assert.equal(tasks.find(r=>r.t.id==='nested').depth,2);
 assert.deepEqual(Array.from(rows.filter(r=>r.group),r=>r.count),[3,1]);
 assert.equal(new Set(tasks.map(r=>r.t.id)).size,tasks.length);
});
test('search retains the matching child path and collapse only changes visibility, not counts',()=>{
 const h=setup();h.context.collapsed.add('parent');assert.equal(h.rows().filter(r=>r.t).length,2);
 h.search.value='nested';const rows=h.rows();assert.deepEqual(Array.from(rows.filter(r=>r.t),r=>r.t.id),['parent','bridge','nested']);assert.equal(rows[0].count,1);assert.equal(rows[1].contextOnly,true);
});
test('changing priority or completion removes a match but keeps necessary parent context',()=>{
 const h=setup();h.state.tasks[0].priority='A';let rows=h.rows();assert.equal(rows[0].count,2);assert.equal(rows[1].contextOnly,true);
 h.state.tasks.find(t=>t.id==='urgent-child').completed=true;h.state.tasks.find(t=>t.id==='nested').deleted_at='now';rows=h.rows();assert.deepEqual(Array.from(rows.filter(r=>r.t),r=>r.t.id),['other']);
});

test('additional aggregates use live runs, enabled schedules and actual completion timestamps',()=>{
 const h=setup(),t=h.state.tasks[0];h.state.runs=[{task_id:t.id,status:'waiting_input'}];
 assert.equal(h.context.matchesAggregate(t,'executing'),true);h.state.runs[0].status='completed';assert.equal(h.context.matchesAggregate(t,'executing'),false);
 t.status='in_progress';assert.equal(h.context.matchesAggregate(t,'executing'),false);
 t.schedule={frequency:'weekly'};assert.equal(h.context.matchesAggregate(t,'recurring'),true);
 t.completed=true;t.completed_at=new Date(Date.now()-86400000).toISOString();assert.equal(h.context.matchesAggregate(t,'recent'),true);
 t.completed_at=new Date(Date.now()-8*86400000).toISOString();assert.equal(h.context.matchesAggregate(t,'recent'),false);
 delete t.completed_at;assert.equal(h.context.matchesAggregate(t,'recent'),false);
 t.archived_at='now';assert.equal(h.context.matchesAggregate(t,'recurring'),false);
 h.context.aggregateId='recurring';assert.equal(h.rows().length,0);
});

test('current tasks includes Todo queue while executing excludes tasks not yet admitted',()=>{
 const h=setup(),t=h.state.tasks[0];h.state.runs=[{task_id:t.id,status:'queued',todo_queued:true}];
 assert.equal(h.context.matchesAggregate(t,'currentTasks'),true);
 assert.equal(h.context.matchesAggregate(t,'executing'),false);
 h.state.runs[0].todo_queued=false;
 assert.equal(h.context.matchesAggregate(t,'executing'),true);
 h.state.runs[0].status='completed';assert.equal(h.context.matchesAggregate(t,'currentTasks'),false);
});
