const assert = require('node:assert/strict');
const {webcrypto} = require('node:crypto');
const {test} = require('node:test');

test('previews an arrangement, tests the exact draft, versions it and restores an older draft', async () => {
    global.window = {};
    global.document = {documentElement: {lang: 'en'}};
    global.crypto = webcrypto;
    require('../web/static/js/studio_comfyui.js');

    const workflow = '{"5":{"inputs":{"seed":18446744073709551615}}}';
    const mapping = {output: '7', prompt: 'Original', size: '1024x1024',
        omitted: [{node: '5', parameter: 'seed', value: '18446744073709551615'}], unusedNodes: []};
    const models = [
        {id: 'mlx', source: 'local', formats: ['png'], qualities: ['auto'], operations: ['image_generation']},
        {id: 'api', source: 'cloud', formats: ['png'], qualities: ['standard'], operations: ['image_generation']},
    ];
    const versions = [];
    let submitted;
    let refreshes = 0;
    global.fetch = async (url, request) => {
        assert.equal(request.headers['X-AI2Apps-App-Instance'], 'fixture');
        const reply = value => ({ok: true, json: async () => value});
        if (url.endsWith('/arrangement/providers')) return reply({codex: true});
        if (url.endsWith('/arrangement')) {
            const input = JSON.parse(request.body);
            assert.equal(input.provider, 'codex');
            return reply({...input.draft, prompt_label: 'Scene', unmapped_requests: ['Sampler is unavailable']});
        }
        if (url.endsWith('/inspect')) {
            assert.equal(JSON.parse(request.body).workflow_json, workflow);
            return reply(mapping);
        }
        if (url.endsWith('/versions')) return reply({items: [...versions].reverse()});
        if (request.method === 'PUT') {
            const body = JSON.parse(request.body);
            assert.equal(body.base_version, versions.length);
            assert.equal(body.test_run_id, 'fixture-run');
            const saved = {...body.preset, version: versions.length + 1};
            versions.push(saved);
            return reply(saved);
        }
        if (url.endsWith('/runs')) {
            submitted = JSON.parse(request.body);
            return reply({id: 'fixture-run', status: 'succeeded'});
        }
        return reply({items: versions.length ? [versions.at(-1)] : []});
    };
    const mount = () => window.AI2AppsComfyUI(
        () => ({'X-AI2Apps-App-Instance': 'fixture'}),
        async () => { refreshes += 1; }, () => models,
        size => size === '1024x1024' ? '' : 'Unsupported size',
    );
    const editor = mount();
    await editor.open();
    await editor.importFile({target: {value: 'selected', files: [{
        name: 'Illustration.json', size: workflow.length, text: async () => workflow,
    }]}});
    assert.equal(editor.error, '');
    assert.equal(editor.editing, true);
    editor.chooseModel('api');
    editor.preset.accepted_mapping = true;
    editor.assistant = 'codex';
    editor.instruction = 'Rename the prompt and map the sampler';
    await editor.propose();
    assert.equal(editor.proposal.diff.afterForm.fields[0].label, 'Scene');
    assert.equal(editor.preset.prompt_label, 'Positive prompt');
    editor.applyProposal();
    assert.equal(editor.preset.prompt_label, 'Scene');
    assert.deepEqual(editor.assistantWarnings, ['Sampler is unavailable']);
    assert.equal(editor.model.id, 'api');

    await editor.run();
    assert.equal(submitted, undefined);
    editor.review();
    await editor.run();
    assert.equal(submitted.test, true);
    assert.equal(submitted.preset.quality, 'standard');
    editor.preset.prompt = 'Changed after test';
    await editor.save();
    assert.equal(versions.length, 0);
    editor.preset.prompt = 'Original';
    await editor.save();
    assert.equal(versions[0].version, 1);
    assert.equal(editor.editing, false);

    await editor.beginEdit();
    editor.preset.layout.size_first = true;
    editor.preset.prompt = 'New default';
    editor.review();
    assert.equal(editor.preview.diff.beforeForm.fields[0].label, 'Scene');
    assert.equal(editor.preview.diff.afterForm.fields[0].label, 'Image size');
    assert.equal(editor.preview.diff.afterExecution.prompt, 'New default');
    await editor.run();
    await editor.save();
    assert.equal(versions[1].version, 2);

    const reopened = mount();
    await reopened.open();
    assert.equal(reopened.preset.version, 2);
    await reopened.beginEdit();
    await reopened.restoreVersion(1);
    assert.equal(reopened.preset.prompt, 'Original');
    assert.equal(reopened.baseVersion, 2);
    assert.equal(reopened.testReady, false);
    reopened.review();
    await reopened.run();
    await reopened.save();
    assert.equal(versions[2].version, 3);
    assert.equal(versions[1].prompt, 'New default');

    reopened.preset.prompt = 'Run override';
    await reopened.run();
    assert.equal(submitted.test, false);
    assert.equal(submitted.preset.prompt, 'Run override');
    assert.equal(versions[2].prompt, 'Original');
    assert.equal(refreshes, 4);
});
