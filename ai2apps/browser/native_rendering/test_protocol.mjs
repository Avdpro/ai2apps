// Exercise the actual native module methods with controlled window/timer primitives.
// C++ widget effects are separately verified in the packaged AceFox native probe.
import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
const root=process.argv[2];
const source=fs.readFileSync(root+'/remote/webdriver-bidi/modules/root/browsingContext.sys.mjs','utf8');
const methods=source.slice(source.indexOf('  #renderingWindow('),source.indexOf('  async hideBrowserWindow('));
const timers=new Map();let next=0;let role='shell';
function window(){return {closed:false,windowUtils:{isWindowFullyOccluded:true,isCompositorPaused:true,ai2AppsRenderingLeaseCount:0,adjustAI2AppsRenderingLease(delta){this.ai2AppsRenderingLeaseCount+=delta;assert(this.ai2AppsRenderingLeaseCount>=0);}}};}
const a=window(),b=window();const contexts={A:{topChromeWindow:a},B:{topChromeWindow:b},frame:{parent:{},topChromeWindow:a}};
const errors={UnsupportedOperationError:Error,InvalidArgumentError:Error};
const sandbox={Services:{env:{get:(name)=>name==='AI2APPS_BROWSER_ROLE'?role:'1'},uuid:{generateUUID:()=>randomUUID()}},lazy:{error:errors,assert:{string(value){assert.equal(typeof value,'string');}},logger:{debug(){}}},setTimeout(fn){const id=++next;timers.set(id,fn);return id;},clearTimeout(id){timers.delete(id);},Date};
const cls=vm.runInNewContext(`(class {#renderingLeases=new Map();#subscribedEvents=new Set();#contextListener={startListening(){},stopListening(){}};_getNavigable(id){return contexts[id];}${methods}destroy(){for(const id of [...this.#renderingLeases.keys()])this.#dropRenderingLease(id)}})`,{...sandbox,contexts});
const module=new cls();
contexts.C={topChromeWindow:{windowUtils:{}}};await assert.rejects(module.getRenderingLeaseCapabilities({context:'C'}));
assert.equal((await module.getRenderingLeaseCapabilities({context:'A'})).scope,'window');
const nativeState=await module.getRenderingLeaseState({context:'A'});assert.equal(nativeState.nativeOccluded,true);assert.equal(nativeState.chromeCompositorPaused,true);
assert.equal((await module.getRenderingLeaseCapabilities({context:'A'})).permanentSafeguard,true);
await assert.rejects(module.acquireRenderingLease({context:'frame',purpose:'capture',holder:'test'}));
for(const params of [{purpose:'invalid'},{ttlMs:0},{ttlMs:60001},{holder:''}])await assert.rejects(module.acquireRenderingLease({context:'A',purpose:'capture',holder:'test',...params}));
const x=await module.acquireRenderingLease({context:'A',purpose:'capture',holder:'test'});
const y=await module.acquireRenderingLease({context:'A',purpose:'input',holder:'other'});
const z=await module.acquireRenderingLease({context:'B',purpose:'layout',holder:'other'});
assert.equal(a.windowUtils.ai2AppsRenderingLeaseCount,2);assert.equal(b.windowUtils.ai2AppsRenderingLeaseCount,1);
await assert.rejects(module.releaseRenderingLease({context:'B',lease:x.lease}));
await module.releaseRenderingLease({context:'A',lease:x.lease});assert.equal(a.windowUtils.ai2AppsRenderingLeaseCount,1);
assert.equal((await module.releaseRenderingLease({context:'A',lease:x.lease})).released,false);
await module.renewRenderingLease({context:'A',lease:y.lease});
for(const [id,fn] of [...timers]){timers.delete(id);fn();}
assert.equal(a.windowUtils.ai2AppsRenderingLeaseCount,0);assert.equal(b.windowUtils.ai2AppsRenderingLeaseCount,0);
await assert.rejects(module.renewRenderingLease({context:'A',lease:y.lease}));
await module.acquireRenderingLease({context:'A',purpose:'input',holder:'test'});module.destroy();assert.equal(a.windowUtils.ai2AppsRenderingLeaseCount,0);
role='other';await assert.rejects(module.getRenderingLeaseCapabilities({context:'A'}));

// Run real connection dispatch/close logic, including shared-session isolation
// and an acquisition whose response races with transport close.
const connectionSource=fs.readFileSync(root+'/remote/webdriver-bidi/WebDriverBiDiConnection.sys.mjs','utf8').replace(/^import .*;$/mg,'').replace(/export /g,'');
const logger={debug(){}};
const dependencies={pprint:(s,...a)=>String.raw(s,...a),assert:{positiveInteger(v){assert(v>0)},string(){},object(){},session(v){assert(v)}},error:{...errors,wrap:e=>e},WebDriverSession:{SESSION_FLAG_BIDI:'bidi'}};
class Base {constructor(){this.id=randomUUID();this.results=[];this.errors=[]}onPacket(){}onConnectionClose(){}send(p){this.results.push(p)}}
const Connection=vm.runInNewContext(connectionSource+';WebDriverBiDiConnection',{WebSocketConnection:Base,ChromeUtils:{now:()=>0,defineESModuleGetters:(obj)=>Object.assign(obj,dependencies),defineLazyGetter:(obj,key)=>obj[key]=logger},Services:{profiler:{IsActive:()=>false}}});
let pending;let releaseAcquisition;let ids=0;const owned=new Map();
const session={id:'shared',removeConnection(){},async execute(mod,cmd,p){
 if(cmd==='acquireRenderingLease') {const value={lease:String(++ids),expiresAt:Date.now()+60000};owned.set(value.lease,p.context);if(p.holder==='delayed')await new Promise(r=>releaseAcquisition=r);return value;}
 if(cmd==='releaseRenderingLease'){const released=owned.delete(p.lease);return {released};}
 if(cmd==='renewRenderingLease')return {expiresAt:Date.now()+60000};
}};
const first=new Connection(),second=new Connection();first.registerSession(session);second.registerSession(session);
let request=0;const packet=(command,params)=>({id:++request,method:'browsingContext.'+command,params});
await first.onPacket(packet('acquireRenderingLease',{context:'A',holder:'one'}));
await second.onPacket(packet('acquireRenderingLease',{context:'B',holder:'two'}));
await second.onPacket(packet('releaseRenderingLease',{context:'A',lease:'1'}));assert(owned.has('1'));
first.onConnectionClose();await Promise.resolve();assert(!owned.has('1'));assert(owned.has('2'));
pending=second.onPacket(packet('acquireRenderingLease',{context:'B',holder:'delayed'}));await Promise.resolve();second.onConnectionClose();releaseAcquisition();await pending;assert.equal(owned.size,0);
console.log('Native module and connection protocol checks passed: scope/refcount/invalid/expiry/renew/session/connection isolation/close race');
