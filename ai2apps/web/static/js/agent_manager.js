function agentManager() {
    const terminal = new Set(['completed', 'failed', 'cancelled']);
    return {
        tab: 'catalog', agents: [], detail: null, runs: [], search: '',
        selectedKey: '', runAgent: '', runStatus: '', rootOnly: false,
        loading: true, runsLoading: false, working: false, error: '',
        installPath: '', approveReview: false,
        runStates: ['queued','planning','running','waiting_input','waiting_capability','interrupted','completed','failed','cancelled'],

        async init() {
            const key = window.AI2APPS_AGENT_MANAGER_API_KEY || '';
            if (key) localStorage.setItem('omlx_chat_api_key', key);
            await this.refresh();
        },
        apiKey() { return localStorage.getItem('omlx_chat_api_key') || window.AI2APPS_AGENT_MANAGER_API_KEY || ''; },
        async request(path, options = {}) {
            const response = await fetch('/v1/platform' + path, {
                credentials: 'same-origin',
                ...options,
                headers: {
                    'Content-Type': 'application/json',
                    ...(this.apiKey() ? { Authorization: 'Bearer ' + this.apiKey() } : {}),
                    ...(options.headers || {}),
                },
            });
            let payload = {};
            try { payload = await response.json(); } catch { /* empty response */ }
            if (!response.ok) throw new Error(payload?.error?.message || payload?.detail || `Request failed (${response.status})`);
            return payload;
        },
        async refresh() {
            this.error = ''; this.loading = true;
            try {
                const payload = await this.request('/agents');
                this.agents = payload.items || [];
                if (!this.selectedKey && this.agents.length) this.selectedKey = this.agents[0].agent_key;
                if (this.selectedKey) await this.selectAgent(this.selectedKey);
                if (this.tab === 'runs') await this.loadRuns();
            } catch (error) { this.error = error.message; }
            finally { this.loading = false; }
        },
        filteredAgents() {
            const query = this.search.trim().toLowerCase();
            if (!query) return this.agents;
            return this.agents.filter(agent => [agent.display_name, agent.agent_key, agent.description, ...(agent.aliases || [])].join(' ').toLowerCase().includes(query));
        },
        async selectAgent(key) {
            this.selectedKey = key; this.error = '';
            try { this.detail = await this.request('/agents/' + encodeURIComponent(key) + '/management'); }
            catch (error) { this.detail = null; this.error = error.message; }
        },
        async setEnabled(enabled) {
            if (!this.selectedKey || this.working) return;
            this.working = true;
            try { await this.request('/agents/' + encodeURIComponent(this.selectedKey) + '/' + (enabled ? 'enable' : 'disable'), { method: 'POST' }); await this.refresh(); }
            catch (error) { this.error = error.message; }
            finally { this.working = false; }
        },
        async uninstallSelected() {
            if (!this.selectedKey || this.detail?.definition.source !== 'installed') return;
            if (!confirm(`Uninstall ${this.detail.definition.display_name}? Existing Run history is retained.`)) return;
            this.working = true;
            try { await this.request('/definitions/agent/' + encodeURIComponent(this.selectedKey), { method: 'DELETE' }); this.selectedKey = ''; this.detail = null; await this.refresh(); }
            catch (error) { this.error = error.message; }
            finally { this.working = false; }
        },
        async installAgent() {
            this.working = true; this.error = '';
            try {
                const installed = await this.request('/interactive-packages/install', { method: 'POST', body: JSON.stringify({ archive_path: this.installPath, approve_review: this.approveReview }) });
                this.installPath = ''; this.selectedKey = installed.key || ''; await this.refresh();
            } catch (error) { this.error = error.message; }
            finally { this.working = false; }
        },
        async activatePackage(digest) {
            this.working = true; this.error = '';
            try { await this.request('/interactive-packages/' + encodeURIComponent(digest) + '/activate', { method: 'POST' }); await this.refresh(); }
            catch (error) { this.error = error.message; }
            finally { this.working = false; }
        },
        async loadRuns() {
            this.runsLoading = true; this.error = '';
            const params = new URLSearchParams({ limit: '200' });
            if (this.runAgent) params.set('agent', this.runAgent);
            if (this.runStatus) params.set('status', this.runStatus);
            if (this.rootOnly) params.set('root_only', 'true');
            try { this.runs = (await this.request('/agent-runs?' + params)).items || []; }
            catch (error) { this.error = error.message; }
            finally { this.runsLoading = false; }
        },
        isActive(run) { return !terminal.has(run.status) && run.status !== 'interrupted'; },
        canPause(run) { return ['queued','planning','running'].includes(run.status); },
        async runAction(run, action) {
            try { await this.request('/agent-runs/' + encodeURIComponent(run.id) + '/' + action, { method: 'POST', body: ['resume','retry'].includes(action) ? '{}' : undefined }); await this.loadRuns(); if (this.selectedKey === run.agent_key) await this.selectAgent(this.selectedKey); }
            catch (error) { this.error = error.message; }
        },
        pretty(value) { return JSON.stringify(value || {}, null, 2); },
        formatTime(value) { if (!value) return '—'; try { return new Intl.DateTimeFormat(undefined, { dateStyle:'medium', timeStyle:'short' }).format(new Date(value)); } catch { return value; } },
    };
}
