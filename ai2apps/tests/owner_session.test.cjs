const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname,'../web/static/js/owner_session.js'),'utf8');
function setup(savedUrl) {
    const nodes = [], storage = new Map(savedUrl ? [['ai2apps.owner.recovery-url',savedUrl]] : []);
    const listeners = {}, calls = [], timeouts = [], intervals = [];
    let locked = false, fail = false;
    const document = {
        visibilityState:'visible',
        addEventListener:(name,fn)=>listeners[name]=fn,
        querySelector:()=>null,
        querySelectorAll:()=>[{remove(){}}],
        createElement:(tag)=>{ const n={tag,append(){},addEventListener(){}}; nodes.push(n); return n; },
        body:{replaceChildren(){ locked=true; }},
    };
    vm.runInNewContext(source, {sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},document,window:{addEventListener(){}},URL,Date,
        setInterval:(fn)=>intervals.push(fn),clearInterval(){},
        setTimeout:(fn)=>timeouts.push(fn),clearTimeout(){},
        fetch:async (url,options)=>{ calls.push({url,options}); return {ok:!fail,json:async()=>({leaseExpiresAt:Date.now()/1000+60})}; },
    });
    return {nodes,listeners,calls,timeouts,intervals,locked:()=>locked,fail:()=>fail=true};
}
test('polling checks status without manufacturing foreground activity',async()=>{
    const e=setup();
    await e.intervals[0]();
    assert.ok(e.calls.length>=2);
    assert.ok(e.calls.every(call=>call.url.endsWith('/status')));
});
test('only real foreground interactions report activity, throttled',async()=>{
    const e=setup();
    await e.listeners.pointerdown({isTrusted:false});
    assert.equal(e.calls.filter(call=>call.url.endsWith('/activity')).length,0);
    await e.listeners.keydown({isTrusted:true});
    await e.listeners.pointerdown({isTrusted:true});
    assert.equal(e.calls.filter(call=>call.url.endsWith('/activity')).length,1);
});
test('authorization loss clears frames and private page',async()=>{
    const e=setup();e.fail();
    await e.intervals[0]();
    assert.equal(e.locked(),true);
});

test('an old browser lease timer revalidates a renewed server session',async()=>{
    const e=setup();
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
    const e=setup();
    await e.listeners.visibilitychange();
    assert.ok(e.calls.length>=2);
    assert.ok(e.calls.every(call=>call.url.endsWith('/status')));
});

const accountUrl='https://coder.ai2apps.com/u/b8696bee-d730-46b6-848c-e41f1f96a0b4?entry=owner-home';
test('first status failure still offers validated account URL from this tab',async()=>{
    const e=setup(accountUrl); e.fail(); await e.intervals[0]();
    assert.equal(e.nodes.find(n=>n.tag==='a').href,accountUrl);
    assert.ok(e.nodes.some(n=>n.tag==='h1'));
});
test('untrusted recovery URL cannot become a redirect',async()=>{
    const e=setup('https://evil.example/u/account'); e.fail(); await e.intervals[0]();
    assert.equal(e.nodes.some(n=>n.tag==='a'),false);
    assert.ok(e.nodes.some(n=>n.tag==='button'));
});
