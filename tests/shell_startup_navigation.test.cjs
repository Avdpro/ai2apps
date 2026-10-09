const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {execFileSync} = require('node:child_process');
const source = fs.readFileSync(path.join(__dirname, '../ai2apps/web/static/js/shell.js'), 'utf8');
const functions = source.slice(source.indexOf('    function provisioningReturnApp('), source.indexOf('    async function refreshAccountStatus('));
const video = status => ({status, intent: {returnTo: '/apps/ai2apps.video-studio'}});
function context(start, currentId = '', items = []) {
    const launches = [];
    let requests = 0;
    const state = {shellStart: start, currentId, launchSequence: 0, URL,
        window: {location: {origin: 'http://localhost'}}, console,
        byId: new Map([['ai2apps.video-studio', {}]]),
        request: async () => { requests++; return {items}; },
        launch: async id => launches.push(id)};
    vm.createContext(state);
    vm.runInContext(functions, state);
    return {state, launches, requests: () => requests};
}
for (const start of [null, 'home']) {
    test(`${start || 'refresh'} does not let old provisioning override navigation`, async () => {
        const c = context(start, '', [video('ready')]);
        assert.equal(await c.state.resumeProvisioningApp(), false);
        assert.equal(c.requests(), 0);
    });
}
test('refresh of current App retains its route', async () => {
    const c = context(null, 'ai2apps.general-chat', [video('failed')]);
    await c.state.resumeProvisioningApp();
    assert.equal(c.state.currentId, 'ai2apps.general-chat');
    assert.deepEqual(c.launches, []);
});
for (const status of ['ready', 'installing']) {
    test(`Runtime reconnect resumes ${status} provisioning`, async () => {
        const c = context('resume', '', [video('failed'), video(status)]);
        assert.equal(await c.state.resumeProvisioningApp(), true);
        assert.deepEqual(c.launches, ['ai2apps.video-studio']);
    });
}
test('stale failures do not reopen Video Studio', async () => {
    const c = context('resume', '', ['failed', 'cancelled', 'unsupported'].map(video));
    assert.equal(await c.state.resumeProvisioningApp(), false);
    assert.deepEqual(c.launches, []);
});
test('Runtime reconnect returns to Discover for legacy dependency continuation', async () => {
    const c = context('resume');
    c.state.byId.set('ai2apps.discover', {});
    c.state.request = async url => url.endsWith('/install-continuation')
        ? {continuation: {packageId: 'ai2apps/model-test'}} : {items: []};
    assert.equal(await c.state.resumeProvisioningApp(), true);
    assert.deepEqual(c.launches, ['ai2apps.discover']);
});
test('Discover ACPF awaiting restart returns to Discover', async () => {
    const c = context('resume', '', [{status: 'awaiting_restart',
        appId: 'ai2apps.discover', capability: 'model.package.install'}]);
    c.state.byId.set('ai2apps.discover', {});
    assert.equal(await c.state.resumeProvisioningApp(), true);
    assert.deepEqual(c.launches, ['ai2apps.discover']);
});
test('late Discover continuation cannot override user navigation', async () => {
    const c = context('resume');
    c.state.byId.set('ai2apps.discover', {});
    c.state.request = async url => {
        if (!url.endsWith('/install-continuation')) return {items: []};
        c.state.launchSequence++;
        return {continuation: {packageId: 'ai2apps/model-test'}};
    };
    assert.equal(await c.state.resumeProvisioningApp(), false);
    assert.deepEqual(c.launches, []);
});
test('late provisioning response cannot override subsequent Home navigation', async () => {
    const c = context('resume');
    c.state.request = async () => {c.state.launchSequence++; return {items: [video('ready')]};};
    assert.equal(await c.state.resumeProvisioningApp(), false);
    assert.deepEqual(c.launches, []);
});

const transformPath = path.join(__dirname, '../apps/ai2apps-acefox/scripts/apply-shell-navigation.py');
const transformed = execFileSync('python3', ['-c', `
import runpy, sys
module = runpy.run_path(sys.argv[1])
source = '  let activeConnection = null;\\n      const principal = Services.scriptSecurityManager.createContentPrincipal(\\n        Services.io.newURI(connection.shellURL),\\n    monitorBusy = true;\\n    try {\\n      const descriptor = await IOUtils.readJSON(descriptorPath);\\n      if (request.action == "open") {'
print(module['transform'](source))
`, transformPath], {encoding: 'utf8'});
const entry = transformed.slice(transformed.indexOf('      const navigation ='), transformed.indexOf('      const principal ='));
for (const [label, previous, epoch, reason, expected] of [
    ['first launch', null, 'a', 'helper-start', 'home'],
    ['Helper restart', 'a', 'b', 'helper-start', 'home'],
    ['menu service restart', 'a', 'b', 'menu-restart', 'home'],
    ['Runtime service restart', 'a', 'a', 'helper-start', 'resume'],
    ['Runtime restart after menu restart', 'b', 'b', 'menu-restart', 'resume'],
]) {
    test(label + ' selects correct native entry intent', async () => {
        const c = vm.createContext({URL, shellNavigationEpoch: previous,
            connection: {shellURL: 'http://localhost/v1/platform/client/shell'},
            readShellNavigation: async () => ({epoch, reason})});
        await vm.runInContext('(async () => {' + entry + '})()', c);
        assert.equal(new URL(c.connection.shellURL).hash, '#ai2apps-shell-start=' + expected);
        assert.equal(c.shellNavigationEpoch, epoch);
    });
}
