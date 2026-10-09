const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/../web/static/js/agent_mini.js', 'utf8');
const code = source.slice(source.indexOf('    function focusRunOutcome('), source.indexOf('    async function returnToWorkspace('));
function harness(hidden = []) {
    const calls = [];
    const nodes = Object.fromEntries(['#agent-run-result', '#agent-run-status', '#agent-notice'].map(id => [id, {
        hidden: hidden.includes(id),
        setAttribute: (name, value) => calls.push([id, name, value]),
        focus: options => { assert.equal(options.preventScroll, true); calls.push([id, 'focus']); },
        scrollIntoView: options => { assert.equal(options.block, 'start'); calls.push([id, 'scroll']); },
    }]));
    const ctx = {state: {run: {id: 'current'}}, $: id => nodes[id]};
    vm.createContext(ctx); vm.runInContext(code, ctx);
    return {calls, focus: ctx.focusRunOutcome};
}
test('completion focuses result; absent output falls back to status', () => {
    for (const hidden of [[], ['#agent-run-result']]) {
        const h = harness(hidden); h.focus({id: 'current', status: 'completed'});
        assert.deepEqual(h.calls.filter(c => c[1] === 'focus'), [[hidden.length ? '#agent-run-status' : '#agent-run-result', 'focus']]);
    }
});
test('failure focuses error and obsolete run cannot move focus', () => {
    const h = harness(); h.focus({id: 'old', status: 'completed'}); assert.equal(h.calls.length, 0);
    h.focus({id: 'current', status: 'failed'});
    assert.deepEqual(h.calls.filter(c => c[1] === 'focus'), [['#agent-notice', 'focus']]);
});

test('only the current manual test returns to Shell, once and after termination', async () => {
    const code = source.slice(source.indexOf('    async function returnToWorkspace('), source.indexOf('    async function driveRun('));
    let returns = 0;
    const state = {run: {id: 'test'}, workspaceTestRunId: 'test'};
    const ctx = {state, window: {frameElement: {ai2appsReturnToWorkspace: async () => returns++}}, notice: () => {}};
    vm.createContext(ctx); vm.runInContext(code, ctx);
    await ctx.returnToWorkspace({id: 'test', status: 'waiting_input'});
    await ctx.returnToWorkspace({id: 'other', status: 'completed'});
    assert.equal(returns, 0);
    await ctx.returnToWorkspace({id: 'test', status: 'completed'});
    await ctx.returnToWorkspace({id: 'test', status: 'completed'});
    assert.equal(returns, 1);
});
