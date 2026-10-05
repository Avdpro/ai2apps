const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/static/js/todo.js'),'utf8');
function setup(leave=true){
 const links=[],notices=[];
 const context=vm.createContext({canLeave:()=>leave,zh:true,notice:t=>notices.push(t),document:{createElement:()=>({click(){this.clicked=true;},remove(){this.removed=true;}}),body:{append:link=>links.push(link)}}});
 vm.runInContext(source.slice(source.indexOf('function downloadTodoBackup('),source.indexOf("$('#export-todo').onclick")),context);
 return {run:context.downloadTodoBackup,links,notices};
}
test('toolbar preserves native HTTP anchor default navigation without fetching a blob',()=>{
 const html=fs.readFileSync(path.join(__dirname,'../web/templates/system_apps/todo.html'),'utf8');
 assert.match(html,/<a id="export-todo"[^>]+href="\/v1\/platform\/todo\/backup"[^>]+download=/);
 const s=setup(),link={};assert.equal(s.run(null,link),true);
 assert.equal(link.href,'/v1/platform/todo/backup');assert.match(link.download,/^todo-backup-\d{4}-\d{2}-\d{2}\.zip$/);
 assert.equal(s.links.length,0);assert.equal(s.notices.length,1);
});
test('directory export uses scoped authenticated HTTP URL and safe filename',()=>{
 const s=setup();s.run({id:'dir /1',title:'work/test'});
 assert.equal(s.links[0].href,'/v1/platform/todo/backup?directory_id=dir%20%2F1');
 assert.match(s.links[0].download,/todo-backup-work_test-/);
 assert.equal(s.links[0].clicked,true);assert.equal(s.links[0].removed,true);
});
test('declining unsaved changes prevents a download and does not claim one started',()=>{
 const s=setup(false);assert.equal(s.run(),false);assert.equal(s.links.length,0);assert.equal(s.notices.length,0);
});
