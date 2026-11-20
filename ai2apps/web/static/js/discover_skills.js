(function () {
    'use strict';

    const endpoint = '/v1/platform/skills';
    const maxBytes = 8 * 1024 * 1024;
    const maxFiles = 256;

    async function request(path = '', method = 'GET', body) {
        const response = await fetch(endpoint + path, {
            method,
            credentials: 'same-origin',
            headers: body ? {'Content-Type': 'application/json'} : {},
            body: body ? JSON.stringify(body) : undefined,
        });
        if (response.status === 204) return null;
        const result = await response.json();
        if (!response.ok) {
            const description = typeof result.detail === 'string' ? result.detail
                : Array.isArray(result.detail) ? result.detail[0]?.msg : result.detail?.message;
            throw new Error(description || response.statusText);
        }
        return result;
    }

    async function encode(file) {
        const bytes = new Uint8Array(await file.arrayBuffer());
        let binary = '';
        for (let start = 0; start < bytes.length; start += 16384) {
            binary += String.fromCharCode(...bytes.subarray(start, start + 16384));
        }
        return {path: file.webkitRelativePath, content: btoa(binary)};
    }

    window.discoverSkills = function () {
        return {
            items: [], preview: null, details: null, removeTarget: null,
            githubUrl: '', github: null, folder: '', busySkills: false, skillError: '',
            reviewPlan: null, reviewReport: null,
            miniDraft: null, miniStudios: [], createdMini: null,
            get currentReview() {
                return this.reviewPlan?.preview_id === this.preview?.id ? this.reviewPlan : null;
            },
            get currentReport() {
                return this.currentReview && this.reviewReport?.id === this.currentReview.id ? this.reviewReport : null;
            },
            label(en, zh) { return document.documentElement.lang.startsWith('zh') ? zh : en; },
            reviewReason(reason) {
                return {
                    too_large: this.label('Over the per-file size limit', '超过单文件大小上限'),
                    not_text: this.label('Binary or unreadable text', '二进制或无法读取的文本'),
                    file_limit: this.label('Over the file count limit', '超过评估文件数上限'),
                    input_limit: this.label('Over the total review size limit', '超过评估总大小上限'),
                }[reason];
            },
            reviewSeverity(severity) {
                return {
                    critical: this.label('Critical', '严重'), high: this.label('High', '高'),
                    medium: this.label('Medium', '中'), low: this.label('Low', '低'),
                    info: this.label('Informational', '提示'),
                }[severity];
            },
            reviewDestination(destination) {
                return {
                    local: this.label('On this device', '在此设备处理'),
                    cloud: this.label('Sent to AI2Apps Cloud', '将发送到 AI2Apps Cloud'),
                    external: this.label('May be sent to the configured model provider', '可能发送到所配置的模型服务商'),
                }[destination];
            },
            sourceLabel(item) {
                if (item.source.kind === 'local') return this.label('Local folder', '本地目录');
                return item.source.repository + (item.source.folder ? '/' + item.source.folder : '');
            },
            async perform(action) {
                if (this.busySkills) return;
                this.busySkills = true;
                this.skillError = '';
                try { await action(); }
                catch (error) { this.skillError = error.message; }
                finally { this.busySkills = false; }
            },
            async loadSkills() { this.items = (await request()).items; },
            async previewLocal(event, target = null) {
                const files = Array.from(event.target.files);
                event.target.value = '';
                if (!files.length) return;
                await this.perform(async () => {
                    this.preview = null;
                    if (files.length > maxFiles || files.reduce((size, file) => size + file.size, 0) > maxBytes) {
                        throw new Error(this.label('Choose a folder with up to 256 files and 8 MiB.', '请选择最多 256 个文件、总大小不超过 8 MiB 的目录。'));
                    }
                    this.preview = await request('/preview/local', 'POST', {
                        files: await Promise.all(files.map(encode)),
                        target: target?.id, expected_revision: target?.revision,
                    });
                });
            },
            async lookupGithub() {
                await this.perform(async () => {
                    this.preview = null;
                    this.github = null;
                    const url = this.githubUrl.trim();
                    const result = await request('/github/folders', 'POST', {url});
                    if (!result.folders.length) {
                        throw new Error(this.label('No Skill folders were found.', '没有找到 Skill 目录。'));
                    }
                    this.github = {...result, url};
                    this.folder = result.folders[0];
                    if (result.folders.length === 1) await this.readGithubPreview();
                });
            },
            async readGithubPreview(target = null) {
                const source = target?.source ?? this.github;
                const result = target ? await request('/github/folders', 'POST', {url: source.url}) : source;
                const folder = target ? source.folder : this.folder;
                if (!result.folders.includes(folder)) {
                    throw new Error(this.label('This Skill folder is no longer in the repository.', '仓库中已找不到这个 Skill 目录。'));
                }
                this.preview = await request('/preview/github', 'POST', {
                    url: source.url, ref: result.ref, commit: result.commit, folder,
                    target: target?.id, expected_revision: target?.revision,
                });
            },
            async commitPreview() {
                await this.perform(async () => {
                    await request('/install/' + this.preview.id, 'POST');
                    this.preview = null;
                    this.details = null;
                    this.github = null;
                    this.githubUrl = '';
                    await this.loadSkills();
                });
            },
            async openReview() {
                await this.perform(async () => {
                    this.reviewReport = null;
                    this.reviewPlan = await request('/preview/' + this.preview.id + '/security-review');
                });
            },
            async runReview() {
                await this.perform(async () => {
                    const plan = this.currentReview;
                    this.reviewReport = null;
                    this.reviewReport = await request('/preview/' + plan.preview_id + '/security-review', 'POST', {
                        plan_id: plan.id,
                        language: this.label('en', 'zh'),
                    });
                });
            },
            async removeSkill() {
                await this.perform(async () => {
                    await request('/' + this.removeTarget.id, 'DELETE');
                    this.removeTarget = null;
                    this.details = null;
                    await this.loadSkills();
                });
            },
            async openSkill(item) {
                await this.perform(async () => {
                    this.miniDraft = null;
                    this.createdMini = null;
                    this.details = await request('/' + item.id);
                });
            },
            addMiniParameter() {
                this.miniDraft.parameters.push({rowId: crypto.randomUUID(), key: '', label: '', type: 'text', required: false, default: '', options: ''});
            },
            async openMiniCreator() {
                await this.perform(async () => {
                    this.miniStudios = (await request('/mini-app-studios')).items;
                    this.createdMini = null;
                    this.miniDraft = {title: this.details.name, studio: '', parameters: []};
                    this.addMiniParameter();
                });
            },
            async createMiniApp() {
                await this.perform(async () => {
                    const {title, studio} = this.miniDraft;
                    const parameters = this.miniDraft.parameters.map(field => ({
                        key: field.key.trim(), label: field.label.trim(), type: field.type, required: field.required,
                        choices: field.type === 'choice' ? field.options.split('\n').map(v => v.trim()).filter(Boolean) : [],
                        default: (field.type === 'image' || field.default === '') ? null
                            : field.type === 'boolean' ? field.default === 'true'
                            : field.type === 'number' ? Number(field.default) : field.default,
                    }));
                    this.createdMini = await request('/' + this.details.id + '/mini-apps', 'POST', {
                        title, studio, revision: this.details.revision, parameters,
                    });
                    this.miniDraft = null;
                });
            },
        };
    };
}());
