(function () {
    'use strict';
    const STUDIO_API = '/v1/platform/video-studio';
    const PROVIDERS_API = STUDIO_API + '/providers';
    const DRAFTS_API = STUDIO_API + '/drafts';
    const TASKS_API = '/v1/videos/generations';
    const APP_ID = 'ai2apps.video-studio';
    const INSTALL_MORE_MODEL_ID = '__install_more__';
    const UPSCALING_INSTALL_MODEL_ID = '__install_upscaling_model__';
    const terminal = new Set(['succeeded', 'failed', 'cancelled', 'expired']);
    const SHELL_STATE_KEY = 'ai2apps-video-studio-shell-v1';
    const GALLERY_MINI_FALLBACK_URL = '/admin/app-content/ai2apps.gallery?surface=mini';
    const MINI_APPS = Object.freeze([
        Object.freeze({ id: 'ai2apps.video.text-to-video', mode: 't2v', key: 'video_studio.mini_app.t2v', icon: 'type' }),
        Object.freeze({ id: 'ai2apps.video.image-to-video', mode: 'i2v', key: 'video_studio.mini_app.i2v', icon: 'image' }),
        Object.freeze({ id: 'ai2apps.video.reference-to-video', mode: 'r2v', key: 'video_studio.mini_app.r2v', icon: 'scan-search' }),
        Object.freeze({ id: 'ai2apps.video.composer', mode: 'composer', key: 'video_studio.mini_app.composer', icon: 'panels-top-left' }),
        Object.freeze({ id: 'ai2apps.video.extract-audio', mode: 'x2a', key: 'video_studio.mini_app.x2a', icon: 'audio-lines' }),
        Object.freeze({ id: 'ai2apps.video.upscaling', mode: 'upscale', key: 'video_studio.mini_app.upscale', icon: 'scan-search' }),
    ]);
    const COMPOSER_CLIP_COLORS = Object.freeze(['#2563eb', '#7c3aed', '#db2777', '#ea580c', '#059669', '#0891b2', '#4f46e5', '#65a30d']);
    const COMPOSER_MIN_SPEED = .25;
    const COMPOSER_MAX_SPEED = 20;
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
        notice: '', noticeTone: 'error', noticeTimer: null, providers: [], modelId: '', tasks: [], selectedTaskId: '', audioRuns: [], selectedAudioRunId: '', upscalingRuns: [], selectedUpscalingRunId: '', upscalingModels: [], upscalingModelId: '', upscalingFile: null, upscalingSeed: 0, upscalingPrompt: '', upscalingSubmitting: false, upscalingInstalling: false, packageRuns: [],
        dismissed: [], pollTimer: null, mode: 't2v', prompt: '', resolution: '512x512', duration: 5,
        preset: 'strict', steps: 20, seed: 42, label: '', firstFile: null, lastFile: null,
        firstPreview: '', lastPreview: '', referenceImages: [], referenceVideos: [], referenceAudios: [], referenceOrder: [],
        batchText: '', joinedVideoUrl: '', clientEnvironment: 'browser', leftView: 'mini-apps', leftCollapsed: false, rightCollapsed: false,
        miniAppDrafts: {}, resizeHandler: null, responsiveNarrow: false, responsiveMobile: false,
        packageMiniApps: [], packageMiniAppId: '', packageMiniAppUrl: '', packageMiniAppMountId: '', packageMiniAppLoading: false, packageMiniAppError: '', packageMiniAppReadiness: {}, packageMiniAppSetupBusy: false,
        packageOutputUrl: '', packageOutputRunId: '', packageOutputMiniAppId: '', packageOutputHandler: null,
        galleryMiniUrl: '', galleryMiniMountId: '', galleryMiniLoading: false, galleryMiniError: '', galleryDragActive: false, gallerySlotTarget: '',
        chatController: null, chatMiniUrl: '', packageChatBridge: null,
        galleryActiveCollectionId: 'recent', galleryActiveCollectionName: 'Recent', galleryMessageHandler: null, galleryAddedTimer: null,
        extractAsset: null, extractOutputName: '', extractImporting: false, extractSubmitting: false, localAudioSources: {}, addingAudioToGallery: false, audioGalleryAdded: false,
        composerProject: newComposerProject(), composerSources: [], composerDocumentPath: '', composerDocumentSaving: false, composerRuns: [], selectedComposerRunId: '', composerSelectedClipId: '', composerSelectedClipIds: [], composerSelectedKeyframeId: '', composerSelectedTrackId: '', composerTrackMenuOpen: false, composerTrackMenuStep: 'type', composerTrackInsertSide: 'after', composerItemMenuOpen: false, composerDropTrackId: '', composerScale: 42, composerPlayhead: 0, composerPlayheadSnapped: false, composerPlaying: false, composerRaf: 0, composerHistory: [], composerFuture: [], composerEditSnapshot: null, composerImporting: false, composerMaskImporting: false, composerPersonMaskBusy: false, composerMaskModels: [], composerFreezeBusy: false, composerRendering: false, composerSaveTimer: 0, composerCropWheelTimer: 0, composerCropWheelEditing: false, composerChatText: '', composerChatLog: [], composerChatBusy: false, composerChatModels: [], composerChatModelId: '', composerKeyHandler: null, composerHoverTip: { text: '', left: 0, top: 0 }, addingComposerToGallery: false, composerGalleryAdded: false,
        tr,
        get miniApps() { return [...MINI_APPS, ...this.packageMiniApps].map(localizedMiniApp); },
        get selectedProvider() { return this.providers.find(item => item.id === this.modelId) || null; },
        get currentMiniApp() { return this.packageMiniAppId ? (this.miniApps.find(item => item.id === this.packageMiniAppId) || this.miniAppForMode(this.mode)) : this.miniAppForMode(this.mode); },
        get miniAppChatEnabled() { return Boolean(window.AI2AppsMiniAppChat && this.currentMiniApp && (this.currentMiniApp.source !== 'package' || this.currentMiniApp.chat?.enabled === true)); },
        get isAudioExtractor() { return !this.packageMiniAppId && this.mode === 'x2a'; },
        get isComposer() { return !this.packageMiniAppId && this.mode === 'composer'; },
        get isUpscaler() { return !this.packageMiniAppId && this.mode === 'upscale'; },
        get isLocalVideoTool() { return this.isAudioExtractor || this.isComposer || this.isUpscaler; },
        get selectedUpscalingModel() { return this.upscalingModels.find(item => item.id === this.upscalingModelId) || null; },
        get activeUpscalingRun() { return this.upscalingRuns.find(run => run.id === this.selectedUpscalingRunId) || this.upscalingRuns[0] || null; },
        get activeUpscalingArtifact() { return this.activeUpscalingRun?.artifacts?.find(item => item.kind === 'video' && item.final) || null; },
        get currentMiniAppReady() { return this.packageMiniAppId ? this.miniAppReady(this.currentMiniApp) : (this.isUpscaler ? Boolean(this.selectedUpscalingModel?.ready) : this.isLocalVideoTool || Boolean(this.selectedProvider?.ready)); },
        get modeProviders() {
            const wantsReference = this.mode === 'r2v';
            if (this.isLocalVideoTool) return [];
            return this.providers.filter(item => Boolean(item.capabilities?.includes('reference_to_video')) === wantsReference);
        },
        get caps() { return this.selectedProvider?.videoCapabilities || {}; },
        get resolutions() { return this.caps.geometry?.resolutions || ['512x512']; },
        get presets() { return this.caps.presets?.length ? this.caps.presets : [{ id: 'strict', display_name: 'Strict' }]; },
        get durationStep() { return .5; },
        get durationMin() {
            const raw = Number(this.caps.duration?.minimum_seconds ?? 1);
            return Math.ceil((raw - Number.EPSILON) / this.durationStep) * this.durationStep;
        },
        get durationMax() {
            const raw = Number(this.caps.duration?.maximum_seconds ?? 15);
            const aligned = Math.floor((raw + Number.EPSILON) / this.durationStep) * this.durationStep;
            return Math.max(this.durationMin, aligned);
        },
        get frameNote() { const fps = Number(this.caps.defaults?.framespersecond || 24); return tr('video_studio.frame_note', { frames: Math.max(1, Math.round(this.duration * fps)), fps }); },
        get canGenerate() {
            if (this.isAudioExtractor) return Boolean(this.extractAsset?.id || this.extractAsset?.nativePath);
            if (this.isComposer) return this.composerProject.clips.length > 0;
            if (this.isUpscaler) return Boolean(this.upscalingFile && this.selectedUpscalingModel?.ready
                && !this.upscalingRuns.some(run => !terminal.has(run.status)));
            if (!this.prompt.trim()) return false;
            if (this.mode === 'i2v') return Boolean(this.firstFile);
            if (this.mode === 'r2v') return Boolean(this.referenceImages.length || this.referenceVideos.length);
            return true;
        },
        get needsConfiguration() { return !this.isLocalVideoTool && (!this.selectedProvider?.ready || !this.modeProviders.some(item => item.id === this.modelId)); },
        get canPrimaryAction() { return this.needsConfiguration || this.canGenerate; },
        get visibleTasks() { return this.tasks.filter(task => !this.dismissed.includes(task.id)); },
        get activeTask() { return this.visibleTasks.find(task => task.id === this.selectedTaskId) || this.visibleTasks.find(task => task.status === 'succeeded') || null; },
        get activePackageRun() {
            return this.packageRuns.find(run => run.id === this.packageOutputRunId && run.miniAppId === this.packageMiniAppId)
                || this.packageRuns.find(run => run.miniAppId === this.packageMiniAppId && run.status === 'succeeded')
                || null;
        },
        get activePackageArtifact() { return this.activePackageRun?.artifacts?.find(item => item.kind === 'video' && item.final) || null; },
        get activeVideoUrl() {
            if (this.isUpscaler) return this.activeUpscalingArtifact?.downloadUrl || '';
            if (this.packageMiniAppId) {
                const liveUrl = this.packageOutputMiniAppId === this.packageMiniAppId ? this.packageOutputUrl : '';
                return liveUrl || this.activePackageArtifact?.downloadUrl || '';
            }
            return this.joinedVideoUrl || this.activeTask?.result?.video?.download_url || '';
        },
        get completedTasks() { return this.visibleTasks.filter(task => task.status === 'succeeded').slice().reverse(); },
        get queueSummary() { const active = this.visibleTasks.filter(task => !terminal.has(task.status)).length; return tr('video_studio.queue_summary', { count: this.visibleTasks.length }) + (active ? tr('video_studio.queue_active', { count: active }) : ''); },
        get presetHelp() { return tr(this.preset === 'strict' ? 'video_studio.preset.strict_help' : this.preset === 'fast_max' ? 'video_studio.preset.fast_max_help' : 'video_studio.preset.fast_help'); },
        get activeAudioRun() { return this.audioRuns.find(run => run.id === this.selectedAudioRunId) || this.audioRuns[0] || null; },
        get activeAudioArtifact() { return this.activeAudioRun?.artifacts?.find(item => item.kind === 'audio' && item.final) || null; },
        get composerDuration() { return Math.max(1, ...this.composerProject.clips.map(clip => clip.start + clip.duration)); },
        get composerFps() { return Math.max(1, Math.min(60, Math.round(Number(this.composerProject.settings.fps) || 30))); },
        get composerFrameDuration() { return 1 / this.composerFps; },
        get composerGridSeconds() {
            if (this.composerScale >= 18) return 1;
            if (this.composerScale >= 8) return 2;
            if (this.composerScale >= 4) return 5;
            return 10;
        },
        get composerTimelineSeconds() { return Math.max(this.composerDuration + Math.max(2, this.composerGridSeconds), 720 / this.composerScale); },
        get composerTimelineWidth() { return Math.ceil(this.composerTimelineSeconds * this.composerScale); },
        get composerTimelineTicks() {
            const count = Math.floor(this.composerTimelineSeconds / this.composerGridSeconds) + 1;
            return Array.from({ length: count }, (_item, index) => index * this.composerGridSeconds);
        },
        get composerClipMinimumWidth() { return this.composerScale >= 18 ? 18 : Math.max(6, this.composerScale); },
        get composerSelectedClip() { return this.composerProject.clips.find(clip => clip.id === this.composerSelectedClipId) || null; },
        get composerSelectedClips() { const ids = new Set(this.composerSelectedClipIds); return this.composerProject.clips.filter(clip => ids.has(clip.id)); },
        get composerSelectedTrack() {
            return this.composerTrack(this.composerSelectedClip?.trackId)
                || this.composerTrack(this.composerSelectedTrackId)
                || this.composerProject.tracks[0]
                || null;
        },
        get composerCanAddProjectItem() { return Boolean(this.composerSelectedTrack?.kind === 'video' && !this.composerSelectedTrack.locked); },
        get composerSelectedKeyframe() { return this.composerSelectedClip?.keyframes?.find(keyframe => keyframe.id === this.composerSelectedKeyframeId) || null; },
        get composerSelectedKeyframeIsEndpoint() { return this.composerIsProtectedKeyframe(this.composerSelectedClip, this.composerSelectedKeyframe); },
        get composerCanFreezeFrame() {
            const clip = this.composerSelectedClip, source = this.composerSource(clip?.sourceId), track = this.composerTrack(clip?.trackId);
            return Boolean(clip && source?.hasVideo && track?.kind === 'video' && !track.locked && this.composerPlayhead >= clip.start - COMPOSER_TIME_EPSILON && this.composerPlayhead <= clip.start + clip.duration + COMPOSER_TIME_EPSILON);
        },
        get composerCanAddKeyframe() {
            const clip = this.composerSelectedClip, source = clip ? this.composerSource(clip.sourceId) : null;
            return Boolean(clip && (clip.layerType === 'spotlight' || clip.layerType === 'text' || source?.hasVideo || source?.hasImage) && this.composerPlayhead >= clip.start && this.composerPlayhead < clip.start + clip.duration);
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
            if (this.mode === 'composer') { await this.loadComposerProject(); await this.loadComposerMaskModels(); await this.loadComposerChatModels(); }
            this.applyResponsiveDefaults();
            this.resizeHandler = () => this.applyResponsiveDefaults(false);
            window.addEventListener('resize', this.resizeHandler);
            this.galleryMessageHandler = event => this.handleGalleryMessage(event);
            window.addEventListener('message', this.galleryMessageHandler);
            this.composerKeyHandler = event => this.handleComposerKeydown(event);
            window.addEventListener('keydown', this.composerKeyHandler);
            this.packageOutputHandler = event => this.handlePackageOutput(event);
            window.addEventListener('ai2apps:studio-output', this.packageOutputHandler);
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
            if (this.noticeTimer) clearTimeout(this.noticeTimer);
            if (this.galleryMessageHandler) window.removeEventListener('message', this.galleryMessageHandler);
            if (this.composerKeyHandler) window.removeEventListener('keydown', this.composerKeyHandler);
            if (this.packageOutputHandler) window.removeEventListener('ai2apps:studio-output', this.packageOutputHandler);
            if (this.resizeHandler) window.removeEventListener('resize', this.resizeHandler);
            this.chatController?.dispose();
            this.packageChatBridge?.dispose();
            this.saveCurrentMiniAppDraft();
            this.persistShellState();
            this.revokePreview('first'); this.revokePreview('last');
        },
        icons() { this.$nextTick(() => window.lucide?.createIcons()); },
        clearNotice() {
            if (this.noticeTimer) clearTimeout(this.noticeTimer);
            this.noticeTimer = null;
            this.notice = '';
        },
        showNotice(message, tone = 'success') {
            this.clearNotice();
            this.notice = String(message || '');
            this.noticeTone = tone;
            if (this.notice) {
                const timeout = tone === 'error' ? 12000 : 4500;
                this.noticeTimer = window.setTimeout(() => this.clearNotice(), timeout);
            }
            this.icons();
        },
        fail(error) { this.showNotice(error?.message || String(error), 'error'); },
        success(message) { this.showNotice(message, 'success'); },
        handlePackageOutput(event) {
            const detail = event?.detail;
            const url = detail?.result?.downloadUrl || '';
            if (detail?.studioId !== APP_ID) return;
            if (!url) { void this.refresh(); return; }
            this.packageOutputUrl = url;
            this.packageOutputRunId = detail.result?.runId || '';
            this.packageOutputMiniAppId = detail.miniAppId || '';
            this.rightCollapsed = false;
            this.persistShellState();
            this.icons();
            void this.refresh();
        },
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
            if (miniApp?.mode === 'upscale') return this.upscalingModels.some(item => item.ready);
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
                try { if (this.isUpscaler) await this.installUpscalingModel(); else await this.ensureVideoCapability('configure-generation'); }
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
                if (Number.isFinite(state.composerScale)) this.composerScale = Math.max(2, Math.min(120, Math.round(state.composerScale / 2) * 2));
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
                    composerScale: this.composerScale,
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
                // Gallery Mini-Entry clicks belong to Gallery's preview flow.
                // Composer media is added only through an explicit drop/import.
                if (this.isComposer) return;
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
            const rawName = this.isUpscaler && this.activeUpscalingArtifact?.downloadUrl === url
                ? `${String(this.activeUpscalingRun?.input?.sourceName || 'video').replace(/\.[^.]+$/, '')}-upscaled.mp4`
                : this.packageOutputUrl === url ? 'subtitled-video.mp4' : (task ? this.taskTitle(task) : tr('video_studio.joined_video'));
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
                const reference = this.artifactReference(url, (this.joinedVideoUrl === url || this.packageOutputUrl === url) ? null : task);
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
                const reference = this.artifactReference(this.activeVideoUrl, (this.isUpscaler || this.joinedVideoUrl || this.packageOutputUrl) ? null : this.activeTask);
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
                    if (this.mode === 'upscale') { this.selectUpscalingFile(localFile); return; }
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
            if (this.mode === 'upscale') { this.selectUpscalingFile(file); return; }
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
                this.upscalingRuns = (runs.items || []).filter(run => run.miniAppId === 'ai2apps.video.upscaling');
                this.packageRuns = (runs.items || []).filter(run => !['ai2apps.video.extract-audio', 'ai2apps.video.composer', 'ai2apps.video.upscaling'].includes(run.miniAppId));
                void this.loadUpscalingModels().catch(() => {});
                let selectedProviderChanged = false;
                if (!this.isLocalVideoTool && !this.modeProviders.some(item => item.id === this.modelId && item.ready)) {
                    const probe = await window.AI2AppsCapabilities?.probe(this.capabilityRequest('probe', ''));
                    const recommendedId = probe?.provider?.modelId || probe?.plan?.stack?.checkpoint?.model_id || '';
                    this.modelId = preferredProviderId(this.modeProviders, recommendedId);
                    selectedProviderChanged = true;
                }
                this.syncDefaults(selectedProviderChanged);
                if (!this.tasks.some(task => task.id === this.selectedTaskId)) this.selectedTaskId = this.tasks.find(task => task.status === 'succeeded')?.id || this.tasks[0]?.id || '';
                if (!this.audioRuns.some(run => run.id === this.selectedAudioRunId)) this.selectedAudioRunId = this.audioRuns[0]?.id || '';
                if (!this.composerRuns.some(run => run.id === this.selectedComposerRunId)) this.selectedComposerRunId = this.composerRuns[0]?.id || '';
                if (!this.upscalingRuns.some(run => run.id === this.selectedUpscalingRunId)) this.selectedUpscalingRunId = this.upscalingRuns[0]?.id || '';
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
            if (this.polling || this.refreshing || (!this.tasks.some(task => !terminal.has(task.status)) && !this.audioRuns.some(run => !terminal.has(run.status)) && !this.composerRuns.some(run => !terminal.has(run.status)) && !this.upscalingRuns.some(run => !terminal.has(run.status)) && !this.packageRuns.some(run => !terminal.has(run.status)))) return;
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
                this.upscalingRuns = runs.filter(run => run.miniAppId === 'ai2apps.video.upscaling');
                this.packageRuns = runs.filter(run => !['ai2apps.video.extract-audio', 'ai2apps.video.composer', 'ai2apps.video.upscaling'].includes(run.miniAppId));
                this.icons();
            } catch (error) { this.fail(error); } finally { this.polling = false; }
        },
        syncDefaults(force = true) {
            if (!this.selectedProvider) return;
            const defaults = this.caps.defaults || {};
            if (force || !this.resolutions.includes(this.resolution)) this.resolution = defaults.resolution || this.resolutions[0];
            if (force || !this.presets.some(item => item.id === this.preset)) this.preset = defaults.preset || this.presets[0]?.id || 'strict';
            if (force) {
                this.seed = Number(defaults.seed ?? 42);
                const recommendedSteps = Number(defaults.steps ?? 20);
                if (Number.isInteger(recommendedSteps) && recommendedSteps >= 1 && recommendedSteps <= 60) this.steps = recommendedSteps;
            }
            this.duration = this.normalizeDuration(this.duration);
            this.syncModelSelectValue();
            this.icons();
        },
        normalizeDuration(value) {
            const numeric = Number(value) || 5;
            const aligned = Math.round(numeric / this.durationStep) * this.durationStep;
            return Math.min(this.durationMax, Math.max(this.durationMin, aligned));
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
            } else if (mode === 'upscale') {
                await this.loadUpscalingModels();
            } else if (mode === 'composer') {
                await this.loadComposerProject(); await this.loadComposerMaskModels(); await this.loadComposerChatModels();
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
        composerMaskModel(modelId) { return this.composerMaskModels.find(model => model.id === modelId) || null; },
        composerMaskNeedsPoint(clip = this.composerSelectedClip) { return Boolean(this.composerMaskModel(clip?.maskModelId)?.promptTypes?.includes('point')); },
        composerCompatibleSources(clip) {
            if (clip?.layerType && clip.layerType !== 'media') return [];
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
        setComposerClipSpeed(value) {
            const clip = this.composerSelectedClip; if (!clip) return;
            const speed = Math.max(COMPOSER_MIN_SPEED, Math.min(COMPOSER_MAX_SPEED, Number(value) || 1));
            if (Math.abs(speed - Number(clip.speed)) <= COMPOSER_TIME_EPSILON) { this.composerChanged(); return; }
            this.composerPushHistory(); this.retimeComposerClip(clip, speed); this.composerChanged(); this.syncComposerPreview();
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
            return {
                x: Number(clip.x) || 0, y: Number(clip.y) || 0,
                width: Number(clip.width) || settings.width, height: Number(clip.height) || settings.height,
                opacity: Number.isFinite(Number(clip.opacity)) ? Number(clip.opacity) : 1,
                scale: Number.isFinite(Number(clip.scale)) ? Number(clip.scale) : 1,
                cropLeft: Math.max(0, Math.min(95, Number(clip.cropLeft)||0)),
                cropTop: Math.max(0, Math.min(95, Number(clip.cropTop)||0)),
                cropRight: Math.max(0, Math.min(95, Number(clip.cropRight)||0)),
                cropBottom: Math.max(0, Math.min(95, Number(clip.cropBottom)||0)),
                cropShape: ['rectangle','ellipse','rounded'].includes(clip.cropShape) ? clip.cropShape : 'rectangle',
                cropCornerRadius: Math.max(0, Number(clip.cropCornerRadius)||0),
                cropFeather: Math.max(0, Number(clip.cropFeather)||0),
                cropScale: Math.max(.01, Math.min(20, Number(clip.cropScale)||1)),
            };
        },
        composerVisualStateAtFrame(clip, localFrame) {
            const numeric = ['x','y','width','height','opacity','scale','cropLeft','cropTop','cropRight','cropBottom','cropCornerRadius','cropFeather','cropScale'];
            let previousFrame = 0, previous = this.composerBaseVisualState(clip);
            for (const keyframe of this.composerClipKeyframes(clip)) {
                const target = { ...previous };
                numeric.forEach(key => { if (keyframe[key] !== null && keyframe[key] !== '' && keyframe[key] !== undefined) target[key] = Number(keyframe[key]); });
                if (['rectangle','ellipse','rounded'].includes(keyframe.cropShape)) target.cropShape = keyframe.cropShape;
                if (localFrame >= keyframe.frame) { previousFrame = keyframe.frame; previous = target; continue; }
                if (keyframe.transition === 'hold' || keyframe.frame <= previousFrame) return { ...previous };
                let progress = Math.max(0, Math.min(1, (localFrame - previousFrame) / (keyframe.frame - previousFrame)));
                if (keyframe.transition === 'ease') progress = progress * progress * (3 - 2 * progress);
                const result = { ...previous };
                numeric.forEach(key => { result[key] = previous[key] + (target[key] - previous[key]) * progress; });
                return result;
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
            const numeric = ['x','y','width','height','opacity','scale','cropLeft','cropTop','cropRight','cropBottom','cropCornerRadius','cropFeather','cropScale'];
            let state = this.composerBaseVisualState(clip);
            for (const item of this.composerClipKeyframes(clip)) {
                if (item.id === keyframe?.id) break;
                const next = { ...state };
                numeric.forEach(key => { if (item[key] !== null && item[key] !== '' && item[key] !== undefined) next[key] = Number(item[key]); });
                if (['rectangle','ellipse','rounded'].includes(item.cropShape)) next.cropShape = item.cropShape;
                state = next;
            }
            return state;
        },
        setComposerKeyframeValue(field, value) {
            const keyframe = this.composerSelectedKeyframe; if (!keyframe || !['x', 'y', 'width', 'height', 'opacity', 'scale', 'cropLeft', 'cropTop', 'cropRight', 'cropBottom', 'cropCornerRadius', 'cropFeather', 'cropScale'].includes(field)) return;
            if (value === '') keyframe[field] = null;
            else {
                let number = Number(value); if (!Number.isFinite(number)) return;
                if (field === 'width' || field === 'height') number = Math.max(16, Math.round(number));
                else if (field === 'opacity') number = Math.max(0, Math.min(1, number));
                else if (field === 'scale') number = Math.max(.05, Math.min(20, number));
                else if (['cropLeft','cropTop','cropRight','cropBottom'].includes(field)) {
                    const opposite = { cropLeft:'cropRight', cropRight:'cropLeft', cropTop:'cropBottom', cropBottom:'cropTop' }[field];
                    const state = this.composerVisualStateAtFrame(this.composerSelectedClip, keyframe.frame);
                    number = Math.max(0, Math.min(95, 99 - (Number(state[opposite])||0), number));
                }
                else if (field === 'cropCornerRadius') number = Math.max(0, Math.min(4096, Math.round(number)));
                else if (field === 'cropFeather') number = Math.max(0, Math.min(512, Math.round(number)));
                else if (field === 'cropScale') number = Math.max(.01, Math.min(20, number));
                else number = Math.round(number);
                keyframe[field] = number;
            }
            this.syncComposerPreview();
        },
        setComposerKeyframeCropShape(value) {
            const keyframe = this.composerSelectedKeyframe; if (!keyframe) return;
            keyframe.cropShape = ['rectangle','ellipse','rounded'].includes(value) ? value : null;
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
                if (!source?.hasAudio || !track || !clip.audioEnabled || !this.composerClipActiveAtPlayhead(clip)) return false;
                return track.kind === 'audio' ? !track.muted : track.kind === 'video' && track.muted;
            });
        },
        composerClipStyle(clip) { const color = clip.color || '#3b82f6'; return `left:${clip.start * this.composerScale}px;width:${Math.max(this.composerClipMinimumWidth, clip.duration * this.composerScale)}px;background:${color};border-color:${color}`;
        },
        composerStageStyle() {
            const settings = this.composerProject.settings;
            const ratio = settings.width / settings.height;
            const width = Math.min(680, 390 * ratio);
            return `width:min(100%,${width}px);aspect-ratio:${settings.width}/${settings.height};background:${settings.background}`;
        },
        composerPreviewStyle(clip) {
            const settings = this.composerProject.settings;
            const state = this.composerVisualStateAt(clip);
            const anchor = clip.layerType === 'text' ? this.composerTextAnchorTransform(clip.textAnchor) : '';
            if (clip.layerType === 'text') return `left:${state.x / settings.width * 100}%;top:${state.y / settings.height * 100}%;opacity:${state.opacity};transform:${anchor} scale(${state.scale});transform-origin:${this.composerTextTransformOrigin(clip.textAnchor)}`;
            let mediaFrame = '';
            const source = this.composerSource(clip.sourceId);
            if (source?.hasVideo || source?.hasImage) {
                const geometry = this.composerCropFrameGeometry(clip, state);
                mediaFrame = `;--media-frame-left:${geometry.left}%;--media-frame-top:${geometry.top}%;--media-frame-width:${geometry.width}%;--media-frame-height:${geometry.height}%;--media-frame-radius:${geometry.radius}`;
            }
            return `left:${state.x / settings.width * 100}%;top:${state.y / settings.height * 100}%;width:${state.width / settings.width * 100}%;height:${state.height / settings.height * 100}%;opacity:${state.opacity};transform:${anchor} scale(${state.scale});transform-origin:${this.composerTextTransformOrigin(clip.textAnchor)}${mediaFrame}`;
        },
        composerTextAnchorTransform(anchor = 'center') {
            const x = anchor.endsWith('left') || anchor === 'left' ? '0' : anchor.endsWith('right') || anchor === 'right' ? '-100%' : '-50%';
            const y = anchor.startsWith('top') || anchor === 'top' ? '0' : anchor.startsWith('bottom') || anchor === 'bottom' ? '-100%' : '-50%';
            return `translate(${x},${y})`;
        },
        composerTextTransformOrigin(anchor = 'center') {
            const x = anchor.endsWith('left') || anchor === 'left' ? 'left' : anchor.endsWith('right') || anchor === 'right' ? 'right' : 'center';
            const y = anchor.startsWith('top') || anchor === 'top' ? 'top' : anchor.startsWith('bottom') || anchor === 'bottom' ? 'bottom' : 'center';
            return `${x} ${y}`;
        },
        composerTextPreview(clip) {
            const text = String(clip.text || '');
            if (!clip.reveal) return text;
            return text.slice(0, Math.max(0, Math.floor((this.composerPlayhead - clip.start) * (Number(clip.revealSpeed) || 12))));
        },
        composerTextStyle(clip) {
            const canvasWidth = this.composerProject.settings.width;
            const unit = value => `${Math.max(0, Number(value)||0) / canvasWidth * 100}cqw`;
            const signedUnit = value => `${(Number(value)||0) / canvasWidth * 100}cqw`;
            const rgba = (color, opacity) => {
                const match = /^#([0-9a-f]{6})$/i.exec(String(color || '#000000'));
                const value = parseInt(match?.[1] || '000000', 16);
                return `rgba(${value >> 16},${value >> 8 & 255},${value & 255},${Math.max(0, Math.min(1, Number(opacity)||0))})`;
            };
            const shadows = [];
            const strokeWidth = clip.textStrokeEnabled ? Math.max(0, Number(clip.textStrokeWidth)||0) : 0;
            let stroke = '0 transparent';
            if (strokeWidth && clip.textStrokeStyle === 'feather') shadows.push(`0 0 ${unit(strokeWidth)} ${clip.textStrokeColor||'#000000'}`);
            else if (strokeWidth) stroke = `${unit(strokeWidth * 2)} ${clip.textStrokeColor||'#000000'}`;
            if (clip.textShadowEnabled && Number(clip.textShadowOpacity) > 0) {
                shadows.push(`${signedUnit(clip.textShadowOffsetX)} ${signedUnit(clip.textShadowOffsetY)} ${unit(clip.textShadowBlur)} ${rgba(clip.textShadowColor,clip.textShadowOpacity)}`);
            }
            const decorations = [clip.textUnderline && 'underline', clip.textStrikethrough && 'line-through'].filter(Boolean).join(' ') || 'none';
            return `font-size:${Math.max(8, Number(clip.fontSize)||64) / canvasWidth * 100}cqw;color:${clip.textColor||'#ffffff'};-webkit-text-fill-color:${clip.textColor||'#ffffff'};font-weight:${clip.textBold?'800':'600'};font-style:${clip.textItalic?'italic':'normal'};text-decoration-line:${decorations};paint-order:stroke fill;-webkit-text-stroke:${stroke};text-shadow:${shadows.length?shadows.join(','):'none'}`;
        },
        composerSpotlightStyle(clip) {
            const alpha = Math.max(0, Math.min(1, Number(clip.dimOpacity) || 0));
            const radius = clip.spotlightShape === 'ellipse' ? '50%' : `${Math.max(0, Number(clip.cornerRadius) || 0)}px`;
            const feather = Math.max(0, Number(clip.feather)||0) / this.composerProject.settings.width * 100;
            const color = `rgba(0,0,0,${alpha})`;
            const inward = feather ? `,inset 0 0 ${feather}cqw ${feather/2}cqw ${color}` : '';
            return `border-radius:${radius};box-shadow:0 0 0 9999px ${color}${inward}`;
        },
        composerPreviewFeather(clip) {
            if (clip.layerType === 'spotlight') return Math.max(0, Number(clip.feather)||0);
            return Math.max(0, Number(this.composerVisualStateAt(clip).cropFeather)||0);
        },
        composerFeatherGuideStyle(clip) {
            const feather = this.composerPreviewFeather(clip) / this.composerProject.settings.width * 100;
            const state = this.composerVisualStateAt(clip);
            const shape = clip.layerType === 'spotlight' ? clip.spotlightShape : state.cropShape;
            const radiusValue = clip.layerType === 'spotlight' ? clip.cornerRadius : state.cropCornerRadius;
            const radius = shape === 'ellipse' ? '50%' : shape === 'rounded' ? `${Math.max(0,Number(radiusValue)||0) / this.composerProject.settings.width * 100}cqw` : '0';
            return `--feather-guide:${feather}cqw;border-radius:${radius}`;
        },
        composerPreviewMaskStyle(clip) {
            const mask = this.composerSource(clip.maskSourceId); if (!mask?.hasImage) return '';
            const url = this.composerSourceUrl(mask.id), mode = mask.hasAlpha ? 'alpha' : 'luminance';
            return `mask-image:url(${url});mask-size:100% 100%;mask-repeat:no-repeat;mask-mode:${mode};-webkit-mask-image:url(${url});-webkit-mask-size:100% 100%;-webkit-mask-repeat:no-repeat`;
        },
        clearComposerDynamicMask(clipId) {
            if (!clipId) return;
            document.querySelectorAll(`video[data-clip-id="${CSS.escape(clipId)}"]`).forEach(sourceVideo => {
                const frame = sourceVideo.closest('.vs-composer-media-frame');
                if (!frame) return;
                ['maskImage','webkitMaskImage','maskSize','webkitMaskSize','maskPosition','webkitMaskPosition','maskRepeat','webkitMaskRepeat','maskMode'].forEach(property => { frame.style[property] = ''; });
            });
        },
        updateComposerDynamicMask(maskVideo) {
            if (!maskVideo?.videoWidth || !maskVideo?.videoHeight) return;
            const clipId = maskVideo.dataset.maskClipId, clip = this.composerProject.clips.find(item => item.id === clipId);
            if (!clip || clip.maskKind !== 'person') return;
            const frame = maskVideo.closest('.vs-composer-media-frame');
            const sourceVideo = frame?.querySelector(`video[data-clip-id="${CSS.escape(clipId)}"]`);
            if (!frame || !sourceVideo) return;
            const canvas = document.createElement('canvas');
            canvas.width = maskVideo.videoWidth; canvas.height = maskVideo.videoHeight;
            const context = canvas.getContext('2d', { alpha: false }); if (!context) return;
            try {
                context.drawImage(maskVideo, 0, 0, canvas.width, canvas.height);
                const url = `url(${canvas.toDataURL('image/jpeg', .82)})`;
                const frameRect = frame.getBoundingClientRect(), sourceRect = sourceVideo.getBoundingClientRect();
                const size = `${sourceRect.width}px ${sourceRect.height}px`;
                const position = `${sourceRect.left-frameRect.left}px ${sourceRect.top-frameRect.top}px`;
                frame.style.maskImage = url; frame.style.webkitMaskImage = url;
                frame.style.maskSize = size; frame.style.webkitMaskSize = size;
                frame.style.maskPosition = position; frame.style.webkitMaskPosition = position;
                frame.style.maskRepeat = 'no-repeat'; frame.style.webkitMaskRepeat = 'no-repeat';
                frame.style.maskMode = 'luminance';
            } catch (_) {}
        },
        composerCropInsetsForViewport(state, width, height, source) {
            const cropLeft = Math.max(0, Math.min(95, Number(state.cropLeft)||0));
            const cropTop = Math.max(0, Math.min(95, Number(state.cropTop)||0));
            const cropScale = Math.max(.01, Math.min(20, Number(state.cropScale)||1));
            const sourceWidth = Math.max(1, Number(source?.width)||width);
            const sourceHeight = Math.max(1, Number(source?.height)||height);
            const cropRight = 100 - cropLeft - Math.max(16, Number(width)||16) / (sourceWidth * cropScale) * 100;
            const cropBottom = 100 - cropTop - Math.max(16, Number(height)||16) / (sourceHeight * cropScale) * 100;
            return {
                cropRight: Math.max(0, Math.min(95, 99-cropLeft, cropRight)),
                cropBottom: Math.max(0, Math.min(95, 99-cropTop, cropBottom)),
            };
        },
        composerCropFrameGeometry(clip, overrideState = null) {
            const source = this.composerSource(clip.sourceId), state = overrideState || this.composerVisualStateAt(clip);
            const left = Math.max(0, Math.min(95, Number(state.cropLeft)||0)) / 100;
            const top = Math.max(0, Math.min(95, Number(state.cropTop)||0)) / 100;
            const right = Math.max(0, Math.min(95, Number(state.cropRight)||0)) / 100;
            const bottom = Math.max(0, Math.min(95, Number(state.cropBottom)||0)) / 100;
            const visibleWidth = Math.max(.01, 1 - left - right), visibleHeight = Math.max(.01, 1 - top - bottom);
            const cropScale = Math.max(.01, Math.min(20, Number(state.cropScale)||1));
            const contentWidth = Math.max(.01, Number(source?.width)||state.width) * visibleWidth * cropScale;
            const contentHeight = Math.max(.01, Number(source?.height)||state.height) * visibleHeight * cropScale;
            const width = Math.min(100, contentWidth / Math.max(.01, state.width) * 100);
            const height = Math.min(100, contentHeight / Math.max(.01, state.height) * 100);
            const shape = state.cropShape || 'rectangle';
            const radius = shape === 'ellipse' ? '50%' : shape === 'rounded' ? `${Math.max(0,Number(state.cropCornerRadius)||0) / this.composerProject.settings.width * 100}cqw` : '0';
            return { left: 0, top: 0, width, height, radius, shape, contentWidth, contentHeight };
        },
        composerCropFrameStyle(clip, overrideState = null) {
            const state = overrideState || this.composerVisualStateAt(clip);
            const geometry = this.composerCropFrameGeometry(clip, state);
            const feather = Math.max(0, Number(state.cropFeather)||0) / this.composerProject.settings.width * 100;
            let mask = '';
            if (feather > 0) {
                const distance = `${feather}cqw`;
                mask = geometry.shape === 'ellipse'
                    ? `mask-image:radial-gradient(ellipse at center,#000 calc(100% - ${distance}),transparent 100%);-webkit-mask-image:radial-gradient(ellipse at center,#000 calc(100% - ${distance}),transparent 100%)`
                    : `mask-image:linear-gradient(to right,transparent,#000 ${distance},#000 calc(100% - ${distance}),transparent),linear-gradient(to bottom,transparent,#000 ${distance},#000 calc(100% - ${distance}),transparent);mask-composite:intersect;-webkit-mask-image:linear-gradient(to right,transparent,#000 ${distance},#000 calc(100% - ${distance}),transparent),linear-gradient(to bottom,transparent,#000 ${distance},#000 calc(100% - ${distance}),transparent);-webkit-mask-composite:source-in`;
            }
            return `left:${geometry.left}%;top:${geometry.top}%;width:${geometry.width}%;height:${geometry.height}%;border-radius:${geometry.radius};${mask}`;
        },
        composerCropMediaStyle(clip, overrideState = null) {
            const state = overrideState || this.composerVisualStateAt(clip);
            const source = this.composerSource(clip.sourceId);
            const left = Math.max(0, Math.min(95, Number(state.cropLeft)||0)) / 100;
            const top = Math.max(0, Math.min(95, Number(state.cropTop)||0)) / 100;
            const right = Math.max(0, Math.min(95, Number(state.cropRight)||0)) / 100;
            const bottom = Math.max(0, Math.min(95, Number(state.cropBottom)||0)) / 100;
            const visibleWidth = Math.max(.01, 1-left-right), visibleHeight = Math.max(.01, 1-top-bottom);
            const cropScale = Math.max(.01, Math.min(20, Number(state.cropScale)||1));
            const sourceWidth = Math.max(.01, Number(source?.width)||state.width), sourceHeight = Math.max(.01, Number(source?.height)||state.height);
            const frameWidth = Math.max(.01, Math.min(Number(state.width)||1, sourceWidth * visibleWidth * cropScale));
            const frameHeight = Math.max(.01, Math.min(Number(state.height)||1, sourceHeight * visibleHeight * cropScale));
            return `left:${-sourceWidth*left*cropScale/frameWidth*100}%;top:${-sourceHeight*top*cropScale/frameHeight*100}%;width:${sourceWidth*cropScale/frameWidth*100}%;height:${sourceHeight*cropScale/frameHeight*100}%`;
        },
        composerClipFrameRange(clip) {
            return { start: this.composerFrameNumber(clip?.start), duration: Math.max(1, this.composerFrameNumber(clip?.duration)) };
        },
        composerClipActiveAtPlayhead(clip) {
            const frame = this.composerFrameNumber(this.composerPlayhead), range = this.composerClipFrameRange(clip);
            return frame >= range.start && frame < range.start + range.duration;
        },
        composerPreviewTimelineClips() {
            const tracks = new Map(this.composerProject.tracks.map(track => [track.id, track]));
            const frame = this.composerFrameNumber(this.composerPlayhead), preloadAhead = this.composerFps, retainBehind = Math.ceil(this.composerFps / 4);
            return this.composerProject.clips.filter(clip => {
                const source = this.composerSource(clip.sourceId), track = tracks.get(clip.trackId);
                const range = this.composerClipFrameRange(clip), nearPlayhead = range.start <= frame + preloadAhead && range.start + range.duration > frame - retainBehind;
                return nearPlayhead && (clip.layerType === 'spotlight' || clip.layerType === 'text' || source?.hasVideo || source?.hasImage) && track?.kind === 'video' && !track.muted;
            }).sort((a, b) => (tracks.get(a.trackId)?.order || 0) - (tracks.get(b.trackId)?.order || 0));
        },
        composerPreviewClips() { return this.composerPreviewTimelineClips().filter(clip => this.composerClipActiveAtPlayhead(clip)); },
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
                    clip.layerType = clip.layerType || 'media';
                    clip.scale = Number.isFinite(Number(clip.scale)) ? Number(clip.scale) : 1;
                    clip.cropLeft = Math.max(0, Math.min(95, Number(clip.cropLeft)||0));
                    clip.cropTop = Math.max(0, Math.min(95, Number(clip.cropTop)||0));
                    clip.cropRight = Math.max(0, Math.min(95, Number(clip.cropRight)||0));
                    clip.cropBottom = Math.max(0, Math.min(95, Number(clip.cropBottom)||0));
                    if (clip.cropLeft + clip.cropRight >= 100) clip.cropRight = Math.max(0, 99 - clip.cropLeft);
                    if (clip.cropTop + clip.cropBottom >= 100) clip.cropBottom = Math.max(0, 99 - clip.cropTop);
                    clip.cropShape = ['rectangle','ellipse','rounded'].includes(clip.cropShape) ? clip.cropShape : 'rectangle';
                    clip.cropCornerRadius = Math.max(0, Math.min(4096, Math.round(Number(clip.cropCornerRadius)||32)));
                    clip.cropFeather = Math.max(0, Math.min(512, Math.round(Number(clip.cropFeather)||0)));
                    const migrateCropViewport = Number(clip.cropViewportVersion||0) < 2;
                    if (!Number.isFinite(Number(clip.cropScale)) || Number(clip.cropScale) <= 0) {
                        const source = this.composerSource(clip.sourceId), settings = this.composerProject.settings;
                        const visibleWidth = Math.max(.01, 1 - clip.cropLeft / 100 - clip.cropRight / 100);
                        const visibleHeight = Math.max(.01, 1 - clip.cropTop / 100 - clip.cropBottom / 100);
                        clip.cropScale = Math.min(
                            (Number(clip.width)||settings.width) / (Math.max(1,Number(source?.width)||settings.width) * visibleWidth),
                            (Number(clip.height)||settings.height) / (Math.max(1,Number(source?.height)||settings.height) * visibleHeight),
                        );
                    }
                    clip.cropScale = Math.max(.01, Math.min(20, Number(clip.cropScale)||1));
                    clip.cropViewportVersion = 2;
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
                            scale: keyframe.scale === null || keyframe.scale === '' || keyframe.scale === undefined ? null : Math.max(.05, Math.min(20, Number(keyframe.scale))),
                            cropLeft: keyframe.cropLeft === null || keyframe.cropLeft === '' || keyframe.cropLeft === undefined ? null : Math.max(0, Math.min(95, Number(keyframe.cropLeft))),
                            cropTop: keyframe.cropTop === null || keyframe.cropTop === '' || keyframe.cropTop === undefined ? null : Math.max(0, Math.min(95, Number(keyframe.cropTop))),
                            cropRight: keyframe.cropRight === null || keyframe.cropRight === '' || keyframe.cropRight === undefined ? null : Math.max(0, Math.min(95, Number(keyframe.cropRight))),
                            cropBottom: keyframe.cropBottom === null || keyframe.cropBottom === '' || keyframe.cropBottom === undefined ? null : Math.max(0, Math.min(95, Number(keyframe.cropBottom))),
                            cropShape: ['rectangle','ellipse','rounded'].includes(keyframe.cropShape) ? keyframe.cropShape : null,
                            cropCornerRadius: keyframe.cropCornerRadius === null || keyframe.cropCornerRadius === '' || keyframe.cropCornerRadius === undefined ? null : Math.max(0, Math.min(4096, Math.round(Number(keyframe.cropCornerRadius)))),
                            cropFeather: keyframe.cropFeather === null || keyframe.cropFeather === '' || keyframe.cropFeather === undefined ? null : Math.max(0, Math.min(512, Math.round(Number(keyframe.cropFeather)))),
                            cropScale: keyframe.cropScale === null || keyframe.cropScale === '' || keyframe.cropScale === undefined ? null : Math.max(.01, Math.min(20, Number(keyframe.cropScale))),
                        });
                    });
                    if (isVideoTrack) {
                        const endFrame = durationFrames - 1;
                        let start = [...byFrame.values()].find(keyframe => keyframe.endpoint === 'start') || byFrame.get(0);
                        if (!start) start = { id: composerId('keyframe'), frame: 0, transition: 'hold', x: Math.round(base.x), y: Math.round(base.y), width: Math.max(16, Math.round(base.width)), height: Math.max(16, Math.round(base.height)), opacity: base.opacity, scale: base.scale, cropLeft: base.cropLeft, cropTop: base.cropTop, cropRight: base.cropRight, cropBottom: base.cropBottom, cropShape: base.cropShape, cropCornerRadius: base.cropCornerRadius, cropFeather: base.cropFeather, cropScale: base.cropScale };
                        start.frame = 0; start.endpoint = 'start'; start.transition = 'hold'; byFrame.set(0, start);
                        let end = [...byFrame.values()].find(keyframe => keyframe.endpoint === 'end') || byFrame.get(endFrame);
                        if (!end || end === start) {
                            end = { id: composerId('keyframe'), frame: endFrame, transition: 'linear', x: null, y: null, width: null, height: null, opacity: null, scale: null, cropLeft: null, cropTop: null, cropRight: null, cropBottom: null, cropShape: null, cropCornerRadius: null, cropFeather: null, cropScale: null };
                        }
                        end.frame = endFrame; end.endpoint = 'end'; byFrame.set(endFrame, end);
                    }
                    clip.keyframes = [...byFrame.values()].sort((a, b) => a.frame - b.frame);
                    if (migrateCropViewport && (this.composerSource(clip.sourceId)?.hasVideo || this.composerSource(clip.sourceId)?.hasImage)) {
                        const source = this.composerSource(clip.sourceId);
                        Object.assign(clip, this.composerCropInsetsForViewport(this.composerBaseVisualState(clip), clip.width, clip.height, source));
                        this.composerClipKeyframes(clip).forEach(keyframe => {
                            const hasOwnViewport = ['width','height','cropLeft','cropTop','cropRight','cropBottom','cropScale'].some(field => keyframe[field] !== null && keyframe[field] !== '' && keyframe[field] !== undefined);
                            if (!hasOwnViewport) return;
                            const state = this.composerVisualStateAtFrame(clip, keyframe.frame);
                            Object.assign(keyframe, this.composerCropInsetsForViewport(state, state.width, state.height, source));
                        });
                    }
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
                        if (!['image','person'].includes(clip.maskKind)) clip.maskKind = 'image';
                        if (!clip.maskModelId) clip.maskModelId = 'apple.vision/person-segmentation';
                        if (!Number.isFinite(Number(clip.maskPromptFrame))) clip.maskPromptFrame = 0;
                        if (!Number.isFinite(Number(clip.maskThreshold))) clip.maskThreshold = .5;
                        if (!Number.isFinite(Number(clip.maskFeather))) clip.maskFeather = 1.5;
                    });
                    this.normalizeComposerTimeline();
                }
                if (Array.isArray(record.draft?.sources)) this.composerSources = record.draft.sources;
                if (typeof record.draft?.documentPath === 'string') {
                    const savedPath = record.draft.documentPath;
                    const interimManagedPath = /[\\/]data[\\/]projects[\\/]video-studio[\\/][^\\/]+$/i.test(savedPath);
                    this.composerDocumentPath = interimManagedPath ? '' : savedPath;
                    if (interimManagedPath) this.scheduleComposerSave();
                }
            } catch (error) { this.fail(error); }
        },
        async loadComposerMaskModels() {
            try {
                const payload = await responsePayload(await fetch(`${STUDIO_API}/composer/mask-models`, {
                    credentials: 'same-origin', headers: this.draftHeaders(),
                }));
                this.composerMaskModels = payload.items || [];
            } catch (error) { this.composerMaskModels = []; this.fail(error); }
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
        async newComposerDocument() {
            if (this.composerProject.clips.length && !window.confirm(tr('video_studio.composer.project_confirm_new'))) return;
            if (this.composerPlaying) this.toggleComposerPreview();
            if (this.composerSaveTimer) { clearTimeout(this.composerSaveTimer); this.composerSaveTimer = 0; }
            this.composerProject = newComposerProject(); this.composerSources = []; this.composerDocumentPath = '';
            this.composerHistory = []; this.composerFuture = []; this.composerSelectedClipId = ''; this.composerSelectedClipIds = []; this.composerSelectedKeyframeId = '';
            this.composerPlayhead = 0; this.composerPlayheadSnapped = false;
            await this.saveComposerProject(); this.icons();
            this.success(tr('video_studio.composer.project_created'));
        },
        async openComposerDocument(event) {
            const file = Array.from(event?.target?.files || [])[0];
            if (!file) return;
            try {
                const sourcePath = nativeFilePath(file);
                let response;
                if (sourcePath) {
                    response = await fetch(`${STUDIO_API}/composer/projects/open`, {
                        method: 'POST', credentials: 'same-origin', headers: this.composerDocumentHeaders(), body: JSON.stringify({ sourcePath }),
                    });
                } else {
                    const form = new FormData(); form.append('file', file, file.name);
                    response = await fetch(`${STUDIO_API}/composer/projects/import`, {
                        method: 'POST', credentials: 'same-origin', headers: this.draftHeaders(), body: form,
                    });
                }
                const record = await responsePayload(response);
                this.applyComposerDocument(record); this.success(tr('video_studio.composer.project_opened', { name: file.name }));
            } catch (error) { this.fail(error); } finally { if (event?.target) event.target.value = ''; }
        },
        async writeComposerDocument(targetPath) {
            const record = await responsePayload(await fetch(`${STUDIO_API}/composer/projects/save`, {
                method: 'POST', credentials: 'same-origin', headers: this.composerDocumentHeaders(),
                body: JSON.stringify({ targetPath, project: this.composerProject, sourceIds: this.composerSources.map(source => source.id) }),
            }));
            this.composerDocumentPath = record.path; this.composerSources = record.sources;
            await this.saveComposerProject();
            this.success(tr('video_studio.composer.project_saved', { name: record.path.split('/').pop() }));
        },
        async exportComposerDocument() {
            if (this.composerDocumentSaving) return;
            this.composerDocumentSaving = true;
            try {
                const record = await responsePayload(await fetch(`${STUDIO_API}/composer/projects/export`, {
                    method: 'POST', credentials: 'same-origin', headers: this.composerDocumentHeaders(),
                    body: JSON.stringify({ outputName: this.composerProjectFileName(), project: this.composerProject, sourceIds: this.composerSources.map(source => source.id) }),
                }));
                const link = document.createElement('a');
                link.href = record.downloadUrl; link.download = record.name || this.composerProjectFileName();
                document.body.appendChild(link); link.click(); link.remove();
                this.success(tr('video_studio.composer.project_save_dialog'));
            } catch (error) { this.fail(error); }
            finally { this.composerDocumentSaving = false; this.icons(); }
        },
        async saveComposerDocument() {
            if (!this.composerDocumentPath) return this.exportComposerDocument();
            if (this.composerDocumentSaving) return;
            this.composerDocumentSaving = true;
            try { await this.writeComposerDocument(this.composerDocumentPath); }
            catch (error) { this.fail(error); }
            finally { this.composerDocumentSaving = false; this.icons(); }
        },
        async saveComposerDocumentAs() {
            return this.exportComposerDocument();
        },
        async registerComposerSource(payload) {
            return responsePayload(await fetch(`${STUDIO_API}/composer/sources`, {
                method: 'POST', credentials: 'same-origin', headers: { ...this.draftHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            }));
        },
        async uploadComposerSource(file) {
            const form = new FormData();
            form.append('file', file, file.name);
            return responsePayload(await fetch(`${STUDIO_API}/composer/sources/import`, {
                method: 'POST', credentials: 'same-origin', headers: { ...this.draftHeaders(), Accept: 'application/json' }, body: form,
            }));
        },
        async captureComposerVideoFrame(clip, source, sourceTime) {
            const video = document.createElement('video');
            video.muted = true; video.playsInline = true; video.preload = 'auto';
            const ready = new Promise((resolve, reject) => {
                const fail = () => reject(new Error(tr('video_studio.error.freeze_frame')));
                video.addEventListener('error', fail, { once: true });
                video.addEventListener('loadedmetadata', () => {
                    const duration = Number.isFinite(video.duration) ? video.duration : Number(source.duration) || 0;
                    const maximum = Math.max(0, duration - this.composerFrameDuration);
                    const target = Math.max(0, Math.min(maximum || sourceTime, sourceTime));
                    if (Math.abs((video.currentTime || 0) - target) < .001) { resolve(); return; }
                    video.addEventListener('seeked', resolve, { once: true });
                    try { video.currentTime = target; } catch (_) { fail(); }
                }, { once: true });
            });
            video.src = this.composerSourceUrl(source.id); video.load();
            try {
                await ready;
                if (!video.videoWidth || !video.videoHeight) throw new Error(tr('video_studio.error.freeze_frame'));
                const canvas = document.createElement('canvas'); canvas.width = video.videoWidth; canvas.height = video.videoHeight;
                const context = canvas.getContext('2d'); if (!context) throw new Error(tr('video_studio.error.freeze_frame'));
                context.drawImage(video, 0, 0, canvas.width, canvas.height);
                const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
                if (!blob) throw new Error(tr('video_studio.error.freeze_frame'));
                const stem = String(source.name || clip.name || 'video').replace(/\.[^.]+$/, '').replace(/[\\/:*?"<>|]/g, '-').slice(0, 96) || 'video';
                const sourceFrame = this.composerFrameNumber(sourceTime);
                return new File([blob], `${stem}-F${sourceFrame}.png`, { type: 'image/png' });
            } finally { video.removeAttribute('src'); video.load(); }
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
                        source = await this.uploadComposerSource(file);
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
                    source = await this.uploadComposerSource(file);
                }
                const clip = this.composerProject.clips.find(item => item.id === clipId); if (!clip) return;
                this.composerPushHistory();
                if (!this.composerSources.some(item => item.id === source.id)) this.composerSources.push(source);
                clip.maskKind = 'image'; clip.maskSourceId = source.id;
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
            this.composerPushHistory(); clip.maskKind = 'image'; clip.maskSourceId = sourceId || null; this.composerChanged();
        },
        setComposerMaskKind(kind) {
            const clip = this.composerSelectedClip; if (!clip || !['none','image','person'].includes(kind)) return;
            this.composerPushHistory();
            if (clip.maskKind === 'person' && kind !== 'person') this.clearComposerDynamicMask(clip.id);
            if (kind === 'none') { clip.maskSourceId = null; clip.maskKind = 'image'; }
            else { if (clip.maskKind !== kind) clip.maskSourceId = null; clip.maskKind = kind; if (kind === 'person' && !clip.maskModelId) clip.maskModelId = 'apple.vision/person-segmentation'; }
            this.composerChanged();
        },
        async generateComposerPersonMask() {
            const selected = this.composerSelectedClip, source = this.composerSource(selected?.sourceId);
            if (!selected || !source?.hasVideo || this.composerPersonMaskBusy) return;
            this.composerPersonMaskBusy = true; this.icons();
            try {
                const payload = await responsePayload(await fetch(`${STUDIO_API}/composer/person-masks`, {
                    method: 'POST', credentials: 'same-origin', headers: { ...this.draftHeaders(), 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        sourceId: selected.sourceId, modelId: selected.maskModelId || 'apple.vision/person-segmentation',
                        promptFrame: Math.max(0, Math.round(Number(selected.maskPromptFrame)||0)),
                        promptX: selected.maskPromptX === null || selected.maskPromptX === undefined ? null : Number(selected.maskPromptX),
                        promptY: selected.maskPromptY === null || selected.maskPromptY === undefined ? null : Number(selected.maskPromptY),
                        threshold: Number(selected.maskThreshold)||.5, feather: Number(selected.maskFeather)||0,
                    }),
                }));
                const clip = this.composerProject.clips.find(item => item.id === selected.id); if (!clip) return;
                this.composerPushHistory();
                if (!this.composerSources.some(item => item.id === payload.source.id)) this.composerSources.push(payload.source);
                clip.maskKind = 'person'; clip.maskSourceId = payload.source.id;
                this.composerChanged(); this.syncComposerPreview();
                this.success(tr('video_studio.success.person_mask_generated'));
            } catch (error) { this.fail(error); }
            finally { this.composerPersonMaskBusy = false; this.icons(); }
        },
        setComposerCropInset(side, value) {
            const clip = this.composerSelectedClip;
            const fields = { left: ['cropLeft','cropRight'], right: ['cropRight','cropLeft'], top: ['cropTop','cropBottom'], bottom: ['cropBottom','cropTop'] };
            const pair = fields[side]; if (!clip || !pair) return;
            const opposite = Math.max(0, Math.min(95, Number(clip[pair[1]])||0));
            clip[pair[0]] = Math.max(0, Math.min(95, 99 - opposite, Number(value)||0));
            this.syncComposerPreview();
        },
        transformComposerCropState(state, transform = {}) {
            const left = Math.max(0, Math.min(95, Number(state.cropLeft)||0));
            const top = Math.max(0, Math.min(95, Number(state.cropTop)||0));
            const right = Math.max(0, Math.min(95, Number(state.cropRight)||0));
            const bottom = Math.max(0, Math.min(95, Number(state.cropBottom)||0));
            const width = Math.max(1, 100 - left - right), height = Math.max(1, 100 - top - bottom);
            const requestedFactor = Number.isFinite(Number(transform.factor)) ? Number(transform.factor) : 1;
            const minimumFactor = Math.max(1 / width, 1 / height);
            const maximumFactor = Math.min(100 / width, 100 / height);
            const factor = Math.max(minimumFactor, Math.min(maximumFactor, requestedFactor));
            const nextWidth = width * factor, nextHeight = height * factor;
            let centerX = left + width / 2 + (Number(transform.panX)||0);
            let centerY = top + height / 2 + (Number(transform.panY)||0);
            centerX = Math.max(nextWidth / 2, Math.min(100 - nextWidth / 2, centerX));
            centerY = Math.max(nextHeight / 2, Math.min(100 - nextHeight / 2, centerY));
            return {
                cropLeft: Math.max(0, centerX - nextWidth / 2),
                cropTop: Math.max(0, centerY - nextHeight / 2),
                cropRight: Math.max(0, 100 - centerX - nextWidth / 2),
                cropBottom: Math.max(0, 100 - centerY - nextHeight / 2),
                cropScale: Math.max(.01, Math.min(20, (Number(state.cropScale)||1) / factor)),
            };
        },
        applyComposerCropTransform(clip, transform, activeKeyframeId = '') {
            const active = activeKeyframeId ? clip.keyframes?.find(item => item.id === activeKeyframeId) : null;
            if (active) {
                Object.assign(active, this.transformComposerCropState(this.composerVisualStateAtFrame(clip, active.frame), transform));
                return;
            }
            const keyframeStates = new Map(this.composerClipKeyframes(clip).map(item => [item.id, this.composerVisualStateAtFrame(clip, item.frame)]));
            Object.assign(clip, this.transformComposerCropState(this.composerBaseVisualState(clip), transform));
            this.composerClipKeyframes(clip).forEach(item => {
                const hasCropValue = ['cropLeft','cropTop','cropRight','cropBottom','cropScale'].some(field => item[field] !== null && item[field] !== '' && item[field] !== undefined);
                if (hasCropValue) Object.assign(item, this.transformComposerCropState(keyframeStates.get(item.id), transform));
            });
        },
        handleComposerCropWheel(event, clip) {
            if (!(event.metaKey || event.ctrlKey) || this.composerTrack(clip.trackId)?.locked || !(this.composerSource(clip.sourceId)?.hasVideo || this.composerSource(clip.sourceId)?.hasImage)) return;
            event.preventDefault(); event.stopPropagation();
            this.selectComposerClip(clip, null, false); this.syncComposerKeyframeSelection();
            if (!this.composerCropWheelEditing) { this.composerPushHistory(); this.composerCropWheelEditing = true; }
            const activeId = this.composerKeyframeAtPlayhead(clip)?.id || '';
            const factor = Math.exp(Math.max(-120, Math.min(120, event.deltaY)) * .0018);
            this.applyComposerCropTransform(clip, { factor }, activeId);
            this.syncComposerPreview();
            if (this.composerCropWheelTimer) window.clearTimeout(this.composerCropWheelTimer);
            this.composerCropWheelTimer = window.setTimeout(() => {
                this.composerCropWheelTimer = 0; this.composerCropWheelEditing = false; this.composerChanged();
            }, 180);
        },
        beginComposerCropPan(event, clip, layer) {
            event.preventDefault(); event.stopPropagation();
            this.selectComposerClip(clip, null, false); this.syncComposerKeyframeSelection(); this.composerPushHistory();
            const activeId = this.composerKeyframeAtPlayhead(clip)?.id || '';
            const initial = this.composerVisualStateAt(clip), frame = layer.querySelector('.vs-composer-media-frame');
            const media = frame?.querySelector('img,video'), bounds = frame?.getBoundingClientRect();
            if (!frame || !media || !bounds?.width || !bounds?.height) return;
            const originX = event.clientX, originY = event.clientY;
            const visibleWidth = Math.max(1, 100 - initial.cropLeft - initial.cropRight);
            const visibleHeight = Math.max(1, 100 - initial.cropTop - initial.cropBottom);
            let transform = { panX: 0, panY: 0 }, next = initial;
            try { layer.setPointerCapture(event.pointerId); } catch (_) {}
            const move = current => {
                current.preventDefault();
                transform = {
                    panX: -(current.clientX - originX) / bounds.width * visibleWidth,
                    panY: -(current.clientY - originY) / bounds.height * visibleHeight,
                };
                next = { ...initial, ...this.transformComposerCropState(initial, transform) };
                frame.style.cssText = this.composerCropFrameStyle(clip, next);
                media.style.cssText = this.composerCropMediaStyle(clip, next);
            };
            const finish = () => {
                window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', finish); window.removeEventListener('pointercancel', finish);
                const target = this.composerProject.clips.find(item => item.id === clip.id);
                if (target) this.applyComposerCropTransform(target, transform, activeId);
                try { if (layer.hasPointerCapture(event.pointerId)) layer.releasePointerCapture(event.pointerId); } catch (_) {}
                this.composerChanged(); this.syncComposerPreview();
            };
            window.addEventListener('pointermove', move); window.addEventListener('pointerup', finish, { once: true }); window.addEventListener('pointercancel', finish, { once: true });
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
                id: composerId('clip'), layerType: 'media', sourceId: source.id, trackId: track.id, name: source.name,
                start, sourceStart: 0, duration: this.quantizeComposerTime(source.hasImage ? 1 : Math.max(this.composerFrameDuration, source.duration || 5), 1), speed: 1,
                volume: 1, fadeIn: 0, fadeOut: 0, x: 0, y: 0,
                width: visual ? Math.round((source.width || settings.width) * scale) : null,
                height: visual ? Math.round((source.height || settings.height) * scale) : null,
                opacity: 1, scale: 1, audioEnabled: true, groupId: null,
                maskSourceId: null, maskKind: 'image', maskModelId: 'apple.vision/person-segmentation',
                maskPromptFrame: 0, maskPromptX: null, maskPromptY: null, maskThreshold: .5, maskFeather: 1.5,
                cropLeft: 0, cropTop: 0, cropRight: 0, cropBottom: 0,
                cropShape: 'rectangle', cropCornerRadius: 32, cropFeather: 0, cropScale: scale, cropViewportVersion: 2,
                color: COMPOSER_CLIP_COLORS[this.composerProject.clips.length % COMPOSER_CLIP_COLORS.length],
                keyframes: [],
            };
            this.insertComposerClip(clip); this.composerProject.clips.push(clip); this.setComposerSelection([clip.id], clip.id); this.composerChanged();
            return clip;
        },
        addComposerSpecialLayer(layerType) {
            if (!['spotlight', 'text'].includes(layerType)) return;
            const track = this.composerSelectedTrack;
            if (!track || track.kind !== 'video' || track.locked) return;
            this.composerPushHistory();
            const settings = this.composerProject.settings, start = this.quantizeComposerTime(this.composerPlayhead);
            const clip = {
                id: composerId('clip'), layerType, sourceId: null, trackId: track.id,
                name: tr(layerType === 'spotlight' ? 'video_studio.composer.spotlight_layer' : 'video_studio.composer.text_layer'), start, sourceStart: 0, duration: this.quantizeComposerTime(3, 2), speed: 1,
                volume: 0, fadeIn: 0, fadeOut: 0,
                x: layerType === 'text' ? Math.round(settings.width / 2) : Math.round(settings.width * .25),
                y: layerType === 'text' ? Math.round(settings.height / 2) : Math.round(settings.height * .25),
                width: Math.round(settings.width * .5), height: Math.round(settings.height * (layerType === 'text' ? .18 : .5)),
                opacity: 1, scale: 1, audioEnabled: false, groupId: null, maskSourceId: null,
                maskKind: 'image', maskModelId: 'apple.vision/person-segmentation', maskPromptFrame: 0,
                maskPromptX: null, maskPromptY: null, maskThreshold: .5, maskFeather: 1.5,
                color: layerType === 'spotlight' ? '#334155' : '#9333ea', keyframes: [],
                spotlightShape: 'rounded', dimOpacity: .65, feather: 24, cornerRadius: 32,
                text: tr('video_studio.composer.text_default'), fontSize: 64, textColor: '#ffffff', textAnchor: 'center', reveal: false, revealSpeed: 12,
                textBold: false, textItalic: false, textUnderline: false, textStrikethrough: false,
                textStrokeEnabled: false, textStrokeWidth: 2, textStrokeColor: '#000000', textStrokeStyle: 'solid',
                textShadowEnabled: false, textShadowColor: '#000000', textShadowOpacity: .5, textShadowBlur: 12, textShadowOffsetX: 8, textShadowOffsetY: 8,
            };
            this.insertComposerClip(clip); this.composerProject.clips.push(clip); this.setComposerSelection([clip.id], clip.id);
            this.composerPlayhead = start; this.composerChanged(); this.syncComposerPreview();
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
            const cropState = this.composerVisualStateAt(clip);
            const cropWidth = Math.max(.01, 1 - (Number(cropState.cropLeft)||0) / 100 - (Number(cropState.cropRight)||0) / 100);
            const cropHeight = Math.max(.01, 1 - (Number(cropState.cropTop)||0) / 100 - (Number(cropState.cropBottom)||0) / 100);
            const naturalWidth = Math.max(16, Math.round(source.width * cropWidth));
            const naturalHeight = Math.max(16, Math.round(source.height * cropHeight));
            this.composerPushHistory(); const keyframe = this.composerKeyframeAtPlayhead(clip);
            if (keyframe) { keyframe.width = naturalWidth; keyframe.height = naturalHeight; }
            else { const state = this.composerBaseVisualState(clip); this.resizeComposerClipVisual(clip, naturalWidth, naturalHeight, state.width, state.height); }
            this.composerChanged();
        },
        translateComposerClipVisual(clip, dx, dy) {
            clip.x = Math.round((Number(clip.x) || 0) + dx); clip.y = Math.round((Number(clip.y) || 0) + dy);
            this.composerClipKeyframes(clip).forEach(keyframe => {
                if (keyframe.x !== null && keyframe.x !== '' && keyframe.x !== undefined) keyframe.x = Math.round(Number(keyframe.x) + dx);
                if (keyframe.y !== null && keyframe.y !== '' && keyframe.y !== undefined) keyframe.y = Math.round(Number(keyframe.y) + dy);
            });
        },
        resizeComposerClipVisual(clip, nextWidth, nextHeight, previousWidth, previousHeight, scaleCrop = true) {
            const scaleX = nextWidth / Math.max(1, previousWidth), scaleY = nextHeight / Math.max(1, previousHeight);
            clip.width = Math.max(16, Math.round(nextWidth)); clip.height = Math.max(16, Math.round(nextHeight));
            const cropFactor = Math.max(.01, Math.min(scaleX, scaleY));
            if (scaleCrop) clip.cropScale = Math.max(.01, Math.min(20, (Number(clip.cropScale)||1) * cropFactor));
            this.composerClipKeyframes(clip).forEach(keyframe => {
                if (keyframe.width !== null && keyframe.width !== '' && keyframe.width !== undefined) keyframe.width = Math.max(16, Math.round(Number(keyframe.width) * scaleX));
                if (keyframe.height !== null && keyframe.height !== '' && keyframe.height !== undefined) keyframe.height = Math.max(16, Math.round(Number(keyframe.height) * scaleY));
                if (scaleCrop && keyframe.cropScale !== null && keyframe.cropScale !== '' && keyframe.cropScale !== undefined) keyframe.cropScale = Math.max(.01, Math.min(20, Number(keyframe.cropScale) * cropFactor));
            });
            const source = this.composerSource(clip.sourceId);
            if (!scaleCrop && (source?.hasVideo || source?.hasImage)) {
                Object.assign(clip, this.composerCropInsetsForViewport(this.composerBaseVisualState(clip), clip.width, clip.height, source));
                this.composerClipKeyframes(clip).forEach(keyframe => {
                    const hasOwnViewport = ['width','height','cropLeft','cropTop','cropRight','cropBottom','cropScale'].some(field => keyframe[field] !== null && keyframe[field] !== '' && keyframe[field] !== undefined);
                    if (!hasOwnViewport) return;
                    const state = this.composerVisualStateAtFrame(clip, keyframe.frame);
                    Object.assign(keyframe, this.composerCropInsetsForViewport(state, state.width, state.height, source));
                });
            }
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
        addComposerTrack(kind = 'video', recordHistory = true, relativeTrackId = '', placement = 'after') {
            if (recordHistory) this.composerPushHistory();
            const count = this.composerProject.tracks.filter(track => track.kind === kind).length + 1;
            const track = { id: composerId('track'), kind, name: `${kind === 'video' ? 'Video' : 'Audio'} ${count}`, order: this.composerProject.tracks.length, muted: false, locked: false };
            const selectedTrackId = relativeTrackId || this.composerSelectedTrack?.id;
            const selectedIndex = this.composerProject.tracks.findIndex(item => item.id === selectedTrackId);
            const insertionIndex = selectedIndex < 0 ? this.composerProject.tracks.length : selectedIndex + (placement === 'before' ? 0 : 1);
            this.composerProject.tracks.splice(insertionIndex, 0, track);
            this.composerProject.tracks.forEach((item, index) => { item.order = index; });
            this.composerSelectedTrackId = track.id;
            if (recordHistory) this.composerChanged(); return track;
        },
        closeComposerAddMenus() {
            this.composerTrackMenuOpen = false; this.composerItemMenuOpen = false;
            this.composerTrackMenuStep = 'type'; this.composerTrackInsertSide = 'after';
        },
        toggleComposerTrackMenu() {
            this.composerTrackMenuOpen = !this.composerTrackMenuOpen; this.composerItemMenuOpen = false;
            this.composerTrackMenuStep = 'type'; this.composerTrackInsertSide = 'after';
        },
        openComposerTrackContextMenu() {
            this.composerTrackMenuOpen = true; this.composerItemMenuOpen = false;
            this.composerTrackMenuStep = 'position'; this.composerTrackInsertSide = 'after';
        },
        chooseComposerTrackInsertSide(side) {
            this.composerTrackInsertSide = side === 'before' ? 'before' : 'after';
            this.composerTrackMenuStep = 'type';
        },
        toggleComposerItemMenu() {
            if (!this.composerCanAddProjectItem) return;
            this.composerItemMenuOpen = !this.composerItemMenuOpen; this.composerTrackMenuOpen = false;
        },
        addComposerTrackFromMenu(kind) {
            this.addComposerTrack(kind, true, this.composerSelectedTrack?.id || '', this.composerTrackInsertSide);
            this.closeComposerAddMenus();
        },
        addComposerItemFromMenu(layerType) { this.addComposerSpecialLayer(layerType); this.closeComposerAddMenus(); },
        isComposerTrackSelected(track) { return this.composerSelectedTrack?.id === track?.id; },
        selectComposerTrack(track) {
            if (!track) return;
            this.composerSelectedTrackId = track.id; this.setComposerSelection([], ''); this.closeComposerAddMenus();
        },
        removeComposerTrack(track) {
            if (this.composerProject.tracks.length <= 1) return;
            const clipCount = this.composerProject.clips.filter(clip => clip.trackId === track.id).length;
            if (clipCount && !window.confirm(tr('video_studio.composer.confirm_remove_track', { name: track.name, count: clipCount }))) return;
            this.composerPushHistory();
            const ids = new Set(this.composerProject.clips.filter(clip => clip.trackId === track.id).map(clip => clip.id));
            const removedIndex = this.composerProject.tracks.findIndex(item => item.id === track.id);
            this.composerProject.tracks = this.composerProject.tracks.filter(item => item.id !== track.id);
            this.composerProject.clips = this.composerProject.clips.filter(clip => clip.trackId !== track.id);
            if (this.composerSelectedClipIds.some(id => ids.has(id))) this.setComposerSelection([], '');
            if (this.composerSelectedTrackId === track.id) this.composerSelectedTrackId = this.composerProject.tracks[Math.max(0, removedIndex - 1)]?.id || '';
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
            this.composerSelectedTrackId = clip.trackId;
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
            const keyframe = { id: composerId('keyframe'), frame, endpoint: null, transition: 'linear', x: Math.round(state.x), y: Math.round(state.y), width: Math.max(16, Math.round(state.width)), height: Math.max(16, Math.round(state.height)), opacity: Math.max(0, Math.min(1, state.opacity)), scale: state.scale, cropLeft: state.cropLeft, cropTop: state.cropTop, cropRight: state.cropRight, cropBottom: state.cropBottom, cropShape: state.cropShape, cropCornerRadius: Math.round(state.cropCornerRadius), cropFeather: Math.round(state.cropFeather), cropScale: state.cropScale };
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
            const makeEndpoint = (endpoint, frame, value) => endpoint === 'end'
                ? { id: composerId('keyframe'), frame, endpoint, transition: 'linear', x: null, y: null, width: null, height: null, opacity: null, scale: null, cropLeft: null, cropTop: null, cropRight: null, cropBottom: null, cropShape: null, cropCornerRadius: null, cropFeather: null, cropScale: null }
                : { id: composerId('keyframe'), frame, endpoint, transition: 'hold', x: Math.round(value.x), y: Math.round(value.y), width: Math.max(16, Math.round(value.width)), height: Math.max(16, Math.round(value.height)), opacity: Math.max(0, Math.min(1, value.opacity)), scale: value.scale, cropLeft: value.cropLeft, cropTop: value.cropTop, cropRight: value.cropRight, cropBottom: value.cropBottom, cropShape: value.cropShape, cropCornerRadius: Math.round(value.cropCornerRadius), cropFeather: Math.round(value.cropFeather), cropScale: value.cropScale };
            const middle = this.composerClipKeyframes(clip).filter(keyframe => !this.composerIsEndpointKeyframe(keyframe));
            const left = [makeEndpoint('start', 0, this.composerVisualStateAtFrame(clip, 0)), ...middle.filter(keyframe => keyframe.frame < splitFrame), makeEndpoint('end', splitFrame - 1, leftEndState)];
            const durationFrames = this.composerFrameNumber(clip.duration), rightDuration = durationFrames - splitFrame;
            const right = [makeEndpoint('start', 0, state), ...middle.filter(keyframe => keyframe.frame > splitFrame).map(keyframe => ({ ...keyframe, id: composerId('keyframe'), frame: keyframe.frame - splitFrame })), makeEndpoint('end', rightDuration - 1, this.composerVisualStateAtFrame(clip, durationFrames - 1))];
            return { state, left, right };
        },
        async insertComposerFreezeFrame() {
            if (!this.composerCanFreezeFrame || this.composerFreezeBusy) return;
            const selected = this.composerSelectedClip, selectedId = selected.id, source = this.composerSource(selected.sourceId);
            const splitAt = this.quantizeComposerTime(Math.max(selected.start, Math.min(selected.start + selected.duration, this.composerPlayhead)));
            const sourceTime = Math.max(0, Number(selected.sourceStart || 0) + (splitAt - selected.start) * (Number(selected.speed) || 1));
            this.composerFreezeBusy = true; this.icons();
            try {
                const file = await this.captureComposerVideoFrame(selected, source, sourceTime);
                const stillSource = await this.uploadComposerSource(file);
                const clip = this.composerProject.clips.find(item => item.id === selectedId);
                if (!clip || this.composerTrack(clip.trackId)?.locked) throw new Error(tr('video_studio.error.freeze_frame'));
                const at = this.quantizeComposerTime(Math.max(clip.start, Math.min(clip.start + clip.duration, splitAt)));
                const offset = this.quantizeComposerTime(at - clip.start), duration = this.quantizeComposerTime(2, 1);
                const durationFrames = Math.max(1, this.composerFrameNumber(clip.duration));
                const visualFrame = Math.max(0, Math.min(durationFrames - 1, this.composerFrameNumber(offset)));
                const visual = this.composerVisualStateAtFrame(clip, visualFrame);
                this.composerPushHistory();
                if (!this.composerSources.some(item => item.id === stillSource.id)) this.composerSources.push(stillSource);
                this.composerTrackClips(clip.trackId).filter(item => item.id !== clip.id && item.start >= at - COMPOSER_TIME_EPSILON).forEach(item => { item.start = this.quantizeComposerTime(item.start + duration); });
                let right = null;
                if (offset >= this.composerFrameDuration && offset <= clip.duration - this.composerFrameDuration) {
                    const keyframes = this.splitComposerKeyframes(clip, this.composerFrameNumber(offset));
                    right = { ...clip, id: composerId('clip'), start: at + duration, sourceStart: clip.sourceStart + offset * clip.speed, duration: this.quantizeComposerTime(clip.duration - offset, 1), fadeIn: 0, keyframes: keyframes.right, ...keyframes.state };
                    clip.duration = offset; clip.fadeOut = 0; clip.keyframes = keyframes.left;
                } else if (offset < this.composerFrameDuration) clip.start = this.quantizeComposerTime(clip.start + duration);
                const freeze = {
                    id: composerId('clip'), layerType: 'media', sourceId: stillSource.id, trackId: clip.trackId,
                    name: tr('video_studio.composer.freeze_frame_name', { name: clip.name }), start: at, sourceStart: 0, duration, speed: 1,
                    volume: 0, fadeIn: 0, fadeOut: 0, x: Math.round(visual.x), y: Math.round(visual.y),
                    width: Math.max(16, Math.round(visual.width)), height: Math.max(16, Math.round(visual.height)),
                    opacity: Math.max(0, Math.min(1, visual.opacity)), scale: visual.scale, audioEnabled: false, groupId: null,
                    maskSourceId: clip.maskSourceId || null, maskKind: clip.maskKind || 'image',
                    maskModelId: clip.maskModelId || 'apple.vision/person-segmentation',
                    maskPromptFrame: clip.maskPromptFrame || 0, maskPromptX: clip.maskPromptX ?? null,
                    maskPromptY: clip.maskPromptY ?? null, maskThreshold: clip.maskThreshold || .5,
                    maskFeather: clip.maskFeather ?? 1.5,
                    cropLeft: visual.cropLeft, cropTop: visual.cropTop, cropRight: visual.cropRight, cropBottom: visual.cropBottom,
                    cropShape: visual.cropShape, cropCornerRadius: Math.round(visual.cropCornerRadius), cropFeather: Math.round(visual.cropFeather), cropScale: visual.cropScale,
                    color: COMPOSER_CLIP_COLORS[this.composerProject.clips.length % COMPOSER_CLIP_COLORS.length], keyframes: [],
                };
                if (right) this.composerProject.clips.push(right);
                this.composerProject.clips.push(freeze); this.composerSelectedKeyframeId = '';
                this.setComposerSelection([freeze.id], freeze.id); this.composerPlayhead = at; this.composerChanged(); this.syncComposerPreview();
                this.success(tr('video_studio.success.freeze_frame_inserted'));
            } catch (error) { this.fail(error); }
            finally { this.composerFreezeBusy = false; this.icons(); }
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
            const speed = Math.max(COMPOSER_MIN_SPEED, Math.min(COMPOSER_MAX_SPEED, Number(desiredSpeed) || 1));
            const oldSpeed = Math.max(COMPOSER_MIN_SPEED, Math.min(COMPOSER_MAX_SPEED, Number(clip.speed) || 1));
            const sourceSpan = clip.duration * oldSpeed;
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
                element.style.width = `${Math.max(this.composerClipMinimumWidth, nextDuration * this.composerScale)}px`;
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
            const layer = event.currentTarget;
            if ((event.metaKey || event.ctrlKey) && (this.composerSource(clip.sourceId)?.hasVideo || this.composerSource(clip.sourceId)?.hasImage)) {
                this.beginComposerCropPan(event, clip, layer); return;
            }
            event.preventDefault();
            const stage = layer.closest('.vs-composer-stage'), bounds = stage.getBoundingClientRect();
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
            // Cmd/Ctrl and Shift select resize behavior here; they must not
            // toggle timeline selection and hide the selected-layer frame.
            this.selectComposerClip(clip, null, false); this.syncComposerKeyframeSelection(); this.composerPushHistory();
            try { layer.setPointerCapture(event.pointerId); } catch (_) {}
            const settings = this.composerProject.settings, canvasWidth = settings.width, canvasHeight = settings.height;
            const activeKeyframe = this.composerKeyframeAtPlayhead(clip), activeKeyframeId = activeKeyframe?.id || '';
            const visual = this.composerVisualStateAt(clip), originX = event.clientX, originY = event.clientY, width = visual.width || canvasWidth, height = visual.height || canvasHeight;
            const source = this.composerSource(clip.sourceId), textLayer = clip.layerType === 'text';
            const aspectLocked = clip.layerType === 'media' && Boolean(source?.hasVideo || source?.hasImage);
            const preserveCropScale = aspectLocked && (event.metaKey || event.ctrlKey);
            const sourceAspect = Math.max(.01, Number(source?.width)||width) / Math.max(.01, Number(source?.height)||height);
            const originalScale = visual.scale || 1;
            const originalCropScale = Math.max(.01, Math.min(20, Number(visual.cropScale)||1));
            let nextWidth = width, nextHeight = height, nextScale = originalScale, nextCropScale = originalCropScale;
            let nextCropRight = Number(visual.cropRight)||0, nextCropBottom = Number(visual.cropBottom)||0;
            const move = current => {
                current.preventDefault();
                if (textLayer) {
                    const delta = (current.clientX - originX) / Math.max(80, bounds.width);
                    nextScale = Math.max(.05, Math.min(20, originalScale * (1 + delta * 2)));
                    layer.style.transform = `${this.composerTextAnchorTransform(clip.textAnchor)} scale(${nextScale})`;
                    return;
                }
                const deltaX = (current.clientX - originX) / bounds.width * canvasWidth;
                const deltaY = (current.clientY - originY) / bounds.height * canvasHeight;
                const maximumWidth = Math.max(16, canvasWidth - visual.x), maximumHeight = Math.max(16, canvasHeight - visual.y);
                if (aspectLocked && !preserveCropScale && !current.shiftKey) {
                    const horizontal = Math.abs(deltaX / Math.max(1, width)) >= Math.abs(deltaY / Math.max(1, height));
                    const desiredWidth = horizontal ? width + deltaX : (height + deltaY) * sourceAspect;
                    const minimumWidth = Math.max(16, 16 * sourceAspect);
                    const maximumLockedWidth = Math.min(maximumWidth, maximumHeight * sourceAspect);
                    const effectiveMaximumWidth = Math.max(minimumWidth, maximumLockedWidth);
                    nextWidth = Math.round(Math.max(minimumWidth, Math.min(effectiveMaximumWidth, desiredWidth)));
                    nextHeight = Math.round(nextWidth / sourceAspect);
                } else {
                    nextWidth = Math.round(Math.max(16, Math.min(maximumWidth, width + deltaX)));
                    nextHeight = Math.round(Math.max(16, Math.min(maximumHeight, height + deltaY)));
                }
                if (aspectLocked && !preserveCropScale) nextCropScale = Math.max(.01, Math.min(20, originalCropScale * Math.min(nextWidth / Math.max(1,width), nextHeight / Math.max(1,height))));
                if (preserveCropScale) {
                    const insets = this.composerCropInsetsForViewport(visual, nextWidth, nextHeight, source);
                    nextCropRight = insets.cropRight; nextCropBottom = insets.cropBottom;
                }
                layer.style.width = `${nextWidth / canvasWidth * 100}%`;
                layer.style.height = `${nextHeight / canvasHeight * 100}%`;
                if (aspectLocked) {
                    const liveState = { ...visual, width: nextWidth, height: nextHeight, cropScale: nextCropScale, cropRight: nextCropRight, cropBottom: nextCropBottom };
                    const geometry = this.composerCropFrameGeometry(clip, liveState);
                    layer.style.setProperty('--media-frame-left', `${geometry.left}%`);
                    layer.style.setProperty('--media-frame-top', `${geometry.top}%`);
                    layer.style.setProperty('--media-frame-width', `${geometry.width}%`);
                    layer.style.setProperty('--media-frame-height', `${geometry.height}%`);
                    layer.style.setProperty('--media-frame-radius', geometry.radius);
                    const frame = layer.querySelector('.vs-composer-media-frame'), media = frame?.querySelector('img,video');
                    if (frame) frame.style.cssText = this.composerCropFrameStyle(clip, liveState);
                    if (media) media.style.cssText = this.composerCropMediaStyle(clip, liveState);
                }
            };
            const finish = () => {
                window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', finish); window.removeEventListener('pointercancel', finish);
                const targetClip = this.composerProject.clips.find(item => item.id === clip.id);
                if (targetClip) {
                    const keyframe = activeKeyframeId ? targetClip.keyframes?.find(item => item.id === activeKeyframeId) : null;
                    if (textLayer && keyframe) keyframe.scale = nextScale;
                    else if (textLayer) {
                        const factor = nextScale / Math.max(.05, originalScale);
                        targetClip.scale = Math.max(.05, Math.min(20, (Number(targetClip.scale) || 1) * factor));
                        this.composerClipKeyframes(targetClip).forEach(item => { if (item.scale !== null && item.scale !== '' && item.scale !== undefined) item.scale = Math.max(.05, Math.min(20, Number(item.scale) * factor)); });
                    }
                    else if (keyframe) {
                        keyframe.width = nextWidth; keyframe.height = nextHeight;
                        if (preserveCropScale) { keyframe.cropRight = nextCropRight; keyframe.cropBottom = nextCropBottom; }
                        else keyframe.cropScale = nextCropScale;
                    }
                    else this.resizeComposerClipVisual(targetClip, nextWidth, nextHeight, width, height, !preserveCropScale);
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
                    const active = this.composerClipActiveAtPlayhead(clip);
                    const target = clip.sourceStart + Math.max(0, this.composerPlayhead - clip.start) * clip.speed;
                    const elapsed = Math.max(0, this.composerPlayhead - clip.start), remaining = Math.max(0, clip.duration - elapsed);
                    const fade = Math.min(clip.fadeIn ? elapsed / clip.fadeIn : 1, clip.fadeOut ? remaining / clip.fadeOut : 1, 1);
                    media.playbackRate = clip.speed; media.volume = Math.min(1, clip.volume * Math.max(0, fade));
                    if (Math.abs((media.currentTime || 0) - target) > .2) media.currentTime = target;
                    if (this.composerPlaying && active) media.play().catch(() => {}); else media.pause();
                });
                document.querySelectorAll('.vs-composer-stage video[data-mask-clip-id]').forEach(media => {
                    const clip = this.composerProject.clips.find(item => item.id === media.dataset.maskClipId); if (!clip) return;
                    const active = this.composerClipActiveAtPlayhead(clip);
                    const target = clip.sourceStart + Math.max(0, this.composerPlayhead - clip.start) * clip.speed;
                    media.playbackRate = clip.speed;
                    if (Math.abs((media.currentTime || 0) - target) > .04) media.currentTime = target;
                    if (this.composerPlaying && active) media.play().catch(() => {}); else { media.pause(); this.updateComposerDynamicMask(media); }
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
            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') { event.preventDefault(); event.shiftKey ? this.saveComposerDocumentAs() : this.saveComposerDocument(); return; }
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
        composerRunDetail(run) {
            const detail = String(run?.steps?.[0]?.detail || '');
            const match = /^composer\.rendering:([0-9.]+):([0-9.]+)$/.exec(detail);
            if (!match) return detail;
            const format = value => {
                const seconds = Math.max(0, Number(value) || 0);
                return seconds >= 100 ? seconds.toFixed(0) : seconds.toFixed(1);
            };
            return tr('video_studio.composer.render_progress', { current: format(match[1]), total: format(match[2]) });
        },
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
            const speed = text.match(/(?:速度|速率|speed)[^0-9]*(\d+(?:\.\d+)?)/i);
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
            const numberRanges = { start: [0, 3600], duration: [.1, 3600], speed: [COMPOSER_MIN_SPEED, COMPOSER_MAX_SPEED], volume: [0, 4], fadeIn: [0, 30], fadeOut: [0, 30], x: [-3840, 3840], y: [-2160, 2160], width: [16, 3840], height: [16, 2160], opacity: [0, 1] };
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

        async loadUpscalingModels() {
            const result = await responsePayload(await fetch(`${STUDIO_API}/upscaling/models`, {
                credentials: 'same-origin', headers: this.draftHeaders(), cache: 'no-store',
            }));
            this.upscalingModels = result.items || [];
            if (!this.upscalingModels.some(item => item.id === this.upscalingModelId)) {
                this.upscalingModelId = this.upscalingModels.find(item => item.ready)?.id || this.upscalingModels[0]?.id || '';
            }
            this.icons();
        },
        selectUpscalingFile(file) {
            if (!file || !file.size || file.size > 1024 * 1024 * 1024 ||
                !(String(file.type).startsWith('video/') ||
                  ((!file.type || file.type === 'application/octet-stream') && /\.(mp4|mov|m4v|mkv|webm|avi)$/i.test(file.name)))) {
                throw new Error(tr('video_studio.upscale.invalid_file'));
            }
            this.upscalingFile = file;
            this.icons();
        },
        chooseUpscalingFile(event) {
            try { if (event.target.files?.[0]) this.selectUpscalingFile(event.target.files[0]); }
            catch (error) { this.fail(error); }
        },
        onUpscalingModelSelect(select) {
            if (select.value === UPSCALING_INSTALL_MODEL_ID) {
                select.value = this.upscalingModelId || '';
                void this.installUpscalingModel();
            } else if (this.upscalingModels.some(item => item.id === select.value)) {
                this.upscalingModelId = select.value;
                this.icons();
            }
        },
        async installUpscalingModel() {
            if (this.upscalingInstalling) return;
            const previous = this.upscalingModelId;
            this.upscalingInstalling = true;
            try {
                const result = await window.AI2AppsCapabilities.ensure({
                    appId: APP_ID, capability: 'video.upscaling', actionId: 'install-video-upscaling-model',
                    requirements: { operations: ['video_upscaling'], outputFormats: ['mp4'] },
                    intent: { returnTo: `/apps/${APP_ID}`, completionPolicy: 'configure_only' },
                }, { installMore: true });
                await this.loadUpscalingModels();
                if (result?.outcome === 'configured') {
                    this.upscalingModelId = this.upscalingModels.find(item => item.id === previous && item.ready)?.id
                        || this.upscalingModels.find(item => item.ready)?.id || previous;
                } else this.upscalingModelId = previous;
                if (result?.outcome === 'configured') this.success(tr('video_studio.success.models_refreshed'));
            } catch (error) { this.upscalingModelId = previous; this.fail(error); }
            finally { this.upscalingInstalling = false; this.icons(); }
        },
        async startUpscaling() {
            if (this.upscalingSubmitting || !this.canGenerate) return;
            const seed = Number(this.upscalingSeed);
            if (!Number.isInteger(seed) || seed < 0 || seed > 0xFFFFFFFF) { this.fail(new Error(tr('video_studio.upscale.invalid_seed'))); return; }
            this.upscalingSubmitting = true;
            try {
                const form = new FormData();
                form.append('file', this.upscalingFile, this.upscalingFile.name);
                form.append('model_id', this.upscalingModelId);
                form.append('seed', String(seed));
                form.append('prompt', this.selectedUpscalingModel?.customPrompt ? this.upscalingPrompt.trim() : '');
                const job = await responsePayload(await fetch(`${STUDIO_API}/upscaling/jobs`, {
                    method: 'POST', credentials: 'same-origin', headers: this.draftHeaders(), body: form,
                }));
                this.selectedUpscalingRunId = job.id;
                this.rightCollapsed = false;
                await this.refresh();
                this.success(tr('video_studio.upscale.started'));
            } catch (error) { this.fail(error); }
            finally { this.upscalingSubmitting = false; this.icons(); }
        },
        async changeUpscalingJob(run, action) {
            if (!run?.id) return;
            try {
                const job = await responsePayload(await fetch(`${STUDIO_API}/upscaling/jobs/${encodeURIComponent(run.id)}/${action}`, {
                    method: 'POST', credentials: 'same-origin', headers: this.draftHeaders(),
                }));
                if (action === 'retry') this.selectedUpscalingRunId = job.id;
                await this.refresh();
            } catch (error) { this.fail(error); }
        },

        async extractAudio(retryOf = null) {
            if (!(this.extractAsset?.id || this.extractAsset?.nativePath) || this.extractSubmitting) return;
            this.extractSubmitting = true; this.clearNotice();
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
            this.submitting = true; this.clearNotice();
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
        taskMenu(event, task, kind) { window.AI2AppsStudioTaskMenu.open(event,{disabled:!['draft','succeeded','failed','cancelled','expired'].includes(task.status),onDelete:()=>this.deleteHistoryTask(task,kind)}); },
        async deleteHistoryTask(task,kind) {
            try {
                await responsePayload(await fetch(`${STUDIO_API}/${kind}/${encodeURIComponent(task.id)}`,{method:'DELETE',credentials:'same-origin',headers:this.draftHeaders()}));
                if(kind==='tasks'&&this.selectedTaskId===task.id)this.joinedVideoUrl='';
                await this.refresh();
            }catch(error){this.fail(error);}
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
