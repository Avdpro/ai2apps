const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../packages/ai2apps-media-voice-studio-suite/web/i18n.js'), 'utf8');
const document = {documentElement: {lang: ''}, title: ''};
const context = {window: {}, document};
vm.runInNewContext(source, context);

const i18n = context.window.AI2AppsMediaVoiceI18n;
assert.equal(i18n.normalize('zh-Hans-CN'), 'zh-CN');
assert.equal(i18n.normalize('en-US'), 'en');
assert.equal(i18n.translate('en', '生成字幕视频'), 'Create subtitled video');
assert.equal(i18n.translate('en', '视频本地化'), 'Video localization');
assert.equal(i18n.translate('en', '步骤 03'), 'Step 03');
assert.equal(i18n.translate('en', '角色 3 名称'), 'Speaker 3 name');
assert.equal(i18n.translate('zh-CN', '生成字幕视频'), '生成字幕视频');
assert.equal(i18n.translate('zh-CN', '视频本地化'), '视频本地化');
i18n.configureDocument('video-subtitles', 'en');
assert.equal(document.documentElement.lang, 'en');
assert.equal(document.title, 'Video Subtitles and Translation');
i18n.configureDocument('video-subtitles', 'zh-CN');
assert.equal(document.documentElement.lang, 'zh-CN');
assert.equal(document.title, '视频字幕与翻译');
