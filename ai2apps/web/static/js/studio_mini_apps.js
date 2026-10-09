(function () {
    'use strict';

    function appInstanceId() {
        return window.AI2AppsCapabilities?.appInstanceId?.()
            || document.querySelector('[data-app-instance-id]')?.dataset?.appInstanceId
            || new URLSearchParams(window.location.hash.slice(1)).get('ai2apps-instance')
            || '';
    }

    function normalizedLocale(value) {
        const raw = String(value || 'en').trim().replaceAll('_', '-');
        if (!/^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*$/.test(raw)) return 'en';
        return raw.split('-').map((part, index) => {
            if (index === 0) return part.toLowerCase();
            if (part.length === 2 && /^[A-Za-z]+$/.test(part)) return part.toUpperCase();
            if (part.length === 4 && /^[A-Za-z]+$/.test(part)) return part[0].toUpperCase() + part.slice(1).toLowerCase();
            return part.toLowerCase();
        }).join('-');
    }

    function localizedDeclaration(item, locale = document.documentElement.lang) {
        if (!item || typeof item !== 'object') return item;
        const normalized = normalizedLocale(locale);
        const localizations = item.localizations && typeof item.localizations === 'object'
            ? item.localizations : {};
        const byLocale = Object.fromEntries(Object.entries(localizations).map(([key, value]) => [
            String(key).replaceAll('_', '-').toLowerCase(), value,
        ]));
        const language = normalized.split('-', 1)[0].toLowerCase();
        const chineseFallback = /^zh-(HK|MO|Hant)$/i.test(normalized) ? byLocale['zh-tw'] : null;
        const languageDefault = language === 'zh' ? byLocale['zh-cn'] : null;
        const localized = byLocale[normalized.toLowerCase()] || chineseFallback
            || byLocale[language] || languageDefault || {};
        return {
            ...item,
            name: localized.name || item.name,
            summary: localized.summary || item.summary,
            description: localized.description || item.description,
        };
    }

    function taskModelError(value, locale = document.documentElement.lang) {
        const detail = value?.detail || value?.error || value;
        const raw = typeof detail === 'string' ? detail : String(detail?.message || '');
        const code = ['translation_not_ready', 'translation_failed'].includes(detail?.code) ? detail.code : (/translation_not_ready/.test(raw) ? 'translation_not_ready' : /translation_failed/.test(raw) ? 'translation_failed' : '');
        if (!['translation_not_ready', 'translation_failed'].includes(code)) return null;
        const zh = /^zh/i.test(locale || '');
        const simple = (detail?.details?.purpose || raw).includes('work_simple');
        const task = zh ? (simple ? '简单任务' : '标准任务') : (simple ? 'Simple Task' : 'Standard Task');
        if (code === 'translation_not_ready') return zh
            ? `尚未配置“${task}”模型。请打开“模型 → 默认模型”，为“${task}”选择已启用的 BYOK 或本地聊天模型，点击“保存默认设置”，再重试。脱机模式不能使用 Cloud 默认模型。`
            : `No ${task} model is configured. Open Models → Default models, select an enabled BYOK or local chat model for ${task}, save the defaults, then retry. Cloud defaults are unavailable in offline mode.`;
        const status = Number(detail?.details?.upstream_status || raw.match(/HTTP (\d{3})/)?.[1]);
        const advice = status === 401 || status === 403
            ? (zh ? '调用被拒绝。请检查 BYOK 密钥及模型访问权限；如果聊天可用而此处仍失败，请反馈此错误以检查系统调用权限。' : 'Access was denied. Check the BYOK key and model permissions. If Chat works but this workflow fails, report this error for a system permission check.')
            : status === 429
                ? (zh ? '请求受限。请检查供应商额度或用量限制，稍后重试。' : 'The request was limited. Check provider quota or rate limits, then retry later.')
                : (zh ? '请检查该模型能否正常聊天；确认供应商连接或本地模型运行状态，或在默认模型设置中换用其他模型后重试。' : 'Check whether the model works in Chat, verify the provider connection or local model status, or choose another default model and retry.');
        return `${zh ? `“${task}”模型调用失败` : `${task} model request failed`}${status ? ` (HTTP ${status})` : ''}。${advice}`;
    }

    async function payload(response) {
        const value = await response.json().catch(() => null);
        if (!response.ok) throw new Error(value?.error?.message || value?.detail?.message || value?.detail || `Request failed (${response.status})`);
        return value;
    }

    async function readAvatarInput(request, signal) {
        const ref = request.reference;
        const kind = request.kind;
        if (!['image', 'audio'].includes(kind) || !ref) throw new Error('Invalid avatar input');
        const identifier = value => typeof value === 'string' && /^[a-zA-Z0-9_-]{1,200}$/.test(value);
        const get = url => fetch(url, {credentials: 'same-origin', cache: 'no-store', signal});
        let url, name;
        if (ref.source === 'gallery' && identifier(ref.assetId)) {
            const asset = await payload(await get(`/v1/platform/gallery/assets/${encodeURIComponent(ref.assetId)}`));
            if (asset.kind !== kind) throw new Error('素材类型与槽位不匹配');
            url = `/v1/platform/gallery/assets/${encodeURIComponent(ref.assetId)}/content`;
            name = asset.name;
        } else if (ref.source === 'image-output' && kind === 'image' && identifier(ref.artifactId) && identifier(ref.appInstanceId)) {
            const runs = await payload(await fetch('/v1/platform/imagine-studio/runs?limit=100', {
                credentials: 'same-origin', cache: 'no-store', signal, headers: {'X-AI2Apps-App-Instance': ref.appInstanceId},
            }));
            const artifact = runs.items?.flatMap(run => run.artifacts || []).find(item => item.id === ref.artifactId);
            const parsed = new URL(artifact?.previewUrl || '/', location.origin);
            if (parsed.origin !== location.origin || !/^\/v1\/platform\/imagine-studio\/results\/isr_[0-9a-f]{32}\/content$/.test(parsed.pathname) || parsed.searchParams.get('appInstanceId') !== ref.appInstanceId) throw new Error('图片输出不可用');
            url = parsed.href; name = artifact.name;
        } else if (ref.source === 'audio-output' && kind === 'audio' && identifier(ref.sessionId) && identifier(ref.artifactId)) {
            const outputs = await payload(await get('/v1/platform/readaloud/outputs'));
            const expected = `/v1/platform/sessions/${encodeURIComponent(ref.sessionId)}/artifacts/${encodeURIComponent(ref.artifactId)}/download`;
            const item = outputs.items?.find(item => item.downloadUrl === expected && item.mediaType?.startsWith('audio/'));
            if (!item) throw new Error('声音输出不可用');
            url = expected; name = (item.title || 'speech') + '.wav';
        } else throw new Error('素材来源或类型不支持');
        const response = await get(url);
        if (!response.ok) throw new Error('无法读取素材');
        const type = (response.headers.get('content-type') || '').split(';')[0];
        const limit = (kind === 'image' ? 20 : 100) * 1024 * 1024;
        if (kind === 'image' ? !['image/png','image/jpeg','image/webp'].includes(type) : !type.startsWith('audio/')) throw new Error('素材类型与槽位不匹配');
        if (Number(response.headers.get('content-length')) > limit) throw new Error('素材超过槽位大小限制');
        const reader = response.body.getReader(), chunks = [];
        let size = 0;
        try {
            while (true) {
                const {done, value} = await reader.read();
                if (done) break;
                size += value.byteLength;
                if (size > limit) throw new Error('素材超过槽位大小限制');
                chunks.push(value);
            }
        } finally { await reader.cancel(); }
        if (!size) throw new Error('素材为空');
        return {body: new Blob(chunks, {type}), name: String(name || (kind === 'image' ? 'portrait.png' : 'speech.wav')).replace(/[\\/]/g, '-')};
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
    const mediaCapabilities = new Set(['video.avatar_generation', 'audio.detailed_transcription', 'audio.source_separation',
        'media.video_subtitles', 'media.video_audio_translation',
        'audio.speaker_voice_replacement', 'media.video_speaker_voice_replacement']);
    const audioGenerationCapabilities = new Set(['audio.music_generation', 'audio.sound_effects_generation', 'audio.song_generation']);
    const setupCapabilities = new Set([...mediaCapabilities, ...audioGenerationCapabilities, 'audio.voice_clone']);
    const progressCapabilities = new Set([
        'video.avatar_generation',
        'media.video_subtitles',
        'media.video_audio_translation',
    ]);
    const formFields = new Set(['avatar_model_id', 'avatar_resolution', 'file', 'reference', 'profile', 'language', 'word_timestamps', 'diarization', 'output_format',
        'source_language', 'target_language', 'subtitle_format', 'subtitle_action', 'subtitle_segments', 'bilingual', 'burn_in', 'speaker_labels',
        'subtitle_font_size', 'subtitle_background', 'voice_profile_id', 'voice_clone_model_id', 'asr_verification',
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
        let avatarJobsState = "";
        const downloads = new Set();
        const progressSources = new Set();
        let audioRecorder = null;
        let audioGenerationAbort = null;
        const abort = new AbortController();
        const active = () => !closed && frame.isConnected && frame.src === src && frame.contentWindow === source;
        const close = () => {
            closed = true; abort.abort(); audioGenerationAbort?.abort();
            audioRecorder?.dispose();
            progressSources.forEach(source => source.close()); progressSources.clear();
            channel.port1.close(); observer.disconnect(); localeObserver.disconnect();
            frame.removeEventListener('load', revoke);
        };
        const revoke = () => { mountedFrames.delete(src); close(); };
        const observer = new MutationObserver(() => { if (!active()) revoke(); });
        const localeObserver = new MutationObserver(() => {
            if (active()) channel.port1.postMessage({type: 'ai2apps:studio-locale', locale: document.documentElement.lang || 'en'});
        });
        localeObserver.observe(document.documentElement, {attributes: true, attributeFilter: ['lang']});
        observer.observe(frame, {attributes: true, attributeFilter: ['src']});
        observer.observe(document.documentElement, {childList: true, subtree: true});
        frame.addEventListener('load', revoke);
        channels.set(frame, close);
        const base = `/v1/platform/studios/${encodeURIComponent(binding.studioId)}/mini-app-mounts/${encodeURIComponent(binding.mountId)}`;
        const storageKey = `ai2apps.studio-draft.v1:${binding.owner}:${binding.provider}:${binding.resource}`;
        channel.port1.onmessage = async message => {
            const request = message.data;
            let progressSource = null;
            if (!active()) { close(); return; }
            if (!Number.isSafeInteger(request?.id) || request.id < 1) return;
            const reply = value => { if (active()) channel.port1.postMessage({id: request.id, ...value}); };
            if (request.operation === 'audio-generation.cancel') {
                // A private channel may cancel only its own in-flight generation.
                audioGenerationAbort?.abort(); reply({value: {cancelled: !!audioGenerationAbort}}); return;
            }
            if (busy) { reply({error: 'A Mini-App operation is already running'}); return; }
            busy = true;
            if (request.operation === 'audio-generation.generate') audioGenerationAbort = new AbortController();
            try {
                // Revalidate actor, live mount and signed declaration for every operation,
                // including draft access; the iframe never receives session credentials.
                const probe = await payload(await fetch(`${base}/capabilities`, {
                    credentials: 'same-origin', cache: 'no-store', signal: abort.signal,
                }));
                if (!active()) return;
                if (request.operation === 'probe') reply({value: probe});
                else if (request.operation === 'audio-generation.models' || request.operation === 'audio-generation.generate') {
                    if (binding.studioId !== 'ai2apps.readaloud' || !audioGenerationCapabilities.has(request.capability)
                        || !probe.items?.some(item => item.capability === request.capability)) throw new Error('Capability is not allowed');
                    if (request.operation === 'audio-generation.models') {
                        reply({value: await payload(await fetch(`${base}/audio-generation-models?capability=${encodeURIComponent(request.capability)}`,
                            {credentials: 'same-origin', signal: abort.signal, cache: 'no-store'}))});
                    } else {
                        if (!request.payload || JSON.stringify(request.payload).length > (request.capability === 'audio.song_generation' ? 524288 : 20000)) throw new Error('Invalid generation request');
                        if (audioGenerationAbort.signal.aborted) throw new Error('Generation cancelled');
                        let invocationId = '';
                        window.dispatchEvent(new CustomEvent('ai2apps:studio-output-state', {detail: {studioId: binding.studioId, running: true}}));
                        try {
                            if (request.capability === 'audio.song_generation') {
                                const invocation = await payload(await fetch(`${base}/invocations`, {method:'POST', credentials:'same-origin',
                                    signal:audioGenerationAbort.signal, headers:{'Content-Type':'application/json'},
                                    body:JSON.stringify({capability:request.capability})}));
                                if (!/^[0-9a-f]{32}$/.test(invocation.id || '')) throw new Error('Invalid progress invocation');
                                invocationId = invocation.id;
                                const eventsUrl = new URL(invocation.eventsUrl, location.origin);
                                if (eventsUrl.origin !== location.origin || eventsUrl.pathname !== `${base}/invocations/${invocationId}/events`) throw new Error('Invalid progress URL');
                                progressSource = new EventSource(eventsUrl.href, {withCredentials:true});
                                progressSources.add(progressSource);
                                progressSource.addEventListener('progress', event => {
                                    try { const progress=JSON.parse(event.data);
                                        if(active() && progress.invocationId===invocationId) channel.port1.postMessage({type:'ai2apps:studio-progress',progress});
                                    } catch (_) {}
                                });
                            }
                            const result = await payload(await fetch(`${base}/audio-generation`, {method:'POST', credentials:'same-origin',
                                signal:audioGenerationAbort.signal, headers:{'Content-Type':'application/json',...(invocationId?{'X-AI2Apps-Invocation-ID':invocationId}:{})},
                                body:JSON.stringify({...request.payload, capability:request.capability})}));
                            const url = new URL(result.downloadUrl, location.origin);
                            if (url.origin !== location.origin || !/^\/v1\/platform\/sessions\/[^/]+\/artifacts\/[^/]+\/download$/.test(url.pathname)) throw new Error('Invalid output URL');
                            window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail:{studioId:binding.studioId,miniAppId:binding.miniAppId,result}}));
                            reply({value:{completed:true, durationSeconds:result.durationSeconds, reachedLimit:result.reachedLimit === true, preparedPrompt:result.preparedPrompt}});
                        } finally {
                            if (progressSource) { progressSource.close(); progressSources.delete(progressSource); }
                            audioGenerationAbort = null;
                            window.dispatchEvent(new CustomEvent('ai2apps:studio-output-state', {detail:{studioId:binding.studioId,running:false}}));
                        }
                    }
                }
                else if (['avatar.record.start', 'avatar.record.stop', 'avatar.record.cancel'].includes(request.operation)) {
                    if (binding.studioId !== 'ai2apps.video-studio' || !probe.items?.some(item => item.capability === 'video.avatar_generation')) throw new Error('Capability is not allowed');
                    if (request.operation === 'avatar.record.start') {
                        if (audioRecorder?.pending || audioRecorder?.recorder?.state === 'recording') throw new Error('recording_busy');
                        audioRecorder?.dispose();
                        audioRecorder = new window.AI2AppsStudioAudioRecorder();
                        reply({value: await audioRecorder.start(request.maxSeconds)});
                    } else if (request.operation === 'avatar.record.stop') {
                        if (!audioRecorder) throw new Error('recording_empty');
                        reply({value: await audioRecorder.stop()});
                    } else { audioRecorder?.dispose(); audioRecorder = null; reply({value:{cancelled:true}}); }
                }
                else if (request.operation === 'avatar.input.read') {
                    if (binding.studioId !== 'ai2apps.video-studio' || !probe.items?.some(item => item.capability === 'video.avatar_generation')) throw new Error('Capability is not allowed');
                    reply({value: await readAvatarInput(request, abort.signal)});
                }
                else if (['avatar.models', 'avatar.jobs', 'avatar.cancel', 'avatar.retry'].includes(request.operation)) {
                    if (!probe.items?.some(item => item.capability === 'video.avatar_generation')) throw new Error('Capability is not allowed');
                    let suffix = request.operation === 'avatar.models' ? 'models' : 'jobs';
                    const cancelling = ['avatar.cancel', 'avatar.retry'].includes(request.operation);
                    if (cancelling) {
                        if (typeof request.jobId !== 'string' || !/^[a-zA-Z0-9_-]{1,100}$/.test(request.jobId)) throw new Error('Invalid avatar job');
                        suffix = `jobs/${encodeURIComponent(request.jobId)}/${request.operation === "avatar.retry" ? "retry" : "cancel"}`;
                    }
                    const result = await payload(await fetch(`${base}/avatar/${suffix}`, {
                        method: cancelling ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', signal: abort.signal,
                    }));
                    if (request.operation !== 'avatar.models') {
                        const nextState = JSON.stringify(result);
                        if (nextState !== avatarJobsState) window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail: {studioId: binding.studioId, miniAppId: binding.miniAppId}}));
                        avatarJobsState = nextState;
                    }
                    reply({value: result});
                }
                else if (request.operation === 'output.read') {
                    if (binding.studioId !== 'ai2apps.readaloud') throw new Error('Output source is not allowed');
                    const reference = request.reference;
                    const history = await payload(await fetch('/v1/platform/readaloud/outputs', {credentials: 'same-origin', signal: abort.signal}));
                    const expected = `/v1/platform/sessions/${encodeURIComponent(reference?.sessionId || '')}/artifacts/${encodeURIComponent(reference?.artifactId || '')}/download`;
                    const item = history.items?.find(item => item.downloadUrl === expected && item.mediaType?.startsWith('audio/'));
                    if (!item) throw new Error('Unknown Studio audio output');
                    const response = await fetch(item.downloadUrl, {credentials: 'same-origin', signal: abort.signal});
                    if (!response.ok) throw new Error('Could not read Studio output');
                    reply({value: {body: await response.blob(), name: item.title + '.wav'}});
                }
                else if (request.operation === 'export.text') {
                    if (typeof request.content !== 'string' || new TextEncoder().encode(request.content).length > 4 * 1024 * 1024) throw new Error('Export exceeds 4 MiB');
                    const result = await payload(await fetch(`${base}/exports`, {
                        method: 'POST', credentials: 'same-origin', signal: abort.signal,
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({filename: request.filename, content: request.content}),
                    }));
                    const url = new URL(result.downloadUrl, location.origin);
                    if (url.origin !== location.origin || !/^\/v1\/platform\/sessions\/[^/]+\/artifacts\/[^/]+\/download$/.test(url.pathname)) throw new Error('Invalid export URL');
                    downloads.add(result.downloadUrl);
                    window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail: {studioId: binding.studioId, miniAppId: binding.miniAppId, result}}));
                    const link = document.createElement('a');
                    link.href = result.downloadUrl; link.download = result.filename;
                    document.body.append(link); link.click(); link.remove();
                    reply({value: {started: true}});
                }
                else if (request.operation === 'download') {
                    if (!downloads.has(request.url)) throw new Error('Unknown Mini-App output');
                    const link = document.createElement('a');
                    link.href = request.url; link.download = ''; document.body.append(link);
                    link.click(); link.remove();
                    reply({value: {started: true}});
                }
                else if (request.operation === 'setup') {
                    if (!setupCapabilities.has(request.capability) || !probe.items?.some(item => item.capability === request.capability)) throw new Error('Capability is not allowed');
                    const result = await window.AI2AppsStudioMiniApps.setup(binding.studioId, {
                        id: binding.miniAppId,
                        requirements: {capabilities: [request.capability]},
                    }, {installMore: request.installMore === true});
                    reply({value: {outcome: result?.outcome || 'cancelled'}});
                }
                else if (request.operation === 'characters.list') {
                    if (!probe.items?.some(item => item.capability === 'audio.speech_generation')) throw new Error('Character access is not allowed');
                    reply({value: await payload(await fetch(`${base}/characters`, {
                        credentials: 'same-origin', cache: 'no-store', signal: abort.signal,
                    }))});
                }
                else if (request.operation === 'voice-clone-models.list') {
                    if (!probe.items?.some(item => item.capability === 'audio.voice_clone')) throw new Error('Voice-clone model access is not allowed');
                    reply({value: await payload(await fetch(`${base}/voice-clone-models`, {
                        credentials: 'same-origin', cache: 'no-store', signal: abort.signal,
                    }))});
                }
                else if (['subtitle.refine', 'subtitle.profiles.get', 'subtitle.profiles.set'].includes(request.operation)) {
                    if (!probe.items?.some(item => item.capability === 'media.video_subtitles')) throw new Error('Subtitle access is not allowed');
                    const profileKey = storageKey + ':correction-profiles';
                    if (request.operation === 'subtitle.profiles.get') reply({value: JSON.parse(localStorage.getItem(profileKey) || '[]')});
                    else if (request.operation === 'subtitle.profiles.set') {
                        const profiles = request.profiles;
                        if (!Array.isArray(profiles) || profiles.length > 100 || profiles.some(p => !p || typeof p.id !== 'string' || p.id.length > 100 || typeof p.name !== 'string' || !p.name.trim() || p.name.length > 100 || typeof p.rules !== 'string' || p.rules.length > 8000)) throw new Error('Invalid correction profiles');
                        localStorage.setItem(profileKey, JSON.stringify(profiles.map(({id,name,rules}) => ({id,name,rules}))));
                        reply({value: null});
                    } else {
                        const body = JSON.stringify({segments: request.segments, rules: request.rules});
                        if (new TextEncoder().encode(body).length > 2 * 1024 * 1024) throw new Error('Subtitle text exceeds 2 MiB');
                        reply({value: await payload(await fetch(`${base}/subtitle-refinement`, {method:'POST', credentials:'same-origin', signal:abort.signal, headers:{'Content-Type':'application/json'}, body}))});
                    }
                }
                else if (request.operation === 'draft.get') reply({value: localStorage.getItem(storageKey)});
                else if (request.operation === 'draft.remove') { localStorage.removeItem(storageKey); reply({value: null}); }
                else if (request.operation === 'draft.set') {
                    if (typeof request.value !== 'string' || new TextEncoder().encode(request.value).length > 4 * 1024 * 1024) throw new Error('Draft exceeds 4 MiB');
                    const draft = JSON.parse(request.value);
                    if (draft?.schema !== 'ai2apps.mini-app-draft/v1' || draft.miniApp !== binding.miniAppId) throw new Error('Invalid Mini-App draft');
                    localStorage.setItem(storageKey, request.value); reply({value: null});
                } else if (request.operation === 'invoke') {
                    if (!mediaCapabilities.has(request.capability) || !probe.items?.some(item => item.capability === request.capability)) throw new Error('Capability is not allowed');
                    if (!Array.isArray(request.fields) || request.fields.length > 24) throw new Error('Invalid media fields');
                    const body = new FormData();
                    const names = new Set();
                    for (const entry of request.fields) {
                        if (!Array.isArray(entry) || entry.length !== 2) throw new Error('Invalid field');
                        const [name, value] = entry;
                        if (!formFields.has(name) || names.has(name)) throw new Error('Invalid or duplicate field');
                        names.add(name);
                        if (name === 'file' || name === 'reference') {
                            if (!(value instanceof Blob)) throw new Error('Expected media file');
                            const limit = name === 'file' ? 1024 * 1024 * 1024 : 100 * 1024 * 1024;
                            if (value.size === 0) throw new Error('Media input is empty');
                            if (value.size > limit) throw new Error(name === 'file'
                                ? 'Media input exceeds the 1 GiB limit'
                                : 'Reference audio exceeds the 100 MiB limit');
                            body.append(name, value, value.name || 'media.bin');
                        } else {
                            const limit = name === 'subtitle_segments' ? 2 * 1024 * 1024 : 4096;
                            if (typeof value !== 'string' || new TextEncoder().encode(value).length > limit) throw new Error('Invalid option');
                            body.append(name, value);
                        }
                    }
                    if (!names.has('file')) throw new Error('Media file is required');
                    let invocationId = '';
                    if (progressCapabilities.has(request.capability) && request.capability !== 'video.avatar_generation') {
                        const invocation = await payload(await fetch(`${base}/invocations`, {
                            method: 'POST', credentials: 'same-origin', signal: abort.signal,
                            headers: {'Content-Type': 'application/json', Accept: 'application/json'},
                            body: JSON.stringify({capability: request.capability}),
                        }));
                        if (!/^[0-9a-f]{32}$/.test(invocation?.id || '')) throw new Error('Invalid progress invocation');
                        const eventsUrl = new URL(invocation.eventsUrl, location.origin);
                        if (eventsUrl.origin !== location.origin
                            || !eventsUrl.pathname.startsWith(`${base}/invocations/${invocation.id}/events`)) throw new Error('Invalid progress URL');
                        invocationId = invocation.id;
                        progressSource = new EventSource(eventsUrl.href, {withCredentials: true});
                        progressSources.add(progressSource);
                        progressSource.addEventListener('progress', event => {
                            try {
                                const progress = JSON.parse(event.data);
                                if (!active() || progress?.invocationId !== invocationId) return;
                                channel.port1.postMessage({type: 'ai2apps:studio-progress', progress});
                                const terminal = progress.status === 'failed'
                                    || (progress.status === 'completed' && Number(progress.percent) >= 100);
                                if (terminal) {
                                    progressSource.close(); progressSources.delete(progressSource);
                                }
                            } catch (_) {}
                        });
                    }
                    window.dispatchEvent(new CustomEvent('ai2apps:studio-output-state', {detail: {studioId: binding.studioId, running: true}}));
                    const response = await fetch(`${base}/capabilities/${encodeURIComponent(request.capability)}/invoke`, {
                        method: 'POST', credentials: 'same-origin', body,
                        signal: abort.signal,
                        headers: {Accept: 'application/json', ...(invocationId ? {'X-AI2Apps-Invocation-ID': invocationId} : {})},
                    });
                    let responseBody = await response.blob();
                    if (!response.ok) {
                        const failure = await responseBody.text();
                        let value;
                        try { value = JSON.parse(failure); } catch (_) { value = failure; }
                        const message = taskModelError(value);
                        if (message) responseBody = new Blob([JSON.stringify({detail: {message}})], {type: 'application/json'});
                    }
                    if (response.status === 202 && request.capability === 'video.avatar_generation') {
                        window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail: {studioId: binding.studioId, miniAppId: binding.miniAppId}}));
                    }
                    if (response.ok && request.capability === 'audio.source_separation' && response.headers.get('content-type')?.includes('application/json')) {
                        const result = JSON.parse(await responseBody.text());
                        const url = new URL(result.downloadUrl, location.origin);
                        if (url.origin !== location.origin || !/^\/v1\/platform\/sessions\/[^/]+\/artifacts\/[^/]+\/download$/.test(url.pathname)) throw new Error('Invalid output URL');
                        downloads.add(result.downloadUrl);
                        window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail: {studioId: binding.studioId, miniAppId: binding.miniAppId, result}}));
                    }
                    const outputUrl = response.headers.get('X-AI2Apps-Download-URL');
                    const outputRunId = response.headers.get('X-AI2Apps-Studio-Run-ID') || '';
                    if (response.ok && outputUrl) {
                        const url = new URL(outputUrl, location.origin);
                        if (url.origin !== location.origin || !/^\/v1\/platform\/sessions\/[^/]+\/artifacts\/[^/]+\/download$/.test(url.pathname)) throw new Error('Invalid output URL');
                        downloads.add(outputUrl);
                        window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail: {studioId: binding.studioId, miniAppId: binding.miniAppId, result: {downloadUrl: outputUrl, runId: outputRunId}}}));
                    }
                    reply({value: {status: response.status, body: responseBody,
                        headers: {'x-ai2apps-download-url': outputUrl || '', 'content-type': response.headers.get('content-type') || '',
                            'content-disposition': response.headers.get('content-disposition') || ''}}});
                } else throw new Error('Unknown Mini-App operation');
            } catch (error) { reply({error: error?.message || 'Mini-App operation failed'}); }
            finally {
                busy = false;
                if (request.operation === 'audio-generation.generate') audioGenerationAbort = null;
                if (request.operation === 'invoke') {
                    window.dispatchEvent(new CustomEvent('ai2apps:studio-output-state', {detail: {studioId: binding.studioId, running: false}}));
                    if (progressSource && progressSources.has(progressSource)) {
                        const cleanupTimer = setTimeout(() => { progressSource.close(); progressSources.delete(progressSource); }, 30000);
                        cleanupTimer?.unref?.();
                    }
                }
            }
        };
        source.postMessage({type: 'ai2apps:studio-connected', version: 1, locale: document.documentElement.lang || 'en'}, '*', [channel.port2]);
    });

    window.AI2AppsStudioMiniApps = Object.freeze({
        async list(studioId) {
            const catalog = await payload(await fetch(`/v1/platform/studios/${encodeURIComponent(studioId)}/mini-apps`, {
                credentials: 'same-origin', headers: { Accept: 'application/json' }, cache: 'no-store',
            }));
            return {
                ...catalog,
                items: (catalog?.items || []).map(item => item?.source === 'package'
                    ? localizedDeclaration(item, document.documentElement.lang)
                    : item),
            };
        },
        async mount(studioId, miniAppId, { placement = 'inline', context = {} } = {}) {
            const instanceId = appInstanceId();
            if (!instanceId) throw new Error('Studio App instance is unavailable');
            const locale = normalizedLocale(context.locale || document.documentElement.lang || navigator.language);
            const mountContext = {...context, locale};
            const mount = await payload(await fetch(`/v1/platform/studios/${encodeURIComponent(studioId)}/mini-app-mounts`, {
                method: 'POST', credentials: 'same-origin',
                headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-AI2Apps-App-Instance': instanceId },
                body: JSON.stringify({ miniAppId, placement, context: mountContext }),
            }));
            const url = new URL(mount.content_url, location.origin);
            if (url.origin !== location.origin) throw new Error('Invalid Mini-App content origin');
            url.searchParams.set('locale', locale);
            mount.content_url = `${url.pathname}${url.search}${url.hash}`;
            if (mountedFrames.size >= 128) mountedFrames.delete(mountedFrames.keys().next().value);
            mountedFrames.set(url.href, {studioId, mountId: mount.id, miniAppId,
                owner: instanceId, provider: mount.app_instance_id, resource: mount.resource, locale});
            return mount;
        },
        localize(item, locale) { return localizedDeclaration(item, locale); },
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
        async setup(studioId, miniApp, {installMore = false} = {}) {
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
                }, {installMore});
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
