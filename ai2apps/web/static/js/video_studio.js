(function () {
    'use strict';
    const PROVIDERS_API = '/v1/platform/video-studio/providers';
    const DRAFTS_API = '/v1/platform/video-studio/drafts';
    const TASKS_API = '/v1/videos/generations';
    const APP_ID = 'ai2apps.video-studio';
    const terminal = new Set(['succeeded', 'failed', 'cancelled', 'expired']);
    const PIPELINES = Object.freeze([
        Object.freeze({ id: 'ai2apps.video.text-to-video', mode: 't2v', key: 'video_studio.pipeline.t2v', icon: 'type' }),
        Object.freeze({ id: 'ai2apps.video.image-to-video', mode: 'i2v', key: 'video_studio.pipeline.i2v', icon: 'image' }),
        Object.freeze({ id: 'ai2apps.video.reference-to-video', mode: 'r2v', key: 'video_studio.pipeline.r2v', icon: 'scan-search' }),
    ]);

    function tr(key, values = {}) {
        let text = typeof window.t === 'function' ? window.t(key) : key;
        Object.entries(values).forEach(([name, value]) => { text = text.replaceAll(`{${name}}`, String(value)); });
        return text;
    }

    function localizedPipeline(pipeline) {
        return {
            ...pipeline,
            name: tr(`${pipeline.key}.name`), summary: tr(`${pipeline.key}.summary`),
            description: tr(`${pipeline.key}.description`), actionTitle: tr(`${pipeline.key}.action`),
            runLabel: tr(`${pipeline.key}.run`),
        };
    }

    function isTemporarilyDisabledProvider(provider) {
        const id = String(provider?.id || '').toLowerCase();
        const family = String(provider?.family || '').toLowerCase().replaceAll('_', '-');
        const precision = String(provider?.precision || '').toLowerCase().replaceAll('_', '-');
        const isH3 = ['minimax-h3', 'h3'].includes(family) || id.includes('minimax-h3');
        return isH3 && (['bf16', 'fp16', 'f16', '16bit', '16-bit'].includes(precision) || id.includes('/fl2va-bf16') || id.includes('/fl2va-fp16'));
    }

    async function responsePayload(response) {
        const payload = await response.json().catch(() => null);
        if (!response.ok) {
            throw new Error(payload?.error?.message || payload?.detail?.message || payload?.detail || tr('video_studio.error.request_failed', { status: response.status }));
        }
        return payload;
    }

    window.videoStudioApp = function () { return {
        refreshing: false, submitting: false, batchSubmitting: false, polling: false, joining: false, addingToGallery: false, galleryAdded: false,
        notice: '', noticeTone: 'error', providers: [], modelId: '', tasks: [], selectedTaskId: '',
        dismissed: [], pollTimer: null, mode: 't2v', prompt: '', resolution: '512x512', duration: 5,
        preset: 'strict', steps: 20, seed: 42, label: '', firstFile: null, lastFile: null,
        firstPreview: '', lastPreview: '', referenceImages: [], referenceVideos: [], referenceAudios: [], referenceOrder: [],
        batchText: '', joinedVideoUrl: '', clientEnvironment: 'browser', leftView: 'pipelines',
        galleryMiniUrl: '', galleryMiniMountId: '', galleryMiniLoading: false, galleryMiniError: '', galleryDragActive: false, gallerySlotTarget: '',
        galleryActiveCollectionId: 'recent', galleryActiveCollectionName: 'Recent', galleryMessageHandler: null, galleryAddedTimer: null,
        tr,
        get pipelines() { return PIPELINES.map(localizedPipeline); },
        get selectedProvider() { return this.providers.find(item => item.id === this.modelId) || null; },
        get currentPipeline() { return this.pipelineForMode(this.mode); },
        get modeProviders() {
            const wantsReference = this.mode === 'r2v';
            return this.providers.filter(item => Boolean(item.capabilities?.includes('reference_to_video')) === wantsReference);
        },
        get caps() { return this.selectedProvider?.videoCapabilities || {}; },
        get resolutions() { return this.caps.geometry?.resolutions || ['512x512']; },
        get presets() { return this.caps.presets?.length ? this.caps.presets : [{ id: 'strict', display_name: 'Strict' }]; },
        get durationMin() { return Number(this.caps.duration?.minimum_seconds ?? 1); },
        get durationMax() { return Number(this.caps.duration?.maximum_seconds ?? 15); },
        get frameNote() { const fps = Number(this.caps.defaults?.framespersecond || 24); return tr('video_studio.frame_note', { frames: Math.max(1, Math.round(this.duration * fps)), fps }); },
        get canGenerate() {
            if (!this.prompt.trim()) return false;
            if (this.mode === 'i2v') return Boolean(this.firstFile);
            if (this.mode === 'r2v') return Boolean(this.referenceImages.length || this.referenceVideos.length);
            return true;
        },
        get needsConfiguration() { return !this.selectedProvider?.ready || !this.modeProviders.some(item => item.id === this.modelId); },
        get canPrimaryAction() { return this.needsConfiguration || this.canGenerate; },
        get visibleTasks() { return this.tasks.filter(task => !this.dismissed.includes(task.id)); },
        get activeTask() { return this.visibleTasks.find(task => task.id === this.selectedTaskId) || this.visibleTasks.find(task => task.status === 'succeeded') || null; },
        get activeVideoUrl() { return this.joinedVideoUrl || this.activeTask?.result?.video?.download_url || ''; },
        get completedTasks() { return this.visibleTasks.filter(task => task.status === 'succeeded').slice().reverse(); },
        get queueSummary() { const active = this.visibleTasks.filter(task => !terminal.has(task.status)).length; return tr('video_studio.queue_summary', { count: this.visibleTasks.length }) + (active ? tr('video_studio.queue_active', { count: active }) : ''); },
        get presetHelp() { return tr(this.preset === 'strict' ? 'video_studio.preset.strict_help' : this.preset === 'fast_max' ? 'video_studio.preset.fast_max_help' : 'video_studio.preset.fast_help'); },

        async init() {
            this.clientEnvironment = this.$root?.dataset?.clientEnvironment || 'browser';
            this.galleryMessageHandler = event => this.handleGalleryMessage(event);
            window.addEventListener('message', this.galleryMessageHandler);
            try { this.dismissed = JSON.parse(localStorage.getItem('ai2apps-video-studio-dismissed') || '[]'); } catch (_) { this.dismissed = []; }
            await this.refresh();
            try {
                for (const capability of ['video.reference_generation', 'video.generation']) {
                    const resumed = await window.AI2AppsCapabilities?.resume(APP_ID, { capability });
                    if (resumed?.status !== 'ready' || resumed.outcome !== 'configured') continue;
                    const resumeToken = resumed.session?.intent?.resumeToken;
                    await this.finishProvisioning(resumed, resumeToken);
                    this.success(tr(this.mode === 'r2v'
                        ? 'video_studio.success.reference_configured'
                        : 'video_studio.success.video_configured'));
                    break;
                }
            } catch (error) { this.fail(error); }
            this.pollTimer = window.setInterval(() => this.poll(), 2000);
            window.addEventListener('beforeunload', () => this.cleanup(), { once: true });
        },
        cleanup() {
            if (this.pollTimer) clearInterval(this.pollTimer);
            if (this.galleryAddedTimer) clearTimeout(this.galleryAddedTimer);
            if (this.galleryMessageHandler) window.removeEventListener('message', this.galleryMessageHandler);
            this.revokePreview('first'); this.revokePreview('last');
        },
        icons() { this.$nextTick(() => window.lucide?.createIcons()); },
        fail(error) { this.notice = error?.message || String(error); this.noticeTone = 'error'; this.icons(); },
        success(message) { this.notice = message; this.noticeTone = 'success'; this.icons(); },
        downloadArtifact(event, url) {
            if (!url) {
                event.preventDefault();
                this.fail(new Error(tr('video_studio.error.download_unavailable')));
                return;
            }
            // Keep the anchor's native navigation. AceFox opens the macOS Save
            // As panel; regular browsers own their normal download UI/history.
            if (this.clientEnvironment !== 'desktop') {
                this.success(tr('video_studio.success.download_started'));
            }
        },

        async showLeftView(view) {
            this.leftView = view === 'assets' ? 'assets' : 'pipelines';
            if (this.leftView === 'assets' && !this.galleryMiniUrl) await this.mountGalleryMini();
            this.icons();
        },
        async selectPipeline(pipelineId) {
            const pipeline = this.pipelines.find(item => item.id === pipelineId);
            if (!pipeline) return;
            await this.switchMode(pipeline.mode);
            this.leftView = 'pipelines';
        },
        pipelineForMode(mode) { return this.pipelines.find(item => item.mode === mode) || this.pipelines[0]; },
        pipelineReady(pipeline) {
            const wantsReference = pipeline?.mode === 'r2v';
            return this.providers.some(item => item.ready && Boolean(item.capabilities?.includes('reference_to_video')) === wantsReference);
        },
        async mountGalleryMini(force = false) {
            if (this.galleryMiniLoading || (this.galleryMiniUrl && !force)) return;
            this.galleryMiniLoading = true; this.galleryMiniError = '';
            try {
                const bridge = window.ai2appsShell;
                if (!bridge?.mountMiniEntry) {
                    this.galleryMiniUrl = '/admin/app-content/ai2apps.gallery?surface=mini';
                    return;
                }
                const mount = await bridge.mountMiniEntry({
                    appId: 'ai2apps.gallery', placement: 'sidebar', requestedBy: APP_ID,
                });
                if (!mount?.content_url) throw new Error(tr('video_studio.error.gallery_mount_url'));
                this.galleryMiniMountId = mount.id || '';
                this.galleryMiniUrl = mount.content_url;
            } catch (error) {
                if (String(error?.message || '').includes('Unsupported host mount')) {
                    // Compatibility path for an older Desktop Host. The route is
                    // still first-party and principal-scoped; newer hosts return
                    // the same URL through the Mini-Entry mount contract.
                    this.galleryMiniUrl = '/admin/app-content/ai2apps.gallery?surface=mini';
                    this.galleryMiniError = '';
                } else {
                    this.galleryMiniUrl = '';
                    this.galleryMiniError = error?.message || tr('video_studio.error.gallery_load');
                }
            } finally { this.galleryMiniLoading = false; this.icons(); }
        },
        openGallery() {
            if (window.ai2appsShell?.openEntry) window.ai2appsShell.openEntry({ appId: 'ai2apps.gallery' });
            else window.open('/apps/ai2apps.gallery', '_blank', 'noopener');
        },
        handleGalleryMessage(event) {
            if (event.origin !== window.location.origin || event.source !== this.$refs.galleryMini?.contentWindow) return;
            if (event.data?.type !== 'ai2apps.gallery.collection-changed') return;
            const collectionId = String(event.data.collectionId || 'recent');
            this.galleryActiveCollectionId = collectionId;
            this.galleryActiveCollectionName = String(event.data.collectionName || collectionId);
        },
        artifactReference(url, task = null) {
            const parsed = new URL(String(url || ''), window.location.origin);
            const match = parsed.pathname.match(/^\/v1\/platform\/sessions\/([^/]+)\/artifacts\/([^/]+)\/download$/);
            if (parsed.origin !== window.location.origin || !match) throw new Error(tr('video_studio.error.artifact_invalid'));
            const rawName = task ? this.taskTitle(task) : tr('video_studio.joined_video');
            const generatedVideo = tr('video_studio.generated_video');
            const safeName = String(rawName || generatedVideo).replace(/[\\/:*?"<>|]/g, '-').slice(0, 120) || generatedVideo;
            return {
                sessionId: decodeURIComponent(match[1]), artifactId: decodeURIComponent(match[2]),
                name: safeName.toLowerCase().endsWith('.mp4') ? safeName : safeName + '.mp4',
                sourceAppId: APP_ID,
            };
        },
        dragGeneratedVideo(event, url, task = null) {
            if (!url || !event.dataTransfer) { event.preventDefault(); return; }
            try {
                const reference = this.artifactReference(url, this.joinedVideoUrl === url ? null : task);
                event.dataTransfer.effectAllowed = 'copy';
                event.dataTransfer.setData('application/x-ai2apps-video-artifact', JSON.stringify(reference));
                event.dataTransfer.setData('text/uri-list', new URL(url, window.location.origin).href);
                event.dataTransfer.setData('text/plain', reference.name);
            } catch (error) { event.preventDefault(); this.fail(error); }
        },
        async addActiveVideoToGallery() {
            if (!this.activeVideoUrl || this.addingToGallery) return;
            this.addingToGallery = true; this.galleryAdded = false;
            try {
                const reference = this.artifactReference(this.activeVideoUrl, this.joinedVideoUrl ? null : this.activeTask);
                await responsePayload(await fetch(
                    `/v1/platform/gallery/assets/import-artifact/${encodeURIComponent(reference.sessionId)}/${encodeURIComponent(reference.artifactId)}`,
                    {
                        method: 'POST', credentials: 'same-origin',
                        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            collectionId: this.galleryActiveCollectionId === 'recent' ? null : this.galleryActiveCollectionId,
                            name: reference.name, sourceAppId: APP_ID,
                        }),
                    },
                ));
                this.galleryAdded = true;
                this.$refs.galleryMini?.contentWindow?.postMessage({ type: 'ai2apps.gallery.refresh' }, window.location.origin);
                if (this.galleryAddedTimer) clearTimeout(this.galleryAddedTimer);
                this.galleryAddedTimer = setTimeout(() => { this.galleryAdded = false; this.icons(); }, 2200);
            } catch (error) { this.fail(error); } finally { this.addingToGallery = false; this.icons(); }
        },
        handleDragLeave(event) {
            if (!event.currentTarget.contains(event.relatedTarget)) {
                this.galleryDragActive = false;
                this.gallerySlotTarget = '';
            }
        },
        enterGallerySlot(slot) {
            this.galleryDragActive = false;
            this.gallerySlotTarget = slot;
        },
        leaveGallerySlot(event, slot) {
            if (this.gallerySlotTarget === slot && !event.currentTarget.contains(event.relatedTarget)) this.gallerySlotTarget = '';
        },
        async handleGalleryDrop(event, imageSlot = '') {
            this.galleryDragActive = false; this.gallerySlotTarget = '';
            try {
                const localFile = event.dataTransfer?.files?.[0];
                if (localFile) {
                    await this.routeDroppedFile(localFile, imageSlot);
                    return;
                }
                const assetId = event.dataTransfer?.getData('application/x-ai2apps-gallery-asset') || '';
                const uri = String(event.dataTransfer?.getData('text/uri-list') || '').split('\n').find(line => line && !line.startsWith('#')) || '';
                if (!assetId || !uri) return;
                const assetUrl = new URL(uri, window.location.origin);
                if (assetUrl.origin !== window.location.origin || !assetUrl.pathname.startsWith('/v1/platform/gallery/assets/') || !assetUrl.pathname.endsWith('/content')) {
                    throw new Error(tr('video_studio.error.gallery_asset_only'));
                }
                const response = await fetch(assetUrl.href, { credentials: 'same-origin' });
                if (!response.ok) throw new Error(tr('video_studio.error.gallery_asset_read', { status: response.status }));
                const blob = await response.blob();
                const fallbackName = `gallery-${assetId}`;
                const name = String(event.dataTransfer?.getData('text/plain') || fallbackName).replace(/[\\/]/g, '-');
                await this.routeDroppedFile(new File([blob], name, { type: blob.type || response.headers.get('content-type') || '' }), imageSlot);
            } catch (error) { this.fail(error); }
        },
        async routeDroppedFile(file, imageSlot = '') {
            const type = String(file.type || '').toLowerCase();
            if (imageSlot) {
                if (!['first', 'last'].includes(imageSlot)) throw new Error(tr('video_studio.error.image_slot_unknown'));
                if (!type.startsWith('image/')) throw new Error(tr('video_studio.error.image_slot_type'));
                await this.switchMode('i2v');
                this.revokePreview(imageSlot);
                this[imageSlot + 'File'] = file;
                this[imageSlot + 'Preview'] = URL.createObjectURL(file);
                this.icons();
                return;
            }
            if (type.startsWith('image/')) {
                if (this.mode === 'r2v') this.addReferenceFile('image', file);
                else {
                    await this.switchMode('i2v');
                    this.revokePreview('first');
                    this.firstFile = file;
                    this.firstPreview = URL.createObjectURL(file);
                }
            } else if (type.startsWith('video/') || type.startsWith('audio/')) {
                await this.switchMode('r2v');
                const kind = type.startsWith('video/') ? 'video' : 'audio';
                this.addReferenceFile(kind, file);
            } else throw new Error(tr('video_studio.error.asset_type'));
            this.icons();
        },
        addReferenceFile(kind, file) {
            const config = {
                image: { key: 'referenceImages', limit: 9 },
                video: { key: 'referenceVideos', limit: 3 },
                audio: { key: 'referenceAudios', limit: 3 },
            }[kind];
            const total = this.referenceImages.length + this.referenceVideos.length + this.referenceAudios.length;
            if (!config || total >= 12 || this[config.key].length >= config.limit) throw new Error(tr('video_studio.error.reference_limit'));
            const index = this[config.key].length;
            this[config.key] = [...this[config.key], file];
            this.referenceOrder.push({ kind, index });
        },

        async refresh() {
            this.refreshing = true;
            try {
                const [providersResponse, tasksResponse] = await Promise.all([
                    fetch(PROVIDERS_API, { credentials: 'same-origin', headers: { Accept: 'application/json' } }),
                    fetch(TASKS_API + '?limit=100', { credentials: 'same-origin', headers: { Accept: 'application/json' } }),
                ]);
                const providers = await responsePayload(providersResponse);
                const tasks = await responsePayload(tasksResponse);
                this.providers = (providers.items || []).filter(item => !isTemporarilyDisabledProvider(item));
                this.tasks = tasks.data || [];
                if (!this.modeProviders.some(item => item.id === this.modelId)) {
                    const probe = await window.AI2AppsCapabilities?.probe(this.capabilityRequest('probe', ''));
                    const recommendedId = probe?.provider?.modelId || probe?.plan?.stack?.checkpoint?.model_id || '';
                    this.modelId = this.modeProviders.some(item => item.id === recommendedId)
                        ? recommendedId
                        : (this.modeProviders.find(item => item.ready)?.id || this.modeProviders[0]?.id || '');
                }
                this.syncDefaults(false);
                if (!this.selectedTaskId) this.selectedTaskId = this.tasks.find(task => task.status === 'succeeded')?.id || this.tasks[0]?.id || '';
                this.icons();
            } catch (error) { this.fail(error); } finally { this.refreshing = false; }
        },
        async poll() {
            if (this.polling || this.refreshing || !this.tasks.some(task => !terminal.has(task.status))) return;
            this.polling = true;
            try {
                const response = await fetch(TASKS_API + '?limit=100', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
                this.tasks = (await responsePayload(response)).data || [];
                this.icons();
            } catch (error) { this.fail(error); } finally { this.polling = false; }
        },
        syncDefaults(force = true) {
            if (!this.selectedProvider) return;
            const defaults = this.caps.defaults || {};
            if (force || !this.resolutions.includes(this.resolution)) this.resolution = defaults.resolution || this.resolutions[0];
            if (force || !this.presets.some(item => item.id === this.preset)) this.preset = defaults.preset || this.presets[0]?.id || 'strict';
            if (force) this.seed = Number(defaults.seed ?? 42);
            this.duration = Math.min(this.durationMax, Math.max(this.durationMin, Number(this.duration) || 5));
            this.icons();
        },
        setImage(which, event) {
            const file = event.target.files?.[0] || null;
            if (!file) return;
            this.revokePreview(which);
            this[which + 'File'] = file;
            this[which + 'Preview'] = URL.createObjectURL(file);
            this.icons();
        },
        revokePreview(which) { const url = this[which + 'Preview']; if (url) URL.revokeObjectURL(url); this[which + 'Preview'] = ''; },
        clearImage(which) { this.revokePreview(which); this[which + 'File'] = null; },
        setReferences(kind, event) {
            const limits = { Images: 9, Videos: 3, Audios: 3 };
            const key = `reference${kind}`;
            const selectedElsewhere = this.referenceImages.length + this.referenceVideos.length
                + this.referenceAudios.length - this[key].length;
            const available = Math.max(0, 12 - selectedElsewhere);
            this[key] = Array.from(event.target.files || []).slice(0, Math.min(limits[kind], available));
            const singular = kind === 'Images' ? 'image' : kind === 'Videos' ? 'video' : 'audio';
            this.referenceOrder = this.referenceOrder.filter(item => item.kind !== singular);
            this[key].forEach((_, index) => this.referenceOrder.push({ kind: singular, index }));
            this.icons();
        },
        async switchMode(mode) {
            this.mode = mode;
            if (!this.modeProviders.some(item => item.id === this.modelId)) {
                this.modelId = this.modeProviders.find(item => item.ready)?.id || this.modeProviders[0]?.id || '';
            }
            this.syncDefaults(false);
            this.icons();
        },
        randomizeSeed() { this.seed = Math.floor(Math.random() * 2147483646) + 1; },

        provisioningDraft(action) {
            return {
                action, pipelineId: this.currentPipeline.id, mode: this.mode, modelId: this.modelId, prompt: this.prompt, resolution: this.resolution,
                duration: this.duration, preset: this.preset, steps: this.steps,
                seed: this.seed, label: this.label, batchText: this.batchText,
            };
        },
        applyProvisioningDraft(value) {
            if (!value) return null;
            for (const key of ['mode', 'modelId', 'prompt', 'resolution', 'duration', 'preset', 'steps', 'seed', 'label', 'batchText']) {
                if (value[key] !== undefined) this[key] = value[key];
            }
            return value;
        },
        draftHeaders() {
            const instanceId = window.AI2AppsCapabilities?.appInstanceId?.() || '';
            return { Accept: 'application/json', ...(instanceId ? { 'X-AI2Apps-App-Instance': instanceId } : {}) };
        },
        async persistProvisioningDraft(action) {
            const form = new FormData();
            form.append('draft', JSON.stringify(this.provisioningDraft(action)));
            if (this.firstFile) form.append('first_frame', this.firstFile, this.firstFile.name);
            if (this.lastFile) form.append('last_frame', this.lastFile, this.lastFile.name);
            return responsePayload(await fetch(DRAFTS_API, {
                method: 'POST', credentials: 'same-origin', headers: this.draftHeaders(), body: form,
            }));
        },
        async restoreDraftFrame(resumeToken, which, descriptor) {
            if (!descriptor?.contentUrl) return;
            const response = await fetch(descriptor.contentUrl, { credentials: 'same-origin', headers: this.draftHeaders() });
            if (!response.ok) {
                const frame = tr(which === 'first' ? 'video_studio.start_frame' : 'video_studio.end_frame');
                throw new Error(tr('video_studio.error.restore_frame', { frame, status: response.status }));
            }
            const blob = await response.blob();
            const file = new File([blob], descriptor.name || `${which}-frame`, { type: descriptor.mediaType || blob.type });
            this.revokePreview(which);
            this[which + 'File'] = file;
            this[which + 'Preview'] = URL.createObjectURL(file);
        },
        async loadProvisioningDraft(resumeToken) {
            if (!resumeToken) throw new Error(tr('video_studio.error.draft_reference'));
            const record = await responsePayload(await fetch(`${DRAFTS_API}/${encodeURIComponent(resumeToken)}`, {
                credentials: 'same-origin', headers: this.draftHeaders(),
            }));
            this.applyProvisioningDraft(record.draft);
            this.clearImage('first');
            this.clearImage('last');
            await Promise.all([
                this.restoreDraftFrame(resumeToken, 'first', record.frames?.first),
                this.restoreDraftFrame(resumeToken, 'last', record.frames?.last),
            ]);
            return record;
        },
        async deleteProvisioningDraft(resumeToken) {
            if (!resumeToken) return;
            const response = await fetch(`${DRAFTS_API}/${encodeURIComponent(resumeToken)}`, {
                method: 'DELETE', credentials: 'same-origin', headers: this.draftHeaders(),
            });
            if (!response.ok && response.status !== 404) throw new Error(tr('video_studio.error.draft_cleanup', { status: response.status }));
        },
        capabilityRequest(action, preferredModelId = this.modelId, resumeToken = '') {
            const intent = action === 'probe' ? {} : {
                returnTo: `/apps/${APP_ID}`,
                resumeToken,
                completionPolicy: 'configure_only',
            };
            return {
                appId: APP_ID,
                capability: this.mode === 'r2v' ? 'video.reference_generation' : 'video.generation',
                actionId: action,
                requirements: {
                    operations: [this.mode === 'r2v' ? 'reference_to_video' : (this.mode === 'i2v' ? 'image_to_video' : 'text_to_video')],
                    outputFormats: ['mp4'],
                    synchronizedAudio: true,
                    ...(preferredModelId ? { modelId: preferredModelId } : {}),
                },
                intent,
            };
        },
        async finishProvisioning(result, resumeToken) {
            await this.loadProvisioningDraft(resumeToken);
            await this.refresh();
            const resumedModelId = result.provider?.modelId;
            const readyModelId = this.modeProviders.some(item => item.id === resumedModelId && item.ready)
                ? resumedModelId
                : (this.selectedProvider?.ready ? this.modelId : this.modeProviders.find(item => item.ready)?.id);
            if (readyModelId) this.modelId = readyModelId;
            this.syncDefaults(false);
            if (!this.selectedProvider?.ready) throw new Error(tr('video_studio.error.provider_missing'));
            if (result.outcome === 'configured' && result.session?.id) {
                await window.AI2AppsCapabilities.acknowledge(result.session.id, { appId: APP_ID });
            }
            await this.deleteProvisioningDraft(resumeToken);
            return { modelId: this.modelId, configured: result.outcome === 'configured' };
        },
        async ensureVideoCapability(action) {
            if (!this.needsConfiguration) return { modelId: this.modelId, configured: false };
            const stored = await this.persistProvisioningDraft(action);
            let result;
            try {
                result = await window.AI2AppsCapabilities.ensure(
                    this.capabilityRequest(action, this.modelId, stored.resumeToken)
                );
            } catch (error) {
                await this.deleteProvisioningDraft(stored.resumeToken).catch(() => {});
                throw error;
            }
            return this.finishProvisioning(result, stored.resumeToken);
        },

        requestPayload(overrides = {}) {
            const prompt = String(overrides.prompt ?? this.prompt).trim();
            const content = [{ type: 'text', role: 'prompt', text: prompt }];
            if (this.mode === 'i2v' && this.firstFile) content.push({ type: 'image_url', role: 'first_frame', image_url: { url: 'multipart://first_frame' } });
            if (this.mode === 'i2v' && this.lastFile) content.push({ type: 'image_url', role: 'last_frame', image_url: { url: 'multipart://last_frame' } });
            if (this.mode === 'r2v') {
                this.referenceOrder.forEach(({ kind, index }) => {
                    if (kind === 'image') content.push({ type: 'image_url', role: 'reference_image', image_url: { url: `multipart://reference_image_${index}` } });
                    if (kind === 'video') content.push({ type: 'video_url', role: 'reference_video', video_url: { url: `multipart://reference_video_${index}` } });
                    if (kind === 'audio') content.push({ type: 'audio_url', role: 'reference_audio', audio_url: { url: `multipart://reference_audio_${index}` } });
                });
            }
            return {
                model: overrides.model || this.modelId, content,
                resolution: overrides.resolution || this.resolution,
                ratio: this.resolutionRatio(overrides.resolution || this.resolution),
                framespersecond: Number(this.caps.defaults?.framespersecond || 24),
                duration: Number(overrides.duration ?? this.duration), preset: overrides.preset || this.preset,
                seed: Number(overrides.seed ?? this.seed), steps: Number(overrides.steps ?? this.steps),
                metadata: {
                    label: String(overrides.label ?? this.label).trim(), prompt,
                    mode: overrides.mode || this.mode,
                    pipeline_id: this.pipelineForMode(overrides.mode || this.mode).id,
                },
            };
        },
        async submitPayload(payload, files = null) {
            const options = { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' } };
            if (files) {
                const form = new FormData(); form.append('request', JSON.stringify(payload));
                if (files.first) form.append('first_frame', files.first, files.first.name);
                if (files.last) form.append('last_frame', files.last, files.last.name);
                (files.referenceImages || []).forEach((file, index) => form.append(`reference_image_${index}`, file, file.name));
                (files.referenceVideos || []).forEach((file, index) => form.append(`reference_video_${index}`, file, file.name));
                (files.referenceAudios || []).forEach((file, index) => form.append(`reference_audio_${index}`, file, file.name));
                options.body = form;
            } else {
                options.headers['Content-Type'] = 'application/json'; options.body = JSON.stringify(payload);
            }
            return responsePayload(await fetch(TASKS_API, options));
        },
        async generate() {
            if (!this.canPrimaryAction || this.submitting) return;
            this.submitting = true; this.notice = '';
            try {
                const capability = await this.ensureVideoCapability('configure-generation');
                if (capability.configured) {
                    this.success(tr('video_studio.success.configured'));
                    return;
                }
                const files = this.mode === 'i2v'
                    ? { first: this.firstFile, last: this.lastFile }
                    : this.mode === 'r2v'
                        ? { referenceImages: this.referenceImages, referenceVideos: this.referenceVideos, referenceAudios: this.referenceAudios }
                        : null;
                const task = await this.submitPayload(this.requestPayload({ model: capability.modelId }), files);
                this.tasks.unshift(task); this.selectedTaskId = task.id; this.success(tr('video_studio.success.queued'));
            } catch (error) { this.fail(error); } finally { this.submitting = false; this.icons(); }
        },
        async cancel(task) {
            try {
                const updated = await responsePayload(await fetch(TASKS_API + '/' + encodeURIComponent(task.id), { method: 'DELETE', credentials: 'same-origin', headers: { Accept: 'application/json' } }));
                Object.assign(task, updated); this.success(tr('video_studio.success.cancelled'));
            } catch (error) { this.fail(error); }
        },
        selectTask(task) { this.joinedVideoUrl = ''; this.selectedTaskId = task.id; },
        async joinFinished() {
            if (this.joining || this.completedTasks.length < 2) return;
            this.joining = true;
            try {
                const response = await fetch('/v1/videos/joins', { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify({ task_ids: this.completedTasks.map(task => task.id) }) });
                const joined = await responsePayload(response); this.joinedVideoUrl = joined.video.download_url; this.success(tr('video_studio.success.joined', { count: this.completedTasks.length }));
            } catch (error) { this.fail(error); } finally { this.joining = false; this.icons(); }
        },
        clearFinished() {
            const ids = this.tasks.filter(task => terminal.has(task.status)).map(task => task.id);
            this.dismissed = Array.from(new Set([...this.dismissed, ...ids])).slice(-500);
            localStorage.setItem('ai2apps-video-studio-dismissed', JSON.stringify(this.dismissed));
            if (ids.includes(this.selectedTaskId)) this.selectedTaskId = '';
        },
        async loadBatchFile(event) { const file = event.target.files?.[0]; if (file) this.batchText = await file.text(); },
        async importBatch() {
            if (this.batchSubmitting) return;
            this.batchSubmitting = true;
            try {
                const document = JSON.parse(this.batchText);
                if (!Array.isArray(document.scenes) || !document.scenes.length) throw new Error(tr('video_studio.error.batch_scenes'));
                const capability = await this.ensureVideoCapability('configure-batch-import');
                if (capability.configured) {
                    this.success(tr('video_studio.success.batch_configured'));
                    return;
                }
                const defaults = document.defaults || {}; let count = 0;
                for (const scene of document.scenes) {
                    if ((scene.mode || 't2v') !== 't2v') throw new Error(tr('video_studio.error.batch_mode', { count: count + 1 }));
                    if (typeof scene.prompt !== 'string' || !scene.prompt.trim() || typeof scene.duration_sec !== 'number' || !Number.isFinite(scene.duration_sec)) throw new Error(tr('video_studio.error.batch_scene', { count: count + 1 }));
                    const payload = this.requestPayload({
                        model: capability.modelId, mode: 't2v', prompt: scene.prompt, label: scene.label || tr('video_studio.scene_label', { count: count + 1 }),
                        duration: scene.duration_sec, resolution: scene.resolution || defaults.resolution,
                        steps: scene.steps ?? defaults.steps, seed: scene.seed ?? defaults.seed ?? this.seed,
                        preset: scene.preset || defaults.preset || this.preset,
                    });
                    payload.content = [{ type: 'text', role: 'prompt', text: String(scene.prompt || '').trim() }];
                    this.tasks.unshift(await this.submitPayload(payload)); count += 1;
                }
                this.selectedTaskId = this.tasks[0]?.id || ''; this.success(tr('video_studio.success.batch_queued', { count }));
            } catch (error) { this.fail(error); } finally { this.batchSubmitting = false; this.icons(); }
        },

        providerLabel(provider) { return `${provider.displayName}${provider.ready ? '' : tr('video_studio.provider.setup')}`; },
        modelDetail(provider) { return [provider?.precision, provider?.residency === 'staged' ? tr('video_studio.residency.staged') : provider?.residency].filter(Boolean).join(' · '); },
        resolutionRatio(value) {
            const [width, height] = value.split('x').map(Number);
            const ratios = this.caps.geometry?.ratios || [];
            return ratios.reduce((closest, candidate) => {
                const [ratioWidth, ratioHeight] = candidate.split(':').map(Number);
                const distance = Math.abs(width / height - ratioWidth / ratioHeight);
                return !closest || distance < closest.distance ? { value: candidate, distance } : closest;
            }, null)?.value || '1:1';
        },
        resolutionLabel(value) { return `${value} · ${this.resolutionRatio(value)}`; },
        presetLabel(item) { return item.display_name || ({ strict: tr('video_studio.preset.strict'), fast: tr('video_studio.preset.fast'), fast_max: tr('video_studio.preset.fast_max') }[item.id] || item.id); },
        isActive(task) { return !terminal.has(task.status); },
        taskTitle(task) { return task.metadata?.label || task.metadata?.prompt?.slice(0, 36) || tr('video_studio.untitled'); },
        statusIcon(status) { return ({ queued: 'clock-3', running: 'loader-circle', succeeded: 'check', failed: 'triangle-alert', cancelled: 'ban' }[status] || 'circle'); },
        statusLabel(status) { return ['queued', 'running', 'succeeded', 'failed', 'cancelled', 'expired'].includes(status) ? tr(`video_studio.status.${status}`) : status; },
        phaseLabel(phase) { return ['queued', 'loading', 'encoding', 'denoising', 'decoding', 'audio', 'muxing', 'completed'].includes(phase) ? tr(`video_studio.phase.${phase}`) : phase || tr('video_studio.phase.waiting'); },
        timeLabel(value) { if (!value) return ''; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString([], { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }); },
    }; };
})();
