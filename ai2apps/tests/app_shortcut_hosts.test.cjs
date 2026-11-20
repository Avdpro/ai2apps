const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function code(file,start,end){const s=fs.readFileSync(__dirname+'/../web/static/js/'+file,'utf8');const a=s.indexOf(start),b=s.indexOf(end,a);assert(a>=0&&b>a);return 'async function run(){'+s.slice(a,b).replace(/^\s*} else if/,'if')+'\n}}';}
const desktop=code('shell.js',"            } else if (message.type === 'ai2apps.shell.open-entry') {","            } else if (message.type === 'ai2apps.shell.open-gallery-preview') {");
const mobile=code('mobile.js',"        } else if(message.type==='ai2apps.shell.ack-app-state'){","        } else if (message.type === 'ai2apps.shell.open-browser-task') {");
for(const appId of ['fixture.alpha','different.beta'])test('Desktop shortcut host uses server target and replies to original caller: '+appId,async()=>{
 const calls=[],source={};const c={message:{type:'ai2apps.shell.open-entry',appId:'forged.target',appStateLaunch:'ascl_'+'a'.repeat(32)},currentId:'caller',currentInstanceId:'source-instance',bridgeTarget:{source},
  jsonRequest:async()=>({target:{app_id:appId}}),launch:async id=>{calls.push(id);c.currentId=id;c.currentInstanceId='target-instance';},saveAppStateIntent:(...a)=>calls.push(a),sendHostContext:()=>calls.push('context'),respondToBridgeTarget:(target,ok,result)=>calls.push({target,ok,result})};
 vm.createContext(c);vm.runInContext(desktop,c);await c.run();assert.equal(calls[0],appId);assert.equal(calls.at(-1).target.source,source);assert.equal(calls.at(-1).result.instanceId,'target-instance');
 c.message.appStateLaunch='https://malicious.invalid';await assert.rejects(c.run(),/Invalid/);
});
test('Mobile shortcut host admits only active trusted sources and pins server target',async()=>{
 const sent=[],source={},record={renderer:'core'},target={renderer:'core',token:'target-token',instanceId:'target-instance',frame:{contentWindow:{postMessage:m=>sent.push(m)}}};
 const c={record,message:{type:'ai2apps.shell.open-entry',appId:'forged',appStateLaunch:'ascl_'+'b'.repeat(32)},event:{source},frames:new Map([['caller',record],['fixture.alpha',target]]),activeAppId:'caller',appsById:new Map([['fixture.alpha',{}]]),location:{origin:'https://fixture'},request:async()=>({target:{app_id:'fixture.alpha'}}),openApp:async id=>{c.activeAppId=id;},sendBridgeResponse:(...args)=>sent.push(args)};
 vm.createContext(c);vm.runInContext(mobile,c);await c.run();assert.equal(target.appStateLaunch,c.message.appStateLaunch);assert.equal(sent.at(-1)[0],source);assert.equal(sent[0].instanceId,'target-instance');
 sent.length=0;c.activeAppId='caller';record.renderer='sandbox';await c.run();assert.equal(sent.length,0);
});
