const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/owner_session.js'),'utf8');
async function setup(savedUrl, resumeUrl, mobile = false) {
    const nodes = [], storage = new Map(savedUrl ? [['ai2apps.owner.recovery-url',savedUrl]] : []);
    const listeners = {}, calls = [], timeouts = [], intervals = [];
    let locked = false, fail = false, code=401, redirects=[], removedFrames=0;
    let identity=savedUrl; const shell={inert:false};
    const logout={addEventListener:(name,fn)=>listeners.logout=fn};
    const document = {
        visibilityState:'visible',
        getElementById:()=>mobile?shell:null,
        addEventListener:(name,fn)=>listeners[name]=fn,
        querySelector:()=>logout,
        querySelectorAll:()=>[{remove(){removedFrames++;}}],
        createElement:(tag)=>{ const n={tag,style:{},append(){},remove(){this.removed=true;},addEventListener(){}}; nodes.push(n); return n; },
        body:{dataset:{},append(){},replaceChildren(){ locked=true; }},
    };
    vm.runInNewContext(source, {sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},document,window:{addEventListener(){},top:{location:{replace:url=>redirects.push(url)}}},location:{origin:"https://device-test.ai2apps.com"},URL,Date,AbortController,
        setInterval:(fn)=>intervals.push(fn),clearInterval(){},
        setTimeout:(fn)=>timeouts.push(fn),clearTimeout(){},
        fetch:async (url,options)=>{ calls.push({url,options}); if(code==='network')throw Error('offline'); return {ok:!fail,status:fail?code:200,json:async()=>({leaseExpiresAt:Date.now()/1000+60,ownerResumeUrl:resumeUrl,ownerAuthorizationUrl:identity})}; },
    });
    await new Promise(resolve=>setImmediate(resolve));
    return {shell,removedFrames:()=>removedFrames,recover:(url=savedUrl)=>{fail=false;identity=url;},redirects,storage,nodes,listeners,calls,timeouts,intervals,locked:()=>locked,fail:(status=401)=>{fail=true;code=status;}};
}
test('polling checks status without manufacturing foreground activity',async()=>{
    const e=await setup();
    await e.intervals[0]();
    assert.ok(e.calls.length>=2);
    assert.ok(e.calls.every(call=>call.url.endsWith('/status')));
});
test('only real foreground interactions report activity, throttled',async()=>{
    const e=await setup();
    await e.listeners.pointerdown({isTrusted:false});
    assert.equal(e.calls.filter(call=>call.url.endsWith('/activity')).length,0);
    await e.listeners.keydown({isTrusted:true});
    await e.listeners.pointerdown({isTrusted:true});
    assert.equal(e.calls.filter(call=>call.url.endsWith('/activity')).length,1);
});
test('authorization loss clears frames and private page',async()=>{
    const e=await setup();e.fail();
    await e.intervals[0]();
    assert.equal(e.locked(),true);
});

test('an old browser lease timer revalidates a renewed server session',async()=>{
    const e=await setup();
    await e.intervals[0]();
    const before=e.calls.length;
    await e.timeouts.at(-1)();
    assert.equal(e.locked(),false);
    assert.equal(e.calls.length,before+1);
    assert.ok(e.calls.at(-1).url.endsWith('/status'));
    e.fail();
    await e.timeouts.at(-1)();
    assert.equal(e.locked(),true);
});
test('returning to the foreground revalidates without reporting activity',async()=>{
    const e=await setup();
    await e.listeners.visibilitychange();
    assert.ok(e.calls.length>=2);
    assert.ok(e.calls.every(call=>call.url.endsWith('/status')));
});

const accountUrl='https://coder.ai2apps.com/u/b8696bee-d730-46b6-848c-e41f1f96a0b4?entry=owner-home';
test('first status failure still offers validated account URL from this tab',async()=>{
    const e=await setup(accountUrl); e.fail(); await e.intervals[0]();
    assert.equal(e.nodes.find(n=>n.tag==='a').href,accountUrl);
    assert.ok(e.nodes.some(n=>n.tag==='h1'));
});
test('untrusted recovery URL cannot become a redirect',async()=>{
    const e=await setup('https://evil.example/u/account'); e.fail(); await e.intervals[0]();
    assert.equal(e.nodes.some(n=>n.tag==='a'),false);
    assert.ok(e.nodes.some(n=>n.tag==='button'));
});

test('network and server errors never destroy the current private page',async()=>{
 for(const code of [429,500,502,503,504,'network']){const e=await setup();e.fail(code);await e.intervals[0]();assert.equal(e.locked(),false);assert.equal(e.redirects.length,0);}
});
const resumeUrl=accountUrl+'&resume=1&device_origin=https%3A%2F%2Fdevice-test.ai2apps.com';
test('401 resumes through Cloud only with an explicit origin-bound capability',async()=>{
 const e=await setup(accountUrl,resumeUrl);e.fail();await e.intervals[0]();assert.deepEqual(e.redirects,[resumeUrl]);assert.ok(e.storage.get('ai2apps.owner.resume-at'));
});
test('403 and recent recovery attempts never auto-reauthorize',async()=>{
 const e=await setup(accountUrl,resumeUrl);e.fail(403);await e.intervals[0]();assert.equal(e.redirects.length,0);assert.equal(e.locked(),true);
 const b=await setup(accountUrl,resumeUrl);b.storage.set('ai2apps.owner.resume-at',String(Date.now()));b.fail();await b.intervals[0]();assert.equal(b.redirects.length,0);assert.equal(b.locked(),true);
});
test('a resume hint for another device or arbitrary URL is rejected',async()=>{
 for(const url of [resumeUrl.replace('device-test','device-other'),resumeUrl+'&resume=1','https://evil.example']){const e=await setup(accountUrl,url);e.fail();await e.intervals[0]();assert.equal(e.redirects.length,0);}
});

test('failed logout preserves retry and never auto-resumes on a racing 401',async()=>{
    const e=await setup(accountUrl);
    e.fail(503);
    await e.listeners.logout();
    assert.equal(e.locked(),false);
    e.fail(401);
    await e.intervals[0]();
    assert.equal(e.redirects.length,0);
});
test('successful logout locks local UI',async()=>{
    const e=await setup(accountUrl);
    await e.listeners.logout();
    assert.equal(e.locked(),true);
    assert.equal(e.redirects.length,0);
});

 test('Mobile expiry retains frame tree and never redirects automatically',async()=>{
 const e=await setup(accountUrl,resumeUrl,true);e.fail(401);await e.intervals[0]();
 assert.equal(e.locked(),false);assert.equal(e.removedFrames(),0);assert.equal(e.shell.inert,true);
 assert.deepEqual(e.redirects,[]);assert.ok(e.nodes.some(n=>n.tag==='a'&&n.href===resumeUrl));
 await e.intervals[0]();assert.equal(e.nodes.filter(n=>n.tag==='main').length,1);
 });
 test('Mobile renewed same-account lease unlocks existing UI without replay',async()=>{
 const e=await setup(accountUrl,resumeUrl,true);e.fail(401);await e.intervals[0]();
 e.recover();await e.intervals[0]();assert.equal(e.shell.inert,false);assert.equal(e.removedFrames(),0);
 assert.deepEqual(e.redirects,[]);assert.ok(e.calls.every(c=>c.url.endsWith('/status')));
 });
 test('Mobile recovery with changed account destroys old private UI',async()=>{
 const e=await setup(accountUrl,resumeUrl,true);e.fail(401);await e.intervals[0]();
 e.recover('https://coder.ai2apps.com/u/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa?entry=owner-home');
 await e.intervals[0]();assert.equal(e.locked(),true);assert.equal(e.removedFrames(),1);
 });
 test('Mobile explicit logout still destroys frames instead of preserving them',async()=>{
 const e=await setup(accountUrl,resumeUrl,true);await e.listeners.logout();
 assert.equal(e.locked(),true);assert.equal(e.removedFrames(),1);assert.deepEqual(e.redirects,[]);
 });
