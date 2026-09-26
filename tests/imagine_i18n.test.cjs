const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname + '/../ai2apps/web/static/js/imagine_studio.js', 'utf8');
const template = fs.readFileSync(__dirname + '/../ai2apps/web/templates/system_apps/imagine_studio.html', 'utf8');
const context = { window: {}, document: {documentElement: {lang: 'en'}}, structuredClone, console };
vm.createContext(context);
vm.runInContext(source.replace('function normalizedLocale(value)', 'window.testTranslations = TRANSLATIONS; function normalizedLocale(value)'), context);
const dictionaries = context.window.testTranslations;
assert.deepEqual(Object.keys(dictionaries.zh).sort(), Object.keys(dictionaries.en).sort());
const placeholders = value => Array.from(value.matchAll(/\{(\w+)\}/g), m => m[1]).sort();
for (const key of Object.keys(dictionaries.en)) {
    assert.deepEqual(placeholders(dictionaries.zh[key]), placeholders(dictionaries.en[key]), key);
}
for (const match of (source + template).matchAll(/\btr\('([^']+)'/g)) {
    assert.ok(Object.hasOwn(dictionaries.en, match[1]), `missing translation: ${match[1]}`);
}
assert.doesNotMatch(template, /locale\s*===|locale\.startsWith/, 'UI must use translation keys');
assert.doesNotMatch(template, />Output<|>Chat<|>Opening Mini-App/);
const app = context.window.imagineStudioApp();
app.icons = () => {};
app.prompt = 'User prompt stays unchanged';
app.productScene = 'custom';
app.productSceneDescription = 'User scene stays unchanged';
app.productLight = 'window';
app.stickerEmotion = 'wow';
const names = {};
for (const locale of ['en', 'zh', 'en']) {
    app.setLocale(locale);
    names[locale] = Array.from(app.miniApps, item => item.name);
    for (const item of app.miniApps) {
        for (const field of ['name', 'summary', 'description', 'actionTitle', 'runLabel']) {
            assert.ok(item[field], `${locale}:${item.id}:${field}`);
            assert.notEqual(item[field], item.prefix + 'Name');
        }
    }
    for (const item of [...app.productScenes, ...app.productLights, ...app.productCompositions, ...app.stickerEmotions]) {
        assert.equal(app.stickerLabel(item), dictionaries[locale][item.labelKey]);
    }
    assert.equal(app.prompt, 'User prompt stays unchanged');
    assert.equal(app.productSceneDescription, 'User scene stays unchanged');
    assert.equal(app.productScene, 'custom');
    assert.equal(app.productLight, 'window');
    assert.equal(app.stickerEmotion, 'wow');
    assert.equal(app.tr('stickerProgress', {done: 2, total: 4}).includes('2/4'), true);
}
assert.notDeepEqual(names.en, names.zh);
app.setLocale('zh');
assert.equal(app.qualityLabel('auto'), '自动');
assert.equal(app.qualityLabel('high'), '高');
assert.equal(app.qualityLabel('future-provider-value'), 'future-provider-value');
console.log('Imagine Studio translations and live language switching: passed');
