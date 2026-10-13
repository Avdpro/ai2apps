const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const test = require('node:test');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../ai2apps/web/static/js/capability_provisioning.js'), 'utf8');
// Exercise the production list-rendering block with a minimal DOM tree.
const block = source.slice(source.indexOf("        const list = overlay.querySelector('.acpf-steps');"),
    source.indexOf('        const percent =', source.indexOf('    function render(')));
class Node {
    constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.open = false; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = nodes; }
    setAttribute() {}
    querySelectorAll() {
        return this.children.filter(node => node instanceof Node).flatMap(node => [
            ...(node.tag === 'details' && node.open ? [node] : []), ...node.querySelectorAll(),
        ]);
    }
}
function harness() {
    const list = new Node('ol');
    const context = vm.createContext({overlay: {querySelector: () => list}, session: {},
        document: {createElement: tag => new Node(tag)},
        groupedSteps: session => session.groups,
        tr: text => text, stepIdentity: step => step.id,
        stepStateLabels: {pending: 'pending', active: 'active'}});
    return {render(groups) {context.session = {groups}; vm.runInContext('{' + block + '}', context);},
        details() {return list.children.map(li => li.children[1].children[1]);}};
}
const group = (key, state = 'pending') => ({key, title: key, state, steps: [{id: 'one'}, {id: 'two'}]});
test('expanded groups survive repeated polls and reordering; explicit collapse persists', () => {
    const h = harness();
    h.render([group('runtime'), group('models')]);
    assert.deepEqual(h.details().map(n => n.open), [false, false]);
    h.details()[1].open = true;
    for (let i = 0; i < 5; i++) h.render([group('runtime'), group('models', 'active')]);
    assert.deepEqual(h.details().map(n => n.open), [false, true]);
    h.render([group('models'), group('runtime')]);
    assert.deepEqual(h.details().map(n => n.open), [true, false]);
    h.details()[0].open = false;
    h.render([group('models'), group('runtime')]);
    assert.deepEqual(h.details().map(n => n.open), [false, false]);
});
test('new sheets and unrelated groups do not inherit expansion', () => {
    const h = harness(); h.render([group('models')]); h.details()[0].open = true;
    const fresh = harness(); fresh.render([group('models')]);
    assert.equal(fresh.details()[0].open, false);
    h.render([group('runtime')]); assert.equal(h.details()[0].open, false);
});
