(function () {
    'use strict';

    const API = '/v1/platform/packages';
    const apiKey = '';
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
            'discover.install.restart_local': 'Restart Local',
            'discover.install.restart_later': 'Later',
            'discover.install.pending_restart': 'Installed · Restart Local to activate',
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
            'discover.install.restart_local': '重启 Local',
            'discover.install.restart_later': '稍后',
            'discover.install.pending_restart': '已安装 · 重启 Local 后激活',
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
        };
    }

    function rows(value) {
        if (Array.isArray(value)) return value;
        for (const key of ['items', 'packages', 'results', 'recommendations', 'submissions']) {
            if (Array.isArray(value?.[key])) return value[key];
        }
        return [];
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
            tab: 'discover', type: '', query: '', busy: false, working: '',
            items: [], installed: [], selected: null, message: '', messageTone: 'error',
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
                { value: 'agent', label: tr('discover.filter.agents') },
                { value: 'service', label: tr('discover.filter.services') },
            ]; },
            get visibleItems() {
                const source = this.tab === 'installed' ? this.installed : this.items;
                const query = this.query.trim().toLowerCase();
                return source.filter(item => (!this.type || item.packageType === this.type) &&
                    (!query || (item.displayName + ' ' + item.packageId + ' ' + item.description + ' ' + item.publisherName).toLowerCase().includes(query)));
            },
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
            async init() { await this.reload(); },
            clearMessage() { this.message = ''; this.messageTone = 'error'; },
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
            async loadCatalog() {
                const [catalog, installed] = await Promise.all([
                    request('/catalog/recommendations?limit=48' + (this.type ? '&type=' + encodeURIComponent(this.type) : '')),
                    request('/installed'),
                ]);
                this.items = rows(catalog).map(normalize).filter(item => item.packageId);
                this.installed = rows(installed).map(normalize).filter(item => item.packageId);
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
                    const params = new URLSearchParams({ q: this.query, sort: this.query ? 'relevance' : 'recommended', limit: '48' });
                    if (this.type) params.set('type', this.type);
                    const result = await request('/catalog/search?' + params.toString());
                    this.items = rows(result).map(normalize).filter(item => item.packageId);
                } catch (error) { this.showError(error); }
                finally { this.busy = false; redraw(); }
            },
            async setTab(tab) {
                this.tab = tab; this.clearMessage(); this.query = ''; this.type = '';
                if (tab === 'publish') await this.reload();
                else if (!this.items.length || tab === 'installed') await this.loadCatalog();
                redraw();
            },
            async setType(type) {
                this.type = type;
                if (this.tab === 'discover') await this.search(); else redraw();
            },
            isInstalled(id) { return Boolean(id && this.installed.some(item => item.packageId === id)); },
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
                const installed = this.installedItem(item.packageId) || item;
                if (installed.packageType !== 'app' || !installed.runtimeKey) return;
                window.top.location.href = '/apps/' + encodeURIComponent(installed.runtimeKey);
            },
            openAccount() { window.top.location.href = '/apps/ai2apps.account'; },
            async verifyAdministrator() {
                if (!this.isPlatformAdmin || this.adminPassword.length < 12 || this.working) return;
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
                    this.selected = { ...item, ...normalize(detail), raw: detail };
                } catch (error) { this.showError(error); }
                redraw();
            },
            async install(item, approved) {
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
                    let current = operation;
                    while (current.status === 'pending' || current.status === 'running') {
                        await new Promise(resolve => window.setTimeout(resolve, 750));
                        current = await request('/install-operations/' + encodeURIComponent(operation.operationId));
                        this.installDialog = { ...this.installDialog, ...current, item: item };
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
                this.working = item.packageId; this.clearMessage();
                try {
                    await request('/' + encodeURIComponent(id.namespace) + '/' + encodeURIComponent(id.name) + '/uninstall', { method: 'POST', body: { force: Boolean(force) } });
                    this.success(tr('discover.success.uninstalled', { package: item.displayName }));
                    this.selected = null; await this.loadCatalog();
                } catch (error) {
                    if (error.code === 'app_has_instances' && !force && window.confirm(tr('discover.confirm.force_uninstall'))) {
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
            iconFor(type) { return type === 'agent' ? 'bot' : type === 'service' ? 'server-cog' : 'app-window'; },
            ratingText(item) { return (item.rating || 0).toFixed(1) + ' (' + item.ratingCount + ')'; },
        };
    };
})();
