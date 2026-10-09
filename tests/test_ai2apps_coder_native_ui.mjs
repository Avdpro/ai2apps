import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

class Element {
    constructor() { this.handlers = {}; this.children = []; this.dataset = {}; this.disabled = false; this.hidden = false; this.value = ''; this.textContent = ''; this.open = false; }
    addEventListener(name, handler) { this.handlers[name] = handler; }
    append(...children) { this.children.push(...children); }
    replaceChildren(...children) { this.children = children; }
    get options() { return this.children; }
    showModal() { this.open = true; }
    close() { this.open = false; this.handlers.close?.(); }
}
function setup(fetcher) {
    const selectors = ['form', '[name="prompt"]', '[name="model"]', '[data-native-children]', '[data-native-title]', '[data-native-progress]', '[data-native-output]', '[data-native-questions]', '[data-native-review]', '[data-native-preview]', '[data-native-preview-component]', '[data-native-apply]', '[data-native-start]', '[data-native-stop]', '[data-native-changes]', '[data-native-new]', '[data-native-close]'];
    const nodes = Object.fromEntries(selectors.map(s => [s, new Element()]));
    const dialog = new Element(); dialog.querySelector = s => nodes[s]; nodes.form.querySelector = s => nodes[s];
    const calls = []; const storage = new Map();
    const context = {
        document: { querySelector: () => dialog, createElement: () => new Element() },
        window: {}, localStorage: { getItem: k => storage.get(k) || null, setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k) },
        fetch: async (url, options) => { calls.push({ url, options }); return fetcher(url, options); },
        setTimeout: () => 1, clearTimeout: () => {},
    };
    vm.runInNewContext(fs.readFileSync(new URL('../ai2apps/web/static/js/coder-native.js', import.meta.url), 'utf8'), context);
    return { context, dialog, nodes, calls, storage, open: (id = 'p1') => context.window.AI2AppsNativeCoder.open({ project: { id, name: id }, models: [{ id: 'test-model' }] }) };
}
const response = (value, ok = true) => ({ ok, status: ok ? 200 : 409, json: async () => value });
const completed = { status: 'completed', output: { content: '<script>unsafe()</script>' }, steps: [], interactions: [], applied: false };

async function begin(fixture) {
    fixture.open(); fixture.nodes['[name="model"]'].value = 'test-model'; fixture.nodes['[name="prompt"]'].value = 'Develop a Mini-App';
    await fixture.nodes.form.handlers.submit({ preventDefault() {} });
}

test('native task uses selected model and Project without external CLI', async () => {
    const f = setup(url => url.endsWith('/tasks') ? response({ task_id: 's1' }) : response(completed));
    await begin(f);
    const created = f.calls.find(call => call.options.method === 'POST');
    const request = JSON.parse(created.options.body);
    assert.equal(request.model, 'test-model'); assert.equal(request.prompt, 'Develop a Mini-App');
    assert.equal(created.url, '/v1/platform/coder/projects/p1/tasks');
    assert.equal(f.nodes['[data-native-output]'].textContent, '\n\n<script>unsafe()</script>');
    assert.equal(f.nodes['[data-native-output]'].children.length, 0);
});

test('review gates write-back and sends exact revision', async () => {
    const f = setup(url => {
        if (url.endsWith('/tasks')) return response({ task_id: 's1' });
        if (url.endsWith('/changes')) return response({ revision: 'r1', changes: [{ path: 'index.html', kind: 'modified', diff: '+fixed' }], validation: { valid: true, components: [{ id: 'mini.app', runnable: true }] } });
        if (url.endsWith('/apply')) return response({ ok: true });
        return response(completed);
    });
    await begin(f); assert.equal(f.nodes['[data-native-apply]'].disabled, true);
    await f.nodes['[data-native-changes]'].handlers.click();
    assert.equal(f.nodes['[data-native-apply]'].disabled, false);
    assert.equal(f.nodes['[data-native-preview]'].src, '/v1/platform/coder/tasks/s1/preview/mini.app');
    await f.nodes['[data-native-apply]'].handlers.click();
    assert.equal(JSON.parse(f.calls.find(c => c.url.endsWith('/apply')).options.body).revision, 'r1');
});

test('conflict and stale-review rejection keep Apply disabled', async () => {
    let conflict = true;
    const f = setup(url => {
        if (url.endsWith('/tasks')) return response({ task_id: 's1' });
        if (url.endsWith('/changes')) return response({ revision: 'r1', changes: [{ path: 'x', kind: 'modified', conflict }], validation: { valid: true, components: [] } });
        if (url.endsWith('/apply')) return response({ detail: { message: 'Draft changed since review' } }, false);
        return response(completed);
    });
    await begin(f); await f.nodes['[data-native-changes]'].handlers.click();
    assert.equal(f.nodes['[data-native-apply]'].disabled, true);
    conflict = false; await f.nodes['[data-native-changes]'].handlers.click();
    await f.nodes['[data-native-apply]'].handlers.click();
    assert.equal(f.nodes['[data-native-apply]'].disabled, true);
    assert.equal(f.nodes['[data-native-progress]'].textContent, 'Draft changed since review');
});

test('closing dialog preserves task for later continuation', async () => {
    const f = setup(url => url.endsWith('/tasks') ? response({ task_id: 's1' }) : response(completed));
    await begin(f); f.dialog.close();
    assert.equal(f.storage.get('ai2apps.native-coder.p1'), 's1');
    assert.equal(f.calls.some(c => c.url.endsWith('/stop')), false);
});

test('sub-Agent status exposes stale evidence and cancellation without HTML execution', async () => {
    const state = { ...completed, status: 'waiting_subruns', children: [{ child_run_id: 'c1', role: 'tester', status: 'running', stale: true, used_tokens: 12, summary: '<script>bad()</script>', checks: [], unverified: ['Bridge'] }] };
    const f = setup(url => url.endsWith('/tasks') ? response({ task_id: 's1' }) : response(state));
    await begin(f);
    const box = f.nodes['[data-native-children]'].children[0];
    assert.match(box.children[0].textContent, /Stale/);
    assert.match(box.children[1].textContent, /<script>bad/);
    assert.equal(box.children[1].children.length, 0);
    assert.equal(f.nodes['[data-native-start]'].disabled, true);
    await box.children[2].onclick();
    assert.ok(f.calls.some(call => call.url.endsWith('/children/c1/cancel') && call.options.method === 'POST'));
});

test('finished child follow-up prepares text without launching a model', async () => {
    const state = { ...completed, children: [{ child_run_id: 'c1', role: 'reviewer', status: 'completed', stale: false, used_tokens: 12, summary: 'Review evidence', checks: [] }] };
    const f = setup(url => url.endsWith('/tasks') ? response({ task_id: 's1' }) : response(state));
    await begin(f);
    const before = f.calls.length;
    f.nodes['[data-native-children]'].children[0].children[2].onclick();
    assert.match(f.nodes['[name="prompt"]'].value, /Review evidence/);
    assert.equal(f.calls.length, before);
});

test('lost origin storage restores the owned persisted task', async () => {
    const f = setup(url => response(url.endsWith('/tasks/latest') ? {task_id:'persisted'} : completed));
    f.open();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(f.storage.get('ai2apps.native-coder.p1'), 'persisted');
    assert.ok(f.calls.some(call => call.url.endsWith('/tasks/persisted')));
    assert.equal(f.nodes['[data-native-output]'].textContent, '\n\n<script>unsafe()</script>');
});

test('explicit new task wins a late restoration response', async () => {
    let resolveLatest;
    const f = setup(() => new Promise(resolve => { resolveLatest = resolve; }));
    f.open();
    f.nodes['[data-native-new]'].handlers.click();
    resolveLatest(response({task_id:'old-task'}));
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(f.storage.get('ai2apps.native-coder.p1'), 'new');
    assert.equal(f.calls.length, 1);
});

test('review can preview each runnable App and Mini-App', async () => {
    const f = setup(url => response(url.endsWith('/tasks') ? {task_id:'s1'} : url.endsWith('/changes') ? {revision:'r',changes:[],validation:{valid:true,components:[{id:'app',name:'Main',runnable:true},{id:'mini',name:'Text Stats',runnable:true}]}} : completed));
    await begin(f);
    await f.nodes['[data-native-changes]'].handlers.click();
    const chooser = f.nodes['[data-native-preview-component]'];
    assert.equal(chooser.hidden, false); assert.equal(chooser.children.length, 2);
    chooser.value = 'mini'; chooser.onchange();
    assert.equal(f.nodes['[data-native-preview]'].src, '/v1/platform/coder/tasks/s1/preview/mini');
});
