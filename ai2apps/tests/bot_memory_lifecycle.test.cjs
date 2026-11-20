const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

test('cleanup can reopen a Bot after the invoking settings form detaches', async () => {
  const roots = [];
  const root = {replaceChildren() {}};
  const initial = {id: 'fixture', name: 'Fixture', duty: 'Synthetic'};
  const fallback = {id: 'default', name: 'AI2Apps', duty: 'Help', is_default: true};
  const context = {
    window: {AI2AppsBotConversation: {async create(options) {
      roots.push(options.root);
      return {dispose() {}};
    }}},
    document: {documentElement: {lang: 'en'}}, navigator: {language: 'en'},
    clearInterval() {}, setInterval() {}, clearTimeout() {}, setTimeout() {},
    async fetch(url) {
      const value = url.endsWith('/bots') ? {items: [fallback, initial]} :
        url.endsWith('/bots-archive') ? {items: []} : {status: 'archived'};
      return {ok: true, async json() {return value;}};
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../web/static/js/messager.js'), 'utf8'), context);
  const app = context.window.messagerApp();
  app.$refs = {botChat: root};
  app.loadBotTasks = app.loadBotAccess = app.loadMemories = async () => {};
  await app.openBot(initial);
  app.$refs = {}; // Alpine's removed x-if form has no surviving magic references.
  app.cleanupTargetId = initial.id;
  app.cleanupAction = 'archive';
  app.cleanupReview = {review_hash: 'synthetic-review'};
  await app.applyCleanup();
  assert.equal(app.currentBot.id, 'default');
  assert.equal(roots.length, 2);
  assert.equal(roots[0], root);
  assert.equal(roots[1], root);
  assert.equal(app.noticeTone, 'success');
  app.currentBot = initial;
  app.cleanupTargetId = initial.id;
  app.cleanupAction = 'clear_dialogue';
  app.cleanupReview = {review_hash: 'another-review'};
  await app.applyCleanup();
  assert.equal(app.currentBot.id, 'fixture');
  assert.equal(roots[2], root);
});

function cleanupFixture() {
  let failMutation = false, releaseMutation;
  const requests = [], controllers = [];
  const bot = {id: 'fixture', name: 'Fixture', duty: 'Help'};
  const root = {children: ['old message', 'old material'], replaceChildren(...items) {this.children = items;}};
  const dialog = {open: false, showModal() {this.open = true;}, close() {this.open = false;}};
  const context = {
    window: {AI2AppsBotConversation: {async create(options) {
      controllers.push(options);
      return {dispose() {}};
    }}},
    document: {documentElement: {lang: 'en'}}, navigator: {language: 'en'},
    clearInterval() {}, setInterval() {}, clearTimeout() {}, setTimeout() {},
    async fetch(url, options) {
      requests.push({url, method: options.method || 'GET',body: options.body?JSON.parse(options.body):null});
      if(options.method === 'POST') {
        if(releaseMutation) await releaseMutation;
        return {ok: !failMutation, async json() {return failMutation ? {detail: 'Scope changed; review again'} : {status: 'cleared'};}};
      }
      const value = url.endsWith('/cleanup') ? {review_hash: 'review', runs: [], tasks: [], hooks: [], memory_count: 0} : {items: [bot]};
      return {ok: true, async json() {return value;}};
    },
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../web/static/js/messager.js'), 'utf8'), context);
  const app = context.window.messagerApp();
  app.$refs = {botChat: root};app.$root = {querySelector() {return dialog;}};
  app.loadBotTasks = app.loadBotAccess = app.loadMemories = app.loadNotificationPolicy = async () => {};
  return {app, bot, root, dialog, requests, controllers, fail() {failMutation = true;}, hold(promise) {releaseMutation = promise;}};
}

test('clear opens a modal and cancelling makes no destructive request', async () => {
  const f = cleanupFixture();await f.app.openBot(f.bot);
  await f.app.reviewCleanup('clear_dialogue');
  assert.equal(f.dialog.open, true);
  assert.deepEqual(f.root.children, ['old message', 'old material']);
  f.app.cancelCleanup();
  assert.equal(f.dialog.open, false);
  await f.app.applyCleanup();
  assert.equal(f.requests.filter(r => r.method === 'POST').length, 0);
});

test('confirmed clear removes old messages/materials, invalidates polls and remounts the same Bot once', async () => {
  const f = cleanupFixture();await f.app.openBot(f.bot);
  await f.app.reviewCleanup('clear_dialogue');
  let release;f.hold(new Promise(resolve => {release = resolve;}));
  const first = f.app.applyCleanup();await f.app.applyCleanup();
  f.app.cancelCleanup();assert.equal(f.dialog.open, true);
  assert.deepEqual(f.root.children, ['old message', 'old material']);
  release();await first;
  assert.equal(f.requests.filter(r => r.method === 'POST').length, 1);
  assert.equal(f.dialog.open, false);
  assert.equal(f.app.currentBot.id, f.bot.id);
  assert.equal(f.controllers.length, 2);
  assert.equal(f.controllers[0].isActive(), false);
  assert.equal(f.controllers[1].isActive(), true);
  assert.equal(f.root.children.length, 0);
  assert.equal(f.app.notice, 'Conversation cleared');
});

test('failed clear keeps messages/materials; a switched Bot cannot use the old review', async () => {
  const f = cleanupFixture();await f.app.openBot(f.bot);
  await f.app.reviewCleanup('clear_dialogue');f.fail();await f.app.applyCleanup();
  assert.deepEqual(f.root.children, ['old message', 'old material']);
  assert.equal(f.controllers[0].isActive(), true);
  assert.equal(f.app.noticeTone, 'error');
  await f.app.reviewCleanup('clear_dialogue');
  await f.app.openBot({...f.bot, id: 'other'});
  assert.equal(f.dialog.open, false);
  await f.app.applyCleanup();
  assert.equal(f.requests.filter(r => r.method === 'POST').length, 1);
});

for (const memory of [false,true]) for (const access of [false,true]) for(const tasks of [false,true]) {
 test(`cleanup choices are explicit in one request: memory=${memory}, access=${access}, tasks=${tasks}`,async()=>{
  const f=cleanupFixture();await f.app.openBot(f.bot);
  f.app.cleanupClearMemory=true;f.app.cleanupRevokeAccess=true;
  await f.app.reviewCleanup('clear_dialogue');
  assert.equal(f.app.cleanupClearMemory,false);assert.equal(f.app.cleanupRevokeAccess,false);
  f.app.cleanupClearMemory=memory;f.app.cleanupRevokeAccess=access;f.app.cleanupDeleteTasks=tasks;
  const summary=f.app.cleanupSelectionSummary();assert.match(summary,memory?/also clears long-term memory/:/keeps long-term memory/);
  assert.match(summary,access?/also revokes App/:/keeps App/);
  await f.app.applyCleanup();const posts=f.requests.filter(x=>x.method==='POST');assert.equal(posts.length,1);
  assert.equal(posts[0].body.clear_memory,memory);assert.equal(posts[0].body.revoke_access,access);assert.equal(posts[0].body.delete_tasks,tasks);
  assert.equal(f.app.cleanupClearMemory,false);assert.equal(f.app.cleanupRevokeAccess,false);
 });
}

test('shortcut card deletion targets the reviewed ASC-Bot and keeps the open conversation', async () => {
  const f = cleanupFixture();
  await f.app.openBot(f.bot);
  const shortcut = {id: 'shortcut', name: 'Saved view', definition: {execution_mode: 'app_shortcut'}};
  await f.app.reviewCleanup('archive', shortcut);
  assert.equal(f.dialog.open, true);
  assert.equal(f.app.cleanupShortcutName, shortcut.name);
  assert.equal(f.requests.some(request => request.method === 'POST'), false);
  await f.app.applyCleanup();
  const [post] = f.requests.filter(request => request.method === 'POST');
  assert.ok(post.url.endsWith('/bots/shortcut/cleanup/archive'));
  assert.equal(f.app.currentBot.id, f.bot.id);
  assert.deepEqual(f.root.children, ['old message', 'old material']);
});
