const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function setup(model='asr'){
 const listeners={},target={value:'Typed',maxLength:200,tagName:'INPUT',dispatchEvent(){},focus(){}},status={};let click,ensure=0,started=0;
 const button={dataset:{todoDictate:'dialog-name'},addEventListener:(_,fn)=>click=fn};
 const dialog={open:true,querySelectorAll:()=>[button],querySelector:()=>({addEventListener(){}}),addEventListener:(n,fn)=>listeners[n]=fn};
 const context={document:{documentElement:{lang:'zh'},getElementById:id=>id==='name-dialog'?dialog:id==='todo-dictation-status'?status:target},window:{addEventListener(){},AI2AppsCapabilities:{ensure:async()=>{ensure++;return {provider:{modelId:model}};}},AI2AppsStudioAudioRecorder:class{async start(){started++;this.result=Promise.resolve({body:'audio',name:'test.webm'});}dispose(){}}},crypto:{randomUUID:()=> 'id'},AbortController,FormData:class{append(){}},Event:class{},setTimeout,clearTimeout,fetch:async()=>({ok:true,json:async()=>({text:'Recognized'})})};
 vm.runInNewContext(fs.readFileSync('web/static/js/todo_dictation.js','utf8'),context);
 return {click:()=>click(),target,status,counts:()=>({ensure,started})};
}
test('dictation ensures capability before recording and appends editable text',async()=>{const h=setup();await h.click();assert.equal(h.target.value,'Typed Recognized');assert.deepEqual(h.counts(),{ensure:1,started:1});});
test('missing configured model never records or overwrites existing input',async()=>{const h=setup('');await h.click();assert.equal(h.target.value,'Typed');assert.equal(h.counts().started,0);assert.match(h.status.textContent,/尚未配置/);});
