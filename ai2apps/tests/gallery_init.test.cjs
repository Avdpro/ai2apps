const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
test('automatic Alpine init plus legacy x-init loads Gallery only once', async () => {
  const events = [];
  const window = {location:{hash:''}, addEventListener:(name)=>events.push(name)};
  const context = {window, URLSearchParams};
  vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/gallery.js','utf8'),context);
  const app = window.galleryApp();
  app.$root = {dataset:{gallerySurface:'mini-entry'}};
  let refreshes = 0;
  app.readAssetClipboard = () => {};
  app.refresh = async () => {refreshes++;};
  await Promise.all([app.init(),app.init()]);
  assert.equal(refreshes,1);
  assert.deepEqual(events,['message','keydown','storage','beforeunload']);
});
