const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');
function setup(mode='natural'){
 const timers=[],window={addEventListener(){}};vm.runInNewContext(source,{window,navigator:{platform:'MacIntel'},URL,Map,crypto:require('node:crypto').webcrypto,setTimeout:(fn,ms)=>{timers.push(ms);fn();},clearTimeout});
 const field={tagName:'TEXTAREA',value:'',selectionStart:0,selectionEnd:0,maxLength:-1,isConnected:true};
 const page={window:{},document:{activeElement:field,queryCommandSupported:()=>true,execCommand:(_,unused,text)=>{insert(text);return true;}}};
 function insert(text){field.value=field.value.slice(0,field.selectionStart)+text+field.value.slice(field.selectionEnd);field.selectionStart+=text.length;field.selectionEnd=field.selectionStart;}
 Object.defineProperty(page,'navigator',{get(){throw Error('Clipboard must not be accessed');}});
 let modifier=false;

 const client=new window.AI2AppsBiDi.AI2AppsPageClient({});client.contextId='tab';client.interactionSettings=async()=>({interaction_mode:mode});
 const calls=[],pauses=[];client.interactionPause=async m=>pauses.push(m);client.connection={command:async(method,params)=>{calls.push({method,params});
 if(method==='input.performActions')for(const action of params.actions[0].actions){
  if(action.value==='\uE03D'){modifier=action.type==='keyDown';continue;}
  if(action.type!=='keyDown')continue;
  if(modifier&&action.value==='a'){field.selectionStart=0;field.selectionEnd=field.value.length;continue;}
  if(action.value==='\uE003'){insert('');continue;}
  if(action.value==='\uE007')continue;
  if(params.actions[0].type==='key')insert(action.value);
 }
 return {result:{sharedId:'chosen-input'}};}};
 client.callJSON=async(fn,args=[])=>vm.runInNewContext('('+fn+')',page)(...args);
 return {client,calls,pauses,field,page,timers};
}
test('natural pointer accelerates and decelerates; fast pointer has a single immediate move',async()=>{
 for(const mode of ['natural','fast']){const {client,calls,pauses}=setup(mode);await client.naturalPointer({rect:{x:400,y:200,width:100,height:50}},{click:false});
 const moves=calls[0].params.actions[0].actions.filter(a=>a.type==='pointerMove');
 assert.equal(moves.length,mode==='natural'?12:1);assert.equal(pauses[0],mode);
 if(mode==='natural'){const speeds=moves.map((m,i)=>m.x-(moves[i-1]?.x||0));assert.ok(speeds[5]>speeds[0]);assert.ok(speeds[5]>speeds[11]);}
 }
});
test('long Unicode input is complete, batched, replaced once and submitted only at the end',async()=>{
 for(const mode of ['natural','fast']){const {client,calls,field}=setup(mode),text='中😀x'.repeat(800);await client.typeText(text,{replace:true,submit:true});
 const actions=calls.flatMap(c=>c.params.actions[0].actions),typed=actions.filter(a=>a.type==='keyDown'&&!['\uE03D','a','\uE003','\uE007'].includes(a.value)).map(a=>a.value).join('');
 assert.equal(field.value,text);assert.ok(typed.length<30);assert.equal(actions.filter(a=>a.type==='keyDown'&&a.value==='\uE003').length,1);assert.equal(actions.at(-1).value,'\uE007');
 assert.equal(actions.some(a=>a.type==='pause'),mode==='natural');assert.ok(calls.length>1);
 }
});
test('natural upload arms capture before clicking, fills captured input and always cleans up',async()=>{
 const {client,calls}=setup();const order=[];client.findTarget=async()=>({ref:'upload',rect:{}});client.callJSON=async(fn)=>order.push(fn.includes('state.timer=')?'arm':'cleanup');client.naturalPointer=async()=>order.push('click');
 await client.setAttachmentFiles('upload',['/tmp/test.png']);assert.deepEqual(order,['arm','click','cleanup']);assert.equal(calls[1].method,'input.setFiles');assert.equal(calls[1].params.element.sharedId,'chosen-input');
 calls.length=0;order.length=0;client.connection.command=async()=>{throw Error('disconnected');};await assert.rejects(client.setAttachmentFiles('upload',['/tmp/test.png']),/disconnected/);assert.deepEqual(order,['arm','click','cleanup']);
});


test('200K input uses bounded bulk calls and pauses rather than 200K keystrokes',async()=>{
 const {client,calls,field,timers}=setup(),text='中文😀\n'.repeat(40000);
 field.value='replace me';field.selectionStart=field.selectionEnd=field.value.length;
 let chunks=0;const insert=client.insertTextChunk.bind(client);client.insertTextChunk=async(token,text)=>{assert.ok(Array.from(text).length<=8192);if(text)chunks++;return insert(token,text);};
 await client.typeText(text,{replace:true,submit:true});assert.equal(field.value,text);
 const actions=calls.flatMap(c=>c.params.actions?.[0]?.actions||[]);
 assert.ok(actions.filter(a=>a.type==='keyDown').length<=20);assert.ok(chunks<=25);
 assert.ok(timers.reduce((sum,n)=>sum+n,0)<10000);assert.equal(actions.at(-1).value,'\uE007');

});

test('bulk insertion refuses maxlength overflow before altering the field',async()=>{
 const {client,field,page,calls}=setup();field.value='original';field.maxLength=100;
 await assert.rejects(client.typeText('x'.repeat(600),{replace:true}),/maximum length/);
 assert.equal(field.value,'original');assert.equal(calls.length,0);assert.equal(page.window.__ai2appsBulkInputs,undefined);
});

test('bulk input stops on editor change, does not submit and cleans up its binding',async()=>{
 const {client,field,page,calls}=setup();const insert=client.insertTextChunk.bind(client);let count=0;
 client.insertTextChunk=async(token,text)=>{if(text&&++count===2)page.document.activeElement={};return insert(token,text);};
 await assert.rejects(client.typeText('x'.repeat(20000),{submit:true}),/editor changed/);
 assert.ok(field.value.length<20000);assert.equal(page.window.__ai2appsBulkInputs.size,0);
 assert.ok(!calls.some(c=>c.params.actions[0].actions.some(a=>a.value==='\uE007')));
});

test('editor truncation fails without automatic replay or submission',async()=>{
 const {client,field,page}=setup();page.document.execCommand=()=>{field.value+='truncated';return true;};
 await assert.rejects(client.typeText('x'.repeat(1000),{submit:true}),/truncated/);
 assert.equal(page.window.__ai2appsBulkInputs.size,0);
});
