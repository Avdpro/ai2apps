function aiBrowserApp() {
    return {
        profiles: [], loading: true, busyKey: '', notice: '', noticeTone: 'success',
        showCreate: false, creating: false, newName: '', deleteTarget: null,
        tr(key, values = {}) {
            const text = window.t(key);
            return text.replace(/\{(\w+)\}/g, (match, name) =>
                Object.prototype.hasOwnProperty.call(values, name) ? String(values[name]) : match);
        },
        async init() { await this.loadProfiles(); },
        async loadProfiles() {
            this.loading = true;
            try {
                const response = await fetch('/v1/platform/client/browser-profiles');
                if (!response.ok) throw new Error(await this.readError(response));
                this.profiles = (await response.json()).map(profile => ({...profile, lastStatus: ''}));
                this.refreshIcons();
            } catch (error) { this.fail(error, this.tr('ai_browser.load_failed')); }
            finally { this.loading = false; }
        },
        async createProfile() {
            const name = this.newName.replace(/\s+/g, ' ').trim();
            if (!name || Array.from(name).length > 80) {
                this.fail(null, this.tr('ai_browser.invalid_name'));
                return;
            }
            this.creating = true; this.notice = '';
            try {
                const response = await fetch('/v1/platform/client/browser-profiles', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name})});
                if (!response.ok) throw new Error(await this.readError(response));
                this.profiles.push({...await response.json(), lastStatus: ''});
                this.newName = ''; this.showCreate = false; this.succeed(this.tr('ai_browser.created')); this.refreshIcons();
            } catch (error) { this.fail(error, this.tr('ai_browser.create_failed')); }
            finally { this.creating = false; }
        },
        async launch(profile) {
            this.busyKey = profile.key; this.notice = '';
            try {
                const response = await fetch(`/v1/platform/client/browser-profiles/${encodeURIComponent(profile.key)}/launch`, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
                if (!response.ok) throw new Error(await this.readError(response));
                const result = await response.json();
                profile.lastStatus = result.status === 'focused' ? this.tr('ai_browser.focused') : this.tr('ai_browser.launched');
                this.succeed(profile.lastStatus); this.refreshIcons();
            } catch (error) { this.fail(error, this.tr('ai_browser.launch_failed')); }
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
                this.deleteTarget = null; this.succeed(this.tr('ai_browser.deleted')); this.refreshIcons();
            } catch (error) { this.fail(error, this.tr('ai_browser.delete_failed')); }
            finally { this.busyKey = ''; }
        },
        succeed(message) { this.noticeTone = 'success'; this.notice = message; },
        fail(error, fallback) {
            this.noticeTone = 'error';
            // Native fetch errors vary by browser and ignore the app's locale.
            const detail = error?.name === 'TypeError' ? this.tr('ai_browser.network_error') : error?.message;
            this.notice = detail ? `${fallback}: ${detail}` : fallback;
            this.refreshIcons();
        },
        refreshIcons() { this.$nextTick(() => window.lucide?.createIcons()); },
        async readError(response) {
            let detail = '';
            try {
                const body = await response.json();
                detail = typeof body.detail === 'string' ? body.detail : '';
            } catch (_) { /* Non-JSON failures still get a localized HTTP message. */ }
            const knownErrors = {
                'Profile name must contain 1 to 80 characters': 'invalid_name',
                'Browser Profile not found': 'not_found',
                'Browser Profile ID is invalid': 'not_found',
                'The default browser Profile cannot be deleted': 'default_protected',
                'AppShell did not acknowledge the browser request': 'timeout',
                'Shell browser request expired': 'timeout',
            };
            // Python KeyError includes quotes around its message.
            const known = knownErrors[detail.replace(/^['"]|['"]$/g, '')];
            const statusKey = {
                401: 'unauthorized', 403: 'unauthorized', 404: 'not_found',
                409: 'invalid_request', 422: 'invalid_name',
                502: 'unavailable', 503: 'unavailable', 504: 'timeout',
            }[response.status];
            const reason = known || statusKey;
            const summary = this.tr('ai_browser.request_failed', {status: response.status});
            return reason ? `${this.tr(`ai_browser.${reason}`)} ${summary}` : summary;
        },
    };
}
