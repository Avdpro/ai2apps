const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/mobile_chat.js','utf8');
const context=vm.createContext({TextDecoder,Error});
vm.runInContext(source.slice(source.indexOf('    async function readChatReply('),source.indexOf('    async function agentRun(')),context);
function stream(parts){let i=0;return {headers:{get:()=> 'text/event-stream'},body:{getReader:()=>({read:async()=>i<parts.length?{value:Buffer.from(parts[i++]),done:false}:{done:true},cancel:async()=>{},releaseLock(){}})}};}
test('accepts compact SSE, CRLF, split chunks and trailing frame without newline',async()=>{
 const text=await context.readChatReply(stream(['data:{"choices":[{"delta":{"content":"你"}}]}\r\n','da','ta: {"choices":[{"delta":{"content":"好"}}]}']),()=>{});
 assert.equal(text,'你好');
});
test('stream error remains an error rather than a saved empty reply',async()=>{
 await assert.rejects(context.readChatReply(stream(['data: {"error":{"message":"Model unavailable"}}\n']),()=>{}),/Model unavailable/);
});
test('reasoning only and empty completion are not successful replies',async()=>{
 await assert.rejects(context.readChatReply(stream(['data: {"choices":[{"delta":{"reasoning_content":"thinking"}}]}\ndata: [DONE]\n']),()=>{}),/未返回/);
});
test('handles a JSON completion when upstream does not stream',async()=>{
 const result=await context.readChatReply({headers:{get:()=> 'application/json'},json:async()=>({choices:[{message:{content:'hello'}}]})},()=>{});
 assert.equal(result,'hello');
});
test('Cloud lifecycle failure exposes actual provider reason',async()=>{
 await assert.rejects(context.readChatReply(stream(['data: '+JSON.stringify({choices:[{delta:{ai2apps_cloud:{phase:'failed',error:{message:'Unsupported temperature'}}}}]})+'\n']),()=>{}),/Unsupported temperature/);
});
test('structured content matches desktop text rendering',async()=>{
 const result=await context.readChatReply(stream(['data: '+JSON.stringify({choices:[{delta:{content:[{type:'text',text:'Hi! '},{type:'output_text',text:'How can I help?'}]}}]})+'\n']),()=>{});
 assert.equal(result,'Hi! How can I help?');
});
test('Mobile leaves temperature to provider just like desktop defaults',async()=>{
 let submitted;
 const direct=source.slice(source.indexOf('    async function directChat('),source.indexOf('    async function readChatReply('));
 const ctx=vm.createContext({content:{messages:[]},current:{title:'test'},model:{value:'cloud'},working(){},persist:async()=>{},addMessage:()=>({copy:{},node:{remove(){}}}),fetch:async(url,options)=>{submitted=JSON.parse(options.body);return {ok:true};},readChatReply:async()=> 'ok'});
 await vm.runInContext(direct+'\ndirectChat("hi","hi")',ctx);
 assert.equal(submitted.temperature,null);
});
