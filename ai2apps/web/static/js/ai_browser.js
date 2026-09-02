function aiBrowserApp() {
    return {
        profiles: [], loading: true, busyKey: '', notice: '', noticeTone: 'success',
        showCreate: false, creating: false, newName: '', deleteTarget: null,
        async init() { await this.loadProfiles(); },
        async loadProfiles() {
            this.loading = true;
            try {
                const response = await fetch('/v1/platform/client/browser-profiles');
                if (!response.ok) throw new Error(await this.readError(response));
                this.profiles = (await response.json()).map(profile => ({...profile, lastStatus: ''}));
                this.refreshIcons();
            } catch (error) { this.fail(error, '无法读取浏览器 Profile'); }
            finally { this.loading = false; }
        },
        async createProfile() {
            this.creating = true; this.notice = '';
            try {
                const response = await fetch('/v1/platform/client/browser-profiles', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: this.newName})});
                if (!response.ok) throw new Error(await this.readError(response));
                this.profiles.push({...await response.json(), lastStatus: ''});
                this.newName = ''; this.showCreate = false; this.succeed('Profile 已创建'); this.refreshIcons();
            } catch (error) { this.fail(error, '创建 Profile 失败'); }
            finally { this.creating = false; }
        },
        async launch(profile) {
            this.busyKey = profile.key; this.notice = '';
            try {
                const response = await fetch(`/v1/platform/client/browser-profiles/${encodeURIComponent(profile.key)}/launch`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
                if (!response.ok) throw new Error(await this.readError(response));
                const result = await response.json();
                profile.lastStatus = result.status === 'focused' ? '已切换到现有窗口' : 'AceFox 窗口已启动';
                this.succeed(profile.lastStatus); this.refreshIcons();
            } catch (error) { this.fail(error, '启动 AceFox 失败'); }
            finally { this.busyKey = ''; }
        },
        requestDelete(profile) { if (!profile.is_default) this.deleteTarget = profile; },
        async deleteProfile() {
            const profile = this.deleteTarget; if (!profile || profile.is_default) return;
            this.busyKey = profile.key; this.notice = '';
            try {
                const response = await fetch(`/v1/platform/client/browser-profiles/${encodeURIComponent(profile.key)}`, {method: 'DELETE'});
                if (!response.ok) throw new Error(await this.readError(response));
                this.profiles = this.profiles.filter(item => item.key !== profile.key);
                this.deleteTarget = null; this.succeed('Profile 及其浏览数据已删除'); this.refreshIcons();
            } catch (error) { this.fail(error, '删除 Profile 失败'); }
            finally { this.busyKey = ''; }
        },
        succeed(message) { this.noticeTone = 'success'; this.notice = message; },
        fail(error, fallback) { this.noticeTone = 'error'; this.notice = error?.message || fallback; this.refreshIcons(); },
        refreshIcons() { this.$nextTick(() => window.lucide?.createIcons()); },
        async readError(response) { try { const body = await response.json(); return typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body); } catch (_) { return `请求失败（HTTP ${response.status}）`; } },
    };
}
