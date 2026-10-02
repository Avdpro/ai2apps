const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {test} = require('node:test');
const context = {window: {}, document: {documentElement: {lang: 'en'}}, console};
vm.createContext(context);
vm.runInContext(fs.readFileSync(__dirname + '/../ai2apps/web/static/js/discover.js', 'utf8'), context);

test('installed upgrades use the catalog release for models and other packages', async () => {
    for (const packageType of ['model', 'service', 'app', 'agent']) {
        const app = context.window.discoverApp();
        const local = {packageId: 'ai2apps/example', packageType, discovery: {kind: packageType}, version: '0.1.2'};
        const cloud = {...local, version: '0.1.3'};
        app.tab = 'installed';
        app.installed = [local];
        app.items = [cloud];
        assert.equal(app.showUpgrade(local), true);
        let target;
        app.install = async (item, approved, packageOnly) => {
            target = item;
            assert.equal(approved, false);
            assert.equal(packageOnly, true);
        };
        await app.upgrade(local);
        assert.equal(target, cloud);
        for (const version of ['0.1.2', '0.1.1']) {
            cloud.version = version;
            target = null;
            assert.equal(app.showUpgrade(local), false);
            await app.upgrade(local);
            assert.equal(target, null);
        }
        app.items = [];
        assert.equal(app.showUpgrade(local), false);
        await app.upgrade(local);
        assert.equal(target, null);
    }
});

test('Discover model install action does not gain a duplicate upgrade button', () => {
    const app = context.window.discoverApp();
    const local = {packageId: 'ai2apps/example', packageType: 'service', discovery: {kind: 'model'}, version: '0.1.2'};
    app.tab = 'discover'; app.installed = [local]; app.items = [{...local, version: '0.1.3'}];
    assert.equal(app.hasUpgrade(local), true);
    assert.equal(app.showUpgrade(local), false);
});

test('model upgrade without an install plan reaches package operation, including review retry', async () => {
    const calls = [];
    context.requestAnimationFrame = callback => callback();
    context.fetch = async (url, options) => {
        calls.push({url, body: JSON.parse(options.body)});
        return {ok: false, json: async () => ({error: {
            code: 'audit_review_required', message: 'Review required',
        }})};
    };
    const app = context.window.discoverApp();
    const local = {packageId: 'ai2apps/model-sol-refiner-mlx', packageType: 'service',
        discovery: {kind: 'model'}, version: '0.1.2'};
    app.tab = 'installed'; app.installed = [local]; app.items = [{...local, version: '0.1.3'}];
    app.installModel = () => { throw new Error('Must not request a model installation plan'); };
    await app.upgrade(local);
    assert.equal(app.installDialog.status, 'awaiting_review');
    assert.equal(calls.length, 1);
    assert.match(calls[0].url, /model-sol-refiner-mlx\/install-operations$/);
    assert.equal(calls[0].body.version, '0.1.3');
    assert.equal(calls[0].body.approve_review, false);
    await app.retryInstallDialog();
    assert.equal(calls.length, 2);
    assert.equal(calls[1].body.version, '0.1.3');
    assert.equal(calls[1].body.approve_review, true);
});
