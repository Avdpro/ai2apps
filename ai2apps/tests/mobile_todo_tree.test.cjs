const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const ctx={};vm.runInNewContext(fs.readFileSync('web/static/js/mobile_todo.js','utf8').split('function mobileTodoTree')[1].split('(() => {')[0].replace(/^/, 'function mobileTodoTree'),ctx);
const tasks=[{id:'child',parent_id:'root',title:'Needle',position:0},{id:'other',title:'Other',position:2},{id:'root',title:'Root',position:1,status:'completed'},{id:'grand',parent_id:'child',title:'Grand',position:0}];
test('tree groups descendants before next sibling and retains completed parent context',()=>{const rows=ctx.mobileTodoTree(tasks,'',false,new Set());assert.equal(rows.map(r=>r.task.id).join(','),'root,child,grand,other');assert.equal(rows.map(r=>r.depth).join(','),'0,1,2,0');assert.equal(rows[0].contextOnly,true);});
test('collapse hides subtree and search expands matching path',()=>{assert.equal(ctx.mobileTodoTree(tasks,'',true,new Set(['root'])).map(r=>r.task.id).join(','),'root,other');const rows=ctx.mobileTodoTree(tasks,'needle',false,new Set(['root']));assert.equal(rows.map(r=>r.task.id).join(','),'root,child');assert.equal(rows[0].contextOnly,true);});
test('sibling connector continues through descendants and ends at last visible child',()=>{
 const tree=[{id:'r',title:'Root'},{id:'a',title:'A',parent_id:'r',position:0},{id:'g',title:'Grand',parent_id:'a'},{id:'b',title:'B',parent_id:'r',position:1,status:'completed'}];
 let rows=ctx.mobileTodoTree(tree,'',true,new Set());
 assert.equal(rows[1].hasNextSibling,true);
 assert.equal(JSON.stringify(rows[2].continuations),'[1]');
 assert.equal(rows[3].hasNextSibling,false);
 rows=ctx.mobileTodoTree(tree,'',false,new Set());
 assert.equal(rows[1].hasNextSibling,true);
 assert.equal(JSON.stringify(rows[2].continuations),'[1]');
 assert.equal(rows[3].task.completedGroup,true);
 rows=ctx.mobileTodoTree(tree,'grand',true,new Set());
 assert.equal(rows[1].hasNextSibling,false);
 rows=ctx.mobileTodoTree(tree,'',true,new Set(['a']));
 assert.equal(rows.map(r=>r.task.id).join(','),'r,a,b');
 assert.equal(rows[1].hasNextSibling,true);
});

test('completed groups toggle at each parent and global show restores original order',()=>{
 const tree=[{id:'r',title:'Root'},{id:'done',title:'Done',parent_id:'r',status:'completed',position:0},{id:'live',title:'Live',parent_id:'r',position:1},{id:'nested',title:'Nested',parent_id:'done',status:'completed'}];
 let rows=ctx.mobileTodoTree(tree,'',false,new Set());
 assert.equal(rows.map(r=>r.task.id).join(','),'r,live,completed:r');
 assert.equal(rows[2].task.count,1);
 rows=ctx.mobileTodoTree(tree,'',false,new Set(),new Set(['r']));
 assert.equal(rows.map(r=>r.task.id).join(','),'r,live,completed:r,done,nested');
 assert.equal(rows[3].depth,2);
 rows=ctx.mobileTodoTree(tree,'',true,new Set());
 assert.equal(rows.map(r=>r.task.id).join(','),'r,done,nested,live');
 rows=ctx.mobileTodoTree(tree,'',false,new Set(['r']),new Set(['r']));
 assert.equal(rows.length,1);
});
test('parent with only completed children still expands to a completed group',()=>{
 const rows=ctx.mobileTodoTree([{id:'r',title:'Root'},{id:'d',title:'Done',parent_id:'r',status:'completed'}],'',false,new Set());
 assert.equal(rows[0].hasChildren,true);
 assert.equal(rows[1].task.count,1);
});
