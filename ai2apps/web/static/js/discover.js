(function () {
    'use strict';

    const API = '/v1/platform/packages';
    const apiKey = '';
    const CATALOG_PAGE_SIZE = 24;
    const LOCAL_PAGE_CURSOR = '__ai2apps_local_page__';
    const fallbackText = {
        en: {
            'discover.action.upgrade': 'Upgrade',
            'discover.action.upgrading': 'Upgrading…',
            'discover.action.verify_upgrade': 'Verify and upgrade',
            'discover.version.local': 'Local {version}',
            'discover.version.cloud': 'Cloud {version}',
            'discover.success.upgraded': '{package} was verified and upgraded.',
            'discover.install.dependency_required': 'A required Runtime must be installed or upgraded first.',
            'discover.install.dependency_install': 'Install dependency',
            'discover.install.dependency_upgrade': 'Upgrade dependency',
            'discover.install.restart_local': 'Restart AI2Apps',
            'discover.install.restart_later': 'Later',
            'discover.install.pending_restart': 'Installed · Restart AI2Apps to activate',
            'discover.publish.auth.title': 'Sign in to publish Packages',
            'discover.publish.auth.description': 'Sign in to AI2Apps Cloud in Account, then refresh this page.',
            'discover.publish.auth.action': 'Open Account',
            'discover.publish.admin.title': 'Administrator verification required',
            'discover.publish.admin.description': 'Verify the current Cloud administrator password. Local does not store it.',
            'discover.publish.admin.password': 'Administrator password',
            'discover.publish.admin.verify': 'Verify administrator',
            'discover.publish.admin.verified': 'administrator verified',
            'discover.publish.admin.verification_required': 'verification required',
            'discover.publish.workflow.reject': 'Reject',
            'discover.publish.review.note_placeholder': 'Required review note',
            'discover.error.reviewer_required': 'This account cannot review Packages.',
            'discover.error.reviewer_level_required': 'Package approval requires the highest reviewer account level.',
            'discover.error.self_approval_not_allowed': 'A reviewer cannot approve their own submission.',
            'discover.error.platform_runtime_required': 'Only the official AI2Apps Runtime can use the large Runtime upload endpoint.',
            'discover.error.review_note_required': 'Enter a review note before approving or rejecting.',
            'discover.error.reserved_publisher_identity': 'The official AI2Apps Publisher identity is reserved.',
            'discover.error.publisher_permission_required': 'Your Publisher role does not allow this operation.',
            'discover.error.invalid_release_transition': 'This submission changed state. Refresh it before continuing.',
            'discover.error.invalid_review_note': 'The review note must contain 1 to 2000 characters.',
            'discover.confirm.reject_submission': 'Reject {package} {version}? The Publisher must submit a new version.',
            'discover.success.admin_verified': 'Administrator verified for 15 minutes.',
            'discover.confirm.delete_checkpoints': 'Also delete the downloaded model checkpoints for {package}? Choose Cancel to keep them and continue uninstalling. Reinstalling after deletion requires downloading them again.',
            'discover.success.uninstalled_with_checkpoints': '{package} was uninstalled and its unused checkpoints were deleted ({size} reclaimed).',
            'discover.success.uninstalled_checkpoints_retained': '{package} was uninstalled. Its checkpoints are still used by another Package and were retained.',
            'discover.success.uninstalled_checkpoint_cleanup_failed': '{package} was uninstalled, but checkpoint cleanup failed: {error}',
            'discover.filter.models': 'Models',
            'discover.filter.mini_apps': 'Mini-Apps',
            'discover.type.model': 'Model',
            'discover.model_category.all': 'All models',
            'discover.model_category.text': 'Text',
            'discover.model_category.speech': 'Speech',
            'discover.model_category.multimodal': 'Multimodal',
            'discover.model_category.image': 'Image',
            'discover.model_category.video': 'Video',
            'discover.model_category.embedding': 'Embedding',
            'discover.model_task.all_speech': 'All speech',
            'discover.model_task.speech_synthesis': 'TTS · Speech synthesis',
            'discover.model_task.speech_recognition': 'ASR · Speech recognition',
            'discover.profile.size': 'Size {value}',
            'discover.profile.memory': 'Memory {value}',
            'discover.profile.speed': 'Speed {value}/5',
            'discover.profile.capability': 'Capability {value}/5',
            'discover.profile.source.manifest': 'Publisher benchmark',
            'discover.profile.source.legacy-map': 'Estimated',
            'discover.action.install_model': 'Install model',
            'discover.action.package_only': 'Package only',
            'discover.success.model_ready': '{package} and its checkpoint are ready.',
            'discover.type.mini-app': 'Mini-App',
            'discover.mini_app_category.all': 'All Mini-Apps',
            'discover.mini_app_category.productivity': 'Productivity',
            'discover.mini_app_category.image': 'Image',
            'discover.mini_app_category.video': 'Video',
            'discover.mini_app_category.audio': 'Audio',
            'discover.mini_app_category.document': 'Document',
            'discover.mini_app_category.automation': 'Automation',
            'discover.mini_app_category.developer': 'Developer',
            'discover.mini_app_category.utility': 'Utilities',
            'discover.pagination.load_more': 'Load more',
            'discover.pagination.loading': 'Loading…',
        },
        zh: {
            'discover.action.upgrade': '升级',
            'discover.action.upgrading': '正在升级…',
            'discover.action.verify_upgrade': '验证并升级',
            'discover.version.local': '本地 {version}',
            'discover.version.cloud': '服务器 {version}',
            'discover.success.upgraded': '{package} 已验证并升级。',
            'discover.install.dependency_required': '需要先安装或升级所需的 Runtime。',
            'discover.install.dependency_install': '安装依赖',
            'discover.install.dependency_upgrade': '升级依赖',
            'discover.install.restart_local': '重启 AI2Apps',
            'discover.install.restart_later': '稍后',
            'discover.install.pending_restart': '已安装 · 重启 AI2Apps 后激活',
            'discover.publish.auth.title': '登录后发布 Package',
            'discover.publish.auth.description': '请先在账户 App 登录 AI2Apps Cloud，然后刷新本页。',
            'discover.publish.auth.action': '打开账户 App',
            'discover.publish.admin.title': '需要管理员验证',
            'discover.publish.admin.description': '请验证当前 Cloud 管理员密码，Local 不会保存密码。',
            'discover.publish.admin.password': '管理员密码',
            'discover.publish.admin.verify': '验证管理员',
            'discover.publish.admin.verified': '管理员已验证',
            'discover.publish.admin.verification_required': '需要验证',
            'discover.publish.workflow.reject': '拒绝',
            'discover.publish.review.note_placeholder': '必填审核意见',
            'discover.error.reviewer_required': '当前账户没有审核 Package 的权限。',
            'discover.error.reviewer_level_required': '批准 Package 需要最高审核账户等级。',
            'discover.error.self_approval_not_allowed': '审核员不能批准自己提交的版本。',
            'discover.error.platform_runtime_required': '大型 Runtime 上传接口仅接受官方 AI2Apps Runtime。',
            'discover.error.review_note_required': '批准或拒绝前请填写审核意见。',
            'discover.error.reserved_publisher_identity': '官方 AI2Apps Publisher 身份为保留身份。',
            'discover.error.publisher_permission_required': '你的 Publisher 角色无权执行此操作。',
            'discover.error.invalid_release_transition': '提交状态已发生变化，请刷新后继续。',
            'discover.error.invalid_review_note': '审核意见长度必须为 1 到 2000 个字符。',
            'discover.confirm.reject_submission': '确定拒绝 {package} {version} 吗？Publisher 必须提交新版本。',
            'discover.success.admin_verified': '管理员已验证，15 分钟内可以继续操作。',
            'discover.confirm.delete_checkpoints': '是否同时删除 {package} 已下载的模型 checkpoint？选择“取消”会保留 checkpoint 并继续卸载；删除后重新安装需要再次下载。',
            'discover.success.uninstalled_with_checkpoints': '{package} 已卸载，并删除了未被其他 Package 使用的 checkpoint（释放 {size}）。',
            'discover.success.uninstalled_checkpoints_retained': '{package} 已卸载；checkpoint 仍被其他 Package 使用，因此已保留。',
            'discover.success.uninstalled_checkpoint_cleanup_failed': '{package} 已卸载，但 checkpoint 清理失败：{error}',
            'discover.filter.models': '模型',
            'discover.filter.mini_apps': 'Mini-App',
            'discover.type.model': '模型',
            'discover.model_category.all': '全部模型',
            'discover.model_category.text': '文本',
            'discover.model_category.speech': '语音',
            'discover.model_category.multimodal': '多模态',
            'discover.model_category.image': '图像',
            'discover.model_category.video': '视频',
            'discover.model_category.embedding': '向量',
            'discover.model_task.all_speech': '全部语音',
            'discover.model_task.speech_synthesis': 'TTS · 语音合成',
            'discover.model_task.speech_recognition': 'ASR · 语音识别',
            'discover.profile.size': '大小 {value}',
            'discover.profile.memory': '内存 {value}',
            'discover.profile.speed': '速度 {value}/5',
            'discover.profile.capability': '能力 {value}/5',
            'discover.profile.source.manifest': 'Publisher 基准',
            'discover.profile.source.legacy-map': '估算',
            'discover.action.install_model': '安装模型',
            'discover.action.package_only': '仅安装 Package',
            'discover.success.model_ready': '{package} 与 Checkpoint 已就绪。',
            'discover.type.mini-app': 'Mini-App',
            'discover.mini_app_category.all': '全部 Mini-App',
            'discover.mini_app_category.productivity': '效率',
            'discover.mini_app_category.image': '图像',
            'discover.mini_app_category.video': '视频',
            'discover.mini_app_category.audio': '音频',
            'discover.mini_app_category.document': '文档',
            'discover.mini_app_category.automation': '自动化',
            'discover.mini_app_category.developer': '开发',
            'discover.mini_app_category.utility': '工具',
            'discover.pagination.load_more': '加载更多',
            'discover.pagination.loading': '正在加载…',
        },
    };

    function tr(key, values) {
        let text = window.t(key);
        if (text === key) {
            const language = String(document.documentElement.lang || 'en').toLowerCase().startsWith('zh') ? 'zh' : 'en';
            text = fallbackText[language][key] || key;
        }
        for (const [name, value] of Object.entries(values || {})) {
            text = text.replaceAll('{' + name + '}', String(value));
        }
        return text;
    }

    async function apiRequest(base, path, options) {
        const headers = { Accept: 'application/json' };
        const instanceId = window.AI2AppsCapabilities?.appInstanceId?.() || '';
        if (instanceId) headers['X-AI2Apps-App-Instance'] = instanceId;
        if (apiKey) headers.Authorization = 'Bearer ' + apiKey;
        if (options && options.body !== undefined) headers['Content-Type'] = 'application/json';
        const response = await fetch(base + path, {
            credentials: 'same-origin', headers: headers, ...(options || {}),
            body: options && options.body !== undefined ? JSON.stringify(options.body) : undefined,
        });
        let value = null;
        try { value = await response.json(); } catch (_) { value = null; }
        if (!response.ok) {
            const envelope = value?.error || value?.detail?.error || value?.detail || {};
            const error = new Error(envelope.message || tr('discover.error.request_failed', { status: response.status }));
            error.code = String(envelope.code || '').toLowerCase();
            error.status = response.status;
            error.details = envelope.details || {};
            throw error;
        }
        return value;
    }

    function request(path, options) { return apiRequest(API, path, options); }

    function packageId(value) {
        return value.packageId || value.package_id || value.id || value.package?.packageId || value.package?.id || '';
    }

    function localizedPackage(pkg, value) {
        const localizations = value.localizations || pkg.localizations || {};
        const locale = String(document.documentElement.lang || 'en').replace('_', '-');
        const normalized = Object.fromEntries(Object.entries(localizations).map(([key, item]) => [key.toLowerCase(), item]));
        const candidates = [locale.toLowerCase(), locale.split('-')[0].toLowerCase()];
        if (/^zh-(hk|mo|hant)$/i.test(locale)) candidates.splice(1, 0, 'zh-tw');
        return candidates.map(key => normalized[key]).find(item => item && typeof item === 'object') || {};
    }

    function normalize(value) {
        const manifest = value.manifest || value.latestRelease?.manifest || value.latest?.manifest || {};
        const pkg = manifest.package || value.package || {};
        const localized = localizedPackage(pkg, value);
        const publisher = value.publisher || value.latestRelease?.publisher || {};
        const id = packageId(value) || pkg.id;
        return {
            raw: value,
            packageId: id,
            runtimeKey: value.runtimeKey || value.runtime_key || '',
            packageType: value.packageType || value.package_type || value.type || pkg.type || 'app',
            displayName: localized.displayName || value.displayName || value.display_name || pkg.displayName || (id ? id.split('/').pop() : 'Package'),
            description: localized.description || value.description || pkg.description || '',
            version: value.version || value.latestVersion || value.latest_release?.version || value.latestRelease?.version || pkg.version || '',
            publisherName: value.publisherName || value.publisher_name || publisher.displayName || publisher.name || '',
            rating: Number(value.ratingAverage || value.rating_average || value.rating?.average || (typeof value.rating === 'number' ? value.rating : 0) || 0),
            ratingCount: Number(value.ratingCount || value.rating_count || value.rating?.count || 0),
            permissions: manifest.permissions || value.permissions || [],
            compatibility: manifest.compatibility || value.compatibility || {},
            installability: value.installability || value.package?.installability || {
                installable: true, blockers: [],
            },
            status: value.status || value.latestRelease?.status || 'published',
            activationStatus: value.activationStatus || value.activation_status || 'active',
            restartScope: value.restartScope || value.restart_scope || null,
            restartRequired: (value.activationStatus || value.activation_status) === 'pending_restart',
            checkpointDeletionAvailable: Boolean(value.checkpointDeletionAvailable || value.checkpoint_deletion_available),
            discovery: value.discovery || manifest.discovery || null,
            modelProfile: value.modelProfile || manifest.modelProfile || null,
            modelInstall: value.modelInstall || manifest.modelInstall || null,
            modelReady: Boolean(value.modelReady || value.model_ready),
            readyModelConfigurationIds: value.readyModelConfigurationIds || value.ready_model_configuration_ids || [],
            miniApps: value.miniApps || manifest.miniApps || [],
            cardId: id,
        };
    }

    function expandPackages(value) {
        return rows(value).map(normalize).filter(item => item.packageId).flatMap(item => [
            item,
            ...(item.miniApps || []).map(component => ({
                ...item,
                cardId: item.packageId + '#' + component.componentId,
                discoveryKind: 'mini-app',
                componentId: component.componentId,
                componentVersion: component.version,
                displayName: component.displayName,
                description: component.description || item.description,
                miniApp: component,
            })),
        ]);
    }

    function rows(value) {
        if (Array.isArray(value)) return value;
        for (const key of ['items', 'packages', 'results', 'recommendations', 'submissions']) {
            if (Array.isArray(value?.[key])) return value[key];
        }
        return [];
    }

    function catalogPage(value) {
        if (Array.isArray(value)) return { items: value, nextCursor: '' };
        const pagination = value?.pagination || {};
        const cursor = value?.nextCursor ?? value?.next_cursor ?? pagination.nextCursor ?? pagination.next_cursor ?? '';
        return { items: rows(value), nextCursor: cursor == null ? '' : String(cursor) };
    }

    function mergeCards(existing, incoming) {
        const merged = [];
        const indexes = new Map();
        for (const item of [...existing, ...incoming]) {
            const key = item.cardId || item.packageId;
            if (!key) continue;
            if (indexes.has(key)) merged[indexes.get(key)] = item;
            else { indexes.set(key, merged.length); merged.push(item); }
        }
        return merged;
    }

    function compareVersions(left, right) {
        const pattern = /^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$/;
        const a = pattern.exec(String(left || '').trim());
        const b = pattern.exec(String(right || '').trim());
        if (!a || !b) {
            return String(left || '').localeCompare(String(right || ''), undefined, {
                numeric: true, sensitivity: 'base',
            });
        }
        for (let index = 1; index <= 3; index += 1) {
            const difference = Number(a[index]) - Number(b[index]);
            if (difference) return difference > 0 ? 1 : -1;
        }
        if (!a[4] && !b[4]) return 0;
        if (!a[4]) return 1;
        if (!b[4]) return -1;
        const aParts = a[4].split('.');
        const bParts = b[4].split('.');
        for (let index = 0; index < Math.max(aParts.length, bParts.length); index += 1) {
            if (aParts[index] === undefined) return -1;
            if (bParts[index] === undefined) return 1;
            if (aParts[index] === bParts[index]) continue;
            const aNumeric = /^\d+$/.test(aParts[index]);
            const bNumeric = /^\d+$/.test(bParts[index]);
            if (aNumeric && bNumeric) return Number(aParts[index]) > Number(bParts[index]) ? 1 : -1;
            if (aNumeric !== bNumeric) return aNumeric ? -1 : 1;
            return aParts[index] > bParts[index] ? 1 : -1;
        }
        return 0;
    }

    function redraw() {
        requestAnimationFrame(function () {
            try { if (window.lucide) window.lucide.createIcons(); } catch (_) { }
        });
    }

    window.discoverApp = function () {
        return {
            tab: 'discover', type: '', modelCategory: '', modelTask: '', miniAppCategory: '', query: '', busy: false, loadingMore: false, working: '',
            items: [], installed: [], nextCursor: '', localRemainder: [], deferredCursor: '', catalogCache: {}, selected: null, message: '', messageTone: 'error',
            installDialog: null,
            publishers: [], localKeys: [], submissions: [], reviewSubmissions: [], publishingContext: null, publishingLoaded: false,
            selectedPublisherId: '', selectedKeyRef: '',
            publisherForm: { displayName: '', namespace: '', kind: 'personal' },
            keyName: '',
            buildForm: { sourcePath: '', outputPath: '/private/tmp/package.ai2app' },
            buildResult: null, submissionDetails: null, reviewNotes: {}, adminPassword: '',
            get filters() { return [
                { value: '', label: tr('discover.filter.all') },
                { value: 'app', label: tr('discover.filter.apps') },
                { value: 'mini-app', label: tr('discover.filter.mini_apps') },
                { value: 'agent', label: tr('discover.filter.agents') },
                { value: 'model', label: tr('discover.filter.models') },
                { value: 'service', label: tr('discover.filter.services') },
            ]; },
            get miniAppFilters() {
                const known = [
                { value: '', icon: 'layout-grid', label: tr('discover.mini_app_category.all') },
                { value: 'productivity', icon: 'list-checks', label: tr('discover.mini_app_category.productivity') },
                { value: 'image', icon: 'image', label: tr('discover.mini_app_category.image') },
                { value: 'video', icon: 'video', label: tr('discover.mini_app_category.video') },
                { value: 'audio', icon: 'audio-lines', label: tr('discover.mini_app_category.audio') },
                { value: 'document', icon: 'files', label: tr('discover.mini_app_category.document') },
                { value: 'automation', icon: 'workflow', label: tr('discover.mini_app_category.automation') },
                { value: 'developer', icon: 'code-2', label: tr('discover.mini_app_category.developer') },
                { value: 'utility', icon: 'wrench', label: tr('discover.mini_app_category.utility') },
                ];
                const available = new Set(this.items.filter(item => this.isMiniApp(item)).flatMap(item => item.miniApp?.categories || []));
                const extra = [...available].filter(value => !known.some(item => item.value === value)).sort().map(value => ({ value, icon: 'shapes', label: value.replaceAll('-', ' ').replace(/\b\w/g, letter => letter.toUpperCase()) }));
                return [...known, ...extra];
            },
            get modelFilters() { return [
                { value: '', icon: 'layout-grid', label: tr('discover.model_category.all') },
                { value: 'text', icon: 'text-cursor-input', label: tr('discover.model_category.text') },
                { value: 'speech', icon: 'audio-lines', label: tr('discover.model_category.speech') },
                { value: 'multimodal', icon: 'scan-eye', label: tr('discover.model_category.multimodal') },
                { value: 'image', icon: 'image', label: tr('discover.model_category.image') },
                { value: 'video', icon: 'video', label: tr('discover.model_category.video') },
                { value: 'embedding', icon: 'binary', label: tr('discover.model_category.embedding') },
            ]; },
            get modelTaskFilters() { return [
                { value: '', icon: 'audio-lines', label: tr('discover.model_task.all_speech') },
                { value: 'speech-synthesis', icon: 'volume-2', label: tr('discover.model_task.speech_synthesis') },
                { value: 'speech-recognition', icon: 'audio-waveform', label: tr('discover.model_task.speech_recognition') },
            ]; },
            get visibleItems() {
                const source = this.tab === 'installed' ? this.installed : this.items;
                const query = this.query.trim().toLowerCase();
                return source.filter(item => this.matchesType(item) && this.matchesModelCategory(item) && this.matchesModelTask(item) && this.matchesMiniAppCategory(item) &&
                    (!query || (item.displayName + ' ' + item.packageId + ' ' + (item.componentId || '') + ' ' + item.description + ' ' + item.publisherName).toLowerCase().includes(query)));
            },
            get installedPackageCount() { return new Set(this.installed.map(item => item.packageId)).size; },
            get hasMore() { return this.tab === 'discover' && Boolean(this.nextCursor); },
            get selectedPublisher() { return this.publishers.find(item => item.id === this.selectedPublisherId) || null; },
            get canReviewPackages() {
                const role = this.publishingContext?.user?.systemRole;
                return role === 'reviewer' || role === 'admin';
            },
            get publishingSignedIn() { return Boolean(this.publishingContext?.user?.id); },
            get isPlatformAdmin() { return this.publishingContext?.user?.systemRole === 'admin'; },
            get adminStepUpActive() {
                const expiresAt = Date.parse(this.publishingContext?.user?.adminStepUpExpiresAt || '');
                return Number.isFinite(expiresAt) && expiresAt > Date.now();
            },
            get selectedLocalKey() { return this.localKeys.find(item => item.keyRef === this.selectedKeyRef) || null; },
            get selectedCloudKey() {
                const fingerprint = this.selectedLocalKey?.fingerprintSha256;
                return (this.selectedPublisher?.keys || []).find(item => item.fingerprintSha256 === fingerprint && item.status === 'active') || null;
            },
            get installPercent() {
                const value = this.installDialog;
                if (!value) return 0;
                if (value.status === 'completed') return 100;
                const total = Math.max(1, Number(value.totalSteps || 1));
                const step = Math.min(total, Math.max(1, Number(value.currentStep || 1)));
                const bytesTotal = Number(value.bytesTotal || 0);
                const withinStep = bytesTotal > 0 ? Math.min(1, Number(value.bytesCompleted || 0) / bytesTotal) : 0;
                return Math.min(99, Math.max(0, ((step - 1 + withinStep) / total) * 100));
            },
            async init() {
                try { this.testCandidatesEnabled = (await request('/test-candidates')).enabled === true; } catch (_) {}
                await this.reload();
                await this.resumeInstallContinuation();
                await this.resumeModelInstall();
            },
            clearMessage() { this.message = ''; this.messageTone = 'error'; },
            testCandidatesEnabled: false, candidatePath: '', candidateReview: null, candidateBusy: false,
            async inspectCandidate() {
                this.candidateBusy = true; this.candidateReview = null;
                try { this.candidateReview = await request('/test-candidates', { method: 'POST', body: { archive_path: this.candidatePath } }); }
                catch (error) { this.showError(error); }
                finally { this.candidateBusy = false; }
            },
            async installCandidate() {
                if (!this.candidateReview || this.candidateBusy) return;
                if (!confirm('Install this signed candidate in Test only? Review the displayed audit before approving. This does not publish the Package.')) return;
                this.candidateBusy = true;
                try {
                    await request('/test-candidates', { method: 'POST', body: { archive_path: this.candidatePath, expected_digest: this.candidateReview.sha256 } });
                    this.candidateReview = null;
                    this.success('Candidate installed in Test only. Open its Studio to view the Mini-Apps.');
                    await this.reload();
                } catch (error) { this.showError(error); }
                finally { this.candidateBusy = false; }
            },
            success(text) { this.message = text; this.messageTone = 'info'; },
            showError(error) {
                const friendly = {
                    repository_metadata_expired: tr('discover.error.repository_metadata_expired'),
                    repository_key_unpinned: tr('discover.error.repository_key_unpinned'),
                    publisher_signature_invalid: tr('discover.error.publisher_signature_invalid'),
                    artifact_digest_mismatch: tr('discover.error.artifact_digest_mismatch'),
                    service_contract_adapter_required: tr('discover.error.service_contract_adapter_required'),
                    authentication_required: tr('discover.error.authentication_required'),
                    cloud_browser_session_required: tr('discover.error.authentication_required'),
                    admin_reauth_required: tr('discover.error.admin_reauth_required'),
                    reviewer_required: tr('discover.error.reviewer_required'),
                    reviewer_level_required: tr('discover.error.reviewer_level_required'),
                    self_approval_not_allowed: tr('discover.error.self_approval_not_allowed'),
                    platform_runtime_required: tr('discover.error.platform_runtime_required'),
                    reserved_publisher_identity: tr('discover.error.reserved_publisher_identity'),
                    publisher_permission_required: tr('discover.error.publisher_permission_required'),
                    invalid_release_transition: tr('discover.error.invalid_release_transition'),
                    invalid_review_note: tr('discover.error.invalid_review_note'),
                    namespace_already_exists: tr('discover.error.namespace_already_exists'),
                    release_already_exists: tr('discover.error.release_already_exists'),
                };
                this.message = friendly[error.code] || error.message || String(error);
                this.messageTone = 'error';
            },
            async reload() {
                this.busy = true; this.clearMessage();
                try {
                    if (this.tab === 'publish') await this.loadPublishing();
                    else await this.loadCatalog();
                } catch (error) {
                    if (this.tab === 'publish') this.publishingLoaded = true;
                    this.showError(error);
                }
                finally { this.busy = false; redraw(); }
            },
            catalogKey() {
                return JSON.stringify([this.type, this.modelCategory, this.modelTask, this.miniAppCategory, this.query.trim(), this.query.trim() ? 'relevance' : 'recommended']);
            },
            async loadCatalogPage(append, force) {
                const key = this.catalogKey();
                const cached = this.catalogCache[key];
                if (!append && !force && cached) {
                    this.items = cached.items;
                    this.nextCursor = cached.nextCursor;
                    this.localRemainder = cached.localRemainder || [];
                    this.deferredCursor = cached.deferredCursor || '';
                    return;
                }
                const cursor = append ? this.nextCursor : '';
                if (append && !cursor) return;
                if (append && cursor === LOCAL_PAGE_CURSOR) {
                    const incoming = this.localRemainder.slice(0, CATALOG_PAGE_SIZE);
                    const remainder = this.localRemainder.slice(CATALOG_PAGE_SIZE);
                    const nextCursor = remainder.length ? LOCAL_PAGE_CURSOR : this.deferredCursor;
                    const entry = {
                        items: mergeCards(this.items, incoming), nextCursor: nextCursor,
                        localRemainder: remainder, deferredCursor: remainder.length ? this.deferredCursor : '',
                    };
                    this.catalogCache = { ...this.catalogCache, [key]: entry };
                    this.items = entry.items;
                    this.nextCursor = entry.nextCursor;
                    this.localRemainder = entry.localRemainder;
                    this.deferredCursor = entry.deferredCursor;
                    return;
                }
                const query = this.query.trim();
                const params = new URLSearchParams({ limit: String(CATALOG_PAGE_SIZE) });
                if (query) {
                    params.set('q', query);
                    params.set('sort', 'relevance');
                }
                if (cursor) params.set('cursor', cursor);
                this.applyCatalogFilters(params);
                const endpoint = query ? '/catalog/search?' : '/catalog/recommendations?';
                let page = catalogPage(await request(endpoint + params.toString()));
                let legacyFallback = false;
                if (!append && !page.nextCursor && page.items.length >= CATALOG_PAGE_SIZE) {
                    const legacyParams = new URLSearchParams(params);
                    legacyParams.set('limit', '100');
                    const legacyPage = catalogPage(await request(endpoint + legacyParams.toString()));
                    if (legacyPage.items.length > page.items.length) {
                        page = legacyPage;
                        legacyFallback = true;
                    }
                }
                const expanded = expandPackages(page.items);
                const incoming = legacyFallback ? expanded.slice(0, CATALOG_PAGE_SIZE) : expanded;
                const localRemainder = legacyFallback ? expanded.slice(CATALOG_PAGE_SIZE) : [];
                const items = append ? mergeCards(this.items, incoming) : mergeCards([], incoming);
                const entry = {
                    items: items,
                    nextCursor: localRemainder.length ? LOCAL_PAGE_CURSOR : page.nextCursor,
                    localRemainder: localRemainder,
                    deferredCursor: localRemainder.length ? page.nextCursor : '',
                };
                this.catalogCache = { ...this.catalogCache, [key]: entry };
                if (key === this.catalogKey()) {
                    this.items = entry.items;
                    this.nextCursor = entry.nextCursor;
                    this.localRemainder = entry.localRemainder;
                    this.deferredCursor = entry.deferredCursor;
                }
            },
            async loadCatalog() {
                const [, installed] = await Promise.all([
                    this.loadCatalogPage(false, true),
                    request('/installed'),
                ]);
                this.installed = expandPackages(installed);
            },
            async loadPublishing() {
                this.publishingLoaded = false;
                this.publishingContext = null;
                this.publishers = [];
                this.submissions = [];
                this.reviewSubmissions = [];
                try {
                    this.publishingContext = await request('/publishing/context');
                    const [publisherResult, keyResult, submissionResult] = await Promise.all([
                        request('/publishing/publishers'), request('/publisher-keys'), request('/publishing/submissions?limit=50'),
                    ]);
                    this.publishers = rows(publisherResult);
                    this.localKeys = rows(keyResult);
                    this.submissions = rows(submissionResult);
                    if (this.canReviewPackages) {
                        this.reviewSubmissions = rows(await request('/publishing/review-submissions?status=review_pending&limit=50'));
                    }
                    if (!this.publishers.some(item => item.id === this.selectedPublisherId)) this.selectedPublisherId = this.publishers[0]?.id || '';
                    if (!this.localKeys.some(item => item.keyRef === this.selectedKeyRef)) this.selectedKeyRef = this.localKeys[0]?.keyRef || '';
                } finally {
                    this.publishingLoaded = true;
                }
            },
            async search() {
                if (this.tab !== 'discover') return;
                this.busy = true; this.clearMessage();
                try {
                    await this.loadCatalogPage(false, false);
                } catch (error) { this.showError(error); }
                finally { this.busy = false; redraw(); }
            },
            async loadMore() {
                if (this.tab !== 'discover' || !this.nextCursor || this.loadingMore) return;
                this.loadingMore = true; this.clearMessage();
                try { await this.loadCatalogPage(true, false); }
                catch (error) { this.showError(error); }
                finally { this.loadingMore = false; redraw(); }
            },
            async setTab(tab) {
                this.tab = tab; this.clearMessage(); this.query = ''; this.type = ''; this.modelCategory = ''; this.modelTask = ''; this.miniAppCategory = '';
                if (tab === 'publish') await this.reload();
                else if (!this.items.length || tab === 'installed') await this.loadCatalog();
                redraw();
            },
            async setType(type) {
                this.type = type;
                this.modelCategory = '';
                this.modelTask = '';
                this.miniAppCategory = '';
                if (this.tab === 'discover') await this.search(); else redraw();
            },
            async setModelCategory(category) {
                this.modelCategory = category;
                this.modelTask = '';
                if (this.tab === 'discover') await this.search(); else redraw();
            },
            async setModelTask(task) {
                this.modelTask = task;
                if (this.tab === 'discover') await this.search(); else redraw();
            },
            async setMiniAppCategory(category) {
                this.miniAppCategory = category;
                if (this.tab === 'discover') await this.search(); else redraw();
            },
            applyCatalogFilters(params) {
                if (this.type === 'model' || this.type === 'service') params.set('content', this.type);
                else if (this.type === 'mini-app') params.set('type', 'app');
                else if (this.type) params.set('type', this.type);
                if (this.type === 'model' && this.modelCategory) params.set('model_category', this.modelCategory);
                if (this.type === 'model' && this.modelTask) params.set('model_task', this.modelTask);
            },
            isModel(item) { return item?.discovery?.kind === 'model'; },
            isMiniApp(item) { return item?.discoveryKind === 'mini-app'; },
            matchesType(item) {
                if (!this.type) return true;
                if (this.type === 'model') return this.isModel(item);
                if (this.type === 'mini-app') return this.isMiniApp(item);
                if (this.type === 'service') return item.packageType === 'service' && !this.isModel(item);
                if (this.type === 'app') return item.packageType === 'app' && !this.isMiniApp(item);
                return item.packageType === this.type && !this.isMiniApp(item);
            },
            matchesModelCategory(item) {
                if (!this.modelCategory) return true;
                const discovery = item?.discovery || {};
                if ((discovery.categories || []).includes(this.modelCategory)) return true;
                return this.modelCategory === 'text'
                    && (discovery.tasks || []).includes('multimodal-conversation');
            },
            matchesModelTask(item) {
                return !this.modelTask || (item?.discovery?.tasks || []).includes(this.modelTask);
            },
            matchesMiniAppCategory(item) {
                return !this.miniAppCategory || (item?.miniApp?.categories || []).includes(this.miniAppCategory);
            },
            isInstalled(id) { return Boolean(id && this.installed.some(item => item.packageId === id)); },
            isModelReady(item) { return Boolean(this.installedItem(item?.packageId)?.modelReady); },
            translate(key, values) { return tr(key, values); },
            installedItem(id) { return this.installed.find(item => item.packageId === id) || null; },
            pendingRestart(item) { return Boolean(this.installedItem(item?.packageId)?.restartRequired); },
            catalogItem(id) { return this.items.find(item => item.packageId === id) || null; },
            localVersion(item) { return this.installedItem(item?.packageId)?.version || ''; },
            cloudVersion(item) { return this.catalogItem(item?.packageId)?.version || (this.tab === 'discover' ? item?.version : '') || ''; },
            hasUpgrade(item) {
                const local = this.localVersion(item);
                const cloud = this.cloudVersion(item);
                return Boolean(local && cloud && compareVersions(cloud, local) > 0);
            },
            localVersionLabel(item) { return tr('discover.version.local', { version: this.localVersion(item) || '—' }); },
            cloudVersionLabel(item) { return tr('discover.version.cloud', { version: this.cloudVersion(item) || '—' }); },
            open(item) {
                if (this.isMiniApp(item)) {
                    const studio = item?.miniApp?.placements?.[0];
                    if (studio) window.top.location.href = '/apps/' + encodeURIComponent(studio);
                    return;
                }
                const installed = this.installedItem(item.packageId) || item;
                if (installed.packageType !== 'app' || !installed.runtimeKey) return;
                window.top.location.href = '/apps/' + encodeURIComponent(installed.runtimeKey);
            },
            openAccount() { window.top.location.href = '/apps/ai2apps.account'; },
            validAccountPassword(value) {
                const bytes = new TextEncoder().encode(String(value || '')).length;
                return bytes >= 8 && bytes <= 128;
            },
            async verifyAdministrator() {
                if (!this.isPlatformAdmin || !this.validAccountPassword(this.adminPassword) || this.working) return;
                this.working = 'admin-reauth'; this.clearMessage();
                try {
                    await request('/publishing/admin/reauth', { method: 'POST', body: { password: this.adminPassword } });
                    this.adminPassword = '';
                    await this.loadPublishing();
                    this.success(tr('discover.success.admin_verified'));
                } catch (error) { this.showError(error); }
                finally { this.adminPassword = ''; this.working = ''; redraw(); }
            },
            split(id) { const parts = String(id || '').split('/'); return { namespace: parts[0], name: parts.slice(1).join('/') }; },
            async openDetails(item) {
                this.selected = item; this.clearMessage(); redraw();
                const id = this.split(item.packageId);
                if (!id.namespace || !id.name) return;
                try {
                    const detail = await request('/catalog/' + encodeURIComponent(id.namespace) + '/' + encodeURIComponent(id.name));
                    const detailed = expandPackages([detail]);
                    const match = item.componentId
                        ? detailed.find(value => value.componentId === item.componentId)
                        : detailed.find(value => !value.componentId);
                    this.selected = { ...item, ...(match || normalize(detail)), raw: detail };
                } catch (error) { this.showError(error); }
                redraw();
            },
            async install(item, approved, packageOnly) {
                if (this.isModel(item) && !packageOnly) return this.installModel(item);
                const id = this.split(item.packageId);
                if (!id.namespace || !id.name || this.working || !this.canInstall(item)) return;
                const upgrading = this.hasUpgrade(item);
                this.working = item.packageId; this.clearMessage();
                this.selected = null;
                this.installDialog = {
                    item: item, operationId: '', packageId: item.packageId,
                    status: 'pending', currentStep: 1, totalSteps: 6,
                    stage: 'preparing', bytesCompleted: null, bytesTotal: null,
                    result: null, error: null,
                };
                redraw();
                try {
                    const operation = await request('/' + encodeURIComponent(id.namespace) + '/' + encodeURIComponent(id.name) + '/install-operations', {
                        method: 'POST', body: { version: item.version || null, approve_review: Boolean(approved) },
                    });
                    this.installDialog = { ...this.installDialog, ...operation, item: item };
                    const transferMeter = window.AI2AppsCapabilities.createTransferMeter();
                    const transferText = value => {
                        const active = value.status === 'running' && String(value.stage).startsWith('downloading_');
                        if (value.download) return window.AI2AppsCapabilities.formatDownloadProgress(value.download, active);
                        return active ? transferMeter(`${value.packageId}:${value.fileName}:${value.bytesTotal}`, value.bytesCompleted, value.bytesTotal) : '';
                    };
                    this.installDialog.transferText = transferText(operation);
                    let current = operation;
                    while (current.status === 'pending' || current.status === 'running') {
                        await new Promise(resolve => window.setTimeout(resolve, 500));
                        current = await request('/install-operations/' + encodeURIComponent(operation.operationId));
                        this.installDialog = { ...this.installDialog, ...current, item: item, transferText: transferText(current) };
                    }
                    if (current.status === 'failed') {
                        const error = new Error(current.error?.message || tr('discover.install.failed'));
                        error.code = String(current.error?.code || 'install_failed').toLowerCase();
                        error.details = current.error?.details || {};
                        throw error;
                    }
                    const installed = current.result;
                    this.success(tr(upgrading ? 'discover.success.upgraded' : 'discover.success.installed', { package: item.displayName }));
                    await this.loadCatalog();
                } catch (error) {
                    if (this.installDialog) {
                        const reviewRequired = error.code === 'audit_review_required';
                        const dependencyRequired = error.code === 'dependency_restart_required';
                        this.installDialog.status = reviewRequired ? 'awaiting_review' : dependencyRequired ? 'dependency_required' : 'failed';
                        this.installDialog.stage = reviewRequired ? 'review_required' : dependencyRequired ? 'dependency_required' : 'failed';
                        this.installDialog.error = { code: error.code || 'install_failed', message: error.message, details: error.details || {} };
                    }
                    if (!['audit_review_required', 'dependency_restart_required'].includes(error.code)) this.showError(error);
                } finally { this.working = ''; redraw(); }
            },
            async installModel(item) {
                const id = this.split(item.packageId);
                if (!id.namespace || !id.name || this.working || !this.canInstall(item)) return;
                this.working = item.packageId; this.clearMessage();
                try {
                    const suffix = item.version ? '?version=' + encodeURIComponent(item.version) : '';
                    const plan = await request('/' + encodeURIComponent(id.namespace) + '/' + encodeURIComponent(id.name) + '/model-install-plan' + suffix);
                    const modelId = await window.AI2AppsCapabilities.chooseProfile(plan);
                    const result = await request('/' + encodeURIComponent(id.namespace) + '/' + encodeURIComponent(id.name) + '/model-install-sessions', {
                        method: 'POST', body: { version: item.version || null, modelId: modelId },
                    });
                    this.selected = null;
                    let completed = result;
                    if (result.status !== 'ready') {
                        completed = await window.AI2AppsCapabilities.runSession(result.session, 'ai2apps.discover');
                    }
                    if (completed?.session) {
                        await window.AI2AppsCapabilities.acknowledge(completed.session, { appId: 'ai2apps.discover' });
                    }
                    this.success(tr('discover.success.model_ready', { package: item.displayName }));
                    await this.loadCatalog();
                } catch (error) {
                    if (!String(error?.message || '').includes('已取消')) this.showError(error);
                } finally { this.working = ''; redraw(); }
            },
            async resumeModelInstall() {
                try {
                    const completed = await window.AI2AppsCapabilities.resume(
                        'ai2apps.discover', { capability: 'model.package.install' }
                    );
                    if (!completed) return;
                    if (completed.session) {
                        await window.AI2AppsCapabilities.acknowledge(completed.session, { appId: 'ai2apps.discover' });
                    }
                    await this.loadCatalog();
                } catch (error) {
                    if (!String(error?.message || '').includes('已取消')) this.showError(error);
                }
            },
            async resumeInstallContinuation() {
                try {
                    const result = await request('/install-continuation');
                    const pending = result?.continuation;
                    if (!pending?.packageId || this.working) return;
                    const installed = this.installedItem(pending.packageId);
                    if (installed && pending.version && compareVersions(installed.version, pending.version) >= 0) {
                        await request('/install-continuation', { method: 'DELETE' });
                        return;
                    }
                    const item = this.catalogItem(pending.packageId) || normalize({
                        packageId: pending.packageId,
                        version: pending.version || '',
                        displayName: pending.packageId,
                        packageType: 'service',
                        description: '',
                    });
                    await this.install(item, pending.approveReview);
                } catch (error) {
                    this.showError(error);
                }
            },
            installStageLabel(value) {
                const stage = String(value?.stage || 'preparing');
                const translated = tr('discover.install.stage.' + stage);
                return translated === 'discover.install.stage.' + stage ? stage.replaceAll('_', ' ') : translated;
            },
            installStepLabel(index) {
                return tr('discover.install.step.' + index);
            },
            closeInstallDialog() {
                if (this.installDialog?.status === 'pending' || this.installDialog?.status === 'running') return;
                this.installDialog = null;
            },
            async retryInstallDialog() {
                const item = this.installDialog?.item;
                const approve = this.installDialog?.status === 'awaiting_review' || this.installDialog?.error?.code === 'audit_review_required';
                this.installDialog = null;
                if (item) await this.install(item, approve);
            },
            requiredDependency() {
                return this.installDialog?.error?.details?.dependency || null;
            },
            requiredDependencyActionLabel() {
                const dependency = this.requiredDependency();
                if (dependency?.pendingRestart) return tr('discover.install.restart_local');
                return tr(dependency?.installedVersion ? 'discover.install.dependency_upgrade' : 'discover.install.dependency_install');
            },
            async installRequiredDependency() {
                const dependency = this.requiredDependency();
                if (!dependency) return;
                if (dependency.pendingRestart) return this.restartLocal();
                const item = this.catalogItem(dependency.packageId) || normalize({
                    packageId: dependency.packageId,
                    packageType: dependency.packageType || 'service',
                    displayName: dependency.displayName || dependency.packageId,
                    version: dependency.availableVersion || '',
                    description: '',
                });
                this.installDialog = null;
                await this.install(item);
            },
            async restartLocal() {
                this.installDialog = null;
                try {
                    const response = await fetch('/v1/platform/client/restart-local', {
                        method: 'POST', credentials: 'same-origin',
                        headers: { Accept: 'application/json' },
                    });
                    if (!response.ok) {
                        let value = null;
                        try { value = await response.json(); } catch (_) { value = null; }
                        throw new Error(value?.detail || value?.error?.message || tr('discover.error.request_failed', { status: response.status }));
                    }
                } catch (error) {
                    // The connection commonly closes while Local restarts.
                    if (error instanceof TypeError) return;
                    this.showError(error);
                }
            },
            finishInstallDialog() {
                const installed = this.installDialog?.result;
                const modelId = installed?.modelConfigurationId;
                this.installDialog = null;
                if (modelId) {
                    localStorage.setItem('ai2apps.pendingModelPackage', modelId);
                    window.top.location.href = '/apps/ai2apps.models';
                }
            },
            async uninstall(item, force) {
                const id = this.split(item.packageId);
                if (!id.namespace || !id.name || this.working) return;
                if (!force && !window.confirm(tr('discover.confirm.uninstall', { package: item.displayName }))) return;
                const installed = this.installedItem(item.packageId) || item;
                const deleteCheckpoints = Boolean(installed.checkpointDeletionAvailable && window.confirm(
                    tr('discover.confirm.delete_checkpoints', { package: item.displayName })
                ));
                this.working = item.packageId; this.clearMessage();
                try {
                    const result = await request('/' + encodeURIComponent(id.namespace) + '/' + encodeURIComponent(id.name) + '/uninstall', {
                        method: 'POST',
                        body: { force: Boolean(force), delete_checkpoints: deleteCheckpoints },
                    });
                    const cleanup = result?.checkpointCleanup;
                    this.success(cleanup?.error
                        ? tr('discover.success.uninstalled_checkpoint_cleanup_failed', {
                            package: item.displayName,
                            error: cleanup.error,
                        })
                        : cleanup?.requested && cleanup?.deletedRepositories?.length
                            ? tr('discover.success.uninstalled_with_checkpoints', {
                            package: item.displayName,
                            size: this.formatBytes(cleanup.reclaimedBytes || 0),
                        })
                            : cleanup?.requested && cleanup?.retainedRepositories?.length
                                ? tr('discover.success.uninstalled_checkpoints_retained', { package: item.displayName })
                                : tr('discover.success.uninstalled', { package: item.displayName }));
                    this.selected = null; await this.loadCatalog();
                } catch (error) {
                    if (['app_has_instances', 'service_has_dependents'].includes(error.code) && !force && window.confirm(tr('discover.confirm.force_uninstall'))) {
                        this.working = ''; return this.uninstall(item, true);
                    }
                    this.showError(error);
                } finally { this.working = ''; redraw(); }
            },
            async createPublisher() {
                if (this.working) return;
                this.working = 'publisher'; this.clearMessage();
                try {
                    const result = await request('/publishing/publishers', { method: 'POST', body: {
                        display_name: this.publisherForm.displayName,
                        namespace: this.publisherForm.namespace,
                        kind: this.publisherForm.kind,
                    } });
                    this.publisherForm = { displayName: '', namespace: '', kind: 'personal' };
                    await this.loadPublishing(); this.selectedPublisherId = result.id;
                    this.success(tr('discover.success.publisher_created'));
                } catch (error) { this.showError(error); }
                finally { this.working = ''; redraw(); }
            },
            async createKey() {
                if (this.working) return;
                this.working = 'key'; this.clearMessage();
                try {
                    const result = await request('/publisher-keys', { method: 'POST', body: { name: this.keyName } });
                    this.keyName = ''; await this.loadPublishing(); this.selectedKeyRef = result.keyRef;
                    this.success(tr('discover.success.key_created'));
                } catch (error) { this.showError(error); }
                finally { this.working = ''; redraw(); }
            },
            async registerSelectedKey() {
                if (!this.selectedPublisher || !this.selectedLocalKey || this.working) return;
                this.working = 'register-key'; this.clearMessage();
                try {
                    const challenge = await request('/publishing/publishers/' + encodeURIComponent(this.selectedPublisher.id) + '/key-challenges', {
                        method: 'POST', body: { key_ref: this.selectedLocalKey.keyRef },
                    });
                    await request('/publishing/publishers/' + encodeURIComponent(this.selectedPublisher.id) + '/keys', {
                        method: 'POST', body: { challenge_id: challenge.challengeId, signature: challenge.proofSignature },
                    });
                    await this.loadPublishing(); this.success(tr('discover.success.key_registered'));
                } catch (error) { this.showError(error); }
                finally { this.working = ''; redraw(); }
            },
            async buildPackage() {
                if (this.working) return;
                this.working = 'build'; this.clearMessage(); this.buildResult = null;
                try {
                    this.buildResult = await request('/build', { method: 'POST', body: {
                        source_path: this.buildForm.sourcePath,
                        output_path: this.buildForm.outputPath,
                    } });
                    this.success(tr('discover.success.built', { package: this.buildResult.package.id, version: this.buildResult.package.version }));
                } catch (error) { this.showError(error); }
                finally { this.working = ''; redraw(); }
            },
            async submitPackage() {
                if (!this.buildResult || !this.selectedPublisher || !this.selectedLocalKey || !this.selectedCloudKey || this.working) return;
                this.working = 'submit'; this.clearMessage();
                try {
                    const envelope = await request('/sign', { method: 'POST', body: {
                        archive_path: this.buildResult.archivePath,
                        key_ref: this.selectedLocalKey.keyRef,
                        publisher_id: this.selectedPublisher.id,
                        publisher_key_id: this.selectedCloudKey.id,
                    } });
                    const submission = await request('/publishing/submissions', { method: 'POST', body: {
                        archive_path: this.buildResult.archivePath, envelope: envelope,
                    } });
                    await this.loadPublishing();
                    this.success(tr('discover.success.submitted', { package: submission.packageId, version: submission.packageVersion }));
                } catch (error) { this.showError(error); }
                finally { this.working = ''; redraw(); }
            },
            async showSubmission(item) {
                this.working = item.id; this.clearMessage();
                try { this.submissionDetails = await request('/publishing/submissions/' + encodeURIComponent(item.id) + '/details'); }
                catch (error) { this.showError(error); }
                finally { this.working = ''; redraw(); }
            },
            async requestReview(item) { await this.submissionAction(item, 'review-request'); },
            async approveSubmission(item) {
                const note = String(this.reviewNotes[item.id] || '').trim();
                if (!note) { this.showError(new Error(tr('discover.error.review_note_required'))); return; }
                await this.submissionAction(item, 'reviews', { decision: 'approved', note: note });
            },
            async rejectSubmission(item) {
                const note = String(this.reviewNotes[item.id] || '').trim();
                if (!note) { this.showError(new Error(tr('discover.error.review_note_required'))); return; }
                if (!window.confirm(tr('discover.confirm.reject_submission', { package: item.packageId, version: item.packageVersion }))) return;
                await this.submissionAction(item, 'reviews', { decision: 'rejected', note: note });
            },
            async publishSubmission(item) { await this.submissionAction(item, 'publication'); },
            async submissionAction(item, action, body) {
                if (this.working) return;
                this.working = item.id; this.clearMessage();
                try {
                    await request('/publishing/submissions/' + encodeURIComponent(item.id) + '/' + action, {
                        method: 'POST', ...(body ? { body: body } : {}),
                    });
                    delete this.reviewNotes[item.id];
                    await this.loadPublishing(); this.success(tr('discover.success.workflow_advanced'));
                } catch (error) { this.showError(error); }
                finally { this.working = ''; redraw(); }
            },
            statusLabel(item) {
                const status = String(item.releaseStatus || item.status || 'candidate');
                const translated = tr('discover.status.' + status);
                return translated === 'discover.status.' + status ? status.replaceAll('_', ' ') : translated;
            },
            statusClass(item) { return 'status-' + String(item.releaseStatus || item.status || 'candidate').replaceAll('_', '-'); },
            shortFingerprint(value) { return value ? value.slice(0, 12) + '…' + value.slice(-8) : '—'; },
            formatBytes(value) { const size = Number(value || 0); return size < 1024 ? size + ' B' : size < 1048576 ? (size / 1024).toFixed(1) + ' KiB' : (size / 1048576).toFixed(1) + ' MiB'; },
            formatTime(value) { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString(); },
            packageTypeLabel(type) { return tr('discover.type.' + (type || 'app')); },
            packageKindLabel(item) { return this.packageTypeLabel(this.isModel(item) ? 'model' : this.isMiniApp(item) ? 'mini-app' : item?.packageType); },
            miniAppCategoryLabel(item) {
                const category = item?.miniApp?.categories?.[0];
                if (!category) return '';
                const key = 'discover.mini_app_category.' + category;
                const label = tr(key);
                return label === key ? category.replaceAll('-', ' ').replace(/\b\w/g, letter => letter.toUpperCase()) : label;
            },
            miniAppPlacementLabel(item) {
                const placements = item?.miniApp?.placements || [];
                return placements.map(value => value.split('.').pop().replaceAll('-', ' ')).join(' · ');
            },
            modelCategoryLabel(item) {
                const category = item?.discovery?.categories?.[0];
                return category ? tr('discover.model_category.' + category) : '';
            },
            primaryModelTask(item) {
                const tasks = item?.discovery?.tasks || [];
                if (tasks.includes('speech-synthesis')) return 'speech_synthesis';
                if (tasks.includes('speech-recognition')) return 'speech_recognition';
                return '';
            },
            primaryModelTaskLabel(item) {
                const task = this.primaryModelTask(item);
                return task ? tr('discover.model_task.' + task) : '';
            },
            modelProfile(item) { return item?.modelProfile || null; },
            formatModelBytes(value) {
                const bytes = Number(value || 0);
                if (!Number.isFinite(bytes) || bytes <= 0) return '—';
                const gib = bytes / (1024 ** 3);
                if (gib >= 1) return gib.toFixed(1).replace('.0', '') + ' GiB';
                const mib = bytes / (1024 ** 2);
                return (mib >= 10 ? mib.toFixed(0) : mib.toFixed(1)).replace('.0', '') + ' MiB';
            },
            modelProfileSizeLabel(item) {
                const profile = this.modelProfile(item);
                const prefix = profile?.source === 'legacy-map' ? '≈' : '';
                return tr('discover.profile.size', { value: prefix + this.formatModelBytes(profile?.sizeBytes) });
            },
            modelProfileMemoryLabel(item) {
                const profile = this.modelProfile(item);
                // Missing runtime evidence must not be replaced with system RAM requirements.
                return tr('discover.profile.memory', { value: profile?.runtimeMemoryBytes ? '≈' + this.formatModelBytes(profile.runtimeMemoryBytes) : '—' });
            },
            modelProfileScoreLabel(item, name) {
                return tr('discover.profile.' + name, { value: this.modelProfile(item)?.scores?.[name] || '—' });
            },
            modelProfileSourceLabel(item) {
                return tr('discover.profile.source.' + (this.modelProfile(item)?.source || 'manifest'));
            },
            modelProfileSourceTitle(item) {
                const benchmark = this.modelProfile(item)?.benchmark;
                return [benchmark?.label, benchmark?.device].filter(Boolean).join(' · ');
            },
            canInstall(item) { return item?.installability?.installable !== false; },
            compatibilityMessage(item) {
                const blocker = item?.installability?.blockers?.[0];
                if (!blocker) return '';
                if (blocker.code === 'os_version_too_old') {
                    return tr('discover.compatibility.os_version_too_old', {
                        minimum: blocker.details?.minimum || '—',
                        current: blocker.details?.current || '—',
                    });
                }
                if (blocker.code === 'platform_incompatible') return tr('discover.compatibility.platform_incompatible');
                if (blocker.code === 'architecture_incompatible') return tr('discover.compatibility.architecture_incompatible');
                if (blocker.code === 'ai2apps_incompatible') return tr('discover.compatibility.ai2apps_incompatible');
                return blocker.message || tr('discover.compatibility.incompatible');
            },
            iconFor(type) { return type === 'model' ? 'brain-circuit' : type === 'mini-app' ? 'panels-top-left' : type === 'agent' ? 'bot' : type === 'service' ? 'server-cog' : 'app-window'; },
            ratingText(item) { return (item.rating || 0).toFixed(1) + ' (' + item.ratingCount + ')'; },
        };
    };
})();
