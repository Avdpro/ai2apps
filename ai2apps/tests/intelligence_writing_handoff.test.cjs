const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(__dirname + '/../web/static/js/intelligence.js', 'utf8');
const dialogSource = source.slice(source.indexOf('async function startWriting('),
    source.indexOf('async function openDraft('));

function fixture({mobile = false, failFirstImport = false} = {}) {
    class Element {
        constructor(tag) {
            this.tag = tag;
            this.children = [];
            this.style = {};
            this.value = '';
            this.handlers = {};
        }
        append(...children) { this.children.push(...children); }
        replaceChildren(...children) {
            this.children = children;
            this.value = children[0]?.value || '';
        }
        querySelectorAll(tag) {
            return this.children.flatMap(child => [child, ...child.querySelectorAll(tag)])
                .filter(child => child.tag === tag);
        }
        setAttribute() {}
        addEventListener(event, callback) { this.handlers[event] = callback; }
        showModal() { this.open = true; }
        close() { this.open = false; this.handlers.close?.(); }
        remove() {}
        focus() {}
    }
    const body = new Element('body');
    const calls = [], storage = new Map(), opened = [];
    let attempts = 0, requestId = 0;
    const env = {
        channel: () => ({id: 'channel', name: 'Watches'}),
        handoffText: (_, en) => en,
        document: {createElement: tag => new Element(tag), body},
        window: {AI2APPS_MOBILE_SURFACE: mobile,
            ai2appsShell: {openEntry: async payload => opened.push(payload.appId)}},
        sessionStorage: {setItem: (key, value) => storage.set(key, value)},
        crypto: {randomUUID: () => 'request-' + ++requestId},
        api: async (path, method, payload) => {
            calls.push({path, payload});
            return path.endsWith('/gallery') ? {missing_images: 1} :
                {id: 'pack', title: 'Watch story', articles: [{title: 'Watch story'}]};
        },
        requestJSON: async (path, options) => {
            const payload = options.body ? JSON.parse(options.body) : null;
            calls.push({path, payload});
            if (path.endsWith('/projects')) return [{id: 'project', title: 'Existing article'}];
            if (++attempts === 1 && failFirstImport) throw Error('Connection interrupted');
            return {id: 'task-1'};
        },
    };
    vm.createContext(env);
    vm.runInContext(dialogSource, env);
    const button = text => body.querySelectorAll('button').find(node => node.textContent === text);
    return {env, calls, storage, opened, body, button};
}

test('write first prepares a pack, then creates or adds to the selected project', async () => {
    const f = fixture({failFirstImport: true});
    await f.env.startWriting('article', 'article-1');
    assert.equal(f.calls.length, 1);
    assert.equal(f.calls[0].path, '/channels/channel/material-packs');
    await f.button('Add to an existing project').onclick();
    await f.button('Add to selected project').onclick();
    await f.button('Add to selected project').onclick();
    const [first, retry] = f.calls.filter(call => call.path.endsWith('/imports'));
    assert.equal(first.payload.project_id, 'project');
    assert.equal(retry.payload.request_id, first.payload.request_id);
    await f.button('Open Doc Studio').onclick();
    assert.equal(f.storage.get('ai2apps.doc-studio.import-task'), 'task-1');
    assert.deepEqual(f.opened, ['ai2apps.doc-studio']);

    const create = fixture();
    await create.env.startWriting('channel', '');
    await create.button('Create a project in Doc Studio').onclick();
    assert.equal(create.calls.at(-1).payload.project_id, null);
    assert.equal(create.calls.at(-1).payload.title, 'Watch story');
});

test('mobile can save to Gallery and displays missing image count', async () => {
    const f = fixture({mobile: true});
    await f.env.startWriting('article', 'article-1');
    assert.equal(f.button('Create a project in Doc Studio').disabled, true);
    assert.equal(f.button('Add to an existing project').disabled, true);
    await f.button('Add to Gallery').onclick();
    assert.equal(f.calls.at(-1).path, '/material-packs/pack/gallery');
    assert.ok(f.body.querySelectorAll('p').some(node => node.textContent.includes('Images not embedded: 1')));
});
