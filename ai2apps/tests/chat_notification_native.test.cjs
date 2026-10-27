const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path');
const source=fs.readFileSync(path.resolve(__dirname,'../../ai2apps-ios/AI2Apps/WebSession.swift'),'utf8');
const script=source.match(/const controller=new AbortController\(\),timer=setTimeout\(\(\)=>controller.abort\(\),10000\);[\s\S]*?finally \{clearTimeout\(timer\);\}/)[0];
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
for(const agent of [true,false])test(`iOS Chat notification uses ${agent?'signed Mobile':'Owner'} identity`,async()=>{
 const calls=[],response={ok:true,json:async()=>({type:'app_route'})};
 const run=new AsyncFunction('target','window','fetch',script);
 await run({app_id:'ai2apps.general-chat'},{AI2AppsAgentConnection:{status:()=>({agent}),signedFetch:async(url,options)=>{calls.push(['signed',url,JSON.parse(options.body)]);return response;}}},async(url,options)=>{calls.push(['owner',url,JSON.parse(options.body)]);return response;});
 assert.equal(calls.length,1);assert.equal(calls[0][0],agent?'signed':'owner');
 assert.equal(calls[0][1],agent?'/v1/mobile/chat/notification-target':'/v1/platform/notifications/resolve-target');
 assert.equal(calls[0][2].target.app_id,'ai2apps.general-chat');
});
