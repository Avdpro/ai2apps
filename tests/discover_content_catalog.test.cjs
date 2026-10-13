const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const schemaVersion = 'ai2apps.content-catalog.v1';
const capability = {contentCatalog: {schemaVersion, endpoint: '/v1/registry/content', maxLimit: 100}};
function card(id, version = '2.0.0') {
    const parent = {packageId: 'example/suite', latestVersion: version, packageType: 'app',
        miniApps: [{componentId: 'example.extra', displayName: 'Must not expand'}]};
    return {parent, cardKey: parent.packageId + '#' + id, contentKind: 'mini-app',
        packageId: parent.packageId, packageVersion: version, componentId: id, componentVersion: '9.0.0',
        displayName: id, categories: ['audio'], placements: ['ai2apps.voice-studio'],
        installationTarget: {packageId: parent.packageId, version}};
}
function setup(handler) {
    const calls = [];
    const context = {URLSearchParams, requestAnimationFrame: fn => fn(),
        document: {documentElement: {lang: 'en'}}, window: {},
        fetch: async url => {calls.push(url); const result = await handler(new URL(url, 'http://local'));
            return {ok: !result.error, status: result.error ? 410 : 200, json: async () => result}; }};
    vm.runInNewContext(fs.readFileSync('ai2apps/web/static/js/discover.js', 'utf8'), context);
    return {app: context.window.discoverApp(), calls};
}
test('native cards paginate without expansion, preserve parent version and server search results', async () => {
    const {app, calls} = setup(url => url.pathname.endsWith('/capabilities') ? capability : {
        schemaVersion, catalogSnapshot: 's1', items: [card(url.searchParams.has('cursor') ? 'two' : 'one')],
        nextCursor: url.searchParams.has('cursor') ? null : 'opaque/+='});
    app.type = 'mini-app'; app.query = 'ai2apps.voice-studio'; app.miniAppCategory = 'audio';
    await app.loadCatalogPage(false, true);
    assert.equal(app.items.length, 1); assert.equal(app.visibleItems.length, 1);
    assert.equal(app.items[0].version, '2.0.0'); assert.equal(app.items[0].componentVersion, '9.0.0');
    await app.loadCatalogPage(true, false);
    assert.equal(app.items.length, 2); assert.equal(app.nextCursor, '');
    const url = new URL(calls.at(-1), 'http://local');
    assert.equal(url.searchParams.get('cursor'), 'opaque/+=');
    assert.equal(url.searchParams.get('limit'), '24');
    assert.equal(url.searchParams.get('mini_app_category'), 'audio');
    assert.equal(url.searchParams.get('content'), 'mini-app');
    assert(!calls.some(url => url.includes('limit=100')));
});
test('expired cursor restarts one snapshot without stale cards or infinite retry', async () => {
    let first = 0;
    const {app} = setup(url => url.pathname.endsWith('/capabilities') ? capability :
        url.searchParams.has('cursor') ? {error: {code: 'CATALOG_CURSOR_EXPIRED', message: 'expired'}} :
        {schemaVersion, catalogSnapshot: String(++first), items: [card('fresh' + first)], nextCursor: 'cursor'});
    app.type = 'mini-app'; await app.loadCatalogPage(false, true); await app.loadCatalogPage(true, false);
    assert.equal(first, 2); assert.equal(app.items.length, 1); assert.equal(app.items[0].componentId, 'fresh2');
});
test('missing capability keeps legacy expansion; installed parent management stays visible', async () => {
    const {app} = setup(url => url.pathname.endsWith('/capabilities') ? {} : {items: [card('one').parent]});
    app.type = 'mini-app'; await app.loadCatalogPage(false, true);
    assert.equal(app.nativeContent, false); assert.equal(app.visibleItems.length, 1);
    const parent = {packageType: 'app', appNavigation: {launcher: false}};
    app.type = 'app'; assert.equal(app.matchesType(parent), false);
    app.tab = 'installed'; assert.equal(app.matchesType(parent), true);
});
test('native parent and component mixed cards are not expanded; unsupported schema falls back', async () => {
    const component = card('one');
    const parent = {...component, cardKey: component.packageId, contentKind: 'app', componentId: undefined};
    const {app} = setup(url => url.pathname.endsWith('/capabilities') ? capability :
        {schemaVersion, catalogSnapshot: 's', items: [parent, component], nextCursor: null});
    await app.loadCatalogPage(false, true);
    assert.equal(app.items.length, 2); assert.equal(app.isMiniApp(app.items[0]), false);
    let requested;
    const fallback = setup(url => {requested = url; return url.pathname.endsWith('/capabilities') ?
        {contentCatalog: {...capability.contentCatalog, schemaVersion: 'future'}} : {items: []};});
    await fallback.app.loadCatalogPage(false, true);
    assert.equal(fallback.app.nativeContent, false); assert(requested.pathname.endsWith('/recommendations'));
});

test('anonymous production catalog with clean client state', {skip: !process.env.DISCOVER_LIVE_TEST}, async () => {
    const {execFileSync} = require('node:child_process');
    const {app} = setup(url => {
        const path = url.pathname.endsWith('/capabilities') ? '/v1/registry' : '/v1/registry/content' + url.search;
        const result = JSON.parse(execFileSync('curl', ['-fsS', 'https://coder.ai2apps.com' + path], {encoding: 'utf8'}));
        return url.pathname.endsWith('/capabilities') ? result.discoveryCapabilities : result;
    });
    app.type = 'mini-app';
    await app.loadCatalogPage(false, true);
    while (app.nextCursor) await app.loadCatalogPage(true, false);
    assert.equal(app.installed.length, 0);
    assert.equal(app.nativeContent, true);
    assert(app.items.length >= 10);
    assert.equal(new Set(app.items.map(x => x.cardId)).size, app.items.length);
    assert(app.items.every(x => app.isMiniApp(x)));
    console.log('Live clean-state Mini-App cards:', app.items.length, 'parent Packages:', new Set(app.items.map(x => x.packageId)).size);
});
