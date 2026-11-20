(function () {
    'use strict';

    const API = '/v1/platform/imagine-studio/comfyui';
    const MAX_BYTES = 512 * 1024;
    const snapshot = value => JSON.parse(JSON.stringify(value));
    const layoutDefaults = () => ({size_first: false, prompt_help: '', size_help: '', size_choices: []});

    window.AI2AppsComfyUI = (headers, refreshOutput, catalog, validateSize) => ({
        presets: [], diagnostics: [], selected: '', preset: null, mapping: null,
        editing: false, busy: false, loaded: false, error: '', status: '',
        baseline: null, baseVersion: 0, preview: null, test: null, versions: [],
        assistant: 'system', codexAvailable: false, instruction: '', proposal: null, assistantWarnings: [],

        label(en, zh) {
            return document.documentElement.lang.startsWith('zh') ? zh : en;
        },
        get executionModels() {
            return catalog().filter(model => model.operations.includes('image_generation'));
        },
        get model() {
            return this.executionModels.find(item => item.id === this.preset?.model && item.source === this.preset?.source);
        },
        get sizeError() {
            if (!this.model) return '';
            const choices = this.preset.layout.size_choices.map(choice => choice.size);
            if (choices.length && !choices.includes(this.preset.size)) {
                return this.label('The default size must be one of the form choices.', '默认尺寸必须是表单选项之一。');
            }
            return validateSize(this.preset.size, this.model)
                || choices.map(size => validateSize(size, this.model)).find(Boolean) || '';
        },
        get layoutError() {
            const choices = this.preset?.layout.size_choices || [];
            if (choices.some(choice => !choice.label.trim() || !choice.size.trim())) {
                return this.label('Name each size choice and enter its dimensions.', '请填写每个尺寸选项的名称和宽高。');
            }
            if (new Set(choices.map(choice => choice.size)).size !== choices.length) {
                return this.label('Size choices must be distinct.', '尺寸选项不能重复。');
            }
            return '';
        },
        get ready() {
            return Boolean(this.mapping?.runnable !== false && this.model && !this.sizeError && !this.layoutError && this.preset?.prompt.trim()
                && this.preset.name.trim() && this.preset.accepted_mapping);
        },
        get draftKey() {
            return this.ready ? JSON.stringify(this.requestPreset()) : '';
        },
        get previewReady() {
            return Boolean(this.preview && this.preview.key === this.draftKey);
        },
        get testReady() {
            return Boolean(this.test?.status === 'succeeded' && this.test.key === this.draftKey);
        },
        get testRunning() {
            return ['queued', 'running', 'waiting_input'].includes(this.test?.status);
        },
        get fields() {
            return this.preset?.layout.size_first ? ['size', 'prompt'] : ['prompt', 'size'];
        },
        formDescription(preset) {
            if (!preset) return null;
            const layout = preset.layout || layoutDefaults();
            const prompt = {label: preset.prompt_label || this.label('Positive prompt', '正向提示词'),
                control: this.label('Multiline text', '多行文本'), help: layout.prompt_help};
            const size = {label: preset.size_label || this.label('Image size', '图片尺寸'),
                control: this.label('Dimensions', '宽高'), help: layout.size_help};
            if (layout.size_choices.length) size.control = layout.size_choices.map(
                choice => choice.label + ' (' + choice.size + ')').join(' · ');
            return {name: preset.name, fields: layout.size_first ? [size, prompt] : [prompt, size]};
        },
        executionDescription(preset) {
            if (!preset) return null;
            return {model: preset.model, source: preset.source, prompt: preset.prompt.trim(),
                size: preset.size, quality: preset.quality, outputFormat: preset.output_format};
        },
        comparison(before, after) {
            return {
                beforeForm: this.formDescription(before), afterForm: this.formDescription(after),
                beforeExecution: this.executionDescription(before), afterExecution: this.executionDescription(after),
            };
        },
        async request(path, method = 'GET', body) {
            const response = await fetch(API + path, {
                credentials: 'same-origin', method,
                headers: {...headers(), ...(body ? {'Content-Type': 'application/json'} : {})},
                body: body ? JSON.stringify(body) : undefined,
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) {
                const detail = typeof result.detail === 'string' ? result.detail : result.detail?.[0]?.msg;
                throw new Error(detail || this.label('Request failed', '请求失败') + ' (' + response.status + ')');
            }
            return result;
        },
        async open() {
            if (this.loaded || this.busy) return;
            await this.perform(async () => {
                this.presets = (await this.request('/presets')).items;
                this.diagnostics = (await this.request('/diagnostics')).items;
                if (this.presets.length) await this.loadPreset(this.presets[0].id);
                const availability = await this.request('/arrangement/providers').catch(() => ({}));
                this.codexAvailable = Boolean(availability.codex);
                this.loaded = true;
            });
        },
        async perform(operation) {
            this.busy = true;
            this.error = '';
            this.status = '';
            try { await operation(); }
            catch (error) { this.error = error.message; }
            finally { this.busy = false; }
        },
        inspect(workflow_json, output = null) {
            return this.request('/inspect', 'POST', {workflow_json, output});
        },
        async loadPreset(id) {
            const source = this.presets.find(item => item.id === id);
            if (!source) return;
            const mapping = await this.inspect(source.workflow_json, source.output);
            this.preset = {layout: layoutDefaults(), ...snapshot(source)};
            this.baseline = snapshot(this.preset);
            this.baseVersion = source.version || 1;
            this.resetReview();
            this.versions = [];
            this.mapping = mapping;
            this.selected = id;
            this.editing = false;
        },
        async select(id) {
            await this.perform(() => this.loadPreset(id));
        },
        async loadDiagnostic(id) {
            const source = this.diagnostics.find(item => item.id === id);
            if (!source) return;
            await this.perform(async () => {
                const mapping = await this.inspect(source.workflow_json, source.output);
                this.startDraft(source, mapping);
            });
        },
        startDraft(source, mapping) {
            this.mapping = mapping;
            this.preset = {
                ...source, output: mapping.output, prompt: mapping.prompt, size: mapping.size,
                model: '', source: 'local', accepted_mapping: false,
                prompt_label: this.label('Positive prompt', '正向提示词'),
                size_label: this.label('Image size', '图片尺寸'), layout: layoutDefaults(),
            };
            this.selected = '';
            this.baseline = null;
            this.baseVersion = 0;
            this.versions = [];
            this.resetReview();
            this.editing = true;
        },
        async benchmark() {
            await this.perform(async () => {
                const result = await this.request('/benchmark', 'POST', {});
                this.status = this.label('Benchmark complete: ', '基准测试完成：')
                    + result.cases + this.label(' cases, ', ' 个案例，') + result.files
                    + this.label(' files. Standard tasks: ', ' 个文件。Standard tasks：')
                    + (result.standard ? 'OK' : this.label('check receipt', '查看记录'))
                    + ' · Codex: ' + (result.codex ? 'OK' : this.label('check receipt', '查看记录'));
                await refreshOutput().catch(() => {});
            });
        },
        async saveDiagnostic() {
            await this.perform(async () => {
                const {id, name, workflow_json, output} = this.preset;
                const item = await this.request('/diagnostics/' + id, 'PUT', {id, name, workflow_json, output});
                this.diagnostics = [...this.diagnostics.filter(existing => existing.id !== id), item];
                this.status = this.label('Diagnostic draft saved.', '诊断草稿已保存。');
            });
        },
        async importFile(event) {
            const file = event.target.files[0];
            event.target.value = '';
            if (!file) return;
            await this.perform(async () => {
                if (file.size > MAX_BYTES) throw new Error(this.label('Workflow exceeds 512 KiB.', '工作流超过 512 KiB。'));
                const workflow_json = await file.text();
                const mapping = await this.inspect(workflow_json);
                this.startDraft({
                    id: crypto.randomUUID().replaceAll('-', ''),
                    name: file.name.replace(/\.json$/i, '').slice(0, 120),
                    workflow_json,
                }, mapping);
            });
        },
        async changeOutput(event) {
            const output = event.target.value;
            await this.perform(async () => {
                const mapping = await this.inspect(this.preset.workflow_json, output);
                Object.assign(this.preset, {
                    output, prompt: mapping.prompt, size: mapping.size, accepted_mapping: false,
                });
                this.mapping = mapping;
                this.resetReview();
            });
            event.target.value = this.preset.output;
        },
        chooseModel(id) {
            const model = this.executionModels.find(item => item.id === id);
            this.preset.model = model?.id || '';
            this.preset.source = model?.source || 'local';
        },
        requestPreset() {
            if (!this.ready) throw new Error(this.label(
                'Choose a model and valid size, enter a prompt, and review the mapping.',
                '请选择模型和有效尺寸、填写提示词，并确认映射说明。'));
            return {
                ...this.preset, output_format: this.model.formats[0] || 'png',
                quality: this.model.qualities.includes('auto') ? 'auto' : this.model.qualities[0] || 'standard',
            };
        },
        resetReview() {
            this.preview = null;
            this.test = null;
            this.proposal = null;
            this.assistantWarnings = [];
        },
        async beginEdit() {
            this.editing = true;
            if (!this.baseVersion) return;
            await this.perform(async () => {
                this.versions = (await this.request('/presets/' + this.preset.id + '/versions')).items;
            });
        },
        async discardEdits() {
            if (this.baseVersion) {
                await this.select(this.preset.id);
                return;
            }
            this.preset = null;
            this.mapping = null;
            this.editing = false;
            this.resetReview();
        },
        async restoreVersion(version) {
            const older = this.versions.find(item => item.version === Number(version));
            if (!older) return;
            await this.perform(async () => {
                const mapping = await this.inspect(older.workflow_json, older.output);
                this.preset = {layout: layoutDefaults(), ...snapshot(older)};
                this.mapping = mapping;
                this.resetReview();
                this.status = this.label('Older version loaded as a draft. Preview and test to save it.',
                    '旧版本已载入为草稿。预览并试跑后可保存为新版本。');
            });
        },
        async propose() {
            if (!this.instruction.trim()) return;
            await this.perform(async () => {
                this.proposal = null;
                const {name, prompt, size, prompt_label, size_label, layout, workflow_json, output} = this.preset;
                const response = await this.request('/arrangement', 'POST', {
                    provider: this.assistant, instruction: this.instruction.trim(),
                    draft: {name, prompt, size, prompt_label, size_label, layout},
                    workflow: {workflow_json, output},
                    model_label: this.model?.label || '',
                    sizes: [...new Set([...(this.model?.sizeCapability?.presets || []), size])]
                        .filter(value => this.model && !validateSize(value, this.model)).slice(0, 24),
                });
                const {unmapped_requests, ...changes} = response;
                const candidate = {...snapshot(this.preset), ...changes};
                const invalidSizes = this.model ? [candidate.size, ...candidate.layout.size_choices.map(choice => choice.size)]
                    .filter(value => validateSize(value, this.model)) : [];
                this.proposal = {changes, unmapped: unmapped_requests, invalidSizes, key: JSON.stringify(this.preset),
                    diff: this.comparison(this.preset, candidate)};
            });
        },
        applyProposal() {
            if (!this.proposal || this.proposal.invalidSizes.length || this.proposal.key !== JSON.stringify(this.preset)) return;
            Object.assign(this.preset, this.proposal.changes);
            this.assistantWarnings = this.proposal.unmapped;
            this.proposal = null;
            this.preview = null;
            this.test = null;
        },
        review() {
            if (!this.ready) return;
            const after = this.requestPreset();
            this.preview = {key: this.draftKey, diff: this.comparison(this.baseline, after)};
        },
        async save() {
            if (!this.previewReady || !this.testReady) return;
            await this.perform(async () => {
                const preset = await this.request('/presets/' + this.preset.id, 'PUT', {
                    preset: this.requestPreset(), base_version: this.baseVersion, test_run_id: this.test.id,
                });
                this.presets = [...this.presets.filter(item => item.id !== preset.id), preset];
                this.preset = snapshot(preset);
                this.baseline = snapshot(preset);
                this.baseVersion = preset.version;
                this.selected = preset.id;
                this.editing = false;
                this.resetReview();
                this.status = this.label('Preset version saved.', '已保存预设版本。');
            });
        },
        async checkTest() {
            if (!this.testRunning) return;
            const {id, key} = this.test;
            const run = await this.request('/runs/' + id);
            if (this.test?.id !== id) return;
            this.test = {id, key, status: run.status, error: run.error?.message};
        },
        async followTest(id) {
            for (let attempt = 0; attempt < 300 && this.test?.id === id && this.testRunning; attempt += 1) {
                await new Promise(resolve => setTimeout(resolve, 2000));
                if (this.test?.id !== id) return;
                try { await this.checkTest(); } catch (_) { return; }
            }
        },
        async run() {
            if (this.editing && (!this.previewReady || this.testRunning)) return;
            await this.perform(async () => {
                const test = this.editing;
                const key = this.draftKey;
                const run = await this.request('/runs', 'POST', {preset: this.requestPreset(), test});
                if (test) {
                    this.test = {id: run.id, status: run.status, key};
                    void this.followTest(run.id);
                }
                this.status = this.label('Submitted. Follow progress and results in Output.', '已提交。请在共享输出中查看进度和结果。');
                await refreshOutput().catch(() => {});
            });
        },
    });
})();
