const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/../web/static/js/agent_mini.js', 'utf8');
const execute = source.slice(source.indexOf('    async function executeInContext('), source.indexOf('    async function executeAgentCall('));
for (const [delay, expected] of [[undefined,3000],[0,0],[5000,5000]]) {
    test(`open waits for navigation, delay ${expected}, then content stability before observation`, async () => {
        const events = [];
        const bidi = {contextId:'tab-1', pageState:async()=>{events.push('observe');return {url:'https://example.com'};},
            connection:{command:async(method,args)=>{events.push('navigate');assert.equal(method,'browsingContext.navigate');assert.equal(args.wait,'complete');}},
            waitForStability:async(timeout,opts)=>{events.push('stability');assert.equal(opts.requireContent,true);return {stable:true};}};
        const ctx = {client:async()=>bidi,state:{draft:{site_scope:[]}},scopeAllows:()=>true,
            setTimeout:(resolve,ms)=>{events.push(ms);resolve();}};
        vm.runInNewContext(execute+'\nglobalThis.execute=executeInContext;',ctx);
        const result = await ctx.execute({operation:'open',description:'Open example',arguments:{url:'https://example.com',...(delay===undefined?{}:{delay_ms:delay})}});
        assert.deepEqual(events,['observe','navigate',expected,'stability','observe']);
        assert.equal(result.evidence.result.delay_ms,expected);
    });
}

test('stability with required content does not treat an unchanged empty document as ready',async()=>{
    const sdk=fs.readFileSync(__dirname+'/../web/static/js/browser_bidi_client.js','utf8');
    const method=sdk.slice(sdk.indexOf('        async waitForStability('),sdk.indexOf('        async waitState('));
    let now=0,calls=0;
    const ctx={Date:{now:()=>now},setTimeout:resolve=>{now+=500;resolve();}};
    vm.runInNewContext('class Client {'+method+'}; globalThis.Client=Client;',ctx);
    const client=new ctx.Client();
    client.pageState=async()=>{calls++;return {fingerprint:'empty',text_length:0,items:[]};};
    const result=await client.waitForStability(2000,{requireContent:true});
    assert.equal(result.stable,false);
    assert.ok(calls>=4);
});
