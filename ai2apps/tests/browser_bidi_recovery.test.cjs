const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../web/static/js/browser_bidi_client.js'), 'utf8');
function setup(failures = 1, denied = false) {
    const sockets = [], tickets = [], actions = [];
    class Socket {
        static OPEN = 1;
        constructor(url) {
            this.url = url; this.readyState = 0; this.listeners = {};
            sockets.push(this);
            setImmediate(() => {
                if (sockets.length <= failures) this.emit('error', {});
                else { this.readyState = 1; this.emit('open', {}); }
            });
        }
        addEventListener(name, fn, opts = {}) { (this.listeners[name] ||= []).push({fn, once: opts.once}); }
        emit(name, value) {
            const listeners = [...(this.listeners[name] || [])];
            this.listeners[name] = listeners.filter(item => !item.once);
            for (const item of listeners) item.fn(value);
        }
        send(value) {
            const command = JSON.parse(value); actions.push(command.method);
            if (command.method === 'input.performActions') { this.close(); return; }
            const result = command.method === 'session.status' ? {ready: true} : {};
            setImmediate(() => this.emit('message', {data: JSON.stringify({id: command.id, result})}));
        }
        close() { this.readyState = 3; this.emit('close', {}); }
    }
    const context = {
        window: {addEventListener() {}}, location: {protocol: 'http:', host: '127.0.0.1:1234'},
        WebSocket: Socket, clearTimeout,
        setTimeout: (fn, ms) => setTimeout(fn, ms === 1000 ? 1 : ms),
        fetch: async () => {
            tickets.push(tickets.length + 1);
            return {ok: !denied, status: denied ? 403 : 200, json: async () => ({ticket: `ticket-${tickets.length}`})};
        },
    };
    vm.runInNewContext(source, context);
    return {connection: new context.window.AI2AppsBiDi.AI2AppsBiDiConnection(), sockets, tickets, actions};
}
test('connect refreshes ticket once after transport failure', async () => {
    const state = setup(); await state.connection.connect();
    assert.equal(state.tickets.length, 2);
    assert.equal(state.sockets[0].readyState, 3);
    assert.notEqual(state.sockets[0].url, state.sockets[1].url);
    await state.connection.close();
});
test('failed connection is bounded and cleaned up', async () => {
    const state = setup(3); await assert.rejects(state.connection.connect());
    assert.equal(state.sockets.length, 2); assert.equal(state.connection.socket, null);
});
test('authorization denial is not retried', async () => {
    const state = setup(0, true); await assert.rejects(state.connection.connect());
    assert.equal(state.tickets.length, 1); assert.equal(state.sockets.length, 0);
});
test('disconnected action is rejected immediately and never replayed', async () => {
    const state = setup(0); await state.connection.connect();
    await assert.rejects(state.connection.command('input.performActions', {}), /disconnected/);
    assert.equal(state.actions.filter(method => method === 'input.performActions').length, 1);
    assert.equal(state.tickets.length, 1); await state.connection.close();
});
test('Agent discards disconnected client and reconnects before the next task', async () => {
    const agentSource = fs.readFileSync(path.join(__dirname, '../web/static/js/agent_mini.js'), 'utf8');
    const clientSource = agentSource.slice(agentSource.indexOf('    async function client() {'), agentSource.indexOf('    function intent(step) {'));
    const instances = [];
    class PageClient {
        constructor() {
            this.listeners = {};
            this.connection = {
                socket: {addEventListener: (name, fn) => {this.listeners[name] = fn;}},
                close: async () => {},
            };
            instances.push(this);
        }
        async connect() {}
        async pageState() {return {title: 'Test'};}
    }
    const context = {state: {client: null, context: {}, contextRevision: 1}, window: {AI2AppsBiDi: {AI2AppsPageClient: PageClient}}};
    vm.runInNewContext(clientSource + '\nglobalThis.obtainClient = client;', context);
    const first = await context.obtainClient();
    assert.equal(await context.obtainClient(), first);
    first.listeners.close();
    assert.equal(context.state.client, null);
    const second = await context.obtainClient();
    assert.notEqual(second, first);
    first.listeners.close();
    assert.equal(context.state.client, second);
    assert.equal(instances.length, 2);
});
