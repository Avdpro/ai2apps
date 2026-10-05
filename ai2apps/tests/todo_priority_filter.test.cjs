const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../web/static/js/todo.js'), 'utf8');
function task(id, priority, parent_id = null, extra = {}) {
 return {id, priority, parent_id, directory_id: 'd', title: id, description: '', position: 0, completed: false, schedule: {frequency: 'off'}, ...extra};
}
function rows(tasks, filter = 'priority-U', search = '', collapsed = []) {
 const context = vm.createContext({state: {tasks}, aggregateId: null, directoryId: 'd', collapsed: new Set(collapsed),
  inTaskView: t => filter === 'trash' ? !!t.deleted_at : filter === 'archived' ? !!t.archived_at && !t.deleted_at : !t.archived_at && !t.deleted_at,
  $: s => ({value: s === '#filter' ? filter : search})});
 vm.runInContext(source.slice(source.indexOf('function visibleRows()'), source.indexOf('function renderTree()')), context);
 return JSON.parse(JSON.stringify(vm.runInContext('visibleRows()', context)));
}
test('priority matches retain gray ancestor paths and reveal collapsed descendants', () => {
 const result = rows([task('root','A'),task('parent','B','root'),task('match','U','parent'),task('sibling','S','parent'),task('other','A')], 'priority-U', '', ['root','parent']);
 assert.deepEqual(result.map(r => [r.t.id,r.depth,r.contextOnly,r.children,r.expanded]), [
  ['root',0,true,true,true],['parent',1,true,true,true],['match',2,false,false,true]
 ]);
});
test('matching parents and children appear once; nonmatching descendants are excluded', () => {
 const result = rows([task('root','U'),task('child','U','root'),task('hidden','B','root')]);
 assert.deepEqual(result.map(r => [r.t.id,r.contextOnly]), [['root',false],['child',false]]);
});
test('each grade matches exactly, C includes legacy default, completed items remain eligible', () => {
 const tasks = [...'USABCD'].map(p => task(p,p,null,{completed:true}));
 tasks.push(task('legacy',undefined));
 for (const p of 'USABCD') assert.deepEqual(rows(tasks,'priority-'+p).map(r=>r.t.id), p==='C'?['C','legacy']:[p]);
});
test('search combines with priority and lifecycle and directory boundaries remain enforced', () => {
 const tasks = [task('root','A'),task('needle','U','root'),task('unmatched','U'),task('foreign','U',null,{directory_id:'other',title:'needle'}),task('archived','U',null,{archived_at:'date',title:'needle'}),task('deleted','U',null,{deleted_at:'date',title:'needle'})];
 assert.deepEqual(rows(tasks,'priority-U','needle').map(r=>r.t.id),['root','needle']);
 assert.deepEqual(rows(tasks,'priority-S'),[]);
});
test('all-project view preserves sibling order and collapsed state', () => {
 const tasks = [task('second','U',null,{position:2}),task('first','A',null,{position:1}),task('child','B','first')];
 assert.deepEqual(rows(tasks,'all','',['first']).map(r=>r.t.id),['first','second']);
});
