(function () {
    'use strict';

    const API = '/v1/platform/packages';
    const apiKey = window.AI2APPS_DISCOVER_API_KEY || '';

    async function request(path, options) {
        const headers = { Accept: 'application/json' };
        if (apiKey) headers.Authorization = 'Bearer ' + apiKey;
        if (options && options.body !== undefined) headers['Content-Type'] = 'application/json';
        const response = await fetch(API + path, {
            credentials: 'same-origin', headers: headers, ...(options || {}),
            body: options && options.body !== undefined ? JSON.stringify(options.body) : undefined,
        });
        let value = null;
        try { value = await response.json(); } catch (_) { value = null; }
        if (!response.ok) {
            const error = new Error(value?.error?.message || ('Request failed (HTTP ' + response.status + ')'));
            error.code = String(value?.error?.code || '').toLowerCase();
            error.status = response.status;
            error.details = value?.error?.details || {};
            throw error;
        }
        return value;
    }

    function packageId(value) {
        return value.packageId || value.package_id || value.id || value.package?.id || '';
    }

    function normalize(value) {
        const manifest = value.manifest || value.latestRelease?.manifest || value.latest?.manifest || {};
        const pkg = manifest.package || value.package || {};
        const publisher = value.publisher || value.latestRelease?.publisher || {};
        const id = packageId(value) || pkg.id;
        return {
            raw: value,
            packageId: id,
            runtimeKey: value.runtimeKey || value.runtime_key || '',
            packageType: value.packageType || value.package_type || value.type || pkg.type || 'app',
            displayName: value.displayName || value.display_name || pkg.displayName || (id ? id.split('/').pop() : 'Package'),
            description: value.description || pkg.description || '',
            version: value.version || value.latestVersion || value.latest_release?.version || value.latestRelease?.version || pkg.version || '',
            publisherName: value.publisherName || value.publisher_name || publisher.displayName || publisher.name || '',
            rating: Number(value.ratingAverage || value.rating_average || value.rating?.average || (typeof value.rating === 'number' ? value.rating : 0) || 0),
            ratingCount: Number(value.ratingCount || value.rating_count || value.rating?.count || 0),
            permissions: manifest.permissions || value.permissions || [],
            status: value.status || value.latestRelease?.status || 'published',
        };
    }

    function rows(value) {
        if (Array.isArray(value)) return value;
        for (const key of ['items', 'packages', 'results', 'recommendations', 'submissions']) {
            if (Array.isArray(value?.[key])) return value[key];
        }
        return [];
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
            publishers: [], localKeys: [], submissions: [], publishingLoaded: false,
            selectedPublisherId: '', selectedKeyRef: '',
            publisherForm: { displayName: '', namespace: '', kind: 'personal' },
            keyName: '',
            buildForm: { sourcePath: '', outputPath: '/private/tmp/package.ai2app' },
            buildResult: null, submissionDetails: null, reviewNote: '',
            filters: [
                { value: '', label: 'All' }, { value: 'app', label: 'Apps' },
                { value: 'agent', label: 'Agents' }, { value: 'service', label: 'Services' },
            ],
            get visibleItems() {
                const source = this.tab === 'installed' ? this.installed : this.items;
                const query = this.query.trim().toLowerCase();
                return source.filter(item => (!this.type || item.packageType === this.type) &&
                    (!query || (item.displayName + ' ' + item.packageId + ' ' + item.description + ' ' + item.publisherName).toLowerCase().includes(query)));
            },
            get selectedPublisher() { return this.publishers.find(item => item.id === this.selectedPublisherId) || null; },
            get selectedLocalKey() { return this.localKeys.find(item => item.keyRef === this.selectedKeyRef) || null; },
            get selectedCloudKey() {
                const fingerprint = this.selectedLocalKey?.fingerprintSha256;
                return (this.selectedPublisher?.keys || []).find(item => item.fingerprintSha256 === fingerprint && item.status === 'active') || null;
            },
            async init() { await this.reload(); },
            clearMessage() { this.message = ''; this.messageTone = 'error'; },
            success(text) { this.message = text; this.messageTone = 'info'; },
            showError(error) {
                const friendly = {
                    repository_metadata_expired: 'The signed package catalog has expired. Try again after Cloud metadata refreshes.',
                    repository_key_unpinned: 'The Cloud repository key does not match this AI2Apps release. Installation was blocked.',
                    publisher_signature_invalid: 'The Publisher signature is invalid. Installation was blocked.',
                    artifact_digest_mismatch: 'The downloaded bytes do not match the signed release. Installation was blocked.',
                    service_contract_adapter_required: 'This Service package uses a runtime entrypoint that this local release cannot activate yet.',
                    authentication_required: 'Sign in to AI2Apps Account before using Publisher tools.',
                    admin_reauth_required: 'Administrator verification is required in Account App before review or publication.',
                    namespace_already_exists: 'That Publisher namespace is already registered.',
                    release_already_exists: 'This package version or artifact was already submitted.',
                };
                this.message = friendly[error.code] || error.message || String(error);
                this.messageTone = 'error';
            },
            async reload() {
                this.busy = true; this.clearMessage();
                try {
                    if (this.tab === 'publish') await this.loadPublishing();
                    else await this.loadCatalog();
                } catch (error) { this.showError(error); }
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
                const [publisherResult, keyResult, submissionResult] = await Promise.allSettled([
                    request('/publishing/publishers'), request('/publisher-keys'), request('/publishing/submissions?limit=50'),
                ]);
                if (publisherResult.status === 'fulfilled') this.publishers = rows(publisherResult.value);
                if (keyResult.status === 'fulfilled') this.localKeys = rows(keyResult.value);
                if (submissionResult.status === 'fulfilled') this.submissions = rows(submissionResult.value);
                if (!this.selectedPublisherId && this.publishers.length) this.selectedPublisherId = this.publishers[0].id;
                if (!this.selectedKeyRef && this.localKeys.length) this.selectedKeyRef = this.localKeys[0].keyRef;
                this.publishingLoaded = true;
                const failure = [publisherResult, keyResult, submissionResult].find(result => result.status === 'rejected');
                if (failure) this.showError(failure.reason);
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
            installedItem(id) { return this.installed.find(item => item.packageId === id) || null; },
            open(item) {
                const installed = this.installedItem(item.packageId) || item;
                if (installed.packageType !== 'app' || !installed.runtimeKey) return;
                window.top.location.href = '/apps/' + encodeURIComponent(installed.runtimeKey);
            },
            openAccount() { window.top.location.href = '/apps/ai2apps.account'; },
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
                if (!id.namespace || !id.name || this.working) return;
                this.working = item.packageId; this.clearMessage();
                try {
                    await request('/' + encodeURIComponent(id.namespace) + '/' + encodeURIComponent(id.name) + '/install', {
                        method: 'POST', body: { version: item.version || null, approve_review: Boolean(approved) },
                    });
                    this.success(item.displayName + ' was verified and installed.');
                    this.selected = null; await this.loadCatalog();
                } catch (error) {
                    if (error.code === 'audit_review_required' && !approved && window.confirm('Local review is required before activation. Review the declared permissions and continue?')) {
                        this.working = ''; return this.install(item, true);
                    }
                    this.showError(error);
                } finally { this.working = ''; redraw(); }
            },
            async uninstall(item, force) {
                const id = this.split(item.packageId);
                if (!id.namespace || !id.name || this.working) return;
                if (!force && !window.confirm('Uninstall ' + item.displayName + '? Local data is preserved where the package runtime allows it.')) return;
                this.working = item.packageId; this.clearMessage();
                try {
                    await request('/' + encodeURIComponent(id.namespace) + '/' + encodeURIComponent(id.name) + '/uninstall', { method: 'POST', body: { force: Boolean(force) } });
                    this.success(item.displayName + ' was uninstalled.');
                    this.selected = null; await this.loadCatalog();
                } catch (error) {
                    if (error.code === 'app_has_instances' && !force && window.confirm('This App still has open instances. Close them and force uninstall?')) {
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
                    this.success('Publisher namespace was created.');
                } catch (error) { this.showError(error); }
                finally { this.working = ''; redraw(); }
            },
            async createKey() {
                if (this.working) return;
                this.working = 'key'; this.clearMessage();
                try {
                    const result = await request('/publisher-keys', { method: 'POST', body: { name: this.keyName } });
                    this.keyName = ''; await this.loadPublishing(); this.selectedKeyRef = result.keyRef;
                    this.success('Signing key was generated locally. Its private material never leaves this device.');
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
                    await this.loadPublishing(); this.success('Signing key ownership was verified and registered with this Publisher.');
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
                    this.success(this.buildResult.package.id + ' ' + this.buildResult.package.version + ' was built and inspected.');
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
                    this.success(submission.packageId + ' ' + submission.packageVersion + ' was signed, uploaded, and verified in quarantine.');
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
                const note = this.reviewNote.trim() || 'Manifest, signature binding, artifact digest, compatibility, permissions, and entrypoints reviewed.';
                await this.submissionAction(item, 'reviews', { decision: 'approved', note: note });
            },
            async publishSubmission(item) { await this.submissionAction(item, 'publication'); },
            async submissionAction(item, action, body) {
                if (this.working) return;
                this.working = item.id; this.clearMessage();
                try {
                    await request('/publishing/submissions/' + encodeURIComponent(item.id) + '/' + action, {
                        method: 'POST', ...(body ? { body: body } : {}),
                    });
                    await this.loadPublishing(); this.success('Submission workflow advanced successfully.');
                } catch (error) { this.showError(error); }
                finally { this.working = ''; redraw(); }
            },
            statusLabel(item) { return String(item.releaseStatus || item.status || 'candidate').replaceAll('_', ' '); },
            statusClass(item) { return 'status-' + String(item.releaseStatus || item.status || 'candidate').replaceAll('_', '-'); },
            shortFingerprint(value) { return value ? value.slice(0, 12) + '…' + value.slice(-8) : '—'; },
            formatBytes(value) { const size = Number(value || 0); return size < 1024 ? size + ' B' : size < 1048576 ? (size / 1024).toFixed(1) + ' KiB' : (size / 1048576).toFixed(1) + ' MiB'; },
            formatTime(value) { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString(); },
            iconFor(type) { return type === 'agent' ? 'bot' : type === 'service' ? 'server-cog' : 'app-window'; },
            ratingText(item) { return (item.rating || 0).toFixed(1) + ' (' + item.ratingCount + ')'; },
        };
    };
})();
