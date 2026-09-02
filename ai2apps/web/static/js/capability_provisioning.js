(function () {
    'use strict';

    const API = '/v1/platform';
    const terminal = new Set(['ready', 'failed', 'cancelled', 'unsupported']);
    const labels = {
        awaiting_confirmation: '等待确认', installing_runtime: '正在安装推理 Runtime',
        awaiting_restart: '需要重启本地服务', installing_provider: '正在安装能力 Package',
        downloading_checkpoint: '正在下载模型 Checkpoint', activating: '正在启动模型服务',
        verifying: '正在验证能力', ready: '配置完成', failed: '配置失败', cancelled: '已取消',
    };
    const defaultPresentation = {
        eyebrow: 'AI2APPS CAPABILITY SETUP',
        title: '配置 AI 能力',
        description: '根据当前设备安装并验证可信的 Runtime、能力服务和必要模型。',
        icon: 'sparkles',
        confirm_label: '下载并配置',
        ready_label: '能力配置完成',
    };

    function formatBytes(value) {
        const bytes = Math.max(0, Number(value) || 0);
        if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
        if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${Math.round(bytes)} B`;
    }

    function appInstanceId() {
        return new URLSearchParams(window.location.hash.replace(/^#/, '')).get('ai2apps-instance') || '';
    }

    async function payload(response) {
        const value = await response.json().catch(() => null);
        if (!response.ok) {
            const detail = value?.detail;
            throw new Error(detail?.message || detail || value?.error?.message || `请求失败 (${response.status})`);
        }
        return value;
    }

    function request(url, options = {}) {
        const instanceId = appInstanceId();
        const suppliedHeaders = options.headers || {};
        return fetch(API + url, {
            ...options,
            credentials: 'same-origin',
            headers: {
                Accept: 'application/json',
                ...(instanceId ? { 'X-AI2Apps-App-Instance': instanceId } : {}),
                ...(options.body ? { 'Content-Type': 'application/json' } : {}),
                ...suppliedHeaders,
            },
        }).then(payload);
    }

    function storageKey(appId) { return `ai2apps.acpf.pending.${appId}`; }
    function savePending(value) {
        localStorage.setItem(storageKey(value.appId), JSON.stringify({
            sessionId: value.sessionId,
            appId: value.appId,
            resumeToken: value.resumeToken || null,
        }));
    }
    function clearPending(appId) { localStorage.removeItem(storageKey(appId)); }
    function completion(session) {
        const policy = session.intent?.completionPolicy || 'configure_only';
        return {
            policy,
            shouldResumeAction: policy === 'resume_action',
            idempotencyKey: policy === 'resume_action' ? session.intent?.idempotencyKey || null : null,
        };
    }
    function configuredResult(session) {
        return {
            status: 'ready',
            outcome: 'configured',
            provider: session.plan?.provider,
            session,
            completion: completion(session),
        };
    }
    async function acknowledge(sessionOrId, { appId, idempotencyKey } = {}) {
        const sessionId = typeof sessionOrId === 'string' ? sessionOrId : sessionOrId?.id;
        if (!sessionId) throw new Error('Provisioning session id is required');
        await request(`/provisioning/sessions/${sessionId}/acknowledge-return`, {
            method: 'POST',
            body: JSON.stringify(idempotencyKey ? { idempotencyKey } : {}),
        });
        if (appId) clearPending(appId);
    }

    function chooseProfile(plan) {
        const options = plan?.profileOptions || [];
        if (options.length === 0) return Promise.resolve(plan?.profileId || null);
        const compatible = options.filter(option => option.compatible);
        if (compatible.length === 0) {
            return Promise.reject(new Error('当前设备没有可运行的配置档位'));
        }
        const multiple = plan?.selectionMode === 'multiple';
        const initial = compatible.filter(option => option.selected);
        const fallback = compatible.find(option => option.recommended) || compatible[0];
        const selectedIds = new Set((initial.length ? initial : [fallback]).map(option => option.profileId));
        const presentation = { ...defaultPresentation, ...(plan.presentation || {}) };
        const memory = Math.round(plan.device?.system_memory_gib || 0);
        const overlay = document.createElement('div');
        overlay.className = 'acpf-overlay acpf-choice-overlay';
        overlay.innerHTML = '<section class="acpf-sheet acpf-choice-sheet" role="dialog" aria-modal="true" aria-labelledby="acpf-choice-title">' +
            '<div class="acpf-choice-header"><div class="acpf-mark"><i></i></div><div class="acpf-heading"><span>AI2APPS CAPABILITY CHOICE</span><h2 id="acpf-choice-title"></h2>' +
            '<p class="acpf-choice-description"></p></div><div class="acpf-device"></div>' +
            '<p class="acpf-choice-note"></p></div>' +
            '<div class="acpf-tiers"></div><div class="acpf-actions acpf-choice-actions"><button type="button" data-choice-action="cancel" class="acpf-secondary">取消</button>' +
            '<button type="button" data-choice-action="continue" class="acpf-primary"></button></div></section>';
        document.body.appendChild(overlay);
        overlay.querySelector('#acpf-choice-title').textContent = multiple ? '选择要安装的模型' : '选择配置档位';
        overlay.querySelector('.acpf-choice-description').textContent = presentation.description;
        overlay.querySelector('.acpf-choice-note').textContent = multiple
            ? '已根据当前设备勾选推荐模型。你可以同时选择多个兼容模型；继续后将合并为一次 ACPF 配置与下载确认。'
            : '推荐项已根据当前设备选中。你可以选择其它兼容档位；继续后才会进入 ACPF 配置与下载确认。';
        overlay.querySelector('.acpf-device').textContent = `${plan.device?.accelerator?.vendor || '本地'} ${plan.device?.accelerator?.api || '设备'} · ${memory} GiB`;
        const mark = overlay.querySelector('.acpf-mark i'); mark.setAttribute('data-lucide', presentation.icon);
        const tiers = overlay.querySelector('.acpf-tiers');
        const draw = () => {
            tiers.replaceChildren();
            for (const option of options) {
                const wrapper = document.createElement('div'); wrapper.className = 'acpf-tier-wrap';
                const button = document.createElement('button'); button.type = 'button';
                button.dataset.choiceProfileId = option.profileId;
                button.disabled = !option.compatible;
                const selected = selectedIds.has(option.profileId);
                button.setAttribute('aria-pressed', selected ? 'true' : 'false');
                button.className = 'acpf-tier' + (selected ? ' selected' : '') + (!option.compatible ? ' unavailable' : '');
                if (multiple) {
                    const check = document.createElement('span'); check.className = 'acpf-tier-check';
                    check.textContent = selected ? '✓' : ''; button.append(check);
                }
                const copy = document.createElement('span'); copy.className = 'acpf-tier-copy';
                const name = document.createElement('strong'); name.textContent = option.label;
                const detail = document.createElement('small');
                detail.textContent = option.compatible
                    ? (option.description || option.modelId || '')
                    : (option.disabledReasons || []).join(' · ');
                copy.append(name, detail); button.append(copy);
                if (option.recommended) {
                    const badge = document.createElement('em'); badge.textContent = '推荐'; button.append(badge);
                } else if (selected) {
                    const badge = document.createElement('em'); badge.textContent = '已选择'; button.append(badge);
                }
                wrapper.title = (option.disabledReasons || []).join(' · ');
                wrapper.append(button); tiers.append(wrapper);
            }
            const proceed = overlay.querySelector('[data-choice-action="continue"]');
            proceed.disabled = selectedIds.size === 0;
            proceed.textContent = multiple ? `安装所选 ${selectedIds.size} 个模型` : '使用所选档位继续';
            window.lucide?.createIcons();
        };
        draw();
        return new Promise((resolve, reject) => {
            let settled = false;
            const finish = (error, value) => {
                if (settled) return; settled = true; overlay.remove();
                if (error) reject(error); else resolve(value);
            };
            overlay.addEventListener('click', event => {
                const profileId = event.target.closest('[data-choice-profile-id]')?.dataset.choiceProfileId;
                if (profileId) {
                    const option = options.find(item => item.profileId === profileId);
                    if (option?.compatible) {
                        if (multiple) {
                            if (selectedIds.has(profileId)) selectedIds.delete(profileId);
                            else selectedIds.add(profileId);
                        } else {
                            selectedIds.clear(); selectedIds.add(profileId);
                        }
                        draw();
                    }
                    return;
                }
                const action = event.target.closest('[data-choice-action]')?.dataset.choiceAction;
                if (action === 'cancel') finish(new Error('已取消能力配置'));
                if (action === 'continue' && selectedIds.size > 0) {
                    finish(null, multiple ? Array.from(selectedIds) : Array.from(selectedIds)[0]);
                }
            });
        });
    }

    async function confirmLicenseChallenges(challenges) {
        const consents = [];
        for (const challenge of challenges || []) {
            const license = challenge.license || {};
            const overlay = document.createElement('div');
            overlay.className = 'acpf-overlay acpf-license-overlay';
            overlay.innerHTML = '<section class="acpf-sheet acpf-license-sheet" role="dialog" aria-modal="true" aria-labelledby="acpf-license-title">' +
                '<div class="acpf-heading"><span>CHECKPOINT LICENSE</span><h2 id="acpf-license-title"></h2>' +
                '<p class="acpf-license-usage"></p></div><div class="acpf-license-terms"></div>' +
                '<a class="acpf-license-link" target="_blank" rel="noopener noreferrer">查看完整许可条款</a>' +
                '<p class="acpf-license-attribution"></p><fieldset class="acpf-license-options"></fieldset>' +
                '<label class="acpf-license-confirm"><input type="checkbox"> <span></span></label>' +
                '<div class="acpf-actions"><button type="button" data-license-action="cancel" class="acpf-secondary">取消</button>' +
                '<button type="button" data-license-action="accept" class="acpf-primary" disabled>确认许可并继续下载</button></div></section>';
            document.body.appendChild(overlay);
            overlay.querySelector('#acpf-license-title').textContent = license.name || '模型许可确认';
            overlay.querySelector('.acpf-license-usage').textContent = `用途限制：${license.usagePolicy || '以许可条款为准'}`;
            const terms = overlay.querySelector('.acpf-license-terms');
            terms.textContent = license.termsText || '完整许可文本由签名 envelope 中的固定条款 URL 与 SHA-256 绑定。';
            const link = overlay.querySelector('.acpf-license-link');
            link.href = license.termsUrl || '#';
            link.hidden = !license.termsUrl;
            const attribution = license.redistributionConditions?.attribution?.noticeText;
            const attributionNode = overlay.querySelector('.acpf-license-attribution');
            attributionNode.textContent = attribution ? `必要署名：${attribution}` : '';
            attributionNode.hidden = !attribution;
            const options = overlay.querySelector('.acpf-license-options');
            const optionLabels = {
                accepted_license_terms: '我接受上述许可条款，并将在许可允许的用途范围内使用',
                obtained_separate_license: '我已为预期用途取得权利方的单独许可或授权',
            };
            for (const [index, option] of (challenge.acceptanceOptions || []).entries()) {
                const label = document.createElement('label');
                const input = document.createElement('input');
                input.type = 'radio'; input.name = `license-decision-${challenge.distributionId}`;
                input.value = option; input.checked = index === 0;
                const text = document.createElement('span'); text.textContent = optionLabels[option] || option;
                label.append(input, text); options.append(label);
            }
            const checkbox = overlay.querySelector('.acpf-license-confirm input');
            overlay.querySelector('.acpf-license-confirm span').textContent = challenge.attestationText || '我确认已同意或获得所需许可。';
            const accept = overlay.querySelector('[data-license-action="accept"]');
            checkbox.addEventListener('change', () => { accept.disabled = !checkbox.checked; });
            const consent = await new Promise((resolve, reject) => {
                overlay.addEventListener('click', event => {
                    const action = event.target.closest('[data-license-action]')?.dataset.licenseAction;
                    if (action === 'cancel') reject(new Error('未确认模型许可，Checkpoint 不会开始下载'));
                    if (action === 'accept' && checkbox.checked) {
                        const decision = overlay.querySelector('input[type="radio"]:checked')?.value;
                        if (!decision) return;
                        resolve({
                            distributionId: challenge.distributionId,
                            manifestDigest: challenge.manifestDigest,
                            termsHash: license.termsHash,
                            decision,
                            confirmed: true,
                        });
                    }
                });
            }).finally(() => overlay.remove());
            consents.push(consent);
        }
        return consents;
    }

    function sheet(session) {
        const overlay = document.createElement('div');
        overlay.className = 'acpf-overlay';
        overlay.innerHTML = '<section class="acpf-sheet" role="dialog" aria-modal="true" aria-labelledby="acpf-title">' +
            '<div class="acpf-mark"><i></i></div><div class="acpf-heading"><span class="acpf-eyebrow"></span><h2 id="acpf-title"></h2><p class="acpf-description"></p><p class="acpf-reason"></p></div>' +
            '<div class="acpf-device"></div><div class="acpf-selected-tier"></div><ol class="acpf-steps"></ol><div class="acpf-progress"><i></i></div>' +
            '<p class="acpf-status"></p><div class="acpf-download-detail" hidden><strong></strong><div class="acpf-download-progress"><i></i></div><p></p><small hidden></small></div>' +
            '<p class="acpf-error" hidden></p><div class="acpf-actions">' +
            '<button type="button" data-action="cancel" class="acpf-secondary">取消</button>' +
            '<button type="button" data-action="confirm" class="acpf-primary">下载并配置</button>' +
            '<button type="button" data-action="restart" class="acpf-primary" hidden>重启本地服务</button>' +
            '<button type="button" data-action="retry" class="acpf-primary" hidden>重试</button></div></section>';
        document.body.appendChild(overlay);
        render(overlay, session);
        return overlay;
    }

    function render(overlay, session) {
        const plan = session.plan || {};
        const presentation = { ...defaultPresentation, ...(plan.presentation || {}) };
        const memory = Math.round(plan.device?.system_memory_gib || 0);
        overlay.querySelector('.acpf-eyebrow').textContent = presentation.eyebrow;
        overlay.querySelector('#acpf-title').textContent = presentation.title;
        overlay.querySelector('.acpf-description').textContent = presentation.description;
        // Lucide replaces the original <i> with an <svg> after the first
        // render.  ACPF polls and renders the same sheet repeatedly, so only
        // initialise the icon while the placeholder still exists.
        const mark = overlay.querySelector('.acpf-mark i');
        if (mark) mark.setAttribute('data-lucide', presentation.icon);
        overlay.querySelector('.acpf-reason').textContent = (plan.reasons || []).join(' · ');
        overlay.querySelector('.acpf-device').textContent = `${plan.device?.accelerator?.vendor || '本地'} ${plan.device?.accelerator?.api || '设备'} · ${memory} GiB · ${plan.profileId || ''}`;
        const options = plan.profileOptions || [];
        const selected = options.filter(option => option.selected);
        const selection = overlay.querySelector('.acpf-selected-tier');
        selection.hidden = selected.length === 0;
        selection.replaceChildren();
        if (selected.length > 0) {
            const label = document.createElement('span'); label.textContent = selected.length > 1 ? `已选择 ${selected.length} 个模型` : '已选择档位';
            const name = document.createElement('strong'); name.textContent = selected.map(option => option.label).join('、');
            selection.append(label, name);
        }
        const list = overlay.querySelector('.acpf-steps'); list.replaceChildren();
        for (const step of plan.steps || []) {
            const item = document.createElement('li');
            const complete = step.status === 'complete' || session.status === 'ready';
            item.className = complete ? 'complete' : '';
            const dot = document.createElement('i');
            const content = document.createElement('span');
            const title = document.createElement('strong'); title.textContent = step.title;
            const detail = document.createElement('small'); detail.textContent = step.modelId || `${step.packageId || ''} ${step.requiredVersion || ''}`;
            content.append(title, detail); item.append(dot, content); list.append(item);
        }
        const percent = Math.max(0, Math.min(100, Number(session.progress?.percent || 0)));
        overlay.querySelector('.acpf-progress i').style.width = `${percent}%`;
        overlay.querySelector('.acpf-status').textContent = `${labels[session.status] || session.status} · ${Math.round(percent)}%`;
        const progressDetail = session.progress?.detail || {};
        const bytesCompleted = Number(progressDetail.bytesCompleted ?? progressDetail.bytes_completed ?? 0);
        const bytesTotal = Number(progressDetail.bytesTotal ?? progressDetail.bytes_total ?? 0);
        const totalBytesCompleted = Number(progressDetail.totalBytesCompleted ?? progressDetail.total_bytes_completed ?? bytesCompleted);
        const totalBytesTotal = Number(progressDetail.totalBytesTotal ?? progressDetail.total_bytes_total ?? bytesTotal);
        const currentFile = progressDetail.fileName || progressDetail.current_file || progressDetail.packageId || progressDetail.model_id || '';
        const itemPercent = bytesTotal > 0 ? Math.max(0, Math.min(100, bytesCompleted / bytesTotal * 100)) : 0;
        const downloadDetail = overlay.querySelector('.acpf-download-detail');
        downloadDetail.hidden = !(currentFile && bytesTotal > 0 && ['installing_runtime', 'installing_provider', 'downloading_checkpoint'].includes(session.status));
        downloadDetail.querySelector('strong').textContent = currentFile;
        downloadDetail.querySelector('.acpf-download-progress i').style.width = `${itemPercent}%`;
        downloadDetail.querySelector('p').textContent = `当前项目 ${Math.round(itemPercent)}% · ${formatBytes(bytesCompleted)} / ${formatBytes(bytesTotal)}`;
        const totalDetail = downloadDetail.querySelector('small');
        totalDetail.hidden = !(totalBytesTotal > bytesTotal);
        totalDetail.textContent = `本次下载总计 ${Math.round(totalBytesCompleted / totalBytesTotal * 100)}% · ${formatBytes(totalBytesCompleted)} / ${formatBytes(totalBytesTotal)}`;
        const error = overlay.querySelector('.acpf-error');
        error.hidden = !session.error; error.textContent = session.error?.message || '';
        overlay.querySelector('[data-action="confirm"]').hidden = session.status !== 'awaiting_confirmation';
        overlay.querySelector('[data-action="confirm"]').textContent = session.error?.code === 'checkpoint_license_consent_required'
            ? '查看并确认模型许可'
            : presentation.confirm_label;
        overlay.querySelector('[data-action="restart"]').hidden = session.status !== 'awaiting_restart';
        overlay.querySelector('[data-action="retry"]').hidden = session.status !== 'failed';
        overlay.querySelector('[data-action="cancel"]').hidden = session.status === 'ready';
        if (session.status === 'ready') {
            overlay.querySelector('.acpf-status').textContent = presentation.ready_label;
        }
        window.lucide?.createIcons();
    }

    async function runSession(initial, appId) {
        let session = initial;
        const overlay = sheet(session);
        return new Promise((resolve, reject) => {
            let stopped = false;
            const finish = (error, value) => {
                if (stopped) return; stopped = true; overlay.remove();
                if (error) reject(error); else resolve(value);
            };
            overlay.addEventListener('click', async event => {
                const action = event.target.closest('[data-action]')?.dataset.action;
                if (!action) return;
                try {
                    if (action === 'cancel') {
                        if (!terminal.has(session.status)) await request(`/provisioning/sessions/${session.id}/cancel`, { method: 'POST' });
                        clearPending(appId); finish(new Error('已取消能力配置')); return;
                    }
                    if (action === 'confirm' || action === 'retry') {
                        const challenges = session.error?.code === 'checkpoint_license_consent_required'
                            ? session.error?.challenges || []
                            : [];
                        const licenseConsents = challenges.length
                            ? await confirmLicenseChallenges(challenges)
                            : [];
                        session = await request(`/provisioning/sessions/${session.id}/${action}`, {
                            method: 'POST',
                            body: JSON.stringify({ licenseConsents }),
                        });
                    } else if (action === 'restart') {
                        overlay.querySelector('[data-action="restart"]').disabled = true;
                        await request('/client/restart-local', { method: 'POST' }).catch(error => {
                            if (!(error instanceof TypeError)) throw error;
                        });
                    }
                    render(overlay, session);
                } catch (error) {
                    const node = overlay.querySelector('.acpf-error'); node.hidden = false; node.textContent = error.message;
                }
            });
            (async function poll() {
                while (!stopped) {
                    if (session.status === 'ready') {
                        finish(null, configuredResult(session)); return;
                    }
                    if (session.status === 'cancelled' || session.status === 'unsupported') {
                        clearPending(appId); finish(new Error(labels[session.status] || session.status)); return;
                    }
                    await new Promise(done => setTimeout(done, 1000));
                    try {
                        const polledSessionId = session.id;
                        const polled = await request(`/provisioning/sessions/${polledSessionId}`);
                        if (session.id !== polledSessionId) continue;
                        session = polled;
                        savePending({ sessionId: session.id, appId, resumeToken: session.intent?.resumeToken }); render(overlay, session);
                    } catch (_) {
                        overlay.querySelector('.acpf-status').textContent = '本地服务正在重启，等待重新连接…';
                    }
                }
            })();
        });
    }

    async function ensure(body) {
        const probed = await probe(body);
        if (probed.status === 'ready') {
            clearPending(body.appId);
            return { ...probed, outcome: 'already_ready' };
        }
        if (probed.status === 'unsupported') throw new Error('当前设备不支持此能力');
        const profileSelection = await chooseProfile(probed.plan);
        const requestBody = {
            ...body,
            appInstanceId: appInstanceId(),
            requirements: {
                ...(body.requirements || {}),
                ...(Array.isArray(profileSelection)
                    ? { profileIds: profileSelection }
                    : (profileSelection ? { profileId: profileSelection } : {})),
            },
        };
        const result = await request('/capabilities/ensure', { method: 'POST', body: JSON.stringify(requestBody) });
        if (result.status === 'ready') {
            clearPending(body.appId);
            return { ...result, outcome: 'already_ready' };
        }
        if (result.status === 'unsupported') throw new Error((result.reasons || ['当前设备不支持此能力']).join('；'));
        savePending({ sessionId: result.sessionId, appId: body.appId, resumeToken: result.session?.intent?.resumeToken });
        return runSession(result.session, body.appId);
    }

    async function resume(appId, { capability } = {}) {
        let pending = null;
        try { pending = JSON.parse(localStorage.getItem(storageKey(appId)) || 'null'); } catch (_) { clearPending(appId); }
        if (!pending?.sessionId) {
            const sessions = await request('/provisioning/sessions');
            const session = (sessions.items || []).find(item =>
                item.appId === appId
                && item.appInstanceId === appInstanceId()
                && (!capability || item.capability === capability)
            );
            if (!session) return null;
            pending = {
                sessionId: session.id,
                appId: session.appId,
                resumeToken: session.intent?.resumeToken || null,
            };
            savePending(pending);
        }
        try {
            const session = await request(`/provisioning/sessions/${pending.sessionId}`);
            if (capability && session.capability !== capability) return null;
            if (session.status === 'ready') {
                return configuredResult(session);
            }
            return runSession(session, appId);
        } catch (error) { clearPending(appId); throw error; }
    }

    function probe(body) {
        return request('/capabilities/probe', {
            method: 'POST',
            body: JSON.stringify({ ...body, appInstanceId: appInstanceId() }),
        });
    }

    window.AI2AppsCapabilities = { ensure, resume, probe, acknowledge, appInstanceId };
})();
