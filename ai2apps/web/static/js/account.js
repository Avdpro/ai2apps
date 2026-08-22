(function () {
    'use strict';

    const API = '/v1/platform/cloud';
    const REMOTE_API = '/v1/platform/remote';
    const LOCAL_AUTH_API = '/v1/platform/auth';
    const apiKey = '';

    function tr(key, params) {
        let text = typeof window.t === 'function' ? window.t(key) : key;
        Object.entries(params || {}).forEach(([name, value]) => {
            text = text.replaceAll('{' + name + '}', String(value));
        });
        return text;
    }

    function errorMessage(payload, status) {
        const error = payload && payload.error;
        const code = error && error.code;
        const known = {
            AUTHENTICATION_REQUIRED: tr('account.error.authentication_required'),
            INVALID_CREDENTIALS: tr('account.error.invalid_credentials'),
            EMAIL_NOT_VERIFIED: tr('account.error.email_not_verified'),
            EMAIL_ALREADY_REGISTERED: tr('account.error.email_already_registered'),
            INVALID_VERIFICATION_CODE: tr('account.error.invalid_verification_code'),
            ADMIN_REQUIRED: tr('account.error.admin_required'),
            ADMIN_REAUTH_REQUIRED: tr('account.error.admin_reauth_required'),
            RATE_LIMITED: tr('account.error.rate_limited'),
            ROLE_NOT_ALLOWED: tr('account.error.role_not_allowed'),
            MEMBERSHIP_ALREADY_ACTIVE: tr('account.error.membership_already_active'),
            MEMBERSHIP_NOT_FOUND: tr('account.error.membership_not_found'),
            OWNER_REAUTH_INVALID: tr('account.error.owner_reauth_invalid'),
            POLICY_VERSION_MISMATCH: tr('account.error.policy_version_mismatch'),
            CORE_DEVICE_LIMIT_REACHED: tr('account.error.core_device_limit'),
            INSTALLATION_MEMBER_LIMIT_REACHED: tr('account.error.member_limit'),
            AI_MODEL_NOT_ALLOWED: tr('account.error.model_not_allowed'),
            AI_MEMBER_MONTHLY_POINT_LIMIT: tr('account.error.monthly_point_limit'),
            AI_MEMBER_CONCURRENCY_LIMIT: tr('account.error.concurrency_limit'),
            owner_reauth_required: tr('account.error.owner_password_role'),
            core_device_limit_reached: tr('account.error.core_device_limit'),
            installation_member_limit_reached: tr('account.error.member_limit'),
            cloud_unavailable: tr('account.error.cloud_unavailable'),
            cloud_timeout: tr('account.error.cloud_timeout'),
            cloud_client_not_ready: tr('account.error.cloud_not_ready'),
        };
        return known[code] || (error && error.message) || tr('account.error.request_failed', { status });
    }

    async function cloud(path, options) {
        const includeMetadata = Boolean(options && options.includeMetadata);
        const requestOptions = { ...(options || {}) };
        delete requestOptions.includeMetadata;
        delete requestOptions.body;
        const headers = { Accept: 'application/json' };
        if (apiKey) headers.Authorization = 'Bearer ' + apiKey;
        if (options && options.body !== undefined) headers['Content-Type'] = 'application/json';
        const response = await fetch(API + path, {
            credentials: 'same-origin',
            ...requestOptions,
            headers: { ...headers, ...((options && options.headers) || {}) },
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
        return includeMetadata ? { payload, etag: response.headers.get('etag') || '' } : payload;
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

    async function localAuth(path, options) {
        const headers = { Accept: 'application/json' };
        if (apiKey) headers.Authorization = 'Bearer ' + apiKey;
        if (options && options.body !== undefined) headers['Content-Type'] = 'application/json';
        const response = await fetch(LOCAL_AUTH_API + path, {
            credentials: 'same-origin',
            headers,
            ...(options || {}),
            body: options && options.body !== undefined ? JSON.stringify(options.body) : undefined,
        });
        const payload = response.status === 204 ? null : await response.json().catch(() => null);
        if (!response.ok) {
            const error = new Error(errorMessage(payload, response.status));
            error.status = response.status;
            error.code = payload?.error?.code;
            throw error;
        }
        return payload;
    }

    async function localAccount(path, options) {
        const headers = { Accept: 'application/json' };
        if (options && options.body !== undefined) headers['Content-Type'] = 'application/json';
        const response = await fetch('/admin/api/account' + path, {
            credentials: 'same-origin',
            headers,
            ...(options || {}),
            body: options && options.body !== undefined ? JSON.stringify(options.body) : undefined,
        });
        const payload = response.status === 204 ? null : await response.json().catch(() => null);
        if (!response.ok) {
            const error = new Error(payload?.detail || tr('account.error.request_failed', { status: response.status }));
            error.status = response.status;
            throw error;
        }
        return payload;
    }

    function notifyShell() {
        if (window.ai2appsShell && window.ai2appsShell.accountChanged) window.ai2appsShell.accountChanged();
    }

    window.accountApp = function () {
        return {
            mode: 'login', signedIn: false, cloudUnavailable: false, busy: false,
            user: null, points: {}, entitlements: [], ledger: [], capacityPolicy: null,
            localIdentity: null, handoffInput: '',
            handoffEntryEnabled: false, credentialEntryEnabled: false,
            displayName: '', email: '', password: '', code: '', newPassword: '',
            adminPassword: '', adminVerifiedUntil: '',
            installation: null, members: [], pendingInvitations: [], memberOwnerPassword: '',
            coreDevices: [], deviceOwnerPassword: '',
            installationAccess: 'unknown',
            inviteEmail: '', inviteRole: 'member', invitation: null, invitationCreating: false,
            policy: null, policyEtag: '', policyOwnerPassword: '',
            policyDraft: { allowedAppIds: '', allowedModelIds: '', defaultMonthlyPointLimit: '', defaultConcurrencyLimit: 1, offlineGraceSeconds: 0 },
            remote: { devices: [], connector: {}, usage: {} }, remoteName: tr('account.remote.this_mac'), pairingUrl: '', pairingQr: '', pairingExpiresAt: '', remotePolling: false, remotePollTimer: null,
            registrationNotice: '',
            uiLanguage: document.documentElement.lang === 'zh' ? 'zh' : 'en',
            message: '', messageTone: 'error',

            tr,

            async init() {
                await this.loadLocalIdentity();
                if (this.localIdentity?.isCore) await this.loadLanguage();
                if (!this.localIdentity || this.localIdentity.isCore) await this.restore();
                this.beginRemotePolling();
            },
            clearNotice() { this.message = ''; this.messageTone = 'error'; },
            success(text) { this.message = text; this.messageTone = 'success'; },
            fail(error) { this.message = error.message || String(error); this.messageTone = 'error'; },
            setMode(mode) { this.clearNotice(); this.password = ''; this.code = ''; this.newPassword = ''; this.mode = mode; },
            async loadLocalIdentity() {
                try { this.localIdentity = await localAuth('/me'); }
                catch (error) { this.localIdentity = null; if (error.status !== 401) this.fail(error); }
            },
            async loadLanguage() {
                try {
                    const result = await localAccount('/ui-language');
                    this.uiLanguage = result?.language === 'zh' ? 'zh' : 'en';
                } catch (error) { this.fail(error); }
            },
            async saveLanguage() {
                if (!this.localIdentity?.isCore) {
                    this.fail(new Error(tr('account.error.language_core_only')));
                    return;
                }
                this.busy = true; this.clearNotice();
                try {
                    await localAccount('/ui-language', {
                        method: 'POST',
                        body: { language: this.uiLanguage },
                    });
                    window.top.location.reload();
                } catch (error) { this.fail(error); }
                finally { this.busy = false; }
            },
            handoffValue() {
                const value = this.handoffInput.trim();
                if (!value) return '';
                try { return new URL(value).hash ? new URLSearchParams(new URL(value).hash.slice(1)).get('handoff') || '' : value; }
                catch (_) { return value; }
            },
            async connectLocalMember() {
                const handoff = this.handoffValue();
                if (handoff.length < 24 || handoff.length > 200) {
                    this.fail(new Error(tr('account.error.invalid_handoff')));
                    return;
                }
                this.busy = true; this.clearNotice();
                try {
                    this.localIdentity = await localAuth('/handoff/exchange', { method: 'POST', body: { handoff } });
                    this.handoffInput = '';
                    this.applyUser(null); this.ledger = [];
                    this.success(tr('account.success.local_account_selected'));
                    notifyShell();
                } catch (error) { this.fail(error); }
                finally { this.busy = false; }
            },
            async activateRegisteredCloudMember() {
                const identity = await localAuth('/cloud-member/activate', { method: 'POST' });
                this.localIdentity = identity;
                this.applyUser(null);
                this.ledger = [];
                this.password = '';
                this.success(tr('account.success.member_verified'));
                notifyShell();
            },
            cloudAccountIsDeviceCore() {
                return Boolean(
                    this.user?.id
                    && this.localIdentity?.isCore
                    && this.user.id === this.localIdentity.actorUserId
                );
            },
            isUnregisteredDeviceError(error) {
                return [
                    'INSTALLATION_NOT_FOUND',
                    'MEMBERSHIP_NOT_FOUND',
                    'installation_not_found',
                    'membership_not_found',
                ].includes(error?.code);
            },
            async activateCloudAccountIfMember() {
                if (!this.signedIn || !this.localIdentity?.isCore || this.cloudAccountIsDeviceCore()) return false;
                try {
                    await this.activateRegisteredCloudMember();
                    return true;
                } catch (error) {
                    if (this.isUnregisteredDeviceError(error)) {
                        await this.rejectUnregisteredCloudAccount();
                        return true;
                    }
                    if (error.code === 'MEMBERSHIP_INACTIVE' || error.code === 'membership_inactive') {
                        this.clearInstallationAccess('inactive');
                        this.clearRemoteAccess();
                        return true;
                    }
                    throw error;
                }
            },
            async logoutLocal() {
                this.busy = true; this.clearNotice();
                try {
                    await localAuth('/logout', { method: 'POST' });
                    notifyShell();
                    // A member handoff clears any dormant administrator cookie,
                    // so returning to Core always requires explicit local auth.
                    window.top.location.assign('/admin');
                } catch (error) { this.fail(error); }
                finally { this.busy = false; }
            },
            async restore() {
                this.busy = true; this.clearNotice();
                try {
                    const result = await cloud('/auth/me');
                    this.applyUser(result.user);
                    if (await this.activateCloudAccountIfMember()) return;
                    await this.loadMembership();
                    if (!this.signedIn) return;
                    await this.loadLedger();
                    if (this.installationAccess === 'manager') await this.loadRemote();
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
            async loadCapacityPolicy() {
                try { this.capacityPolicy = await cloud('/capacity-policy'); }
                catch (error) { if (error.status !== 401) this.capacityPolicy = null; }
            },
            get accountLevelId() {
                return String(this.user?.level?.id || this.user?.levelId || '').trim();
            },
            get subscriptionPlanId() {
                const value = this.user?.subscriptionPlan ?? this.user?.subscription?.planId ?? this.user?.subscription?.id ?? 'none';
                return String(typeof value === 'object' ? (value.id || value.planId || 'none') : value || 'none').trim();
            },
            get subscriptionPlanLabel() {
                if (this.subscriptionPlanId === 'subscriber') return tr('account.capacity.plan_subscriber');
                if (this.subscriptionPlanId === 'team') return tr('account.capacity.plan_team');
                return tr('account.capacity.no_paid_plan');
            },
            validCapacityLimits(value) {
                const devices = Number(value?.maxCoreDevices);
                const members = Number(value?.maxMembersPerDevice);
                return Number.isInteger(devices) && devices >= 0 && Number.isInteger(members) && members >= 0
                    ? { maxCoreDevices: devices, maxMembersPerDevice: members }
                    : null;
            },
            get effectiveCapacityLimits() {
                const authoritative = this.validCapacityLimits(
                    this.installation?.capacity?.effectiveLimits
                    || this.user?.capacity?.effectiveLimits
                    || this.user?.effectiveLimits
                );
                if (authoritative) return authoritative;
                const base = this.validCapacityLimits(this.capacityPolicy?.baseLevels?.[this.accountLevelId]);
                const paid = this.validCapacityLimits(this.capacityPolicy?.subscriptionPlans?.[this.subscriptionPlanId]);
                if (!base && !paid) return null;
                return {
                    maxCoreDevices: Math.max(base?.maxCoreDevices || 0, paid?.maxCoreDevices || 0),
                    maxMembersPerDevice: Math.max(base?.maxMembersPerDevice || 0, paid?.maxMembersPerDevice || 0),
                };
            },
            get coreDevicesUsed() {
                const value = this.user?.capacity?.usage?.coreDevices ?? this.user?.usage?.coreDevices;
                const number = Number(value);
                return Number.isInteger(number) && number >= 0 ? number : null;
            },
            get currentCloudDeviceId() { return this.installation?.cloudDeviceId || ''; },
            get membersUsed() {
                const authoritative = this.installation?.capacity?.usage?.members;
                if (Number.isInteger(Number(authoritative)) && Number(authoritative) >= 0) return Number(authoritative);
                return this.members.filter(member => !['core', 'owner'].includes(member.role) && member.status !== 'revoked').length;
            },
            get pendingSeatsUsed() {
                const authoritative = this.installation?.capacity?.usage?.pendingInvitations;
                if (Number.isInteger(Number(authoritative)) && Number(authoritative) >= 0) return Number(authoritative);
                return this.pendingInvitations.length;
            },
            get memberSeatsUsed() { return this.membersUsed + this.pendingSeatsUsed; },
            get memberSeatLimit() { return this.effectiveCapacityLimits?.maxMembersPerDevice ?? null; },
            get memberSeatAvailable() { return this.memberSeatLimit === null || this.memberSeatsUsed < this.memberSeatLimit; },
            get coreDeviceCapacityLabel() {
                const limit = this.effectiveCapacityLimits?.maxCoreDevices;
                return limit === undefined || limit === null ? tr('account.common.not_available') : ((this.coreDevicesUsed === null ? '—' : this.coreDevicesUsed) + ' / ' + limit);
            },
            get memberCapacityLabel() {
                return this.memberSeatLimit === null ? tr('account.common.not_available') : (this.memberSeatsUsed + ' / ' + this.memberSeatLimit);
            },
            get memberCapacityDetail() {
                if (this.memberSeatLimit === null) return tr('account.capacity.limit_pending');
                const memberText = tr(this.membersUsed === 1 ? 'account.members.count_one' : 'account.members.count_many', { count: this.membersUsed });
                const pendingText = tr(this.pendingSeatsUsed === 1 ? 'account.capacity.pending_one' : 'account.capacity.pending_many', { count: this.pendingSeatsUsed });
                const detail = memberText + ' + ' + pendingText;
                return this.memberSeatAvailable ? detail : detail + tr('account.capacity.no_invitations_suffix');
            },
            get hasRemoteEntitlement() { return this.entitlements.includes('remote.connect'); },
            get installationAccessLabel() {
                if (!this.signedIn || this.installationAccess === 'unknown') return this.signedIn ? tr('account.status.checking_access') : tr('account.status.not_signed_in');
                if (this.installationAccess === 'unregistered') return tr('account.status.not_registered');
                if (this.installationAccess === 'inactive') return tr('account.status.access_inactive');
                if (this.installationAccess === 'member') return tr('account.status.registered_role', { role: this.installation?.role || tr('account.common.member') });
                return this.cloudAccountIsDeviceCore() ? tr('account.status.device_owner') : tr('account.status.registered_role', { role: this.installation?.role || tr('account.common.manager') });
            },
            async refresh() {
                this.busy = true; this.clearNotice();
                try {
                    const me = await cloud('/auth/me');
                    this.applyUser(me.user);
                    if (await this.activateCloudAccountIfMember()) return;
                    const [pointResult, ledgerResult] = await Promise.all([
                        cloud('/points'), cloud('/points/ledger?limit=50'),
                    ]);
                    this.points = pointResult || this.points;
                    this.ledger = Array.isArray(ledgerResult && ledgerResult.items) ? ledgerResult.items : [];
                    await this.loadMembership();
                    if (!this.signedIn) return;
                    if (this.installationAccess === 'manager') await this.loadRemote();
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
                    this.password = ''; this.registrationNotice = ''; this.applyUser(result.user); if (await this.activateCloudAccountIfMember()) return; await this.loadMembership(); if (!this.signedIn) return; await this.loadLedger(); if (this.installationAccess === 'manager') await this.loadRemote(); notifyShell();
                } catch (error) {
                    if (error.code === 'EMAIL_NOT_VERIFIED') this.mode = 'verify';
                    this.fail(error);
                } finally { this.password = ''; this.busy = false; }
            },
            async register() {
                this.busy = true; this.clearNotice();
                try {
                    await cloud('/auth/register', { method: 'POST', body: { displayName: this.displayName, email: this.email, password: this.password } });
                    this.password = ''; this.mode = 'verify'; this.success(tr('account.success.account_created'));
                } catch (error) { this.fail(error); }
                finally { this.password = ''; this.busy = false; }
            },
            async verifyEmail() {
                this.busy = true; this.clearNotice();
                try {
                    await cloud('/auth/email/verify', { method: 'POST', body: { email: this.email, code: this.code } });
                    this.code = ''; this.mode = 'login'; this.success(tr('account.success.email_verified'));
                } catch (error) { this.fail(error); }
                finally { this.code = ''; this.busy = false; }
            },
            async resendCode() {
                this.busy = true; this.clearNotice();
                try { await cloud('/auth/email/resend', { method: 'POST', body: { email: this.email } }); this.success(tr('account.success.code_resent')); }
                catch (error) { this.fail(error); }
                finally { this.busy = false; }
            },
            async requestReset() {
                this.busy = true; this.clearNotice();
                try { await cloud('/auth/password/reset-request', { method: 'POST', body: { email: this.email } }); this.mode = 'reset'; this.success(tr('account.success.reset_code_sent')); }
                catch (error) { this.fail(error); }
                finally { this.busy = false; }
            },
            async resetPassword() {
                this.busy = true; this.clearNotice();
                try {
                    await cloud('/auth/password/reset', { method: 'POST', body: { email: this.email, code: this.code, newPassword: this.newPassword } });
                    this.code = ''; this.newPassword = ''; this.mode = 'login'; this.applyUser(null); this.success(tr('account.success.password_reset')); notifyShell();
                } catch (error) { this.fail(error); }
                finally { this.code = ''; this.newPassword = ''; this.busy = false; }
            },
            async logout() {
                this.busy = true; this.clearNotice();
                try { await cloud('/auth/logout', { method: 'POST' }); }
                catch (error) { if (error.status !== 401) this.fail(error); }
                finally { this.applyUser(null); this.ledger = []; this.email = ''; this.password = ''; this.handoffInput = ''; this.credentialEntryEnabled = false; this.handoffEntryEnabled = false; this.registrationNotice = ''; this.clearInstallationAccess('unknown'); this.remote = { devices: [], connector: {}, usage: {} }; this.pairingUrl = ''; this.pairingQr = ''; this.pairingExpiresAt = ''; this.mode = 'login'; this.busy = false; notifyShell(); }
            },
            get memberRoles() {
                return this.installation?.organizationType === 'business'
                    ? ['admin', 'developer', 'member', 'guest']
                    : ['member', 'child', 'guest'];
            },
            clearInstallationAccess(status) {
                this.installationAccess = status;
                this.installation = null;
                this.members = [];
                this.pendingInvitations = [];
                this.invitation = null;
                this.policy = null;
                this.policyEtag = '';
                this.memberOwnerPassword = '';
                this.policyOwnerPassword = '';
            },
            clearRemoteAccess() {
                this.remote = { devices: [], connector: {}, usage: {} };
                this.pairingUrl = '';
                this.pairingQr = '';
                this.pairingExpiresAt = '';
            },
            async rejectUnregisteredCloudAccount() {
                try { await cloud('/auth/logout', { method: 'POST' }); } catch (_) {}
                this.applyUser(null);
                this.email = '';
                this.password = '';
                this.handoffInput = '';
                this.credentialEntryEnabled = false;
                this.handoffEntryEnabled = false;
                this.ledger = [];
                this.clearInstallationAccess('unregistered');
                this.clearRemoteAccess();
                this.registrationNotice = tr('account.notice.unregistered_account');
                notifyShell();
            },
            async loadMembership() {
                if (!this.signedIn || (this.localIdentity && !this.localIdentity.isCore)) return;
                if (!this.capacityPolicy) await this.loadCapacityPolicy();
                this.clearInstallationAccess('unknown');
                try {
                    const installation = await cloud('/installation');
                    this.installation = installation || null;
                    const isDeviceCore = this.cloudAccountIsDeviceCore();
                    this.installationAccess = isDeviceCore ? 'manager' : 'member';
                    if (this.installationAccess !== 'manager') {
                        this.clearRemoteAccess();
                        await this.activateRegisteredCloudMember();
                        return;
                    }
                    const [members, policyResult, invitations] = await Promise.all([
                        cloud('/installation/members'),
                        cloud('/installation/policy', { includeMetadata: true }),
                        cloud('/installation/invitations?status=pending'),
                    ]);
                    this.applyPolicy(policyResult.payload, policyResult.etag);
                    this.members = (Array.isArray(members?.items) ? members.items : []).map(member => ({ ...member, pendingRole: member.role, quota: null, quotaEtag: '', quotaLoaded: false, quotaDraft: { allowedModelIds: '', monthlyPointLimit: '', concurrencyLimit: '' } }));
                    this.pendingInvitations = Array.isArray(invitations?.items) ? invitations.items : [];
                    await this.loadCoreDevices();
                    await Promise.all(this.members.filter(member => member.role !== 'core' && member.role !== 'owner').map(member => this.loadMemberQuota(member)));
                    if (!this.memberRoles.includes(this.inviteRole)) this.inviteRole = this.memberRoles[0] || 'member';
                } catch (error) {
                    if (this.isUnregisteredDeviceError(error)) {
                        await this.rejectUnregisteredCloudAccount();
                        return;
                    }
                    if (error.code === 'MEMBERSHIP_INACTIVE') {
                        this.clearInstallationAccess('inactive');
                        this.clearRemoteAccess();
                        return;
                    }
                    if (error.status !== 401) this.fail(error);
                }
            },
            async loadCoreDevices() {
                try {
                    const result = await cloud('/account/devices');
                    this.coreDevices = Array.isArray(result?.items)
                        ? result.items.map(device => ({ ...device, pendingDisplayName: device.displayName || '' }))
                        : [];
                } catch (error) {
                    this.coreDevices = [];
                    if (error.status !== 401 && error.status !== 403) this.fail(error);
                }
            },
            async renameCoreDevice(device) {
                const displayName = String(device.pendingDisplayName || '').trim();
                if (!displayName || displayName.length > 120) {
                    this.fail(new Error(tr('account.error.device_name_length')));
                    return;
                }
                if (displayName === device.displayName) return;
                this.busy = true; this.clearNotice();
                try {
                    const updated = await cloud('/account/devices/' + encodeURIComponent(device.id), {
                        method: 'PATCH', body: { displayName },
                    });
                    this.coreDevices = this.coreDevices.map(item => item.id === device.id
                        ? { ...updated, pendingDisplayName: updated.displayName || displayName }
                        : item);
                    this.remote.devices = this.remote.devices.map(item => item.deviceId === device.id
                        ? { ...item, displayName: updated.displayName || displayName }
                        : item);
                    this.success(tr('account.success.device_renamed'));
                } catch (error) {
                    device.pendingDisplayName = device.displayName || '';
                    this.fail(error);
                } finally { this.busy = false; }
            },
            async revokeCoreDevice(device) {
                if (!this.deviceOwnerPassword) {
                    this.fail(new Error(tr('account.error.device_revoke_password')));
                    return;
                }
                const deviceId = device.id || device.deviceId;
                const current = deviceId === this.currentCloudDeviceId;
                const warning = current
                    ? tr('account.confirm.revoke_this_device')
                    : tr('account.confirm.revoke_named_device', { device: device.displayName || tr('account.devices.this_device_lower') });
                if (!confirm(warning + ' ' + tr('account.confirm.cannot_undo'))) return;
                this.busy = true; this.clearNotice();
                try {
                    await cloud('/account/devices/' + encodeURIComponent(deviceId) + '/revoke', {
                        method: 'POST', body: { ownerPassword: this.deviceOwnerPassword },
                    });
                    this.deviceOwnerPassword = '';
                    if (current) {
                        window.top.location.assign('/admin');
                        return;
                    }
                    const me = await cloud('/auth/me');
                    this.applyUser(me.user);
                    await this.loadCoreDevices();
                    this.success(tr('account.success.device_revoked'));
                } catch (error) { this.fail(error); }
                finally { this.deviceOwnerPassword = ''; this.busy = false; }
            },
            async inviteMember() {
                this.busy = true; this.invitationCreating = true; this.invitation = null; this.clearNotice();
                try {
                    const targetEmail = this.inviteEmail;
                    const created = await cloud('/installation/invitations', { method: 'POST', body: { email: targetEmail, role: this.inviteRole } });
                    this.invitation = { ...created, email: targetEmail };
                    this.upsertPendingInvitation({ ...created, email: targetEmail, status: 'pending' });
                    this.inviteEmail = '';
                    this.noticeInvitationDelivery(this.invitation, false);
                    this.loadPendingInvitations().catch(() => {});
                } catch (error) { this.fail(error); }
                finally { this.invitationCreating = false; this.busy = false; }
            },
            upsertPendingInvitation(invitation) {
                if (!invitation?.invitationId) return;
                const index = this.pendingInvitations.findIndex(item => item.invitationId === invitation.invitationId);
                if (index < 0) this.pendingInvitations = [invitation, ...this.pendingInvitations];
                else this.pendingInvitations = this.pendingInvitations.map((item, itemIndex) => itemIndex === index ? { ...item, ...invitation } : item);
            },
            async loadPendingInvitations() {
                const result = await cloud('/installation/invitations?status=pending');
                this.pendingInvitations = Array.isArray(result?.items) ? result.items : [];
            },
            invitationDeliveryLabel(delivery) {
                const status = String(delivery?.status || 'pending');
                if (status === 'sent') return tr('account.delivery.sent');
                if (status === 'failed') return tr('account.delivery.failed');
                return tr('account.delivery.pending');
            },
            invitationDeliveryClass(delivery) {
                const status = String(delivery?.status || 'pending');
                return status === 'sent' ? 'delivery-sent' : (status === 'failed' ? 'delivery-failed' : 'delivery-pending');
            },
            invitationDeliveryDetail(delivery) {
                if (!delivery) return tr('account.delivery.unavailable');
                const attempts = Number(delivery.attempts || 0);
                if (delivery.status === 'failed') return tr('account.delivery.attempt_failed', { count: attempts, detail: delivery.failureCategory ? ' · ' + delivery.failureCategory : '' });
                if (delivery.status === 'sent') return tr('account.delivery.accepted', { detail: delivery.deliveredAt ? ' · ' + this.formatTime(delivery.deliveredAt) : '' });
                return attempts ? tr('account.delivery.attempt_pending', { count: attempts }) : tr('account.delivery.waiting');
            },
            noticeInvitationDelivery(invitation, resent) {
                if (invitation?.delivery?.status === 'sent') {
                    this.success(tr(resent ? 'account.delivery.resent_success' : 'account.delivery.sent_success', { email: invitation.email || tr('account.delivery.invited_address') }));
                    return;
                }
                if (invitation?.delivery?.status === 'failed') {
                    this.message = tr('account.delivery.failed_notice');
                    this.messageTone = 'error';
                    return;
                }
                this.success(tr('account.delivery.created_pending'));
            },
            async resendInvitation(item) {
                if (!item?.invitationId) return;
                this.busy = true; this.clearNotice();
                try {
                    const resent = await cloud('/installation/invitations/' + encodeURIComponent(item.invitationId) + '/resend', { method: 'POST' });
                    this.invitation = { ...resent, email: item.email || '' };
                    this.upsertPendingInvitation({ ...item, ...resent, email: item.email || '', status: 'pending' });
                    this.noticeInvitationDelivery(this.invitation, true);
                    this.loadPendingInvitations().catch(() => {});
                } catch (error) { this.fail(error); }
                finally { this.busy = false; }
            },
            async cancelInvitation() {
                if (!this.invitation?.invitationId) return;
                await this.cancelPendingInvitation(this.invitation);
            },
            async cancelPendingInvitation(item) {
                if (!item?.invitationId) return;
                this.busy = true; this.clearNotice();
                try {
                    await cloud('/installation/invitations/' + encodeURIComponent(item.invitationId) + '/cancel', { method: 'POST' });
                    if (this.invitation?.invitationId === item.invitationId) this.invitation = null;
                    await this.loadPendingInvitations();
                    this.success(tr('account.success.invitation_cancelled'));
                } catch (error) { this.fail(error); }
                finally { this.busy = false; }
            },
            async copyInvitationLink() {
                try { await navigator.clipboard.writeText(this.invitation?.inviteUrl || this.invitation?.inviteCode || ''); this.success(tr('account.success.invitation_copied')); }
                catch (_) { this.fail(new Error(tr('account.error.invitation_copy'))); }
            },
            openInvitationLink() {
                const url = this.invitation?.inviteUrl;
                if (url) window.open(url, '_blank', 'noopener,noreferrer');
            },
            listText(value) { return Array.isArray(value) ? value.join('\n') : ''; },
            listValue(value) {
                const items = String(value || '').split(/[\n,]/).map(item => item.trim()).filter(Boolean);
                return items.length ? [...new Set(items)] : null;
            },
            nullableDecimal(value) { const text = String(value ?? '').trim(); return text === '' ? null : text; },
            applyPolicy(policy, etag) {
                this.policy = policy || null;
                this.policyEtag = etag || (policy?.policyVersion ? '"policy-' + policy.policyVersion + '"' : '');
                if (!policy) return;
                this.policyDraft = {
                    allowedAppIds: this.listText(policy.allowedAppIds),
                    allowedModelIds: this.listText(policy.allowedModelIds),
                    defaultMonthlyPointLimit: policy.defaultMonthlyPointLimit ?? '',
                    defaultConcurrencyLimit: policy.defaultConcurrencyLimit,
                    offlineGraceSeconds: policy.offlineGraceSeconds,
                };
            },
            async savePolicy() {
                if (!this.policyEtag || !this.policyOwnerPassword) { this.fail(new Error(tr('account.error.policy_owner_password'))); return; }
                this.busy = true; this.clearNotice();
                try {
                    const result = await cloud('/installation/policy', { method: 'PATCH', includeMetadata: true, headers: { 'If-Match': this.policyEtag }, body: {
                        allowedAppIds: this.listValue(this.policyDraft.allowedAppIds),
                        allowedModelIds: this.listValue(this.policyDraft.allowedModelIds),
                        defaultMonthlyPointLimit: this.nullableDecimal(this.policyDraft.defaultMonthlyPointLimit),
                        defaultConcurrencyLimit: Number(this.policyDraft.defaultConcurrencyLimit),
                        offlineGraceSeconds: Number(this.policyDraft.offlineGraceSeconds),
                        ownerPassword: this.policyOwnerPassword,
                    }});
                    this.applyPolicy(result.payload, result.etag); this.policyOwnerPassword = '';
                    await this.loadMembership(); this.success(tr('account.success.policy_updated'));
                } catch (error) { if (error.code === 'POLICY_VERSION_MISMATCH') await this.loadMembership(); this.fail(error); }
                finally { this.policyOwnerPassword = ''; this.busy = false; }
            },
            async loadMemberQuota(member) {
                try {
                    const result = await cloud('/installation/members/' + encodeURIComponent(member.userId) + '/quota', { includeMetadata: true });
                    member.quota = result.payload; member.quotaEtag = result.etag || this.policyEtag;
                    member.quotaLoaded = true;
                    member.quotaDraft = { allowedModelIds: this.listText(result.payload?.allowedModelIds), monthlyPointLimit: result.payload?.monthlyPointLimit ?? '', concurrencyLimit: result.payload?.concurrencyLimit ?? '' };
                } catch (error) { member.quotaError = error.message || String(error); }
            },
            async saveMemberQuota(member) {
                if (!member?.quotaDraft || !member.quotaEtag || !this.policyOwnerPassword) { this.fail(new Error(tr('account.error.quota_owner_password'))); return; }
                this.busy = true; this.clearNotice();
                try {
                    const concurrency = String(member.quotaDraft.concurrencyLimit ?? '').trim();
                    const result = await cloud('/installation/members/' + encodeURIComponent(member.userId) + '/quota', { method: 'PATCH', includeMetadata: true, headers: { 'If-Match': member.quotaEtag }, body: {
                        allowedModelIds: this.listValue(member.quotaDraft.allowedModelIds),
                        monthlyPointLimit: this.nullableDecimal(member.quotaDraft.monthlyPointLimit),
                        concurrencyLimit: concurrency === '' ? null : Number(concurrency),
                        ownerPassword: this.policyOwnerPassword,
                    }});
                    member.quota = result.payload; member.quotaEtag = result.etag || member.quotaEtag; this.policyOwnerPassword = '';
                    await this.loadMembership(); this.success(tr('account.success.quota_updated'));
                } catch (error) { if (error.code === 'POLICY_VERSION_MISMATCH') await this.loadMembership(); this.fail(error); }
                finally { this.policyOwnerPassword = ''; this.busy = false; }
            },
            async updateMember(member, changes) {
                if (!member || member.role === 'core' || member.role === 'owner') return;
                const roleChange = Object.prototype.hasOwnProperty.call(changes, 'role');
                if (roleChange && !this.memberOwnerPassword) {
                    this.fail(new Error(tr('account.error.owner_password_role')));
                    return;
                }
                if (changes.status === 'revoked' && !confirm(tr('account.confirm.remove_member'))) return;
                this.busy = true; this.clearNotice();
                try {
                    await cloud('/installation/members/' + encodeURIComponent(member.userId), {
                        method: 'PATCH',
                        body: { ...changes, ...(roleChange ? { ownerPassword: this.memberOwnerPassword } : {}) },
                    });
                    this.memberOwnerPassword = '';
                    await this.loadMembership();
                    this.success(tr(changes.status === 'revoked' ? 'account.success.member_removed' : 'account.success.member_updated'));
                } catch (error) { member.pendingRole = member.role; this.fail(error); }
                finally { this.memberOwnerPassword = ''; this.busy = false; }
            },
            async verifyAdmin() {
                this.busy = true; this.clearNotice();
                try {
                    const result = await cloud('/admin/reauth', { method: 'POST', body: { password: this.adminPassword } });
                    this.adminVerifiedUntil = result.expiresAt || '';
                    this.success(tr('account.success.admin_verified'));
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
            async registerRemote() { this.busy = true; this.clearNotice(); try { await remoteRequest('/devices', { method:'POST', body:{ displayName:this.remoteName } }); await this.loadRemote(); this.success(tr('account.success.remote_registered')); } catch(error){ this.fail(error); } finally { this.busy=false; } },
            async startRemote(device) { this.busy=true; this.clearNotice(); try { await remoteRequest('/devices/'+encodeURIComponent(device.deviceId)+'/start',{method:'POST'}); await this.loadRemote(); this.success(tr('account.success.remote_starting')); } catch(error){this.fail(error);} finally{this.busy=false;} },
            async stopRemote(device) { this.busy=true; this.clearNotice(); try { await remoteRequest('/devices/'+encodeURIComponent(device.deviceId)+'/stop',{method:'POST'}); await this.loadRemote(); this.success(tr('account.success.remote_stopped')); } catch(error){this.fail(error);} finally{this.busy=false;} },
            async rotateRemote(device) { this.busy=true; this.clearNotice(); try { const wasEnabled=device.enabled; await remoteRequest('/devices/'+encodeURIComponent(device.deviceId)+'/credentials/rotate',{method:'POST'}); await this.loadRemote(); this.success(tr(wasEnabled?'account.success.remote_rotated_reconnecting':'account.success.remote_rotated')); } catch(error){await this.loadRemote();this.fail(error);} finally{this.busy=false;} },
            async createPairing(device) { this.busy=true; this.clearNotice(); try { const result=await remoteRequest('/devices/'+encodeURIComponent(device.deviceId)+'/pairing-challenges',{method:'POST'}); this.pairingUrl=result.pairingUrl||''; this.pairingQr=result.pairingQrDataUrl||''; this.pairingExpiresAt=result.expiresAt||''; this.success(tr('account.success.pairing_created')); } catch(error){this.pairingUrl='';this.pairingQr='';this.pairingExpiresAt='';this.fail(error);} finally{this.busy=false;} },
            async reregisterRemote(device) { if(!confirm(tr('account.confirm.reregister_remote'))) return; this.busy=true; this.clearNotice(); const displayName=device.displayName||this.remoteName||tr('account.remote.this_mac'); try { await remoteRequest('/devices/'+encodeURIComponent(device.deviceId),{method:'DELETE'}); await remoteRequest('/devices',{method:'POST',body:{displayName}}); await this.loadRemote(); this.success(tr('account.success.remote_reregistered')); } catch(error){ try { await this.loadRemote(); } catch(_) {} this.fail(error); } finally{this.busy=false;} },
            async copyPairing() { try { await navigator.clipboard.writeText(this.pairingUrl); this.success(tr('account.success.pairing_copied')); } catch(_) { this.fail(new Error(tr('account.error.pairing_copy'))); } },
            async sharePairing() { if(navigator.share) { try { await navigator.share({title:tr('account.remote.share_title'),url:this.pairingUrl}); } catch(_){} } else await this.copyPairing(); },
            formatBytes(value) { const size=Number(value||0); if(!Number.isFinite(size)) return String(value); const units=['B','KiB','MiB','GiB']; let amount=size,index=0; while(amount>=1024&&index<units.length-1){amount/=1024;index++;} return amount.toFixed(index?1:0)+' '+units[index]; },
            initials() {
                const value = (this.user && (this.user.displayName || this.user.email)) || 'A';
                return value.trim().slice(0, 2).toUpperCase();
            },
            shortIdentity(value) {
                const text = String(value || '');
                return text.length > 18 ? text.slice(0, 8) + '…' + text.slice(-6) : text;
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
