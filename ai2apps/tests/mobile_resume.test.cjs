const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/static/js/mobile.js'),'utf8').split('/* Temporary navigation diagnostics:')[0];
const shell=fs.readFileSync(path.join(__dirname,'../web/static/js/mobile.js'),'utf8');
const owner='https://coder.ai2apps.com/u/12345678-1234-1234-1234-123456789abc?entry=owner-home';
function fixture(){
 const data=new Map(),storage={getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)};
 const c={window:{},location:{origin:'https://device-one.ai2apps.com'},URL,Date,sessionStorage:storage};vm.createContext(c);vm.runInContext(source,c);
 return {c,data,position:c.window.ai2appsMobilePosition(owner)};
}
test('position saves only navigation identifiers, no draft, URL or handoff',()=>{
 const f=fixture();f.position.save({appId:'ai2apps.imagine-studio',browserMiniApp:'text-to-image',draft:'private',handoff:'secret',url:'https://example.com'});
 assert.equal(f.position.read().mini,'text-to-image');const raw=[...f.data.values()][0];
 for(const secret of ['private','secret','example.com'])assert.ok(!raw.includes(secret));
 assert.deepEqual(Object.keys(JSON.parse(raw)).sort(),['app','at','mini','scope']);
});
test('Home, logout clear, invalid identifiers and expired hints cannot reopen a Mini-App',()=>{
 const f=fixture();f.position.save({appId:'studio',browserMiniApp:'mini'});f.position.save({appId:null});assert.equal(f.position.read(),null);
 f.position.save({appId:'studio',browserMiniApp:'https://evil.test'});assert.equal(f.position.read().mini,null);
 f.position.clear();assert.equal(f.position.read(),null);
 f.position.save({appId:'studio'});for(const [k,v]of f.data)f.data.set(k,JSON.stringify({...JSON.parse(v),at:Date.now()-86400001}));
 assert.equal(f.position.read(),null);
});
test('position is bound to current verified account and device origin',()=>{
 const f=fixture();f.position.save({appId:'studio',browserMiniApp:'mini'});
 assert.equal(f.c.window.ai2appsMobilePosition(owner.replace('12345678','aaaaaaaa')).read(),null);
 f.c.location.origin='https://device-two.ai2apps.com';assert.equal(f.c.window.ai2appsMobilePosition(owner).read(),null);
 for(const url of ['https://evil.test/u/123',owner+'&token=x',owner+'#secret'])assert.equal(f.c.window.ai2appsMobilePosition(url),null);
});
test('storage disabled is nonfatal',()=>{
 const f=fixture();const bad={getItem(){throw Error()},setItem(){throw Error()},removeItem(){throw Error()}};
 const p=f.c.window.ai2appsMobilePosition(owner,bad);p.save({appId:'studio'});p.clear();assert.equal(p.read(),null);
});
async function bootFixture(retained=false, options={}){
 const events=[],app='ai2apps.imagine-studio',record={frame:{contentWindow:{}},token:'t',instanceId:'i'};
 const history={state:retained?{mobileRoot:true,appId:app,browserMiniApp:'mini'}:null,replaceState(s){this.state=s;events.push('home-history');}};
 const c={agentHome:false,agentConnected:false,homePath:'/mobile',URLSearchParams,location:{hash:retained?'#app='+app:'',pathname:'/mobile'},history,document:{body:{dataset:{ownerHome:options.local?'false':'true'}},addEventListener(name,handler){assert.equal(name,'visibilitychange');assert.equal(typeof handler,'function');}},
 request:async url=>url.endsWith('/apps')?{items:[{id:app}]}:url.endsWith('/mounts')?{items:[]}:{ownerAuthorizationUrl:owner},
 normalizeApp:x=>x,appsById:new Map(),mounts:new Map(),frames:new Map(),renderCatalog(){},renderDock(){},refreshIcons(){},
 window:{addEventListener(name,handler){assert.ok(['ai2apps-agent-connection-ready','pageshow'].includes(name));assert.equal(typeof handler,'function');},ai2appsMobilePosition:()=>options.noPosition?null:({read:()=>Object.hasOwn(options,'saved')?options.saved:({app,mini:'mini'}),save(){}})},notificationID:null,position:null,positionReady:false,savePosition(){events.push('save');},
 showHome(){events.push('home');},openApp:async(id,push)=>{events.push(push===false?'reuse-app-history':'open-app');c.frames.set(id,record);},
 mobileMiniAppNavigation:(id,sender,token,instance,action,mini)=>{assert.equal(action,'open');assert.equal(mini,'mini');assert.equal(sender,record.frame.contentWindow);events.push('open-mini');}};
 vm.createContext(c);const start=shell.indexOf('    async function boot()');const end=shell.indexOf('\n    boot();',start);
 assert.ok(end>start);vm.runInContext(shell.slice(start,end),c);await c.boot();return events;
}
test('fresh authorized document restores App then Mini-App without business requests',async()=>{
 assert.deepEqual(await bootFixture(),['home-history','home','open-app','open-mini','save']);
});
test('reclaimed document reuses existing App history rather than inserting another Home',async()=>{
 assert.deepEqual(await bootFixture(true),['reuse-app-history','open-mini','save']);
});

for (const [name,options] of [
 ['first visit with empty storage',{saved:null}],
 ['missing stored position',{saved:undefined}],
 ['unavailable position scope',{noPosition:true}],
 ['non-Owner Mobile session',{local:true}],
]) test(`Mobile boot succeeds at Home: ${name}`,async()=>{
 assert.deepEqual(await bootFixture(false,options),['home-history','home','save']);
});
test('explicit App route still opens without a saved Mini-App',async()=>{
 assert.deepEqual(await bootFixture(true,{saved:null}),['reuse-app-history','save']);
});
