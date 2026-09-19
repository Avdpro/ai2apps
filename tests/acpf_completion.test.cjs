const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync('ai2apps/web/static/js/capability_provisioning.js', 'utf8')
    .replace('const overlay = sheet(session);', 'const overlay = window.testSheet(session);')
    .replaceAll('render(overlay, session);', 'window.testRender(overlay, session);');
async function scenario(restored) {
    const store = new Map();
    const ready = {id: 's1', status: 'ready', appId: 'chat', intent: {completionPolicy: 'resume_action', idempotencyKey: 'once'}};
    let removed = false, click, polls = 0, resolved = false;
    const overlay = {remove() {removed = true;}, addEventListener(name, fn) {click = fn;}};
    const context = {URLSearchParams, localStorage: {getItem: key => store.get(key), setItem: (k,v) => store.set(k,v), removeItem: k => store.delete(k)},
        setTimeout: done => done(), window: {location: {hash: ''}, testSheet: () => overlay, testRender: () => {}},
        fetch: async () => {polls++; return {ok: true, json: async () => ready};}};
    vm.runInNewContext(source, context);
    if (restored) store.set('ai2apps.acpf.pending.chat', JSON.stringify({sessionId: 's1'}));
    const api = context.window.AI2AppsCapabilities;
    const promise = (restored ? api.resume('chat') : api.runSession({...ready, status: 'downloading_checkpoint'}, 'chat'))
        .then(value => {resolved = true; return value;});
    for (let i = 0; i < 20; i++) await Promise.resolve();
    assert.equal(polls, 1);
    assert.equal(removed, false);
    assert.equal(resolved, false);
    await click({target: {closest: () => ({dataset: {action: 'cancel'}})}});
    assert.equal(removed, false);
    await click({target: {closest: () => ({dataset: {action: 'done'}})}});
    const result = await promise;
    assert(removed);
    assert.equal(result.outcome, 'configured');
    assert.equal(result.completion.shouldResumeAction, true);
    assert.equal(result.completion.idempotencyKey, 'once');
    assert.equal(polls, 1);
}
(async () => {await scenario(false); await scenario(true); console.log('ACPF success waits for confirmation, including restored sessions');})()
    .catch(error => {console.error(error); process.exitCode = 1;});
