const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function startup(){
 const nodes=new Map(),events={},posted=[];let deadline;
 const get=id=>{if(!nodes.has(id))nodes.set(id,{hidden:['app-content','startup-retry'].includes(id),attrs:{},setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];}});return nodes.get(id);};
 const g={document:{documentElement:{lang:'zh'},getElementById:get},location:{search:'?locale=zh'},URLSearchParams,
  setTimeout:fn=>{deadline=fn;return 1;},clearTimeout(){},addEventListener:(type,fn)=>{events[type]=fn;},parent:{postMessage:(...args)=>posted.push(args)}};
 g.window=g;vm.runInNewContext(fs.readFileSync(__dirname+'/../../packages/ai2apps-search-all/web/startup.js','utf8'),g);
 return {g,get,events,posted,timeout:()=>deadline()};
}
test('unfinished startup keeps interactive content hidden until explicitly ready',()=>{
 const s=startup();assert.equal(s.get('app-content').hidden,true);assert.equal(s.get('app-content').attrs['aria-busy'],'true');
 assert.equal(s.g.SearchAllStartup.complete(),true);assert.equal(s.get('app-content').hidden,false);assert.equal(s.get('startup').hidden,true);
 s.events.error({error:Error('later task failed')});assert.equal(s.get('app-content').hidden,false);
});
test('startup failure never reveals partial content; retry requests a fresh host mount',()=>{
 const s=startup();s.events.unhandledrejection({reason:Error('profiles unavailable')});
 assert.equal(s.get('app-content').hidden,true);assert.equal(s.get('startup-retry').hidden,false);
 assert.match(s.get('startup-message').textContent,/profiles unavailable/);
 assert.equal(s.g.SearchAllStartup.complete(),false);
 s.get('startup-retry').onclick();assert.equal(s.posted[0][0].type,'ai2apps:mini-app-retry');
});
test('startup timeout remains recoverable without revealing default markup',()=>{
 const s=startup();s.timeout();assert.equal(s.get('app-content').hidden,true);assert.equal(s.get('startup-retry').hidden,false);
});
