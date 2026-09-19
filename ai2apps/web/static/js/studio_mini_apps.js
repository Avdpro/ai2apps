(function () {
    'use strict';

    function appInstanceId() {
        return window.AI2AppsCapabilities?.appInstanceId?.()
            || document.querySelector('[data-app-instance-id]')?.dataset?.appInstanceId
            || new URLSearchParams(window.location.hash.slice(1)).get('ai2apps-instance')
            || '';
    }

    async function payload(response) {
        const value = await response.json().catch(() => null);
        if (!response.ok) throw new Error(value?.error?.message || value?.detail?.message || value?.detail || `Request failed (${response.status})`);
        return value;
    }

    function primaryCapability(miniApp) {
        const values = miniApp?.requirements?.capabilities;
        if (!Array.isArray(values) || values.length === 0) return '';
        const first = values[0];
        return typeof first === 'string' ? first : (typeof first?.capability === 'string' ? first.capability : '');
    }
    function setupStorageKey(studioId) { return `ai2apps.studio-mini-app.setup.${studioId}`; }
    function pendingSetup(studioId) {
        try { return JSON.parse(localStorage.getItem(setupStorageKey(studioId)) || 'null'); }
        catch (_) { localStorage.removeItem(setupStorageKey(studioId)); return null; }
    }
    function clearPendingSetup(studioId) { localStorage.removeItem(setupStorageKey(studioId)); }

    const PACKAGE_FRAME_SELECTORS = [
        '.ra-package-mini-app-frame',
        '.vs-package-mini-app-frame',
        '.is-package-mini-app-frame',
    ].join(',');
    function packageFrameForSource(source) {
        return [...document.querySelectorAll(PACKAGE_FRAME_SELECTORS)]
            .find(frame => frame.contentWindow === source);
    }
    function handlePackageMiniAppResize(event) {
        const message = event?.data;
        if (message?.type !== 'ai2apps:mini-app-resize' || message?.version !== 1) return;
        const frame = packageFrameForSource(event.source);
        if (!frame) return;
        const requested = Number(message.height);
        if (!Number.isFinite(requested)) return;
        const height = Math.min(20000, Math.max(620, Math.ceil(requested)));
        if (frame.dataset.contentHeight === String(height)) return;
        frame.dataset.contentHeight = String(height);
        frame.style.height = `${height}px`;
    }
    window.addEventListener('message', handlePackageMiniAppResize);

    const mountedFrames = new Map();
    const channels = new WeakMap();
    const mediaCapabilities = new Set(['audio.detailed_transcription', 'audio.source_separation',
        'media.video_subtitles', 'audio.speaker_voice_replacement', 'media.video_speaker_voice_replacement']);
    const formFields = new Set(['file', 'reference', 'profile', 'language', 'word_timestamps', 'diarization',
        'source_language', 'target_language', 'subtitle_format', 'bilingual', 'burn_in', 'speaker_labels',
        'action', 'target_speaker', 'consent', 'conversion_profile', 'voice_name']);
    window.addEventListener('message', event => {
        if (event.data?.type !== 'ai2apps:studio-connect' || event.data?.version !== 1) return;
        const frame = packageFrameForSource(event.source);
        const binding = frame && mountedFrames.get(frame.src);
        if (!binding || (event.origin !== 'null' && event.origin !== location.origin)) return;
        channels.get(frame)?.();
        const channel = new MessageChannel();
        const source = event.source;
        const src = frame.src;
        let closed = false;
        let busy = false;
        const abort = new AbortController();
        const active = () => !closed && frame.isConnected && frame.src === src && frame.contentWindow === source;
        const close = () => {
            closed = true; abort.abort(); channel.port1.close(); observer.disconnect();
            frame.removeEventListener('load', revoke);
        };
        const revoke = () => { mountedFrames.delete(src); close(); };
        const observer = new MutationObserver(() => { if (!active()) revoke(); });
        observer.observe(frame, {attributes: true, attributeFilter: ['src']});
        frame.addEventListener('load', revoke);
        channels.set(frame, close);
        const base = `/v1/platform/studios/${encodeURIComponent(binding.studioId)}/mini-app-mounts/${encodeURIComponent(binding.mountId)}`;
        const storageKey = `ai2apps.studio-draft.v1:${binding.owner}:${binding.provider}:${binding.resource}`;
        channel.port1.onmessage = async message => {
            const request = message.data;
            if (!active()) { close(); return; }
            if (!Number.isSafeInteger(request?.id) || request.id < 1) return;
            const reply = value => { if (active()) channel.port1.postMessage({id: request.id, ...value}); };
            if (busy) { reply({error: 'A Mini-App operation is already running'}); return; }
            busy = true;
            try {
                // Revalidate actor, live mount and signed declaration for every operation,
                // including draft access; the iframe never receives session credentials.
                const probe = await payload(await fetch(`${base}/capabilities`, {
                    credentials: 'same-origin', cache: 'no-store', signal: abort.signal,
                }));
                if (!active()) return;
                if (request.operation === 'probe') reply({value: probe});
                else if (request.operation === 'draft.get') reply({value: localStorage.getItem(storageKey)});
                else if (request.operation === 'draft.remove') { localStorage.removeItem(storageKey); reply({value: null}); }
                else if (request.operation === 'draft.set') {
                    if (typeof request.value !== 'string' || new TextEncoder().encode(request.value).length > 65536) throw new Error('Draft exceeds 64 KiB');
                    const draft = JSON.parse(request.value);
                    if (draft?.schema !== 'ai2apps.mini-app-draft/v1' || draft.miniApp !== binding.miniAppId) throw new Error('Invalid Mini-App draft');
                    localStorage.setItem(storageKey, request.value); reply({value: null});
                } else if (request.operation === 'invoke') {
                    if (!mediaCapabilities.has(request.capability) || !probe.items?.some(item => item.capability === request.capability)) throw new Error('Capability is not allowed');
                    if (!Array.isArray(request.fields) || request.fields.length > 24) throw new Error('Invalid media fields');
                    const body = new FormData();
                    const names = new Set();
                    let bytes = 0;
                    for (const entry of request.fields) {
                        if (!Array.isArray(entry) || entry.length !== 2) throw new Error('Invalid field');
                        const [name, value] = entry;
                        if (!formFields.has(name) || names.has(name)) throw new Error('Invalid or duplicate field');
                        names.add(name);
                        if (name === 'file' || name === 'reference') {
                            if (!(value instanceof Blob)) throw new Error('Expected media file');
                            bytes += value.size;
                            body.append(name, value, value.name || 'media.bin');
                        } else {
                            if (typeof value !== 'string' || value.length > 4096) throw new Error('Invalid option');
                            body.append(name, value);
                        }
                    }
                    if (!names.has('file') || bytes > 100 * 1024 * 1024) throw new Error('Invalid media upload size');
                    const response = await fetch(`${base}/capabilities/${encodeURIComponent(request.capability)}/invoke`, {
                        method: 'POST', credentials: 'same-origin', body, signal: abort.signal,
                    });
                    reply({value: {status: response.status, body: await response.blob(),
                        headers: {'content-type': response.headers.get('content-type') || '',
                            'content-disposition': response.headers.get('content-disposition') || ''}}});
                } else throw new Error('Unknown Mini-App operation');
            } catch (error) { reply({error: error?.message || 'Mini-App operation failed'}); }
            finally { busy = false; }
        };
        source.postMessage({type: 'ai2apps:studio-connected', version: 1}, '*', [channel.port2]);
    });

    window.AI2AppsStudioMiniApps = Object.freeze({
        async list(studioId) {
            return payload(await fetch(`/v1/platform/studios/${encodeURIComponent(studioId)}/mini-apps`, {
                credentials: 'same-origin', headers: { Accept: 'application/json' }, cache: 'no-store',
            }));
        },
        async mount(studioId, miniAppId, { placement = 'inline', context = {} } = {}) {
            const instanceId = appInstanceId();
            if (!instanceId) throw new Error('Studio App instance is unavailable');
            const mount = await payload(await fetch(`/v1/platform/studios/${encodeURIComponent(studioId)}/mini-app-mounts`, {
                method: 'POST', credentials: 'same-origin',
                headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-AI2Apps-App-Instance': instanceId },
                body: JSON.stringify({ miniAppId, placement, context }),
            }));
            const url = new URL(mount.content_url, location.origin);
            if (url.origin !== location.origin) throw new Error('Invalid Mini-App content origin');
            if (mountedFrames.size >= 128) mountedFrames.delete(mountedFrames.keys().next().value);
            mountedFrames.set(url.href, {studioId, mountId: mount.id, miniAppId,
                owner: instanceId, provider: mount.app_instance_id, resource: mount.resource});
            return mount;
        },
        async probe(studioId, mountId) {
            return payload(await fetch(`/v1/platform/studios/${encodeURIComponent(studioId)}/mini-app-mounts/${encodeURIComponent(mountId)}/capabilities`, {
                credentials: 'same-origin', headers: { Accept: 'application/json' }, cache: 'no-store',
            }));
        },
        async probeAll(studioId) {
            const instanceId = appInstanceId();
            if (!instanceId) throw new Error('Studio App instance is unavailable');
            return payload(await fetch(`/v1/platform/studios/${encodeURIComponent(studioId)}/mini-app-capabilities`, {
                credentials: 'same-origin',
                headers: { Accept: 'application/json', 'X-AI2Apps-App-Instance': instanceId },
                cache: 'no-store',
            }));
        },
        async readiness(studioId) {
            const catalog = await this.probeAll(studioId);
            return Object.fromEntries((catalog?.items || []).map(probe => {
                const capabilities = Array.isArray(probe?.items) ? probe.items : [];
                const required = capabilities.filter(value => value?.required !== false);
                return [probe.miniAppId, required.length > 0 && required.every(value => value?.implemented === true && value?.ready === true)];
            }));
        },
        async setup(studioId, miniApp) {
            const capability = primaryCapability(miniApp);
            if (!capability) throw new Error('Mini-App does not declare a setup capability');
            if (!window.AI2AppsCapabilities?.ensure) throw new Error('ACPF is unavailable');
            const resumeToken = globalThis.crypto?.randomUUID?.() || `studio-mini-app-${Date.now()}`;
            localStorage.setItem(setupStorageKey(studioId), JSON.stringify({ miniAppId: miniApp.id, capability, resumeToken }));
            try {
                const result = await window.AI2AppsCapabilities.ensure({
                    appId: studioId,
                    capability,
                    actionId: 'setup-mini-app',
                    requirements: {},
                    intent: {
                        returnTo: `/apps/${studioId}`,
                        resumeToken,
                        completionPolicy: 'configure_only',
                    },
                });
                if (result?.outcome === 'configured' && result.session?.id) {
                    await window.AI2AppsCapabilities.acknowledge(result.session.id, { appId: studioId });
                }
                return result;
            } finally {
                clearPendingSetup(studioId);
            }
        },
        pendingSetup,
        async resumeSetup(studioId, miniApps = []) {
            if (!window.AI2AppsCapabilities?.resume) return null;
            const pending = pendingSetup(studioId);
            try {
                const result = await window.AI2AppsCapabilities.resume(studioId, { actionId: 'setup-mini-app' });
                if (result?.outcome === 'configured' && result.session?.id) {
                    await window.AI2AppsCapabilities.acknowledge(result.session.id, { appId: studioId });
                }
                const capability = result?.session?.capability || pending?.capability || '';
                const inferred = miniApps.find(item => primaryCapability(item) === capability);
                return result ? { ...result, miniAppId: pending?.miniAppId || inferred?.id || '' } : null;
            } finally {
                if (pending) clearPendingSetup(studioId);
            }
        },
    });
})();
