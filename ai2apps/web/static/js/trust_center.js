function trustCenter() {
    return {
        tabs: [
            { id: 'overview', label: 'Overview' },
            { id: 'approvals', label: 'Approvals' },
            { id: 'permissions', label: 'Permissions' },
            { id: 'secrets', label: 'Secrets' },
        ],
        tab: 'overview', approvals: [], grants: [], secrets: [],
        backend: { provider: 'unknown', portable: false }, safeMode: { active: false },
        approvalScopes: {}, includeResolved: false, includeInactive: false,
        working: false, loading: true, error: '', secretModal: false,
        secretForm: { id: '', name: '', value: '', purpose: '', allowedTools: '' },

        async init() {
            localStorage.removeItem('omlx_chat_api_key');
            await this.refresh();
        },
        async request(path, options = {}, platform = false) {
            const response = await fetch((platform ? '/v1/platform' : '/admin/api/shell') + path, {
                credentials: 'same-origin', ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...(options.headers || {}),
                },
            });
            let payload = {};
            try { payload = await response.json(); } catch { /* empty */ }
            if (!response.ok) {
                const detail = typeof payload.detail === 'string' ? payload.detail : payload.detail?.message;
                throw new Error(payload?.error?.message || detail || `Request failed (${response.status})`);
            }
            return payload;
        },
        async refresh() {
            this.error = ''; this.loading = true;
            try {
                const [control, backend, secretPayload] = await Promise.all([
                    this.request('/control'),
                    this.request('/secrets/backend', {}, true),
                    this.request('/secrets', {}, true),
                    this.loadApprovals(), this.loadGrants(),
                ]);
                this.safeMode = control.safe_mode || { active: false };
                this.backend = backend;
                this.secrets = secretPayload.items || [];
            } catch (error) { this.error = error.message; }
            finally { this.loading = false; }
        },
        async loadApprovals() {
            try {
                const payload = await this.request('/approvals?include_resolved=' + (this.includeResolved ? 'true' : 'false'));
                this.approvals = payload.items || [];
                this.approvals.forEach(item => { if (!this.approvalScopes[item.id]) this.approvalScopes[item.id] = 'once'; });
            } catch (error) { this.error = error.message; }
        },
        async loadGrants() {
            try { this.grants = (await this.request('/grant-leases?include_inactive=' + (this.includeInactive ? 'true' : 'false'))).items || []; }
            catch (error) { this.error = error.message; }
        },
        get pendingApprovals() { return this.approvals.filter(item => item.status === 'pending'); },
        get activeGrants() { return this.grants.filter(item => item.active); },
        scopesFor(item) { return item.source_kind === 'app' ? ['once','session','app'] : ['once','run','session','agent','app']; },
        scopeLabel(scope) { return ({ once:'This action only', run:'This Run', session:'This Session', agent:'This Agent', app:'This App' })[scope] || scope; },
        async decide(item, decision) {
            if (this.working) return;
            this.working = true; this.error = '';
            try {
                await this.request('/approvals/' + encodeURIComponent(item.id) + '/decide', {
                    method: 'POST', body: JSON.stringify({ decision, scope: this.approvalScopes[item.id] || 'once' }),
                });
                await Promise.all([this.loadApprovals(), this.loadGrants()]);
            } catch (error) { this.error = error.message; }
            finally { this.working = false; }
        },
        async revoke(item) {
            if (!confirm(`Revoke permission for ${item.tool_pattern}?`)) return;
            this.working = true; this.error = '';
            try {
                await this.request('/grant-leases/' + encodeURIComponent(item.id) + '/revoke', { method:'POST', body:JSON.stringify({ reason:'user-revoked-from-trust-center' }) });
                await this.loadGrants();
            } catch (error) { this.error = error.message; }
            finally { this.working = false; }
        },
        async setSafeMode(active) {
            if (active && !confirm('Enter Safe Mode? All active permissions will be revoked and managed processes will be stopped.')) return;
            this.working = true; this.error = '';
            try {
                const result = await this.request('/safe-mode', { method:'POST', body:JSON.stringify({ active, reason:'trust-center' }) });
                this.safeMode = result.safe_mode || result;
                await this.loadGrants();
            } catch (error) { this.error = error.message; }
            finally { this.working = false; }
        },
        openSecret(item = null) {
            this.secretForm = item
                ? { id:item.id, name:item.name, value:'', purpose:item.purpose||'', allowedTools:(item.allowed_tools||[]).join(', ') }
                : { id:'', name:'', value:'', purpose:'', allowedTools:'' };
            this.secretModal = true;
        },
        async saveSecret() {
            this.working = true; this.error = '';
            try {
                if (this.secretForm.id) {
                    await this.request('/secrets/' + encodeURIComponent(this.secretForm.id) + '/value', { method:'PUT', body:JSON.stringify({ value:this.secretForm.value }) }, true);
                } else {
                    const allowed = this.secretForm.allowedTools.split(/[\n,]+/).map(value => value.trim()).filter(Boolean);
                    if (!allowed.length) throw new Error('At least one allowed Tool pattern is required.');
                    await this.request('/secrets', { method:'POST', body:JSON.stringify({ name:this.secretForm.name, value:this.secretForm.value, purpose:this.secretForm.purpose, allowed_tools:allowed }) }, true);
                }
                this.secretModal = false;
                this.secrets = (await this.request('/secrets', {}, true)).items || [];
            } catch (error) { this.error = error.message; }
            finally { this.working = false; }
        },
        async deleteSecret(item) {
            if (!confirm(`Delete Secret “${item.name}”? Tools using its URI will stop working.`)) return;
            this.working = true; this.error = '';
            try {
                await this.request('/secrets/' + encodeURIComponent(item.id), { method:'DELETE' }, true);
                this.secrets = this.secrets.filter(secret => secret.id !== item.id);
            } catch (error) { this.error = error.message; }
            finally { this.working = false; }
        },
        backendLabel() { return ({ 'macos-keychain':'macOS Keychain', 'linux-secret-service':'Linux Secret Service', 'encrypted-file':'Encrypted Vault', memory:'Memory test provider' })[this.backend.provider] || this.backend.provider || 'Unavailable'; },
        pretty(value) { return JSON.stringify(value || {}, null, 2); },
        formatTime(value) { if (!value) return '—'; try { return new Intl.DateTimeFormat(undefined, { dateStyle:'medium', timeStyle:'short' }).format(new Date(value)); } catch { return value; } },
    };
}
