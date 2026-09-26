(function () {
    'use strict';
    const API = '/v1/platform/readaloud';
    const APP_ID = 'ai2apps.readaloud';
    const GALLERY_MINI_FALLBACK_URL = '/admin/app-content/ai2apps.gallery?surface=mini';
    const FALLBACK_MINI_APPS = Object.freeze([
        Object.freeze({ id: 'ai2apps.audio.quick-read', mode: 'quick', key: 'readaloud.pipeline.quick', capability: 'audio.speech_generation', icon: 'volume-2' }),
        Object.freeze({ id: 'ai2apps.audio.voice-design', mode: 'voice', key: 'readaloud.pipeline.voice', capability: 'audio.voice_clone', icon: 'users-round' }),
        Object.freeze({ id: 'ai2apps.audio.audiobook', mode: 'audiobook', key: 'readaloud.pipeline.audiobook', capability: 'audio.speech_generation', icon: 'book-headphones' }),
    ]);

    const PREVIEW_EXAMPLES = Object.freeze({
        zh_short: '你好，很高兴见到你。窗外阳光正好，我们慢慢说，把每句话讲清楚。',
        en_short: "Hello, it's nice to meet you. The sun is shining outside. Let's take our time and speak clearly.",
        zh_long: '清晨，我推开窗户，听见树上的小鸟正在唱歌。街角的面包店刚刚开门，空气里飘来温暖的香气。今天我们准备去河边散步，带上一本书、一瓶水，还有一份简单的午餐。你想先走过那座小桥，还是在树荫下坐一会儿？不用着急，我们有足够的时间。等到夕阳落下，再一起慢慢回家，把路上的故事讲给朋友听。',
        en_long: "This morning, I opened the window and heard birds singing in the trees. The bakery on the corner had just opened, and the air smelled of fresh bread. Today, we are going for a walk by the river. We will bring a book, a bottle of water, and a simple lunch. Would you like to cross the little bridge first, or sit in the shade for a while? There is no need to hurry. When the sun goes down, we can walk home together and tell our friends about the day.",
        mixed_short: "你好，很高兴见到你。窗外阳光正好，我们慢慢说，把每句话讲清楚。\nHello, it's nice to meet you. The sun is shining outside. Let's take our time and speak clearly.",
        mixed_long: "清晨，我推开窗户，听见树上的小鸟正在唱歌。街角的面包店刚刚开门，空气里飘来温暖的香气。今天我们准备去河边散步，带上一本书、一瓶水，还有一份简单的午餐。\nWould you like to cross the little bridge first, or sit in the shade for a while? There is no need to hurry. We have plenty of time to enjoy the view and listen to the water.\n等到夕阳落下，我们再一起慢慢回家，把路上的故事讲给朋友听。\nSometimes, a quiet day with good company is all we need. Let's remember this moment and look forward to our next little adventure."
    });

    function tr(key, values = {}) {
        let text = typeof window.t === 'function' ? window.t(key) : key;
        const waitLabels = {
            'readaloud.source.model': ['分析模型', 'Analysis model'],
            'readaloud.source.default_model': ['系统默认 · Standard tasks（中难度任务）', 'System default · Standard tasks'],
            'readaloud.source.add': ['追加文本', 'Add source text'],
            'readaloud.source.help': ['使用所选 AI 模型分析，参考演员定位、Notes 和插入点前后各 8 行。最多 30,000 字符。确认前不会修改项目。', 'Analyze with the selected AI model using cast roles, Notes and up to 8 lines before and after the insertion point. Maximum 30,000 characters. The project stays unchanged until confirmation.'],
            'readaloud.source.analyze': ['分析文本', 'Analyze text'],
            'readaloud.source.analyzing': ['AI 正在分析，请稍候…', 'AI is analyzing. Please wait…'],
            'readaloud.source.append': ['插入位置：列表末尾', 'Insert at the end'],
            'readaloud.source.after': ['插入位置：第 {number} 行之后', 'Insert after line {number}'],
            'readaloud.source.actors': ['建议新建的演员（可选音色）', 'Suggested new actors (optional voice binding)'],
            'readaloud.source.review': ['审核台词与演员，可修改或移除', 'Review lines and actors; edit or remove as needed'],
            'readaloud.source.apply': ['确认添加到项目', 'Confirm and add to project'],
            'readaloud.source.back': ['重新编辑原文', 'Edit source text'],

            'readaloud.cast.role': ['角色定位', 'Role'],
            'readaloud.cast.role_help': ['角色定位与 Notes 将作为 AI 生成台词和分配说话人的参考。', 'Role and Notes guide AI line generation and speaker assignment.'],
            'readaloud.cast.role.auto': ['自动匹配', 'Automatic matching'],
            'readaloud.cast.role.narrator': ['旁白', 'Narrator'],
            'readaloud.cast.role.female_lead': ['女主角', 'Female lead'],
            'readaloud.cast.role.male_lead': ['男主角', 'Male lead'],
            'readaloud.cast.role.default_male': ['默认男声', 'Default male voice'],
            'readaloud.cast.role.default_female': ['默认女声', 'Default female voice'],

            'readaloud.cast.edit': ['编辑角色', 'Edit character'],
            'readaloud.cast.delete_help': ['删除此项目中的角色？相关台词将重置为未选择角色，并需要重新生成。角色库中的音色不会删除。', 'Delete this project character? Affected lines will have no character assigned and need regeneration. The voice library is kept.'],
            'readaloud.line.stale': ['未更新', 'Needs update'],

            'readaloud.character.delete': ['删除角色', 'Delete character'],
            'readaloud.character.delete_confirm': ['确定删除这个角色？', 'Delete this character?'],
            'readaloud.character.delete_help': ['角色将从角色库移除，使用它的有声书角色将解除音色绑定。已有音频和 Gallery 文件会保留。', 'The character will be removed from the library. Audiobook cast using it will have their voice binding cleared. Existing audio and Gallery files will be kept.'],

            'readaloud.design.example.zh_short': ['中文 · 短', 'Chinese · Short'],
            'readaloud.design.example.zh_long': ['中文 · 长', 'Chinese · Long'],
            'readaloud.design.example.en_short': ['英文 · 短', 'English · Short'],
            'readaloud.design.example.en_long': ['英文 · 长', 'English · Long'],
            'readaloud.design.example.mixed_short': ['中英混合 · 短', 'Chinese + English · Short'],
            'readaloud.design.example.mixed_long': ['中英混合 · 长', 'Chinese + English · Long'],

            'readaloud.line.emotion_fallback': ['当前模型不支持「{emotion}」，生成时将使用自然语气。', 'This model does not support {emotion}; audio will use natural delivery.'],
            'readaloud.models.install_more': ['安装更多模型…', 'Install more models…'],
            'readaloud.models.refreshed': ['模型列表已更新。', 'Model list refreshed.'],
            'readaloud.line.expand': ['展开编辑', 'Expand to edit'],
            'readaloud.line.collapse': ['收起编辑', 'Collapse editor'],
            'readaloud.line.delete': ['删除台词', 'Delete line'],
            'readaloud.dialogue.title': ['完整对话输出', 'Full dialogue output'],
            'readaloud.dialogue.help': ['复用已有音频，生成缺失或已修改的台词，再按顺序和句后间隔合并。', 'Reuse matching audio, generate missing or changed lines, then merge with pauses.'],
            'readaloud.dialogue.generate': ['生成完整对话', 'Generate full dialogue'],
            'readaloud.line.generate': ['生成 / 重新生成', 'Generate / regenerate'],
            'readaloud.line.play': ['播放（设置改变时重新生成）', 'Play (regenerate if settings changed)'],
            'readaloud.line.up': ['上移', 'Move up'],
            'readaloud.line.down': ['下移', 'Move down'],
            'readaloud.line.pause': ['句后间隔（毫秒）', 'Pause after (ms)'],
            'readaloud.line.delete_confirm': ['确定删除这条台词？历史生成音频会保留。', 'Delete this line? Previously generated audio will be kept.'],
            'readaloud.line.model_default': ['模型默认', 'Model default'],
            'readaloud.project.delete': ['删除项目', 'Delete project'],
            'readaloud.project.delete_confirm': ['确定删除这个项目？', 'Delete this project?'],
            'readaloud.project.delete_help': ['项目将从列表中移除。已有生成音频、角色库和 Gallery 素材会保留。', 'The project will be removed from the list. Generated audio, saved voices and Gallery assets are kept.'],
            'readaloud.project.deleted': ['项目已删除', 'Project deleted'],
            'readaloud.training.merge_requirements': ['模型接收一条参考音频；多选素材将自动合并。参考文本：{text}。', 'This model accepts one reference; multiple selected clips will be merged. Reference transcript: {text}.'],
            'readaloud.training.merge_notice': ['所选的 {count} 条素材将按列表顺序合并为一条参考音频，文本也会同步合并。请使用同一人的录音。', 'The {count} selected clips and their transcripts will be combined in list order into one reference. Use recordings of the same speaker.'],
            'readaloud.training.merge_text': ['合并素材时，请为每条音频提供并确认文本；文本可选时也可全部留空。', 'For merged references, provide and confirm every transcript, or leave all transcripts empty when optional.'],
            'readaloud.training.delete_confirm': ['确定移除这条参考语音？', 'Remove this reference audio?'],
            'readaloud.training.delete_help': ['仅从当前角色移除，Gallery 原素材会保留。保存角色后生效。', 'This removes the reference from this character. The Gallery original is kept. Save the character to apply the change.'],
            'readaloud.wait.asr': ['正在识别语音…', 'Transcribing audio…'],
            'readaloud.wait.preview': ['正在生成试听音频…', 'Generating voice preview…'],
            'readaloud.wait.help': ['首次加载模型可能需要较长时间，完成后会自动关闭。', 'The first model load may take a while. This dialog closes when processing finishes.'],
            'readaloud.wait.background': ['在后台继续', 'Continue in background'],
            'readaloud.wait.timeout': ['识别请求超时，请重试。', 'Transcription timed out. Please try again.'],
        };
        if (text === key && waitLabels[key]) text = waitLabels[key][(document.documentElement?.lang || '').startsWith('zh') ? 0 : 1];
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
        expandedLineId: '', lineEditing: false, pendingLineRemoval: null, busy: false, notice: '', noticeTone: '', noticeTimer: null, leftView: 'mini-apps', pipelineMode: 'quick', tab: 'script',
        miniAppDefinitions: [], runs: [], selectedRunId: '', selectedArtifactId: '', runTimer: null, draftTimer: null,
        packageMiniAppId: '', packageMiniAppUrl: '', packageMiniAppMountId: '', packageMiniAppLoading: false, packageMiniAppError: '', packageMiniAppReadiness: {}, packageMiniAppSetupBusy: false,
        leftCollapsed: false, rightCollapsed: false, mobilePanel: 'create',
        audioPlaying: false, audioPosition: 0, audioDuration: 0, previewAudioBlob: null, previewAudioBlobUrl: '',
        quickForm: { text: '', voice: '', speed: 1, asrVerification: true, asrModelId: '' }, configuringQuickAsr: false, configuringProjectAsr: false, quickGenerating: false, quickAudioUrl: '', quickDownloadUrl: '', quickDownloadFormat: 'wav', quickAudioTitle: '', quickStatus: 'idle', quickTasks: [], selectedQuickTaskId: '',
        projects: [], selected: null, selectedProjectId: '', providers: [], voiceProfiles: [], selectedTtsModel: '',
        lineAudioArtifact: null, dialogueJob: null, dialogueTimer: null, dialogueStarting: false, autoPlayRunId: '', previewing: '', configuringSpeech: false, configuringVoice: false, currentAudioUrl: '', currentAudioTitle: '', previewHistory: [],
        designBusy: false, designPreviewUrl: '', designStatus: 'idle', conversionModelId: '', trainingHistory: [], trainingPreviewTitle: '', trainingSamples: [], trainingPreviewUrl: '', trainingPreviewStatus: 'idle', trainingPreviewText: '', trainingPreviewEmotion: 'neutral', trainingPreviewSpeed: 1, trainingBusy: false, autoTrainingAsr: true, trainingAsrModelId: '', configuringTrainingAsr: false,
        transcribingTraining: false, savingTraining: false, recordingTraining: false, trainingAudioUrl: '', trainingRecorder: null, trainingStream: null, trainingChunks: [],
        capabilityProbes: {},
        galleryMiniUrl: '', galleryMiniMountId: '', galleryMiniLoading: false, galleryMiniError: '',
        chatController: null, chatMiniUrl: '', packageChatBridge: null,
        showProjectForm: false, showCharacterForm: false, showSegmentForm: false, showVoiceForm: false,
        projectForm: { title: '', purpose: 'private', sourceRights: 'user_owned', sourceText: '' },
        characterForm: { name: '', description: '', voiceProfileId: '', role: 'auto' },
        segmentForm: { speakerId: '', text: '', emotion: 'neutral', emotionStrength: 1, speed: 1, pauseAfterMs: 300 },
        voiceForm: { profileId: '', description: '', name: '', sourceType: 'synthetic_designed', modelId: '', providerVoiceId: '', referenceTranscript: tr('readaloud.design.sample_text'), consentConfirmed: false, usageRightsConfirmed: false, antiImpersonationAcknowledged: false },
        pendingProjectRemoval: null, deletingProject: false,
        pendingCharacterRemoval: null, deletingCharacter: false,
        showSourceDialog: false, sourceTextDraft: '', sourceProposal: null, sourceBusy: false, sourceApplying: false, sourceError: '', sourceProjectId: '', sourceModelId: '', sourceModels: [], sourceAfterId: null, sourcePosition: '',
        editingCastId: '', castBusy: false, pendingCastRemoval: null,
        pendingSampleRemoval: null,
        waitDialogDismissed: false,
        get voiceWaitKind() {
            if (this.transcribingTraining || this.trainingSamples.some(sample => sample.state === 'running')) return 'asr';
            if (this.trainingBusy || this.quickGenerating || (this.designBusy && this.designStatus === 'running')) return 'preview';
            return '';
        },
        get voiceWaitDetail() {
            if (this.voiceWaitKind === 'asr') return this.trainingSamples.filter(sample => sample.state === 'running').map(sample => sample.name).join(', ');
            return this.pipelineMode === 'training' ? this.trainingForm.name : this.pipelineMode === 'voice' ? this.voiceForm.name : '';
        },
        trainingForm: { profileId: '', modelId: '', name: '', sourceType: 'self_voice', referenceTranscript: '', audioFile: null, assetId: '', resourceHandle: '', assetName: '', mediaType: '', consentConfirmed: false, usageRightsConfirmed: false, antiImpersonationAcknowledged: false },
        tr,
        get miniApps() { return (this.miniAppDefinitions.length ? this.miniAppDefinitions : FALLBACK_MINI_APPS).map(localizedMiniApp); },
        get currentProjects() { return this.projects.filter(project => (project.miniAppId === 'ai2apps.audio.ensemble-drama' ? 'ai2apps.audio.audiobook' : (project.miniAppId || 'ai2apps.audio.audiobook')) === this.currentMiniApp.id); },
        // Output ownership belongs to the Studio, never to the active Mini-App.
        packageOutputBusy: false, studioOutputs: [], selectedOutput: null, outputRefreshSequence: 0,
        async refreshOutputs(preferredUrl = '') {
            const sequence = ++this.outputRefreshSequence;
            const payload = await request('/outputs');
            if (sequence !== this.outputRefreshSequence) return;
            this.studioOutputs = payload.items || [];
            this.selectedOutput = this.studioOutputs.find(item => item.downloadUrl === preferredUrl)
                || this.studioOutputs.find(item => item.id === this.selectedOutput?.id)
                || this.studioOutputs[0] || null;
            this.icons();
        },
        get outputMediaType() { return this.selectedOutput?.mediaType || 'audio/wav'; },
        get outputDownloadUrl() { return this.selectedOutput?.downloadUrl || ''; },
        async refreshQuickHistory() {
            if (this.quickGenerating) return;
            const payload = await request('/quick-read/history');
            const previous = this.quickTasks;
            const selectedUrl = this.quickDownloadUrl;
            this.quickTasks = payload.items || [];
            const selected = this.quickTasks.find(item => item.id === this.selectedQuickTaskId || item.downloadUrl === selectedUrl) || this.quickTasks[0];
            if (selected) this.selectQuickTask(selected, false);
            else { this.selectedQuickTaskId = ''; this.quickAudioUrl = ''; this.quickDownloadUrl = ''; this.quickAudioTitle = ''; this.quickStatus = 'idle'; }
            previous.forEach(item => { if (item.url?.startsWith('blob:')) URL.revokeObjectURL(item.url); });
        },
        selectQuickTask(task, reveal = true) {
            this.selectedQuickTaskId = task.id;
            this.quickAudioUrl = task.url || ''; this.quickDownloadUrl = task.downloadUrl || ''; this.quickAudioTitle = task.title;
            this.quickStatus = task.status; if (reveal) this.showMobilePanel('output'); this.icons();
        },
        get quickExportUrl() { return this.outputDownloadUrl ? this.outputDownloadUrl + '?audio_format=' + encodeURIComponent(this.quickDownloadFormat) : ''; },
        audioTime(value) { const seconds = Math.max(0, Math.floor(Number(value) || 0)); return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`; },
        toggleAudio() { this.linePlayer?.pause(); const player = this.$refs.audioPlayer; if (!player) return; if (player.paused) player.play().catch(error => this.fail(error)); else player.pause(); },
        async prepareAudioDrag(url) {
            this.audioPosition = 0; this.audioDuration = 0; this.audioPlaying = false;
            this.previewAudioBlob = null; this.previewAudioBlobUrl = '';
            if (!url) return;
            try { const response = await fetch(url, { credentials: 'same-origin' }); if (!response.ok) return; const blob = await response.blob(); if (this.outputAudioUrl === url && blob.type.startsWith('audio/')) { this.previewAudioBlob = blob; this.previewAudioBlobUrl = url; } } catch (_) {}
        },
        dragPreviewAudio(event) {
            const url = this.outputDownloadUrl;
            const mediaType = this.outputMediaType;
            const suffix = mediaType.startsWith('video/') ? '.mp4' : '.wav';
            const title = (this.outputAudioTitle || 'voice-studio').replace(/[\\/:*?"<>|]/g, '-').slice(0, 100);
            const name = title.toLowerCase().endsWith(suffix) ? title : title + suffix;
            if (!url || !event.dataTransfer) { event.preventDefault(); return; }
            try {
                const parsed = new URL(url, window.location.origin);
                const match = parsed.pathname.match(/^\/v1\/platform\/sessions\/([^/]+)\/artifacts\/([^/]+)\/download$/);
                if (parsed.origin !== window.location.origin || !match) throw new Error('Invalid audio artifact');
                const reference = { sessionId: decodeURIComponent(match[1]), artifactId: decodeURIComponent(match[2]), name, sourceAppId: APP_ID, mediaType };
                event.dataTransfer.effectAllowed = 'copy';
                event.dataTransfer.setData(mediaType.startsWith('video/') ? 'application/x-ai2apps-video-artifact' : 'application/x-ai2apps-audio-artifact', JSON.stringify(reference));
                event.dataTransfer.setData('text/uri-list', parsed.href);
                event.dataTransfer.setData('text/plain', name);
                const blob = this.previewAudioBlobUrl === this.outputAudioUrl ? this.previewAudioBlob : null;
                if (blob) event.dataTransfer.items.add(new File([blob], name, { type: 'audio/wav' }));
            } catch (error) { event.preventDefault(); this.fail(error); }
        },
        get outputAudioUrl() { return this.outputMediaType.startsWith('audio/') ? this.outputDownloadUrl : ''; },
        get outputAudioTitle() { return this.selectedOutput?.title || ''; },
        get outputStatus() { return this.quickGenerating || this.designBusy || this.trainingBusy || this.runActive || this.packageOutputBusy ? 'running' : this.selectedOutput?.status || 'idle'; },
        async selectQuickAsrModel(event) {
            const value = event.target.value;
            if (value !== '__install_more__') { this.quickForm.asrModelId = value; this.scheduleDraft(); return; }
            event.target.value = this.quickForm.asrModelId || '';
            if (this.configuringQuickAsr) return;
            this.configuringQuickAsr = true;
            try {
                await this.saveDraft();
                const request = this.capabilityRequest('audio.speech_recognition', 'install-quick-read-asr');
                delete request.requirements.modelId;
                const result = await window.AI2AppsCapabilities.ensure(request, {installMore: true});
                await this.finishCapability(result, 'audio.speech_recognition');
                const id = result.provider?.modelId;
                if (this.sttProviders.some(item => item.id === id && item.ready)) this.quickForm.asrModelId = id;
                await this.saveDraft();
                this.success(tr('readaloud.models.refreshed'));
            } catch (error) { if (error.code !== 'provisioning_cancelled') this.fail(error); }
            finally { this.configuringQuickAsr = false; this.icons(); }
        },
        async selectProjectAsrModel(event) {
            const project = this.selected;
            if (!project) return;
            if (event.target.value !== '__install_more__') {
                project.asrModelId = event.target.value;
                await this.saveProject(); return;
            }
            event.target.value = project.asrModelId || '';
            if (this.configuringProjectAsr) return;
            this.configuringProjectAsr = true;
            try {
                const capability = this.capabilityRequest('audio.speech_recognition', 'install-audiobook-asr');
                delete capability.requirements.modelId;
                const result = await window.AI2AppsCapabilities.ensure(capability, {installMore: true});
                await this.finishCapability(result, 'audio.speech_recognition');
                const id = result.provider?.modelId;
                if (this.selected?.id === project.id && this.sttProviders.some(item => item.id === id && item.ready)) {
                    this.selected.asrModelId = id;
                    await this.saveProject();
                }
            } catch (error) { if (error.code !== 'provisioning_cancelled') this.fail(error); }
            finally { this.configuringProjectAsr = false; this.icons(); }
        },
        get quickCharacter() { return this.voiceProfiles.find(item => 'character:' + item.id === this.quickForm.voice); },
        get quickProvider() { return this.quickCharacter ? this.speechProviders.find(item => item.id === this.quickCharacter.modelId) : this.selectedSpeechProvider; },
        quickActorChanged() { if (this.quickCharacter) this.selectedTtsModel = this.quickCharacter.modelId; this.scheduleDraft(); },
        get quickActors() { return this.selectedSpeechProvider?.audioCapabilities?.tts?.named_voices?.voices || []; },
        async generateQuickRead() {
            if (this.quickGenerating || !this.quickForm.text.trim()) return;
            if (this.quickForm.voice.startsWith('character:') && !this.quickCharacter) { this.fail(new Error('Character no longer exists; select another actor.')); return; }
            if (!this.quickProvider?.ready) { if (this.quickCharacter) this.fail(new Error('Configure the character’s bound model in Characters first.')); else await this.configureSpeech(); return; }
            this.waitDialogDismissed = false; this.quickGenerating = true; this.quickStatus = 'running'; this.notice = '';
            this.showMobilePanel('output');
            const title = this.quickForm.text.trim().slice(0, 80);
            const task = { id: 'quick-' + Date.now(), title, status: 'running', url: '', model: this.quickProvider.displayName, actor: this.quickCharacter?.name || this.quickForm.voice || this.quickActors[0] || '', createdAt: new Date().toLocaleString() };
            this.quickTasks.unshift(task); this.selectQuickTask(task);
            try {
                const response = await fetch(API + '/quick-read', {
                    method: 'POST', credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json', ...(appInstanceId() ? { 'X-AI2Apps-App-Instance': appInstanceId() } : {}) },
                    body: JSON.stringify({ text: this.quickForm.text, speed: Number(this.quickForm.speed ?? 1), asr_verification: !!this.quickForm.asrVerification, asr_model_id: this.quickForm.asrVerification ? this.quickForm.asrModelId || null : null, model_id: this.quickProvider.id, voice_profile_id: this.quickCharacter?.id || null, voice: this.quickCharacter ? null : this.quickActors.includes(this.quickForm.voice) ? this.quickForm.voice : null }),
                });
                if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.detail || error.error?.message || tr('readaloud.quick.failed')); }
                const blob = await response.blob();
                if (!blob.size) throw new Error(tr('readaloud.quick.failed'));
                Object.assign(this.quickTasks.find(item => item.id === task.id), { blob, url: URL.createObjectURL(blob), downloadUrl: response.headers.get('X-AI2Apps-Download-URL') || '', status: 'succeeded' });
                if (this.selectedQuickTaskId === task.id) this.selectQuickTask(this.quickTasks.find(item => item.id === task.id));
                await this.refreshOutputs(this.quickTasks.find(item => item.id === task.id)?.downloadUrl);
                if (this.quickTasks.length > 20) this.quickTasks.splice(20).forEach(item => { if (item.url?.startsWith('blob:')) URL.revokeObjectURL(item.url); });
                this.scheduleDraft();
                if (this.pipelineMode === 'quick' && this.selectedQuickTaskId === task.id) this.$nextTick(() => this.$refs.audioPlayer?.play().catch(() => {}));
            } catch (error) { Object.assign(this.quickTasks.find(item => item.id === task.id), { status: 'failed', error: error.message }); if (this.selectedQuickTaskId === task.id) this.quickStatus = 'failed'; this.fail(error); } finally { this.quickGenerating = false; this.icons(); }
        },
        async restoreProject() {
            if (this.pipelineMode === 'quick') { this.selected = null; this.selectedProjectId = ''; this.mobilePanel = 'create'; return; }
            const projectId = this.currentProjects.find(item => item.id === this.selectedProjectId)?.id || this.currentProjects[0]?.id || '';
            await this.openProject(projectId, false);
        },
        get currentMiniApp() { return this.packageMiniAppId ? (this.miniApps.find(item => item.id === this.packageMiniAppId) || this.miniApps[0]) : (this.miniApps.find(item => item.mode === (this.pipelineMode === 'training' ? 'voice' : this.pipelineMode)) || this.miniApps[0]); },
        get miniAppChatEnabled() { return Boolean(window.AI2AppsMiniAppChat && this.currentMiniApp && (this.currentMiniApp.source !== 'package' || this.currentMiniApp.chat?.enabled === true)); },
        get currentRun() { if(this.lineAudioArtifact)return null; return this.runs.find(item => item.id === this.selectedRunId) || this.runs[0] || null; },
        get currentArtifact() { if(this.lineAudioArtifact)return this.lineAudioArtifact; return this.currentRun?.artifacts?.find(item => item.id === this.selectedArtifactId) || this.currentRun?.artifacts?.[0] || null; },
        get runActive() { return ['queued', 'running', 'waiting_input'].includes(this.currentRun?.status); },
        get voiceDesignProviders() { return this.speechProviders.filter(item => (item.capabilities || []).includes('voice_design')); },
        normalizeVoiceDesignBinding() { if (this.voiceForm.modelId && !this.voiceDesignProviders.some(item => item.id === this.voiceForm.modelId)) this.voiceForm.modelId = ''; },
        get speechProviders() { return this.providers.filter(item => item.modelType === 'audio_tts'); },
        get sttProviders() { return this.providers.filter(item => item.modelType === 'audio_stt'); },
        get selectedSpeechProvider() { return this.speechProviders.find(item => item.id === this.selectedTtsModel) || this.speechProviders.find(item => item.ready) || null; },
        get selectedSttProvider() { if (this.pipelineMode === 'training' && this.trainingAsrModelId) return this.sttProviders.find(item => item.id === this.trainingAsrModelId) || null; return this.sttProviders.find(item => item.ready) || this.sttProviders[0] || null; },
        get speechReady() { return Boolean(this.selectedSpeechProvider?.ready); },
        get sttReady() { return Boolean(this.selectedSttProvider?.ready); },
        get voiceCloneReady() { return this.speechProviders.some(item => item.ready && (item.capabilities?.includes('voice_cloning') || item.audioCapabilities?.tts?.voice_profiles?.mode === 'native')); },
        get trainedVoices() { return this.voiceProfiles.filter(item => item.referenceAssetId && (item.training?.samples?.length || item.sourceType !== 'synthetic_designed')); },
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
            window.addEventListener('ai2apps:studio-output-state', event => { if(event.detail?.studioId === APP_ID) this.packageOutputBusy = event.detail.running; });
            window.addEventListener('ai2apps:studio-output', event => { if (event.detail?.studioId === APP_ID) { this.refreshOutputs(event.detail.result?.tracks?.[0]?.downloadUrl || event.detail.result?.downloadUrl || '').catch(error => this.fail(error)); this.rightCollapsed = false; } });
            window.addEventListener('resize', () => this.applyResponsiveLayout());
            this.applyResponsiveLayout();
            try { this.miniAppDefinitions = (await request('/mini-apps')).items || []; } catch (_) {}
            await this.refreshAllPackageMiniAppReadiness();
            const pendingMiniApp = window.AI2AppsStudioMiniApps?.pendingSetup(APP_ID)?.miniAppId;
            const rememberedId = pendingMiniApp || localStorage.getItem('ai2apps.readaloud.active-mini-app');
            const rememberedMiniApp = rememberedId === 'ai2apps.audio.ensemble-drama' ? 'ai2apps.audio.audiobook' : rememberedId;
            const remembered = this.miniApps.find(item => item.id === (rememberedMiniApp === 'ai2apps.audio.character-training' ? 'ai2apps.audio.voice-design' : rememberedMiniApp));
            if (remembered?.source === 'package') await this.mountPackageMiniApp(remembered);
            else if (remembered) this.pipelineMode = remembered.mode;
            await this.refresh();
            if (!this.packageMiniAppId) { await this.loadDraft(this.currentMiniApp.id); if (rememberedMiniApp === 'ai2apps.audio.character-training') { await this.loadDraft(rememberedMiniApp); this.pipelineMode = 'training'; this.showVoiceForm = true; } }
            if (this.leftView === 'assets') this.mountGalleryMini();
            if (this.leftView === 'chat') this.mountMiniAppChat();
            await this.restoreProject();
            await this.refreshRuns();
            await this.refreshQuickHistory();
            await this.refreshTrainingHistory();
            await this.refreshOutputs();
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
            for (const capability of ['audio.speech_generation', 'audio.speech_recognition', 'audio.voice_clone', 'audio.voice_design']) {
                try {
                    const resumed = await window.AI2AppsCapabilities?.resume(APP_ID, { capability });
                    if (resumed?.status !== 'ready' || resumed.outcome !== 'configured') continue;
                    await this.finishCapability(resumed, capability);
                    this.success(tr(capability === 'audio.voice_clone' ? 'readaloud.success.voice_configured' : capability === 'audio.speech_recognition' ? 'readaloud.success.stt_configured' : 'readaloud.success.speech_configured'));
                } catch (error) { this.fail(error); }
            }
        },
        cleanup() { this.linePlayer?.pause(); clearTimeout(this.dialogueTimer); clearTimeout(this.runTimer); clearTimeout(this.draftTimer); this.chatController?.dispose(); this.packageChatBridge?.dispose(); this.quickTasks.forEach(task => { if (task.url) URL.revokeObjectURL(task.url); }); const urls = new Set(this.previewHistory.filter(item => item.local).map(item => item.url)); if (this.trainingAudioUrl?.startsWith('blob:')) urls.add(this.trainingAudioUrl); urls.forEach(url => URL.revokeObjectURL(url)); this.trainingStream?.getTracks().forEach(track => track.stop()); },
        icons() { this.$nextTick(() => window.lucide?.createIcons()); },
        dismissNotice() { clearTimeout(this.noticeTimer); this.noticeTimer = null; this.notice = ''; },
        showNotice(text, tone) {
            this.dismissNotice(); this.notice = text; this.noticeTone = tone; this.icons();
            this.noticeTimer = setTimeout(() => this.dismissNotice(), tone === 'error' ? 8000 : 4000);
        },
        success(text) { this.showNotice(text, 'success'); },
        fail(error) { this.showNotice(error?.message || String(error), 'error'); },
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
                    characters: (this.selected.characters || []).map(item => ({ id: item.id, name: item.name, role: item.role || 'auto', notes: item.description || '', voiceProfileId: item.voiceProfileId || null })),
                    segments: (this.selected.segments || []).slice(0, 30).map(item => ({ id: item.id, speakerId: item.speakerId, text: String(item.text || '').slice(0, 500), emotion: item.emotion, speed: item.speed })),
                } : null,
                draft: this.pipelineMode === 'quick' ? this.quickForm : this.pipelineMode === 'voice' ? this.voiceForm : this.pipelineMode === 'training' ? { ...this.trainingForm, samples:this.trainingSamples.map(({assetId,name,transcript,confirmed,selected,duration,state})=>({assetId,name,transcript,confirmed,selected,duration,state})), audioFile: this.trainingForm.audioFile?.name || null, resourceHandle: undefined } : this.segmentForm,
            };
            const properties = this.pipelineMode === 'quick' ? { text: { type: 'string', maxLength: 10000 }, voice: { type: 'string', enum: this.quickActors } } : ['audiobook', 'drama'].includes(this.pipelineMode)
                ? { projectTitle: { type: 'string', maxLength: 160 }, sourceText: { type: 'string', maxLength: 200000 }, segmentText: { type: 'string', maxLength: 10000 }, emotion: { type: 'string' }, speed: { type: 'number', minimum: .5, maximum: 2 } }
                : { sampleId: { type: 'string', maxLength: 255 }, name: { type: 'string', maxLength: 120 }, referenceTranscript: { type: 'string', maxLength: 20000 } };
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
                if (this.pipelineMode === 'quick') {
                    if (typeof args.text === 'string') this.quickForm.text = args.text.slice(0, 10000);
                    if (typeof args.voice === 'string' && this.quickActors.includes(args.voice)) this.quickForm.voice = args.voice;
                } else if (['audiobook', 'drama'].includes(this.pipelineMode)) {
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
                    if (typeof args.referenceTranscript === 'string') {
                        if (this.pipelineMode === 'training') {
                            const samples = args.sampleId ? this.trainingSamples.filter(item => item.assetId === args.sampleId) : this.selectedTrainingSamples;
                            if (samples.length !== 1) throw new Error('Specify one sampleId to edit its transcript');
                            samples[0].transcript=args.referenceTranscript.slice(0,20000); samples[0].confirmed=false; this.trainingChanged();
                        } else form.referenceTranscript=args.referenceTranscript.slice(0,20000);
                    }
                }
                this.scheduleDraft(); this.icons();
                return { updated: true, state: (await this.describeMiniAppChat()).context };
            }
            if (name === 'run_current') {
                if (this.pipelineMode === 'quick') await this.generateQuickRead();
                else if (this.pipelineMode === 'voice') await this.createVoiceProfile();
                else if (this.pipelineMode === 'training') { if (!this.trainingCanSave) throw new Error('Complete model selection, sample requirements, name and rights confirmation before saving'); await this.saveTrainingMaterial(); }
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
                this.projects = projects.items || []; this.providers = providers.items || []; this.voiceProfiles = voices.items || []; this.normalizeVoiceDesignBinding();
                if (!this.speechProviders.some(item => item.id === this.selectedTtsModel)) this.selectedTtsModel = this.speechProviders.find(item => item.ready)?.id || this.speechProviders[0]?.id || '';
                await this.restoreProject();
                this.icons();
            } catch (error) { this.fail(error); } finally { this.busy = false; }
        },
        async showLeftView(view) { this.leftView = view === 'assets' ? 'assets' : (view === 'chat' && this.miniAppChatEnabled ? 'chat' : 'mini-apps'); if (this.leftView === 'assets' && !this.galleryMiniUrl) await this.mountGalleryMini(); if (this.leftView === 'chat') await this.mountMiniAppChat(); this.icons(); },
        beginCharacter() {
            this.trainingForm = {profileId:'',modelId:'',modelRevision:null,name:'',sourceType:'self_voice',referenceTranscript:'',audioFile:null,assetId:'',resourceHandle:'',assetName:'',mediaType:'',consentConfirmed:false,usageRightsConfirmed:false,antiImpersonationAcknowledged:false};
            this.trainingSamples = [];
            if (this.trainingAudioUrl) URL.revokeObjectURL(this.trainingAudioUrl);
            this.trainingAudioUrl = ''; this.trainingPreviewUrl = ''; this.trainingPreviewTitle = ''; this.trainingPreviewStatus = 'idle';
            this.trainingPreviewText = ''; this.trainingPreviewEmotion = 'neutral'; this.trainingPreviewSpeed = 1;
            this.voiceForm={profileId:'',name:'',sourceType:'synthetic_designed',modelId:'',description:'',referenceTranscript:tr('readaloud.design.sample_text')}; this.designPreviewUrl=''; this.designStatus='idle'; this.conversionModelId=''; this.pipelineMode = 'voice'; this.showVoiceForm = true; this.scheduleDraft(); this.icons(); },
        setCharacterMode(mode) { if (this.recordingTraining) this.stopTrainingRecording(); this.pipelineMode = mode === 'training' ? 'training' : 'voice'; this.scheduleDraft(); this.icons(); },
        get currentCharacterId() { return this.pipelineMode === 'training' ? this.trainingForm.profileId : this.voiceForm.profileId; },
        get characterDeleteBusy() { return this.deletingCharacter || this.designBusy || this.trainingBusy || this.recordingTraining || this.configuringVoice || this.trainingSamples.some(sample => sample.state === 'running'); },
        requestCharacterRemoval() {
            if (!this.currentCharacterId || this.characterDeleteBusy) return;
            const voice = this.voiceProfiles.find(item => item.id === this.currentCharacterId);
            if (voice) this.pendingCharacterRemoval = {id:voice.id, name:voice.name};
        },
        async confirmCharacterRemoval() {
            const target = this.pendingCharacterRemoval;
            if (!target || this.characterDeleteBusy) return;
            this.deletingCharacter = true;
            try {
                await request('/voice-profiles/' + encodeURIComponent(target.id), {method:'DELETE'});
                this.pendingCharacterRemoval = null;
                this.beginCharacter();
                this.closeCharacterForm();
                await this.saveDraft();
                await this.refresh();
            } catch (error) { this.fail(error); }
            finally { this.deletingCharacter = false; }
        },
        closeCharacterForm() { if (this.recordingTraining) this.stopTrainingRecording(); this.pipelineMode = 'voice'; this.showVoiceForm = false; this.scheduleDraft(); },
        async selectMiniApp(id) { const item = this.miniApps.find(value => value.id === id); if (!item) return; if (!this.packageMiniAppId) await this.saveDraft(); localStorage.setItem('ai2apps.readaloud.active-mini-app', item.id); if (this.leftView !== 'chat') this.leftView = 'mini-apps'; if (item.source === 'package') { await this.mountPackageMiniApp(item); if (!this.miniAppChatEnabled && this.leftView === 'chat') this.leftView = 'mini-apps'; return; } this.packageChatBridge?.dispose(); this.packageChatBridge = null; this.packageMiniAppId = ''; this.packageMiniAppUrl = ''; this.packageMiniAppError = ''; this.resetProjectDraft(); this.pipelineMode = item.mode; if (item.mode === 'drama') this.tab = 'script'; if (item.mode === 'voice') this.showVoiceForm = false; await this.loadDraft(item.id); await this.restoreProject(); this.chatController?.changed(); this.emitBridge('mini-app.ready', { miniAppId: item.id, version: item.version }); this.icons(); },
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

        resetProjectDraft() {
            this.selected = null; this.selectedProjectId = '';
            this.showProjectForm = false; this.showCharacterForm = false; this.showSegmentForm = false;
            this.projectForm = { title: '', purpose: 'private', sourceRights: 'user_owned', sourceText: '' };
            this.characterForm = { name: '', description: '', voiceProfileId: '', role: 'auto' };
            this.segmentForm = { speakerId: '', text: '', emotion: 'neutral', emotionStrength: 1, speed: 1, pauseAfterMs: 300 };
        },
        draftPayload() {
            const training = { ...this.trainingForm, audioFile: null, resourceHandle: '' };
            return { trainingSamples: this.trainingSamples.map(({assetId,name,transcript,confirmed,selected,duration}) => ({assetId,name,transcript,confirmed,selected,duration})), trainingPreviewText: this.trainingPreviewText, trainingPreviewEmotion:this.trainingPreviewEmotion, trainingPreviewSpeed:this.trainingPreviewSpeed, autoTrainingAsr: this.autoTrainingAsr, trainingAsrModelId: this.trainingAsrModelId, characterDraftVersion: 1, characterMode: this.pipelineMode === 'training' ? 'training' : 'voice', showVoiceForm: this.showVoiceForm, selectedQuickTaskId: this.quickDownloadUrl?.split('/').at(-2) || this.selectedQuickTaskId, ...(this.pipelineMode === 'quick' ? { quickForm: this.quickForm } : {}), selectedProjectId: this.selectedProjectId, selectedTtsModel: this.selectedTtsModel, tab: this.tab, leftView: this.leftView, leftCollapsed: this.leftCollapsed, rightCollapsed: this.rightCollapsed, mobilePanel: this.mobilePanel, projectForm: this.projectForm, characterForm: this.characterForm, segmentForm: this.segmentForm, voiceForm: this.voiceForm, trainingForm: training, selectedRunId: this.selectedRunId };
        },
        applyDraft(draft = {}) {
            for (const key of ['selectedQuickTaskId', 'selectedProjectId', 'selectedTtsModel', 'tab', 'leftView', 'leftCollapsed', 'rightCollapsed', 'mobilePanel', 'selectedRunId']) if (draft[key] !== undefined) this[key] = draft[key];
            if (this.pipelineMode === 'quick' && draft.quickForm) this.quickForm = { ...this.quickForm, ...draft.quickForm };
            for (const key of ['projectForm', 'characterForm', 'segmentForm', 'voiceForm']) if (draft[key] && typeof draft[key] === 'object') this[key] = { ...this[key], ...draft[key] };
            if (Array.isArray(draft.trainingSamples)) this.trainingSamples = draft.trainingSamples.map(item => ({...item, state: 'idle', error: ''}));
            this.trainingPreviewEmotion = draft.trainingPreviewEmotion || 'neutral';
            this.trainingPreviewSpeed = Number(draft.trainingPreviewSpeed) || 1;
            if (typeof draft.trainingPreviewText === 'string') this.trainingPreviewText = draft.trainingPreviewText;
            if (draft.trainingForm && typeof draft.trainingForm === 'object') this.trainingForm = { ...this.trainingForm, ...draft.trainingForm, audioFile: null, resourceHandle: '' };
            if (!Array.isArray(draft.trainingSamples) && !this.trainingSamples.length && this.trainingForm.assetId) this.trainingSamples = [{assetId:this.trainingForm.assetId,name:this.trainingForm.assetName||tr('readaloud.gallery_asset'),transcript:this.trainingForm.referenceTranscript||'',confirmed:false,selected:true,duration:null,state:'idle',error:''}];
            if (typeof draft.trainingAsrModelId === 'string') this.trainingAsrModelId = draft.trainingAsrModelId;
            if (typeof draft.autoTrainingAsr === 'boolean') this.autoTrainingAsr = draft.autoTrainingAsr;
            if (this.providers.length) this.normalizeVoiceDesignBinding();
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
            if (miniAppId === 'ai2apps.audio.voice-design') {
                this.pipelineMode = payload.draft?.characterMode === 'training' ? 'training' : 'voice';
                this.showVoiceForm = Boolean(payload.draft?.showVoiceForm);
                const profile=this.voiceProfiles.find(item=>item.id===this.voiceForm.profileId);
                const preview=profile?.training?.design?.preview;
                if(preview&&preview.description===this.voiceForm.description&&preview.text===this.voiceForm.referenceTranscript&&preview.model_id===this.voiceForm.modelId&&(preview.emotion||'neutral')===(this.voiceForm.emotion||'neutral')&&(preview.speed||1)===(Number(this.voiceForm.speed)||1)) {this.designPreviewUrl=preview.download_url||'';this.designStatus='succeeded';}
                if (!payload.draft?.characterDraftVersion && !payload.draft?.trainingForm?.assetId && !payload.draft?.trainingForm?.name) {
                    const legacy = await request('/drafts/ai2apps.audio.character-training');
                    if (legacy.draft?.trainingForm) this.applyDraft({ trainingForm: legacy.draft.trainingForm });
                }
            }
        },

        async acceptGalleryMessage(event) {
            if (event.origin !== window.location.origin || event.data?.type !== 'ai2apps.gallery.asset-selected') return;
            try { await this.useGalleryAsset(event.data.asset); } catch (error) { this.fail(error); }
        },
        async acceptGalleryDrop(event) {
            event.preventDefault();
            if (this.pipelineMode === 'training' && event.dataTransfer?.files?.[0]?.type.startsWith('audio/')) { await this.importTrainingFile(event.dataTransfer.files[0]); return; }
            const raw = event.dataTransfer?.getData('application/x-ai2apps-gallery-asset');
            if (!raw) return;
            const asset = { id: raw, name: event.dataTransfer?.getData('text/plain') || tr('readaloud.gallery_asset'), mediaType: 'audio/*' };
            await this.useGalleryAsset(asset); this.emitBridge('gallery.asset.drop', { assetId: raw });
        },
        async useGalleryAsset(asset) {
            if (!asset?.id) return;
            const payload = await request('/training/materials/from-gallery/' + encodeURIComponent(asset.id), {method:'POST'});
            this.addTrainingSample(payload.asset); this.mobilePanel = 'create'; this.icons();
        },
        async importTrainingFile(file) {
            if (!file) return;
            const form = new FormData(); form.append('file', file, file.name);
            const response = await fetch(API + '/training/materials', { method:'POST', credentials:'same-origin', body:form });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(payload?.detail || tr('readaloud.error.training_upload', {status:response.status}));
            this.addTrainingSample(payload.asset); this.icons();
        },

        capabilityRequest(capability, action, resumeToken = '') {
            const voice = capability === 'audio.voice_clone';
            const design = capability === 'audio.voice_design';
            const recognition = capability === 'audio.speech_recognition';
            const modelId = (voice || design) ? '' : recognition ? (this.selectedSttProvider?.id || '') : (this.selectedSpeechProvider?.id || '');
            const effectiveResumeToken = resumeToken || globalThis.crypto?.randomUUID?.() || `readaloud-${Date.now()}-${Math.random().toString(36).slice(2)}`;
            return {
                appId: APP_ID, capability, actionId: action,
                requirements: { operations: design ? ['speech_generation', 'voice_design'] : [voice ? 'voice_cloning' : recognition ? 'speech_recognition' : 'speech_generation'], ...(recognition ? {} : { outputFormats: ['wav'] }), ...(modelId ? { modelId } : {}) },
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
                const modelId = result.provider?.modelId;
                if (this.pipelineMode === 'quick' && this.sttProviders.some(item => item.id === modelId && item.ready)) this.quickForm.asrModelId = modelId;
                if (this.pipelineMode === 'training' && this.sttProviders.some(item => item.id === modelId && item.ready)) this.trainingAsrModelId = modelId;
                if (!this.sttReady) throw new Error(tr('readaloud.error.stt_provider_missing'));
            } else if (capability === 'audio.voice_design') {
                if (!this.voiceDesignProviders.some(item => item.ready)) throw new Error(tr('readaloud.design.not_ready'));
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
        async selectDesignModel(event) {
            const value = event.target.value;
            if (value !== '__install_more__') {
                this.voiceForm.modelId = value;
                this.designChanged();
                return;
            }
            event.target.value = this.voiceForm.modelId;
            if (this.configuringVoice || this.designBusy) return;
            this.configuringVoice = true;
            try {
                await this.saveDraft();
                const result = await window.AI2AppsCapabilities.ensure(
                    this.capabilityRequest('audio.voice_design', 'install-more-voice-design-models'),
                    { installMore: true },
                );
                await this.finishCapability(result, 'audio.voice_design');
                this.success(tr('readaloud.models.refreshed'));
            } catch (error) {
                if (error.code !== 'provisioning_cancelled') this.fail(error);
            } finally { this.configuringVoice = false; this.icons(); }
        },
        async selectCloneModel(event, target) {
            const value = event.target.value;
            if (value !== '__install_more__') {
                if (target === 'training') { this.trainingForm.modelId = value; this.trainingModelChanged(); }
                else this.conversionModelId = value;
                return;
            }
            event.target.value = target === 'training' ? this.trainingForm.modelId : this.conversionModelId;
            if (this.configuringVoice) return;
            this.configuringVoice = true;
            try {
                await this.saveDraft();
                const result = await window.AI2AppsCapabilities.ensure(
                    this.capabilityRequest('audio.voice_clone', 'install-more-voice-clone-models'),
                    { installMore: true },
                );
                await this.finishCapability(result, 'audio.voice_clone');
                this.success(tr('readaloud.models.refreshed'));
            } catch (error) {
                if (error.code !== 'provisioning_cancelled') this.fail(error);
            } finally { this.configuringVoice = false; this.icons(); }
        },
        async configureVoiceClone() { if (this.configuringVoice) return; this.configuringVoice = true; try { const result = await this.ensureCapability('audio.voice_clone', 'configure-voice-clone'); this.success(tr(result.configured ? 'readaloud.success.voice_configured' : 'readaloud.voice_already_ready')); } catch (error) { this.fail(error); } finally { this.configuringVoice = false; } },

        setTrainingAudio(file) {
            if (!file) return;
            if (!String(file.type || '').startsWith('audio/')) { this.fail(new Error(tr('readaloud.error.training_audio_type'))); return; }
            if (this.trainingAudioUrl) URL.revokeObjectURL(this.trainingAudioUrl);
            this.trainingForm.audioFile = file;
            this.trainingAudioUrl = URL.createObjectURL(file);
        },
        async selectTrainingAudio(event) { for (const file of Array.from(event?.target?.files || [])) { try { await this.importTrainingFile(file); } catch (error) { this.fail(error); } } event.target.value = ''; },
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
        runTaskMenu(event, run) { window.AI2AppsStudioTaskMenu.open(event,{disabled:!['draft','succeeded','failed','cancelled','expired'].includes(run.status),onDelete:()=>this.deleteRunTask(run)}); },
        async deleteRunTask(run) { try { await request('/runs/'+encodeURIComponent(run.id),{method:'DELETE'});if(this.selectedRunId===run.id){this.selectedRunId='';this.selectedArtifactId='';this.currentAudioUrl='';} await this.refresh(); }catch(error){this.fail(error);} },
        audioTaskMenu(event, task) { window.AI2AppsStudioTaskMenu.open(event,{disabled:task.status==='running'||task.status==='queued',onDelete:()=>this.deleteAudioTask(task)}); },
        async deleteAudioTask(task) {
            try {
                if(task.downloadUrl) {
                    const id=task.downloadUrl.split('/').at(-2);
                    await request('/audio-history/'+encodeURIComponent(id),{method:'DELETE'});
                }
                if(this.trainingPreviewUrl===task.downloadUrl){this.trainingPreviewUrl='';this.trainingPreviewTitle='';this.trainingPreviewStatus='idle';}
                if(this.designPreviewUrl===task.downloadUrl){this.designPreviewUrl='';this.designStatus='idle';}
                if(this.selectedQuickTaskId===task.id){this.selectedQuickTaskId='';this.quickDownloadUrl='';this.quickAudioUrl='';this.quickStatus='idle';}

                this.quickTasks=this.quickTasks.filter(item=>item.id!==task.id);
                this.trainingHistory=this.trainingHistory.filter(item=>item.id!==task.id);
                await this.refreshQuickHistory(); await this.refreshTrainingHistory(); await this.refreshOutputs(); this.scheduleDraft(); this.icons();
            } catch(error){this.fail(error);}
        },
        get audioTasks() { return this.studioOutputs; },
        audioTaskSelected(task) { return this.selectedOutput?.id === task.id; },
        selectAudioTask(task) { this.linePlayer?.pause(); this.selectedOutput = task; this.showMobilePanel('output'); this.icons(); },
        audioTaskTime(value) { const date=new Date(value);return Number.isNaN(date.getTime())?value:date.toLocaleString(); },
        async refreshTrainingHistory() { const payload = await request('/training/history'); this.trainingHistory = payload.items || []; if (!this.trainingPreviewUrl && this.trainingHistory.length && !(this.showVoiceForm && !this.trainingForm.profileId)) this.selectTrainingPreview(this.trainingHistory[0]); },
        selectTrainingPreview(item) { this.trainingPreviewUrl=item.downloadUrl;this.trainingPreviewTitle=item.title;this.trainingPreviewStatus='succeeded'; },
        get trainingProviders() { return this.providers.filter(item => item.trainingRequirements); },
        get trainingProvider() { return this.trainingProviders.find(item => item.id === this.trainingForm.modelId); },
        get trainingSpec() { return this.trainingProvider?.trainingRequirements || null; },
        get trainingMergesSamples() { return this.trainingSpec?.method === 'reference' && this.trainingSpec?.maxSamples === 1 && this.selectedTrainingSamples.length > 1; },
        get selectedTrainingSamples() { return this.trainingSamples.filter(item => item.selected); },
        trainingSampleUrl(sample) { return `${API}/training/materials/${encodeURIComponent(sample.assetId)}/content`; },
        trainingChanged() { this.trainingPreviewUrl = ''; this.trainingPreviewStatus = 'idle'; this.scheduleDraft(); },
        trainingModelChanged() { this.trainingForm.modelRevision = this.trainingSpec?.revision || ''; this.trainingChanged(); },
        addTrainingSample(asset) {
            if (this.trainingSamples.some(item => item.assetId === asset.id)) return;
            if (this.trainingSamples.length >= 50) throw new Error(tr('readaloud.training.limit'));
            const sample = { assetId: asset.id, name: asset.name || this.trainingForm.assetName, transcript: '', confirmed: false, selected: true, duration: null, state: 'idle', error: '' };
            this.trainingSamples.push(sample); this.trainingChanged();
            if (this.autoTrainingAsr && this.sttReady) this.transcribeTrainingSample(sample);
        },
        requestSampleRemoval(sample) { this.pendingSampleRemoval = {assetId:sample.assetId,name:sample.name}; },
        confirmSampleRemoval() {
            const sample = this.pendingSampleRemoval;
            this.pendingSampleRemoval = null;
            if (sample) this.removeTrainingSample(sample);
        },
        removeTrainingSample(sample) { this.trainingSamples = this.trainingSamples.filter(item => item.assetId !== sample.assetId); this.trainingChanged(); },
        async selectTrainingAsrModel(event) {
            const value = event.target.value;
            if (value !== '__install_more__') { this.trainingAsrModelId = value; this.scheduleDraft(); return; }
            event.target.value = this.trainingAsrModelId || '';
            if (this.configuringTrainingAsr) return;
            this.configuringTrainingAsr = true;
            try {
                await this.saveDraft();
                const request = this.capabilityRequest('audio.speech_recognition', 'install-training-asr');
                delete request.requirements.modelId;
                const result = await window.AI2AppsCapabilities.ensure(request, {installMore: true});
                await this.finishCapability(result, 'audio.speech_recognition');
                const id = result.provider?.modelId;
                if (this.sttProviders.some(item => item.id === id && item.ready)) this.trainingAsrModelId = id;
                await this.saveDraft();
                this.success(tr('readaloud.models.refreshed'));
            } catch (error) { if (error.code !== 'provisioning_cancelled') this.fail(error); }
            finally { this.configuringTrainingAsr = false; this.icons(); }
        },
        async transcribeTrainingSample(sample) {
            // Automatic imports pass a raw object; always mutate Alpine's reactive sample.
            sample = this.trainingSamples.find(item => item.assetId === sample.assetId);
            if (!sample || sample.state === 'running') return;
            if (!this.transcribingTraining && !this.trainingSamples.some(item => item.state === 'running')) this.waitDialogDismissed = false;
            sample.state = 'running'; sample.error = '';
            const original = sample.transcript;
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 180000);
            try {
                await this.ensureCapability('audio.speech_recognition', 'configure-training-asr');
                if (!this.selectedSttProvider) throw new Error(tr('readaloud.error.stt_provider_missing'));
                const source = await fetch(this.trainingSampleUrl(sample), {credentials:'same-origin', signal:controller.signal});
                if (!source.ok) throw new Error(tr('readaloud.error.gallery_load'));
                const blob = await source.blob();
                const form = new FormData(); form.append('file', blob, sample.name); form.append('model', this.selectedSttProvider.id); form.append('response_format', 'json');
                const response = await fetch('/v1/audio/transcriptions', { method:'POST', credentials:'same-origin', body:form, signal:controller.signal });
                const payload = await response.json().catch(() => ({}));
                if (!response.ok) throw new Error(payload?.error?.message || payload?.detail || tr('readaloud.error.transcription', {status:response.status}));
                // Do not overwrite an edit made while ASR was in flight.
                if (sample.transcript === original && this.trainingSamples.includes(sample)) { sample.transcript = String(payload.text || '').trim(); sample.confirmed = false; }
                sample.state = 'idle'; this.trainingChanged();
            } catch (error) { sample.state = 'failed'; sample.error = controller.signal.aborted ? tr('readaloud.wait.timeout') : error.message; }
            finally { clearTimeout(timeout); this.scheduleDraft(); }
        },
        async transcribeTrainingAudio() {
            if (this.transcribingTraining) return;
            this.waitDialogDismissed = false; this.transcribingTraining = true;
            try { for (const sample of [...this.trainingSamples]) if (!sample.transcript.trim() && this.trainingSamples.includes(sample)) await this.transcribeTrainingSample(sample); }
            finally { this.transcribingTraining = false; }
        },
        get trainingIssues() {
            const spec = this.trainingSpec, chosen = this.selectedTrainingSamples, issues = [];
            if (!spec) return [tr('readaloud.training.choose_model')];
            if (this.trainingForm.modelRevision != null && this.trainingForm.modelRevision !== spec.revision) issues.push(tr('readaloud.training.revision_changed'));
            if (chosen.length < spec.minSamples || (!this.trainingMergesSamples && spec.maxSamples != null && chosen.length > spec.maxSamples)) issues.push(tr('readaloud.training.count_issue', {min:spec.minSamples,max:spec.maxSamples ?? '∞'}));
            for (const sample of chosen) {
                if (sample.duration != null && ((!this.trainingMergesSamples && spec.minSeconds != null && sample.duration < spec.minSeconds) || (spec.maxSeconds != null && sample.duration > spec.maxSeconds))) issues.push(sample.name + ': ' + tr('readaloud.training.duration_issue'));
            }
            const total = chosen.reduce((sum,item) => sum + (item.duration || 0),0);
            if (chosen.every(item => item.duration != null) && ((spec.minTotalSeconds != null && total < spec.minTotalSeconds) || (spec.maxTotalSeconds != null && total > spec.maxTotalSeconds))) issues.push(tr('readaloud.training.duration_issue'));
            if (this.trainingMergesSamples && chosen.every(item => item.duration != null) && (total > 600 || (spec.minSeconds != null && total < spec.minSeconds) || (spec.maxSeconds != null && total > spec.maxSeconds))) issues.push(tr('readaloud.training.duration_issue'));
            return issues;
        },
        get trainingCanSave() { return !this.recordingTraining && !this.transcribingTraining && !this.trainingSamples.some(item => item.state === 'running') && !this.trainingIssues.length && this.trainingForm.name.trim() && (this.trainingForm.sourceType==='synthetic_designed' || (this.trainingForm.consentConfirmed && this.trainingForm.usageRightsConfirmed && this.trainingForm.antiImpersonationAcknowledged)); },
        get trainingPreviewIssues() {
            const issues = [...this.trainingIssues];
            if (this.recordingTraining || this.transcribingTraining || this.trainingSamples.some(item=>item.state==='running')) issues.push(tr('readaloud.training.wait_materials'));
            if (!this.trainingForm.name.trim()) issues.push(tr('readaloud.training.name_needed'));
            if (this.trainingForm.sourceType!=='synthetic_designed' && !(this.trainingForm.consentConfirmed && this.trainingForm.usageRightsConfirmed && this.trainingForm.antiImpersonationAcknowledged)) issues.push(tr('readaloud.training.rights_needed'));
            if (this.trainingSpec) {
                if (!this.trainingSpec.executable) issues.push(tr('readaloud.training.adapter_pending'));
                if (!this.trainingProvider?.ready) issues.push(tr('readaloud.training.model_not_ready'));
                for (const sample of this.selectedTrainingSamples) {
                    if (this.trainingSpec.transcript==='required' && !sample.transcript.trim()) issues.push(tr('readaloud.training.text_needed',{name:sample.name}));
                    else if (sample.transcript.trim() && !sample.confirmed) issues.push(tr('readaloud.training.confirm_needed',{name:sample.name}));
                }
            }
            if (this.trainingMergesSamples && this.selectedTrainingSamples.some(item=>item.transcript.trim()) && this.selectedTrainingSamples.some(item=>!item.transcript.trim())) issues.push(tr('readaloud.training.merge_text'));
            return issues;
        },
        get trainingCanPreview() { return !this.trainingPreviewIssues.length; },
        trainingPayload() { const draft = this.trainingForm; return {profile_id:draft.profileId||null,name:draft.name.trim(),source_type:draft.sourceType,model_id:draft.modelId,model_revision:draft.modelRevision??null,samples:this.trainingSamples.map(item => ({asset_id:item.assetId,transcript:item.transcript,confirmed:item.confirmed,selected:item.selected})),emotion:this.trainingPreviewEmotion, speed:Number(this.trainingPreviewSpeed), preview_text:this.trainingPreviewText.trim() || tr('readaloud.design.sample_text'),rights_scope:{consent_confirmed:draft.consentConfirmed,usage_rights_confirmed:draft.usageRightsConfirmed,prohibited_impersonation_acknowledged:draft.antiImpersonationAcknowledged}}; },
        async previewTrainingVoice() {
            if (!this.trainingCanPreview || this.trainingBusy) return;
            this.waitDialogDismissed = false; this.trainingBusy = true; this.trainingPreviewStatus = 'running'; this.showMobilePanel('output');
            const payload = this.trainingPayload(); let fingerprint = JSON.stringify(payload);
            try {
                const saved = await request('/training/profiles', {method:'POST',body:payload});
                if (fingerprint !== JSON.stringify(this.trainingPayload())) { this.trainingPreviewStatus = 'idle'; return; }
                this.trainingForm.profileId = saved.id; payload.profile_id = saved.id;
                fingerprint = JSON.stringify(this.trainingPayload()); this.scheduleDraft();
                const response = await fetch(API + '/training/preview', {method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
                if (!response.ok) { const error = await response.json(); throw new Error(error.detail || error.error?.message || tr('readaloud.quick.failed')); }
                if (fingerprint === JSON.stringify(this.trainingPayload())) { this.trainingPreviewUrl = response.headers.get('X-AI2Apps-Download-URL'); this.trainingPreviewStatus = 'succeeded'; this.trainingPreviewTitle = payload.name; await this.refreshTrainingHistory(); await this.refreshOutputs(this.trainingPreviewUrl); this.voiceProfiles = (await request('/voice-profiles')).items || []; }
            } catch(error) { this.trainingPreviewStatus = 'failed'; this.fail(error); } finally { this.trainingBusy = false; }
        },
        editTrainingVoice(voice) {
            this.trainingForm = {profileId:voice.id,modelId:voice.modelId,modelRevision:voice.training?.model_revision,name:voice.name,sourceType:voice.sourceType,consentConfirmed:false,usageRightsConfirmed:false,antiImpersonationAcknowledged:false};
            this.trainingSamples = (voice.training?.samples || []).map(item => ({assetId:item.asset_id,name:item.name,transcript:item.transcript,confirmed:item.confirmed,selected:item.selected,duration:item.duration,state:'idle',error:''}));
            this.pipelineMode='training';this.showVoiceForm=true;this.trainingChanged();this.icons();
        },
        async saveTrainingMaterial() {
            if (!this.trainingCanSave || this.savingTraining) return;
            this.savingTraining = true;
            const form = this.trainingForm, payload = this.trainingPayload();
            try {
                const saved = await request('/training/profiles', {method:'POST',body:payload});
                this.voiceProfiles = [saved, ...this.voiceProfiles.filter(voice => voice.id !== saved.id)];
                if (this.trainingForm === form) {
                    this.trainingForm.profileId = saved.id;
                    if (this.trainingForm.modelId === payload.model_id) this.trainingForm.modelRevision = saved.training?.model_revision ?? this.trainingForm.modelRevision;
                    this.scheduleDraft();
                }
                this.success(tr('readaloud.success.training_saved'));
            } catch(error) { this.fail(error); } finally { this.savingTraining=false; this.icons(); }
        },
        toggleLine(id) { this.expandedLineId = this.expandedLineId === id ? '' : id; },
        async openProject(id, switchView = true) {
            if (this.selected?.id !== id) this.expandedLineId = '';
            const miniAppId = this.currentMiniApp.id;
            if (!id || !this.currentProjects.some(project => project.id === id)) { this.selected = null; this.selectedProjectId = ''; return; }
            this.busy = true;
            this.selectedProjectId = id;
            try {
                const project = await request('/projects/' + encodeURIComponent(id));
                if (this.currentMiniApp.id !== miniAppId || this.selectedProjectId !== id) return;
                this.selected = project;
                this.loadDialogue(id);
                this.icons();
            } catch (error) { this.fail(error); } finally { this.busy = false; }
        },
        requestProjectRemoval() { if (this.selected && !this.runActive) this.pendingProjectRemoval = {id:this.selected.id,title:this.selected.title}; },
        async confirmProjectRemoval() {
            if (!this.pendingProjectRemoval || this.deletingProject) return;
            const project = this.pendingProjectRemoval;
            this.deletingProject = true;
            try {
                await request('/projects/' + encodeURIComponent(project.id), {method:'PATCH',body:{status:'archived'}});
                this.projects = this.projects.filter(item => item.id !== project.id);
                if (this.selectedProjectId === project.id) { this.selectedProjectId = ''; this.selected = null; await this.restoreProject(); }
                this.pendingProjectRemoval = null; this.scheduleDraft(); this.success(tr('readaloud.project.deleted'));
            } catch(error) { this.pendingProjectRemoval = null; this.fail(error); }
            finally { this.deletingProject = false; this.icons(); }
        },
        async createProject() { this.busy = true; try { const created = await request('/projects', { method: 'POST', body: { mini_app_id: this.currentMiniApp.id, title: this.projectForm.title, purpose: this.projectForm.purpose, source_rights: this.projectForm.sourceRights, source_text: this.projectForm.sourceText } }); this.showProjectForm = false; this.projectForm = { title: '', purpose: 'private', sourceRights: 'user_owned', sourceText: '' }; this.selectedProjectId = created.id; await this.refresh(); this.success(tr('readaloud.success.project_created')); } catch (error) { this.fail(error); } finally { this.busy = false; } },
        async saveProject() { if (!this.selected) return; try { this.selected = await request('/projects/' + encodeURIComponent(this.selected.id), { method: 'PATCH', body: { title: this.selected.title, purpose: this.selected.purpose, source_rights: this.selected.sourceRights, source_text: this.selected.sourceText, asr_verification: !!this.selected.asrVerification, asr_model_id: this.selected.asrModelId || '' } }); const item = this.projects.find(project => project.id === this.selected.id); if (item) Object.assign(item, this.selected); this.success(tr('readaloud.success.project_saved')); } catch (error) { this.fail(error); } },
        async loadSourceModels() {
            try {
                const response = await fetch('/v1/models', {credentials:'same-origin',cache:'no-store'});
                if (!response.ok) throw new Error('Model discovery failed: HTTP ' + response.status);
                this.sourceModels = ((await response.json()).data || []).filter(model => {
                    const type = String(model.model_type || model.type || '').toLowerCase();
                    const caps = model.capabilities;
                    return Array.isArray(caps) && caps.length ? caps.some(cap => ['conversation','chat','chat_completions'].includes(String(cap).toLowerCase())) : ['llm','vlm',''].includes(type);
                });
                if (!this.sourceModels.some(model => model.id === this.sourceModelId)) this.sourceModelId = '';
            } catch (error) { this.sourceError = error.message; }
        },
        openSourceDialog() {
            if (!this.selected) return;
            this.sourceProjectId = this.selected.id;
            const index = this.selected.segments.findIndex(line => line.id === this.expandedLineId);
            this.sourceAfterId = index >= 0 ? this.expandedLineId : null;
            this.sourcePosition = index >= 0 ? tr('readaloud.source.after', {number:index+1}) : tr('readaloud.source.append');
            this.sourceProposal = null; this.sourceError = ''; this.showSourceDialog = true;
            this.loadSourceModels();
        },
        async analyzeSource() {
            if (this.sourceBusy || !this.sourceTextDraft.trim()) return;
            this.sourceBusy = true; this.sourceError = ''; this.sourceProposal = null;
            try {
                this.sourceProposal = await request('/projects/' + encodeURIComponent(this.sourceProjectId) + '/source/analyze', {method:'POST', body:{text:this.sourceTextDraft,after_id:this.sourceAfterId,model_id:this.sourceModelId || null}});
            } catch (error) { this.sourceError = error.message; }
            finally { this.sourceBusy = false; }
        },
        async applySource() {
            if (this.sourceApplying || !this.sourceProposal?.lines.length) return;
            this.sourceApplying = true; this.sourceError = '';
            try {
                const {model_id, ...proposal} = this.sourceProposal;
                await request('/projects/' + encodeURIComponent(this.sourceProjectId) + '/source/apply', {method:'POST', body:proposal});
                this.showSourceDialog = false; this.sourceProposal = null; this.sourceTextDraft = '';
                await this.openProject(this.sourceProjectId, false);
            } catch (error) { this.sourceError = error.message; }
            finally { this.sourceApplying = false; }
        },
        openCast(character = null) {
            this.editingCastId = character?.id || '';
            this.characterForm = {role: character?.role || 'auto', name: character?.name || '', description: character?.description || '', voiceProfileId: character?.voiceProfileId || ''};
            this.showCharacterForm = true;
        },
        async createCharacter() {
            if (!this.selected || this.castBusy) return;
            this.castBusy = true;
            try {
                const base = '/projects/' + encodeURIComponent(this.selected.id) + '/characters';
                await request(base + (this.editingCastId ? '/' + encodeURIComponent(this.editingCastId) : ''), {
                    method: this.editingCastId ? 'PATCH' : 'POST',
                    body: {role:this.characterForm.role || 'auto', name:this.characterForm.name, description:this.characterForm.description, voice_profile_id:this.characterForm.voiceProfileId || null},
                });
                this.showCharacterForm = false; this.editingCastId = '';
                await this.openProject(this.selected.id, false);
            } catch (error) { this.fail(error); } finally { this.castBusy = false; }
        },
        async deleteCast() {
            if (!this.selected || !this.pendingCastRemoval || this.castBusy) return;
            this.castBusy = true;
            try {
                await request('/projects/' + encodeURIComponent(this.selected.id) + '/characters/' + encodeURIComponent(this.pendingCastRemoval.id), {method:'DELETE'});
                this.pendingCastRemoval = null; this.showCharacterForm = false; this.editingCastId = '';
                await this.openProject(this.selected.id, false);
            } catch (error) { this.fail(error); } finally { this.castBusy = false; }
        },
        get dialogueBusy() { return this.dialogueStarting || ['queued','running'].includes(this.dialogueJob?.status); },
        async loadDialogue(id) {
            clearTimeout(this.dialogueTimer); this.dialogueJob = null;
            try { const result = await request('/projects/' + encodeURIComponent(id) + '/dialogue'); if(this.selected?.id !== id)return; this.dialogueJob=result?.job || null; if(this.dialogueBusy)this.pollDialogue(id); } catch(error){this.fail(error);}
        },
        pollDialogue(projectId) {
            clearTimeout(this.dialogueTimer);
            const jobId=this.dialogueJob?.id;
            if(!jobId)return;
            this.dialogueTimer=setTimeout(async()=>{try {
                const job=await request('/render-jobs/'+encodeURIComponent(jobId));
                if(this.selected?.id!==projectId||this.dialogueJob?.id!==jobId)return;
                this.dialogueJob=job;
                if(this.dialogueBusy)this.pollDialogue(projectId);
            }catch(error){this.fail(error);}},1000);
        },
        async cancelDialogue() {
            if(!this.dialogueJob)return;
            try {this.dialogueJob=await request('/render-jobs/'+encodeURIComponent(this.dialogueJob.id)+'/cancel',{method:'POST'});clearTimeout(this.dialogueTimer);}catch(error){this.fail(error);}
        },
        async generateDialogue() {
            if(!this.selected||this.dialogueBusy||!this.selectedSpeechProvider)return;
            this.dialogueStarting=true;
            const projectId=this.selected.id;
            try {
                for(const line of this.selected.segments){line.reviewStatus='approved';await this.saveSegment(line);}
                const run=await request('/runs',{method:'POST',body:{miniAppId:this.currentMiniApp.id,projectId,modelId:this.selectedSpeechProvider.id,mergeOutput:true,title:this.selected.title+' · '+tr('readaloud.dialogue.title')}});
                this.runs=[run,...this.runs.filter(item=>item.id!==run.id)];
                this.selectRun(run);this.pollRun();
                if(this.selected?.id===projectId){this.dialogueJob={id:run.id,status:run.status};this.pollDialogue(projectId);}
            }catch(error){this.fail(error);}finally{this.dialogueStarting=false;}
        },
        async changeLine(segment, action) {
            if (!this.selected || this.lineEditing || this.runActive) return;
            const projectId = this.selected.id;
            this.lineEditing = true;
            try {
                const base = '/projects/' + encodeURIComponent(projectId) + '/segments/' + encodeURIComponent(segment.id);
                const project = await request(action === 'delete' ? base : base + '/move/' + action, {method:action === 'delete' ? 'DELETE' : 'POST'});
                if (this.selected?.id === projectId) this.selected = project;
                this.pendingLineRemoval = null;
                this.scheduleDraft(); this.icons();
            } catch (error) { this.fail(error); }
            finally { this.lineEditing = false; }
        },
        async createSegment() { if (!this.selected) return; try { await request('/projects/' + encodeURIComponent(this.selected.id) + '/segments', { method: 'POST', body: { speaker_id: this.segmentForm.speakerId || null, text: this.segmentForm.text, emotion: this.segmentForm.emotion, emotion_strength: Number(this.segmentForm.emotionStrength), speed: Number(this.segmentForm.speed), pause_after_ms: Number(this.segmentForm.pauseAfterMs) } }); this.segmentForm = { speakerId: '', text: '', emotion: 'neutral', emotionStrength: 1, speed: 1, pauseAfterMs: 300 }; this.showSegmentForm = false; await this.openProject(this.selected.id, false); this.success(tr('readaloud.success.segment_added')); } catch (error) { this.fail(error); } },
        async saveSegment(segment) { if (!this.selected) return; const updated = await request('/projects/' + encodeURIComponent(this.selected.id) + '/segments/' + encodeURIComponent(segment.id), { method: 'PATCH', body: { speaker_id: segment.speakerId || null, text: segment.text, emotion: segment.emotion, emotion_strength: Number(segment.emotionStrength), speed: Number(segment.speed), pause_after_ms: Number(segment.pauseAfterMs), ...(segment.reviewStatus ? { review_status: segment.reviewStatus } : {}) } }); Object.assign(segment, updated); this.scheduleDraft(); },
        openVoice(voice) { if (voice.training?.samples?.length) { this.editTrainingVoice(voice); return; } const design=voice.training?.design||{}; this.voiceForm={emotion:design.preview?.emotion||'neutral',speed:design.preview?.speed||1,profileId:voice.id,name:voice.name,sourceType:'synthetic_designed',modelId:voice.modelId||'',description:design.description||'',referenceTranscript:voice.referenceTranscript||tr('readaloud.design.sample_text')}; this.pipelineMode='voice';this.showVoiceForm=true;this.designPreviewUrl=design.preview?.download_url||'';this.designStatus=this.designPreviewUrl?'succeeded':'idle';this.scheduleDraft(); },
        previewModel(mode) { return mode === 'design' ? this.designProvider : this.providers.find(model=>model.id===this.trainingForm.modelId); },
        previewSpeedCaps(mode) { return this.previewModel(mode)?.audioCapabilities?.tts?.speed || {}; },
        previewSpeedSupported(mode) { const value=this.previewSpeedCaps(mode).mode;return !!value && value!=='unsupported'; },
        previewEmotionWarning(mode) {
            const emotion=mode==='design' ? this.voiceForm.emotion||'neutral' : this.trainingPreviewEmotion;
            const caps=this.previewModel(mode)?.audioCapabilities?.tts?.emotion;
            if(emotion==='neutral'||(caps?.mode && caps.mode!=='unsupported' && caps.values?.includes(emotion)))return '';
            return tr('readaloud.line.emotion_fallback',{emotion:this.emotions.find(item=>item.id===emotion)?.name||emotion});
        },
        useDesignSample(kind) {
            if (this.designBusy || !Object.hasOwn(PREVIEW_EXAMPLES, kind)) return;
            this.voiceForm.referenceTranscript = PREVIEW_EXAMPLES[kind];
            this.designChanged();
        },
        designChanged() { this.designPreviewUrl='';this.designStatus='idle';this.scheduleDraft(); },
        designPayload() { return {profile_id:this.voiceForm.profileId||null,name:this.voiceForm.name,model_id:this.voiceForm.modelId,description:this.voiceForm.description||'',text:this.voiceForm.referenceTranscript,emotion:this.voiceForm.emotion||'neutral',speed:Number(this.voiceForm.speed)||1}; },
        async configureDesignModel() {
            if (this.designBusy || !this.voiceForm.modelId) return;
            this.designBusy = true;
            const modelId = this.voiceForm.modelId;
            try {
                const body = this.capabilityRequest('audio.voice_design', 'configure-design');
                body.requirements = { modelId, operations:['speech_generation','voice_design'], outputFormats:['wav'] };
                const result = await window.AI2AppsCapabilities.ensure(body);
                await this.refresh();
                if (result.outcome === 'configured' && result.session?.id) await window.AI2AppsCapabilities.acknowledge(result.session.id, {appId:APP_ID});
                if (!this.providers.find(item=>item.id===modelId)?.ready) throw new Error(tr('readaloud.design.not_ready'));
            } catch(error) { this.fail(error); } finally { this.designBusy=false; }
        },
        get designProvider() { return this.voiceDesignProviders.find(item=>item.id===this.voiceForm.modelId); },
        get designCanRun() { return this.voiceForm.name.trim() && this.voiceDesignProviders.some(item=>item.id===this.voiceForm.modelId) && this.voiceForm.description?.trim() && this.voiceForm.referenceTranscript.trim(); },
        async createVoiceProfile() { if (!this.designCanRun || this.designBusy) return; try { const profile=await request('/design/profiles',{method:'POST',body:this.designPayload()}); this.voiceForm.profileId=profile.id; this.designStatus=this.designPreviewUrl?'succeeded':'idle'; await this.refresh(); this.success(tr('readaloud.save'));this.scheduleDraft(); } catch(error){this.fail(error);} },
        async previewDesignedVoice() { if (!this.designCanRun || this.designBusy) return;this.waitDialogDismissed=false;this.designBusy=true;this.designStatus='running';this.showMobilePanel('output'); const payload=this.designPayload();try {const profile=await request('/design/preview',{method:'POST',body:payload}); if (JSON.stringify(payload)===JSON.stringify(this.designPayload())) this.openVoice(profile); await this.refresh(); await this.refreshOutputs(profile.training?.design?.preview?.download_url || this.designPreviewUrl);}catch(error){this.designStatus='failed';this.fail(error);}finally{this.designBusy=false;} },
        async convertDesignedVoice() { if (!this.designPreviewUrl||!this.voiceForm.profileId||!this.conversionModelId||this.designBusy)return;this.designBusy=true;try {const profile=await request(`/design/profiles/${encodeURIComponent(this.voiceForm.profileId)}/convert`,{method:'POST',body:{model_id:this.conversionModelId}});await this.refresh();this.editTrainingVoice(profile);}catch(error){this.fail(error);}finally{this.designBusy=false;} },


        async preview(segment, force = false) {
            if (this.previewing || !segment?.text?.trim()) return;
            this.previewing = segment.id; this.notice = '';
            try {
                segment.reviewStatus = 'approved';
                await this.saveSegment(segment);
                if (!force && this.selectedSpeechProvider) {
                    const cached = await request('/projects/' + encodeURIComponent(this.selected.id) + '/segments/' + encodeURIComponent(segment.id) + '/audio?model_id=' + encodeURIComponent(this.selectedSpeechProvider.id));
                    if (cached.audio) {
                        if(cached.audio.url){
                            this.lineAudioArtifact={id:segment.id,name:segment.text.slice(0,54),previewUrl:cached.audio.url,downloadUrl:cached.audio.url};
                            this.$refs.audioPlayer?.pause();
                            this.linePlayer?.pause();
                            this.linePlayer = new Audio(cached.audio.url);
                            await this.linePlayer.play();
                            return;
                        }
                        const run = await request('/runs/' + encodeURIComponent(cached.audio.runId));
                        this.runs = [run, ...this.runs.filter(item => item.id !== run.id)];
                        this.selectRun(run);
                        const artifact = run.artifacts?.find(item => item.metadata?.stepId === segment.id);
                        if (artifact) this.selectArtifact(artifact);
                        else this.$nextTick(() => this.$refs.audioPlayer?.play().catch(error => this.fail(error)));
                        return;
                    }
                }
                const capability = await this.ensureCapability('audio.speech_generation', 'configure-preview', segment.id);
                if (capability.configured) { this.success(tr('readaloud.success.speech_configured_retry')); return; }
                const run = await this.createRun([segment.id], segment.text.slice(0, 54));
                if (!force && run) this.autoPlayRunId = run.id;
            } catch (error) { this.fail(error); } finally { this.previewing = ''; this.icons(); }
        },
        async renderProject() { if (!this.selected) return; for (const segment of this.selected.segments || []) if (segment.reviewStatus !== 'approved') { segment.reviewStatus = 'approved'; await this.saveSegment(segment); } await this.createRun(null, this.selected.title); },
        async createRun(segmentIds = null, title = '') { if (!this.selected || !this.selectedSpeechProvider) return; const run = await request('/runs', { method: 'POST', body: { miniAppId: this.currentMiniApp.id, projectId: this.selected.id, modelId: this.selectedSpeechProvider.id, segmentIds, title: title || this.selected.title } }); this.runs = [run, ...this.runs.filter(item => item.id !== run.id)]; this.selectRun(run); this.emitBridge('mini-app.run.create', { runId: run.id, miniAppId: run.miniAppId }); this.pollRun(); return run; },
        async refreshRuns() { if (!appInstanceId()) return; const payload = await request('/runs?limit=50'); this.runs = payload.items || []; if (!this.runs.some(item => item.id === this.selectedRunId)) this.selectedRunId = this.runs[0]?.id || ''; this.syncArtifactPreview(); if (this.runActive) this.pollRun(); },
        async selectRun(run) { if (!run) return; this.lineAudioArtifact=null; this.selectedRunId = run.id; this.selectedArtifactId = run.artifacts?.[0]?.id || ''; this.mobilePanel = 'output'; await this.syncArtifactPreview(true); this.scheduleDraft(); this.emitBridge('mini-app.run.select', { runId: run.id }); this.icons(); },
        async selectArtifact(artifact) { if (!artifact) return; this.selectedArtifactId = artifact.id; await this.syncArtifactPreview(true); this.emitBridge('mini-app.artifact.select', { artifactId: artifact.id }); this.$nextTick(() => this.$refs.audioPlayer?.play().catch(() => {})); },
        async syncArtifactPreview(reveal = false) { const artifact = this.currentArtifact; if (reveal && artifact?.downloadUrl) await this.refreshOutputs(artifact.downloadUrl); this.currentAudioUrl = artifact?.previewUrl || artifact?.downloadUrl || ''; this.currentAudioTitle = artifact?.name || this.currentRun?.title || ''; },
        pollRun() { clearTimeout(this.runTimer); if (!this.currentRun) return; this.runTimer = setTimeout(async () => { try { const run = await request(`/runs/${encodeURIComponent(this.currentRun.id)}`); const index = this.runs.findIndex(item => item.id === run.id); if (index >= 0) this.runs.splice(index, 1, run); else this.runs.unshift(run); await this.syncArtifactPreview(run.status === 'succeeded'); if (this.autoPlayRunId === run.id && !['queued','running','waiting_input'].includes(run.status)) { this.autoPlayRunId = ''; if (run.status === 'succeeded') this.$nextTick(() => this.$refs.audioPlayer?.play().catch(error => this.fail(error))); } if (['queued', 'running', 'waiting_input'].includes(run.status)) this.pollRun(); else await this.refreshRuns(); } catch (error) { this.fail(error); } this.icons(); }, 900); },
        async cancelRun() { if (!this.currentRun) return; const run = await request(`/runs/${encodeURIComponent(this.currentRun.id)}/cancel`, { method: 'POST' }); const index = this.runs.findIndex(item => item.id === run.id); if (index >= 0) this.runs.splice(index, 1, run); this.icons(); },
        async retryRun() { const source = this.currentRun; if (!source) return; const input = source.input || {}; const run = await request('/runs', { method: 'POST', body: { miniAppId: source.miniAppId, projectId: input.projectId, modelId: input.modelId, segmentIds: input.segmentIds, title: source.title, retryOf: source.id, mergeOutput: !!input.mergeOutput } }); this.runs.unshift(run); this.selectRun(run); this.pollRun(); },
        async addArtifactToGallery(artifact) { const sessionId = artifact?.metadata?.artifactSessionId; const sourceId = artifact?.metadata?.sourceArtifactId || artifact?.metadata?.artifactId || artifact?.sourceId; if (!sessionId || !sourceId) throw new Error(tr('readaloud.error.artifact_unavailable')); const response = await fetch(`/v1/platform/gallery/assets/import-artifact/${encodeURIComponent(sessionId)}/${encodeURIComponent(sourceId)}`, { method: 'POST', credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, body: JSON.stringify({ sourceAppId: APP_ID }) }); const payload = await response.json().catch(() => ({})); if (!response.ok) throw new Error(payload?.error?.message || payload?.detail || tr('readaloud.error.gallery_load')); this.success(tr('readaloud.success.artifact_gallery')); },
        playHistory(item) { this.selectRun(item); this.$nextTick(() => this.$refs.audioPlayer?.play().catch(() => {})); },
        segmentFeature(segment, feature) {
            const character = this.selected?.characters?.find(item => item.id === segment.speakerId);
            const voice = this.voiceProfiles.find(item => item.id === character?.voiceProfileId);
            const model = voice?.modelId ? this.providers.find(item => item.id === voice.modelId) : this.selectedSpeechProvider;
            const mode = model?.audioCapabilities?.tts?.[feature]?.mode;
            return !!mode && mode !== 'unsupported';
        },
        segmentEmotionWarning(segment) {
            if (!segment.emotion || segment.emotion === 'neutral') return '';
            const character = this.selected?.characters?.find(item => item.id === segment.speakerId);
            const voice = this.voiceProfiles.find(item => item.id === character?.voiceProfileId);
            const model = voice?.modelId ? this.providers.find(item => item.id === voice.modelId) : this.selectedSpeechProvider;
            if (!model) return '';
            const capability = model.audioCapabilities?.tts?.emotion;
            if (capability?.mode && capability.mode !== 'unsupported' && (capability.values || []).includes(segment.emotion)) return '';
            return tr('readaloud.line.emotion_fallback', {emotion: this.emotions.find(item => item.id === segment.emotion)?.name || segment.emotion});
        },
        segmentMeta(segment) { return `${this.emotions.find(item => item.id === segment.emotion)?.name || segment.emotion} · ${tr('readaloud.speed_value', { value: Number(segment.speed || 1).toFixed(2) })}`; },
        voiceName(id) { if (!id) return tr('readaloud.voice_unbound'); const voice = this.voiceProfiles.find(item => item.id === id); return voice ? `${voice.name} · ${this.voiceStatusLabel(voice.status)}` : tr('readaloud.voice_unavailable'); },
        voiceSourceLabel(value) { return tr(value === 'synthetic_designed' ? 'readaloud.voice.synthetic_short' : value === 'self_voice' ? 'readaloud.voice.self' : 'readaloud.voice.authorized_short'); },
        voiceStatusLabel(value) { return tr(value === 'ready' ? 'readaloud.status.ready' : value === 'unverified' ? 'readaloud.status.unverified' : value === 'blocked' ? 'readaloud.status.blocked' : value); },
    }; };
})();
