(function () {
    'use strict';
    const API = '/v1/platform/readaloud';
    const APP_ID = 'ai2apps.readaloud';
    const GALLERY_MINI_FALLBACK_URL = '/admin/app-content/ai2apps.gallery?surface=mini';
    const FALLBACK_MINI_APPS = Object.freeze([
        Object.freeze({ id: 'ai2apps.audio.quick-read', mode: 'quick', key: 'readaloud.pipeline.quick', capability: 'audio.speech_generation', icon: 'volume-2' }),
        Object.freeze({ id: 'ai2apps.audio.audiobook', mode: 'audiobook', key: 'readaloud.pipeline.audiobook', capability: 'audio.speech_generation', icon: 'book-headphones' }),
        Object.freeze({ id: 'ai2apps.audio.ensemble-drama', mode: 'drama', key: 'readaloud.pipeline.drama', capability: 'audio.speech_generation', icon: 'users-round' }),
        Object.freeze({ id: 'ai2apps.audio.voice-design', mode: 'voice', key: 'readaloud.pipeline.voice', capability: 'audio.voice_clone', icon: 'audio-waveform' }),
        Object.freeze({ id: 'ai2apps.audio.character-training', mode: 'training', key: 'readaloud.pipeline.training', capability: 'audio.voice_clone', icon: 'mic-2' }),
    ]);

    function tr(key, values = {}) {
        let text = typeof window.t === 'function' ? window.t(key) : key;
        Object.entries(values).forEach(([name, value]) => { text = text.replaceAll(`{${name}}`, String(value)); });
        return text;
    }
    function galleryHostUnavailable(error) {
        return /AI2Apps Host did not respond|Unsupported host mount/i.test(String(error?.message || error || ''));
    }
    function localizedMiniApp(item) {
        if (item.source === 'package') return {
            ...item, mode: `package:${item.id}`, capability: item.requirements?.capabilities?.[0] || '', icon: item.icon || 'blocks',
            name: item.name || item.title || item.id,
            summary: item.summary || item.description || item.provider?.name || 'Installed Package',
            description: item.description || item.summary || item.provider?.name || '',
        };
        const key = item.key || item.title_key?.replace(/\.name$/, '') || 'readaloud.pipeline.quick';
        const capability = item.capability || item.requirements?.capabilities?.[0] || 'audio.speech_generation';
        const value = (candidate, fallback) => { const translated = tr(candidate); return translated === candidate ? tr(fallback) : translated; };
        return { ...item, key, capability, name: value(item.title_key || `${key}.name`, `${key}.name`), summary: value(item.summary_key || `${key}.summary`, `${key}.summary`), description: value(item.description_key || `${key}.description`, `${key}.description`) };
    }
    function appInstanceId() {
        return window.AI2AppsCapabilities?.appInstanceId?.()
            || document.querySelector('[data-app-instance-id]')?.dataset?.appInstanceId
            || '';
    }
    async function request(path, options) {
        const response = await fetch(API + path, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json', ...(appInstanceId() ? { 'X-AI2Apps-App-Instance': appInstanceId() } : {}), ...(options?.body ? { 'Content-Type': 'application/json' } : {}) },
            ...(options || {}), body: options?.body ? JSON.stringify(options.body) : undefined,
        });
        const payload = await response.json().catch(() => null);
        if (!response.ok) throw new Error(payload?.error?.message || payload?.detail?.message || payload?.detail || tr('readaloud.error.request', { status: response.status }));
        return payload;
    }

    window.readAloudApp = function () { return {
        busy: false, notice: '', noticeTone: '', leftView: 'mini-apps', pipelineMode: 'quick', tab: 'script',
        miniAppDefinitions: [], runs: [], selectedRunId: '', selectedArtifactId: '', runTimer: null, draftTimer: null,
        packageMiniAppId: '', packageMiniAppUrl: '', packageMiniAppMountId: '', packageMiniAppLoading: false, packageMiniAppError: '', packageMiniAppReadiness: {}, packageMiniAppSetupBusy: false,
        leftCollapsed: false, rightCollapsed: false, mobilePanel: 'create',
        projects: [], selected: null, selectedProjectId: '', providers: [], voiceProfiles: [], selectedTtsModel: '',
        previewing: '', configuringSpeech: false, configuringVoice: false, currentAudioUrl: '', currentAudioTitle: '', previewHistory: [],
        transcribingTraining: false, savingTraining: false, recordingTraining: false, trainingAudioUrl: '', trainingRecorder: null, trainingStream: null, trainingChunks: [],
        capabilityProbes: {},
        galleryMiniUrl: '', galleryMiniMountId: '', galleryMiniLoading: false, galleryMiniError: '',
        chatController: null, chatMiniUrl: '', packageChatBridge: null,
        showProjectForm: false, showCharacterForm: false, showSegmentForm: false, showVoiceForm: false,
        projectForm: { title: '', purpose: 'private', sourceRights: 'user_owned', sourceText: '' },
        characterForm: { name: '', description: '', voiceProfileId: '' },
        segmentForm: { speakerId: '', text: '', emotion: 'neutral', emotionStrength: 1, speed: 1, pauseAfterMs: 300 },
        voiceForm: { name: '', sourceType: 'synthetic_designed', modelId: '', providerVoiceId: '', referenceTranscript: '', consentConfirmed: false, usageRightsConfirmed: false, antiImpersonationAcknowledged: false },
        trainingForm: { name: '', sourceType: 'self_voice', referenceTranscript: '', audioFile: null, assetId: '', resourceHandle: '', assetName: '', mediaType: '', consentConfirmed: false, usageRightsConfirmed: false, antiImpersonationAcknowledged: false },
        tr,
        get miniApps() { return (this.miniAppDefinitions.length ? this.miniAppDefinitions : FALLBACK_MINI_APPS).map(localizedMiniApp); },
        get currentMiniApp() { return this.packageMiniAppId ? (this.miniApps.find(item => item.id === this.packageMiniAppId) || this.miniApps[0]) : (this.miniApps.find(item => item.mode === this.pipelineMode) || this.miniApps[0]); },
        get miniAppChatEnabled() { return Boolean(window.AI2AppsMiniAppChat && this.currentMiniApp && (this.currentMiniApp.source !== 'package' || this.currentMiniApp.chat?.enabled === true)); },
        get currentRun() { return this.runs.find(item => item.id === this.selectedRunId) || this.runs[0] || null; },
        get currentArtifact() { return this.currentRun?.artifacts?.find(item => item.id === this.selectedArtifactId) || this.currentRun?.artifacts?.[0] || null; },
        get runActive() { return ['queued', 'running', 'waiting_input'].includes(this.currentRun?.status); },
        get speechProviders() { return this.providers.filter(item => item.modelType === 'audio_tts'); },
        get sttProviders() { return this.providers.filter(item => item.modelType === 'audio_stt'); },
        get selectedSpeechProvider() { return this.speechProviders.find(item => item.id === this.selectedTtsModel) || this.speechProviders.find(item => item.ready) || null; },
        get selectedSttProvider() { return this.sttProviders.find(item => item.ready) || this.sttProviders[0] || null; },
        get speechReady() { return Boolean(this.selectedSpeechProvider?.ready); },
        get sttReady() { return Boolean(this.selectedSttProvider?.ready); },
        get voiceCloneReady() { return this.speechProviders.some(item => item.ready && (item.capabilities?.includes('voice_cloning') || item.audioCapabilities?.tts?.voice_profiles?.mode === 'native')); },
        get trainedVoices() { return this.voiceProfiles.filter(item => item.sourceType !== 'synthetic_designed' && item.referenceAssetId); },
        get previewActionTitle() { return tr(this.speechReady ? 'readaloud.preview_local' : 'readaloud.configure_speech'); },
        get emotions() { return ['neutral', 'happy', 'sad', 'angry', 'calm', 'excited', 'whisper'].map(id => ({ id, name: tr(`readaloud.emotion.${id}`) })); },

        favoriteMiniApps: [],
        openCoder() { if (window.ai2appsShell?.openEntry) window.ai2appsShell.openEntry({ appId: 'ai2apps.coder', query: { template: 'mini-app', placement: APP_ID } }); else window.open('/apps/ai2apps.coder?template=mini-app&placement='+encodeURIComponent(APP_ID), '_blank', 'noopener'); },
        isFavorite(id) { return this.favoriteMiniApps.includes(id); },
        toggleFavorite(id) { this.favoriteMiniApps = this.isFavorite(id) ? this.favoriteMiniApps.filter(value => value !== id) : [...this.favoriteMiniApps, id]; try { localStorage.setItem('ai2apps.readaloud.favorites', JSON.stringify(this.favoriteMiniApps)); } catch (_) {} },
        miniAppStatusLabel(ready) { const zh = document.documentElement.lang.startsWith('zh'); return ready ? (zh ? '可用 · 切换收藏' : 'Available · Toggle favorite') : (zh ? '需要下载依赖' : 'Dependencies need download'); },
        async init() {
            try { const saved = JSON.parse(localStorage.getItem('ai2apps.readaloud.favorites') || '[]'); this.favoriteMiniApps = Array.isArray(saved) ? saved : []; } catch (_) {}
            this.setupMiniAppChat();
            window.addEventListener('beforeunload', () => { this.saveDraft().catch(() => {}); this.cleanup(); }, { once: true });
            window.addEventListener('message', event => this.acceptGalleryMessage(event));
            window.addEventListener('resize', () => this.applyResponsiveLayout());
            this.applyResponsiveLayout();
            try { this.miniAppDefinitions = (await request('/mini-apps')).items || []; } catch (_) {}
            await this.refreshAllPackageMiniAppReadiness();
            const pendingMiniApp = window.AI2AppsStudioMiniApps?.pendingSetup(APP_ID)?.miniAppId;
            const rememberedMiniApp = pendingMiniApp || localStorage.getItem('ai2apps.readaloud.active-mini-app');
            const remembered = this.miniApps.find(item => item.id === rememberedMiniApp);
            if (remembered?.source === 'package') await this.mountPackageMiniApp(remembered);
            else if (remembered) this.pipelineMode = remembered.mode;
            await this.refresh();
            if (!this.packageMiniAppId) await this.loadDraft(this.currentMiniApp.id);
            if (this.leftView === 'assets') this.mountGalleryMini();
            if (this.leftView === 'chat') this.mountMiniAppChat();
            if (this.selectedProjectId && this.selectedProjectId !== this.selected?.id) await this.openProject(this.selectedProjectId, false);
            await this.refreshRuns();
            await this.probeCapabilities();
            try {
                const resumed = await window.AI2AppsStudioMiniApps?.resumeSetup(APP_ID, this.miniApps.filter(item => item.source === 'package'));
                if (resumed?.status === 'ready') {
                    const item = this.miniApps.find(value => value.id === (resumed.miniAppId || this.packageMiniAppId));
                    if (item?.source === 'package' && item.id !== this.packageMiniAppId) await this.mountPackageMiniApp(item);
                    else if (item?.source === 'package') await this.refreshPackageMiniAppReadiness(item);
                    await this.refreshAllPackageMiniAppReadiness();
                    await this.refresh(); this.success(tr('readaloud.deps_ready'));
                }
            } catch (error) { this.fail(error); }
            for (const capability of ['audio.speech_generation', 'audio.speech_recognition', 'audio.voice_clone']) {
                try {
                    const resumed = await window.AI2AppsCapabilities?.resume(APP_ID, { capability });
                    if (resumed?.status !== 'ready' || resumed.outcome !== 'configured') continue;
                    await this.finishCapability(resumed, capability);
                    this.success(tr(capability === 'audio.voice_clone' ? 'readaloud.success.voice_configured' : capability === 'audio.speech_recognition' ? 'readaloud.success.stt_configured' : 'readaloud.success.speech_configured'));
                } catch (error) { this.fail(error); }
            }
        },
        cleanup() { clearTimeout(this.runTimer); clearTimeout(this.draftTimer); this.chatController?.dispose(); this.packageChatBridge?.dispose(); const urls = new Set(this.previewHistory.filter(item => item.local).map(item => item.url)); if (this.trainingAudioUrl?.startsWith('blob:')) urls.add(this.trainingAudioUrl); urls.forEach(url => URL.revokeObjectURL(url)); this.trainingStream?.getTracks().forEach(track => track.stop()); },
        icons() { this.$nextTick(() => window.lucide?.createIcons()); },
        success(text) { this.notice = text; this.noticeTone = 'success'; this.icons(); },
        fail(error) { this.notice = error?.message || String(error); this.noticeTone = 'error'; this.icons(); },
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
                mode: this.pipelineMode, ready: this.miniAppReady(miniApp),
                selectedModel: this.selectedSpeechProvider?.displayName || null,
                project: this.selected ? {
                    id: this.selected.id, title: this.selected.title, purpose: this.selected.purpose,
                    sourceText: String(this.selected.sourceText || '').slice(0, 20000),
                    characters: (this.selected.characters || []).map(item => ({ id: item.id, name: item.name })),
                    segments: (this.selected.segments || []).slice(0, 30).map(item => ({ id: item.id, speakerId: item.speakerId, text: String(item.text || '').slice(0, 500), emotion: item.emotion, speed: item.speed })),
                } : null,
                draft: this.pipelineMode === 'voice' ? this.voiceForm : this.pipelineMode === 'training' ? { ...this.trainingForm, audioFile: this.trainingForm.audioFile?.name || null, resourceHandle: undefined } : this.segmentForm,
            };
            const properties = ['quick', 'audiobook', 'drama'].includes(this.pipelineMode)
                ? { projectTitle: { type: 'string', maxLength: 160 }, sourceText: { type: 'string', maxLength: 200000 }, segmentText: { type: 'string', maxLength: 10000 }, emotion: { type: 'string' }, speed: { type: 'number', minimum: .5, maximum: 2 } }
                : { name: { type: 'string', maxLength: 120 }, referenceTranscript: { type: 'string', maxLength: 20000 } };
            const runTitle = this.pipelineMode === 'voice' ? 'Create voice profile' : this.pipelineMode === 'training' ? 'Save training material' : 'Render audio';
            return {
                schema: window.AI2AppsMiniAppChat.SCHEMA, enabled: true,
                miniApp: { id: miniApp.id, name: miniApp.name, version: miniApp.version, studioId: APP_ID },
                systemPrompt: `You are the conversational controller for ${miniApp.name} in Voice Studio. Help the user prepare narration, character, voice, or training material using only the current Mini-App. Preserve authorship and voice-consent requirements.`,
                context,
                help: { available: true, format: 'markdown', maxBytes: 32 * 1024 },
                tools: [
                    { name: 'update_current_draft', title: 'Update current draft', description: 'Update the current project or form fields.', inputSchema: { type: 'object', properties, additionalProperties: false } },
                    { name: 'run_current', title: runTitle, description: 'Run the current Mini-App with its visible project and form state.', inputSchema: { type: 'object', properties: {}, additionalProperties: false }, confirmation: 'always' },
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
                if (['quick', 'audiobook', 'drama'].includes(this.pipelineMode)) {
                    if (this.selected) {
                        if (typeof args.projectTitle === 'string') this.selected.title = args.projectTitle.slice(0, 160);
                        if (typeof args.sourceText === 'string') this.selected.sourceText = args.sourceText.slice(0, 200000);
                        if ('projectTitle' in args || 'sourceText' in args) await this.saveProject();
                    }
                    if (typeof args.segmentText === 'string') this.segmentForm.text = args.segmentText.slice(0, 10000);
                    if (typeof args.emotion === 'string' && this.emotions.some(item => item.id === args.emotion)) this.segmentForm.emotion = args.emotion;
                    if (Number.isFinite(args.speed)) this.segmentForm.speed = Math.max(.5, Math.min(2, Number(args.speed)));
                } else {
                    const form = this.pipelineMode === 'training' ? this.trainingForm : this.voiceForm;
                    if (typeof args.name === 'string') form.name = args.name.slice(0, 120);
                    if (typeof args.referenceTranscript === 'string') form.referenceTranscript = args.referenceTranscript.slice(0, 20000);
                }
                this.scheduleDraft(); this.icons();
                return { updated: true, state: (await this.describeMiniAppChat()).context };
            }
            if (name === 'run_current') {
                if (this.pipelineMode === 'voice') await this.createVoiceProfile();
                else if (this.pipelineMode === 'training') await this.saveTrainingMaterial();
                else {
                    if (!this.selected) throw new Error('Select or create a project first');
                    if (!this.speechReady) throw new Error('Configure a speech model first');
                    await this.renderProject();
                }
                return { started: true, mode: this.pipelineMode };
            }
            throw new Error('Unknown Mini-App Tool');
        },

        async refresh() {
            this.busy = true; this.notice = '';
            try {
                const [projects, providers, voices] = await Promise.all([request('/projects'), request('/providers'), request('/voice-profiles')]);
                this.projects = projects.items || []; this.providers = providers.items || []; this.voiceProfiles = voices.items || [];
                if (!this.speechProviders.some(item => item.id === this.selectedTtsModel)) this.selectedTtsModel = this.speechProviders.find(item => item.ready)?.id || this.speechProviders[0]?.id || '';
                const projectId = this.selectedProjectId || this.selected?.id || this.projects[0]?.id || '';
                if (projectId && this.projects.some(item => item.id === projectId)) await this.openProject(projectId, false);
                else { this.selected = null; this.selectedProjectId = ''; }
                this.icons();
            } catch (error) { this.fail(error); } finally { this.busy = false; }
        },
        async showLeftView(view) { this.leftView = view === 'assets' ? 'assets' : (view === 'chat' && this.miniAppChatEnabled ? 'chat' : 'mini-apps'); if (this.leftView === 'assets' && !this.galleryMiniUrl) await this.mountGalleryMini(); if (this.leftView === 'chat') await this.mountMiniAppChat(); this.icons(); },
        async selectMiniApp(id) { const item = this.miniApps.find(value => value.id === id); if (!item) return; if (!this.packageMiniAppId) await this.saveDraft(); localStorage.setItem('ai2apps.readaloud.active-mini-app', item.id); if (this.leftView !== 'chat') this.leftView = 'mini-apps'; if (item.source === 'package') { await this.mountPackageMiniApp(item); if (!this.miniAppChatEnabled && this.leftView === 'chat') this.leftView = 'mini-apps'; return; } this.packageChatBridge?.dispose(); this.packageChatBridge = null; this.packageMiniAppId = ''; this.packageMiniAppUrl = ''; this.packageMiniAppError = ''; this.pipelineMode = item.mode; if (item.mode === 'drama') this.tab = 'script'; if (item.mode === 'voice') this.showVoiceForm = false; await this.loadDraft(item.id); if (this.selectedProjectId && this.selectedProjectId !== this.selected?.id) await this.openProject(this.selectedProjectId, false); this.chatController?.changed(); this.emitBridge('mini-app.ready', { miniAppId: item.id, version: item.version }); this.icons(); },
        miniAppReady(item) { if (item?.source === 'package') return this.packageMiniAppReadiness[item.id] === true; return item?.capability === 'audio.voice_clone' ? this.voiceCloneReady : this.speechReady; },
        async refreshAllPackageMiniAppReadiness() {
            try { this.packageMiniAppReadiness = await window.AI2AppsStudioMiniApps?.readiness(APP_ID) || {}; }
            catch (_) { /* Keep the most recent readiness snapshot during reconnects. */ }
            this.icons();
            return this.packageMiniAppReadiness;
        },
        async refreshPackageMiniAppReadiness(item, mountId = this.packageMiniAppMountId) {
            if (!item?.id || !mountId) return false;
            try {
                const probe = await window.AI2AppsStudioMiniApps.probe(APP_ID, mountId);
                const capabilities = Array.isArray(probe?.items) ? probe.items : [];
                const required = capabilities.filter(value => value?.required !== false);
                const ready = required.length > 0 && required.every(value => value?.implemented === true && value?.ready === true);
                this.packageMiniAppReadiness = { ...this.packageMiniAppReadiness, [item.id]: ready };
                return ready;
            } catch (_) {
                this.packageMiniAppReadiness = { ...this.packageMiniAppReadiness, [item.id]: false };
                return false;
            }
        },
        async setupCurrentMiniApp() {
            const item = this.currentMiniApp;
            if (!item || this.miniAppReady(item) || this.packageMiniAppSetupBusy) return;
            if (item.source !== 'package') {
                if (item.capability === 'audio.voice_clone') await this.configureVoiceClone();
                else await this.configureSpeech();
                return;
            }
            this.packageMiniAppSetupBusy = true;
            try {
                await window.AI2AppsStudioMiniApps.setup(APP_ID, item);
                const readiness = await this.refreshAllPackageMiniAppReadiness();
                const ready = readiness[item.id] === true;
                if (ready) this.success(tr('readaloud.deps_ready'));
            } catch (error) { this.fail(error); }
            finally { this.packageMiniAppSetupBusy = false; this.icons(); }
        },
        async mountPackageMiniApp(item) {
            if (!item?.id || this.packageMiniAppLoading) return;
            this.packageMiniAppId = item.id; this.packageMiniAppUrl = ''; this.packageMiniAppError = ''; this.packageMiniAppLoading = true;
            this.packageMiniAppReadiness = { ...this.packageMiniAppReadiness, [item.id]: false };
            try {
                const mount = await window.AI2AppsStudioMiniApps.mount(APP_ID, item.id, { placement: 'inline' });
                this.packageMiniAppMountId = mount.id || ''; this.packageMiniAppUrl = mount.content_url || '';
                if (!this.packageMiniAppUrl) throw new Error('Mini-App content URL is unavailable');
                await this.refreshPackageMiniAppReadiness(item, mount.id);
                if (item.chat?.enabled === true) await new Promise(resolve => this.$nextTick(() => {
                    this.packageChatBridge?.dispose();
                    this.packageChatBridge = window.AI2AppsMiniAppChat.createPackageBridge(() => this.$refs.packageMiniApp, item.chat);
                    resolve();
                }));
                this.emitBridge('mini-app.ready', { miniAppId: item.id, version: item.version, mountId: mount.id });
            } catch (error) { this.packageMiniAppError = error?.message || String(error); }
            finally { this.packageMiniAppLoading = false; this.chatController?.changed(); this.icons(); }
        },
        applyResponsiveLayout() { if (window.innerWidth < 760 && !['mini-apps', 'create', 'output'].includes(this.mobilePanel)) this.mobilePanel = 'create'; },
        showMobilePanel(panel) { this.mobilePanel = panel; if (panel === 'mini-apps') this.leftCollapsed = false; if (panel === 'output') this.rightCollapsed = false; this.icons(); },
        emitBridge(name, detail = {}) { window.dispatchEvent(new CustomEvent('ai2apps.studio.bridge', { detail: { type: name, studioId: APP_ID, ...detail } })); },
        async mountGalleryMini(force = false) {
            if (this.galleryMiniLoading || (this.galleryMiniUrl && !force)) return;
            this.galleryMiniLoading = true; this.galleryMiniError = '';
            if (force) { this.galleryMiniUrl = ''; this.galleryMiniMountId = ''; }
            try {
                if (!window.ai2appsShell?.mountMiniEntry) { this.galleryMiniUrl = GALLERY_MINI_FALLBACK_URL; return; }
                const mount = await window.ai2appsShell.mountMiniEntry({ appId: 'ai2apps.gallery', placement: 'sidebar', requestedBy: APP_ID });
                if (!mount?.content_url) throw new Error(tr('readaloud.error.gallery_url'));
                this.galleryMiniMountId = mount.id || '';
                this.galleryMiniUrl = mount.content_url;
            } catch (error) {
                if (galleryHostUnavailable(error)) this.galleryMiniUrl = GALLERY_MINI_FALLBACK_URL;
                else { this.galleryMiniUrl = ''; this.galleryMiniError = error?.message || tr('readaloud.error.gallery_load'); }
            } finally { this.galleryMiniLoading = false; this.icons(); }
        },
        openGallery() { if (window.ai2appsShell?.openEntry) window.ai2appsShell.openEntry({ appId: 'ai2apps.gallery' }); else window.open('/apps/ai2apps.gallery', '_blank', 'noopener'); },

        draftPayload() {
            const training = { ...this.trainingForm, audioFile: null, resourceHandle: '' };
            return { selectedProjectId: this.selectedProjectId, selectedTtsModel: this.selectedTtsModel, tab: this.tab, leftView: this.leftView, leftCollapsed: this.leftCollapsed, rightCollapsed: this.rightCollapsed, mobilePanel: this.mobilePanel, projectForm: this.projectForm, characterForm: this.characterForm, segmentForm: this.segmentForm, voiceForm: this.voiceForm, trainingForm: training, selectedRunId: this.selectedRunId };
        },
        applyDraft(draft = {}) {
            for (const key of ['selectedProjectId', 'selectedTtsModel', 'tab', 'leftView', 'leftCollapsed', 'rightCollapsed', 'mobilePanel', 'selectedRunId']) if (draft[key] !== undefined) this[key] = draft[key];
            for (const key of ['projectForm', 'characterForm', 'segmentForm', 'voiceForm']) if (draft[key] && typeof draft[key] === 'object') this[key] = { ...this[key], ...draft[key] };
            if (draft.trainingForm && typeof draft.trainingForm === 'object') this.trainingForm = { ...this.trainingForm, ...draft.trainingForm, audioFile: null, resourceHandle: '' };
            if (this.trainingForm.assetId) this.useGalleryAsset({ id: this.trainingForm.assetId, name: this.trainingForm.assetName, mediaType: this.trainingForm.mediaType }).catch(error => this.fail(error));
        },
        scheduleDraft() {
            clearTimeout(this.draftTimer);
            if (this.currentMiniApp?.source !== 'package') {
                this.draftTimer = setTimeout(() => this.saveDraft().catch(error => this.fail(error)), 450);
            }
            this.emitBridge('mini-app.draft.changed', { miniAppId: this.currentMiniApp.id });
        },
        async saveDraft() {
            if (!appInstanceId() || !this.currentMiniApp?.id || this.currentMiniApp.source === 'package') return;
            clearTimeout(this.draftTimer);
            await request(`/drafts/${encodeURIComponent(this.currentMiniApp.id)}`, { method: 'PUT', body: { draft: this.draftPayload() } });
        },
        async loadDraft(miniAppId) {
            if (!appInstanceId() || this.miniApps.find(item => item.id === miniAppId)?.source === 'package') return;
            const payload = await request(`/drafts/${encodeURIComponent(miniAppId)}`);
            this.applyDraft(payload.draft || {});
        },

        async acceptGalleryMessage(event) {
            if (event.origin !== window.location.origin || event.data?.type !== 'ai2apps.gallery.asset-selected') return;
            try { await this.useGalleryAsset(event.data.asset); } catch (error) { this.fail(error); }
        },
        async acceptGalleryDrop(event) {
            event.preventDefault();
            const raw = event.dataTransfer?.getData('application/x-ai2apps-gallery-asset');
            if (!raw) return;
            const asset = { id: raw, name: event.dataTransfer?.getData('text/plain') || tr('readaloud.gallery_asset'), mediaType: 'audio/*' };
            await this.useGalleryAsset(asset); this.emitBridge('gallery.asset.drop', { assetId: raw });
        },
        async useGalleryAsset(asset) {
            if (!asset?.id) return;
            const response = await fetch(`/v1/platform/gallery/assets/${encodeURIComponent(asset.id)}/resource-handles`, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify({ consumerAppId: APP_ID, appInstanceId: appInstanceId() }) });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload?.error?.message || payload?.detail?.message || payload?.detail || tr('readaloud.error.gallery_load'));
            if (!String(payload.mediaType || asset.mediaType || '').startsWith('audio/')) throw new Error(tr('readaloud.error.training_audio_type'));
            this.trainingForm.assetId = asset.id; this.trainingForm.resourceHandle = payload.resourceHandle || payload.id; this.trainingForm.assetName = asset.name || payload.name || tr('readaloud.gallery_asset'); this.trainingForm.mediaType = asset.mediaType || payload.mediaType || 'audio/*'; this.trainingForm.audioFile = null;
            const query = new URLSearchParams({ appInstanceId: appInstanceId(), consumerAppId: APP_ID });
            const handleId = String(this.trainingForm.resourceHandle).replace(/^resource:\/\//, '');
            this.trainingAudioUrl = `/v1/platform/gallery/resource-handles/${encodeURIComponent(handleId)}/content?${query}`;
            this.scheduleDraft(); this.mobilePanel = 'create'; this.icons();
        },
        async importTrainingFile(file) {
            if (!file) return;
            const form = new FormData(); form.append('file', file, file.name); form.append('sourceAppId', APP_ID); form.append('sourceRef', 'character-training');
            const response = await fetch('/v1/platform/gallery/assets/import', { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json' }, body: form });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload?.error?.message || payload?.detail || tr('readaloud.error.training_upload', { status: response.status }));
            await this.useGalleryAsset(payload.asset);
        },

        capabilityRequest(capability, action, resumeToken = '') {
            const voice = capability === 'audio.voice_clone';
            const recognition = capability === 'audio.speech_recognition';
            const modelId = voice ? '' : recognition ? (this.selectedSttProvider?.id || '') : (this.selectedSpeechProvider?.id || '');
            const effectiveResumeToken = resumeToken || globalThis.crypto?.randomUUID?.() || `readaloud-${Date.now()}-${Math.random().toString(36).slice(2)}`;
            return {
                appId: APP_ID, capability, actionId: action,
                requirements: { operations: [voice ? 'voice_cloning' : recognition ? 'speech_recognition' : 'speech_generation'], ...(recognition ? {} : { outputFormats: ['wav'] }), ...(modelId ? { modelId } : {}) },
                intent: action === 'probe' ? {} : { returnTo: `/apps/${APP_ID}`, resumeToken: effectiveResumeToken, completionPolicy: 'configure_only' },
            };
        },
        async probeCapabilities() {
            if (!window.AI2AppsCapabilities?.probe) return;
            const capabilities = ['audio.speech_generation', 'audio.speech_recognition', 'audio.voice_clone'];
            const results = await Promise.all(capabilities.map(async capability => {
                try { return [capability, await window.AI2AppsCapabilities.probe(this.capabilityRequest(capability, 'probe'))]; }
                catch (_) { return [capability, null]; }
            }));
            this.capabilityProbes = Object.fromEntries(results);
        },
        async finishCapability(result, capability) {
            await this.refresh();
            if (capability === 'audio.speech_generation') {
                const modelId = result.provider?.modelId;
                if (this.speechProviders.some(item => item.id === modelId && item.ready)) this.selectedTtsModel = modelId;
                if (!this.speechReady) throw new Error(tr('readaloud.error.speech_provider_missing'));
            } else if (capability === 'audio.speech_recognition') {
                if (!this.sttReady) throw new Error(tr('readaloud.error.stt_provider_missing'));
            } else if (!this.voiceCloneReady) throw new Error(tr('readaloud.error.voice_provider_missing'));
            if (result.outcome === 'configured' && result.session?.id) await window.AI2AppsCapabilities.acknowledge(result.session.id, { appId: APP_ID });
            return { configured: result.outcome === 'configured' };
        },
        async ensureCapability(capability, action, resumeToken = '') {
            if ((capability === 'audio.speech_generation' && this.speechReady) || (capability === 'audio.speech_recognition' && this.sttReady) || (capability === 'audio.voice_clone' && this.voiceCloneReady)) return { configured: false };
            const result = await window.AI2AppsCapabilities.ensure(this.capabilityRequest(capability, action, resumeToken));
            return this.finishCapability(result, capability);
        },
        async configureSpeech() { if (this.configuringSpeech) return; this.configuringSpeech = true; try { const result = await this.ensureCapability('audio.speech_generation', 'configure-speech'); this.success(tr(result.configured ? 'readaloud.success.speech_configured' : 'readaloud.speech_already_ready')); } catch (error) { this.fail(error); } finally { this.configuringSpeech = false; } },
        async configureVoiceClone() { if (this.configuringVoice) return; this.configuringVoice = true; try { const result = await this.ensureCapability('audio.voice_clone', 'configure-voice-clone'); this.success(tr(result.configured ? 'readaloud.success.voice_configured' : 'readaloud.voice_already_ready')); } catch (error) { this.fail(error); } finally { this.configuringVoice = false; } },

        setTrainingAudio(file) {
            if (!file) return;
            if (!String(file.type || '').startsWith('audio/')) { this.fail(new Error(tr('readaloud.error.training_audio_type'))); return; }
            if (this.trainingAudioUrl) URL.revokeObjectURL(this.trainingAudioUrl);
            this.trainingForm.audioFile = file;
            this.trainingAudioUrl = URL.createObjectURL(file);
        },
        async selectTrainingAudio(event) { const file = event?.target?.files?.[0]; this.setTrainingAudio(file); try { await this.importTrainingFile(file); } catch (error) { this.fail(error); } },
        async startTrainingRecording() {
            if (this.recordingTraining) return;
            try {
                this.trainingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                this.trainingChunks = [];
                this.trainingRecorder = new MediaRecorder(this.trainingStream);
                this.trainingRecorder.addEventListener('dataavailable', event => { if (event.data?.size) this.trainingChunks.push(event.data); });
                this.trainingRecorder.addEventListener('stop', async () => {
                    const type = this.trainingRecorder?.mimeType || 'audio/webm';
                    const extension = type.includes('mp4') ? 'm4a' : type.includes('ogg') ? 'ogg' : 'webm';
                    const file = new File(this.trainingChunks, `character-reference-${Date.now()}.${extension}`, { type });
                    this.setTrainingAudio(file);
                    try { await this.importTrainingFile(file); } catch (error) { this.fail(error); }
                    this.trainingStream?.getTracks().forEach(track => track.stop());
                    this.trainingStream = null; this.recordingTraining = false; this.icons();
                }, { once: true });
                this.trainingRecorder.start(); this.recordingTraining = true; this.icons();
            } catch (error) { this.fail(error); this.recordingTraining = false; }
        },
        stopTrainingRecording() { if (this.trainingRecorder?.state === 'recording') this.trainingRecorder.stop(); },
        async transcribeTrainingAudio() {
            if (this.transcribingTraining || (!this.trainingForm.audioFile && !this.trainingForm.resourceHandle)) return;
            this.transcribingTraining = true; this.notice = '';
            try {
                const capability = await this.ensureCapability('audio.speech_recognition', 'configure-training-asr');
                if (capability.configured) { this.success(tr('readaloud.success.stt_configured_retry')); return; }
                let file = this.trainingForm.audioFile;
                if (!file && this.trainingAudioUrl) { const source = await fetch(this.trainingAudioUrl, { credentials: 'same-origin' }); if (!source.ok) throw new Error(tr('readaloud.error.gallery_load')); const blob = await source.blob(); file = new File([blob], this.trainingForm.assetName || 'reference-audio', { type: blob.type || this.trainingForm.mediaType }); }
                const form = new FormData(); form.append('file', file, file.name); form.append('model', this.selectedSttProvider.id); form.append('response_format', 'json');
                const response = await fetch('/v1/audio/transcriptions', { method: 'POST', credentials: 'same-origin', body: form, headers: { Accept: 'application/json' } });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(payload?.error?.message || payload?.detail || tr('readaloud.error.transcription', { status: response.status }));
                this.trainingForm.referenceTranscript = String(payload.text || '').trim(); this.success(tr('readaloud.success.transcribed'));
            } catch (error) { this.fail(error); } finally { this.transcribingTraining = false; this.icons(); }
        },
        async saveTrainingMaterial() {
            const draft = this.trainingForm;
            if (this.savingTraining || (!draft.audioFile && !draft.assetId) || !draft.name.trim() || !draft.referenceTranscript.trim()) return;
            this.savingTraining = true; this.notice = '';
            try {
                if (!draft.assetId && draft.audioFile) await this.importTrainingFile(draft.audioFile);
                await request('/voice-profiles', { method: 'POST', body: { name: draft.name.trim(), source_type: draft.sourceType, reference_transcript: draft.referenceTranscript.trim(), reference_asset_id: draft.assetId, rights_scope: { consent_confirmed: draft.consentConfirmed, usage_rights_confirmed: draft.usageRightsConfirmed, prohibited_impersonation_acknowledged: draft.antiImpersonationAcknowledged } } });
                if (this.trainingAudioUrl) URL.revokeObjectURL(this.trainingAudioUrl);
                this.trainingAudioUrl = ''; this.trainingForm = { name: '', sourceType: 'self_voice', referenceTranscript: '', audioFile: null, assetId: '', resourceHandle: '', assetName: '', mediaType: '', consentConfirmed: false, usageRightsConfirmed: false, antiImpersonationAcknowledged: false };
                await this.refresh(); this.success(tr('readaloud.success.training_saved'));
            } catch (error) { this.fail(error); } finally { this.savingTraining = false; this.icons(); }
        },

        async openProject(id, switchView = true) { if (!id) { this.selected = null; this.selectedProjectId = ''; return; } this.busy = true; try { this.selected = await request('/projects/' + encodeURIComponent(id)); this.selectedProjectId = id; if (switchView && this.pipelineMode === 'voice') this.pipelineMode = 'audiobook'; this.icons(); } catch (error) { this.fail(error); } finally { this.busy = false; } },
        async createProject() { this.busy = true; try { const created = await request('/projects', { method: 'POST', body: { title: this.projectForm.title, purpose: this.projectForm.purpose, source_rights: this.projectForm.sourceRights, source_text: this.projectForm.sourceText } }); this.showProjectForm = false; this.projectForm = { title: '', purpose: 'private', sourceRights: 'user_owned', sourceText: '' }; this.selectedProjectId = created.id; await this.refresh(); this.success(tr('readaloud.success.project_created')); } catch (error) { this.fail(error); } finally { this.busy = false; } },
        async saveProject() { if (!this.selected) return; try { this.selected = await request('/projects/' + encodeURIComponent(this.selected.id), { method: 'PATCH', body: { title: this.selected.title, purpose: this.selected.purpose, source_rights: this.selected.sourceRights, source_text: this.selected.sourceText } }); const item = this.projects.find(project => project.id === this.selected.id); if (item) Object.assign(item, this.selected); this.success(tr('readaloud.success.project_saved')); } catch (error) { this.fail(error); } },
        async createCharacter() { if (!this.selected) return; try { await request('/projects/' + encodeURIComponent(this.selected.id) + '/characters', { method: 'POST', body: { name: this.characterForm.name, description: this.characterForm.description, voice_profile_id: this.characterForm.voiceProfileId || null } }); this.characterForm = { name: '', description: '', voiceProfileId: '' }; this.showCharacterForm = false; await this.openProject(this.selected.id, false); this.success(tr('readaloud.success.character_added')); } catch (error) { this.fail(error); } },
        async createSegment() { if (!this.selected) return; try { await request('/projects/' + encodeURIComponent(this.selected.id) + '/segments', { method: 'POST', body: { speaker_id: this.segmentForm.speakerId || null, text: this.segmentForm.text, emotion: this.segmentForm.emotion, emotion_strength: Number(this.segmentForm.emotionStrength), speed: Number(this.segmentForm.speed), pause_after_ms: Number(this.segmentForm.pauseAfterMs) } }); this.segmentForm = { speakerId: '', text: '', emotion: 'neutral', emotionStrength: 1, speed: 1, pauseAfterMs: 300 }; this.showSegmentForm = false; await this.openProject(this.selected.id, false); this.success(tr('readaloud.success.segment_added')); } catch (error) { this.fail(error); } },
        async saveSegment(segment) { if (!this.selected) return; const updated = await request('/projects/' + encodeURIComponent(this.selected.id) + '/segments/' + encodeURIComponent(segment.id), { method: 'PATCH', body: { speaker_id: segment.speakerId || null, text: segment.text, emotion: segment.emotion, emotion_strength: Number(segment.emotionStrength), speed: Number(segment.speed), pause_after_ms: Number(segment.pauseAfterMs), ...(segment.reviewStatus ? { review_status: segment.reviewStatus } : {}) } }); Object.assign(segment, updated); this.scheduleDraft(); },
        async createVoiceProfile() { try { await request('/voice-profiles', { method: 'POST', body: { name: this.voiceForm.name, source_type: this.voiceForm.sourceType, model_id: this.voiceForm.modelId || null, provider_voice_id: this.voiceForm.providerVoiceId || null, reference_transcript: this.voiceForm.referenceTranscript, rights_scope: { consent_confirmed: this.voiceForm.consentConfirmed, usage_rights_confirmed: this.voiceForm.usageRightsConfirmed, prohibited_impersonation_acknowledged: this.voiceForm.antiImpersonationAcknowledged } } }); this.voiceForm = { name: '', sourceType: 'synthetic_designed', modelId: '', providerVoiceId: '', referenceTranscript: '', consentConfirmed: false, usageRightsConfirmed: false, antiImpersonationAcknowledged: false }; this.showVoiceForm = false; await this.refresh(); this.success(tr('readaloud.success.voice_created')); } catch (error) { this.fail(error); } },

        async preview(segment) {
            if (this.previewing || !segment?.text?.trim()) return;
            this.previewing = segment.id; this.notice = '';
            try {
                segment.reviewStatus = 'approved';
                await this.saveSegment(segment);
                const capability = await this.ensureCapability('audio.speech_generation', 'configure-preview', segment.id);
                if (capability.configured) { this.success(tr('readaloud.success.speech_configured_retry')); return; }
                await this.createRun([segment.id], segment.text.slice(0, 54));
            } catch (error) { this.fail(error); } finally { this.previewing = ''; this.icons(); }
        },
        async renderProject() { if (!this.selected) return; for (const segment of this.selected.segments || []) if (segment.reviewStatus !== 'approved') { segment.reviewStatus = 'approved'; await this.saveSegment(segment); } await this.createRun(null, this.selected.title); },
        async createRun(segmentIds = null, title = '') { if (!this.selected || !this.selectedSpeechProvider) return; const run = await request('/runs', { method: 'POST', body: { miniAppId: this.currentMiniApp.id, projectId: this.selected.id, modelId: this.selectedSpeechProvider.id, segmentIds, title: title || this.selected.title } }); this.runs = [run, ...this.runs.filter(item => item.id !== run.id)]; this.selectRun(run); this.emitBridge('mini-app.run.create', { runId: run.id, miniAppId: run.miniAppId }); this.pollRun(); },
        async refreshRuns() { if (!appInstanceId()) return; const payload = await request('/runs?limit=50'); this.runs = payload.items || []; if (!this.runs.some(item => item.id === this.selectedRunId)) this.selectedRunId = this.runs[0]?.id || ''; this.syncArtifactPreview(); if (this.runActive) this.pollRun(); },
        selectRun(run) { if (!run) return; this.selectedRunId = run.id; this.selectedArtifactId = run.artifacts?.[0]?.id || ''; this.mobilePanel = 'output'; this.syncArtifactPreview(); this.scheduleDraft(); this.emitBridge('mini-app.run.select', { runId: run.id }); this.icons(); },
        selectArtifact(artifact) { if (!artifact) return; this.selectedArtifactId = artifact.id; this.syncArtifactPreview(); this.emitBridge('mini-app.artifact.select', { artifactId: artifact.id }); this.$nextTick(() => this.$refs.audioPlayer?.play().catch(() => {})); },
        syncArtifactPreview() { const artifact = this.currentArtifact; this.currentAudioUrl = artifact?.previewUrl || artifact?.downloadUrl || ''; this.currentAudioTitle = artifact?.name || this.currentRun?.title || ''; },
        pollRun() { clearTimeout(this.runTimer); if (!this.currentRun) return; this.runTimer = setTimeout(async () => { try { const run = await request(`/runs/${encodeURIComponent(this.currentRun.id)}`); const index = this.runs.findIndex(item => item.id === run.id); if (index >= 0) this.runs.splice(index, 1, run); else this.runs.unshift(run); this.syncArtifactPreview(); if (['queued', 'running', 'waiting_input'].includes(run.status)) this.pollRun(); } catch (error) { this.fail(error); } this.icons(); }, 900); },
        async cancelRun() { if (!this.currentRun) return; const run = await request(`/runs/${encodeURIComponent(this.currentRun.id)}/cancel`, { method: 'POST' }); const index = this.runs.findIndex(item => item.id === run.id); if (index >= 0) this.runs.splice(index, 1, run); this.icons(); },
        async retryRun() { const source = this.currentRun; if (!source) return; const input = source.input || {}; const run = await request('/runs', { method: 'POST', body: { miniAppId: source.miniAppId, projectId: input.projectId, modelId: input.modelId, segmentIds: input.segmentIds, title: source.title, retryOf: source.id } }); this.runs.unshift(run); this.selectRun(run); this.pollRun(); },
        async addArtifactToGallery(artifact) { const sessionId = artifact?.metadata?.artifactSessionId; const sourceId = artifact?.metadata?.sourceArtifactId || artifact?.metadata?.artifactId || artifact?.sourceId; if (!sessionId || !sourceId) throw new Error(tr('readaloud.error.artifact_unavailable')); const response = await fetch(`/v1/platform/gallery/assets/import-artifact/${encodeURIComponent(sessionId)}/${encodeURIComponent(sourceId)}`, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify({ sourceAppId: APP_ID }) }); const payload = await response.json().catch(() => ({})); if (!response.ok) throw new Error(payload?.error?.message || payload?.detail || tr('readaloud.error.gallery_load')); this.success(tr('readaloud.success.artifact_gallery')); },
        playHistory(item) { this.selectRun(item); this.$nextTick(() => this.$refs.audioPlayer?.play().catch(() => {})); },
        segmentMeta(segment) { return `${this.emotions.find(item => item.id === segment.emotion)?.name || segment.emotion} · ${tr('readaloud.speed_value', { value: Number(segment.speed || 1).toFixed(2) })}`; },
        voiceName(id) { if (!id) return tr('readaloud.voice_unbound'); const voice = this.voiceProfiles.find(item => item.id === id); return voice ? `${voice.name} · ${this.voiceStatusLabel(voice.status)}` : tr('readaloud.voice_unavailable'); },
        voiceSourceLabel(value) { return tr(value === 'synthetic_designed' ? 'readaloud.voice.synthetic_short' : value === 'self_voice' ? 'readaloud.voice.self' : 'readaloud.voice.authorized_short'); },
        voiceStatusLabel(value) { return tr(value === 'ready' ? 'readaloud.status.ready' : value === 'unverified' ? 'readaloud.status.unverified' : value === 'blocked' ? 'readaloud.status.blocked' : value); },
        capabilitySummary(model) { const audio = model.audioCapabilities || {}; const section = model.modelType === 'audio_tts' ? audio.tts || {} : audio.stt || {}; const names = Object.entries(section).filter(([, value]) => value?.mode && value.mode !== 'unsupported').map(([name]) => name.replaceAll('_', ' ')); return names.length ? names.join(' · ') : (model.capabilities || []).join(' · '); },
    }; };
})();
