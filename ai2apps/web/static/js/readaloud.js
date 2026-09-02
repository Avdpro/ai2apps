(function () {
    'use strict';
    const API = '/v1/platform/readaloud';
    const APP_ID = 'ai2apps.readaloud';
    const PIPELINES = Object.freeze([
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
    function localizedPipeline(item) {
        return { ...item, name: tr(`${item.key}.name`), summary: tr(`${item.key}.summary`), description: tr(`${item.key}.description`) };
    }
    async function request(path, options) {
        const response = await fetch(API + path, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json', ...(options?.body ? { 'Content-Type': 'application/json' } : {}) },
            ...(options || {}), body: options?.body ? JSON.stringify(options.body) : undefined,
        });
        const payload = await response.json().catch(() => null);
        if (!response.ok) throw new Error(payload?.error?.message || payload?.detail?.message || payload?.detail || tr('readaloud.error.request', { status: response.status }));
        return payload;
    }

    window.readAloudApp = function () { return {
        busy: false, notice: '', noticeTone: '', leftView: 'pipelines', pipelineMode: 'quick', tab: 'script',
        projects: [], selected: null, selectedProjectId: '', providers: [], voiceProfiles: [], selectedTtsModel: '',
        previewing: '', configuringSpeech: false, configuringVoice: false, currentAudioUrl: '', currentAudioTitle: '', previewHistory: [],
        transcribingTraining: false, savingTraining: false, recordingTraining: false, trainingAudioUrl: '', trainingRecorder: null, trainingStream: null, trainingChunks: [],
        capabilityProbes: {},
        galleryMiniUrl: '', galleryMiniLoading: false, galleryMiniError: '',
        showProjectForm: false, showCharacterForm: false, showSegmentForm: false, showVoiceForm: false,
        projectForm: { title: '', purpose: 'private', sourceRights: 'user_owned', sourceText: '' },
        characterForm: { name: '', description: '', voiceProfileId: '' },
        segmentForm: { speakerId: '', text: '', emotion: 'neutral', emotionStrength: 1, speed: 1, pauseAfterMs: 300 },
        voiceForm: { name: '', sourceType: 'synthetic_designed', modelId: '', providerVoiceId: '', referenceTranscript: '', consentConfirmed: false, usageRightsConfirmed: false, antiImpersonationAcknowledged: false },
        trainingForm: { name: '', sourceType: 'self_voice', referenceTranscript: '', audioFile: null, consentConfirmed: false, usageRightsConfirmed: false, antiImpersonationAcknowledged: false },
        tr,
        get pipelines() { return PIPELINES.map(localizedPipeline); },
        get currentPipeline() { return this.pipelines.find(item => item.mode === this.pipelineMode) || this.pipelines[0]; },
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

        async init() {
            window.addEventListener('beforeunload', () => this.cleanup(), { once: true });
            await this.refresh();
            await this.probeCapabilities();
            for (const capability of ['audio.speech_generation', 'audio.speech_recognition', 'audio.voice_clone']) {
                try {
                    const resumed = await window.AI2AppsCapabilities?.resume(APP_ID, { capability });
                    if (resumed?.status !== 'ready' || resumed.outcome !== 'configured') continue;
                    await this.finishCapability(resumed, capability);
                    this.success(tr(capability === 'audio.voice_clone' ? 'readaloud.success.voice_configured' : capability === 'audio.speech_recognition' ? 'readaloud.success.stt_configured' : 'readaloud.success.speech_configured'));
                } catch (error) { this.fail(error); }
            }
        },
        cleanup() { const urls = new Set(this.previewHistory.map(item => item.url)); if (this.currentAudioUrl) urls.add(this.currentAudioUrl); if (this.trainingAudioUrl) urls.add(this.trainingAudioUrl); urls.forEach(url => URL.revokeObjectURL(url)); this.trainingStream?.getTracks().forEach(track => track.stop()); },
        icons() { this.$nextTick(() => window.lucide?.createIcons()); },
        success(text) { this.notice = text; this.noticeTone = 'success'; this.icons(); },
        fail(error) { this.notice = error?.message || String(error); this.noticeTone = 'error'; this.icons(); },

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
        async showLeftView(view) { this.leftView = view === 'assets' ? 'assets' : 'pipelines'; if (this.leftView === 'assets' && !this.galleryMiniUrl) await this.mountGalleryMini(); this.icons(); },
        selectPipeline(id) { const item = PIPELINES.find(pipeline => pipeline.id === id); if (!item) return; this.pipelineMode = item.mode; this.leftView = 'pipelines'; if (item.mode === 'drama') this.tab = 'script'; if (item.mode === 'voice') this.showVoiceForm = false; this.icons(); },
        pipelineReady(pipeline) { return pipeline?.capability === 'audio.voice_clone' ? this.voiceCloneReady : this.speechReady; },
        async mountGalleryMini(force = false) {
            if (this.galleryMiniLoading || (this.galleryMiniUrl && !force)) return;
            this.galleryMiniLoading = true; this.galleryMiniError = '';
            try {
                if (!window.ai2appsShell?.mountMiniEntry) { this.galleryMiniUrl = '/admin/app-content/ai2apps.gallery?surface=mini'; return; }
                const mount = await window.ai2appsShell.mountMiniEntry({ appId: 'ai2apps.gallery', placement: 'sidebar', requestedBy: APP_ID });
                if (!mount?.content_url) throw new Error(tr('readaloud.error.gallery_url'));
                this.galleryMiniUrl = mount.content_url;
            } catch (error) {
                if (String(error?.message || '').includes('Unsupported host mount')) this.galleryMiniUrl = '/admin/app-content/ai2apps.gallery?surface=mini';
                else { this.galleryMiniUrl = ''; this.galleryMiniError = error?.message || tr('readaloud.error.gallery_load'); }
            } finally { this.galleryMiniLoading = false; this.icons(); }
        },
        openGallery() { if (window.ai2appsShell?.openEntry) window.ai2appsShell.openEntry({ appId: 'ai2apps.gallery' }); else window.open('/apps/ai2apps.gallery', '_blank', 'noopener'); },

        capabilityRequest(capability, action, resumeToken = '') {
            const voice = capability === 'audio.voice_clone';
            const recognition = capability === 'audio.speech_recognition';
            const modelId = voice ? '' : recognition ? (this.selectedSttProvider?.id || '') : (this.selectedSpeechProvider?.id || '');
            return {
                appId: APP_ID, capability, actionId: action,
                requirements: { operations: [voice ? 'voice_cloning' : recognition ? 'speech_recognition' : 'speech_generation'], ...(recognition ? {} : { outputFormats: ['wav'] }), ...(modelId ? { modelId } : {}) },
                intent: action === 'probe' ? {} : { returnTo: `/apps/${APP_ID}`, resumeToken: resumeToken || null, completionPolicy: 'configure_only' },
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
        selectTrainingAudio(event) { this.setTrainingAudio(event?.target?.files?.[0]); },
        async startTrainingRecording() {
            if (this.recordingTraining) return;
            try {
                this.trainingStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                this.trainingChunks = [];
                this.trainingRecorder = new MediaRecorder(this.trainingStream);
                this.trainingRecorder.addEventListener('dataavailable', event => { if (event.data?.size) this.trainingChunks.push(event.data); });
                this.trainingRecorder.addEventListener('stop', () => {
                    const type = this.trainingRecorder?.mimeType || 'audio/webm';
                    const extension = type.includes('mp4') ? 'm4a' : type.includes('ogg') ? 'ogg' : 'webm';
                    this.setTrainingAudio(new File(this.trainingChunks, `character-reference-${Date.now()}.${extension}`, { type }));
                    this.trainingStream?.getTracks().forEach(track => track.stop());
                    this.trainingStream = null; this.recordingTraining = false; this.icons();
                }, { once: true });
                this.trainingRecorder.start(); this.recordingTraining = true; this.icons();
            } catch (error) { this.fail(error); this.recordingTraining = false; }
        },
        stopTrainingRecording() { if (this.trainingRecorder?.state === 'recording') this.trainingRecorder.stop(); },
        async transcribeTrainingAudio() {
            if (this.transcribingTraining || !this.trainingForm.audioFile) return;
            this.transcribingTraining = true; this.notice = '';
            try {
                const capability = await this.ensureCapability('audio.speech_recognition', 'configure-training-asr');
                if (capability.configured) { this.success(tr('readaloud.success.stt_configured_retry')); return; }
                const form = new FormData(); form.append('file', this.trainingForm.audioFile, this.trainingForm.audioFile.name); form.append('model', this.selectedSttProvider.id); form.append('response_format', 'json');
                const response = await fetch('/v1/audio/transcriptions', { method: 'POST', credentials: 'same-origin', body: form, headers: { Accept: 'application/json' } });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(payload?.error?.message || payload?.detail || tr('readaloud.error.transcription', { status: response.status }));
                this.trainingForm.referenceTranscript = String(payload.text || '').trim(); this.success(tr('readaloud.success.transcribed'));
            } catch (error) { this.fail(error); } finally { this.transcribingTraining = false; this.icons(); }
        },
        async saveTrainingMaterial() {
            const draft = this.trainingForm;
            if (this.savingTraining || !draft.audioFile || !draft.name.trim() || !draft.referenceTranscript.trim()) return;
            this.savingTraining = true; this.notice = '';
            try {
                const form = new FormData(); form.append('file', draft.audioFile, draft.audioFile.name); form.append('sourceAppId', APP_ID); form.append('sourceRef', 'character-training');
                const imported = await fetch('/v1/platform/gallery/assets/import', { method: 'POST', credentials: 'same-origin', body: form, headers: { Accept: 'application/json' } });
                const importedPayload = await imported.json().catch(() => ({}));
                if (!imported.ok) throw new Error(importedPayload?.error?.message || importedPayload?.detail || tr('readaloud.error.training_upload', { status: imported.status }));
                await request('/voice-profiles', { method: 'POST', body: { name: draft.name.trim(), source_type: draft.sourceType, reference_transcript: draft.referenceTranscript.trim(), reference_asset_id: importedPayload.asset.id, rights_scope: { consent_confirmed: draft.consentConfirmed, usage_rights_confirmed: draft.usageRightsConfirmed, prohibited_impersonation_acknowledged: draft.antiImpersonationAcknowledged } } });
                if (this.trainingAudioUrl) URL.revokeObjectURL(this.trainingAudioUrl);
                this.trainingAudioUrl = ''; this.trainingForm = { name: '', sourceType: 'self_voice', referenceTranscript: '', audioFile: null, consentConfirmed: false, usageRightsConfirmed: false, antiImpersonationAcknowledged: false };
                await this.refresh(); this.success(tr('readaloud.success.training_saved'));
            } catch (error) { this.fail(error); } finally { this.savingTraining = false; this.icons(); }
        },

        async openProject(id, switchView = true) { if (!id) { this.selected = null; this.selectedProjectId = ''; return; } this.busy = true; try { this.selected = await request('/projects/' + encodeURIComponent(id)); this.selectedProjectId = id; if (switchView && this.pipelineMode === 'voice') this.pipelineMode = 'audiobook'; this.icons(); } catch (error) { this.fail(error); } finally { this.busy = false; } },
        async createProject() { this.busy = true; try { const created = await request('/projects', { method: 'POST', body: { title: this.projectForm.title, purpose: this.projectForm.purpose, source_rights: this.projectForm.sourceRights, source_text: this.projectForm.sourceText } }); this.showProjectForm = false; this.projectForm = { title: '', purpose: 'private', sourceRights: 'user_owned', sourceText: '' }; this.selectedProjectId = created.id; await this.refresh(); this.success(tr('readaloud.success.project_created')); } catch (error) { this.fail(error); } finally { this.busy = false; } },
        async saveProject() { if (!this.selected) return; try { this.selected = await request('/projects/' + encodeURIComponent(this.selected.id), { method: 'PATCH', body: { title: this.selected.title, purpose: this.selected.purpose, source_rights: this.selected.sourceRights, source_text: this.selected.sourceText } }); const item = this.projects.find(project => project.id === this.selected.id); if (item) Object.assign(item, this.selected); this.success(tr('readaloud.success.project_saved')); } catch (error) { this.fail(error); } },
        async createCharacter() { if (!this.selected) return; try { await request('/projects/' + encodeURIComponent(this.selected.id) + '/characters', { method: 'POST', body: { name: this.characterForm.name, description: this.characterForm.description, voice_profile_id: this.characterForm.voiceProfileId || null } }); this.characterForm = { name: '', description: '', voiceProfileId: '' }; this.showCharacterForm = false; await this.openProject(this.selected.id, false); this.success(tr('readaloud.success.character_added')); } catch (error) { this.fail(error); } },
        async createSegment() { if (!this.selected) return; try { await request('/projects/' + encodeURIComponent(this.selected.id) + '/segments', { method: 'POST', body: { speaker_id: this.segmentForm.speakerId || null, text: this.segmentForm.text, emotion: this.segmentForm.emotion, emotion_strength: Number(this.segmentForm.emotionStrength), speed: Number(this.segmentForm.speed), pause_after_ms: Number(this.segmentForm.pauseAfterMs) } }); this.segmentForm = { speakerId: '', text: '', emotion: 'neutral', emotionStrength: 1, speed: 1, pauseAfterMs: 300 }; this.showSegmentForm = false; await this.openProject(this.selected.id, false); this.success(tr('readaloud.success.segment_added')); } catch (error) { this.fail(error); } },
        async saveSegment(segment) { if (!this.selected) return; const updated = await request('/projects/' + encodeURIComponent(this.selected.id) + '/segments/' + encodeURIComponent(segment.id), { method: 'PATCH', body: { speaker_id: segment.speakerId || null, text: segment.text, emotion: segment.emotion, emotion_strength: Number(segment.emotionStrength), speed: Number(segment.speed), pause_after_ms: Number(segment.pauseAfterMs) } }); Object.assign(segment, updated); },
        async createVoiceProfile() { try { await request('/voice-profiles', { method: 'POST', body: { name: this.voiceForm.name, source_type: this.voiceForm.sourceType, model_id: this.voiceForm.modelId || null, provider_voice_id: this.voiceForm.providerVoiceId || null, reference_transcript: this.voiceForm.referenceTranscript, rights_scope: { consent_confirmed: this.voiceForm.consentConfirmed, usage_rights_confirmed: this.voiceForm.usageRightsConfirmed, prohibited_impersonation_acknowledged: this.voiceForm.antiImpersonationAcknowledged } } }); this.voiceForm = { name: '', sourceType: 'synthetic_designed', modelId: '', providerVoiceId: '', referenceTranscript: '', consentConfirmed: false, usageRightsConfirmed: false, antiImpersonationAcknowledged: false }; this.showVoiceForm = false; await this.refresh(); this.success(tr('readaloud.success.voice_created')); } catch (error) { this.fail(error); } },

        async preview(segment) {
            if (this.previewing || !segment?.text?.trim()) return;
            this.previewing = segment.id; this.notice = '';
            try {
                await this.saveSegment(segment);
                const capability = await this.ensureCapability('audio.speech_generation', 'configure-preview', segment.id);
                if (capability.configured) { this.success(tr('readaloud.success.speech_configured_retry')); return; }
                const model = this.selectedSpeechProvider;
                const voices = model?.audioCapabilities?.tts?.named_voices?.voices || [];
                const payload = { model: model.id, input: segment.text, response_format: 'wav', speed: Number(segment.speed) || 1 };
                if (voices[0]) payload.voice = voices[0];
                if (segment.emotion && segment.emotion !== 'neutral') payload.style = { emotion: segment.emotion };
                const response = await fetch('/v1/audio/speech', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json', Accept: 'audio/wav' }, body: JSON.stringify(payload) });
                if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body?.error?.message || body?.detail || tr('readaloud.error.speech', { status: response.status })); }
                const url = URL.createObjectURL(await response.blob());
                const item = { id: `${segment.id}-${Date.now()}`, title: segment.text.slice(0, 54), modelName: model.displayName, url };
                this.previewHistory = [item, ...this.previewHistory].slice(0, 20); this.currentAudioUrl = url; this.currentAudioTitle = item.title;
                this.$nextTick(() => this.$refs.audioPlayer?.play().catch(() => {}));
            } catch (error) { this.fail(error); } finally { this.previewing = ''; this.icons(); }
        },
        playHistory(item) { this.currentAudioUrl = item.url; this.currentAudioTitle = item.title; this.$nextTick(() => this.$refs.audioPlayer?.play().catch(() => {})); },
        segmentMeta(segment) { return `${this.emotions.find(item => item.id === segment.emotion)?.name || segment.emotion} · ${tr('readaloud.speed_value', { value: Number(segment.speed || 1).toFixed(2) })}`; },
        voiceName(id) { if (!id) return tr('readaloud.voice_unbound'); const voice = this.voiceProfiles.find(item => item.id === id); return voice ? `${voice.name} · ${this.voiceStatusLabel(voice.status)}` : tr('readaloud.voice_unavailable'); },
        voiceSourceLabel(value) { return tr(value === 'synthetic_designed' ? 'readaloud.voice.synthetic_short' : value === 'self_voice' ? 'readaloud.voice.self' : 'readaloud.voice.authorized_short'); },
        voiceStatusLabel(value) { return tr(value === 'ready' ? 'readaloud.status.ready' : value === 'unverified' ? 'readaloud.status.unverified' : value === 'blocked' ? 'readaloud.status.blocked' : value); },
        capabilitySummary(model) { const audio = model.audioCapabilities || {}; const section = model.modelType === 'audio_tts' ? audio.tts || {} : audio.stt || {}; const names = Object.entries(section).filter(([, value]) => value?.mode && value.mode !== 'unsupported').map(([name]) => name.replaceAll('_', ' ')); return names.length ? names.join(' · ') : (model.capabilities || []).join(' · '); },
    }; };
})();
