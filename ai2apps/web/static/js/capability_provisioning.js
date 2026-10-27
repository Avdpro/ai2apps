(function () {
    'use strict';


    // Catalogs are supplied by the host's existing locale system.
    function tr(source, ...values) {
        if (typeof source !== 'string') return source || '';
        let key = source;
        // Legacy plans persist concrete device messages; normalize their values.
        const patterns = [
            [/^安装 (.+)$/, '安装 {0}'],
            [/^匹配 (\S+) (\S+) 设备$/, '匹配 {0} {1} 设备'],
            [/^统一内存约 (\S+) GiB$/, '统一内存约 {0} GiB'],
            [/^App 推荐方案：(.*)$/, 'App 推荐方案：{0}'],
            [/^至少需要 (\S+) GiB 统一内存$/, '至少需要 {0} GiB 统一内存'],
            [/^仅支持低于 (\S+) GiB 统一内存的设备$/, '仅支持低于 {0} GiB 统一内存的设备'],
        ];
        for (const [pattern, normalized] of patterns) {
            // Exact phrases (e.g. the install button) take precedence over dynamic titles.
            if (window._t?.['acpf.' + source] !== undefined) break;
            const match = source.match(pattern);
            if (match) { key = normalized; values = match.slice(1); break; }
        }
        const translated = window._t?.['acpf.' + key] ?? source;
        return translated.replace(/\{(\d+)\}/g, (match, index) => values[index] ?? match);
    }

    const API = '/v1/platform';
    const terminal = new Set(['ready', 'failed', 'cancelled', 'unsupported']);
    // A host reconnect can cause an App's startup recovery to ask for the same
    // durable Session more than once. Share one runner per Session so repeated
    // resume/ensure calls cannot create competing pollers and duplicate sheets.
    const activeRuns = window.__AI2AppsCapabilityActiveRuns || new Map();
    window.__AI2AppsCapabilityActiveRuns = activeRuns;
    const labels = {
        awaiting_confirmation: tr('等待确认'), installing_runtime: tr('正在安装推理 Runtime'),
        awaiting_restart: tr('需要重启本地服务'), installing_provider: tr('正在安装能力 Package'),
        downloading_checkpoint: tr('正在下载模型 Checkpoint'), activating: tr('正在启动模型服务'),
        verifying: tr('正在验证能力'), ready: tr('配置完成'), failed: tr('配置失败'), cancelled: tr('已取消'),
    };
    const defaultPresentation = {
        eyebrow: 'AI2APPS CAPABILITY SETUP',
        title: tr('配置 AI 能力'),
        description: tr('根据当前设备安装并验证可信的 Runtime、能力服务和必要模型。'),
        icon: 'sparkles',
        confirm_label: tr('下载并配置'),
        ready_label: tr('能力配置完成'),
    };

    function formatBytes(value) {
        const bytes = Math.max(0, Number(value) || 0);
        if (bytes >= 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
        if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${Math.round(bytes)} B`;
    }

    function createTransferMeter() {
        let identity = null;
        let samples = [];
        return (key, completed, total, now = performance.now()) => {
            completed = Math.max(0, Number(completed) || 0);
            total = Math.max(0, Number(total) || 0);
            if (identity !== key || completed < (samples.at(-1)?.bytes ?? 0)) {
                identity = key;
                samples = [];
            }
            samples.push({ time: now, bytes: completed });
            while (samples.length > 2 && samples[1].time <= now - 5000) samples.shift();
            const elapsed = (now - samples[0].time) / 1000;
            const speed = elapsed >= 0.25 ? (completed - samples[0].bytes) / elapsed : null;
            const remaining = total > completed && speed > 0 ? Math.ceil((total - completed) / speed) : null;
            const eta = remaining === null ? '—' : [Math.floor(remaining / 3600), Math.floor(remaining / 60) % 60, remaining % 60]
                .map(value => String(value).padStart(2, '0')).join(':');
            return `${speed === null ? '—' : formatBytes(speed) + '/s'} · ETA ${eta}`;
        };
    }

    function formatDownloadProgress(download, active = true, now = Date.now()) {
        if (!download) return '';
        const stale = active && now / 1000 - Number(download.sampledAt || 0) > 5;
        const speed = stale ? 0 : download.bytesPerSecond;
        const speedText = speed == null ? '—' : `${formatBytes(speed)}/s`;
        if (!active) return tr('最近下载：{0} / {1} · 最近速度 {2}',
            formatBytes(download.bytesCompleted), formatBytes(download.bytesTotal), speedText);
        const seconds = stale ? null : download.etaSeconds;
        const eta = seconds == null ? '—' : [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60]
            .map(value => String(value).padStart(2, '0')).join(':');
        return tr('下载速度 {0} · ETA {1}', speedText, eta);
    }

    function appInstanceId() {
        return new URLSearchParams(window.location.hash.replace(/^#/, '')).get('ai2apps-instance') || '';
    }

    async function payload(response) {
        const value = await response.json().catch(() => null);
        if (!response.ok) {
            const detail = value?.detail;
            throw new Error(detail?.message || detail || value?.error?.message || tr('请求失败 ({0})', response.status));
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
        const options = (plan?.profileOptions || []).map((option, index) => ({ ...option, __order: index }))
            .sort((left, right) => Number(Boolean(left.deprecated)) - Number(Boolean(right.deprecated)) || left.__order - right.__order);
        if (options.length === 0) return Promise.resolve(plan?.profileId || null);
        const compatible = options.filter(option => option.compatible && !(plan.installMore && option.installed));
        if (compatible.length === 0 && !plan.installMore) {
            return Promise.reject(new Error(tr('当前设备没有可运行的配置档位')));
        }
        const multiple = plan?.selectionMode === 'multiple';
        const initial = compatible.filter(option => option.selected);
        const fallback = compatible.find(option => option.recommended && !option.deprecated)
            || compatible.find(option => !option.deprecated);
        const selectedIds = new Set((initial.length ? initial : (fallback ? [fallback] : [])).map(option => option.profileId));
        const presentation = { ...defaultPresentation, ...(plan.presentation || {}) };
        const memory = Math.round(plan.device?.system_memory_gib || 0);
        const overlay = document.createElement('div');
        overlay.className = 'acpf-overlay acpf-choice-overlay';
        overlay.innerHTML = '<section class="acpf-sheet acpf-choice-sheet" role="dialog" aria-modal="true" aria-labelledby="acpf-choice-title">' +
            '<div class="acpf-choice-header"><div class="acpf-mark"><i></i></div><div class="acpf-heading"><span>AI2APPS CAPABILITY CHOICE</span><h2 id="acpf-choice-title"></h2>' +
            '<p class="acpf-choice-description"></p></div><div class="acpf-device"></div>' +
            '<p class="acpf-choice-note"></p></div>' +
            '<div class="acpf-tiers"></div><div class="acpf-actions acpf-choice-actions"><button type="button" data-choice-action="cancel" class="acpf-secondary">' + tr("取消") + '</button>' +
            '<button type="button" data-choice-action="continue" class="acpf-primary"></button></div></section>';
        (document.querySelector('dialog[open]') || document.body).appendChild(overlay);
        overlay.querySelector('#acpf-choice-title').textContent = multiple ? tr('选择要安装的模型') : tr('选择配置档位');
        overlay.querySelector('.acpf-choice-description').textContent = tr(presentation.description);
        overlay.querySelector('.acpf-choice-note').textContent = multiple
            ? tr('已根据当前设备勾选推荐模型。你可以同时选择多个兼容模型；继续后将合并为一次 ACPF 配置与下载确认。')
            : tr('推荐项已根据当前设备选中。你可以选择其它兼容档位；继续后才会进入 ACPF 配置与下载确认。');
        overlay.querySelector('.acpf-device').textContent = `${plan.device?.accelerator?.vendor || tr('本地')} ${plan.device?.accelerator?.api || tr('设备')} · ${memory} GiB`;
        const mark = overlay.querySelector('.acpf-mark i'); mark.setAttribute('data-lucide', presentation.icon);
        const tiers = overlay.querySelector('.acpf-tiers');
        const draw = () => {
            tiers.replaceChildren();
            for (const option of options) {
                const wrapper = document.createElement('div'); wrapper.className = 'acpf-tier-wrap';
                const button = document.createElement('button'); button.type = 'button';
                button.dataset.choiceProfileId = option.profileId;
                button.disabled = !option.compatible || Boolean(plan.installMore && option.installed);
                const selected = selectedIds.has(option.profileId);
                button.setAttribute('aria-pressed', selected ? 'true' : 'false');
                button.className = 'acpf-tier' + (selected ? ' selected' : '') + (button.disabled ? ' unavailable' : '') + (option.deprecated ? ' deprecated' : '');
                if (multiple) {
                    const check = document.createElement('span'); check.className = 'acpf-tier-check';
                    check.textContent = selected ? '✓' : ''; button.append(check);
                }
                const copy = document.createElement('span'); copy.className = 'acpf-tier-copy';
                const name = document.createElement('strong'); name.textContent = tr(option.label);
                const detail = document.createElement('small');
                const baseDetail = plan.installMore && option.installed ? tr('已安装')
                    : option.compatible
                    ? tr(option.description || option.modelId || '')
                    : (option.disabledReasons || []).map(tr).join(' · ');
                detail.textContent = [baseDetail, option.deprecated ? tr('已过时') : '', option.lifecycleReason || ''].filter(Boolean).join(' · ');
                copy.append(name, detail); button.append(copy);
                if (option.deprecated) {
                    const badge = document.createElement('em'); badge.textContent = tr('已过时'); button.append(badge);
                } else if (option.recommended) {
                    const badge = document.createElement('em'); badge.textContent = tr('推荐'); button.append(badge);
                } else if (selected) {
                    const badge = document.createElement('em'); badge.textContent = tr('已选择'); button.append(badge);
                }
                wrapper.title = (option.disabledReasons || []).map(tr).join(' · ');
                wrapper.append(button); tiers.append(wrapper);
            }
            const proceed = overlay.querySelector('[data-choice-action="continue"]');
            proceed.disabled = selectedIds.size === 0;
            proceed.textContent = multiple ? tr('安装所选 {0} 个模型', selectedIds.size) : tr('使用所选档位继续');
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
                    if (option?.compatible && !(plan.installMore && option.installed)) {
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
                if (action === 'cancel') finish(Object.assign(new Error(tr('已取消能力配置')), { code: 'provisioning_cancelled' }));
                if (action === 'continue' && selectedIds.size > 0) {
                    finish(null, multiple ? Array.from(selectedIds) : Array.from(selectedIds)[0]);
                }
            });
        });
    }

    async function confirmLicenseChallenges(challenges, root = null) {
        const consents = [];
        for (const challenge of challenges || []) {
            const license = challenge.license || {};
            const overlay = document.createElement('div');
            overlay.className = 'acpf-overlay acpf-license-overlay';
            overlay.innerHTML = '<section class="acpf-sheet acpf-license-sheet" role="dialog" aria-modal="true" aria-labelledby="acpf-license-title">' +
                '<div class="acpf-heading"><span>CHECKPOINT LICENSE</span><h2 id="acpf-license-title"></h2>' +
                '<p class="acpf-license-usage"></p></div><div class="acpf-license-terms"></div>' +
                '<a class="acpf-license-link" target="_blank" rel="noopener noreferrer">' + tr("查看完整许可条款") + '</a>' +
                '<p class="acpf-license-attribution"></p><fieldset class="acpf-license-options"></fieldset>' +
                '<label class="acpf-license-confirm"><input type="checkbox"> <span></span></label>' +
                '<div class="acpf-actions"><button type="button" data-license-action="cancel" class="acpf-secondary">' + tr("取消") + '</button>' +
                '<button type="button" data-license-action="accept" class="acpf-primary" disabled>' + tr("确认许可并继续下载") + '</button></div></section>';
            if (root) { overlay.classList.add('acpf-inline'); overlay.querySelector('section').removeAttribute('aria-modal'); }
        (root || document.querySelector('dialog[open]') || document.body).appendChild(overlay);
            overlay.querySelector('#acpf-license-title').textContent = license.name || tr('模型许可确认');
            overlay.querySelector('.acpf-license-usage').textContent = tr('用途限制：{0}', license.usagePolicy || tr('以许可条款为准'));
            const terms = overlay.querySelector('.acpf-license-terms');
            terms.textContent = license.termsText || tr('完整许可文本由签名 envelope 中的固定条款 URL 与 SHA-256 绑定。');
            const link = overlay.querySelector('.acpf-license-link');
            link.href = license.termsUrl || '#';
            link.hidden = !license.termsUrl;
            const attribution = license.redistributionConditions?.attribution?.noticeText;
            const attributionNode = overlay.querySelector('.acpf-license-attribution');
            attributionNode.textContent = attribution ? tr('必要署名：{0}', attribution) : '';
            attributionNode.hidden = !attribution;
            const options = overlay.querySelector('.acpf-license-options');
            const optionLabels = {
                accepted_license_terms: tr('我已阅读并同意上述许可条款，并将在许可允许的用途范围内使用'),
                obtained_separate_license: tr('我已为预期用途取得权利方的单独许可或授权'),
            };
            for (const option of (challenge.acceptanceOptions || [])) {
                const label = document.createElement('label');
                const input = document.createElement('input');
                input.type = 'radio'; input.name = `license-decision-${challenge.distributionId}`;
                input.value = option; input.checked = false;
                const text = document.createElement('span'); text.textContent = optionLabels[option] || option;
                label.append(input, text); options.append(label);
            }
            const checkbox = overlay.querySelector('.acpf-license-confirm input');
            overlay.querySelector('.acpf-license-confirm span').textContent = challenge.attestationText || tr('我确认已同意或获得所需许可。');
            const accept = overlay.querySelector('[data-license-action="accept"]');
            const updateLicenseConfirmation = () => {
                accept.disabled = !checkbox.checked || !options.querySelector('input[type="radio"]:checked');
            };
            checkbox.addEventListener('change', updateLicenseConfirmation);
            options.addEventListener('change', updateLicenseConfirmation);
            const consent = await new Promise((resolve, reject) => {
                overlay.addEventListener('click', event => {
                    const action = event.target.closest('[data-license-action]')?.dataset.licenseAction;
                    if (action === 'cancel') reject(new Error(tr('未确认模型许可，Checkpoint 不会开始下载')));
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

    const stepPhaseOrder = { runtime: 0, provider: 1, checkpoint: 2, verify: 3 };
    const sessionStepPhase = {
        installing_runtime: 'runtime', installing_provider: 'provider',
        downloading_checkpoint: 'checkpoint', activating: 'verify', verifying: 'verify',
    };
    const stepStateLabels = { complete: tr('已完成'), active: tr('进行中'), failed: tr('失败'), pending: tr('待处理') };

    function stepIdentity(step) {
        return step.modelId || step.packageId || step.serviceKey || step.id || '';
    }

    function currentStepPhase(session) {
        if (session.status === 'ready') return 'ready';
        const direct = sessionStepPhase[session.status] || sessionStepPhase[session.progress?.phase];
        if (direct) return direct;
        const detail = session.progress?.detail || {};
        if (detail.modelId || detail.model_id) return 'checkpoint';
        if (session.status === 'awaiting_restart') {
            const operation = [...(session.operations || [])].reverse().find(item => item?.kind === 'package');
            const matchingStep = (session.plan?.steps || []).find(step => step.packageId === operation?.packageId);
            return matchingStep?.phase || 'provider';
        }
        return null;
    }

    function resolvedStepState(step, session) {
        if (session.status === 'ready' || step.status === 'complete') return 'complete';
        const completedPackages = new Set((session.operations || [])
            .filter(item => item?.kind === 'package' && item?.stage === 'finalizing')
            .map(item => item.packageId));
        if (step.packageId && completedPackages.has(step.packageId)) return 'complete';
        const phase = currentStepPhase(session);
        if (phase === 'ready') return 'complete';
        if (!phase || stepPhaseOrder[step.phase] === undefined) return 'pending';
        const comparison = stepPhaseOrder[step.phase] - stepPhaseOrder[phase];
        if (comparison < 0) return 'complete';
        if (comparison > 0) return 'pending';

        if (step.phase === 'checkpoint') {
            const detail = session.progress?.detail || {};
            const currentModel = detail.modelId || detail.model_id || '';
            if (currentModel && step.modelId && step.modelId !== currentModel) {
                const checkpoints = (session.plan?.steps || []).filter(item => item.phase === 'checkpoint');
                const stepIndex = checkpoints.findIndex(item => item.id === step.id);
                const currentIndex = checkpoints.findIndex(item => item.modelId === currentModel);
                if (currentIndex >= 0 && stepIndex < currentIndex) return 'complete';
                if (currentIndex >= 0 && stepIndex > currentIndex) return 'pending';
            }
        }
        return session.status === 'failed' ? 'failed' : 'active';
    }

    function groupedSteps(session) {
        const groups = [];
        for (const step of session.plan?.steps || []) {
            const key = `${step.phase || step.kind}\n${step.title}`;
            let group = groups.find(item => item.key === key);
            if (!group) {
                group = { key, title: step.title, phase: step.phase, steps: [] };
                groups.push(group);
            }
            group.steps.push(step);
        }
        return groups.map(group => {
            const states = group.steps.map(step => resolvedStepState(step, session));
            const state = states.includes('failed') ? 'failed'
                : states.includes('active') ? 'active'
                    : states.every(value => value === 'complete') ? 'complete' : 'pending';
            return { ...group, state };
        });
    }

    function sheet(session, root = null) {
        const overlay = document.createElement('div');
        overlay.className = 'acpf-overlay';
        overlay.innerHTML = '<section class="acpf-sheet acpf-run-sheet" role="dialog" aria-modal="true" aria-labelledby="acpf-title">' +
            '<header class="acpf-run-header"><div class="acpf-mark"><i></i></div><div class="acpf-heading"><span class="acpf-eyebrow"></span><h2 id="acpf-title"></h2><p class="acpf-description"></p><p class="acpf-reason"></p></div>' +
            '<div class="acpf-device"></div><div class="acpf-selected-tier"></div></header><div class="acpf-run-scroll"><ol class="acpf-steps"></ol></div>' +
            '<footer class="acpf-run-footer"><div class="acpf-progress"><i></i></div><p class="acpf-status"></p><div class="acpf-download-detail" hidden><strong></strong><div class="acpf-download-progress"><i></i></div><p></p><small hidden></small></div>' +
            '<p class="acpf-status acpf-transfer-summary" hidden></p><p class="acpf-error" hidden></p><div class="acpf-actions">' +
            '<button type="button" data-action="cancel" class="acpf-secondary">' + tr("取消") + '</button>' +
            '<button type="button" data-action="confirm" class="acpf-primary">' + tr("下载并配置") + '</button>' +
            '<button type="button" data-action="restart" class="acpf-primary" hidden>' + tr("重启本地服务") + '</button>' +
            '<button type="button" data-action="retry" class="acpf-primary" hidden>' + tr("重试") + '</button>' +
            '<button type="button" data-action="done" class="acpf-primary" hidden>' + tr('完成') + '</button></div></footer></section>';
        if (root) { overlay.classList.add('acpf-inline'); overlay.querySelector('section').removeAttribute('aria-modal'); }
        (root || document.querySelector('dialog[open]') || document.body).appendChild(overlay);
        render(overlay, session);
        return overlay;
    }

    function render(overlay, session) {
        const plan = session.plan || {};
        const presentation = { ...defaultPresentation, ...(plan.presentation || {}) };
        const memory = Math.round(plan.device?.system_memory_gib || 0);
        overlay.querySelector('.acpf-eyebrow').textContent = tr(presentation.eyebrow);
        overlay.querySelector('#acpf-title').textContent = tr(presentation.title);
        overlay.querySelector('.acpf-description').textContent = tr(presentation.description);
        // Lucide replaces the original <i> with an <svg> after the first
        // render.  ACPF polls and renders the same sheet repeatedly, so only
        // initialise the icon while the placeholder still exists.
        const mark = overlay.querySelector('.acpf-mark i');
        if (mark) mark.setAttribute('data-lucide', presentation.icon);
        overlay.querySelector('.acpf-reason').textContent = (plan.reasons || []).map(value => tr(value)).join(' · ');
        overlay.querySelector('.acpf-device').textContent = `${plan.device?.accelerator?.vendor || tr('本地')} ${plan.device?.accelerator?.api || tr('设备')} · ${memory} GiB · ${plan.profileId || ''}`;
        const options = plan.profileOptions || [];
        const selected = options.filter(option => option.selected);
        const selection = overlay.querySelector('.acpf-selected-tier');
        selection.hidden = selected.length === 0;
        selection.replaceChildren();
        if (selected.length > 0) {
            const label = document.createElement('span'); label.textContent = selected.length > 1 ? tr('已选择 {0} 个模型', selected.length) : tr('已选择档位');
            const name = document.createElement('strong'); name.textContent = selected.map(option => tr(option.label)).join('、');
            selection.append(label, name);
        }
        if (overlay.classList.contains('acpf-inline') && session.status === 'awaiting_confirmation' && options.length > 1 && !overlay.querySelector('.acpf-chat-profiles')) {
            const group=document.createElement('div');group.className='acpf-chat-profiles';
            const select=document.createElement('select');select.setAttribute('aria-label',tr('选择配置档位'));
            for(const option of options){const item=document.createElement('option');item.value=option.profileId;item.textContent=tr(option.label);item.disabled=!option.compatible;item.selected=option.profileId===plan.profileId;select.append(item);}
            const button=document.createElement('button');button.type='button';button.dataset.action='select-profile';button.textContent=tr('选择配置档位');
            group.append(select,button);overlay.querySelector('.acpf-run-header').append(group);
        }
        const profiles=overlay.querySelector('.acpf-chat-profiles');if(profiles)profiles.hidden=session.status!=='awaiting_confirmation';
        const list = overlay.querySelector('.acpf-steps');
        // Polling rebuilds these rows. Read the live state before replacing them
        // so both mouse and keyboard toggles survive the next progress update.
        const expandedGroups = new Set(Array.from(
            list.querySelectorAll('details.acpf-step-items[open]'),
            details => details.dataset.groupKey
        ));
        list.replaceChildren();
        for (const group of groupedSteps(session)) {
            const item = document.createElement('li');
            item.className = group.state;
            item.setAttribute('aria-label', `${tr(group.title)}, ${stepStateLabels[group.state]}`);
            const dot = document.createElement('i');
            const content = document.createElement('span');
            const heading = document.createElement('div'); heading.className = 'acpf-step-heading';
            const title = document.createElement('strong'); title.textContent = tr(group.title);
            if (group.steps.length > 1) {
                const count = document.createElement('b'); count.textContent = `×${group.steps.length}`; title.append(' ', count);
            }
            const state = document.createElement('em'); state.className = 'acpf-step-state'; state.textContent = stepStateLabels[group.state];
            heading.append(title, state); content.append(heading);
            if (group.steps.length === 1) {
                const step = group.steps[0];
                const detail = document.createElement('small'); detail.textContent = `${stepIdentity(step)} ${step.requiredVersion || ''}`.trim();
                content.append(detail);
            } else {
                const details = document.createElement('details'); details.className = 'acpf-step-items';
                details.dataset.groupKey = group.key;
                details.open = expandedGroups.has(group.key);
                const summary = document.createElement('summary'); summary.textContent = tr('查看 {0} 项', group.steps.length);
                const identifiers = document.createElement('ul');
                for (const step of group.steps) {
                    const row = document.createElement('li'); row.textContent = `${stepIdentity(step)} ${step.requiredVersion || ''}`.trim(); identifiers.append(row);
                }
                details.append(summary, identifiers); content.append(details);
            }
            item.append(dot, content); list.append(item);
        }
        const percent = Math.max(0, Math.min(100, Number(session.progress?.percent || 0)));
        overlay.querySelector('.acpf-progress i').style.width = `${percent}%`;
        const progressDetail = session.progress?.detail || {};
        const progressStage = String(progressDetail.stage || '');
        const statusLabel = progressStage === 'verifying_checkpoint'
            || progressStage === 'materializing_checkpoint'
            ? labels.verifying
            : progressStage === 'activating_checkpoint'
                ? labels.activating
                : (labels[session.status] || session.status);
        overlay.querySelector('.acpf-status').textContent = `${statusLabel} · ${Math.round(percent)}%`;
        const bytesCompleted = Number(progressDetail.bytesCompleted ?? progressDetail.bytes_completed ?? 0);
        const bytesTotal = Number(progressDetail.bytesTotal ?? progressDetail.bytes_total ?? 0);
        const totalBytesCompleted = Number(progressDetail.totalBytesCompleted ?? progressDetail.total_bytes_completed ?? bytesCompleted);
        const totalBytesTotal = Number(progressDetail.totalBytesTotal ?? progressDetail.total_bytes_total ?? bytesTotal);
        const currentFile = progressDetail.fileName || progressDetail.current_file || progressDetail.packageId || progressDetail.model_id || '';
        const itemPercent = bytesTotal > 0 ? Math.max(0, Math.min(100, bytesCompleted / bytesTotal * 100)) : 0;
        const downloadDetail = overlay.querySelector('.acpf-download-detail');
        const transferStage = progressStage === 'verifying_checkpoint' || progressStage.startsWith('downloading_');
        downloadDetail.hidden = !(transferStage && currentFile && bytesTotal > 0 && ['installing_runtime', 'installing_provider', 'downloading_checkpoint'].includes(session.status));
        downloadDetail.querySelector('strong').textContent = currentFile;
        downloadDetail.querySelector('.acpf-download-progress i').style.width = `${itemPercent}%`;
        downloadDetail.querySelector('p').textContent = tr('当前项目 {0}% · {1} / {2}', Math.round(itemPercent), formatBytes(bytesCompleted), formatBytes(bytesTotal));
        overlay.transferMeter ||= createTransferMeter();
        const transfer = overlay.transferMeter(
            `${session.id}:${session.status}:${progressDetail.distributionId || progressDetail.model_id || currentFile}:${totalBytesTotal}`,
            totalBytesCompleted, totalBytesTotal
        );
        const activeTransfer = String(progressDetail.stage || '').startsWith('downloading_')
            || progressDetail.status === 'downloading';
        if (progressDetail.download) overlay.lastDownload = progressDetail.download;
        const measuredTransfer = progressDetail.download
            ? formatDownloadProgress(progressDetail.download, true) : transfer;
        if (!downloadDetail.hidden && activeTransfer) downloadDetail.querySelector('p').textContent += ` · ${measuredTransfer}`;
        const transferSummary = overlay.querySelector('.acpf-transfer-summary');
        transferSummary.hidden = activeTransfer || !overlay.lastDownload;
        transferSummary.textContent = formatDownloadProgress(overlay.lastDownload, false);
        const totalDetail = downloadDetail.querySelector('small');
        totalDetail.hidden = !(totalBytesTotal > bytesTotal);
        totalDetail.textContent = tr('本次下载总计 {0}% · {1} / {2}', Math.round(totalBytesCompleted / totalBytesTotal * 100), formatBytes(totalBytesCompleted), formatBytes(totalBytesTotal));
        const error = overlay.querySelector('.acpf-error');
        const sourceWarnings = (progressDetail.download || overlay.lastDownload)?.warnings || [];
        error.hidden = !session.error && !sourceWarnings.length;
        error.textContent = session.error ? tr(session.error.message || '') : `Warning: ${sourceWarnings.join(' ')}`;
        error.classList.toggle('is-notice', !session.error || session.status === 'awaiting_restart');
        overlay.querySelector('[data-action="confirm"]').hidden = session.status !== 'awaiting_confirmation';
        overlay.querySelector('[data-action="confirm"]').textContent = session.error?.code === 'checkpoint_license_consent_required'
            ? tr('查看并确认模型许可')
            : tr(presentation.confirm_label);
        overlay.querySelector('[data-action="restart"]').hidden = session.status !== 'awaiting_restart';
        overlay.querySelector('[data-action="retry"]').hidden = session.status !== 'failed';
        overlay.querySelector('[data-action="cancel"]').hidden = session.status === 'ready';
        overlay.querySelector('[data-action="done"]').hidden = session.status !== 'ready';
        if (session.status === 'ready') {
            overlay.querySelector('#acpf-title').textContent = tr('安装成功');
            overlay.querySelector('.acpf-description').textContent = tr('安装已完成，可以开始使用。');
            overlay.querySelector('.acpf-progress i').style.width = '100%';
            overlay.querySelector('.acpf-status').textContent = tr(presentation.ready_label);
        }
        window.lucide?.createIcons();
    }

    async function runSession(initial, appId, options = {}) {
        const send = options.request || request;
        const sessionId = initial?.id;
        if (!sessionId) throw new Error('Provisioning session id is required');
        if(!options.root)savePending({ sessionId, appId, resumeToken: initial.intent?.resumeToken });
        const runnerKey = options.root || sessionId;
        const active = activeRuns.get(runnerKey);
        if (active) return active;
        let session = initial;
        const overlay = sheet(session, options.root);
        if (options.readOnly) overlay.querySelectorAll("button").forEach(button => button.hidden = true);
        let sharedRun;
        const run = new Promise((resolve, reject) => {
            let stopped = false;
            let acting = false;
            const observer=options.root ? new MutationObserver(()=>{if(!options.root.isConnected)finish(Object.assign(new Error('Configuration view detached'),{code:'view_detached'}));}) : null;
            observer?.observe(document.body,{childList:true,subtree:true});
            const finish = (error, value) => {
                if (stopped) return; stopped = true; observer?.disconnect(); overlay.remove();
                if (error) reject(error); else resolve(value);
            };
            overlay.addEventListener('click', async event => {
                const action = event.target.closest('[data-action]')?.dataset.action;
                if (!action || acting || options.readOnly) return;
                acting = true;
                try {
                    if (session.status === 'ready') {
                        if (action === 'done') finish(null, configuredResult(session));
                        return;
                    }
                    if (action === 'cancel') {
                        if (!terminal.has(session.status)) await send(`/provisioning/sessions/${session.id}/cancel`, { method: 'POST' });
                        clearPending(appId); finish(Object.assign(new Error(tr('已取消能力配置')), { code: 'provisioning_cancelled' })); return;
                    }
                    if (action === 'confirm' || action === 'retry') {
                        const challenges = session.error?.code === 'checkpoint_license_consent_required'
                            ? session.error?.challenges || []
                            : [];
                        const licenseConsents = challenges.length
                            ? await confirmLicenseChallenges(challenges, options.root ? overlay : null)
                            : [];
                        session = await send(`/provisioning/sessions/${session.id}/${action}`, {
                            method: 'POST',
                            body: JSON.stringify({ licenseConsents }),
                        });
                    } else if (action === 'select-profile') {
                        const selected = await send(`/provisioning/sessions/${session.id}/select-profile`, {method:'POST', body:JSON.stringify({profileId:overlay.querySelector('.acpf-chat-profiles select').value})});
                        if(selected.status==='ready'&&!selected.id){finish(null,selected);return;}
                        session=selected;
                        overlay.querySelector('.acpf-chat-profiles')?.remove();
                    } else if (action === 'restart') {
                        overlay.querySelector('[data-action="restart"]').disabled = true;
                        await request('/client/restart-local', { method: 'POST' }).catch(error => {
                            if (!(error instanceof TypeError)) throw error;
                        });
                    }
                    render(overlay, session);
                } catch (error) {
                    const node = overlay.querySelector('.acpf-error'); node.hidden = false; node.textContent = error.message;
                } finally { acting = false; }
            });
            (async function poll() {
                while (!stopped) {
                    if (options.root && !options.root.isConnected) { finish(Object.assign(new Error('Configuration view detached'), {code:'view_detached'})); return; }
                    if (session.status === 'ready') {
                        render(overlay, session); if(options.readOnly){overlay.querySelectorAll("button").forEach(button => button.hidden=true);finish(null,configuredResult(session));} return;
                    }
                    if (session.status === 'cancelled' || session.status === 'unsupported') {
                        clearPending(appId); finish(new Error(labels[session.status] || session.status)); return;
                    }
                    await new Promise(done => setTimeout(done, 500));
                    if (stopped) return;
                    try {
                        const polledSessionId = session.id;
                        const polled = await send(`/provisioning/sessions/${polledSessionId}`);
                        if (stopped) return;
                        if (session.id !== polledSessionId) continue;
                        session = polled;
                        if(!options.root)savePending({ sessionId: session.id, appId, resumeToken: session.intent?.resumeToken }); render(overlay, session); if(options.readOnly) overlay.querySelectorAll("button").forEach(button => button.hidden=true);
                    } catch (error) {
                        if(options.root && error.status>=400 && error.status<500){finish(error);return;}
                        overlay.querySelector('.acpf-status').textContent = tr('本地服务正在重启，等待重新连接…');
                    }
                }
            })();
        });
        sharedRun = run.finally(() => {
            if (activeRuns.get(runnerKey) === sharedRun) activeRuns.delete(runnerKey);
        });
        activeRuns.set(runnerKey, sharedRun);
        return sharedRun;
    }

    async function ensure(body, { installMore = false } = {}) {
        const probed = await probe(body);
        if (probed.status === 'ready' && !installMore) {
            clearPending(body.appId);
            return { ...probed, outcome: 'already_ready' };
        }
        if (window.AI2APPS_MOBILE_SURFACE) throw new Error(document.documentElement.lang.startsWith('zh') ? '请先在 Mac 上安装并配置此模型，再回到手机使用。' : 'Install and configure this model on your Mac, then return to Mobile.');
        if (probed.status === 'unsupported') throw new Error(tr('当前设备不支持此能力'));
        if (installMore && probed.plan) {
            probed.plan.installMore = true;
            probed.plan.selectionMode = 'multiple';
        }
        const profileSelection = await chooseProfile(probed.plan);
        const requestBody = {
            ...body,
            appInstanceId: body.appInstanceId || appInstanceId(),
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
        if (result.status === 'unsupported') throw new Error((result.reasons || [tr('当前设备不支持此能力')]).join('；'));
        savePending({ sessionId: result.sessionId, appId: body.appId, resumeToken: result.session?.intent?.resumeToken });
        return runSession(result.session, body.appId);
    }

    async function resume(appId, { capability, actionId } = {}) {
        if (window.AI2APPS_MOBILE_SURFACE) return null;
        const matches = session => (!capability || session.capability === capability)
            && (!actionId || session.actionId === actionId);
        let pending = null;
        try { pending = JSON.parse(localStorage.getItem(storageKey(appId)) || 'null'); } catch (_) { clearPending(appId); }
        if (!pending?.sessionId) {
            const sessions = await request('/provisioning/sessions');
            const session = (sessions.items || []).find(item =>
                item.appId === appId
                && item.appInstanceId === appInstanceId()
                && !['cancelled', 'unsupported'].includes(item.status)
                && matches(item)
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
            if (['cancelled', 'unsupported'].includes(session.status)) { clearPending(appId); return null; }
            if (!matches(session)) return null;
            return runSession(session, appId);
        } catch (error) { clearPending(appId); throw error; }
    }

    function probe(body) {
        return request('/capabilities/probe', {
            method: 'POST',
            body: JSON.stringify({ ...body, appInstanceId: body.appInstanceId || appInstanceId() }),
        });
    }

    function miniAppPackageComponents(item,placement){
        const components=item.miniApps||item.manifest?.miniApps||item.latestRelease?.manifest?.miniApps||[];
        return Array.isArray(components)?components.filter(c=>Array.isArray(c?.placements)&&c.placements.includes(placement)):[];
    }
    const miniAppHosts = {
        'ai2apps.ai-browser': 'AI Browser',
        'ai2apps.imagine-studio': 'Imagine Studio',
        'ai2apps.video-studio': 'Video Studio',
        'ai2apps.readaloud': 'Voice Studio',
    };
    async function createPrivateMiniAppProject({placement,name,requirements}) {
        if(!miniAppHosts[placement])throw Error('Unsupported Mini-App placement');
        name=String(name||'').trim();requirements=String(requirements||'').trim();
        if(!name||name.length>120||!requirements||requirements.length>24000)throw Error('Enter a name and requirements');
        const response=await fetch('/v1/platform/coder/projects',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,root_path:'private-mini-app-'+crypto.randomUUID(),kind:'ai2apps',create_directory:true,bootstrap:true})});
        const project=await response.json();if(!response.ok)throw Error(project.detail?.message||project.detail||'Could not create private project');
        if(!project.id)throw Error('Missing project identity');
        let contract='Follow docs/ai2apps-studio-mini-app-package-contract-v1.md. Use the host SDK, declared capabilities and host-owned output. ';
        if(placement==='ai2apps.ai-browser')contract+='Follow docs/ai2apps-browser-control-architecture.md; execute WebAgents through the shared background Task system and authenticated host SDK. ';
        if(placement==='ai2apps.readaloud')contract+='All output must use the one host-owned Preview & Output based on Quick Read. Do not add per-Mini-App output history, playback, download or drag logic. Keep private Line caches and reference materials outside output retention/deletion. ';
        const prompt='Build a private AI2Apps Mini-App Package for placement '+placement+'. '+contract+'Provide a fixed UI with one or more capabilities. Keep this project private and local; do not publish or upload it. Include validation and local installation instructions. User requirements:\n'+requirements;
        sessionStorage.setItem('ai2apps.coder.mini-app-handoff',JSON.stringify({projectId:project.id,prompt}));
        if(window.ai2appsShell?.openEntry)await window.ai2appsShell.openEntry({appId:'ai2apps.coder'});else window.open('/apps/ai2apps.coder','_top');
        return project;
    }
    async function openMiniAppCustomization({placement}) {
        if(!miniAppHosts[placement])throw Error('Unsupported Mini-App placement');
        const labels=document.querySelector('.studio-mini-more')?.dataset||{};
        const overlay=document.createElement('div');overlay.className='acpf-overlay';
        overlay.innerHTML='<form class="acpf-sheet" role="dialog" aria-modal="true"><h2></h2><label data-name-label></label><input data-name required maxlength="120"><label data-request-label></label><textarea data-request required maxlength="24000" rows="7"></textarea><p class="acpf-error" role="status"></p><div class="acpf-actions"><button type="button" class="acpf-secondary" data-cancel></button><button type="submit" class="acpf-primary" data-confirm></button></div></form>';
        overlay.querySelector('h2').textContent=labels.customTitle||'Customize Mini-App';
        overlay.querySelector('[data-name-label]').textContent=labels.customName||'Name';
        overlay.querySelector('[data-request-label]').textContent=labels.customRequest||'Your requirements';
        const cancel=overlay.querySelector('[data-cancel]'),confirm=overlay.querySelector('[data-confirm]'),form=overlay.querySelector('form');
        cancel.textContent=labels.customCancel||'Cancel';confirm.textContent=labels.customConfirm||'Open Coder';
        const previous=document.activeElement;let busy=false;document.body.append(overlay);overlay.querySelector('[data-name]').focus();
        return new Promise(resolve=>{
            const finish=()=>{if(busy)return;document.removeEventListener('keydown',keys);overlay.remove();previous?.focus?.();resolve();};
            const keys=event=>{if(event.key==='Escape'){event.preventDefault();finish();}if(event.key==='Tab'){const nodes=[...overlay.querySelectorAll('input,textarea,button:not(:disabled)')],i=nodes.indexOf(document.activeElement);if(event.shiftKey&&i<=0){event.preventDefault();nodes.at(-1).focus();}else if(!event.shiftKey&&(i<0||i===nodes.length-1)){event.preventDefault();nodes[0].focus();}}};
            document.addEventListener('keydown',keys);cancel.onclick=finish;
            form.onsubmit=async event=>{event.preventDefault();if(busy||!form.reportValidity())return;busy=true;cancel.disabled=true;confirm.disabled=true;
                try{await createPrivateMiniAppProject({placement,name:overlay.querySelector('[data-name]').value,requirements:overlay.querySelector('[data-request]').value});busy=false;finish();}
                catch(error){overlay.querySelector('.acpf-error').textContent=error.message;}
                finally{busy=false;cancel.disabled=false;confirm.disabled=false;}
            };
        });
    }
    async function openMiniAppPackages({placement}) {
        if(!miniAppHosts[placement])throw Error('Unsupported Mini-App placement');
        const hostName=miniAppHosts[placement];
        const zh=/^zh/i.test(document.documentElement.lang),label=(cn,en)=>zh?cn:en;
        const overlay=document.createElement('div');overlay.className='acpf-overlay acpf-choice-overlay';
        overlay.innerHTML='<section class="acpf-sheet acpf-choice-sheet" role="dialog" aria-modal="true"><header class="acpf-choice-header"><div class="acpf-heading"><span>AI2APPS MINI-APPS</span><h2></h2><p></p></div></header><div class="acpf-mini-catalog"></div><p class="acpf-error" role="status"></p><div class="acpf-actions"><button type="button" class="acpf-secondary" data-more></button><button type="button" class="acpf-secondary" data-close></button></div></section>';
        overlay.querySelector('h2').textContent=label('安装 '+hostName+' Mini-App','Install '+hostName+' Mini-Apps');
        overlay.querySelector('.acpf-heading p').textContent=label('只显示声明支持 '+hostName+' 的 Package。安装使用系统签名校验和依赖检查。','Only Packages declaring '+hostName+' support are shown. Installation uses system signature and dependency checks.');
        const list=overlay.querySelector('.acpf-mini-catalog'),error=overlay.querySelector('.acpf-error'),more=overlay.querySelector('[data-more]'),close=overlay.querySelector('[data-close]');
        more.textContent=label('加载更多','Load more');close.textContent=label('关闭','Close');
        let cursor='',busy=false,installed=false;const seen=new Set();
        const previous=document.activeElement;document.body.append(overlay);close.focus();
        return await new Promise(resolve=>{
            const finish=()=>{if(busy)return;document.removeEventListener('keydown',keys);overlay.remove();previous?.focus?.();resolve({installed});};
            const keys=event=>{if(event.key==='Escape'){event.preventDefault();finish();}if(event.key==='Tab'){const nodes=[...overlay.querySelectorAll('button:not(:disabled),a[href]')];if(!nodes.length)return;const i=nodes.indexOf(document.activeElement);if(event.shiftKey&&i<=0){event.preventDefault();nodes.at(-1).focus();}else if(!event.shiftKey&&(i<0||i===nodes.length-1)){event.preventDefault();nodes[0].focus();}}};
            document.addEventListener('keydown',keys);close.onclick=finish;
            const install=async(item,button)=>{
                busy=true;close.disabled=true;more.disabled=true;button.disabled=true;error.textContent='';
                try{
                    const id=item.packageId||item.package?.id||item.manifest?.package?.id;
                    if(!/^[a-zA-Z0-9._-]+\/[a-zA-Z0-9._-]+$/.test(id||''))throw Error('Invalid Package identity');
                    const path='/packages/'+id.split('/').map(encodeURIComponent).join('/');
                    let op=await request(path+'/install-operations',{method:'POST',body:JSON.stringify({version:item.latestVersion||item.version||item.latestRelease?.version||null,approve_review:false})});
                    while(['pending','running'].includes(op.status)){
                        error.textContent=label('正在安装：','Installing: ')+(op.stage||op.status);
                        await new Promise(r=>setTimeout(r,750));op=await request('/packages/install-operations/'+encodeURIComponent(op.operationId));
                    }
                    if(op.status!=='completed'&&op.status!=='succeeded')throw Error(op.error?.message||label('安装未完成，请在“发现”查看审核或依赖要求。','Installation did not finish. Check Discover for review or dependency requirements.'));
                    installed=true;button.textContent=label('已安装','Installed');error.textContent=label('安装完成，可关闭此窗口。','Installed. You can close this window.');
                }catch(e){error.textContent=String(e.message);button.disabled=false;}
                finally{busy=false;close.disabled=false;more.disabled=false;}
            };
            const load=async()=>{
                more.disabled=true;error.textContent=label('正在加载…','Loading…');
                try{
                    let pages=0;
                    do{
                        const result=await request('/packages/catalog/search?type=app&limit=100'+(cursor?'&cursor='+encodeURIComponent(cursor):''));
                        cursor=result.nextCursor||result.next_cursor||result.pagination?.nextCursor||result.pagination?.next_cursor||'';
                        const rows=Array.isArray(result)?result:(result.items||result.packages||result.results||[]);
                        for(const item of rows){
                            const id=item.packageId||item.package?.id||item.manifest?.package?.id;
                            const compatible=miniAppPackageComponents(item,placement);
                            if(!compatible.length||seen.has(id))continue;seen.add(id);
                            const card=document.createElement('article');card.className='acpf-mini-package';const title=document.createElement('strong'),description=document.createElement('p'),button=document.createElement('button');
                            title.textContent=item.displayName||item.package?.displayName||id;description.textContent=compatible.map(c=>c.displayName||c.componentId).join(' · ');button.className='acpf-primary';button.textContent=label('安装 Mini-App','Install Mini-App');button.onclick=()=>install(item,button);card.append(title,description,button);list.append(card);
                        }
                        pages++;
                    }while(!seen.size&&cursor&&pages<5);
                    error.textContent=seen.size?'':label('暂无已发布且适配 '+hostName+' 的 Mini-App Package。','No published '+hostName+' Mini-App Packages are available.');more.hidden=!cursor;
                }catch(e){error.textContent=String(e.message);}
                finally{more.disabled=false;}
            };
            more.onclick=load;void load();
        });
    }

    // A generic owner-declared setup handoff. It configures prerequisites only;
    // returning never submits the pending Tool or accepts a licence automatically.
    const setupViews=new Map();
    window.addEventListener('ai2apps:host-context',async event=>{
        const context=event.detail, intent=context?.appInteraction;
        if(intent?.kind!=='capability_setup'||intent.returning||window.AI2APPS_MOBILE_SURFACE)return;
        const key=intent.runId+':'+intent.interactionId;
        if(setupViews.has(key))return;
        setupViews.set(key,true);
        const panel=document.createElement('section');panel.className='aaat-setup-return';panel.style.cssText='position:relative;z-index:20;padding:14px;margin:12px;border:1px solid #ccd3df;border-radius:12px;background:var(--bg-primary,#fff)';
        const status=document.createElement('p');status.textContent=document.documentElement.lang.startsWith('zh')?'正在准备模型配置，原对话参数已保留。':'Preparing model setup; conversation parameters are preserved.';
        const back=document.createElement('button');back.type='button';back.textContent=document.documentElement.lang.startsWith('zh')?'返回对话，重新检查':'Return to conversation and recheck';
        back.onclick=()=>window.ai2appsShell.openSetup(intent.runId,intent.interactionId,true).catch(error=>{status.textContent=error.message;});
        panel.append(status,back);document.body.prepend(panel);
        try{
            const setup=await request('/agent-runs/'+encodeURIComponent(intent.runId)+'/interactions/'+encodeURIComponent(intent.interactionId)+'/parameters/setup');
            if(setup.target.app_id!==context.appId||setup.install.appId!==context.appId)throw Error('Configuration owner changed');
            const result=await ensure({...setup.install,appInstanceId:context.instanceId});
            if(result.status==='ready'&&result.session?.id)await acknowledge(result.session.id,{appId:context.appId});
            status.textContent=result.status==='ready'?(document.documentElement.lang.startsWith('zh')?'配置已完成。返回对话选择模型并确认继续。':'Setup ready. Return to select the model and confirm.'):String(result.status);
        }catch(error){status.textContent=error.message;setupViews.delete(key);}
    });
    window.AI2AppsCapabilities = { createPrivateMiniAppProject, openMiniAppCustomization, miniAppPackageComponents, openMiniAppPackages, ensure, resume, probe, acknowledge, appInstanceId, chooseProfile, runSession, createTransferMeter, formatDownloadProgress };
})();
