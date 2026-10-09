const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync('web/static/js/todo.js','utf8');
function setup(){
 const listeners=[],calls=[],errors=[];
 // Preserve the production module boundary and the entire initialization tail.
 const tail=source.slice(source.indexOf('safe(async()=>{await refresh(true);setInterval'));
 const declarations=`const state={runs:[{id:'run',task_id:'task'}],tasks:[{id:'task',revision:7}]};let dirty=false,fieldSavePending=false,pollBusy=false;const zh=true;function safe(fn){return async(...args)=>{try{return await fn(...args);}catch(e){errors.push(e.message);}}}const api=async(...args)=>calls.push(args),codexApi=api,refresh=async()=>{},renderRuns=()=>{};`;
 vm.runInNewContext('(function(){'+declarations+tail,{document:{addEventListener:(_,fn)=>listeners.push(fn)},calls,errors,setInterval(){}});
 return {calls,errors,click:async(selector,dataset)=>{const button={dataset,disabled:false};for(const fn of listeners)await fn({target:{closest:s=>s===selector?button:null}});assert.equal(button.disabled,false);}};
}
test('review handler registers inside module and submits revision then refreshes',async()=>{
 const h=setup();await h.click('[data-review-run]',{reviewRun:'run',decision:'completed'});
 assert.deepEqual(JSON.parse(JSON.stringify(h.calls)),[['/runs/run/review','POST',{decision:'completed',revision:7}]]);assert.deepEqual(h.errors,[]);
});
test('desktop open handler registers and calls the system endpoint',async()=>{
 const h=setup();await h.click('[data-open-codex]',{openCodex:'thread'});
 assert.deepEqual(JSON.parse(JSON.stringify(h.calls)),[['/threads/thread/open','POST',{}]]);assert.deepEqual(h.errors,[]);
});
