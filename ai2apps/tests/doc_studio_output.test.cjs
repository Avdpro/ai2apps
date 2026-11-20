const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

function element() {
    return {
        dataset: {}, children: [],
        replaceChildren(...children) { this.children = children; },
        append(...children) { this.children.push(...children); },
        setAttribute(name, value) { this[name] = value; },
    };
}

test('the host retains selected output when another producer completes', async () => {
    const nodes = new Map();
    const root = {querySelector(selector) {
        if (!nodes.has(selector)) nodes.set(selector, element());
        return nodes.get(selector);
    }};
    const context = {
        window: {},
        document: {createElement: tag => ({tag, ...element()})},
        Option: class { constructor(text, value) { this.text = text; this.value = value; } },
        fetch: async () => ({ok: true, text: async () => 'X Post text'}),
    };
    vm.runInNewContext(readFileSync(join(__dirname, '../web/static/js/studio_document_output.js'), 'utf8'), context);
    const mount = context.window.AI2AppsStudioDocumentOutput(root, {
        tr: (_, en) => en, formatLabel: target => target === 'x-long-post' ? 'X Long Post' : target, busy: () => false, cancel: () => {}, taskNames: {},
        error: failure => assert.fail(failure.message),
    });
    const artifact = (id, mediaType, producer, target) => ({
        id, target, name: id, created_at: '2026-11-11T01:00:00Z', mini_app_id: producer,
        media_type: mediaType, preview_url: '/' + id, download_url: '/' + id + '?download=true',
    });
    const html = artifact('html', 'text/html', 'writer', 'html');
    const post = artifact('post', 'text/plain', 'another-producer', 'x-long-post');
    const preview = root.querySelector('[data-output-preview]');
    const picker = root.querySelector('[data-output-select]');
    mount.update('project-one', [html], []);
    assert.equal(preview.children[0].sandbox, '');
    mount.update('project-one', [post, html], []);
    assert.equal(picker.value, 'html');
    assert.match(picker.children[0].text, /X Long Post/);
    assert.equal(preview.children[0].src, '/html');
    picker.value = 'post';
    await picker.onchange();
    assert.equal(preview.children[0].textContent, 'X Post text');
    assert.equal(root.querySelector('[data-output-download]').href, '/post?download=true');
    mount.update('project-two', [], []);
    assert.equal(preview.hidden, true);
    mount.update('project-one', [html, post], []);
    assert.equal(picker.value, 'post');

    mount.update('project-one', [html, post], [{
        id: 'failure', kind: 'generate', status: 'failed', message: '502 generic failure',
        progress: {draft_error: {code: 'post_too_long', count: 306, limit: 280, weighted: true}},
    }]);
    const message = root.querySelector('[data-output-tasks]').children[0].children[1].textContent;
    assert.match(message, /306 weighted characters/);
    assert.match(message, /Shorten it by at least 26/);
});
