const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../ai2apps/web/static/js/video_studio.js'), 'utf8');

function studio() {
    const context = {
        window: {t: key => key, matchMedia: () => ({matches: false}), location: {origin: 'http://localhost'}},
        document: {documentElement: {lang: 'en'}},
        crypto: {randomUUID: () => '00000000-0000-4000-8000-000000000000'},
        localStorage: {setItem() {}},
        URL,
    };
    vm.runInNewContext(source, context);
    const app = context.window.videoStudioApp();
    app.$nextTick = callback => callback();
    return app;
}

test('Video Output combines producers and keeps the selected result across Mini-App switches', () => {
    const app = studio();
    app.tasks = [{id: 'generated', status: 'succeeded', created_at: '2026-10-11T10:00:00Z',
        metadata: {label: 'Generated'}, progress: {percent: 100},
        result: {video: {download_url: '/v1/platform/sessions/ses_a/artifacts/art_a/download'}}}];
    app.audioRuns = [{id: 'audio', miniAppId: 'ai2apps.video.extract-audio', status: 'succeeded',
        createdAt: '2026-10-11T10:01:00Z', title: 'Extracted audio', progress: 100,
        artifacts: [{id: 'audio-artifact', kind: 'audio', name: 'voice.wav', mediaType: 'audio/wav', final: true,
            downloadUrl: '/v1/platform/sessions/ses_b/artifacts/art_b/download'}]}];
    app.composerRuns = [{id: 'composer', miniAppId: 'ai2apps.video.composer', status: 'succeeded',
        createdAt: '2026-10-11T10:02:00Z', title: 'Composition', progress: 100,
        artifacts: [{id: 'composer-artifact', kind: 'video', name: 'composition.mp4', mediaType: 'video/mp4', final: true,
            downloadUrl: '/v1/platform/sessions/ses_c/artifacts/art_c/download'}]}];
    app.upscalingRuns = [{id: 'upscale', miniAppId: 'ai2apps.video.upscaling', status: 'succeeded',
        createdAt: '2026-10-11T10:02:30Z', title: 'Upscaled video', progress: 100,
        artifacts: [{id: 'upscale-artifact', kind: 'video', name: 'upscaled.mp4', mediaType: 'video/mp4', final: true,
            downloadUrl: '/v1/platform/sessions/ses_e/artifacts/art_e/download'}]}];
    app.packageRuns = [{id: 'package', miniAppId: 'ai2apps.video.subtitles', status: 'succeeded',
        createdAt: '2026-10-11T10:03:00Z', title: 'Subtitles', progress: 100,
        artifacts: [{id: 'package-artifact', kind: 'file', name: 'subtitles.zip', mediaType: 'application/zip', final: true,
            downloadUrl: '/v1/platform/sessions/ses_d/artifacts/art_d/download'}]}];

    assert.deepEqual(Array.from(app.sharedOutputItems, item => item.key),
        ['run:package', 'run:upscale', 'run:composer', 'run:audio', 'task:generated']);
    app.selectOutputItem(app.sharedOutputItems.find(item => item.key === 'run:audio'));
    assert.equal(app.selectedOutputKind, 'audio');
    app.mode = 'composer';
    assert.equal(app.selectedOutputItem.key, 'run:audio');
    app.packageMiniAppId = 'ai2apps.video.subtitles';
    assert.equal(app.selectedOutputItem.key, 'run:audio');
    assert.equal(app.selectedOutputArtifact.name, 'voice.wav');
    app.selectOutputItem(app.sharedOutputItems.find(item => item.key === 'run:package'));
    assert.equal(app.selectedOutputKind, 'file');
    assert.equal(app.selectedOutputArtifact.name, 'subtitles.zip');
});

test('Package download event selects a temporary file result until its run appears', () => {
    const app = studio();
    app.refresh = async () => {};
    app.handlePackageOutput({detail: {studioId: 'ai2apps.video-studio', miniAppId: 'ai2apps.video.subtitles',
        result: {downloadUrl: '/v1/platform/sessions/ses_z/artifacts/art_z/download', filename: 'subtitles.zip',
            mediaType: 'application/zip'}}});
    assert.equal(app.selectedOutputItem.source, 'package-live');
    assert.equal(app.selectedOutputKind, 'file');
    assert.equal(app.selectedOutputArtifact.name, 'subtitles.zip');
    app.mode = 'composer';
    assert.match(app.selectedOutputItem.key, /^package-live:/);
    app.handlePackageOutput({detail: {studioId: 'ai2apps.video-studio', miniAppId: 'ai2apps.video.dubbing',
        result: {downloadUrl: '/v1/platform/sessions/ses_y/artifacts/art_y/download', filename: 'dubbed.mp4',
            mediaType: 'video/mp4'}}});
    assert.equal(app.sharedOutputItems.length, 2);
    assert.equal(app.selectedOutputKind, 'video');
});

for (const mobile of [false, true]) test(`actual Mini-App navigation preserves shared Output (${mobile?'Mobile':'Desktop'})`, async () => {
    const app=studio();
    app.mobileViewport=mobile;
    app.tasks=[{id:'video',status:'succeeded',created_at:'2026-10-15',metadata:{mode:'t2v'},result:{video:{download_url:'/video'}}}];
    app.audioRuns=[{id:'audio',status:'succeeded',miniAppId:'ai2apps.video.extract-audio',artifacts:[{id:'a',kind:'audio',mediaType:'audio/wav',downloadUrl:'/audio'}]}];
    app.selectedOutputKey='run:audio';app.selectedOutputArtifactId='a';
    for(const name of ['loadExtractorDraft','loadUpscalingModels','loadComposerProject','loadComposerMaskModels','loadComposerChatModels'])app[name]=async()=>{};
    app.syncDefaults=()=>{};app.persistShellState=()=>{};app.saveCurrentMiniAppDraft=()=>{};app.restoreMiniAppDraft=()=>{};app.icons=()=>{};
    const tasks=app.tasks,runs=app.audioRuns,keys=Array.from(app.sharedOutputItems,x=>x.key);
    for(const mini of app.miniApps.filter(x=>x.mode)) {
        await app.selectMiniApp(mini.id);
        assert.equal(app.tasks,tasks);assert.equal(app.audioRuns,runs);
        assert.deepEqual(Array.from(app.sharedOutputItems,x=>x.key),keys);
        assert.equal(app.selectedOutputArtifact.id,'a');
    }
});

test('late Package completion does not steal shared Output selection',()=>{
    const app=studio();app.refresh=async()=>{};
    app.selectedOutputKey='task:chosen';
    app.handlePackageOutput({detail:{studioId:'ai2apps.video-studio',miniAppId:'package.video',preserveSelection:true,
        result:{runId:'background',downloadUrl:'/v1/platform/sessions/s/artifacts/a/download'}}});
    assert.equal(app.selectedOutputKey,'task:chosen');
});
