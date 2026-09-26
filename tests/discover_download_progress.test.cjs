const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const context = {window: {t: key => key, setTimeout: done => done()},
    document: {documentElement: {lang: 'en'}}, requestAnimationFrame: done => done(),
    performance, URLSearchParams};
vm.runInNewContext(fs.readFileSync('ai2apps/web/static/js/capability_provisioning.js', 'utf8'), context);
context.window.AI2AppsCapabilities.appInstanceId = () => '';
vm.runInNewContext(fs.readFileSync('ai2apps/web/static/js/discover.js', 'utf8'), context);
(async () => {
    const app = context.window.discoverApp();
    Object.assign(app, {canInstall: () => true, hasUpgrade: () => false, clearMessage: () => {}, loadCatalog: async () => {}});
    const download = {fileName: 'runtime', bytesCompleted: 2048, bytesTotal: 4096, bytesPerSecond: 1024, etaSeconds: 2, sampledAt: Date.now()/1000};
    const states = [
        {status: 'pending', operationId: 'op'},
        {status: 'running', stage: 'downloading_package', download},
        {status: 'failed', stage: 'failed', download, error: {code: 'audit_review_required', message: 'Review'}},
    ];
    const rendered = [];
    context.fetch = async () => {
        rendered.push(app.installDialog?.transferText);
        return {ok: true, json: async () => states.shift()};
    };
    await app.install({packageId: 'ai2apps/runtime-omlx', packageType: 'service'});
    assert(rendered.some(text => text?.includes('1.0 KB/s') && text.includes('00:00:02')));
    assert.equal(app.installDialog.status, 'awaiting_review');
    assert(app.installDialog.transferText.includes('2.0 KB / 4.0 KB'));
    assert(!app.installDialog.transferText.includes('ETA'));
    let delegated = false;
    context.window.AI2AppsCapabilities.chooseProfile = async () => 'model';
    context.window.AI2AppsCapabilities.runSession = async (session, appId) => {assert.equal(appId, 'ai2apps.discover'); delegated = true; return {};};
    context.fetch = async url => ({ok: true, json: async () => url.includes('model-install-sessions') ? {status: 'downloading_checkpoint', session: {id: 'model-session'}} : {}});
    app.success = () => {};
    app.showError = error => {throw error;};
    await app.installModel({packageId: 'ai2apps/model-test', packageType: 'model'});
    assert(delegated);
    app.installed = [{packageId:'test/multi',modelReady:true,modelInstall:{models:[{id:'base'},{id:'design'}]},readyModelConfigurationIds:['base']}];
    assert.equal(app.isModelReady({packageId:'test/multi'}),false);
    app.installed[0].readyModelConfigurationIds.push('design');
    assert.equal(app.isModelReady({packageId:'test/multi'}),true);
    console.log('Discover Package telemetry and Checkpoint delegation checks passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
