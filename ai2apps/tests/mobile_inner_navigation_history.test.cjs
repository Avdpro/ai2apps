const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const host=fs.readFileSync(__dirname+'/../web/static/js/mobile.js','utf8');
function fixture(){
 const sent=[],states=[],backs=[];const active={token:'mount-one',instanceId:'instance-one',renderer:'trusted',loaded:true,frame:{contentWindow:{postMessage:(m,origin)=>sent.push({m,origin})},hidden:false}};
 const other={token:'mount-two',instanceId:'instance-two',renderer:'trusted',loaded:true,frame:{contentWindow:{}}};
 const history={state:{appId:'arbitrary.app'},replaceState(s){this.state=s;states.push(['replace',s]);},pushState(s){this.state=s;states.push(['push',s]);},back(){backs.push(true);}};
 const c={frames:new Map([['arbitrary.app',active],['other.app',other]]),activeAppId:'arbitrary.app',history,location:{origin:'https://fixture.test',href:'https://fixture.test/mobile'},window:{location:{origin:'https://fixture.test'}},renderDock(){},loading:{hidden:false},errorView:{hidden:false},displayMount(){throw Error('unexpected remount');}};
 vm.createContext(c);let start=host.indexOf('        const record = Array.from(frames.values()).find'),end=host.indexOf('\n    });',start);vm.runInContext('async function message(event){'+host.slice(start,end)+'}',c);
 start=host.indexOf('        const uiRecord=frames.get(appId);');end=host.indexOf("        const intelRecord=frames.get('ai2apps.intelligence');",start);vm.runInContext('function pop(event){const appId=event.state?.appId;'+host.slice(start,end)+'}',c);
 return {c,active,other,history,sent,states,backs,send:(r,data={},origin='https://fixture.test')=>c.message({source:r.frame.contentWindow,origin,data:{type:'ai2apps.shell.navigation.push',mountToken:r.token,instanceId:r.instanceId,depth:1,...data}})};
}
test('inner history belongs only to the active trusted mount and advances one UI at a time',async()=>{
 const f=fixture();await f.send(f.other);await f.send(f.active,{mountToken:'wrong'});await f.send(f.active,{},'https://foreign.test');await f.send(f.active,{instanceId:'wrong'});assert.equal(f.states.length,0);
 f.active.renderer='sandbox';await f.send(f.active);assert.equal(f.states.length,0);f.active.renderer='trusted';
 await f.send(f.active,{depth:2});await f.send(f.active,{depth:-1});assert.equal(f.states.length,0);
 await f.send(f.active);assert.deepEqual(f.states.map(x=>x[0]),['replace','push']);assert.equal(f.states[0][1].appUiDepth,0);assert.equal(f.history.state.appUiDepth,1);assert.equal(f.history.state.appId,'arbitrary.app');await f.send(f.active,{depth:2});assert.equal(f.history.state.appUiDepth,2);
 await f.send(f.active,{type:'ai2apps.shell.navigation.back'});await f.send(f.active,{type:'ai2apps.shell.navigation.back'});assert.equal(f.backs.length,1);
});
test('native pop restores the same mounted App without animation or loading; button pop animates once',()=>{
 const f=fixture();const state={appId:'arbitrary.app',appUiMount:f.active.token,appUiDepth:1};f.c.pop({state});assert.equal(f.sent[0].m.animate,false);assert.equal(f.sent[0].m.depth,1);assert.equal(f.active.frame.hidden,false);assert.equal(f.c.loading.hidden,true);assert.equal(f.c.errorView.hidden,true);
 f.active.uiBackPending=true;f.c.pop({state:{...state,appUiDepth:0}});assert.equal(f.sent[1].m.animate,true);assert.equal(f.active.uiBackPending,false);assert.equal(f.sent[1].m.instanceId,f.active.instanceId);
 f.c.pop({state:{...state,appUiMount:'old-mount'}});assert.equal(f.sent.length,2);f.active.renderer='sandbox';f.c.pop({state});assert.equal(f.sent.length,2);
});
