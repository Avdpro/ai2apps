const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {join} = require('node:path');
const test = require('node:test');
const {chromium} = require('playwright');

const web = join(__dirname, '../web');
const origin = 'https://doc-studio.test';
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l2kAAAAASUVORK5CYII=', 'base64');

async function withEditor(run, {legacy = false, packages = null} = {}) {
    const browser = await chromium.launch({headless: true, channel: 'chrome'});
    try {
        const page = await browser.newPage({viewport: {width: 1500, height: 1100}});
        page.setDefaultTimeout(5000);
        const failures = [];
        page.on('pageerror', error => failures.push(error.message));
        const template = readFileSync(join(web, 'templates/system_apps/doc_studio.html'), 'utf8')
            .split('{% block content %}')[1].split('{% block scripts %}')[0]
            .replace(/\{\{[^}]*\}\}|\{%[^%]*%\}/g, '');
        const versions = [{id: 'original', title: 'Draft', target: 'html', created_at: '2026-11-11T00:00:00Z'}];
        const material = {asset_id: 'material', alt: 'Project image', preview_url: '/material.png'};
        const galleryImage = {asset_id: 'copied-gallery', alt: 'Gallery image'};
        const project = {id: 'project', title: 'Project', versions, tasks: [], outputs: [],
            materials: [{title: 'Material', active: true, sources: [], images: [material]}]};
        const original = {...versions[0], content: 'First paragraph.\n\nSecond paragraph.', blocks: [
            {type: 'paragraph', text: 'First paragraph.'}, {type: 'paragraph', text: 'Second paragraph.'},
        ]};
        if (legacy) delete original.blocks;
        let saved;
        await page.route(origin + '/**', async route => {
            const {pathname} = new URL(route.request().url());
            const method = route.request().method();
            if (pathname === '/') return route.fulfill({contentType: 'text/html', body: '<html lang="en">' + template + '</html>'});
            if (packages) {
                if (pathname.endsWith('/mini-apps')) return route.fulfill({json: {items: [{
                    id: 'fixture.doc', name: 'Fixture Doc', source: 'package', provider: {digest: packages.revision},
                    entry: {kind: 'sandbox'},
                }]}});
                if (pathname.endsWith('/mini-app-mounts')) {
                    packages.mounts++;
                    return route.fulfill({json: {id: 'mount-' + packages.mounts, content_url: '/package/' + packages.revision,
                        effective_digest: packages.revision}});
                }
                if (pathname.startsWith('/package/')) return route.fulfill({contentType:'text/html',body:pathname});
                if (pathname.endsWith('/mini-app-outputs')) return route.fulfill({json: {items: []}});
            }
            if (pathname === '/admin/app-content/ai2apps.gallery') {
                return route.fulfill({contentType: 'text/html', body:
                    '<button draggable="true" ondragstart="event.dataTransfer.setData(\'application/x-ai2apps-gallery-asset\',\'gallery\');' +
                    'event.dataTransfer.setData(\'application/x-ai2apps-gallery-kind\',\'image\')">Gallery image</button>'});
            }
            if (pathname.endsWith('/images/gallery')) {
                assert.deepEqual(route.request().postDataJSON(), {asset_id: 'gallery'});
                return route.fulfill({json: galleryImage});
            }
            if (pathname.endsWith('/material.png') || pathname.includes('/images/')) {
                return route.fulfill({contentType: 'image/png', body: png});
            }
            if (pathname.endsWith('/versions/original') && method === 'POST') {
                saved = route.request().postDataJSON();
                return route.fulfill({json: {id: 'saved'}});
            }
            if (pathname.endsWith('/versions/original')) return route.fulfill({json: original});
            if (pathname.endsWith('/versions/saved')) return route.fulfill({json: {
                ...original, id: 'saved', content: saved.content ?? original.content, blocks: saved.blocks,
            }});
            if (pathname.endsWith('/projects/project')) return route.fulfill({json: project});
            if (pathname.endsWith('/projects')) return route.fulfill({json: [{id: project.id, title: project.title}]});
            return route.fulfill({status: 404});
        });
        await page.goto(packages ? origin + '/#ai2apps-instance=fixture' : origin);
        await page.addStyleTag({path: join(web, 'static/css/doc_studio.css')});
        await page.evaluate(() => { window.AI2AppsStudioDocumentOutput = () => ({update() {}}); });
        if (packages) await page.addScriptTag({path: join(web, 'static/js/studio_mini_apps.js')});
        await page.addScriptTag({path: join(web, 'static/js/doc_studio.js')});
        const save = async () => {
            await Promise.all([
                page.waitForResponse(response => response.url().endsWith('/versions/original') &&
                    response.request().method() === 'POST' && response.ok()),
                page.locator('#ds-editor button[type="submit"]').click(),
            ]);
            return saved;
        };
        await run(page, original, material, galleryImage, save);
        assert.deepEqual(failures, []);
    } finally {
        await browser.close();
    }
}

test('dropping from project materials inserts a row and dropping from Gallery joins it', () =>
    withEditor(async (page, original, material, galleryImage, save) => {
        await page.locator('#ds-editor-materials summary').click();
        await page.locator('#ds-editor-material-images img').dragTo(page.locator('#ds-blocks .ds-block-gap').nth(1));
        const figure = page.locator('#ds-blocks figure').first();
        await figure.waitFor();
        await page.locator('#ds-gallery-tab').click();
        await page.frameLocator('#ds-gallery-frame').getByRole('button', {name: 'Gallery image'}).dragTo(figure);
        await page.locator('.ds-image-row img[alt="Gallery image"]').waitFor();
        assert.equal(await page.locator('.ds-image-row').count(), 1);
        assert.equal(await page.locator('.ds-image-row figure').count(), 2);
        const saved = await save();
        assert.deepEqual(saved.blocks, [
            original.blocks[0],
            {type: 'image_row', images: [{asset_id: material.asset_id, alt: material.alt}, galleryImage]},
            original.blocks[1],
        ]);
    }));

test('a draft returned by an older Local opens by paragraph and saves through its text endpoint', () =>
    withEditor(async (page, original, _material, _galleryImage, save) => {
        const paragraphs = page.locator('#ds-blocks textarea');
        await paragraphs.nth(1).waitFor();
        assert.deepEqual(await paragraphs.evaluateAll(nodes => nodes.map(node => node.value)), original.content.split('\n\n'));
        assert.equal(await page.locator('#ds-error').isHidden(), true);
        assert.equal(await page.locator('#ds-legacy-editor-note').evaluate(note => note.hidden), false);
        assert.equal(await page.getByRole('button', {name: 'Rewrite with AI'}).count(), 0);
        await paragraphs.first().fill('Edited first paragraph.');
        const saved = await save();
        assert.equal(saved.content, 'Edited first paragraph.\n\nSecond paragraph.');
        assert.equal('blocks' in saved, false);
    }, {legacy: true}));


test('Doc Studio reuses the frame on same-version entry and mounts the updated Package', async () => {
    const packages = {revision: 'first', mounts: 0};
    await withEditor(async page => {
        const card = page.getByRole('button', {name:'Fixture Doc'});
        const frame = page.frameLocator('#ds-package-frame');
        const select = () => Promise.all([
            page.waitForResponse(response => response.url().endsWith('/mini-apps') && response.ok()),
            card.click(),
        ]);
        await select();
        await frame.getByText('/package/first').waitFor();
        await select();
        assert.equal(packages.mounts, 1);
        packages.revision = 'second';
        await select();
        await frame.getByText('/package/second').waitFor();
        assert.equal(packages.mounts, 2);
    }, {packages});
});
