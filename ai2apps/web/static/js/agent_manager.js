function agentManager() {
    const terminal = new Set(['completed', 'failed', 'cancelled']);
    return {
        tab: 'studio', agents: [], detail: null, runs: [], search: '',
        selectedKey: '', runAgent: '', runStatus: '', rootOnly: false,
        loading: true, runsLoading: false, working: false, error: '',
        installPath: '', approveReview: false,
        drafts: [], selectedDraft: null, generations: [], draftSourceText: '', draftScopeText: '', selectedCapabilityId: '',
        newDraftType: 'web', workflows: [], workflowName: '', workflowDraftIds: [],
        schedules: [], scheduleName: '', scheduleTarget: '', scheduleKind: 'interval',
        scheduleInterval: 3600, scheduleRunAt: '', scheduleBucket: '', knowledgeBuckets: [],
        discoveryUrl: '', discoveryCapability: '', discoveryOutputSchema: '',
        installedSitePackages: [], registrySitePackages: [], selectedLifecycle: null,
        healthItems: [], exportPackageId: '', exportVersion: '1.0.0', exportPublisher: '',
        runStates: ['queued','planning','running','waiting_input','waiting_capability','interrupted','completed','failed','cancelled'],

        async init() {
            localStorage.removeItem('omlx_chat_api_key');
            await this.refresh();
        },
        async request(path, options = {}) {
            const response = await fetch('/v1/platform' + path, {
                credentials: 'same-origin',
                ...options,
                headers: {
                    'Content-Type': 'application/json',
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
                await this.loadStudio();
            } catch (error) { this.error = error.message; }
            finally { this.loading = false; }
        },
        async loadStudio() {
            try {
                await this.request('/site-agents/reconcile', {method:'POST', body:'{}'});
                this.drafts = (await this.request('/agent-drafts')).items || [];
                if (this.selectedDraft) {
                    const current = this.drafts.find(item => item.id === this.selectedDraft.id);
                    if (current) await this.selectDraft(current);
                }
            } catch (error) { this.error = error.message; }
        },
        async createDraft() {
            this.error = '';
            const type = this.newDraftType;
            const source = type === 'web' ? {
                schema: 'ai2apps.site-agent-source/v1', agent_type: type,
                name: 'New ' + type[0].toUpperCase() + type.slice(1) + ' Agent',
                description: '', site_scope: [],
                capabilities:[{id:'run',name:'site.run',title:'Run',description:'',
                    inputs:{type:'object',properties:{}},outputs:{type:'object',properties:{}},
                    fixtures:[],validators:[],steps:[{name:'step-1',desc:'读取当前页面并完成',operation:'complete'}]}],
            } : {
                schema:'ai2apps.agent-source/v1',agent_type:type,
                name:'New '+type[0].toUpperCase()+type.slice(1)+' Agent',description:'',
                site_scope:[],inputs:{type:'object',properties:{}},outputs:{type:'object',properties:{}},
                capability_exports:[],fixtures:[],validators:[],steps:[],
            };
            try {
                const draft = await this.request('/agent-drafts', {method:'POST', body:JSON.stringify({agent_type:type, name:source.name, source})});
                await this.loadStudio(); await this.selectDraft(draft);
            } catch (error) { this.error = error.message; }
        },
        async selectDraft(draft) {
            this.selectedDraft = JSON.parse(JSON.stringify(draft));
            this.draftSourceText = JSON.stringify(draft.source || {}, null, 2);
            this.draftScopeText = (draft.site_scope || []).join('\n');
            this.selectedCapabilityId = draft.source?.capabilities?.[0]?.id || '';
            try { this.generations = await this.request('/agent-drafts/' + encodeURIComponent(draft.id) + '/generations'); }
            catch (error) { this.generations = []; this.error = error.message; }
        },
        draftCapabilities() {
            try { return JSON.parse(this.draftSourceText || '{}').capabilities || []; }
            catch { return []; }
        },
        addCapability() {
            try {
                const source=JSON.parse(this.draftSourceText||'{}');
                if(!Array.isArray(source.capabilities)) throw new Error('Reconcile this legacy Agent before adding Capabilities.');
                let n=source.capabilities.length+1,id='capability-'+n;
                while(source.capabilities.some(item=>item.id===id)) id='capability-'+(++n);
                source.capabilities.push({id,name:'site.'+id,title:'New capability',description:'',inputs:{type:'object',properties:{}},outputs:{type:'object',properties:{}},fixtures:[],validators:[],steps:[]});
                this.selectedCapabilityId=id; this.draftSourceText=JSON.stringify(source,null,2);
            } catch(error){ this.error=error.message; }
        },
        removeCapability(id) {
            try {
                const source=JSON.parse(this.draftSourceText||'{}');
                if(!confirm('Remove this Capability from the editable source? Active generations remain available for rollback.')) return;
                source.capabilities=(source.capabilities||[]).filter(item=>item.id!==id);
                this.selectedCapabilityId=source.capabilities[0]?.id||'';
                this.draftSourceText=JSON.stringify(source,null,2);
            } catch(error){ this.error=error.message; }
        },
        async saveDraft() {
            if (!this.selectedDraft) return;
            try {
                const source = JSON.parse(this.draftSourceText);
                source.agent_type = this.selectedDraft.agent_type;
                const site_scope = this.draftScopeText.split(/[\n,]/).map(value=>value.trim()).filter(Boolean);
                this.selectedDraft = await this.request('/agent-drafts/' + encodeURIComponent(this.selectedDraft.id), {method:'PATCH', body:JSON.stringify({expected_revision:this.selectedDraft.revision, name:this.selectedDraft.name, description:this.selectedDraft.description, site_scope, source})});
                this.draftSourceText = JSON.stringify(this.selectedDraft.source, null, 2);
                await this.loadStudio();
            } catch (error) { this.error = error.message; }
        },
        async compileDraft() {
            await this.saveDraft(); if (!this.selectedDraft) return;
            try {
                const generation = await this.request('/agent-drafts/' + encodeURIComponent(this.selectedDraft.id) + '/compile', {method:'POST', body:'{}'});
                await this.selectDraft(await this.request('/agent-drafts/' + encodeURIComponent(this.selectedDraft.id)));
                if (generation.status === 'failed') this.error = 'Compile failed: ' + (generation.report?.errors || []).map(item=>item.code).join(', ');
            } catch (error) { this.error = error.message; }
        },
        async activateGeneration(generation) {
            try {
                if (generation.report?.repair_id) {
                    await this.request('/agent-repairs/' + encodeURIComponent(generation.report.repair_id) + '/activate', {method:'POST', body:'{}'});
                    this.selectedDraft = await this.request('/agent-drafts/' + encodeURIComponent(this.selectedDraft.id));
                } else {
                    this.selectedDraft = await this.request('/agent-drafts/' + encodeURIComponent(this.selectedDraft.id) + '/generations/' + encodeURIComponent(generation.id) + '/activate', {method:'POST', body:'{}'});
                }
                await this.selectDraft(this.selectedDraft); await this.loadStudio();
            } catch (error) { this.error = error.message; }
        },
        async archiveDraft() {
            if (!this.selectedDraft || !confirm('Archive this Agent? Existing generations and run history are retained.')) return;
            try { await this.request('/agent-drafts/' + encodeURIComponent(this.selectedDraft.id) + '/archive', {method:'POST', body:JSON.stringify({expected_revision:this.selectedDraft.revision})}); this.selectedDraft=null; this.generations=[]; await this.loadStudio(); }
            catch (error) { this.error = error.message; }
        },
        async exportPackageSource() {
            if (!this.selectedDraft || !this.exportPackageId || !this.exportPublisher) return;
            try {
                const result = await this.request('/agent-drafts/' + encodeURIComponent(this.selectedDraft.id) + '/package-source', {
                    method: 'POST', body: JSON.stringify({package_id:this.exportPackageId, version:this.exportVersion, publisher_id:this.exportPublisher}),
                });
                window.alert('Package candidate built:\n' + result.artifact + '\n\nSign and publish it with the standard Package release scripts.');
            } catch (error) { this.error = error.message; }
        },
        async loadDiscovery() {
            this.error = '';
            const params = new URLSearchParams({
                url:this.discoveryUrl||'', capability:this.discoveryCapability||'',
                output_schema:this.discoveryOutputSchema||'',
            });
            try {
                const result = await this.request('/site-agent-discovery?' + params);
                this.installedSitePackages = result.installed || [];
                const registry = result.registry || {};
                this.registrySitePackages = Array.isArray(registry) ? registry : (registry.items || registry.results || registry.packages || []);
                if (result.registry_error) this.error = result.registry_error.message;
            } catch (error) { this.error = error.message; }
        },
        async provisionPackage(pkg) {
            const permissions = pkg.permissions || [];
            if (!window.confirm('Compile this signed Source locally and grant:\n\n' + (permissions.join('\n') || 'No extra permissions') + '\n\nPublisher Hint will not execute.')) return;
            try {
                await this.request('/site-agent-packages/' + encodeURIComponent(pkg.package_key) + '/provision', {
                    method:'POST', body:JSON.stringify({granted_permissions:permissions, expected_digest:pkg.digest, activate:true}),
                });
                await this.loadStudio(); await this.loadDiscovery();
            } catch (error) { this.error = error.message; }
        },
        registryPackageId(pkg) {
            return pkg.packageId || pkg.package_id || pkg.id || '';
        },
        registryPermissions(pkg) {
            return pkg.permissions || pkg.webAgent?.permissions || pkg.web_agent?.permissions || [];
        },
        async installRegistryPackage(pkg) {
            const packageId = this.registryPackageId(pkg);
            const parts = packageId.split('/');
            if (parts.length !== 2) { this.error = 'Registry result has no valid Package ID.'; return; }
            const permissions = this.registryPermissions(pkg);
            if (!window.confirm(
                'Download and verify ' + packageId + ' from AI2Apps Registry, then locally compile its Source and grant:\n\n' +
                (permissions.join('\n') || 'No extra permissions') +
                '\n\nNew versions remain candidates until explicitly activated. Publisher Hint will not execute.'
            )) return;
            this.working = true; this.error = '';
            try {
                await this.request('/site-agent-registry/' + encodeURIComponent(parts[0]) + '/' + encodeURIComponent(parts[1]) + '/install', {
                    method:'POST', body:JSON.stringify({
                        version:pkg.version || pkg.latestVersion || null,
                        granted_permissions:permissions, approve_review:false, activate:false,
                    }),
                });
                await this.loadStudio(); await this.loadDiscovery();
            } catch (error) { this.error = error.message; }
            finally { this.working = false; }
        },
        async openLifecycle(pkg) {
            try {
                this.selectedLifecycle = await this.request('/site-agent-packages/' + encodeURIComponent(pkg.package_key) + '/lifecycle');
            } catch (error) { this.error = error.message; }
        },
        async activateSitePackage(pkg) {
            if (!window.confirm('Activate Site Agent v' + pkg.version + '? The current version will remain available for rollback.')) return;
            try {
                await this.request('/site-agent-packages/' + encodeURIComponent(pkg.package_key) + '/activate', {
                    method:'POST', body:JSON.stringify({package_digest:pkg.digest}),
                });
                await this.loadStudio(); await this.loadDiscovery(); await this.openLifecycle(pkg);
            } catch (error) { this.error = error.message; }
        },
        async rollbackSitePackage(version) {
            const key = this.selectedLifecycle?.package_key;
            if (!key || !window.confirm('Roll back to v' + version.version + '? This is an explicit activation and will be recorded.')) return;
            try {
                await this.request('/site-agent-packages/' + encodeURIComponent(key) + '/rollback', {
                    method:'POST', body:JSON.stringify({package_digest:version.digest}),
                });
                await this.loadStudio(); await this.loadDiscovery();
                this.selectedLifecycle = await this.request('/site-agent-packages/' + encodeURIComponent(key) + '/lifecycle');
            } catch (error) { this.error = error.message; }
        },
        async setLifecyclePolicy(policy) {
            const key = this.selectedLifecycle?.package_key;
            if (!key) return;
            const activeVersion = this.selectedLifecycle?.active_binding?.package_version || null;
            try {
                await this.request('/site-agent-packages/' + encodeURIComponent(key) + '/policy', {
                    method:'POST', body:JSON.stringify({
                        update_policy:policy, pinned_version:policy==='pinned' ? activeVersion : null,
                    }),
                });
                this.selectedLifecycle = await this.request('/site-agent-packages/' + encodeURIComponent(key) + '/lifecycle');
            } catch (error) { this.error = error.message; }
        },
        async loadHealth() {
            try { this.healthItems = (await this.request('/agent-health')).items || []; }
            catch (error) { this.error = error.message; }
        },
        async repairFromCurrentSource(item) {
            const draft = this.drafts.find(value => value.id === item.draft_id);
            if (!draft) { this.error = 'The Site Agent source is unavailable.'; return; }
            if (!window.confirm('Compile the current reviewed Source as a repair candidate? It will require explicit activation and calibration.')) return;
            try {
                const repair = await this.request('/agent-drafts/' + encodeURIComponent(draft.id) + '/repairs', {
                    method:'POST', body:JSON.stringify({capability_name:item.capability_name, strategy:'manual', source:draft.source}),
                });
                this.tab='studio'; await this.selectDraft(await this.request('/agent-drafts/' + encodeURIComponent(draft.id)));
                window.alert('Repair candidate validated. Review generation ' + repair.candidate_generation_id + ' and activate it explicitly.');
            } catch (error) { this.error = error.message; }
        },
        async loadWorkflows() {
            try { await this.loadStudio(); this.workflows = (await this.request('/agent-workflows')).items || []; }
            catch (error) { this.error = error.message; }
        },
        async createWorkflow() {
            if (!this.workflowName.trim() || !this.workflowDraftIds.length) return;
            try {
                await this.request('/agent-workflows', {method:'POST', body:JSON.stringify({name:this.workflowName, definition:{inputs:{type:'object',properties:{}}, outputs:{type:'object',properties:{}}, steps:this.workflowDraftIds.map((draft_id,index)=>({name:'agent-'+(index+1),draft_id}))}})});
                this.workflowName=''; this.workflowDraftIds=[]; await this.loadWorkflows();
            } catch (error) { this.error = error.message; }
        },
        async runWorkflow(workflow) {
            try { const result=await this.request('/agent-workflows/'+encodeURIComponent(workflow.id)+'/runs',{method:'POST',body:JSON.stringify({input:{}})}); this.tab='runs'; await this.loadRuns(); return result; }
            catch (error) { this.error = error.message; }
        },
        async loadSchedules() {
            try {
                await this.loadWorkflows();
                this.schedules=(await this.request('/agent-schedules')).items||[];
                this.knowledgeBuckets=(await this.request('/knowledge/buckets')).items||[];
            } catch (error) { this.error=error.message; }
        },
        async createSchedule() {
            if (!this.scheduleName.trim() || !this.scheduleTarget) return;
            const [target,id]=this.scheduleTarget.split(':',2);
            const body={name:this.scheduleName,kind:this.scheduleKind,input:{},knowledge_bucket_id:this.scheduleBucket||null,[target+'_id']:id};
            if(this.scheduleKind==='interval') body.interval_seconds=Number(this.scheduleInterval);
            else body.run_at=new Date(this.scheduleRunAt).toISOString();
            try { await this.request('/agent-schedules',{method:'POST',body:JSON.stringify(body)}); this.scheduleName=''; await this.loadSchedules(); }
            catch(error){ this.error=error.message; }
        },
        async scheduleAction(schedule,action){
            try{ await this.request('/agent-schedules/'+encodeURIComponent(schedule.id)+'/'+action,{method:'POST',body:JSON.stringify({expected_revision:schedule.revision})}); await this.loadSchedules(); }
            catch(error){ this.error=error.message; }
        },
        async runSchedule(schedule){ return this.scheduleAction(schedule,'run'); },
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
