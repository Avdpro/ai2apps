const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs');
const {chromium}=require('playwright');
const source=fs.readFileSync('web/static/js/mobile_todo.js','utf8');
test('mobile execution selects project/thread, saves binding then runs; ChatGPT uses official universal link',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width:390,height:844}});
 await page.setContent('<div id="results"></div>');
 await page.evaluate(()=>{
  window.$=id=>document.getElementById(id);window.mt=x=>x;window.current={id:'t',revision:1};window.busy=false;window.dirty=false;window.shellDetail=false;window.calls=[];window.notice=()=>{};window.refresh=async()=>{};window.data={tasks:[current]};window.edit=()=>{};
  window.api=async(path,method,body)=>{
   calls.push({path,method,body});
   if(path.endsWith('/execution')&&!method)return {executor:'codex_desktop',codex:{project_path:'/repo',thread_id:'thread'}};
   if(path==='/executors')return [{id:'codex_desktop',name:'Codex Desktop',available:true}];
   if(path==='/codex/projects')return {data:[{path:'/repo',name:'Repo'}]};
   if(path.startsWith('/codex/threads'))return {data:[{id:'thread',name:'Existing conversation'}]};
   return {id:'t',revision:current.revision+1};
  };
 });
 await page.addScriptTag({content:source.slice(source.indexOf('    function renderExecution('),source.indexOf('    function renderAttachments('))+'\nrenderExecution(current);'});
 await page.getByRole('button',{name:'配置与执行'}).click();
 await page.waitForFunction(()=>document.querySelectorAll('option').length===4);
 assert.equal(await page.getByLabel('Codex 对话').inputValue(),'thread');
 assert.equal(await page.getByRole('link',{name:'打开 ChatGPT'}).getAttribute('href'),'https://chatgpt.com/#native');
 await page.getByRole('button',{name:'开始执行',exact:true}).click();
 await page.waitForFunction(()=>calls.some(c=>c.path==='/tasks/t/run'));
 const writes=await page.evaluate(()=>calls.filter(c=>c.method));
 assert.deepEqual(writes.map(x=>x.path),['/tasks/t/codex/desktop','/tasks/t/execution','/tasks/t/run']);
 assert.equal(writes[0].body.binding.thread_id,'thread');assert.equal(writes[1].body.revision,2);
 }finally{await browser.close();}
});
