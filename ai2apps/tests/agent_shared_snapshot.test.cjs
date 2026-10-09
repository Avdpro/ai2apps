const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const context={window:{addEventListener(){}},fetch:async(url)=>{assert.equal(url,'/admin/static/js/browser_snapshot.js?v=upload-controls-2');return {ok:true,text:async()=>fs.readFileSync(__dirname+'/../web/static/js/browser_snapshot.js','utf8')};}};
vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8'),context);
const Client=context.window.AI2AppsBiDi.AI2AppsPageClient;
test('observation and target resolution use the shared enhanced snapshot and retain refs',async()=>{
 const client=new Client({}),calls=[];
 client.callJSON=async(source,args)=>{calls.push({source,args});return {url:'https://weibo.com/',title:'微博',text:'需要登录',html:'<button data-ai2apps-ref="e1">登录</button>',htmlTruncated:false,
  items:[{ref:'e1',tag:'button',text:'登录',rect:[1,2,30,40],disabled:false},{ref:'e2',tag:'div',text:'内容',editable:true,rect:[2,3,40,50]}]};};
 const observation=await client.explorationObservation();
 assert.match(observation.html,/data-ai2apps-ref/);assert.equal(observation.controls[0].ref,'e1');
 assert.equal((await client.findTarget('e1')).name,'登录');assert.equal((await client.findTarget('内容',{operation:'input'})).ref,'e2');
 assert.equal(calls.length,3);assert.ok(calls.every(call=>call.source.includes('data-ai2apps-shadow-root')));
 assert.ok(calls.every(call=>call.args[0].htmlMode==='visible'));
});
