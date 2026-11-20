/* Studio host output surface. Producers supply artifact metadata, never markup. */
(() => {
    'use strict';

    window.AI2AppsStudioDocumentOutput = function mount(root, {tr, formatLabel, cancel, error, busy, taskNames, resume, canResume}) {
        const get = selector => root.querySelector(selector);
        const picker = get('[data-output-select]');
        const preview = get('[data-output-preview]');
        const copy = get('[data-output-copy]');
        const download = get('[data-output-download]');
        const selection = new Map();
        let project = '', outputs = [], shown = null, text = '';

        async function show() {
            const output = outputs.find(item => item.id === picker.value) || outputs[0];
            if (shown?.id === output?.id) return;
            shown = output || null;
            preview.replaceChildren();
            preview.hidden = !output;
            copy.hidden = true;
            download.hidden = !output;
            text = '';
            if (!output) return;
            selection.set(project, output.id);
            download.href = output.download_url;
            if (output.media_type === 'image/png') {
                const image = document.createElement('img');
                image.alt = output.name;
                image.src = output.preview_url;
                preview.append(image);
            } else if (output.media_type === 'application/zip') {
                const name = document.createElement('p');
                name.textContent = output.name;
                preview.append(name);
            } else if (output.media_type === 'text/html' || output.media_type === 'application/pdf') {
                const frame = document.createElement('iframe');
                frame.title = output.name;
                if (output.media_type === 'text/html') frame.setAttribute('sandbox', '');
                frame.src = output.preview_url;
                preview.append(frame);
            } else if (output.media_type === 'text/plain') {
                try {
                    const response = await fetch(output.preview_url, {credentials: 'same-origin'});
                    if (!response.ok) throw new Error(tr('无法预览此产物', 'Could not preview this output'));
                    const value = await response.text();
                    if (shown !== output) return;
                    const pre = document.createElement('pre');
                    pre.textContent = text = value;
                    preview.append(pre);
                    copy.hidden = false;
                    copy.textContent = output.target?.startsWith('translation-') ? tr('复制译文', 'Copy translation') : tr('复制 X Post', 'Copy X Post');
                } catch (failure) {
                    if (shown === output) {
                        shown = null;
                        error(failure);
                    }
                }
            } else {
                const name = document.createElement('p');
                name.textContent = output.name + ' · ' + formatLabel(output.target);
                preview.append(name);
            }
        }
        picker.onchange = show;
        copy.onclick = async () => {
            try {
                const selected = shown;
                const label = copy.textContent;
                await navigator.clipboard.writeText(text);
                copy.textContent = tr('已复制', 'Copied');
                window.setTimeout(() => { if (shown === selected) copy.textContent = label; }, 1500);
            } catch (failure) { error(failure); }
        };

        const labels = {
            queued: ['排队中', 'Queued'], running: ['运行中', 'Running'],
            waiting_resource: ['等待资源', 'Waiting for resources'], waiting_user: ['等待处理', 'Waiting for input'],
            cancelling: ['正在取消', 'Cancelling'], cancelled: ['已取消', 'Cancelled'],
            completed: ['已完成', 'Completed'], failed: ['失败', 'Failed'],
            interrupted: ['已中断', 'Interrupted'], partial: ['部分完成', 'Partially completed'],
        };
        function failureMessage(task) {
            const details = task.progress?.draft_error;
            switch (details?.code) {
                case 'post_too_long': {
                    const {count, limit, weighted} = details;
                    const name = weighted ? tr('X 普通帖', 'X Standard Post') : tr('X 长帖', 'X Long Post');
                    const unit = weighted ? tr('加权字符', 'weighted characters') : tr('字符', 'characters');
                    const shorten = count - limit;
                    return tr(
                        `${name}成稿共 ${count.toLocaleString()} 个${unit}，上限 ${limit.toLocaleString()}。请至少缩短 ${shorten.toLocaleString()} 个${unit}。`,
                        `${name} uses ${count.toLocaleString()} ${unit} after formatting. The limit is ${limit.toLocaleString()}. Shorten it by at least ${shorten.toLocaleString()} ${unit}.`);
                }
                case 'url_in_body':
                    return tr('正文含有网址。请用 [1] 这类编号标注来源，导出时会附上来源链接。',
                        'The draft body contains a URL. Use numbered citations like [1]. Export appends the source link.');
                case 'empty_body':
                    return tr('去掉引用编号后正文为空。请补写正文。', 'The post is empty after citation markers are removed. Add body text.');
                case 'invalid_citations':
                    return tr('模型未能用素材中的有效编号标注引用。可重试生成。',
                        'The model did not cite the supplied materials with valid citation numbers. Try generating again.');
                case 'invalid_draft':
                    return tr('模型未返回符合稿件格式的内容。可重试生成。',
                        'The model returned a draft in an invalid format. Try generating again.');
                default:
                    if (task.progress?.model_validation_error === 'X Post exceeds 280 weighted characters including its source link') {
                        return tr('X 普通帖含来源链接超过 280 个加权字符。请缩短正文，或选择 X 长帖重新生成。',
                            'The X Standard Post exceeds 280 weighted characters with its source link. Shorten it or regenerate as an X Long Post.');
                    }
                    return task.message;
            }
        }
        let lastTaskSnapshot = '';
        function tasks(items) {
            const snapshot = JSON.stringify(items);
            if (snapshot === lastTaskSnapshot) return;
            lastTaskSnapshot = snapshot;
            const rows = items.map(task => {
                const row = document.createElement('div');
                row.className = 'ds-task';
                const label = document.createElement('strong');
                label.textContent = tr(...(taskNames[task.kind] || [task.kind, task.kind])) + ' · ' +
                    tr(...(labels[task.status] || [task.status, task.status]));
                row.append(label);
                if (Number.isInteger(task.progress?.total) && Number.isInteger(task.progress?.completed)) {
                    const progress = document.createElement('small');
                    const {completed, total} = task.progress;
                    progress.textContent = tr(` · ${completed}/${total} 段`, ` · ${completed}/${total} passages`);
                    row.append(progress);
                }
                if (task.progress?.model_attempt && busy(task)) {
                    const attempt = document.createElement('small');
                    const number = task.progress.model_attempt;
                    attempt.textContent = tr(` · 第 ${number} 次模型调用`, ` · Model attempt ${number}`);
                    row.append(attempt);
                }
                if (task.message && ['failed', 'interrupted', 'partial'].includes(task.status)) {
                    const detail = document.createElement('p');
                    detail.textContent = failureMessage(task);
                    row.append(detail);
                }
                if (busy(task) && task.status !== 'cancelling') {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.textContent = tr('取消', 'Cancel');
                    button.onclick = async () => {
                        button.disabled = true;
                        try { await cancel(task); }
                        catch (failure) { error(failure); button.disabled = false; }
                    };
                    row.append(' ', button);
                }
                if (resume && canResume?.(task)) {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.textContent = tr('继续翻译', 'Resume translation');
                    button.onclick = async () => {
                        button.disabled = true;
                        try { await resume(task); }
                        catch (failure) { error(failure); button.disabled = false; }
                    };
                    row.append(' ', button);
                }
                return row;
            });
            get('[data-output-tasks]').replaceChildren(...rows);
        }

        return {
            select(id) {
                if (!outputs.some(item => item.id === id)) return false;
                picker.value = id;
                void show();
                return true;
            },
            update(projectId, artifacts, jobs) {
                project = projectId;
                outputs = artifacts;
                get('[data-output-empty]').hidden = !!outputs.length;
                get('[data-output-picker]').hidden = !outputs.length;
                const selected = selection.get(projectId);
                const choices = outputs.map(item => new Option(
                    `${item.name} · ${formatLabel(item.target)} · ${new Date(item.created_at).toLocaleString()}`, item.id));
                const signature = JSON.stringify(choices.map(option => [option.value, option.text]));
                if (picker.dataset.signature !== signature) {
                    picker.replaceChildren(...choices);
                    picker.dataset.signature = signature;
                }
                picker.value = outputs.some(item => item.id === selected) ? selected : outputs[0]?.id || '';
                void show();
                tasks(jobs);
            },
        };
    };
})();
