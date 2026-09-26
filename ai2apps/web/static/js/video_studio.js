(function () {
    'use strict';
    const STUDIO_API = '/v1/platform/video-studio';
    const PROVIDERS_API = STUDIO_API + '/providers';
    const DRAFTS_API = STUDIO_API + '/drafts';
    const TASKS_API = '/v1/videos/generations';
    const APP_ID = 'ai2apps.video-studio';
    const INSTALL_MORE_MODEL_ID = '__install_more__';
    const terminal = new Set(['succeeded', 'failed', 'cancelled', 'expired']);
    const SHELL_STATE_KEY = 'ai2apps-video-studio-shell-v1';
    const GALLERY_MINI_FALLBACK_URL = '/admin/app-content/ai2apps.gallery?surface=mini';
    const MINI_APPS = Object.freeze([
        Object.freeze({ id: 'ai2apps.video.text-to-video', mode: 't2v', key: 'video_studio.mini_app.t2v', icon: 'type' }),
        Object.freeze({ id: 'ai2apps.video.image-to-video', mode: 'i2v', key: 'video_studio.mini_app.i2v', icon: 'image' }),
        Object.freeze({ id: 'ai2apps.video.reference-to-video', mode: 'r2v', key: 'video_studio.mini_app.r2v', icon: 'scan-search' }),
        Object.freeze({ id: 'ai2apps.video.composer', mode: 'composer', key: 'video_studio.mini_app.composer', icon: 'panels-top-left' }),
        Object.freeze({ id: 'ai2apps.video.extract-audio', mode: 'x2a', key: 'video_studio.mini_app.x2a', icon: 'audio-lines' }),
    ]);
    const COMPOSER_CLIP_COLORS = Object.freeze(['#2563eb', '#7c3aed', '#db2777', '#ea580c', '#059669', '#0891b2', '#4f46e5', '#65a30d']);
    const COMPOSER_TIME_EPSILON = .002;

    function tr(key, values = {}) {
        let text = typeof window.t === 'function' ? window.t(key) : key;
        Object.entries(values).forEach(([name, value]) => { text = text.replaceAll(`{${name}}`, String(value)); });
        return text;
    }
    function galleryHostUnavailable(error) {
        return /AI2Apps Host did not respond|Unsupported host mount/i.test(String(error?.message || error || ''));
    }
    function nativeFilePath(file) {
        try { return String(file?.mozAI2AppsFullPath || ''); }
        catch (_) { return ''; }
    }
    function selectedDirectory(files) {
        const file = Array.from(files || [])[0];
        const fullPath = nativeFilePath(file), relativePath = String(file?.webkitRelativePath || '');
        if (!fullPath || !relativePath || !fullPath.endsWith(relativePath)) return '';
        return fullPath.slice(0, -relativePath.length).replace(/\/$/, '');
    }
    function composerId(prefix) { return `${prefix}_${crypto.randomUUID().replaceAll('-', '')}`; }
    function newComposerProject() {
        return {
            schema: 'ai2apps.video-composition/v1', title: 'Untitled composition',
            settings: { width: 1280, height: 720, fps: 30, background: '#000000', snapping: true },
            tracks: [
                { id: composerId('track'), kind: 'video', name: 'Video 1', order: 0, muted: false, locked: false },
                { id: composerId('track'), kind: 'audio', name: 'Audio 1', order: 1, muted: false, locked: false },
            ],
            clips: [],
        };
    }
    function copyComposerProject(project) { return JSON.parse(JSON.stringify(project)); }
    function conversationModel(model) {
        const type = String(model?.model_type || model?.type || '').toLowerCase();
        return ['llm', 'vlm'].includes(type) || (!type && !String(model?.id || '').includes('embedding'));
    }

    function localizedMiniApp(miniApp) {
        if (miniApp.source === 'package') return {
            ...miniApp, mode: `package:${miniApp.id}`, icon: miniApp.icon || 'blocks',
            name: miniApp.name || miniApp.title || miniApp.id,
            summary: miniApp.summary || miniApp.description || miniApp.provider?.name || 'Installed Package',
            description: miniApp.description || miniApp.summary || miniApp.provider?.name || '',
            actionTitle: miniApp.name || miniApp.title || miniApp.id, runLabel: miniApp.name || miniApp.id,
        };
        return {
            ...miniApp,
            name: tr(`${miniApp.key}.name`), summary: tr(`${miniApp.key}.summary`),
            description: tr(`${miniApp.key}.description`), actionTitle: tr(`${miniApp.key}.action`),
            runLabel: tr(`${miniApp.key}.run`),
        };
    }

    function emptyMiniAppDraft(mode) {
        return {
            mode, modelId: '', prompt: '', resolution: '512x512', duration: 5,
            preset: 'strict', steps: 20, seed: 42, label: '', batchText: '',
            firstFile: null, lastFile: null, firstPreview: '', lastPreview: '',
            referenceImages: [], referenceVideos: [], referenceAudios: [], referenceOrder: [],
            extractAsset: null, extractOutputName: '',
        };
    }

    function isTemporarilyDisabledProvider(provider) {
        const id = String(provider?.id || '').toLowerCase();
        const family = String(provider?.family || '').toLowerCase().replaceAll('_', '-');
        const precision = String(provider?.precision || '').toLowerCase().replaceAll('_', '-');
        const isH3 = ['minimax-h3', 'h3'].includes(family) || id.includes('minimax-h3');
        return isH3 && (['bf16', 'fp16', 'f16', '16bit', '16-bit'].includes(precision) || id.includes('/fl2va-bf16') || id.includes('/fl2va-fp16'));
    }

    function preferredProviderId(providers, recommendedId = '') {
        const recommended = providers.find(item => item.id === recommendedId);
        return (recommended?.ready ? recommended : providers.find(item => item.ready) || recommended || providers[0])?.id || '';
    }

    async function responsePayload(response) {
        const payload = await response.json().catch(() => null);
        if (!response.ok) {
            throw new Error(payload?.error?.message || payload?.detail?.message || payload?.detail || tr('video_studio.error.request_failed', { status: response.status }));
        }
        return payload;
    }

    window.videoStudioApp = function () { return {
        refreshing: false, refreshRequestId: 0, submitting: false, batchSubmitting: false, polling: false, joining: false, addingToGallery: false, galleryAdded: false, retryingTaskId: '', modelInstallBusy: false,
        notice: '', noticeTone: 'error', providers: [], modelId: '', tasks: [], selectedTaskId: '', audioRuns: [], selectedAudioRunId: '',
        dismissed: [], pollTimer: null, mode: 't2v', prompt: '', resolution: '512x512', duration: 5,
        preset: 'strict', steps: 20, seed: 42, label: '', firstFile: null, lastFile: null,
        firstPreview: '', lastPreview: '', referenceImages: [], referenceVideos: [], referenceAudios: [], referenceOrder: [],
        batchText: '', joinedVideoUrl: '', clientEnvironment: 'browser', leftView: 'mini-apps', leftCollapsed: false, rightCollapsed: false,
        miniAppDrafts: {}, resizeHandler: null, responsiveNarrow: false, responsiveMobile: false,
        packageMiniApps: [], packageMiniAppId: '', packageMiniAppUrl: '', packageMiniAppMountId: '', packageMiniAppLoading: false, packageMiniAppError: '', packageMiniAppReadiness: {}, packageMiniAppSetupBusy: false,
        galleryMiniUrl: '', galleryMiniMountId: '', galleryMiniLoading: false, galleryMiniError: '', galleryDragActive: false, gallerySlotTarget: '',
        chatController: null, chatMiniUrl: '', packageChatBridge: null,
        galleryActiveCollectionId: 'recent', galleryActiveCollectionName: 'Recent', galleryMessageHandler: null, galleryAddedTimer: null,
        extractAsset: null, extractOutputName: '', extractImporting: false, extractSubmitting: false, localAudioSources: {}, addingAudioToGallery: false, audioGalleryAdded: false,
        composerProject: newComposerProject(), composerSources: [], composerDocumentPath: '', composerDocumentSaving: false, composerRuns: [], selectedComposerRunId: '', composerSelectedClipId: '', composerSelectedClipIds: [], composerSelectedKeyframeId: '', composerDropTrackId: '', composerScale: 42, composerPlayhead: 0, composerPlayheadSnapped: false, composerPlaying: false, composerRaf: 0, composerHistory: [], composerFuture: [], composerEditSnapshot: null, composerImporting: false, composerMaskImporting: false, composerRendering: false, composerSaveTimer: 0, composerChatText: '', composerChatLog: [], composerChatBusy: false, composerChatModels: [], composerChatModelId: '', composerKeyHandler: null, composerHoverTip: { text: '', left: 0, top: 0 }, addingComposerToGallery: false, composerGalleryAdded: false,
        tr,
        get miniApps() { return [...MINI_APPS, ...this.packageMiniApps].map(localizedMiniApp); },
        get selectedProvider() { return this.providers.find(item => item.id === this.modelId) || null; },
        get currentMiniApp() { return this.packageMiniAppId ? (this.miniApps.find(item => item.id === this.packageMiniAppId) || this.miniAppForMode(this.mode)) : this.miniAppForMode(this.mode); },
        get miniAppChatEnabled() { return Boolean(window.AI2AppsMiniAppChat && this.currentMiniApp && (this.currentMiniApp.source !== 'package' || this.currentMiniApp.chat?.enabled === true)); },
        get isAudioExtractor() { return this.mode === 'x2a'; },
        get isComposer() { return this.mode === 'composer'; },
        get isLocalVideoTool() { return this.isAudioExtractor || this.isComposer; },
        get currentMiniAppReady() { return this.packageMiniAppId ? this.miniAppReady(this.currentMiniApp) : (this.isLocalVideoTool || Boolean(this.selectedProvider?.ready)); },
        get modeProviders() {
            const wantsReference = this.mode === 'r2v';
            if (this.isLocalVideoTool) return [];
            return this.providers.filter(item => Boolean(item.capabilities?.includes('reference_to_video')) === wantsReference);
        },
        get caps() { return this.selectedProvider?.videoCapabilities || {}; },
        get resolutions() { return this.caps.geometry?.resolutions || ['512x512']; },
        get presets() { return this.caps.presets?.length ? this.caps.presets : [{ id: 'strict', display_name: 'Strict' }]; },
        get durationMin() { return Number(this.caps.duration?.minimum_seconds ?? 1); },
        get durationMax() { return Number(this.caps.duration?.maximum_seconds ?? 15); },
        get frameNote() { const fps = Number(this.caps.defaults?.framespersecond || 24); return tr('video_studio.frame_note', { frames: Math.max(1, Math.round(this.duration * fps)), fps }); },
        get canGenerate() {
            if (this.isAudioExtractor) return Boolean(this.extractAsset?.id || this.extractAsset?.nativePath);
            if (this.isComposer) return this.composerProject.clips.length > 0;
            if (!this.prompt.trim()) return false;
            if (this.mode === 'i2v') return Boolean(this.firstFile);
            if (this.mode === 'r2v') return Boolean(this.referenceImages.length || this.referenceVideos.length);
            return true;
        },
        get needsConfiguration() { return !this.isLocalVideoTool && (!this.selectedProvider?.ready || !this.modeProviders.some(item => item.id === this.modelId)); },
        get canPrimaryAction() { return this.needsConfiguration || this.canGenerate; },
        get visibleTasks() { return this.tasks.filter(task => !this.dismissed.includes(task.id)); },
        get activeTask() { return this.visibleTasks.find(task => task.id === this.selectedTaskId) || this.visibleTasks.find(task => task.status === 'succeeded') || null; },
        get activeVideoUrl() { return this.joinedVideoUrl || this.activeTask?.result?.video?.download_url || ''; },
        get completedTasks() { return this.visibleTasks.filter(task => task.status === 'succeeded').slice().reverse(); },
        get queueSummary() { const active = this.visibleTasks.filter(task => !terminal.has(task.status)).length; return tr('video_studio.queue_summary', { count: this.visibleTasks.length }) + (active ? tr('video_studio.queue_active', { count: active }) : ''); },
        get presetHelp() { return tr(this.preset === 'strict' ? 'video_studio.preset.strict_help' : this.preset === 'fast_max' ? 'video_studio.preset.fast_max_help' : 'video_studio.preset.fast_help'); },
        get activeAudioRun() { return this.audioRuns.find(run => run.id === this.selectedAudioRunId) || this.audioRuns[0] || null; },
        get activeAudioArtifact() { return this.activeAudioRun?.artifacts?.find(item => item.kind === 'audio' && item.final) || null; },
        get composerDuration() { return Math.max(1, ...this.composerProject.clips.map(clip => clip.start + clip.duration)); },
        get composerFps() { return Math.max(1, Math.min(60, Math.round(Number(this.composerProject.settings.fps) || 30))); },
        get composerFrameDuration() { return 1 / this.composerFps; },
        get composerTimelineWidth() { return Math.max(720, Math.ceil((this.composerDuration + 2) * this.composerScale)); },
        get composerSelectedClip() { return this.composerProject.clips.find(clip => clip.id === this.composerSelectedClipId) || null; },
        get composerSelectedClips() { const ids = new Set(this.composerSelectedClipIds); return this.composerProject.clips.filter(clip => ids.has(clip.id)); },
        get composerSelectedKeyframe() { return this.composerSelectedClip?.keyframes?.find(keyframe => keyframe.id === this.composerSelectedKeyframeId) || null; },
        get composerSelectedKeyframeIsEndpoint() { return this.composerIsProtectedKeyframe(this.composerSelectedClip, this.composerSelectedKeyframe); },
        get composerCanAddKeyframe() {
            const clip = this.composerSelectedClip, source = clip ? this.composerSource(clip.sourceId) : null;
            return Boolean(clip && (source?.hasVideo || source?.hasImage) && this.composerPlayhead >= clip.start && this.composerPlayhead < clip.start + clip.duration);
        },
        get composerCanGroupSelection() {
            const clips = this.composerSelectedClips;
            if (clips.length < 2 || new Set(clips.map(clip => clip.trackId)).size !== 1) return false;
            const ordered = this.composerTrackClips(clips[0].trackId), positions = clips.map(clip => ordered.findIndex(item => item.id === clip.id)).sort((a, b) => a - b);
            return positions.every((position, index) => position === positions[0] + index);
        },
        get composerCanUngroupSelection() { return this.composerSelectedClips.some(clip => Boolean(clip.groupId)); },
        get activeComposerRun() { return this.composerRuns.find(run => run.id === this.selectedComposerRunId) || this.composerRuns[0] || null; },
        get activeComposerArtifact() { return this.activeComposerRun?.artifacts?.find(item => item.kind === 'video' && item.final) || null; },

        favoriteMiniApps: [],
        openCoder() { if (window.ai2appsShell?.openEntry) window.ai2appsShell.openEntry({ appId: 'ai2apps.coder', query: { template: 'mini-app', placement: APP_ID } }); else window.open('/apps/ai2apps.coder?template=mini-app&placement='+encodeURIComponent(APP_ID), '_blank', 'noopener'); },
        isFavorite(id) { return this.favoriteMiniApps.includes(id); },
        toggleFavorite(id) { this.favoriteMiniApps = this.isFavorite(id) ? this.favoriteMiniApps.filter(value => value !== id) : [...this.favoriteMiniApps, id]; try { localStorage.setItem('ai2apps.video-studio.favorites', JSON.stringify(this.favoriteMiniApps)); } catch (_) {} },
        miniAppStatusLabel(ready) { const zh = document.documentElement.lang.startsWith('zh'); return ready ? (zh ? '可用 · 切换收藏' : 'Available · Toggle favorite') : (zh ? '需要下载依赖' : 'Dependencies need download'); },
        async init() {
            try { const saved = JSON.parse(localStorage.getItem('ai2apps.video-studio.favorites') || '[]'); this.favoriteMiniApps = Array.isArray(saved) ? saved : []; } catch (_) {}
            this.clientEnvironment = this.$root?.dataset?.clientEnvironment || 'browser';
            this.restoreShellState();
            const restoredModelId = this.modelId;
            await this.refreshPackageMiniApps();
            const pendingPackageMiniAppId = window.AI2AppsStudioMiniApps?.pendingSetup(APP_ID)?.miniAppId;
            const pendingPackageMiniApp = this.packageMiniApps.find(item => item.id === pendingPackageMiniAppId);
            if (pendingPackageMiniApp) await this.mountPackageMiniApp(pendingPackageMiniApp);
            this.setupMiniAppChat();
            this.miniAppDrafts = Object.fromEntries(MINI_APPS.map(item => [item.mode, emptyMiniAppDraft(item.mode)]));
            this.restoreMiniAppDraft(this.mode);
            if (restoredModelId) this.modelId = restoredModelId;
            if (this.mode === 'x2a') await this.loadExtractorDraft();
            if (this.mode === 'composer') { await this.loadComposerProject(); await this.loadComposerChatModels(); }
            this.applyResponsiveDefaults();
            this.resizeHandler = () => this.applyResponsiveDefaults(false);
            window.addEventListener('resize', this.resizeHandler);
            this.galleryMessageHandler = event => this.handleGalleryMessage(event);
            window.addEventListener('message', this.galleryMessageHandler);
            this.composerKeyHandler = event => this.handleComposerKeydown(event);
            window.addEventListener('keydown', this.composerKeyHandler);
            try { this.dismissed = JSON.parse(localStorage.getItem('ai2apps-video-studio-dismissed') || '[]'); } catch (_) { this.dismissed = []; }
            await this.refresh();
            if (this.leftView === 'assets') this.mountGalleryMini();
            if (this.leftView === 'chat') this.mountMiniAppChat();
            try {
                const resumed = await window.AI2AppsStudioMiniApps?.resumeSetup(APP_ID, this.packageMiniApps);
                if (resumed?.status === 'ready') {
                    const item = this.packageMiniApps.find(value => value.id === (resumed.miniAppId || this.packageMiniAppId));
                    if (item && item.id !== this.packageMiniAppId) await this.mountPackageMiniApp(item);
                    else if (item) await this.refreshPackageMiniAppReadiness(item);
                    await this.refreshAllPackageMiniAppReadiness();
                    await this.refresh(); this.success(tr('video_studio.deps_ready'));
                }
                for (const capability of ['video.reference_generation', 'video.generation']) {
                    const resumed = await window.AI2AppsCapabilities?.resume(APP_ID, { capability });
                    if (resumed?.status !== 'ready' || resumed.outcome !== 'configured') continue;
                    const resumeToken = resumed.session?.intent?.resumeToken;
                    await this.finishProvisioning(resumed, resumeToken, {
                        preserveModelId: resumed.session?.actionId === 'install-more-video-models' ? this.modelId : '',
                    });
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
            if (this.composerRaf) cancelAnimationFrame(this.composerRaf);
            if (this.composerSaveTimer) clearTimeout(this.composerSaveTimer);
            if (this.galleryAddedTimer) clearTimeout(this.galleryAddedTimer);
            if (this.galleryMessageHandler) window.removeEventListener('message', this.galleryMessageHandler);
            if (this.composerKeyHandler) window.removeEventListener('keydown', this.composerKeyHandler);
            if (this.resizeHandler) window.removeEventListener('resize', this.resizeHandler);
            this.chatController?.dispose();
            this.packageChatBridge?.dispose();
            this.saveCurrentMiniAppDraft();
            this.persistShellState();
            this.revokePreview('first'); this.revokePreview('last');
        },
        icons() { this.$nextTick(() => window.lucide?.createIcons()); },
        fail(error) { this.notice = error?.message || String(error); this.noticeTone = 'error'; this.icons(); },
        success(message) { this.notice = message; this.noticeTone = 'success'; this.icons(); },
        setupMiniAppChat() {
            if (!window.AI2AppsMiniAppChat) return;
            this.chatController = window.AI2AppsMiniAppChat.createStudioController({
                describe: () => this.describeMiniAppChat(),
                invoke: (name, args) => this.invokeMiniAppChatTool(name, args),
                help: () => this.readMiniAppHelp(),
            });
            this.chatMiniUrl = this.chatController.url();
        },
        mountMiniAppChat() {
            if (!this.chatController) this.setupMiniAppChat();
            return new Promise(resolve => this.$nextTick(() => { this.chatController?.bind(this.$refs.miniAppChat); resolve(); }));
        },
        async describeMiniAppChat() {
            const miniApp = this.currentMiniApp;
            if (miniApp.source === 'package') {
                if (!this.packageChatBridge) throw new Error('Package Mini-App Chat provider is not ready');
                return this.packageChatBridge.describe({ id: miniApp.id, name: miniApp.name, version: miniApp.version, studioId: APP_ID });
            }
            const context = {
                mode: this.mode, prompt: this.prompt, modelId: this.modelId,
                resolution: this.resolution, duration: this.duration, preset: this.preset,
                steps: this.steps, seed: this.seed, label: this.label,
                ready: this.currentMiniAppReady, canRun: this.canPrimaryAction,
                inputs: {
                    firstFrame: this.firstFile?.name || null, lastFrame: this.lastFile?.name || null,
                    referenceImages: this.referenceImages.map(file => file.name),
                    referenceVideos: this.referenceVideos.map(file => file.name),
                    referenceAudios: this.referenceAudios.map(file => file.name),
                    extractSource: this.extractAsset?.name || null,
                },
                composer: this.isComposer ? { title: this.composerProject.title, tracks: this.composerProject.tracks.length, clips: this.composerProject.clips.length } : null,
            };
            const properties = this.isComposer
                ? { projectTitle: { type: 'string', maxLength: 160 } }
                : this.isAudioExtractor
                    ? { outputName: { type: 'string', maxLength: 255 } }
                    : {
                        prompt: { type: 'string', maxLength: 8000 }, modelId: { type: 'string' },
                        resolution: { type: 'string' }, duration: { type: 'number', minimum: .5, maximum: 60 },
                        preset: { type: 'string' }, steps: { type: 'integer', minimum: 1, maximum: 60 },
                        seed: { type: 'integer', minimum: 0, maximum: 2147483647 }, label: { type: 'string', maxLength: 120 },
                    };
            return {
                schema: window.AI2AppsMiniAppChat.SCHEMA, enabled: true,
                miniApp: { id: miniApp.id, name: miniApp.name, version: '1.0.0', studioId: APP_ID },
                systemPrompt: `You are the conversational controller for ${miniApp.name} in Video Studio. Help prepare its current draft, explain missing inputs, and run only the declared operations.`,
                context,
                help: { available: true, format: 'markdown', maxBytes: 32 * 1024 },
                tools: [
                    { name: 'update_current_draft', title: 'Update current draft', description: 'Update only the supplied fields in the current Mini-App draft.', inputSchema: { type: 'object', properties, additionalProperties: false } },
                    { name: 'run_current', title: this.isComposer ? 'Render composition' : this.isAudioExtractor ? 'Extract audio' : 'Generate video', description: 'Start the current Mini-App operation using the visible draft and selected assets.', inputSchema: { type: 'object', properties: {}, additionalProperties: false }, confirmation: 'always' },
                ],
            };
        },
        async readMiniAppHelp() {
            if (this.currentMiniApp.source === 'package') {
                if (!this.packageChatBridge) throw new Error('Package Mini-App Chat provider is not ready');
                return this.packageChatBridge.help();
            }
            return window.AI2AppsMiniAppChat.loadBuiltinHelp(this.currentMiniApp);
        },
        async invokeMiniAppChatTool(name, args) {
            if (this.currentMiniApp.source === 'package') {
                if (!this.packageChatBridge) throw new Error('Package Mini-App Chat provider is not ready');
                return this.packageChatBridge.invoke(name, args);
            }
            if (name === 'update_current_draft') {
                if (this.isComposer && typeof args.projectTitle === 'string') this.composerProject.title = args.projectTitle.slice(0, 160);
                else if (this.isAudioExtractor && typeof args.outputName === 'string') this.extractOutputName = args.outputName.slice(0, 255);
                else {
                    if (typeof args.prompt === 'string') this.prompt = args.prompt.slice(0, 8000);
                    if (typeof args.modelId === 'string' && this.providers.some(item => item.id === args.modelId)) this.modelId = args.modelId;
                    if (typeof args.resolution === 'string' && this.resolutions.includes(args.resolution)) this.resolution = args.resolution;
                    if (Number.isFinite(args.duration)) this.duration = Math.max(.5, Math.min(60, Number(args.duration)));
                    if (typeof args.preset === 'string' && this.presets.some(item => item.id === args.preset)) this.preset = args.preset;
                    if (Number.isInteger(args.steps)) this.steps = Math.max(1, Math.min(60, args.steps));
                    if (Number.isInteger(args.seed)) this.seed = Math.max(0, Math.min(2147483647, args.seed));
                    if (typeof args.label === 'string') this.label = args.label.slice(0, 120);
                }
                this.saveCurrentMiniAppDraft(); this.persistShellState(); this.icons();
                return { updated: true, state: (await this.describeMiniAppChat()).context };
            }
            if (name === 'run_current') {
                if (!this.canPrimaryAction) throw new Error('The current Mini-App is missing required inputs');
                if (this.isComposer) await this.renderComposer();
                else if (this.isAudioExtractor) await this.extractAudio();
                else { const run = this.generate.bind(this); await run(); }
                return { started: true, mode: this.mode };
            }
            throw new Error('Unknown Mini-App Tool');
        },
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
            this.leftView = view === 'assets' ? 'assets' : (view === 'chat' && this.miniAppChatEnabled ? 'chat' : 'mini-apps');
            if (this.leftView === 'assets' && !this.galleryMiniUrl) await this.mountGalleryMini();
            if (this.leftView === 'chat') await this.mountMiniAppChat();
            this.persistShellState();
            this.icons();
        },
        async selectMiniApp(miniAppId) {
            const miniApp = this.miniApps.find(item => item.id === miniAppId);
            if (!miniApp) return;
            if (miniApp.source === 'package') {
                await this.mountPackageMiniApp(miniApp);
                this.leftView = this.miniAppChatEnabled && this.leftView === 'chat' ? 'chat' : 'mini-apps';
                if (window.matchMedia('(max-width: 1000px)').matches) this.leftCollapsed = true;
                return;
            }
            this.packageChatBridge?.dispose(); this.packageChatBridge = null;
            this.packageMiniAppId = ''; this.packageMiniAppUrl = ''; this.packageMiniAppError = '';
            await this.switchMode(miniApp.mode);
            if (this.leftView !== 'chat') this.leftView = 'mini-apps';
            this.chatController?.changed();
            if (window.matchMedia('(max-width: 1000px)').matches) this.leftCollapsed = true;
            this.persistShellState();
        },
        miniAppForMode(mode) { return this.miniApps.find(item => item.mode === mode) || this.miniApps[0]; },
        miniAppForTask(task) { return this.miniAppForMode(task?.metadata?.mode || 't2v'); },
        miniAppReady(miniApp) {
            if (miniApp?.source === 'package') return this.packageMiniAppReadiness[miniApp.id] === true;
            if (['x2a', 'composer'].includes(miniApp?.mode)) return true;
            const wantsReference = miniApp?.mode === 'r2v';
            return this.providers.some(item => item.ready && Boolean(item.capabilities?.includes('reference_to_video')) === wantsReference);
        },
        async refreshAllPackageMiniAppReadiness() {
            try { this.packageMiniAppReadiness = await window.AI2AppsStudioMiniApps?.readiness(APP_ID) || {}; }
            catch (_) { /* Keep the most recent readiness snapshot during reconnects. */ }
            this.icons();
            return this.packageMiniAppReadiness;
        },
        async refreshPackageMiniAppReadiness(miniApp, mountId = this.packageMiniAppMountId) {
            if (!miniApp?.id || !mountId) return false;
            try {
                const probe = await window.AI2AppsStudioMiniApps.probe(APP_ID, mountId);
                const capabilities = Array.isArray(probe?.items) ? probe.items : [];
                const required = capabilities.filter(value => value?.required !== false);
                const ready = required.length > 0 && required.every(value => value?.implemented === true && value?.ready === true);
                this.packageMiniAppReadiness = { ...this.packageMiniAppReadiness, [miniApp.id]: ready };
                return ready;
            } catch (_) {
                this.packageMiniAppReadiness = { ...this.packageMiniAppReadiness, [miniApp.id]: false };
                return false;
            }
        },
        async setupCurrentMiniApp() {
            const miniApp = this.currentMiniApp;
            if (!miniApp || this.currentMiniAppReady || this.packageMiniAppSetupBusy) return;
            if (miniApp.source !== 'package') {
                try { await this.ensureVideoCapability('configure-generation'); }
                catch (error) { this.fail(error); }
                return;
            }
            this.packageMiniAppSetupBusy = true;
            try {
                await window.AI2AppsStudioMiniApps.setup(APP_ID, miniApp);
                const readiness = await this.refreshAllPackageMiniAppReadiness();
                const ready = readiness[miniApp.id] === true;
                if (ready) this.success(tr('video_studio.deps_ready'));
            } catch (error) { this.fail(error); }
            finally { this.packageMiniAppSetupBusy = false; this.icons(); }
        },
        async refreshPackageMiniApps() {
            try {
                const catalog = await window.AI2AppsStudioMiniApps?.list(APP_ID);
                this.packageMiniApps = (catalog?.items || []).filter(item => item.source === 'package');
                await this.refreshAllPackageMiniAppReadiness();
            } catch (_) { this.packageMiniApps = []; }
        },
        async mountPackageMiniApp(miniApp) {
            if (!miniApp?.id || this.packageMiniAppLoading) return;
            this.packageMiniAppId = miniApp.id; this.packageMiniAppUrl = ''; this.packageMiniAppError = ''; this.packageMiniAppLoading = true;
            this.packageMiniAppReadiness = { ...this.packageMiniAppReadiness, [miniApp.id]: false };
            try {
                const mount = await window.AI2AppsStudioMiniApps.mount(APP_ID, miniApp.id, { placement: 'inline' });
                this.packageMiniAppMountId = mount.id || ''; this.packageMiniAppUrl = mount.content_url || '';
                if (!this.packageMiniAppUrl) throw new Error('Mini-App content URL is unavailable');
                await this.refreshPackageMiniAppReadiness(miniApp, mount.id);
                if (miniApp.chat?.enabled === true) await new Promise(resolve => this.$nextTick(() => {
                    this.packageChatBridge?.dispose();
                    this.packageChatBridge = window.AI2AppsMiniAppChat.createPackageBridge(() => this.$refs.packageMiniApp, miniApp.chat);
                    resolve();
                }));
            } catch (error) { this.packageMiniAppError = error?.message || String(error); }
            finally { this.packageMiniAppLoading = false; this.chatController?.changed(); this.icons(); }
        },
        restoreShellState() {
            try {
                const state = JSON.parse(localStorage.getItem(SHELL_STATE_KEY) || '{}');
                if (['mini-apps', 'assets', 'chat'].includes(state.leftView)) this.leftView = state.leftView;
                if (MINI_APPS.some(item => item.mode === state.mode)) this.mode = state.mode;
                if (typeof state.modelId === 'string') this.modelId = state.modelId;
                if (typeof state.selectedTaskId === 'string') this.selectedTaskId = state.selectedTaskId;
                if (typeof state.selectedAudioRunId === 'string') this.selectedAudioRunId = state.selectedAudioRunId;
                if (typeof state.selectedComposerRunId === 'string') this.selectedComposerRunId = state.selectedComposerRunId;
                if (typeof state.leftCollapsed === 'boolean') this.leftCollapsed = state.leftCollapsed;
                if (typeof state.rightCollapsed === 'boolean') this.rightCollapsed = state.rightCollapsed;
            } catch (_) { /* Ignore invalid display preferences. */ }
        },
        persistShellState() {
            try {
                localStorage.setItem(SHELL_STATE_KEY, JSON.stringify({
                    leftView: this.leftView, mode: this.mode, modelId: this.modelId,
                    selectedTaskId: this.selectedTaskId,
                    selectedAudioRunId: this.selectedAudioRunId, selectedComposerRunId: this.selectedComposerRunId,
                    leftCollapsed: this.leftCollapsed, rightCollapsed: this.rightCollapsed,
                }));
            } catch (_) { /* Display preferences must never block Studio work. */ }
        },
        applyResponsiveDefaults(initial = true) {
            const narrow = window.matchMedia('(max-width: 1000px)').matches;
            const mobile = window.matchMedia('(max-width: 760px)').matches;
            if (narrow && (initial || !this.responsiveNarrow)) this.rightCollapsed = true;
            if (mobile && (initial || !this.responsiveMobile)) this.leftCollapsed = true;
            this.responsiveNarrow = narrow; this.responsiveMobile = mobile;
            if (!initial) this.persistShellState();
        },
        toggleLeftPanel() {
            this.leftCollapsed = !this.leftCollapsed;
            this.persistShellState(); this.icons();
        },
        toggleRightPanel() {
            this.rightCollapsed = !this.rightCollapsed;
            this.persistShellState(); this.icons();
        },
        captureMiniAppDraft(mode = this.mode) {
            return {
                mode, modelId: this.modelId, prompt: this.prompt, resolution: this.resolution,
                duration: this.duration, preset: this.preset, steps: this.steps, seed: this.seed,
                label: this.label, batchText: this.batchText,
                firstFile: this.firstFile, lastFile: this.lastFile,
                firstPreview: this.firstPreview, lastPreview: this.lastPreview,
                referenceImages: [...this.referenceImages], referenceVideos: [...this.referenceVideos],
                referenceAudios: [...this.referenceAudios], referenceOrder: this.referenceOrder.map(item => ({ ...item })),
                extractAsset: this.extractAsset ? { ...this.extractAsset } : null,
                extractOutputName: this.extractOutputName,
            };
        },
        saveCurrentMiniAppDraft() { this.miniAppDrafts[this.mode] = this.captureMiniAppDraft(this.mode); },
        restoreMiniAppDraft(mode) {
            const draft = this.miniAppDrafts[mode] || emptyMiniAppDraft(mode);
            for (const key of ['modelId', 'prompt', 'resolution', 'duration', 'preset', 'steps', 'seed', 'label', 'batchText', 'firstFile', 'lastFile', 'firstPreview', 'lastPreview']) {
                this[key] = draft[key];
            }
            this.referenceImages = [...draft.referenceImages];
            this.referenceVideos = [...draft.referenceVideos];
            this.referenceAudios = [...draft.referenceAudios];
            this.referenceOrder = draft.referenceOrder.map(item => ({ ...item }));
            this.extractAsset = draft.extractAsset ? { ...draft.extractAsset } : null;
            this.extractOutputName = draft.extractOutputName || '';
        },
        async mountGalleryMini(force = false) {
            if (this.galleryMiniLoading || (this.galleryMiniUrl && !force)) return;
            this.galleryMiniLoading = true; this.galleryMiniError = '';
            if (force) { this.galleryMiniUrl = ''; this.galleryMiniMountId = ''; }
            try {
                const bridge = window.ai2appsShell;
                if (!bridge?.mountMiniEntry) {
                    this.galleryMiniUrl = GALLERY_MINI_FALLBACK_URL;
                    return;
                }
                const mount = await bridge.mountMiniEntry({
                    appId: 'ai2apps.gallery', placement: 'sidebar', requestedBy: APP_ID,
                });
                if (!mount?.content_url) throw new Error(tr('video_studio.error.gallery_mount_url'));
                this.galleryMiniMountId = mount.id || '';
                this.galleryMiniUrl = mount.content_url;
            } catch (error) {
                if (galleryHostUnavailable(error)) {
                    // Compatibility path for an older Desktop Host. The route is
                    // still first-party and principal-scoped; newer hosts return
                    // the same URL through the Mini-Entry mount contract.
                    this.galleryMiniUrl = GALLERY_MINI_FALLBACK_URL;
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
            if (event.data?.type === 'ai2apps.gallery.asset-selected') {
                const asset = event.data.asset || {};
                if (this.isComposer) {
                    if (['video', 'audio'].includes(asset.kind)) void this.importComposerGalleryAsset(asset).catch(error => this.fail(error));
                    else this.fail(new Error(tr('video_studio.error.asset_type')));
                    return;
                }
                if (!this.isAudioExtractor) return;
                if (asset.kind === 'video') void this.selectExtractAsset(asset).catch(error => this.fail(error));
                else this.fail(new Error(tr('video_studio.error.extract_video_only')));
                return;
            }
            if (event.data?.type === 'ai2apps.gallery.collection-changed') {
                const collectionId = String(event.data.collectionId || 'recent');
                this.galleryActiveCollectionId = collectionId;
                this.galleryActiveCollectionName = String(event.data.collectionName || collectionId);
            }
        },
        async selectExtractAsset(asset) {
            if (!asset?.id || asset.kind !== 'video') throw new Error(tr('video_studio.error.extract_video_only'));
            await this.switchMode('x2a');
            this.extractAsset = {
                id: String(asset.id), name: String(asset.name || tr('video_studio.extract.untitled_video')),
                kind: 'video', sourceKind: 'gallery', mediaType: String(asset.mediaType || asset.media_type || 'video/mp4'),
            };
            this.extractOutputName = String(this.extractAsset.name).replace(/\.[^.]+$/, '') + '.wav';
            await this.saveExtractorDraft();
            this.success(tr('video_studio.success.extract_asset_selected', { name: this.extractAsset.name }));
            this.icons();
        },
        async saveExtractorDraft() {
            const persistentAsset = this.extractAsset?.sourceKind === 'local' ? null : this.extractAsset;
            await responsePayload(await fetch(`${STUDIO_API}/studio-drafts/${encodeURIComponent('ai2apps.video.extract-audio')}`, {
                method: 'PUT', credentials: 'same-origin', headers: { ...this.draftHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({ draft: { asset: persistentAsset, outputName: this.extractOutputName } }),
            }));
        },
        async loadExtractorDraft() {
            try {
                const record = await responsePayload(await fetch(`${STUDIO_API}/studio-drafts/${encodeURIComponent('ai2apps.video.extract-audio')}`, {
                    credentials: 'same-origin', headers: this.draftHeaders(),
                }));
                const asset = record.draft?.asset;
                if (asset?.id && asset.kind === 'video') this.extractAsset = asset;
                this.extractOutputName = String(record.draft?.outputName || this.extractOutputName || '');
            } catch (error) { this.fail(error); }
        },
        async importExtractFile(eventOrFile) {
            const file = eventOrFile?.target?.files?.[0] || eventOrFile;
            if (!file) return;
            if (!String(file.type || '').startsWith('video/')) throw new Error(tr('video_studio.error.extract_video_only'));
            this.extractImporting = true;
            try {
                const sourcePath = nativeFilePath(file);
                if (sourcePath) {
                    await this.switchMode('x2a');
                    this.extractAsset = {
                        id: null, name: String(file.name || tr('video_studio.extract.untitled_video')),
                        kind: 'video', sourceKind: 'local', mediaType: String(file.type), nativePath: sourcePath,
                    };
                    this.extractOutputName = String(this.extractAsset.name).replace(/\.[^.]+$/, '') + '.wav';
                    await this.saveExtractorDraft();
                    this.success(tr('video_studio.success.extract_asset_selected', { name: this.extractAsset.name }));
                    return;
                }
                const form = new FormData();
                form.append('file', file, file.name);
                form.append('sourceAppId', APP_ID);
                const imported = await responsePayload(await fetch('/v1/platform/gallery/assets/import', {
                    method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' }, body: form,
                }));
                await this.selectExtractAsset(imported.asset);
                this.$refs.galleryMini?.contentWindow?.postMessage({ type: 'ai2apps.gallery.refresh' }, window.location.origin);
            } finally {
                this.extractImporting = false;
                if (eventOrFile?.target) eventOrFile.target.value = '';
                this.icons();
            }
        },
        clearExtractAsset() { this.extractAsset = null; this.extractOutputName = ''; void this.saveExtractorDraft().catch(error => this.fail(error)); this.icons(); },
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
                    if (this.mode === 'composer') { await this.importComposerFiles([localFile]); return; }
                    if (this.mode === 'x2a') { await this.importExtractFile(localFile); return; }
                    await this.routeDroppedFile(localFile, imageSlot);
                    return;
                }
                const assetId = event.dataTransfer?.getData('application/x-ai2apps-gallery-asset') || '';
                if (this.mode === 'composer' && assetId) {
                    const type = String(event.dataTransfer?.getData('application/x-ai2apps-gallery-kind') || 'video');
                    await this.importComposerGalleryAsset({ id: assetId, name: event.dataTransfer?.getData('text/plain') || 'Media', kind: type });
                    return;
                }
                if (this.mode === 'x2a' && assetId) {
                    await this.selectExtractAsset({ id: assetId, name: event.dataTransfer?.getData('text/plain') || 'Video', kind: 'video' });
                    return;
                }
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
            if (this.mode === 'composer' && /^(image|video|audio)\//.test(type)) {
                await this.importComposerFiles([file]);
                return;
            }
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
            } else if (type.startsWith('video/') && this.mode === 'x2a') {
                await this.importExtractFile(file);
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
            const requestId = ++this.refreshRequestId;
            this.refreshing = true;
            try {
                const [providersResponse, tasksResponse, runsResponse] = await Promise.all([
                    fetch(PROVIDERS_API, { credentials: 'same-origin', headers: { Accept: 'application/json' } }),
                    fetch(TASKS_API + '?limit=100', { credentials: 'same-origin', headers: { Accept: 'application/json' } }),
                    fetch(STUDIO_API + '/runs?limit=100', { credentials: 'same-origin', headers: this.draftHeaders() }),
                ]);
                const providers = await responsePayload(providersResponse);
                const tasks = await responsePayload(tasksResponse);
                const runs = await responsePayload(runsResponse);
                if (requestId !== this.refreshRequestId) return;
                this.providers = (providers.items || []).filter(item => !isTemporarilyDisabledProvider(item));
                this.tasks = tasks.data || [];
                this.audioRuns = (runs.items || []).filter(run => run.miniAppId === 'ai2apps.video.extract-audio');
                this.composerRuns = (runs.items || []).filter(run => run.miniAppId === 'ai2apps.video.composer');
                if (!this.isLocalVideoTool && !this.modeProviders.some(item => item.id === this.modelId && item.ready)) {
                    const probe = await window.AI2AppsCapabilities?.probe(this.capabilityRequest('probe', ''));
                    const recommendedId = probe?.provider?.modelId || probe?.plan?.stack?.checkpoint?.model_id || '';
                    this.modelId = preferredProviderId(this.modeProviders, recommendedId);
                }
                this.syncDefaults(false);
                if (!this.tasks.some(task => task.id === this.selectedTaskId)) this.selectedTaskId = this.tasks.find(task => task.status === 'succeeded')?.id || this.tasks[0]?.id || '';
                if (!this.audioRuns.some(run => run.id === this.selectedAudioRunId)) this.selectedAudioRunId = this.audioRuns[0]?.id || '';
                if (!this.composerRuns.some(run => run.id === this.selectedComposerRunId)) this.selectedComposerRunId = this.composerRuns[0]?.id || '';
                this.persistShellState();
                this.syncModelSelectValue();
                this.icons();
            } catch (error) {
                if (requestId === this.refreshRequestId) this.fail(error);
            } finally {
                if (requestId === this.refreshRequestId) this.refreshing = false;
            }
        },
        async poll() {
            if (this.polling || this.refreshing || (!this.tasks.some(task => !terminal.has(task.status)) && !this.audioRuns.some(run => !terminal.has(run.status)) && !this.composerRuns.some(run => !terminal.has(run.status)))) return;
            this.polling = true;
            try {
                const [tasksResponse, runsResponse] = await Promise.all([
                    fetch(TASKS_API + '?limit=100', { credentials: 'same-origin', headers: { Accept: 'application/json' } }),
                    fetch(STUDIO_API + '/runs?limit=100', { credentials: 'same-origin', headers: this.draftHeaders() }),
                ]);
                this.tasks = (await responsePayload(tasksResponse)).data || [];
                const runs = (await responsePayload(runsResponse)).items || [];
                this.audioRuns = runs.filter(run => run.miniAppId === 'ai2apps.video.extract-audio');
                this.composerRuns = runs.filter(run => run.miniAppId === 'ai2apps.video.composer');
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
            this.syncModelSelectValue();
            this.icons();
        },
        syncModelSelectValue() {
            this.$nextTick(() => {
                if (this.$refs.modelSelect) this.$refs.modelSelect.value = this.modelId || '';
            });
        },
        onModelSelect(select) {
            const value = String(select?.value || '');
            if (value === INSTALL_MORE_MODEL_ID) {
                select.value = this.modelId || '';
                this.syncModelSelectValue();
                void this.installMoreVideoModels();
                return;
            }
            if (!this.modeProviders.some(item => item.id === value)) {
                this.syncModelSelectValue();
                return;
            }
            this.modelId = value;
            this.syncDefaults();
            this.saveCurrentMiniAppDraft();
            this.persistShellState();
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
            if (!MINI_APPS.some(item => item.mode === mode)) return;
            if (mode !== this.mode) {
                this.saveCurrentMiniAppDraft();
                this.mode = mode;
                this.restoreMiniAppDraft(mode);
            }
            if (mode === 'x2a') {
                await this.loadExtractorDraft();
            } else if (mode === 'composer') {
                await this.loadComposerProject(); await this.loadComposerChatModels();
            } else if (!this.modeProviders.some(item => item.id === this.modelId)) {
                this.modelId = this.modeProviders.find(item => item.ready)?.id || this.modeProviders[0]?.id || '';
            }
            this.syncDefaults(false);
            this.saveCurrentMiniAppDraft();
            this.persistShellState();
            this.icons();
        },
        randomizeSeed() { this.seed = Math.floor(Math.random() * 2147483646) + 1; },

        composerSourceUrl(sourceId) {
            const instanceId = window.AI2AppsCapabilities?.appInstanceId?.() || '';
            return `${STUDIO_API}/composer/sources/${encodeURIComponent(sourceId)}/content?appInstanceId=${encodeURIComponent(instanceId)}`;
        },
        composerSource(sourceId) { return this.composerSources.find(source => source.id === sourceId) || null; },
        composerMaskSources() { return this.composerSources.filter(source => source.hasImage); },
        composerCompatibleSources(clip) {
            const current = this.composerSource(clip?.sourceId); if (!current) return [];
            if (current.hasVideo) return this.composerSources.filter(source => source.hasVideo);
            if (current.hasImage) return this.composerSources.filter(source => source.hasImage);
            return this.composerSources.filter(source => source.kind === 'audio');
        },
        composerTrack(trackId) { return this.composerProject.tracks.find(track => track.id === trackId) || null; },
        composerTrackClips(trackId) { return this.composerProject.clips.filter(clip => clip.trackId === trackId).sort((a, b) => a.start - b.start); },
        composerFrameNumber(value) { return Math.max(0, Math.round((Number(value) || 0) * this.composerFps)); },
        composerTimeFromFrame(frame) { return Number((Math.max(0, Math.round(Number(frame) || 0)) / this.composerFps).toFixed(9)); },
        quantizeComposerTime(value, minimumFrames = 0) { return this.composerTimeFromFrame(Math.max(minimumFrames, this.composerFrameNumber(value))); },
        composerFormatTime(value) { return this.quantizeComposerTime(value).toFixed(3); },
        setComposerClipTime(field, value) {
            const clip = this.composerSelectedClip; if (!clip || !['start', 'duration'].includes(field)) return;
            clip[field] = this.quantizeComposerTime(value, field === 'duration' ? 1 : 0);
        },
        composerClipKeyframes(clip) { return Array.isArray(clip?.keyframes) ? clip.keyframes.slice().sort((a, b) => a.frame - b.frame) : []; },
        composerIsEndpointKeyframe(keyframe) { return keyframe?.endpoint === 'start' || keyframe?.endpoint === 'end'; },
        composerIsProtectedKeyframe(clip, keyframe) {
            if (!clip || !keyframe) return false;
            const endFrame = Math.max(1, this.composerFrameNumber(clip.duration)) - 1;
            return this.composerIsEndpointKeyframe(keyframe) || keyframe.frame === 0 || keyframe.frame === endFrame;
        },
        composerLocalFrameAtPlayhead(clip) { return this.composerFrameNumber(this.composerPlayhead - (Number(clip?.start) || 0)); },
        composerKeyframeAtPlayhead(clip) {
            if (!clip || this.composerPlayhead < clip.start || this.composerPlayhead >= clip.start + clip.duration) return null;
            const frame = this.composerLocalFrameAtPlayhead(clip);
            return this.composerClipKeyframes(clip).find(keyframe => keyframe.frame === frame) || null;
        },
        composerStageEditMode(clip) { return this.composerKeyframeAtPlayhead(clip) ? 'keyframe-edit' : 'clip-edit'; },
        syncComposerKeyframeSelection() {
            const keyframe = this.composerKeyframeAtPlayhead(this.composerSelectedClip), nextId = keyframe?.id || '';
            if (this.composerSelectedKeyframeId !== nextId) this.composerSelectedKeyframeId = nextId;
        },
        composerBaseVisualState(clip) {
            const settings = this.composerProject.settings;
            return { x: Number(clip.x) || 0, y: Number(clip.y) || 0, width: Number(clip.width) || settings.width, height: Number(clip.height) || settings.height, opacity: Number.isFinite(Number(clip.opacity)) ? Number(clip.opacity) : 1 };
        },
        composerVisualStateAtFrame(clip, localFrame) {
            let previousFrame = 0, previous = this.composerBaseVisualState(clip);
            for (const keyframe of this.composerClipKeyframes(clip)) {
                const target = Object.fromEntries(Object.keys(previous).map(key => [key, keyframe[key] === null || keyframe[key] === '' || keyframe[key] === undefined ? previous[key] : Number(keyframe[key])]));
                if (localFrame >= keyframe.frame) { previousFrame = keyframe.frame; previous = target; continue; }
                if (keyframe.transition === 'hold' || keyframe.frame <= previousFrame) return { ...previous };
                let progress = Math.max(0, Math.min(1, (localFrame - previousFrame) / (keyframe.frame - previousFrame)));
                if (keyframe.transition === 'ease') progress = progress * progress * (3 - 2 * progress);
                return Object.fromEntries(Object.keys(previous).map(key => [key, previous[key] + (target[key] - previous[key]) * progress]));
            }
            return { ...previous };
        },
        composerVisualStateAt(clip, timelineTime = this.composerPlayhead) {
            return this.composerVisualStateAtFrame(clip, Math.max(0, this.composerFrameNumber(timelineTime - clip.start)));
        },
        composerEditableVisual(clip) {
            return clip.id === this.composerSelectedClipId && this.composerKeyframeAtPlayhead(clip) ? this.composerKeyframeAtPlayhead(clip) : clip;
        },
        composerPreviousKeyframeState(clip, keyframe) {
            let state = this.composerBaseVisualState(clip);
            for (const item of this.composerClipKeyframes(clip)) {
                if (item.id === keyframe?.id) break;
                state = Object.fromEntries(Object.keys(state).map(key => [key, item[key] === null || item[key] === '' || item[key] === undefined ? state[key] : Number(item[key])]));
            }
            return state;
        },
        setComposerKeyframeValue(field, value) {
            const keyframe = this.composerSelectedKeyframe; if (!keyframe || !['x', 'y', 'width', 'height', 'opacity'].includes(field)) return;
            if (value === '') keyframe[field] = null;
            else {
                let number = Number(value); if (!Number.isFinite(number)) return;
                if (field === 'width' || field === 'height') number = Math.max(16, Math.round(number));
                else if (field === 'opacity') number = Math.max(0, Math.min(1, number));
                else number = Math.round(number);
                keyframe[field] = number;
            }
            this.syncComposerPreview();
        },
        setComposerKeyframeFrame(value) {
            const clip = this.composerSelectedClip, keyframe = this.composerSelectedKeyframe;
            if (!clip || !keyframe || this.composerIsProtectedKeyframe(clip, keyframe)) return;
            const lastFrame = Math.max(1, this.composerFrameNumber(clip.duration)) - 1;
            if (lastFrame <= 1) return;
            const frame = Math.max(1, Math.min(lastFrame - 1, Math.round(Number(value) || 0)));
            if (clip.keyframes.some(item => item.id !== keyframe.id && item.frame === frame)) return;
            keyframe.frame = frame;
            clip.keyframes = this.composerClipKeyframes(clip);
            this.composerPlayhead = this.quantizeComposerTime(clip.start + this.composerTimeFromFrame(frame));
            this.syncComposerPreview();
        },
        composerPreviewAudioClips() {
            return this.composerProject.clips.filter(clip => {
                const source = this.composerSource(clip.sourceId), track = this.composerTrack(clip.trackId);
                if (!source?.hasAudio || !track || !clip.audioEnabled || this.composerPlayhead < clip.start || this.composerPlayhead >= clip.start + clip.duration) return false;
                return track.kind === 'audio' ? !track.muted : track.kind === 'video' && track.muted;
            });
        },
        composerClipStyle(clip) { const color = clip.color || '#3b82f6'; return `left:${clip.start * this.composerScale}px;width:${Math.max(18, clip.duration * this.composerScale)}px;background:${color};border-color:${color}`;
        },
        composerPreviewStyle(clip) {
            const settings = this.composerProject.settings;
            const state = this.composerVisualStateAt(clip);
            return `left:${state.x / settings.width * 100}%;top:${state.y / settings.height * 100}%;width:${state.width / settings.width * 100}%;height:${state.height / settings.height * 100}%;opacity:${state.opacity}`;
        },
        composerPreviewMaskStyle(clip) {
            const mask = this.composerSource(clip.maskSourceId); if (!mask?.hasImage) return '';
            const url = this.composerSourceUrl(mask.id), mode = mask.hasAlpha ? 'alpha' : 'luminance';
            return `mask-image:url(${url});mask-size:100% 100%;mask-repeat:no-repeat;mask-mode:${mode};-webkit-mask-image:url(${url});-webkit-mask-size:100% 100%;-webkit-mask-repeat:no-repeat`;
        },
        composerPreviewClips() {
            const tracks = new Map(this.composerProject.tracks.map(track => [track.id, track]));
            return this.composerProject.clips.filter(clip => {
                const source = this.composerSource(clip.sourceId), track = tracks.get(clip.trackId);
                return (source?.hasVideo || source?.hasImage) && track?.kind === 'video' && !track.muted && this.composerPlayhead >= clip.start && this.composerPlayhead < clip.start + clip.duration;
            }).sort((a, b) => (tracks.get(a.trackId)?.order || 0) - (tracks.get(b.trackId)?.order || 0));
        },
        composerPushHistory() {
            this.composerHistory.push(copyComposerProject(this.composerProject));
            if (this.composerHistory.length > 100) this.composerHistory.shift();
            this.composerFuture = [];
        },
        composerChanged() {
            this.normalizeComposerTimeline();
            this.composerProject = copyComposerProject(this.composerProject);
            this.scheduleComposerSave(); this.icons();
        },
        cleanComposerGroups() {
            const groups = new Map();
            this.composerProject.clips.forEach(clip => { if (clip.groupId) groups.set(clip.groupId, [...(groups.get(clip.groupId) || []), clip]); });
            for (const [groupId, members] of groups) {
                const sameTrack = new Set(members.map(clip => clip.trackId)).size === 1;
                const ordered = sameTrack ? this.composerTrackClips(members[0].trackId) : [];
                const positions = members.map(clip => ordered.findIndex(item => item.id === clip.id)).sort((a, b) => a - b);
                const consecutive = positions.every((position, index) => position === positions[0] + index);
                if (members.length < 2 || !sameTrack || !consecutive) this.composerProject.clips.forEach(clip => { if (clip.groupId === groupId) clip.groupId = null; });
            }
        },
        normalizeComposerTimeline() {
            this.composerProject.tracks.forEach(track => {
                let cursor = 0;
                this.composerTrackClips(track.id).forEach(clip => {
                    const isVideoTrack = track.kind === 'video';
                    clip.duration = this.quantizeComposerTime(clip.duration, isVideoTrack ? 2 : 1);
                    clip.start = this.quantizeComposerTime(Math.max(cursor, Math.max(0, Number(clip.start) || 0)));
                    const durationFrames = Math.max(1, this.composerFrameNumber(clip.duration)), base = this.composerBaseVisualState(clip), byFrame = new Map();
                    (Array.isArray(clip.keyframes) ? clip.keyframes : []).forEach(keyframe => {
                        let frame = Math.max(0, Math.round(Number(keyframe.frame) || 0));
                        if (keyframe.endpoint === 'start') frame = 0;
                        if (keyframe.endpoint === 'end') frame = durationFrames - 1;
                        if (frame >= durationFrames) return;
                        byFrame.set(frame, {
                            id: keyframe.id || composerId('keyframe'), frame,
                            endpoint: keyframe.endpoint === 'start' || keyframe.endpoint === 'end' ? keyframe.endpoint : null,
                            transition: ['hold', 'linear', 'ease'].includes(keyframe.transition) ? keyframe.transition : 'linear',
                            x: keyframe.x === null || keyframe.x === '' || keyframe.x === undefined ? null : Math.round(Number(keyframe.x)),
                            y: keyframe.y === null || keyframe.y === '' || keyframe.y === undefined ? null : Math.round(Number(keyframe.y)),
                            width: keyframe.width === null || keyframe.width === '' || keyframe.width === undefined ? null : Math.max(16, Math.round(Number(keyframe.width))),
                            height: keyframe.height === null || keyframe.height === '' || keyframe.height === undefined ? null : Math.max(16, Math.round(Number(keyframe.height))),
                            opacity: keyframe.opacity === null || keyframe.opacity === '' || keyframe.opacity === undefined ? null : Math.max(0, Math.min(1, Number(keyframe.opacity))),
                        });
                    });
                    if (isVideoTrack) {
                        const endFrame = durationFrames - 1;
                        let start = [...byFrame.values()].find(keyframe => keyframe.endpoint === 'start') || byFrame.get(0);
                        if (!start) start = { id: composerId('keyframe'), frame: 0, transition: 'hold', x: Math.round(base.x), y: Math.round(base.y), width: Math.max(16, Math.round(base.width)), height: Math.max(16, Math.round(base.height)), opacity: base.opacity };
                        start.frame = 0; start.endpoint = 'start'; start.transition = 'hold'; byFrame.set(0, start);
                        let end = [...byFrame.values()].find(keyframe => keyframe.endpoint === 'end') || byFrame.get(endFrame);
                        if (!end || end === start) {
                            const state = this.composerVisualStateAtFrame({ ...clip, keyframes: [...byFrame.values()] }, endFrame);
                            end = { id: composerId('keyframe'), frame: endFrame, transition: 'linear', x: Math.round(state.x), y: Math.round(state.y), width: Math.max(16, Math.round(state.width)), height: Math.max(16, Math.round(state.height)), opacity: Math.max(0, Math.min(1, state.opacity)) };
                        }
                        end.frame = endFrame; end.endpoint = 'end'; byFrame.set(endFrame, end);
                    }
                    clip.keyframes = [...byFrame.values()].sort((a, b) => a.frame - b.frame);
                    cursor = this.quantizeComposerTime(clip.start + clip.duration);
                });
            });
            if (this.composerSelectedKeyframeId && !this.composerSelectedKeyframe) this.composerSelectedKeyframeId = '';
            this.cleanComposerGroups();
        },
        composerUndo() {
            const previous = this.composerHistory.pop(); if (!previous) return;
            this.composerFuture.push(copyComposerProject(this.composerProject)); this.composerProject = previous;
            this.composerSelectedClipId = ''; this.composerSelectedClipIds = []; this.composerSelectedKeyframeId = ''; this.scheduleComposerSave();
        },
        composerRedo() {
            const next = this.composerFuture.pop(); if (!next) return;
            this.composerHistory.push(copyComposerProject(this.composerProject)); this.composerProject = next;
            this.composerSelectedClipId = ''; this.composerSelectedClipIds = []; this.composerSelectedKeyframeId = ''; this.scheduleComposerSave();
        },
        beginComposerEdit() { this.composerEditSnapshot = copyComposerProject(this.composerProject); },
        reconcileComposerEdit(before) {
            const current = this.composerSelectedClip, previous = before?.clips?.find(item => item.id === current?.id);
            if (!current || !previous) return;
            if (current.trackId !== previous.trackId) {
                const targetId = current.trackId, target = this.composerTrack(targetId), origin = this.composerTrack(previous.trackId);
                current.trackId = previous.trackId;
                if (!target || target.locked || target.kind !== origin?.kind) return;
                const plan = this.composerMovePlan(current, current.start, targetId);
                for (const [id, start] of plan.starts) { const clip = this.composerProject.clips.find(item => item.id === id); if (clip) clip.start = start; }
                this.composerProject.clips.forEach(clip => { if (plan.movingIds.has(clip.id)) clip.trackId = targetId; });
                return;
            }
            if (Math.abs(current.start - previous.start) > COMPOSER_TIME_EPSILON) {
                const desired = this.quantizeComposerTime(Math.max(0, Number(current.start) || 0)); current.start = previous.start;
                const plan = this.composerMovePlan(current, desired, previous.trackId);
                for (const [id, start] of plan.starts) { const clip = this.composerProject.clips.find(item => item.id === id); if (clip) clip.start = start; }
                return;
            }
            if (Math.abs(Number(current.speed) - Number(previous.speed)) > COMPOSER_TIME_EPSILON) {
                const desiredSpeed = Number(current.speed);
                current.speed = previous.speed; current.duration = previous.duration;
                this.retimeComposerClip(current, desiredSpeed);
                return;
            }
            if (Math.abs(current.duration - previous.duration) > COMPOSER_TIME_EPSILON) {
                const desiredEnd = this.quantizeComposerTime(current.start + Math.max(this.composerFrameDuration, Number(current.duration) || this.composerFrameDuration)); current.duration = previous.duration;
                const plan = this.composerTrimPlan(current, 'right', desiredEnd); current.duration = plan.duration;
                for (const [id, start] of plan.starts) { const clip = this.composerProject.clips.find(item => item.id === id); if (clip) clip.start = start; }
            }
        },
        finishComposerEdit() {
            if (this.composerEditSnapshot) {
                this.reconcileComposerEdit(this.composerEditSnapshot);
                this.composerHistory.push(this.composerEditSnapshot); this.composerHistory = this.composerHistory.slice(-100);
                this.composerFuture = []; this.composerEditSnapshot = null;
            }
            this.composerChanged();
        },
        setComposerResolution(value) {
            const resolutions = { '1280x720': [1280, 720], '1920x1080': [1920, 1080], '3840x2160': [3840, 2160], '1080x1920': [1080, 1920] };
            const selected = resolutions[value]; if (!selected) return;
            this.composerPushHistory();
            [this.composerProject.settings.width, this.composerProject.settings.height] = selected;
            this.composerChanged();
        },
        scheduleComposerSave() {
            if (this.composerSaveTimer) clearTimeout(this.composerSaveTimer);
            this.composerSaveTimer = setTimeout(() => this.saveComposerProject().catch(error => this.fail(error)), 350);
        },
        async saveComposerProject() {
            await responsePayload(await fetch(`${STUDIO_API}/studio-drafts/${encodeURIComponent('ai2apps.video.composer')}`, {
                method: 'PUT', credentials: 'same-origin', headers: { ...this.draftHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({ draft: { project: this.composerProject, sources: this.composerSources, documentPath: this.composerDocumentPath } }),
            }));
        },
        async loadComposerProject() {
            try {
                const record = await responsePayload(await fetch(`${STUDIO_API}/studio-drafts/${encodeURIComponent('ai2apps.video.composer')}`, { credentials: 'same-origin', headers: this.draftHeaders() }));
                if (record.draft?.project?.schema === 'ai2apps.video-composition/v1') {
                    this.composerProject = record.draft.project;
                    if (typeof this.composerProject.settings.snapping !== 'boolean') this.composerProject.settings.snapping = true;
                    this.composerProject.clips.forEach((clip, index) => {
                        if (!clip.color) clip.color = COMPOSER_CLIP_COLORS[index % COMPOSER_CLIP_COLORS.length];
                        if (typeof clip.groupId !== 'string') clip.groupId = null;
                        if (typeof clip.maskSourceId !== 'string') clip.maskSourceId = null;
                    });
                    this.normalizeComposerTimeline();
                }
                if (Array.isArray(record.draft?.sources)) this.composerSources = record.draft.sources;
                if (typeof record.draft?.documentPath === 'string') this.composerDocumentPath = record.draft.documentPath;
            } catch (error) { this.fail(error); }
        },
        composerProjectFileName() {
            const stem = String(this.composerProject.title || 'Untitled composition').trim().replace(/[\\/:*?"<>|]/g, '-').replace(/^\.+|\.+$/g, '').slice(0, 120) || 'Untitled composition';
            return `${stem}.ai2video`;
        },
        composerDocumentHeaders() { return { ...this.draftHeaders(), 'Content-Type': 'application/json' }; },
        applyComposerDocument(record) {
            if (record?.project?.schema !== 'ai2apps.video-composition/v1' || !Array.isArray(record.sources)) throw new Error(tr('video_studio.composer.project_invalid'));
            if (this.composerPlaying) this.toggleComposerPreview();
            this.composerProject = record.project; this.composerSources = record.sources; this.composerDocumentPath = record.path || '';
            this.composerHistory = []; this.composerFuture = []; this.composerSelectedClipId = ''; this.composerSelectedClipIds = []; this.composerSelectedKeyframeId = '';
            this.composerPlayhead = 0; this.normalizeComposerTimeline(); this.scheduleComposerSave(); this.icons();
        },
        async openComposerDocument(event) {
            const file = Array.from(event?.target?.files || [])[0];
            if (!file) return;
            try {
                const sourcePath = nativeFilePath(file);
                if (!sourcePath) throw new Error(tr('video_studio.composer.project_native_required'));
                const record = await responsePayload(await fetch(`${STUDIO_API}/composer/projects/open`, {
                    method: 'POST', credentials: 'same-origin', headers: this.composerDocumentHeaders(), body: JSON.stringify({ sourcePath }),
                }));
                this.applyComposerDocument(record); this.notice = tr('video_studio.composer.project_opened', { name: file.name }); this.noticeTone = 'success';
            } catch (error) { this.fail(error); } finally { if (event?.target) event.target.value = ''; }
        },
        async writeComposerDocument(targetPath) {
            const record = await responsePayload(await fetch(`${STUDIO_API}/composer/projects/save`, {
                method: 'POST', credentials: 'same-origin', headers: this.composerDocumentHeaders(),
                body: JSON.stringify({ targetPath, project: this.composerProject, sourceIds: this.composerSources.map(source => source.id) }),
            }));
            this.composerDocumentPath = record.path; this.composerSources = record.sources;
            await this.saveComposerProject();
            this.notice = tr('video_studio.composer.project_saved', { name: record.path.split('/').pop() }); this.noticeTone = 'success';
        },
        async saveComposerDocument() {
            if (!this.composerDocumentPath) { this.$refs.composerSaveAs?.click(); return; }
            if (this.composerDocumentSaving) return;
            this.composerDocumentSaving = true;
            try { await this.writeComposerDocument(this.composerDocumentPath); }
            catch (error) { this.fail(error); }
            finally { this.composerDocumentSaving = false; this.icons(); }
        },
        async saveComposerDocumentAs(event) {
            const directory = selectedDirectory(event?.target?.files);
            if (!directory) { if (event?.target?.files?.length) this.fail(new Error(tr('video_studio.composer.project_folder_required'))); if (event?.target) event.target.value = ''; return; }
            const proposed = this.composerProjectFileName();
            let name = window.prompt(tr('video_studio.composer.project_file_name'), proposed);
            if (name === null) { event.target.value = ''; return; }
            name = String(name).trim().replace(/[\\/]/g, '-');
            if (!/\.(ai2video|json)$/i.test(name)) name += '.ai2video';
            if (!name || this.composerDocumentSaving) { event.target.value = ''; return; }
            if (Array.from(event.target.files || []).some(file => file.name === name) && !window.confirm(tr('video_studio.composer.project_confirm_overwrite', { name }))) { event.target.value = ''; return; }
            this.composerDocumentSaving = true;
            try { await this.writeComposerDocument(`${directory}/${name}`); }
            catch (error) { this.fail(error); }
            finally { this.composerDocumentSaving = false; event.target.value = ''; this.icons(); }
        },
        async registerComposerSource(payload) {
            return responsePayload(await fetch(`${STUDIO_API}/composer/sources`, {
                method: 'POST', credentials: 'same-origin', headers: { ...this.draftHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            }));
        },
        async importComposerFiles(filesOrEvent, targetTrackId = '', startAt = null) {
            const files = Array.from(filesOrEvent?.target?.files || filesOrEvent || []);
            if (!files.length || this.composerImporting) return;
            this.composerImporting = true;
            let cursor = startAt;
            try {
                for (const file of files) {
                    if (!String(file.type || '').match(/^(image|video|audio)\//)) continue;
                    const sourcePath = nativeFilePath(file);
                    let source;
                    if (sourcePath) {
                        source = await this.registerComposerSource({ sourcePath, name: file.name, mediaType: file.type });
                    } else {
                        const form = new FormData(); form.append('file', file, file.name); form.append('sourceAppId', APP_ID);
                        const imported = await responsePayload(await fetch('/v1/platform/gallery/assets/import', { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' }, body: form }));
                        source = await this.importComposerGalleryAsset(imported.asset, false);
                    }
                    const clip = this.addComposerSource(source, targetTrackId, cursor);
                    if (cursor !== null) cursor = clip.start + clip.duration;
                }
            } catch (error) { this.fail(error); } finally {
                this.composerImporting = false;
                if (filesOrEvent?.target) filesOrEvent.target.value = '';
                this.icons();
            }
        },
        async importComposerMask(filesOrEvent) {
            const file = Array.from(filesOrEvent?.target?.files || filesOrEvent || [])[0];
            const clipId = this.composerSelectedClipId;
            if (!file || !clipId || !String(file.type || '').startsWith('image/') || this.composerMaskImporting) return;
            this.composerMaskImporting = true;
            try {
                const sourcePath = nativeFilePath(file);
                let source;
                if (sourcePath) source = await this.registerComposerSource({ sourcePath, name: file.name, mediaType: file.type });
                else {
                    const form = new FormData(); form.append('file', file, file.name); form.append('sourceAppId', APP_ID);
                    const imported = await responsePayload(await fetch('/v1/platform/gallery/assets/import', { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' }, body: form }));
                    source = await this.importComposerGalleryAsset(imported.asset, false);
                }
                const clip = this.composerProject.clips.find(item => item.id === clipId); if (!clip) return;
                this.composerPushHistory();
                if (!this.composerSources.some(item => item.id === source.id)) this.composerSources.push(source);
                clip.maskSourceId = source.id;
                this.composerChanged();
            } catch (error) { this.fail(error); } finally {
                this.composerMaskImporting = false;
                if (filesOrEvent?.target) filesOrEvent.target.value = '';
                this.icons();
            }
        },
        setComposerMask(sourceId) {
            const clip = this.composerSelectedClip; if (!clip) return;
            if (sourceId && !this.composerSource(sourceId)?.hasImage) return;
            this.composerPushHistory(); clip.maskSourceId = sourceId || null; this.composerChanged();
        },
        setComposerClipSource(sourceId) {
            const clip = this.composerSelectedClip, source = this.composerSource(sourceId);
            if (!clip || !source || !this.composerCompatibleSources(clip).some(item => item.id === source.id) || clip.sourceId === source.id) return;
            this.composerPushHistory();
            clip.sourceId = source.id; clip.sourceStart = 0; clip.name = source.name;
            const maximum = source.hasImage ? clip.duration : this.quantizeComposerTime(Math.max(this.composerFrameDuration, (Number(source.duration) || 0) / clip.speed), 1);
            if (clip.duration > maximum + COMPOSER_TIME_EPSILON) {
                const plan = this.composerTrimPlan(clip, 'right', clip.start + maximum); clip.duration = plan.duration;
                for (const [id, start] of plan.starts) { const item = this.composerProject.clips.find(candidate => candidate.id === id); if (item) item.start = start; }
            }
            this.composerChanged(); this.syncComposerPreview();
        },
        async importComposerGalleryAsset(asset, add = true, targetTrackId = '', startAt = null) {
            if (!asset?.id || !['image', 'video', 'audio'].includes(asset.kind)) throw new Error(tr('video_studio.error.asset_type'));
            const instanceId = window.AI2AppsCapabilities?.appInstanceId?.() || '';
            const reference = await responsePayload(await fetch(`/v1/platform/gallery/assets/${encodeURIComponent(asset.id)}/resource-handles`, {
                method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
                body: JSON.stringify({ consumerAppId: APP_ID, appInstanceId: instanceId }),
            }));
            const source = await this.registerComposerSource({ resourceHandle: reference.resourceHandle });
            if (add) this.addComposerSource(source, targetTrackId, startAt);
            return source;
        },
        addComposerSource(source, targetTrackId = '', startAt = null) {
            this.composerPushHistory();
            if (!this.composerSources.some(item => item.id === source.id)) this.composerSources.push(source);
            const timelineKind = source.kind === 'audio' ? 'audio' : 'video';
            let track = targetTrackId ? this.composerTrack(targetTrackId) : null;
            if (track && (track.kind !== timelineKind || track.locked)) throw new Error(track.locked ? 'The target track is locked.' : `Drop this ${source.kind} source on a ${timelineKind} track.`);
            if (!track) track = this.composerProject.tracks.find(item => item.kind === timelineKind && !item.locked);
            if (!track) track = this.addComposerTrack(timelineKind, false);
            const trackEnd = Math.max(0, ...this.composerTrackClips(track.id).map(clip => clip.start + clip.duration));
            const start = this.quantizeComposerTime(startAt === null ? trackEnd : Math.max(0, Number(startAt) || 0));
            const settings = this.composerProject.settings;
            const visual = source.hasVideo || source.hasImage;
            const scale = visual && source.width ? Math.min(settings.width / source.width, settings.height / source.height, 1) : 1;
            const clip = {
                id: composerId('clip'), sourceId: source.id, trackId: track.id, name: source.name,
                start, sourceStart: 0, duration: this.quantizeComposerTime(source.hasImage ? 1 : Math.max(this.composerFrameDuration, source.duration || 5), 1), speed: 1,
                volume: 1, fadeIn: 0, fadeOut: 0, x: 0, y: 0,
                width: visual ? Math.round((source.width || settings.width) * scale) : null,
                height: visual ? Math.round((source.height || settings.height) * scale) : null,
                opacity: 1, audioEnabled: true, groupId: null,
                maskSourceId: null,
                color: COMPOSER_CLIP_COLORS[this.composerProject.clips.length % COMPOSER_CLIP_COLORS.length],
                keyframes: [],
            };
            this.insertComposerClip(clip); this.composerProject.clips.push(clip); this.setComposerSelection([clip.id], clip.id); this.composerChanged();
            return clip;
        },
        insertComposerClip(clip) {
            clip.start = this.quantizeComposerTime(clip.start);
            clip.duration = this.quantizeComposerTime(clip.duration, 1);
            const ordered = this.composerTrackClips(clip.trackId).filter(item => item.id !== clip.id);
            const insertion = ordered.findIndex(item => item.start >= clip.start - COMPOSER_TIME_EPSILON);
            const previous = insertion < 0 ? ordered[ordered.length - 1] : ordered[insertion - 1];
            if (previous) clip.start = Math.max(clip.start, previous.start + previous.duration);
            let cursor = clip.start + clip.duration;
            const later = insertion < 0 ? [] : ordered.slice(insertion);
            later.forEach(item => { if (item.start < cursor - COMPOSER_TIME_EPSILON) item.start = cursor; cursor = item.start + item.duration; });
        },
        resetComposerClipSize(clip) {
            const source = this.composerSource(clip.sourceId);
            if (!source?.width || !source?.height || this.composerTrack(clip.trackId)?.locked) return;
            this.composerPushHistory(); const keyframe = this.composerKeyframeAtPlayhead(clip);
            if (keyframe) { keyframe.width = source.width; keyframe.height = source.height; }
            else { const state = this.composerBaseVisualState(clip); this.resizeComposerClipVisual(clip, source.width, source.height, state.width, state.height); }
            this.composerChanged();
        },
        translateComposerClipVisual(clip, dx, dy) {
            clip.x = Math.round((Number(clip.x) || 0) + dx); clip.y = Math.round((Number(clip.y) || 0) + dy);
            this.composerClipKeyframes(clip).forEach(keyframe => {
                if (keyframe.x !== null && keyframe.x !== '' && keyframe.x !== undefined) keyframe.x = Math.round(Number(keyframe.x) + dx);
                if (keyframe.y !== null && keyframe.y !== '' && keyframe.y !== undefined) keyframe.y = Math.round(Number(keyframe.y) + dy);
            });
        },
        resizeComposerClipVisual(clip, nextWidth, nextHeight, previousWidth, previousHeight) {
            const scaleX = nextWidth / Math.max(1, previousWidth), scaleY = nextHeight / Math.max(1, previousHeight);
            clip.width = Math.max(16, Math.round(nextWidth)); clip.height = Math.max(16, Math.round(nextHeight));
            this.composerClipKeyframes(clip).forEach(keyframe => {
                if (keyframe.width !== null && keyframe.width !== '' && keyframe.width !== undefined) keyframe.width = Math.max(16, Math.round(Number(keyframe.width) * scaleX));
                if (keyframe.height !== null && keyframe.height !== '' && keyframe.height !== undefined) keyframe.height = Math.max(16, Math.round(Number(keyframe.height) * scaleY));
            });
        },
        composerTrackDropTime(event) {
            const row = event.currentTarget, bounds = row.getBoundingClientRect();
            return Math.max(0, (event.clientX - bounds.left) / this.composerScale);
        },
        enterComposerTrackDrop(track) { this.galleryDragActive = false; this.composerDropTrackId = track.id; },
        leaveComposerTrackDrop(event, track) { if (this.composerDropTrackId === track.id && !event.currentTarget.contains(event.relatedTarget)) this.composerDropTrackId = ''; },
        async dropComposerOnTrack(event, track) {
            this.galleryDragActive = false; this.composerDropTrackId = '';
            if (track.locked) { this.fail(new Error('The target track is locked.')); return; }
            try {
                const at = this.snapComposerTime(this.composerTrackDropTime(event));
                const localFiles = Array.from(event.dataTransfer?.files || []);
                if (localFiles.length) { await this.importComposerFiles(localFiles, track.id, at); return; }
                const assetId = event.dataTransfer?.getData('application/x-ai2apps-gallery-asset') || '';
                if (!assetId) return;
                const kind = String(event.dataTransfer?.getData('application/x-ai2apps-gallery-kind') || 'video');
                await this.importComposerGalleryAsset({ id: assetId, name: event.dataTransfer?.getData('text/plain') || 'Media', kind }, true, track.id, at);
            } catch (error) { this.fail(error); }
        },
        addComposerTrack(kind = 'video', recordHistory = true) {
            if (recordHistory) this.composerPushHistory();
            const count = this.composerProject.tracks.filter(track => track.kind === kind).length + 1;
            const track = { id: composerId('track'), kind, name: `${kind === 'video' ? 'Video' : 'Audio'} ${count}`, order: this.composerProject.tracks.length, muted: false, locked: false };
            const selectedTrackId = this.composerSelectedClip?.trackId;
            const selectedIndex = this.composerProject.tracks.findIndex(item => item.id === selectedTrackId);
            this.composerProject.tracks.splice(selectedIndex >= 0 ? selectedIndex + 1 : this.composerProject.tracks.length, 0, track);
            this.composerProject.tracks.forEach((item, index) => { item.order = index; });
            if (recordHistory) this.composerChanged(); return track;
        },
        removeComposerTrack(track) {
            if (this.composerProject.tracks.length <= 1) return;
            const clipCount = this.composerProject.clips.filter(clip => clip.trackId === track.id).length;
            if (clipCount && !window.confirm(tr('video_studio.composer.confirm_remove_track', { name: track.name, count: clipCount }))) return;
            this.composerPushHistory();
            const ids = new Set(this.composerProject.clips.filter(clip => clip.trackId === track.id).map(clip => clip.id));
            this.composerProject.tracks = this.composerProject.tracks.filter(item => item.id !== track.id);
            this.composerProject.clips = this.composerProject.clips.filter(clip => clip.trackId !== track.id);
            if (this.composerSelectedClipIds.some(id => ids.has(id))) this.setComposerSelection([], '');
            this.composerProject.tracks.forEach((item, index) => { item.order = index; }); this.composerChanged();
        },
        toggleComposerTrack(track, key) { this.composerPushHistory(); track[key] = !track[key]; this.composerChanged(); },
        composerTrackOutputIcon(track) {
            return track.kind === 'video' ? (track.muted ? 'eye-off' : 'eye') : (track.muted ? 'volume-x' : 'volume-2');
        },
        composerTrackOutputLabel(track) {
            if (track.kind === 'video') return tr(track.muted ? 'video_studio.composer.show_track' : 'video_studio.composer.hide_track');
            return tr(track.muted ? 'video_studio.composer.unmute_track' : 'video_studio.composer.mute_track');
        },
        showComposerHoverTip(event, text) {
            const bounds = event.currentTarget.getBoundingClientRect();
            const tooltipHalfWidth = 88;
            // The App Shell mounts Mini-App content beside its own rail. Pointer
            // coordinates remain in the rendered viewport while element bounds
            // can be relative to the mounted content context, so anchor the tip
            // horizontally to the actual pointer instead of mixing the two spaces.
            const frameOffsetX = window.frameElement?.getBoundingClientRect?.().left || 0;
            const pointerX = (Number.isFinite(event.clientX) ? event.clientX : bounds.left + bounds.width / 2) + frameOffsetX;
            this.composerHoverTip = {
                text,
                left: Math.max(tooltipHalfWidth, Math.min(window.innerWidth - tooltipHalfWidth, pointerX)),
                top: Math.max(30, bounds.top - 6),
            };
        },
        hideComposerHoverTip() { this.composerHoverTip = { text: '', left: 0, top: 0 }; },
        composerTrackAcceptsClip(track, clip) {
            const origin = this.composerTrack(clip?.trackId);
            return Boolean(track && clip && !track.locked && track.kind === origin?.kind);
        },
        setComposerSelection(ids, primaryId = '') {
            const available = new Set(this.composerProject.clips.map(clip => clip.id));
            const previousPrimary = this.composerSelectedClipId;
            this.composerSelectedClipIds = [...new Set(ids)].filter(id => available.has(id));
            this.composerSelectedClipId = this.composerSelectedClipIds.includes(primaryId) ? primaryId : (this.composerSelectedClipIds[0] || '');
            if (this.composerSelectedClipId !== previousPrimary) this.composerSelectedKeyframeId = '';
        },
        isComposerClipSelected(clip) { return this.composerSelectedClipIds.includes(clip.id); },
        composerClipSelectionUnit(clip) {
            return clip.groupId ? this.composerProject.clips.filter(item => item.groupId === clip.groupId).map(item => item.id) : [clip.id];
        },
        composerDragUnit(anchorClip) {
            const ordered = this.composerTrackClips(anchorClip.trackId), selected = new Set(this.composerSelectedClipIds);
            const anchorIndex = ordered.findIndex(item => item.id === anchorClip.id);
            if (anchorIndex < 0 || !selected.has(anchorClip.id)) return anchorClip.groupId ? this.composerProject.clips.filter(item => item.groupId === anchorClip.groupId) : [anchorClip];
            let first = anchorIndex, last = anchorIndex;
            while (first > 0 && selected.has(ordered[first - 1].id)) first -= 1;
            while (last + 1 < ordered.length && selected.has(ordered[last + 1].id)) last += 1;
            return ordered.slice(first, last + 1);
        },
        syncComposerPlayheadToClip(clip) {
            if (!clip) return;
            const start = this.quantizeComposerTime(clip.start), end = this.quantizeComposerTime(clip.start + clip.duration);
            if (this.composerPlayhead >= start && this.composerPlayhead <= end) return;
            this.composerPlayhead = Math.abs(this.composerPlayhead - start) <= Math.abs(this.composerPlayhead - end) ? start : end;
            this.composerPlayheadSnapped = false;
            this.syncComposerPreview();
        },
        selectComposerClip(clip, event = null, syncPlayhead = true) {
            const unit = this.composerClipSelectionUnit(clip), toggle = Boolean(event?.metaKey || event?.ctrlKey);
            if (event?.shiftKey && this.composerSelectedClip) {
                const anchor = this.composerSelectedClip;
                if (anchor.trackId === clip.trackId) {
                    const ordered = this.composerTrackClips(clip.trackId), from = ordered.findIndex(item => item.id === anchor.id), to = ordered.findIndex(item => item.id === clip.id);
                    const range = ordered.slice(Math.min(from, to), Math.max(from, to) + 1).map(item => item.id);
                    this.setComposerSelection(range, clip.id);
                } else this.setComposerSelection(unit, clip.id);
            } else if (toggle) {
                const selected = new Set(this.composerSelectedClipIds), shouldRemove = unit.every(id => selected.has(id));
                unit.forEach(id => shouldRemove ? selected.delete(id) : selected.add(id));
                this.setComposerSelection([...selected], shouldRemove ? this.composerSelectedClipId : clip.id);
            } else this.setComposerSelection(unit, clip.id);
            if (syncPlayhead) this.syncComposerPlayheadToClip(clip);
        },
        addComposerKeyframe() {
            const clip = this.composerSelectedClip; if (!this.composerCanAddKeyframe || !clip) return;
            const frame = Math.max(0, Math.min(this.composerFrameNumber(clip.duration) - 1, this.composerFrameNumber(this.composerPlayhead - clip.start)));
            const existing = this.composerClipKeyframes(clip).find(keyframe => keyframe.frame === frame);
            if (existing) { this.composerSelectedKeyframeId = existing.id; return; }
            this.composerPushHistory(); const state = this.composerVisualStateAtFrame(clip, frame);
            const keyframe = { id: composerId('keyframe'), frame, endpoint: null, transition: 'linear', x: Math.round(state.x), y: Math.round(state.y), width: Math.max(16, Math.round(state.width)), height: Math.max(16, Math.round(state.height)), opacity: Math.max(0, Math.min(1, state.opacity)) };
            clip.keyframes = [...this.composerClipKeyframes(clip), keyframe].sort((a, b) => a.frame - b.frame);
            this.composerSelectedKeyframeId = keyframe.id; this.composerChanged(); this.syncComposerPreview();
        },
        selectComposerKeyframe(keyframe) {
            const clip = this.composerSelectedClip; if (!clip || !keyframe) return;
            this.composerSelectedKeyframeId = keyframe.id;
            this.composerPlayhead = this.quantizeComposerTime(clip.start + this.composerTimeFromFrame(keyframe.frame));
            this.syncComposerPreview();
        },
        deleteComposerKeyframe() {
            const clip = this.composerSelectedClip, keyframe = this.composerSelectedKeyframe; if (!clip || !keyframe) return;
            if (this.composerIsProtectedKeyframe(clip, keyframe)) return;
            this.composerPushHistory(); clip.keyframes = this.composerClipKeyframes(clip).filter(item => item.id !== keyframe.id);
            this.composerSelectedKeyframeId = ''; this.composerChanged(); this.syncComposerPreview();
        },
        groupComposerSelection() {
            if (!this.composerCanGroupSelection) return;
            this.composerPushHistory(); const groupId = composerId('group');
            this.composerSelectedClips.forEach(clip => { clip.groupId = groupId; }); this.composerChanged();
        },
        ungroupComposerSelection() {
            if (!this.composerCanUngroupSelection) return;
            this.composerPushHistory(); const groupIds = new Set(this.composerSelectedClips.map(clip => clip.groupId).filter(Boolean));
            this.composerProject.clips.forEach(clip => { if (groupIds.has(clip.groupId)) clip.groupId = null; }); this.composerChanged();
        },
        deleteComposerClip() {
            if (!this.composerSelectedClip) return; this.composerPushHistory();
            const ids = new Set(this.composerSelectedClipIds.length ? this.composerSelectedClipIds : [this.composerSelectedClipId]);
            this.composerProject.clips = this.composerProject.clips.filter(clip => !ids.has(clip.id));
            this.setComposerSelection([], ''); this.composerChanged();
        },
        splitComposerKeyframes(clip, splitFrame) {
            const state = this.composerVisualStateAtFrame(clip, splitFrame);
            const leftEndState = this.composerVisualStateAtFrame(clip, splitFrame - 1);
            const makeEndpoint = (endpoint, frame, value) => ({ id: composerId('keyframe'), frame, endpoint, transition: endpoint === 'start' ? 'hold' : 'linear', x: Math.round(value.x), y: Math.round(value.y), width: Math.max(16, Math.round(value.width)), height: Math.max(16, Math.round(value.height)), opacity: Math.max(0, Math.min(1, value.opacity)) });
            const middle = this.composerClipKeyframes(clip).filter(keyframe => !this.composerIsEndpointKeyframe(keyframe));
            const left = [makeEndpoint('start', 0, this.composerVisualStateAtFrame(clip, 0)), ...middle.filter(keyframe => keyframe.frame < splitFrame), makeEndpoint('end', splitFrame - 1, leftEndState)];
            const durationFrames = this.composerFrameNumber(clip.duration), rightDuration = durationFrames - splitFrame;
            const right = [makeEndpoint('start', 0, state), ...middle.filter(keyframe => keyframe.frame > splitFrame).map(keyframe => ({ ...keyframe, id: composerId('keyframe'), frame: keyframe.frame - splitFrame })), makeEndpoint('end', rightDuration - 1, this.composerVisualStateAtFrame(clip, durationFrames - 1))];
            return { state, left, right };
        },
        splitComposerClip() {
            const clip = this.composerSelectedClip, splitAt = this.quantizeComposerTime(this.composerPlayhead), offset = splitAt - (clip?.start || 0);
            if (!clip || offset < this.composerFrameDuration || offset > clip.duration - this.composerFrameDuration) return;
            this.composerPushHistory(); const keyframes = this.splitComposerKeyframes(clip, this.composerFrameNumber(offset));
            const right = { ...clip, id: composerId('clip'), start: splitAt, sourceStart: clip.sourceStart + offset * clip.speed, duration: this.quantizeComposerTime(clip.duration - offset, 1), fadeIn: 0, keyframes: keyframes.right, ...keyframes.state };
            clip.duration = offset; clip.fadeOut = 0; clip.keyframes = keyframes.left; this.composerSelectedKeyframeId = '';
            this.composerProject.clips.push(right); this.setComposerSelection(this.composerClipSelectionUnit(right), right.id); this.composerChanged();
        },
        composerMovePlan(anchorClip, desiredStart, targetTrackId, movingClips = null) {
            const moving = movingClips?.length ? movingClips : (anchorClip.groupId ? this.composerProject.clips.filter(item => item.groupId === anchorClip.groupId) : [anchorClip]);
            const movingIds = new Set(moving.map(item => item.id)), originTrackId = anchorClip.trackId;
            const orderedMoving = moving.slice().sort((a, b) => a.start - b.start);
            const anchorStart = orderedMoving[0].start, starts = new Map();
            let delta = desiredStart - anchorStart;
            if (targetTrackId === originTrackId) {
                const ordered = this.composerTrackClips(originTrackId), firstIndex = ordered.findIndex(item => movingIds.has(item.id));
                const lastIndex = ordered.reduce((result, item, index) => movingIds.has(item.id) ? index : result, firstIndex);
                const previous = firstIndex > 0 ? ordered[firstIndex - 1] : null;
                if (previous) delta = Math.max(delta, previous.start + previous.duration - anchorStart);
                else delta = Math.max(delta, -anchorStart);
                orderedMoving.forEach(item => starts.set(item.id, item.start + delta));
                let cursor = Math.max(...orderedMoving.map(item => starts.get(item.id) + item.duration));
                let previousOriginalEnd = Math.max(...orderedMoving.map(item => item.start + item.duration));
                for (const item of ordered.slice(lastIndex + 1)) {
                    const attached = Math.abs(item.start - previousOriginalEnd) <= COMPOSER_TIME_EPSILON;
                    const nextStart = attached || item.start < cursor - COMPOSER_TIME_EPSILON ? cursor : item.start;
                    starts.set(item.id, nextStart); cursor = nextStart + item.duration;
                    previousOriginalEnd = item.start + item.duration;
                }
            } else {
                const targetClips = this.composerTrackClips(targetTrackId).filter(item => !movingIds.has(item.id));
                const insertion = targetClips.findIndex(item => item.start >= desiredStart);
                const before = insertion < 0 ? targetClips[targetClips.length - 1] : targetClips[insertion - 1];
                if (before) delta = Math.max(delta, before.start + before.duration - anchorStart);
                else delta = Math.max(delta, -anchorStart);
                orderedMoving.forEach(item => starts.set(item.id, item.start + delta));
                let cursor = Math.max(...orderedMoving.map(item => starts.get(item.id) + item.duration));
                const later = insertion < 0 ? [] : targetClips.slice(insertion);
                for (const item of later) {
                    const nextStart = item.start < cursor - COMPOSER_TIME_EPSILON ? cursor : item.start;
                    starts.set(item.id, nextStart); cursor = nextStart + item.duration;
                }
            }
            return { starts, movingIds, targetTrackId };
        },
        snapComposerBlockStart(value, clips, trackId, feedback = null) {
            value = this.quantizeComposerTime(value);
            if (this.composerProject.settings.snapping === false) { if (feedback) feedback.snapped = false; return value; }
            const ids = new Set(clips.map(item => item.id)), first = Math.min(...clips.map(item => item.start));
            const span = Math.max(...clips.map(item => item.start + item.duration)) - first;
            const candidates = [0, this.composerPlayhead];
            this.composerProject.clips.forEach(item => { if (!ids.has(item.id) && item.trackId === trackId) candidates.push(item.start, item.start + item.duration); });
            let result = value, distance = Infinity;
            for (const edge of [value, value + span]) for (const candidate of candidates) {
                const current = Math.abs(candidate - edge);
                if (current < distance) { distance = current; result = value + candidate - edge; }
            }
            const snapped = distance * this.composerScale <= 12;
            if (feedback) feedback.snapped = snapped;
            return this.quantizeComposerTime(snapped ? Math.max(0, result) : value);
        },
        snapComposerTime(value, clipId = '') {
            value = this.quantizeComposerTime(value);
            if (this.composerProject.settings.snapping === false) return value;
            const candidates = [0, this.composerPlayhead];
            this.composerProject.clips.forEach(clip => { if (clip.id !== clipId) candidates.push(clip.start, clip.start + clip.duration); });
            const nearest = candidates.reduce((best, item) => Math.abs(item - value) < Math.abs(best - value) ? item : best, value);
            return this.quantizeComposerTime(Math.abs(nearest - value) * this.composerScale <= 12 ? nearest : value);
        },
        snapComposerPlayhead(value, feedback = null) {
            value = this.quantizeComposerTime(Math.max(0, Math.min(this.composerDuration, value)));
            if (this.composerProject.settings.snapping === false) { if (feedback) feedback.snapped = false; return value; }
            const candidates = [0];
            this.composerProject.clips.forEach(clip => candidates.push(clip.start, clip.start + clip.duration));
            const nearest = candidates.reduce((best, item) => Math.abs(item - value) < Math.abs(best - value) ? item : best, value);
            const snapped = Math.abs(nearest - value) * this.composerScale <= 12;
            if (feedback) feedback.snapped = snapped;
            return this.quantizeComposerTime(snapped ? nearest : value);
        },
        toggleComposerSnapping() {
            this.composerProject.settings.snapping = this.composerProject.settings.snapping === false;
            this.composerPlayheadSnapped = false;
            this.scheduleComposerSave();
        },
        setComposerPlayheadValue(value) {
            const feedback = { snapped: false };
            this.composerPlayhead = this.snapComposerPlayhead(Number(value) || 0, feedback);
            this.composerPlayheadSnapped = feedback.snapped;
            this.syncComposerPreview();
        },
        snapComposerClipStart(value, clip, feedback = null, trackId = clip.trackId) {
            value = this.quantizeComposerTime(value);
            if (this.composerProject.settings.snapping === false) { if (feedback) feedback.snapped = false; return value; }
            const candidates = [0, this.composerPlayhead];
            this.composerProject.clips.forEach(item => { if (item.id !== clip.id && item.trackId === trackId) candidates.push(item.start, item.start + item.duration); });
            let result = value, distance = Infinity;
            for (const edge of [value, value + clip.duration]) for (const candidate of candidates) {
                const current = Math.abs(candidate - edge);
                if (current < distance) { distance = current; result = value + candidate - edge; }
            }
            const snapped = distance * this.composerScale <= 12;
            if (feedback) feedback.snapped = snapped;
            return this.quantizeComposerTime(snapped ? Math.max(0, result) : value);
        },
        snapComposerClipEdge(value, clip, feedback = null) {
            value = this.quantizeComposerTime(value);
            if (this.composerProject.settings.snapping === false) { if (feedback) feedback.snapped = false; return value; }
            const candidates = [0, this.composerPlayhead];
            this.composerProject.clips.forEach(item => { if (item.id !== clip.id && item.trackId === clip.trackId) candidates.push(item.start, item.start + item.duration); });
            const nearest = candidates.reduce((best, item) => Math.abs(item - value) < Math.abs(best - value) ? item : best, value);
            const snapped = Math.abs(nearest - value) * this.composerScale <= 12;
            if (feedback) feedback.snapped = snapped;
            return this.quantizeComposerTime(snapped ? Math.max(0, nearest) : value);
        },
        composerTrimPlan(clip, edge, desiredEdge) {
            const ordered = this.composerTrackClips(clip.trackId), index = ordered.findIndex(item => item.id === clip.id);
            const starts = new Map(), originalEnd = clip.start + clip.duration;
            desiredEdge = this.quantizeComposerTime(desiredEdge);
            const minimumDuration = this.composerFrameDuration * (this.composerTrack(clip.trackId)?.kind === 'video' ? 2 : 1);
            let start = clip.start, duration = clip.duration;
            if (edge === 'left') {
                const previous = index > 0 ? ordered[index - 1] : null;
                const minimum = previous ? previous.start + previous.duration : 0;
                start = this.quantizeComposerTime(Math.max(minimum, Math.min(originalEnd - minimumDuration, desiredEdge)));
                duration = this.quantizeComposerTime(originalEnd - start, 1);
                starts.set(clip.id, start);
            } else {
                duration = this.quantizeComposerTime(Math.max(minimumDuration, desiredEdge - clip.start), 1);
                starts.set(clip.id, clip.start);
                let cursor = clip.start + duration, previousOriginalEnd = originalEnd;
                for (const item of ordered.slice(index + 1)) {
                    const attached = Math.abs(item.start - previousOriginalEnd) <= COMPOSER_TIME_EPSILON;
                    const nextStart = attached || item.start < cursor - COMPOSER_TIME_EPSILON ? cursor : item.start;
                    starts.set(item.id, nextStart); cursor = nextStart + item.duration;
                    previousOriginalEnd = item.start + item.duration;
                }
            }
            return { start, duration, starts };
        },
        retimeComposerClip(clip, desiredSpeed) {
            const speed = Math.max(.25, Math.min(4, Number(desiredSpeed) || 1));
            const oldSpeed = Math.max(.25, Number(clip.speed) || 1), sourceSpan = clip.duration * oldSpeed;
            const desiredDuration = this.quantizeComposerTime(sourceSpan / speed, this.composerTrack(clip.trackId)?.kind === 'video' ? 2 : 1);
            clip.speed = speed;
            const plan = this.composerTrimPlan(clip, 'right', clip.start + desiredDuration); clip.duration = plan.duration;
            for (const [id, start] of plan.starts) { const item = this.composerProject.clips.find(candidate => candidate.id === id); if (item) item.start = start; }
            clip.fadeIn = Math.min(Number(clip.fadeIn) || 0, clip.duration);
            clip.fadeOut = Math.min(Number(clip.fadeOut) || 0, Math.max(0, clip.duration - clip.fadeIn));
        },
        beginComposerDrag(event, clip) {
            if (event.button !== 0 || this.composerTrack(clip.trackId)?.locked) return;
            event.preventDefault();
            const preserveSelection = this.isComposerClipSelected(clip) && this.composerSelectedClipIds.length > 1 && !event.shiftKey && !event.metaKey && !event.ctrlKey;
            if (!preserveSelection) this.selectComposerClip(clip, event, false);
            this.composerPushHistory();
            const element = event.currentTarget, originRow = element.closest('.vs-composer-track-row');
            const originX = event.clientX, originTrackId = clip.trackId, originTrack = this.composerTrack(originTrackId);
            const originY = event.clientY;
            const moving = this.composerDragUnit(clip);
            const origin = Math.min(...moving.map(item => item.start));
            const feedback = { snapped: false };
            let nextStart = origin, nextTrackId = originTrackId, highlightedRow = null;
            let moved = false;
            let plan = this.composerMovePlan(clip, origin, originTrackId, moving);
            const clearTrackHighlight = () => {
                if (highlightedRow) highlightedRow.classList.remove('clip-drop-target');
                highlightedRow = null;
            };
            const clipElement = id => document.querySelector(`.vs-composer-clip[data-clip-id="${CSS.escape(id)}"]`);
            try { element.setPointerCapture(event.pointerId); } catch (_) {}
            moving.forEach(item => clipElement(item.id)?.classList.add('dragging'));
            const move = current => {
                current.preventDefault();
                if (Math.hypot(current.clientX - originX, current.clientY - originY) > 3) moved = true;
                const rows = Array.from(document.querySelectorAll('.vs-composer-track-row'));
                const pointerRow = rows.find(row => {
                    const bounds = row.getBoundingClientRect();
                    return current.clientY >= bounds.top && current.clientY <= bounds.bottom;
                });
                const candidate = pointerRow ? this.composerTrack(pointerRow.dataset.trackId) : null;
                const targetRow = candidate && !candidate.locked && candidate.kind === originTrack?.kind ? pointerRow : originRow;
                nextTrackId = targetRow?.dataset.trackId || originTrackId;
                nextStart = this.quantizeComposerTime(Math.max(0, this.snapComposerBlockStart(origin + (current.clientX - originX) / this.composerScale, moving, nextTrackId, feedback)));
                plan = this.composerMovePlan(clip, nextStart, nextTrackId, moving);
                const verticalOffset = targetRow && originRow ? targetRow.getBoundingClientRect().top - originRow.getBoundingClientRect().top : 0;
                for (const [id, start] of plan.starts) {
                    const node = clipElement(id); if (!node) continue;
                    node.style.left = `${start * this.composerScale}px`;
                    if (plan.movingIds.has(id)) node.style.transform = `translateY(${verticalOffset}px)`;
                }
                moving.forEach(item => clipElement(item.id)?.classList.toggle('snapped', feedback.snapped));
                if (highlightedRow !== targetRow) { clearTrackHighlight(); highlightedRow = targetRow; highlightedRow?.classList.add('clip-drop-target'); }
            };
            const finish = () => {
                window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', finish); window.removeEventListener('pointercancel', finish);
                for (const [id, start] of plan.starts) {
                    const target = this.composerProject.clips.find(item => item.id === id); if (target) target.start = start;
                }
                this.composerProject.clips.forEach(target => { if (plan.movingIds.has(target.id)) target.trackId = nextTrackId; });
                clearTrackHighlight();
                this.composerProject.clips.forEach(item => { const node = clipElement(item.id); if (node) { node.classList.remove('snapped', 'dragging'); node.style.transform = ''; } });
                try { if (element.hasPointerCapture(event.pointerId)) element.releasePointerCapture(event.pointerId); } catch (_) {}
                this.composerChanged();
                if (!moved) this.syncComposerPlayheadToClip(this.composerProject.clips.find(item => item.id === clip.id));
            };
            window.addEventListener('pointermove', move); window.addEventListener('pointerup', finish, { once: true }); window.addEventListener('pointercancel', finish, { once: true });
        },
        beginComposerTrim(event, clip, edge) {
            event.stopPropagation(); event.preventDefault(); if (this.composerTrack(clip.trackId)?.locked) return;
            this.selectComposerClip(clip, null, false); this.composerPushHistory();
            const handle = event.currentTarget, element = handle.closest('.vs-composer-clip');
            const originX = event.clientX, start = clip.start, duration = clip.duration, sourceStart = clip.sourceStart;
            const feedback = { snapped: false };
            let nextStart = start, nextDuration = duration, nextSourceStart = sourceStart;
            let trimPlan = this.composerTrimPlan(clip, edge, edge === 'right' ? start + duration : start);
            const clipElement = id => document.querySelector(`.vs-composer-clip[data-clip-id="${CSS.escape(id)}"]`);
            try { handle.setPointerCapture(event.pointerId); } catch (_) {}
            const move = current => {
                current.preventDefault();
                const delta = (current.clientX - originX) / this.composerScale;
                if (edge === 'right') {
                    const nextEnd = this.snapComposerClipEdge(start + Math.max(this.composerFrameDuration, duration + delta), clip, feedback);
                    trimPlan = this.composerTrimPlan(clip, edge, nextEnd);
                    nextDuration = trimPlan.duration;
                }
                else {
                    const rawStart = start + Math.max(-start, Math.min(duration - this.composerFrameDuration, delta));
                    const snappedStart = this.snapComposerClipEdge(rawStart, clip, feedback);
                    trimPlan = this.composerTrimPlan(clip, edge, snappedStart);
                    nextStart = trimPlan.start; nextDuration = trimPlan.duration;
                    const applied = nextStart - start;
                    nextSourceStart = Math.max(0, sourceStart + applied * clip.speed);
                    element.style.left = `${nextStart * this.composerScale}px`;
                }
                element.style.width = `${Math.max(18, nextDuration * this.composerScale)}px`;
                for (const [id, next] of trimPlan.starts) { if (id !== clip.id) { const node = clipElement(id); if (node) node.style.left = `${next * this.composerScale}px`; } }
                element.classList.toggle('snapped', feedback.snapped);
            };
            const finish = () => {
                window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', finish); window.removeEventListener('pointercancel', finish);
                const target = this.composerProject.clips.find(item => item.id === clip.id);
                if (target) {
                    if (edge === 'left' && nextStart > start) {
                        const keyframes = this.splitComposerKeyframes(target, this.composerFrameNumber(nextStart - start));
                        target.keyframes = keyframes.right; Object.assign(target, keyframes.state); this.composerSelectedKeyframeId = '';
                    }
                    target.start = nextStart; target.duration = nextDuration; target.sourceStart = nextSourceStart;
                    target.fadeIn = Math.min(target.fadeIn, target.duration);
                    target.fadeOut = Math.min(target.fadeOut, target.duration - target.fadeIn);
                }
                for (const [id, next] of trimPlan.starts) { const affected = this.composerProject.clips.find(item => item.id === id); if (affected) affected.start = next; }
                element.classList.remove('snapped');
                try { if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId); } catch (_) {}
                this.composerChanged();
            };
            window.addEventListener('pointermove', move); window.addEventListener('pointerup', finish, { once: true }); window.addEventListener('pointercancel', finish, { once: true });
        },
        beginComposerStageDrag(event, clip) {
            if (event.button !== 0 || this.composerTrack(clip.trackId)?.locked) return;
            event.preventDefault();
            const layer = event.currentTarget, stage = layer.closest('.vs-composer-stage'), bounds = stage.getBoundingClientRect();
            this.selectComposerClip(clip, event, false); this.syncComposerKeyframeSelection(); this.composerPushHistory();
            try { layer.setPointerCapture(event.pointerId); } catch (_) {}
            const settings = this.composerProject.settings, canvasWidth = settings.width, canvasHeight = settings.height;
            const activeKeyframe = this.composerKeyframeAtPlayhead(clip), activeKeyframeId = activeKeyframe?.id || '';
            const visual = this.composerVisualStateAt(clip), originX = event.clientX, originY = event.clientY, x = visual.x, y = visual.y;
            const width = visual.width || canvasWidth, height = visual.height || canvasHeight;
            let nextX = x, nextY = y;
            const move = current => {
                current.preventDefault();
                nextX = Math.round(Math.max(16 - width, Math.min(canvasWidth - 16, x + (current.clientX - originX) / bounds.width * canvasWidth)));
                nextY = Math.round(Math.max(16 - height, Math.min(canvasHeight - 16, y + (current.clientY - originY) / bounds.height * canvasHeight)));
                // Keep the active pointer target stable. Updating the reactive
                // Clip here would rebuild the x-for layer and cancel the drag.
                layer.style.left = `${nextX / canvasWidth * 100}%`;
                layer.style.top = `${nextY / canvasHeight * 100}%`;
            };
            const finish = () => {
                window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', finish); window.removeEventListener('pointercancel', finish);
                const targetClip = this.composerProject.clips.find(item => item.id === clip.id);
                if (targetClip) {
                    const keyframe = activeKeyframeId ? targetClip.keyframes?.find(item => item.id === activeKeyframeId) : null;
                    if (keyframe) { keyframe.x = nextX; keyframe.y = nextY; }
                    else this.translateComposerClipVisual(targetClip, nextX - x, nextY - y);
                }
                try { if (layer.hasPointerCapture(event.pointerId)) layer.releasePointerCapture(event.pointerId); } catch (_) {}
                this.composerChanged();
            };
            window.addEventListener('pointermove', move); window.addEventListener('pointerup', finish, { once: true }); window.addEventListener('pointercancel', finish, { once: true });
        },
        beginComposerStageResize(event, clip) {
            if (event.button !== 0 || this.composerTrack(clip.trackId)?.locked) return;
            event.preventDefault();
            const layer = event.currentTarget.closest('.vs-composer-layer'), stage = layer.closest('.vs-composer-stage'), bounds = stage.getBoundingClientRect();
            this.selectComposerClip(clip, event, false); this.syncComposerKeyframeSelection(); this.composerPushHistory();
            try { layer.setPointerCapture(event.pointerId); } catch (_) {}
            const settings = this.composerProject.settings, canvasWidth = settings.width, canvasHeight = settings.height;
            const activeKeyframe = this.composerKeyframeAtPlayhead(clip), activeKeyframeId = activeKeyframe?.id || '';
            const visual = this.composerVisualStateAt(clip), originX = event.clientX, originY = event.clientY, width = visual.width || canvasWidth, height = visual.height || canvasHeight;
            let nextWidth = width, nextHeight = height;
            const move = current => {
                current.preventDefault();
                nextWidth = Math.round(Math.max(16, Math.min(canvasWidth - visual.x, width + (current.clientX - originX) / bounds.width * canvasWidth)));
                nextHeight = Math.round(Math.max(16, Math.min(canvasHeight - visual.y, height + (current.clientY - originY) / bounds.height * canvasHeight)));
                layer.style.width = `${nextWidth / canvasWidth * 100}%`;
                layer.style.height = `${nextHeight / canvasHeight * 100}%`;
            };
            const finish = () => {
                window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', finish); window.removeEventListener('pointercancel', finish);
                const targetClip = this.composerProject.clips.find(item => item.id === clip.id);
                if (targetClip) {
                    const keyframe = activeKeyframeId ? targetClip.keyframes?.find(item => item.id === activeKeyframeId) : null;
                    if (keyframe) { keyframe.width = nextWidth; keyframe.height = nextHeight; }
                    else this.resizeComposerClipVisual(targetClip, nextWidth, nextHeight, width, height);
                }
                try { if (layer.hasPointerCapture(event.pointerId)) layer.releasePointerCapture(event.pointerId); } catch (_) {}
                this.composerChanged();
            };
            window.addEventListener('pointermove', move); window.addEventListener('pointerup', finish, { once: true }); window.addEventListener('pointercancel', finish, { once: true });
        },
        setComposerPlayhead(event) {
            const bounds = event.currentTarget.getBoundingClientRect();
            this.setComposerPlayheadValue((event.clientX - bounds.left + event.currentTarget.scrollLeft) / this.composerScale);
        },
        beginComposerScrub(event) {
            if (event.button !== 0) return;
            event.preventDefault();
            const ruler = event.currentTarget, bounds = ruler.getBoundingClientRect();
            const update = current => {
                current.preventDefault();
                this.setComposerPlayheadValue((current.clientX - bounds.left) / this.composerScale);
            };
            const finish = () => {
                window.removeEventListener('pointermove', update); window.removeEventListener('pointerup', finish); window.removeEventListener('pointercancel', finish);
                try { if (ruler.hasPointerCapture(event.pointerId)) ruler.releasePointerCapture(event.pointerId); } catch (_) {}
            };
            try { ruler.setPointerCapture(event.pointerId); } catch (_) {}
            update(event); window.addEventListener('pointermove', update); window.addEventListener('pointerup', finish, { once: true }); window.addEventListener('pointercancel', finish, { once: true });
        },
        syncComposerPreview() {
            this.syncComposerKeyframeSelection();
            this.$nextTick(() => {
                document.querySelectorAll('.vs-composer-stage video,.vs-composer-stage audio').forEach(media => {
                    const clip = this.composerProject.clips.find(item => item.id === media.dataset.clipId); if (!clip) return;
                    const target = clip.sourceStart + Math.max(0, this.composerPlayhead - clip.start) * clip.speed;
                    const elapsed = Math.max(0, this.composerPlayhead - clip.start), remaining = Math.max(0, clip.duration - elapsed);
                    const fade = Math.min(clip.fadeIn ? elapsed / clip.fadeIn : 1, clip.fadeOut ? remaining / clip.fadeOut : 1, 1);
                    media.playbackRate = clip.speed; media.volume = Math.min(1, clip.volume * Math.max(0, fade));
                    if (Math.abs((media.currentTime || 0) - target) > .2) media.currentTime = target;
                    if (this.composerPlaying) media.play().catch(() => {}); else media.pause();
                });
            });
        },
        toggleComposerPreview() {
            this.composerPlaying = !this.composerPlaying;
            if (!this.composerPlaying) { if (this.composerRaf) cancelAnimationFrame(this.composerRaf); this.composerRaf = 0; this.syncComposerPreview(); return; }
            if (this.composerPlayhead >= this.composerDuration) this.composerPlayhead = 0;
            const startedAt = performance.now(), startedPlayhead = this.composerPlayhead;
            const tick = now => {
                if (!this.composerPlaying) return;
                this.composerPlayhead = this.quantizeComposerTime(startedPlayhead + (now - startedAt) / 1000);
                if (this.composerPlayhead >= this.composerDuration) { this.composerPlayhead = this.composerDuration; this.composerPlaying = false; }
                this.syncComposerPreview();
                if (this.composerPlaying) this.composerRaf = requestAnimationFrame(tick);
            };
            this.syncComposerPreview(); this.composerRaf = requestAnimationFrame(tick);
        },
        handleComposerKeydown(event) {
            if (!this.isComposer || event.defaultPrevented) return;
            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') { event.preventDefault(); event.shiftKey ? this.$refs.composerSaveAs?.click() : this.saveComposerDocument(); return; }
            if (/^(INPUT|TEXTAREA|SELECT)$/.test(event.target?.tagName || '')) return;
            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'n') { event.preventDefault(); this.toggleComposerSnapping(); return; }
            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); event.shiftKey ? this.composerRedo() : this.composerUndo(); return; }
            if (event.key === ' ') { event.preventDefault(); this.toggleComposerPreview(); return; }
            if (event.key === 'Delete' || event.key === 'Backspace') { event.preventDefault(); this.composerSelectedKeyframe ? this.deleteComposerKeyframe() : this.deleteComposerClip(); return; }
            if (event.key.toLowerCase() === 's') { event.preventDefault(); this.splitComposerClip(); }
        },
        async renderComposer() {
            if (!this.composerProject.clips.length || this.composerRendering) return;
            this.composerRendering = true;
            try {
                await this.saveComposerProject();
                const title = `${this.composerProject.title.replace(/\.[^.]+$/, '')}.mp4`;
                const run = await responsePayload(await fetch(`${STUDIO_API}/runs`, {
                    method: 'POST', credentials: 'same-origin', headers: { ...this.draftHeaders(), 'Content-Type': 'application/json' },
                    body: JSON.stringify({ miniAppId: 'ai2apps.video.composer', title, input: { projectTitle: this.composerProject.title, trackCount: this.composerProject.tracks.length, clipCount: this.composerProject.clips.length } }),
                }));
                const started = await responsePayload(await fetch(`${STUDIO_API}/runs/${encodeURIComponent(run.id)}/compose`, {
                    method: 'POST', credentials: 'same-origin', headers: { ...this.draftHeaders(), 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project: this.composerProject, outputName: title }),
                }));
                this.composerRuns = [started, ...this.composerRuns.filter(item => item.id !== started.id)]; this.selectedComposerRunId = started.id; this.rightCollapsed = false;
                this.persistShellState(); this.composerGalleryAdded = false;
                this.success('Composition rendering started');
            } catch (error) { this.fail(error); } finally { this.composerRendering = false; this.icons(); }
        },
        async cancelComposer(run) {
            try {
                const updated = await responsePayload(await fetch(`${STUDIO_API}/runs/${encodeURIComponent(run.id)}/cancel`, { method: 'POST', credentials: 'same-origin', headers: this.draftHeaders() }));
                const index = this.composerRuns.findIndex(item => item.id === updated.id); if (index >= 0) this.composerRuns.splice(index, 1, updated);
            } catch (error) { this.fail(error); } finally { this.icons(); }
        },
        selectComposerRun(run) { this.selectedComposerRunId = run.id; this.composerGalleryAdded = false; this.persistShellState(); },
        async addActiveComposerToGallery() {
            const artifact = this.activeComposerArtifact;
            if (!artifact?.downloadUrl || this.addingComposerToGallery) return;
            this.addingComposerToGallery = true; this.composerGalleryAdded = false;
            try {
                const reference = this.artifactReference(artifact.downloadUrl);
                await responsePayload(await fetch(`/v1/platform/gallery/assets/import-artifact/${encodeURIComponent(reference.sessionId)}/${encodeURIComponent(reference.artifactId)}`, {
                    method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
                    body: JSON.stringify({ collectionId: this.galleryActiveCollectionId === 'recent' ? null : this.galleryActiveCollectionId, name: artifact.name, sourceAppId: APP_ID }),
                }));
                this.composerGalleryAdded = true;
                this.$refs.galleryMini?.contentWindow?.postMessage({ type: 'ai2apps.gallery.refresh' }, window.location.origin);
            } catch (error) { this.fail(error); } finally { this.addingComposerToGallery = false; this.icons(); }
        },
        async loadComposerChatModels() {
            if (this.composerChatModels.length) return;
            try {
                const payload = await responsePayload(await fetch('/v1/models', { credentials: 'same-origin', cache: 'no-store' }));
                this.composerChatModels = (payload.data || []).filter(conversationModel);
                const saved = localStorage.getItem('ai2apps-video-composer-chat-model');
                this.composerChatModelId = this.composerChatModels.some(model => model.id === saved) ? saved : (this.composerChatModels[0]?.id || '');
            } catch (_) { this.composerChatModels = []; }
        },
        async requestComposerChatPlan(text) {
            if (!this.composerChatModelId) return null;
            localStorage.setItem('ai2apps-video-composer-chat-model', this.composerChatModelId);
            const context = {
                canvas: this.composerProject.settings,
                playhead: this.composerPlayhead,
                selectedClipId: this.composerSelectedClipId,
                tracks: this.composerProject.tracks.map(({ id, kind, name, order }) => ({ id, kind, name, order })),
                clips: this.composerProject.clips.map(({ id, name, trackId, start, duration, speed, volume, fadeIn, fadeOut, x, y, width, height, opacity, groupId, color }) => ({ id, name, trackId, start, duration, speed, volume, fadeIn, fadeOut, x, y, width, height, opacity, groupId, color })),
            };
            const response = await responsePayload(await fetch('/v1/chat/completions', {
                method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model: this.composerChatModelId, stream: false, messages: [
                    { role: 'system', content: 'Plan safe edits for an AI2Apps video timeline. Return JSON only: {"operations":[...]}. Allowed operations: clip.update with clipId and changes using only trackId,start,duration,speed,volume,fadeIn,fadeOut,x,y,width,height,opacity,audioEnabled,color; clip.split with clipId and at; clip.delete with clipId; track.add with kind and optional name. fadeIn and fadeOut affect audio only; use opacity keyframes for visual fades. Use seconds and canvas pixels. Colors must be six-digit hex. Never invent IDs. Maximum 20 operations.' },
                    { role: 'user', content: `Timeline context:\n${JSON.stringify(context)}\n\nUser request:\n${text}` },
                ] }),
            }));
            const content = String(response.choices?.[0]?.message?.content || '').replace(/^```(?:json)?\s*|\s*```$/g, '');
            const planned = JSON.parse(content);
            return Array.isArray(planned.operations) ? planned.operations : null;
        },
        fallbackComposerOperations(text) {
            const clip = this.composerSelectedClip; if (!clip) return [];
            if (/分割|切开|split/i.test(text)) return [{ op: 'clip.split', clipId: clip.id, at: this.composerPlayhead }];
            if (/删除|移除|delete|remove/i.test(text)) return [{ op: 'clip.delete', clipId: clip.id }];
            const changes = {};
            const speed = text.match(/(?:速度|速率|speed)[^0-9]*(0\.25|0\.5|1(?:\.\d+)?|2|3|4)/i);
            const volume = text.match(/(?:音量|volume)[^0-9]*(\d+(?:\.\d+)?)\s*%?/i);
            const fade = text.match(/(?:淡入淡出|淡入|fade)[^0-9]*(\d+(?:\.\d+)?)\s*(?:秒|s)?/i);
            if (speed) changes.speed = Number(speed[1]);
            if (volume) changes.volume = Number(volume[1]) / (text.includes('%') ? 100 : 1);
            if (fade) changes.fadeIn = changes.fadeOut = Number(fade[1]);
            if (/左下|bottom.?left/i.test(text)) { changes.x = 24; changes.y = Math.max(0, this.composerProject.settings.height - (clip.height || 180) - 24); }
            if (/右下|bottom.?right/i.test(text)) { changes.x = Math.max(0, this.composerProject.settings.width - (clip.width || 320) - 24); changes.y = Math.max(0, this.composerProject.settings.height - (clip.height || 180) - 24); }
            if (/缩小|画中画|picture.?in.?picture/i.test(text)) { changes.width = Math.round(this.composerProject.settings.width * .28); changes.height = Math.round(this.composerProject.settings.height * .28); }
            return Object.keys(changes).length ? [{ op: 'clip.update', clipId: clip.id, changes }] : [];
        },
        applyComposerOperations(operations) {
            if (!Array.isArray(operations) || !operations.length || operations.length > 20) throw new Error('The edit plan is empty or too large.');
            const allowed = new Set(['trackId', 'start', 'duration', 'speed', 'volume', 'fadeIn', 'fadeOut', 'x', 'y', 'width', 'height', 'opacity', 'audioEnabled', 'color']);
            const numberRanges = { start: [0, 3600], duration: [.1, 3600], speed: [.25, 4], volume: [0, 4], fadeIn: [0, 30], fadeOut: [0, 30], x: [-3840, 3840], y: [-2160, 2160], width: [16, 3840], height: [16, 2160], opacity: [0, 1] };
            const before = copyComposerProject(this.composerProject); this.composerPushHistory(); const summaries = [];
            try { for (const operation of operations) {
                const clip = this.composerProject.clips.find(item => item.id === operation.clipId);
                if (operation.op === 'track.add') {
                    if (!['video', 'audio'].includes(operation.kind)) throw new Error('Invalid track kind.');
                    const track = this.addComposerTrack(operation.kind, false); if (operation.name) track.name = String(operation.name).slice(0, 120); summaries.push(`add ${operation.kind} track`); continue;
                }
                if (!clip) throw new Error('The edit plan referenced an unknown clip.');
                if (operation.op === 'clip.delete') { this.composerProject.clips = this.composerProject.clips.filter(item => item.id !== clip.id); summaries.push(`delete ${clip.name}`); continue; }
                if (operation.op === 'clip.split') {
                    const at = this.quantizeComposerTime(Number(operation.at)), offset = at - clip.start;
                    if (!(offset >= this.composerFrameDuration && offset <= clip.duration - this.composerFrameDuration)) throw new Error('Split point must be inside the clip.');
                    const keyframes = this.splitComposerKeyframes(clip, this.composerFrameNumber(offset));
                    const right = { ...clip, id: composerId('clip'), start: at, sourceStart: clip.sourceStart + offset * clip.speed, duration: this.quantizeComposerTime(clip.duration - offset, 1), fadeIn: 0, keyframes: keyframes.right, ...keyframes.state };
                    clip.duration = offset; clip.fadeOut = 0; clip.keyframes = keyframes.left; this.composerSelectedKeyframeId = '';
                    this.composerProject.clips.push(right); this.setComposerSelection(this.composerClipSelectionUnit(right), right.id); summaries.push(`split ${clip.name}`); continue;
                }
                if (operation.op !== 'clip.update' || !operation.changes || typeof operation.changes !== 'object') throw new Error('Unsupported edit operation.');
                if (Object.prototype.hasOwnProperty.call(operation.changes, 'speed')) {
                    const speed = Number(operation.changes.speed), range = numberRanges.speed;
                    if (!Number.isFinite(speed) || speed < range[0] || speed > range[1]) throw new Error('Invalid value for speed.');
                    this.retimeComposerClip(clip, speed);
                }
                for (const [key, raw] of Object.entries(operation.changes)) {
                    if (!allowed.has(key)) throw new Error(`Unsupported clip field: ${key}`);
                    if (key === 'speed') continue;
                    if (key === 'trackId') { const target = this.composerTrack(String(raw)); if (!this.composerTrackAcceptsClip(target, clip)) throw new Error('The target track is incompatible or locked.'); clip.trackId = String(raw); continue; }
                    if (key === 'audioEnabled') { clip.audioEnabled = Boolean(raw); continue; }
                    if (key === 'color') { if (!/^#[0-9a-fA-F]{6}$/.test(String(raw))) throw new Error('Invalid clip color.'); clip.color = String(raw); continue; }
                    const range = numberRanges[key], value = Number(raw);
                    if (!range || !Number.isFinite(value) || value < range[0] || value > range[1]) throw new Error(`Invalid value for ${key}.`);
                    clip[key] = value;
                }
                if (clip.fadeIn + clip.fadeOut > clip.duration) throw new Error('Clip fades exceed its duration.');
                summaries.push(`update ${clip.name}`);
            } this.normalizeComposerTimeline(); } catch (error) { this.composerProject = before; this.composerHistory.pop(); throw error; }
            this.composerChanged(); return summaries;
        },
        async applyComposerChat() {
            const text = this.composerChatText.trim();
            if (!text || this.composerChatBusy) return; this.composerChatBusy = true;
            try {
                let operations = null;
                if (this.composerChatModelId) {
                    try { operations = await this.requestComposerChatPlan(text); }
                    catch (_) { operations = null; }
                }
                operations = operations?.length ? operations : this.fallbackComposerOperations(text);
                if (!operations.length) throw new Error('Select a clip and describe a supported edit, or choose a Chat model for broader instructions.');
                const summaries = this.applyComposerOperations(operations);
                this.composerChatLog.push({ text, result: summaries.join(' · ') }); this.composerChatText = '';
            } catch (error) { this.fail(error); } finally { this.composerChatBusy = false; this.icons(); }
        },

        async extractAudio(retryOf = null) {
            if (!(this.extractAsset?.id || this.extractAsset?.nativePath) || this.extractSubmitting) return;
            this.extractSubmitting = true; this.notice = '';
            try {
                await this.saveExtractorDraft();
                const instanceId = window.AI2AppsCapabilities?.appInstanceId?.() || '';
                if (!instanceId) throw new Error(tr('video_studio.error.app_instance_missing'));
                const isLocal = this.extractAsset.sourceKind === 'local' && Boolean(this.extractAsset.nativePath);
                const reference = isLocal ? null : await responsePayload(await fetch(
                    `/v1/platform/gallery/assets/${encodeURIComponent(this.extractAsset.id)}/resource-handles`,
                    { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify({ consumerAppId: APP_ID, appInstanceId: instanceId }) },
                ));
                const title = this.extractOutputName || String(this.extractAsset.name).replace(/\.[^.]+$/, '') + '.wav';
                const runInput = isLocal
                    ? { sourceKind: 'local', assetName: this.extractAsset.name, mediaType: this.extractAsset.mediaType }
                    : { sourceKind: 'gallery', assetId: this.extractAsset.id, assetName: this.extractAsset.name, mediaType: this.extractAsset.mediaType };
                const run = await responsePayload(await fetch(STUDIO_API + '/runs', {
                    method: 'POST', credentials: 'same-origin', headers: { ...this.draftHeaders(), 'Content-Type': 'application/json' },
                    body: JSON.stringify({ miniAppId: 'ai2apps.video.extract-audio', title, input: runInput, retryOf }),
                }));
                const started = await responsePayload(await fetch(`${STUDIO_API}/runs/${encodeURIComponent(run.id)}/extract-audio`, {
                    method: 'POST', credentials: 'same-origin', headers: { ...this.draftHeaders(), 'Content-Type': 'application/json' },
                    body: JSON.stringify(isLocal
                        ? { sourcePath: this.extractAsset.nativePath, sourceName: this.extractAsset.name, mediaType: this.extractAsset.mediaType, outputName: title }
                        : { resourceHandle: reference.resourceHandle, outputName: title }),
                }));
                if (isLocal) this.localAudioSources[started.id] = { ...this.extractAsset };
                this.audioRuns = [started, ...this.audioRuns.filter(item => item.id !== started.id)];
                this.selectedAudioRunId = started.id;
                this.rightCollapsed = false;
                this.persistShellState();
                this.success(tr('video_studio.success.extract_started'));
            } catch (error) { this.fail(error); } finally { this.extractSubmitting = false; this.icons(); }
        },
        async retryAudio(run) {
            const input = run?.input || {};
            if (input.sourceKind === 'local') {
                const source = this.localAudioSources[run.id];
                if (!source?.nativePath) {
                    this.fail(new Error(tr('video_studio.error.extract_video_only')));
                    return;
                }
                this.extractAsset = { ...source };
                this.extractOutputName = run.title || '';
                await this.extractAudio(run.id);
                return;
            }
            if (!input.assetId) return;
            this.extractAsset = { id: input.assetId, name: input.assetName || 'Video', kind: 'video', sourceKind: 'gallery', mediaType: input.mediaType || 'video/mp4' };
            this.extractOutputName = run.title || '';
            await this.extractAudio(run.id);
        },
        async cancelAudio(run) {
            try {
                const updated = await responsePayload(await fetch(`${STUDIO_API}/runs/${encodeURIComponent(run.id)}/cancel`, { method: 'POST', credentials: 'same-origin', headers: this.draftHeaders() }));
                const index = this.audioRuns.findIndex(item => item.id === updated.id);
                if (index >= 0) this.audioRuns.splice(index, 1, updated);
            } catch (error) { this.fail(error); } finally { this.icons(); }
        },
        selectAudioRun(run) { this.selectedAudioRunId = run.id; this.audioGalleryAdded = false; this.persistShellState(); },
        async addActiveAudioToGallery() {
            const artifact = this.activeAudioArtifact;
            if (!artifact?.downloadUrl || this.addingAudioToGallery) return;
            this.addingAudioToGallery = true; this.audioGalleryAdded = false;
            try {
                const parsed = new URL(artifact.downloadUrl, window.location.origin);
                const match = parsed.pathname.match(/^\/v1\/platform\/sessions\/([^/]+)\/artifacts\/([^/]+)\/download$/);
                if (!match) throw new Error(tr('video_studio.error.artifact_invalid'));
                await responsePayload(await fetch(`/v1/platform/gallery/assets/import-artifact/${encodeURIComponent(decodeURIComponent(match[1]))}/${encodeURIComponent(decodeURIComponent(match[2]))}`, {
                    method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
                    body: JSON.stringify({ collectionId: this.galleryActiveCollectionId === 'recent' ? null : this.galleryActiveCollectionId, name: artifact.name, sourceAppId: APP_ID }),
                }));
                this.audioGalleryAdded = true;
                this.$refs.galleryMini?.contentWindow?.postMessage({ type: 'ai2apps.gallery.refresh' }, window.location.origin);
            } catch (error) { this.fail(error); } finally { this.addingAudioToGallery = false; this.icons(); }
        },

        provisioningDraft(action) {
            return {
                action, mode: this.mode, modelId: this.modelId, prompt: this.prompt, resolution: this.resolution,
                duration: this.duration, preset: this.preset, steps: this.steps,
                seed: this.seed, label: this.label, batchText: this.batchText,
            };
        },
        applyProvisioningDraft(value) {
            if (!value) return null;
            this.saveCurrentMiniAppDraft();
            for (const key of ['mode', 'modelId', 'prompt', 'resolution', 'duration', 'preset', 'steps', 'seed', 'label', 'batchText']) {
                if (value[key] !== undefined) this[key] = value[key];
            }
            this.saveCurrentMiniAppDraft();
            this.persistShellState();
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
        async finishProvisioning(result, resumeToken, { preserveModelId = '' } = {}) {
            await this.loadProvisioningDraft(resumeToken);
            const retainedModelId = preserveModelId
                || (result.session?.actionId === 'install-more-video-models' ? this.modelId : '');
            await this.refresh();
            const resumedModelId = result.provider?.modelId;
            const readyModelId = this.modeProviders.some(item => item.id === retainedModelId && item.ready)
                ? retainedModelId
                : this.modeProviders.some(item => item.id === resumedModelId && item.ready)
                ? resumedModelId
                : (this.selectedProvider?.ready ? this.modelId : this.modeProviders.find(item => item.ready)?.id);
            if (readyModelId) this.modelId = readyModelId;
            this.syncDefaults(false);
            if (!this.selectedProvider?.ready) throw new Error(tr('video_studio.error.provider_missing'));
            this.persistShellState();
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
        async installMoreVideoModels() {
            if (this.modelInstallBusy || this.isLocalVideoTool || this.packageMiniAppId) return;
            const originalModelId = this.modelId;
            this.modelInstallBusy = true;
            let stored = null;
            try {
                stored = await this.persistProvisioningDraft('install-more-video-models');
                const result = await window.AI2AppsCapabilities.ensure(
                    this.capabilityRequest('install-more-video-models', '', stored.resumeToken),
                    { installMore: true },
                );
                await this.finishProvisioning(result, stored.resumeToken, { preserveModelId: originalModelId });
                this.success(tr('video_studio.success.models_refreshed'));
            } catch (error) {
                this.modelId = originalModelId;
                if (stored?.resumeToken) await this.deleteProvisioningDraft(stored.resumeToken).catch(() => {});
                this.fail(error);
            } finally {
                this.modelInstallBusy = false;
                this.syncModelSelectValue();
                this.icons();
            }
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
                    pipeline_id: this.miniAppForMode(overrides.mode || this.mode).id,
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
                this.tasks.unshift(task); this.selectedTaskId = task.id; this.saveCurrentMiniAppDraft(); this.persistShellState(); this.success(tr('video_studio.success.queued'));
            } catch (error) { this.fail(error); } finally { this.submitting = false; this.icons(); }
        },
        async cancel(task) {
            try {
                const updated = await responsePayload(await fetch(TASKS_API + '/' + encodeURIComponent(task.id), { method: 'DELETE', credentials: 'same-origin', headers: { Accept: 'application/json' } }));
                Object.assign(task, updated); this.success(tr('video_studio.success.cancelled'));
            } catch (error) { this.fail(error); }
        },
        selectTask(task) {
            this.joinedVideoUrl = ''; this.selectedTaskId = task.id;
            if (window.matchMedia('(max-width: 1000px)').matches) this.rightCollapsed = false;
            this.persistShellState();
        },
        canRetry(task) { return ['failed', 'cancelled', 'expired'].includes(task?.status); },
        async retry(task) {
            if (!this.canRetry(task) || this.retryingTaskId) return;
            this.retryingTaskId = task.id;
            try {
                const retried = await responsePayload(await fetch(
                    `${STUDIO_API}/tasks/${encodeURIComponent(task.id)}/retry`,
                    { method: 'POST', credentials: 'same-origin', headers: this.draftHeaders() },
                ));
                this.tasks.unshift(retried); this.selectedTaskId = retried.id;
                this.persistShellState(); this.success(tr('video_studio.success.retried'));
            } catch (error) { this.fail(error); } finally { this.retryingTaskId = ''; this.icons(); }
        },
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
        isTerminalStatus(status) { return terminal.has(status); },
        taskTitle(task) { return task.metadata?.label || task.metadata?.prompt?.slice(0, 36) || tr('video_studio.untitled'); },
        statusIcon(status) { return ({ queued: 'clock-3', running: 'loader-circle', succeeded: 'check', failed: 'triangle-alert', cancelled: 'ban' }[status] || 'circle'); },
        statusLabel(status) { return ['queued', 'running', 'succeeded', 'failed', 'cancelled', 'expired'].includes(status) ? tr(`video_studio.status.${status}`) : status; },
        phaseLabel(phase) { return ['queued', 'loading', 'encoding', 'denoising', 'decoding', 'audio', 'muxing', 'completed'].includes(phase) ? tr(`video_studio.phase.${phase}`) : phase || tr('video_studio.phase.waiting'); },
        stepStatusLabel(task) { return tr(`video_studio.step.${terminal.has(task?.status) ? task.status : (task?.status || 'queued')}`); },
        revisionLabel(value) { return value ? String(value).slice(0, 12) : tr('video_studio.not_available'); },
        timeLabel(value) { if (!value) return ''; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : date.toLocaleString([], { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }); },
    }; };
})();
