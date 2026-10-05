const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../web/static/js/agent_mini.js'), 'utf8');
function setup(url) {
    const commands = [];
    const state = {page: {url}, context: {url}};
    const bidi = {
        contextId: 'bound-tab', pageState: async () => ({url: state.page.url}),
        connection: {command: async (method, params) => {commands.push({method, params}); state.page.url = params.url;}},
    };
    const context = {URL, state, client: async () => bidi};
    const parts = [
        source.slice(source.indexOf('    function pageScope()'), source.indexOf('    function normalizedStep(')),
        source.slice(source.indexOf('    function scopeAllows('), source.indexOf('    async function client()')),
        source.slice(source.indexOf('    async function execute('), source.indexOf('    async function saveEvidence(')),
    ];
    vm.runInNewContext(parts.join('\n') + '\nglobalThis.scope = pageScope; globalThis.run = execute;', context);
    return {context, commands};
}
for (const url of ['about:newtab', 'about:blank', 'file:///tmp/page.html']) {
    test('internal page has no invented website scope: ' + url, () => {
        assert.equal(setup(url).context.scope(), '');
    });
}
test('web page keeps its origin scope', () => {
    assert.equal(setup('https://www.google.com/search?q=test').context.scope(), 'https://www.google.com/**');
});
test('new tab can navigate into an authorized website', async () => {
    const {context, commands} = setup('about:newtab');
    const result = await context.run({operation:'open', description:'Open Google', arguments:{url:'https://www.google.com/'}}, false, ['https://www.google.com/**']);
    assert.equal(result.outcome, 'success');
    assert.equal(commands[0].method, 'browsingContext.navigate');
    assert.equal(commands[0].params.context, 'bound-tab');
});
test('out-of-scope navigation is blocked in execution and preview', async () => {
    for (const preview of [false, true]) {
        const {context, commands} = setup('about:newtab');
        const result = await context.run({operation:'open', description:'Open another site', arguments:{url:'https://other.example/'}}, preview, ['https://www.google.com/**']);
        assert.equal(result.outcome, 'restricted');
        assert.equal(result.evidence.reason, 'navigation_outside_scope');
        assert.equal(commands.length, 0);
    }
});
test('page interactions outside the allowed website stay blocked', async () => {
    const {context, commands} = setup('https://other.example/');
    const result = await context.run({operation:'inspect'}, false, ['https://www.google.com/**']);
    assert.equal(result.evidence.reason, 'site_scope');
    assert.equal(commands.length, 0);
});
test('Google homepage without a trailing slash is inside origin scope', async () => {
 const {context,commands}=setup('https://www.google.com/imghp?hl=en');
 const result=await context.run({operation:'open',description:'Return to search',arguments:{url:'https://www.google.com'}},false,['https://www.google.com/**']);
 assert.equal(result.outcome,'success');assert.equal(commands.length,1);
});
test('scope matching checks host, protocol, port and path boundaries', async () => {
 for(const url of ['https://www.google.com.evil.example/','http://www.google.com/','https://www.google.com:8080/']) {
  const {context,commands}=setup('https://www.google.com/');
  const result=await context.run({operation:'open',description:'Open',arguments:{url}},false,['https://www.google.com/**']);
  assert.equal(result.outcome,'restricted');assert.equal(commands.length,0);
 }
});
