(function () {
    'use strict';

    const API = '/v1/platform/cloud';
    const REMOTE_API = '/v1/platform/remote';
    const apiKey = window.AI2APPS_ACCOUNT_API_KEY || '';

    function errorMessage(payload, status) {
        const error = payload && payload.error;
        const code = error && error.code;
        const known = {
            AUTHENTICATION_REQUIRED: 'Your Cloud session has expired. Please sign in again.',
            INVALID_CREDENTIALS: 'The email or password is incorrect.',
            EMAIL_NOT_VERIFIED: 'Verify your email before signing in.',
            EMAIL_ALREADY_REGISTERED: 'This email is already registered.',
            INVALID_VERIFICATION_CODE: 'The verification code is invalid or expired.',
            ADMIN_REQUIRED: 'This account is not a system administrator.',
            ADMIN_REAUTH_REQUIRED: 'Verify the administrator password to continue.',
            RATE_LIMITED: 'Too many attempts. Please wait and try again.',
            cloud_unavailable: 'AI2Apps Cloud is currently unavailable. Local features are unaffected.',
            cloud_timeout: 'AI2Apps Cloud did not respond in time. Local features are unaffected.',
            cloud_client_not_ready: 'The Cloud connection is not ready. Local features are unaffected.',
        };
        return known[code] || (error && error.message) || ('Request failed (HTTP ' + status + ').');
    }

    async function cloud(path, options) {
        const headers = { Accept: 'application/json' };
        if (apiKey) headers.Authorization = 'Bearer ' + apiKey;
        if (options && options.body !== undefined) headers['Content-Type'] = 'application/json';
        const response = await fetch(API + path, {
            credentials: 'same-origin',
            headers: headers,
            ...(options || {}),
            body: options && options.body !== undefined ? JSON.stringify(options.body) : undefined,
        });
        let payload = null;
        if (response.status !== 204) {
            try { payload = await response.json(); } catch (_) { payload = null; }
        }
        if (!response.ok) {
            const error = new Error(errorMessage(payload, response.status));
            error.status = response.status;
            error.code = payload && payload.error && payload.error.code;
            throw error;
        }
        return payload;
    }

    async function remoteRequest(path, options) {
        const headers = { Accept: 'application/json' };
        if (apiKey) headers.Authorization = 'Bearer ' + apiKey;
        if (options && options.body !== undefined) headers['Content-Type'] = 'application/json';
        const response = await fetch(REMOTE_API + path, { credentials: 'same-origin', headers, ...(options || {}), body: options && options.body !== undefined ? JSON.stringify(options.body) : undefined });
        const payload = response.status === 204 ? null : await response.json().catch(() => null);
        if (!response.ok) {
            const error = new Error(errorMessage(payload, response.status));
            error.status = response.status; error.code = payload?.error?.code; throw error;
        }
        return payload;
    }

    function notifyShell() {
        if (window.ai2appsShell && window.ai2appsShell.accountChanged) window.ai2appsShell.accountChanged();
    }

    window.accountApp = function () {
        return {
            mode: 'login', signedIn: false, cloudUnavailable: false, busy: false,
            user: null, points: {}, entitlements: [], ledger: [],
            displayName: '', email: '', password: '', code: '', newPassword: '',
            adminPassword: '', adminVerifiedUntil: '',
            remote: { devices: [], connector: {}, usage: {} }, remoteName: 'This Mac', pairingUrl: '', pairingQr: '', pairingExpiresAt: '', remotePolling: false, remotePollTimer: null,
            message: '', messageTone: 'error',

            async init() { await this.restore(); this.beginRemotePolling(); },
            clearNotice() { this.message = ''; this.messageTone = 'error'; },
            success(text) { this.message = text; this.messageTone = 'success'; },
            fail(error) { this.message = error.message || String(error); this.messageTone = 'error'; },
            setMode(mode) { this.clearNotice(); this.password = ''; this.code = ''; this.newPassword = ''; this.mode = mode; },
            async restore() {
                this.busy = true; this.clearNotice();
                try {
                    const result = await cloud('/auth/me');
                    this.applyUser(result.user);
                    await Promise.all([this.loadLedger(), this.loadRemote()]);
                } catch (error) {
                    this.signedIn = false;
                    this.cloudUnavailable = error.status !== 401;
                    if (error.status !== 401) this.fail(error);
                } finally { this.busy = false; notifyShell(); }
            },
            applyUser(user) {
                this.user = user || null;
                this.signedIn = Boolean(user);
                this.cloudUnavailable = false;
                this.points = (user && user.points) || {};
                this.entitlements = Array.isArray(user && user.entitlements) ? user.entitlements : [];
            },
            get hasRemoteEntitlement() { return this.entitlements.includes('remote.connect'); },
            async refresh() {
                this.busy = true; this.clearNotice();
                try {
                    const [me, pointResult, ledgerResult] = await Promise.all([
                        cloud('/auth/me'), cloud('/points'), cloud('/points/ledger?limit=50'),
                    ]);
                    this.applyUser(me.user); this.points = pointResult || this.points;
                    this.ledger = Array.isArray(ledgerResult && ledgerResult.items) ? ledgerResult.items : [];
                    await this.loadRemote();
                } catch (error) {
                    if (error.status === 401) { this.applyUser(null); this.mode = 'login'; notifyShell(); }
                    this.fail(error);
                } finally { this.busy = false; }
            },
            async loadLedger() {
                try {
                    const result = await cloud('/points/ledger?limit=50');
                    this.ledger = Array.isArray(result && result.items) ? result.items : [];
                } catch (error) { if (error.status !== 401) this.fail(error); }
            },
            async login() {
                this.busy = true; this.clearNotice();
                try {
                    const result = await cloud('/auth/login', { method: 'POST', body: { email: this.email, password: this.password } });
                    this.password = ''; this.applyUser(result.user); await Promise.all([this.loadLedger(), this.loadRemote()]); notifyShell();
                } catch (error) {
                    if (error.code === 'EMAIL_NOT_VERIFIED') this.mode = 'verify';
                    this.fail(error);
                } finally { this.password = ''; this.busy = false; }
            },
            async register() {
                this.busy = true; this.clearNotice();
                try {
                    await cloud('/auth/register', { method: 'POST', body: { displayName: this.displayName, email: this.email, password: this.password } });
                    this.password = ''; this.mode = 'verify'; this.success('Account created. Enter the verification code sent to your email.');
                } catch (error) { this.fail(error); }
                finally { this.password = ''; this.busy = false; }
            },
            async verifyEmail() {
                this.busy = true; this.clearNotice();
                try {
                    await cloud('/auth/email/verify', { method: 'POST', body: { email: this.email, code: this.code } });
                    this.code = ''; this.mode = 'login'; this.success('Email verified. You can now sign in.');
                } catch (error) { this.fail(error); }
                finally { this.code = ''; this.busy = false; }
            },
            async resendCode() {
                this.busy = true; this.clearNotice();
                try { await cloud('/auth/email/resend', { method: 'POST', body: { email: this.email } }); this.success('If the address can receive a code, a new one has been sent.'); }
                catch (error) { this.fail(error); }
                finally { this.busy = false; }
            },
            async requestReset() {
                this.busy = true; this.clearNotice();
                try { await cloud('/auth/password/reset-request', { method: 'POST', body: { email: this.email } }); this.mode = 'reset'; this.success('If the account exists, a reset code has been sent.'); }
                catch (error) { this.fail(error); }
                finally { this.busy = false; }
            },
            async resetPassword() {
                this.busy = true; this.clearNotice();
                try {
                    await cloud('/auth/password/reset', { method: 'POST', body: { email: this.email, code: this.code, newPassword: this.newPassword } });
                    this.code = ''; this.newPassword = ''; this.mode = 'login'; this.applyUser(null); this.success('Password reset. Sign in with your new password.'); notifyShell();
                } catch (error) { this.fail(error); }
                finally { this.code = ''; this.newPassword = ''; this.busy = false; }
            },
            async logout() {
                this.busy = true; this.clearNotice();
                try { await cloud('/auth/logout', { method: 'POST' }); }
                catch (error) { if (error.status !== 401) this.fail(error); }
                finally { this.applyUser(null); this.ledger = []; this.remote = { devices: [], connector: {}, usage: {} }; this.pairingUrl = ''; this.pairingQr = ''; this.pairingExpiresAt = ''; this.mode = 'login'; this.busy = false; notifyShell(); }
            },
            async verifyAdmin() {
                this.busy = true; this.clearNotice();
                try {
                    const result = await cloud('/admin/reauth', { method: 'POST', body: { password: this.adminPassword } });
                    this.adminVerifiedUntil = result.expiresAt || '';
                    this.success('Administrator verified for 15 minutes. Package review and publication can continue.');
                } catch (error) { this.fail(error); }
                finally { this.adminPassword = ''; this.busy = false; }
            },
            async loadRemote() {
                try {
                    const status = await remoteRequest('/status');
                    this.remote.devices = status.devices || [];
                    this.remote.connector = status.connector || {};
                    if (this.signedIn && this.hasRemoteEntitlement) {
                        const synchronized = await remoteRequest('/devices/reconcile', { method: 'POST' });
                        this.remote.devices = synchronized.devices || this.remote.devices;
                        this.remote.usage = await remoteRequest('/usage');
                    }
                } catch (error) { if (error.status !== 401 && error.status !== 403) this.fail(error); }
            },
            beginRemotePolling() { if(this.remotePollTimer) return; this.remotePollTimer=setInterval(()=>{ if(this.signedIn&&this.hasRemoteEntitlement&&this.remote.devices.some(device=>device.enabled&&!device.proxyConnected&&device.status==='active')) this.refreshRemoteConnectionState(); },1500); },
            async refreshRemoteConnectionState() { if(this.remotePolling) return; this.remotePolling=true; try { const status=await remoteRequest('/status'); this.remote.connector=status.connector||this.remote.connector; const synchronized=await remoteRequest('/devices/reconcile',{method:'POST'}); this.remote.devices=synchronized.devices||status.devices||this.remote.devices; } catch(error) { if(error.status!==401&&error.status!==403) this.remote.connector={...this.remote.connector,lastError:error.message||String(error)}; } finally { this.remotePolling=false; } },
            async registerRemote() { this.busy = true; this.clearNotice(); try { await remoteRequest('/devices', { method:'POST', body:{ displayName:this.remoteName } }); await this.loadRemote(); this.success('This Mac is registered for remote access.'); } catch(error){ this.fail(error); } finally { this.busy=false; } },
            async startRemote(device) { this.busy=true; this.clearNotice(); try { await remoteRequest('/devices/'+encodeURIComponent(device.deviceId)+'/start',{method:'POST'}); await this.loadRemote(); this.success('Remote connector is starting.'); } catch(error){this.fail(error);} finally{this.busy=false;} },
            async stopRemote(device) { this.busy=true; this.clearNotice(); try { await remoteRequest('/devices/'+encodeURIComponent(device.deviceId)+'/stop',{method:'POST'}); await this.loadRemote(); this.success('Remote connector stopped and local mobile sessions were closed.'); } catch(error){this.fail(error);} finally{this.busy=false;} },
            async rotateRemote(device) { this.busy=true; this.clearNotice(); try { const wasEnabled=device.enabled; await remoteRequest('/devices/'+encodeURIComponent(device.deviceId)+'/credentials/rotate',{method:'POST'}); await this.loadRemote(); this.success(wasEnabled?'Remote connector credential rotated. Reconnecting automatically…':'Remote connector credential rotated.'); } catch(error){await this.loadRemote();this.fail(error);} finally{this.busy=false;} },
            async createPairing(device) { this.busy=true; this.clearNotice(); try { const result=await remoteRequest('/devices/'+encodeURIComponent(device.deviceId)+'/pairing-challenges',{method:'POST'}); this.pairingUrl=result.pairingUrl||''; this.pairingQr=result.pairingQrDataUrl||''; this.pairingExpiresAt=result.expiresAt||''; this.success('Pairing QR code created. It expires in five minutes and can be used once.'); } catch(error){this.pairingUrl='';this.pairingQr='';this.pairingExpiresAt='';this.fail(error);} finally{this.busy=false;} },
            async revokeRemote(device) { if(!confirm('Permanently revoke remote access for this Mac? Existing phone sessions will close. This device identity cannot be started again; you must register a new one.')) return; this.busy=true; this.clearNotice(); try { await remoteRequest('/devices/'+encodeURIComponent(device.deviceId)+'/revoke',{method:'POST'}); await this.loadRemote(); this.success('Remote device revoked. Register this Mac again before starting remote access.'); } catch(error){this.fail(error);} finally{this.busy=false;} },
            async reregisterRemote(device) { if(!confirm('Register this Mac again? A new public device URL and connector credential will be created.')) return; this.busy=true; this.clearNotice(); const displayName=device.displayName||this.remoteName||'This Mac'; try { await remoteRequest('/devices/'+encodeURIComponent(device.deviceId),{method:'DELETE'}); await remoteRequest('/devices',{method:'POST',body:{displayName}}); await this.loadRemote(); this.success('This Mac has a new remote identity. You can now start it and pair your phone.'); } catch(error){ try { await this.loadRemote(); } catch(_) {} this.fail(error); } finally{this.busy=false;} },
            async copyPairing() { try { await navigator.clipboard.writeText(this.pairingUrl); this.success('Pairing link copied.'); } catch(_) { this.fail(new Error('Could not copy the pairing link.')); } },
            async sharePairing() { if(navigator.share) { try { await navigator.share({title:'AI2Apps Remote Access',url:this.pairingUrl}); } catch(_){} } else await this.copyPairing(); },
            formatBytes(value) { const size=Number(value||0); if(!Number.isFinite(size)) return String(value); const units=['B','KiB','MiB','GiB']; let amount=size,index=0; while(amount>=1024&&index<units.length-1){amount/=1024;index++;} return amount.toFixed(index?1:0)+' '+units[index]; },
            initials() {
                const value = (this.user && (this.user.displayName || this.user.email)) || 'A';
                return value.trim().slice(0, 2).toUpperCase();
            },
            signedDelta(value) {
                const text = String(value == null ? '0' : value);
                return text.startsWith('-') || text === '0' ? text : '+' + text;
            },
            formatTime(value) {
                if (!value) return '—';
                const date = new Date(value);
                return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
            },
        };
    };
})();
