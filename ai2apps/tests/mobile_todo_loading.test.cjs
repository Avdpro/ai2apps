const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
const source=fs.readFileSync('web/static/js/mobile_todo.js','utf8');
const template=fs.readFileSync('web/templates/mobile_todo.html','utf8').split('{% block content %}')[1].split('{% endblock %}')[0].replace(/{{\s*'([^']*)'[^}]*}}/g,'$1').replace(/{%[\s\S]*?%}/g,'');
test('detail iframe prewarms without data, loads only selected project on initialization',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage();const requests=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
 const task={id:'one',title:'Task',directory_id:'d',revision:1,status:'in_progress',priority:'A',progress:10};
 await page.route('http://todo.test/**',route=>{
  const url=new URL(route.request().url());
  if(url.pathname.startsWith('/v1/')){requests.push(url.pathname);return route.fulfill({json:{task:{...task,description:'Only in detail'},attachments:[],runs:[{id:'r',task_id:'one',status:'ended',output:'Result text'}]}});}
  return route.fulfill({contentType:'text/html',body:url.pathname==='/host'?'<iframe src="/detail?todo_shell_detail=1#ai2apps-mount=token"></iframe>':'<html lang="zh"><body>'+template+'<script>'+source+'</script></body></html>'});
 });
 await page.goto('http://todo.test/host');
 const frame=page.frames().find(f=>f.url().includes('/detail'));
 await frame.waitForFunction(()=>typeof window.mobileTodoCanLeave==='function');
 assert.deepEqual(requests,[]);
 await page.evaluate(task=>document.querySelector('iframe').contentWindow.postMessage({type:'ai2apps.todo.initialize-detail',mountToken:'token',taskId:'one',directoryId:'d',snapshot:{directories:[{id:'d',title:'Folder'}],tasks:[task]}},location.origin),task);
 await frame.waitForFunction(()=>document.getElementById('description').value==='Only in detail');
 assert.deepEqual(requests,['/v1/mobile/todo/tasks/one/detail']);
 assert.match(await frame.locator('#runs').innerText(),/Result text/);
 assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
