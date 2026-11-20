const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(__dirname + '/../web/static/js/shell.js', 'utf8');
const launchSource = source.slice(
    source.indexOf('    async function launch('),
    source.indexOf('    async function createMiniMount('),
);

function fixture() {
    const requests = [];
    const selections = [];
    const opened = [];
    const errors = [];
    const apps = ['old', 'first', 'second'].map((id) => [id, {
        id, name: id, status: 'active', instances: [],
    }]);
    const scope = {
        homeAppsLocked: false,
        byId: new Map(apps),
        currentId: 'old',
        currentInstanceId: 'old-instance',
        currentMountToken: 'old-token',
        pendingAppId: null,
        launchSequence: 0,
        frame: { getAttribute: () => '/old' },
        framePool: new Map(),
        loading: { hidden: true },
        loadingAppName: { textContent: '' },
        updateDockSelection: () => selections.push(scope.pendingAppId || scope.currentId),
        request: (url) => new Promise((resolve, reject) => requests.push({ url, resolve, reject })),
        displayEntry: (app) => {
            opened.push(app.id);
            scope.currentId = app.id;
            scope.pendingAppId = null;
            scope.loading.hidden = true;
            scope.updateDockSelection();
        },
        loadCatalog: async () => {},
        closeLauncher: () => {},
        closeDockContextMenu: () => {},
        setDockVisible: () => {},
        showToast: (message) => errors.push(message),
    };
    vm.createContext(scope);
    vm.runInContext(launchSource, scope);
    return { scope, requests, selections, opened, errors };
}

test('cold App switch highlights the target and shows its loading state before launch resolves', async () => {
    const f = fixture();
    const pending = f.scope.launch('first');
    assert.equal(f.scope.pendingAppId, 'first');
    assert.equal(f.scope.loading.hidden, false);
    assert.equal(f.scope.loadingAppName.textContent, 'first');
    assert.equal(f.selections.at(-1), 'first');
    f.requests[0].resolve({ instance_id: 'first-instance' });
    await pending;
    assert.deepEqual(f.opened, ['first']);
    assert.equal(f.scope.loading.hidden, true);
});

test('a later App choice wins over a slow response, including a return to the current App', async () => {
    const f = fixture();
    const first = f.scope.launch('first');
    const second = f.scope.launch('second');
    f.requests[0].resolve({ instance_id: 'first-instance' });
    await first;
    assert.deepEqual(f.opened, []);
    assert.equal(f.selections.at(-1), 'second');
    f.requests[1].resolve({ instance_id: 'second-instance' });
    await second;
    assert.deepEqual(f.opened, ['second']);

    const third = f.scope.launch('first');
    await f.scope.launch('second');
    assert.equal(f.scope.pendingAppId, null);
    assert.equal(f.scope.loading.hidden, true);
    f.requests[2].resolve({ instance_id: 'first-instance' });
    await third;
    assert.deepEqual(f.opened, ['second']);
});

test('failed launch restores the previous Dock selection and removes the wait state', async () => {
    const f = fixture();
    const pending = f.scope.launch('first');
    f.requests[0].reject(new Error('unavailable'));
    await pending;
    assert.equal(f.scope.pendingAppId, null);
    assert.equal(f.scope.loading.hidden, true);
    assert.equal(f.selections.at(-1), 'old');
    assert.match(f.errors[0], /unavailable/);
});
