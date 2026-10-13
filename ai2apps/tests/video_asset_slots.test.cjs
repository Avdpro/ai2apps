const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.join(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'web/templates/system_apps/video_studio.html'), 'utf8');
const mobile = fs.readFileSync(path.join(root, 'web/static/js/studio_mobile.js'), 'utf8');
const source = fs.readFileSync(path.join(root, 'web/static/js/video_studio.js'), 'utf8');

test('built-in Video Mini-Apps use shared asset slots; specialized batch imports remain separate', () => {
    assert.equal((template.match(/AI2AppsAssetSlot\.bind/g) || []).length, 7);
    for (const call of ["setImage('first'", "setImage('last'", "setReferenceFiles('image'",
        "setReferenceFiles('video'", "setReferenceFiles('audio'", 'importExtractFile(file)', 'selectUpscalingFile(file)']) {
        assert.ok(template.includes(call), call);
    }
    assert.ok(template.includes('importComposerFiles($event)'));
    assert.ok(template.includes('loadBatchFile($event)'));
    assert.ok(mobile.includes("target?.closest('[data-asset-slot],label')"));
    assert.ok(mobile.includes("root.addEventListener('click',handleClick,true)"));
});

test('reference and upscale slots preserve ordering, validate limits and revoke Blob previews', () => {
    let next = 0;
    const revoked = [];
    const context = {
        window: {t: key => key}, document: {documentElement: {lang: 'en'}},
        crypto: {randomUUID: () => '00000000-0000-4000-8000-000000000000'},
        URL: {createObjectURL: () => `blob:${++next}`, revokeObjectURL: url => revoked.push(url)},
    };
    vm.runInNewContext(source, context);
    const app = context.window.videoStudioApp();
    app.$nextTick = callback => callback();
    const image = name => ({name, type: 'image/png'});
    app.setReferenceFiles('image', [image('one.png'), image('two.png')]);
    assert.equal(app.referenceSlotState('image').count, 2);
    assert.equal(app.referenceSlotState('image').preview, 'blob:1');
    assert.deepEqual(Array.from(app.referenceOrder, item => item.index), [0, 1]);
    assert.throws(() => app.setReferenceFiles('image', [image('bad.png'), {name: 'wrong.mp3', type: 'audio/mpeg'}]));
    assert.equal(app.referenceImages.length, 2, 'invalid batches must not partially change the slot');
    app.clearReferenceFiles('image');
    assert.equal(app.referenceSlotState('image').count, 0);
    assert.ok(revoked.includes('blob:1'));
    app.selectUpscalingFile({name: 'first.mp4', type: 'video/mp4', size: 1024});
    app.selectUpscalingFile({name: 'second.mp4', type: 'video/mp4', size: 1024});
    assert.ok(revoked.includes('blob:2'));
    app.clearUpscalingFile();
    assert.equal(app.upscalingFile, null);
    assert.ok(revoked.includes('blob:3'));
});
