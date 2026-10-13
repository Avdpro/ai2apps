const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('web/static/js/mobile_todo.js','utf8');
function setup(fail=false){
 const current={id:'t',title:'Saved title',description:'Saved description',priority:'A',status:'in_progress',progress:20,revision:1,emoji:'🎯',highlight:''};
 const fields={'task-title':{value:'Unsaved title'},description:{value:'Saved description'},priority:{value:'A'},'task-status':{value:'in_progress'},'task-progress':{value:'20'},'task-emoji':{value:'🚀'}};
 const calls=[];
 const ctx={current,data:{tasks:[current]},dirty:true,busy:false,highlight:'',shellDetail:true,$:id=>fields[id],clearTimeout,setTimeout,render(){},notice(){},mt:x=>x,shellSend(){},api:async(path,method,body)=>{calls.push(body);if(fail)throw Error('save failed');return {...current,...body,revision:2};}};
 vm.createContext(ctx);
 vm.runInContext(source.slice(source.indexOf('    let emojiSaveTimer;'),source.indexOf("    $('task-emoji').addEventListener")),ctx);
 return {ctx,calls};
}
test('Emoji autosave preserves unsaved title and advances revision',async()=>{
 const {ctx,calls}=setup();await ctx.saveEmoji();
 assert.equal(calls[0].title,'Saved title');assert.equal(calls[0].emoji,'🚀');
 assert.equal(ctx.current.revision,2);assert.equal(ctx.dirty,true);
 ctx.$('task-title').value='Saved title';ctx.$('task-emoji').value='';await ctx.saveEmoji();
 assert.equal(calls[1].revision,2);assert.equal(ctx.current.emoji,'');assert.equal(ctx.dirty,false);
});
test('failed save retains draft and new projects do not write',async()=>{
 const {ctx,calls}=setup(true);await ctx.saveEmoji();assert.equal(ctx.current.emoji,'🎯');assert.equal(ctx.dirty,true);assert.equal(ctx.busy,false);
 ctx.current=null;await ctx.saveEmoji();assert.equal(calls.length,1);
});
