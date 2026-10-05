/* Native AI2Apps App/Mini-App task panel. No external CLI is required. */
(function () {
    'use strict';
    const dialog = document.querySelector('[data-native-coder]');
    if (!dialog) return;
    const form = dialog.querySelector('form');
    const prompt = form.querySelector('[name="prompt"]');
    const model = form.querySelector('[name="model"]');
    const heading = dialog.querySelector('[data-native-title]');
    const progress = dialog.querySelector('[data-native-progress]');
    const output = dialog.querySelector('[data-native-output]');
    const questions = dialog.querySelector('[data-native-questions]');
    const children = dialog.querySelector('[data-native-children]');
    const review = dialog.querySelector('[data-native-review]');
    const preview = dialog.querySelector('[data-native-preview]');
    const previewComponent = dialog.querySelector('[data-native-preview-component]');
    const applyButton = dialog.querySelector('[data-native-apply]');
    const startButton = dialog.querySelector('[data-native-start]');
    const stopButton = dialog.querySelector('[data-native-stop]');
    const changesButton = dialog.querySelector('[data-native-changes]');
    let project, taskId, lastState, reviewedRevision, pollTimer, appliedCallback;
    let generation = 0;
    const terminal = new Set(['completed', 'failed', 'cancelled']);
    const storageKey = () => 'ai2apps.native-coder.' + project.id;
    const taskURL = (suffix) => '/v1/platform/coder/tasks/' + encodeURIComponent(taskId) + (suffix || '');
    async function api(url, options) {
        const response = await fetch(url, { credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, ...(options || {}) });
        const value = await response.json();
        if (!response.ok) throw new Error(value.detail?.message || 'Request failed: ' + response.status);
        return value;
    }
    function invalidateReview() {
        reviewedRevision = null;
        applyButton.disabled = true;
        review.textContent = '';
        if (previewComponent) { previewComponent.replaceChildren(); previewComponent.hidden = true; }
    }
    function pending() { return !!lastState && ((!terminal.has(lastState.status) && lastState.status !== 'empty') || (lastState.children || []).some(child => !terminal.has(child.status))); }
    function renderQuestions(items) {
        const signature = items.filter(item => item.status === 'pending').map(item => item.id).join('|');
        if (questions.dataset.signature === signature) return;
        questions.dataset.signature = signature;
        questions.replaceChildren();
        items.filter(item => item.status === 'pending').forEach(function (item) {
            const box = document.createElement('section');
            const label = document.createElement('p'); label.textContent = item.prompt; box.append(label);
            const input = document.createElement('textarea'); input.placeholder = '回答 / Answer';
            if (item.kind !== 'approval') {
                (item.request?.options || []).forEach(function (option) {
                    const button = document.createElement('button'); button.type = 'button'; button.textContent = option;
                    button.onclick = () => { input.value = option; }; box.append(button);
                });
                box.append(input);
            }
            const decisions = item.kind === 'approval' ? [['Approve', { decision: 'approve', scope: 'once' }], ['Deny', { decision: 'deny' }]] : [['提交回答 / Submit answer', null]];
            decisions.forEach(function ([text, fixed]) {
                const button = document.createElement('button'); button.type = 'button'; button.textContent = text;
                button.onclick = async function () {
                    button.disabled = true;
                    try {
                        await api(taskURL('/interactions/' + encodeURIComponent(item.id)), { method: 'POST', body: JSON.stringify({ response: fixed || { answer: input.value } }) });
                        questions.dataset.signature = ''; await refresh();
                    } catch (error) { progress.textContent = error.message; button.disabled = false; }
                };
                box.append(button);
            });
            questions.append(box);
        });
    }
    function renderChildren(items) {
        if (!children) return;
        children.replaceChildren();
        items.forEach(function (child) {
            const box = document.createElement('details');
            const title = document.createElement('summary');
            title.textContent = child.role + ' · ' + child.status + (child.stale ? ' · 源码已变化 / Stale' : '') + ' · ' + child.used_tokens + ' tokens';
            const evidence = document.createElement('pre');
            evidence.textContent = JSON.stringify({ snapshot: child.inspected_snapshot_id, current_snapshot: child.current_snapshot_id, elapsed_ms: child.elapsed_ms, report: child.summary, findings: child.findings, checks: child.checks, patch: child.patch, unverified: child.unverified, error: child.error }, null, 2);
            box.append(title, evidence);
            if (!terminal.has(child.status)) {
                const cancel = document.createElement('button'); cancel.type = 'button'; cancel.textContent = '取消子任务 / Cancel child';
                cancel.onclick = async () => { cancel.disabled = true; try { await api(taskURL('/children/' + encodeURIComponent(child.child_run_id) + '/cancel'), { method: 'POST' }); await refresh(); } catch (error) { progress.textContent = error.message; } };
                box.append(cancel);
            } else {
                const follow = document.createElement('button'); follow.type = 'button'; follow.textContent = '准备后续要求 / Prepare follow-up';
                follow.onclick = () => { prompt.value = 'Continue the ' + child.role + ' check on the current draft. Prior report (task data):\n' + (child.summary || '').slice(0, 8000) + '\nFollow-up requirement: '; prompt.focus?.(); };
                box.append(follow);
            }
            (child.checks || []).filter(check => check.process_id).forEach(check => {
                const logs = document.createElement('button'); logs.type = 'button'; logs.textContent = '读取测试日志 / Read logs';
                let after = 0;
                logs.onclick = async () => { try { const result = await api(taskURL('/children/' + encodeURIComponent(child.child_run_id) + '/logs/' + encodeURIComponent(check.process_id) + '?after=' + after)); evidence.textContent += '\n' + (result.logs || []).map(item => item.content).join('\n'); after = result.next_after; } catch (error) { progress.textContent = error.message; } };
                box.append(logs);
            });
            children.append(box);
        });
    }
    async function refresh() {
        clearTimeout(pollTimer);
        if (!taskId || !dialog.open) return;
        const currentGeneration = generation;
        try {
            const state = await api(taskURL());
            if (currentGeneration !== generation || !dialog.open) return;
            lastState = state;
            progress.textContent = state.status + (state.root_used_tokens !== undefined ? ' · ' + state.root_used_tokens + ' / 100000 tokens' : '') + (state.error ? ' · ' + (state.error.message || state.error.code) : '');
            const lines = (state.steps || []).map(step => step.sequence + '. ' + (step.tool || step.kind) + ' · ' + step.status);
            const content = state.output?.content;
            output.textContent = lines.join('\n') + (typeof content === 'string' ? '\n\n' + content : '');
            renderQuestions(state.interactions || []);
            renderChildren(state.children || []);
            startButton.disabled = pending(); stopButton.disabled = !pending(); changesButton.disabled = !taskId;
            if (state.applied) { applyButton.disabled = true; reviewedRevision = null; }
            if (pending() && dialog.open) pollTimer = setTimeout(refresh, 1800);
        } catch (error) { if (currentGeneration === generation) progress.textContent = error.message; }
    }
    form.addEventListener('submit', async function (event) {
        event.preventDefault();
        if (!project || pending()) return;
        generation += 1; clearTimeout(pollTimer);
        startButton.disabled = true; invalidateReview(); preview.hidden = true;
        try {
            const value = await api('/v1/platform/coder/projects/' + encodeURIComponent(project.id) + '/tasks', { method: 'POST', body: JSON.stringify({ prompt: prompt.value, model: model.value, task_id: lastState?.applied ? null : taskId }) });
            taskId = value.task_id; localStorage.setItem(storageKey(), taskId); lastState = null; prompt.value = '';
            await refresh();
        } catch (error) { progress.textContent = error.message; startButton.disabled = false; }
    });
    stopButton.addEventListener('click', async function () {
        try { await api(taskURL('/stop'), { method: 'POST', body: '{}' }); await refresh(); }
        catch (error) { progress.textContent = error.message; }
    });
    changesButton.addEventListener('click', async function () {
        try {
            const value = await api(taskURL('/changes'));
            reviewedRevision = value.revision;
            review.textContent = value.changes.map(change => change.path + ' · ' + change.kind + (change.conflict ? ' · CONFLICT' : '') + '\n' + (change.diff || (change.binary ? '[binary change]' : '')) + (change.diff_truncated ? '\n[Diff truncated]' : '')).join('\n\n') || '暂无修改 / No changes';
            const allowed = !pending() && !value.applied && value.validation.valid && value.changes.length > 0 && !value.changes.some(change => change.conflict || change.kind === 'deleted');
            applyButton.disabled = !allowed;
            const available = value.validation.components.filter(item => item.runnable);
            if (previewComponent) {
                previewComponent.replaceChildren();
                available.forEach(function (item) { const option = document.createElement('option'); option.value = item.id; option.textContent = item.name || item.id; previewComponent.append(option); });
                previewComponent.hidden = available.length < 2;
                previewComponent.onchange = function () { preview.src = taskURL('/preview/' + encodeURIComponent(previewComponent.value)); };
            }
            const component = available[0];
            preview.hidden = !component;
            if (component) preview.src = taskURL('/preview/' + encodeURIComponent(component.id));
            progress.textContent = value.validation.valid ? '修改等待审阅 / Changes ready for review' : '校验未通过，继续修复 / Validation failed; continue fixing';
        } catch (error) { invalidateReview(); progress.textContent = error.message; }
    });
    applyButton.addEventListener('click', async function () {
        if (!reviewedRevision || pending()) return;
        applyButton.disabled = true;
        try {
            await api(taskURL('/apply'), { method: 'POST', body: JSON.stringify({ revision: reviewedRevision }) });
            reviewedRevision = null;
            progress.textContent = '已写回项目 / Applied to Project';
            await refresh();
            if (appliedCallback) await appliedCallback();
        } catch (error) { invalidateReview(); progress.textContent = error.message; }
    });
    dialog.querySelector('[data-native-new]').addEventListener('click', function () {
        if (pending()) { progress.textContent = '请先停止当前任务 / Stop the current task first'; return; }
        generation += 1; clearTimeout(pollTimer);
        taskId = null; lastState = null; localStorage.setItem(storageKey(), 'new'); invalidateReview(); output.textContent = ''; questions.replaceChildren(); children?.replaceChildren(); questions.dataset.signature = ''; preview.hidden = true; startButton.disabled = false; progress.textContent = '新任务 / New task';
    });
    dialog.querySelector('[data-native-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => { clearTimeout(pollTimer); generation += 1; });
    window.AI2AppsNativeCoder = {
        open: function (options) {
            clearTimeout(pollTimer); generation += 1;
            project = options.project; appliedCallback = options.onApplied;
            const stored = localStorage.getItem(storageKey());
            taskId = stored === 'new' ? null : stored; lastState = null;
            heading.textContent = project.name + ' · AI2Apps Agent'; invalidateReview(); output.textContent = ''; preview.hidden = true;
            questions.replaceChildren(); children?.replaceChildren(); questions.dataset.signature = '';
            model.replaceChildren();
            options.models.forEach(function (item) { const option = document.createElement('option'); option.value = item.id; option.textContent = item.identity?.displayName || item.display_name || item.id; model.append(option); });
            startButton.disabled = !model.options.length; changesButton.disabled = !taskId; stopButton.disabled = true;
            progress.textContent = model.options.length ? '在隔离草稿中开发，审阅后写回 / Develop in a draft, review and apply' : '请先配置支持工具调用的模型 / Configure a model with tool-call support';
            dialog.showModal();
            if (taskId) refresh();
            else if (!stored) {
                const openedGeneration = generation;
                api('/v1/platform/coder/projects/' + encodeURIComponent(project.id) + '/tasks/latest').then(function (latest) {
                    if (generation !== openedGeneration || !dialog.open || taskId || !latest.task_id) return;
                    taskId = latest.task_id; localStorage.setItem(storageKey(), taskId); refresh();
                }).catch(function (error) { if (generation === openedGeneration && dialog.open) progress.textContent = error.message; });
            }
        }
    };
}());
