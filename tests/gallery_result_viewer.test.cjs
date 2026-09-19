const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
let focused = 0;
const document = {body: {style: {overflow: 'auto'}}, activeElement: {focus() {focused++;}}};
const window = {location: {origin: 'http://localhost'}, lucide: {createIcons() {}}};
window.getComputedStyle = () => ({paddingLeft: '0', paddingRight: '0', paddingTop: '0', paddingBottom: '0'});
vm.runInNewContext(fs.readFileSync(__dirname + '/../ai2apps/web/static/js/gallery.js', 'utf8'), {window, document, URL});
const viewer = window.galleryResultViewer();
viewer.$nextTick = fn => fn();
viewer.$refs = {previewDialog: {focus() {}}, previewImage: {
    clientWidth: 800, clientHeight: 600, naturalWidth: 800, naturalHeight: 600,
    parentElement: {clientWidth: 800, clientHeight: 600},
}};
viewer.init(); // Must not request Gallery collections or import assets.
viewer.openResult({id: 'result-1', name: 'test.png', previewUrl: '/v1/platform/imagine-studio/results/1/content', downloadUrl: '/download'});
assert.equal(viewer.previewReadOnly, true);
assert.equal(viewer.previewAsset.id, 'result-1');
assert.equal(viewer.previewPosition, '1 / 1');
assert.equal(viewer.hasNextPreview, false);
assert.equal(document.body.style.overflow, 'hidden');
viewer.changePreviewZoom(.25);
assert.match(viewer.previewImageTransform, /scale\(1.25\)/);
viewer.startPreviewPan({clientX: 0, clientY: 0, pointerId: 1, currentTarget: {}});
viewer.movePreviewPan({clientX: 20, clientY: 10, pointerId: 1});
assert.match(viewer.previewImageTransform, /20px,10px/);
viewer.endPreviewPan({pointerId: 1, currentTarget: {}});
for (const zoom of [.25, .75, 1, 1.25, 1.5, 2]) {
    viewer.resetPreviewTransform();
    viewer.previewZoom = zoom;
    viewer.$refs.previewImage.parentElement.clientWidth = 400;
    viewer.startPreviewPan({clientX: 0, clientY: 0, pointerId: 1, currentTarget: {}});
    assert.ok(viewer.previewPanStart, `clipped image must pan at ${zoom}`);
    assert.match(viewer.previewImageTransform, /cursor:grabbing/);
    viewer.movePreviewPan({clientX: 9999, clientY: 9999, pointerId: 1});
    assert.equal(viewer.previewPanX, Math.abs(800 * zoom - 400) / 2 + 48);
    assert.equal(viewer.previewPanY, Math.abs(600 * zoom - 600) / 2 + 48);
    const right = viewer.previewPanX, bottom = viewer.previewPanY;
    viewer.movePreviewPan({clientX: -9999, clientY: -9999, pointerId: 1});
    assert.equal(viewer.previewPanX, -right);
    assert.equal(viewer.previewPanY, -bottom);
    viewer.endPreviewPan({pointerId: 1, currentTarget: {}});
}
viewer.resetPreviewTransform();
viewer.$refs.previewImage.parentElement.clientWidth = 800;
viewer.startPreviewPan({clientX: 0, clientY: 0, pointerId: 1, currentTarget: {}});
assert.ok(viewer.previewPanStart, 'fully visible image can also be dragged');
viewer.endPreviewPan({pointerId: 1, currentTarget: {}});
assert.match(viewer.previewImageTransform, /cursor:grab/);
viewer.previewZoom = 2;
viewer.previewPanX = 100;
viewer.changePreviewZoom(-1);
assert.equal(Math.abs(viewer.previewPanX), 0, 'zooming to fit recenters the image');
viewer.openResult({id: 'result-2', previewUrl: '/other'});
assert.equal(viewer.previewZoom, 1);
viewer.handlePreviewKey({key: 'Escape'});
assert.equal(viewer.previewAsset, null);
assert.equal(document.body.style.overflow, 'auto');
assert.equal(focused, 1);
viewer.openResult({previewUrl: 'https://external.example/image.png'});
assert.equal(viewer.previewAsset, null);
viewer.openResult({previewUrl: 'javascript:alert(1)'});
assert.equal(viewer.previewAsset, null);
console.log('Gallery result viewer: passed');
