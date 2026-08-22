(function () {
    'use strict';

    const boot = window.AI2APPS_SHELL_BOOT || { apps: [], initialAppId: '' };
    const root = document.getElementById('ai2apps-shell');
    if (!root) return;

    const storage = {
        mode: 'ai2apps.shell.dockMode',
        pinned: 'ai2apps.shell.pinnedApps',
        order: 'ai2apps.shell.dockOrder',
        warm: 'ai2apps.shell.warmApps',
    };
    const appStage = root.querySelector('.app-stage');
    const home = root.querySelector('.desktop-home');
    const homeApps = root.querySelector('[data-desktop-home-apps]');
    const homeAccount = root.querySelector('[data-desktop-home-account]');
    const desktopClientVersion = root.querySelector('[data-desktop-client-version]');
    let frame = root.querySelector('.app-frame');
    let spareFrame = frame;
    const loading = root.querySelector('.app-loading');
    const dockApps = root.querySelector('.dock-apps');
    const currentName = root.querySelector('.dock-current-name');
    const accountButton = root.querySelector('.dock-account');
    const accountName = root.querySelector('[data-account-name]');
    const accountDetail = root.querySelector('[data-account-detail]');
    const modeButton = root.querySelector('[data-shell-action="toggle-mode"]');
    const closeButton = root.querySelector('[data-shell-action="close-current"]');
    const launcher = root.querySelector('.app-launcher');
    const launcherGrid = root.querySelector('.launcher-grid');
    const launcherEmpty = root.querySelector('.launcher-empty');
    const categoryHost = root.querySelector('.launcher-categories');
    const search = root.querySelector('[data-launcher-search]');
    const toast = root.querySelector('.shell-toast');
    const control = root.querySelector('.system-control');
    const controlContent = root.querySelector('.control-content');
    const controlAlert = root.querySelector('.control-alert-count');
    const dockContextMenu = root.querySelector('.dock-context-menu');
    const dockContextDismiss = root.querySelector('.dock-context-dismiss');
    const dockTooltipHost = root.querySelector('.dock-tooltip-host');

    let apps = [];
    let byId = new Map();
    let mode = localStorage.getItem(storage.mode) === 'immersive' ? 'immersive' : 'docked';
    let pinned = [];
    let dockOrder = [];
    let warmApps = [];
    let currentId = boot.initialAppId || '';
    let currentInstanceId = boot.initialInstanceId || null;
    let currentMountToken = null;
    let homeAppsLocked = false;
    let activeCategory = 'All';
    let dockHideTimer = null;
    let toastTimer = null;
    let launchSequence = 0;
    let controlTab = 'overview';
    let controlSnapshot = null;
    let approvalSnapshot = [];
    let grantSnapshot = [];
    let contextAppId = null;
    let dockDraggingId = null;
    let suppressDockClick = false;
    let dockTooltipTimer = null;
    let principalBoundary = null;
    let principalBoundarySync = Promise.resolve();
    const framePool = new Map();
    const frameCacheLimit = 4;
    const persistentFrameApps = new Set(['ai2apps.general-chat', 'ai2apps.coder']);
    const appBadges = new Map();
    const capabilityBridgeWaiters = new Map();

    function escapeHtml(value) {
        return String(value == null ? '' : value).replace(/[&<>"]/g, (character) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;',
        })[character]);
    }

    async function applyDesktopClientVersion() {
        const getDesktopInfo = window.ai2appsDesktop?.getDesktopInfo;
        if (!desktopClientVersion) return;
        let rawVersion = '';
        try {
            if (typeof getDesktopInfo === 'function') {
                const info = await getDesktopInfo();
                rawVersion = String(info?.version || '').trim();
            }
        } catch (error) {
            console.warn('Unable to read AI2Apps Desktop version', error);
        }
        if (!rawVersion || rawVersion.toLowerCase() === 'unknown') {
            const userAgentVersion = navigator.userAgent.match(
                /(?:^|\s)AI2Apps\/([^\s]+)/i
            );
            rawVersion = String(userAgentVersion?.[1] || '').trim();
        }
        if (!rawVersion || rawVersion.toLowerCase() === 'unknown') return;
        desktopClientVersion.textContent = ' · ' + (
            rawVersion.toLowerCase().startsWith('v') ? rawVersion : `v${rawVersion}`
        );
        desktopClientVersion.hidden = false;
    }

    function tr(key, values) {
        let text = typeof window.t === 'function' ? window.t(key) : key;
        Object.entries(values || {}).forEach(([name, value]) => {
            text = text.replaceAll('{' + name + '}', String(value));
        });
        return text;
    }

    function normalizeApp(item) {
        const navigation = item.navigation || {};
        const id = item.app_key || item.id;
        return {
            id,
            name: item.display_name || item.name || id,
            description: item.description || '',
            category: navigation.category || item.category || 'Third-party',
            icon: navigation.icon || item.icon || 'app-window',
            pinnedDefault: Boolean(navigation.pinned_default),
            singleton: item.instance_mode ? item.instance_mode === 'singleton' : Boolean(item.singleton),
            instanceMode: item.instance_mode || (item.singleton ? 'singleton' : 'multiple'),
            source: item.source || 'builtin',
            entryUrl: item.entry_url || '',
            instances: Array.isArray(item.instances) ? item.instances : [],
        };
    }

    function safeIcon(name) {
        return /^[a-z0-9-]{1,48}$/.test(name || '') ? name : 'app-window';
    }

    function iconMarkup(name) {
        return '<i data-lucide="' + safeIcon(name) + '"></i>';
    }

    function readPins() {
        try {
            const value = JSON.parse(localStorage.getItem(storage.pinned));
            if (Array.isArray(value)) return value.filter((id) => byId.has(id));
        } catch (_) { /* use manifest defaults */ }
        return apps.filter((app) => app.pinnedDefault).map((app) => app.id);
    }

    function readDockOrder() {
        try {
            const value = JSON.parse(localStorage.getItem(storage.order));
            if (Array.isArray(value)) return value.filter((id) => byId.has(id));
        } catch (_) { /* begin with manifest order */ }
        return [];
    }

    function readWarmApps() {
        try {
            const value = JSON.parse(localStorage.getItem(storage.warm));
            if (Array.isArray(value)) return value.filter((id) => byId.has(id));
        } catch (_) { /* no explicit warm Apps */ }
        return [];
    }

    function persist() {
        localStorage.setItem(storage.mode, mode);
        localStorage.setItem(storage.pinned, JSON.stringify(pinned));
        localStorage.setItem(storage.order, JSON.stringify(dockOrder));
        localStorage.setItem(storage.warm, JSON.stringify(warmApps));
    }

    async function request(url, options) {
        const response = await fetch(url, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
            ...(options || {}),
        });
        if (!response.ok) {
            let detail = 'HTTP ' + response.status;
            try {
                const body = await response.json();
                detail = typeof body.detail === 'string' ? body.detail : body.detail?.message || detail;
            } catch (_) { /* retain status */ }
            const error = new Error(detail);
            error.status = response.status;
            throw error;
        }
        return response.json();
    }

    function jsonRequest(url, method, body) {
        return request(url, {
            method: method || 'GET',
            headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
            body: body === undefined ? undefined : JSON.stringify(body),
        });
    }

    async function refreshAccountStatus() {
        try {
            const result = await request('/admin/api/shell/account-status');
            const state = result.state || 'unavailable';
            accountButton.classList.toggle('is-signed-in', state === 'signed_in');
            accountButton.classList.toggle('is-unavailable', state === 'unavailable');
            if (state === 'signed_in') {
                accountName.textContent = result.display_name || 'AI2Apps Account';
                accountDetail.textContent = (result.points || '0') + ' points';
                accountButton.title = result.email ? result.email + ' · Open Account App' : 'Open Account App';
            } else if (state === 'local_member') {
                accountName.textContent = result.display_name || 'Local member';
                accountDetail.textContent = result.role || 'member';
                accountButton.title = 'Open Local Account';
            } else if (state === 'signed_out') {
                accountName.textContent = 'Not signed in';
                accountDetail.textContent = 'Local features available';
                accountButton.title = 'Sign in to AI2Apps Cloud';
            } else {
                accountName.textContent = 'Cloud unavailable';
                accountDetail.textContent = 'Local features available';
                accountButton.title = 'Open Account App';
            }
            renderHomeAccount(result);
            return result;
        } catch (_) {
            accountButton.classList.remove('is-signed-in');
            accountButton.classList.add('is-unavailable');
            accountName.textContent = 'Cloud unavailable';
            accountDetail.textContent = 'Local features available';
            renderHomeAccount({ state: 'unavailable' });
            return null;
        }
    }

    async function loadCatalog(options) {
        try {
            const result = await request('/admin/api/shell/apps');
            apps = result.items.map(normalizeApp);
        } catch (error) {
            apps = options?.fallback === false ? [] : boot.apps.map(normalizeApp);
            if (!options || !options.quiet) showToast('App Runtime unavailable: ' + error.message);
        }
        byId = new Map(apps.map((app) => [app.id, app]));
        if (!pinned.length) pinned = readPins();
        else pinned = pinned.filter((id) => byId.has(id));
        if (!dockOrder.length) dockOrder = readDockOrder();
        else dockOrder = dockOrder.filter((id) => byId.has(id));
        if (!warmApps.length) warmApps = readWarmApps();
        else warmApps = warmApps.filter((id) => byId.has(id));
        renderDock();
        renderHomeApps();
        if (launcher.classList.contains('is-open')) {
            renderCategories();
            renderLauncher();
        }
    }

    function refreshIcons() {
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            try { window.lucide.createIcons(); } catch (_) { /* base template also processes icons */ }
        }
    }

    function applyDesktopDeviceLabel() {
        const labels = Array.from(root.querySelectorAll('[data-desktop-device-label]'));
        const serverLabel = labels[0]?.textContent.trim() || '';
        let label = ['Mac', 'PC', 'Spark'].includes(serverLabel) ? serverLabel : '';
        if (!label) {
            const clientPlatform = [
                navigator.userAgentData?.platform,
                navigator.platform,
                navigator.userAgent,
            ].filter(Boolean).join(' ');
            if (/mac/i.test(clientPlatform)) label = 'Mac';
            else if (/win|linux|x11/i.test(clientPlatform)) label = 'PC';
            else label = 'Device';
        }
        labels.forEach((element) => { element.textContent = label; });
    }

    function renderHomeAccount(result) {
        const state = result.state || 'unavailable';
        const registered = result.installation_registered;
        const signedInCore = state === 'signed_in' && result.signed_in_user_is_core !== false;
        const localMember = state === 'local_member';
        homeAppsLocked = registered === true && state === 'signed_out';
        if (signedInCore || localMember || (state === 'signed_in' && registered === true)) {
            homeAccount.hidden = true;
            renderHomeApps();
            return;
        }

        const setup = registered === false;
        const knownSignedOut = state === 'signed_out';
        if (!setup && !knownSignedOut) {
            homeAccount.hidden = true;
            renderHomeApps();
            return;
        }
        homeAccount.hidden = false;
        homeAccount.dataset.mode = setup ? 'setup' : 'signin';
        homeAccount.querySelector('[data-home-account-title]').textContent = setup
            ? tr('shell.home.account.setup.title')
            : tr('shell.home.account.signin.title');
        homeAccount.querySelector('[data-home-account-body]').textContent = setup
            ? tr('shell.home.account.setup.body')
            : tr('shell.home.account.signin.body');
        homeAccount.querySelector('[data-home-account-action-label]').textContent = setup
            ? tr('shell.home.account.setup.action') : tr('shell.home.account.signin.action');
        const benefits = setup
            ? [['smartphone', tr('shell.home.account.setup.phone')], ['shield-check', tr('shell.home.account.setup.ownership')], ['users', tr('shell.home.account.setup.members')]]
            : [['lock-keyhole', tr('shell.home.account.signin.limited')], ['refresh-cw', tr('shell.home.account.signin.restore')]];
        homeAccount.querySelector('[data-home-account-benefits]').innerHTML = benefits.map((item) =>
            '<span><i data-lucide="' + item[0] + '"></i>' + escapeHtml(item[1]) + '</span>'
        ).join('');
        renderHomeApps();
        refreshIcons();
    }

    function renderHomeApps() {
        const preferred = ['ai2apps.general-chat', 'ai2apps.coder', 'ai2apps.dashboard', 'ai2apps.models'];
        const visible = [
            ...preferred.map((id) => byId.get(id)).filter(Boolean),
            ...apps.filter((app) => !preferred.includes(app.id)),
        ].slice(0, 4);
        homeApps.innerHTML = visible.map((app) =>
            '<button class="desktop-home-app' + (homeAppsLocked ? ' is-locked' : '') +
                '" type="button" data-home-app-id="' + escapeHtml(app.id) + '"' +
                (homeAppsLocked ? ' disabled aria-disabled="true" title="' + escapeHtml(tr('shell.home.apps.signin_title')) + '"' : '') + '>' +
                '<span class="desktop-home-app-icon">' + iconMarkup(app.icon) + '</span>' +
                '<span class="desktop-home-app-copy"><strong>' + escapeHtml(app.name) + '</strong><small>' +
                    escapeHtml(homeAppsLocked ? tr('shell.home.apps.signin_description') : app.description || tr('shell.home.apps.open', { app: app.name })) + '</small></span>' +
                '<i class="desktop-home-app-arrow" data-lucide="' + (homeAppsLocked ? 'lock-keyhole' : 'arrow-up-right') + '"></i>' +
            '</button>'
        ).join('');
        refreshIcons();
    }

    function showToast(message) {
        toast.textContent = message;
        toast.classList.add('is-visible');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 2200);
    }

    function updateMode(options) {
        root.dataset.mode = mode;
        root.classList.toggle('dock-visible', mode === 'docked');
        const immersive = mode === 'immersive';
        modeButton.setAttribute('aria-label', immersive ? 'Keep Dock visible' : 'Enter immersive mode');
        modeButton.innerHTML = iconMarkup(immersive ? 'panel-top-open' : 'maximize-2');
        if (!options || options.persist !== false) persist();
        refreshIcons();
    }

    function setDockVisible(visible) {
        if (mode !== 'immersive') return;
        clearTimeout(dockHideTimer);
        if (visible) root.classList.add('dock-visible');
        else dockHideTimer = setTimeout(() => {
            if (!launcher.classList.contains('is-open')) root.classList.remove('dock-visible');
        }, 520);
    }

    function runningApps() {
        return apps.filter((app) => app.instances.length > 0).map((app) => app.id);
    }

    function renderDock() {
        const available = [...new Set([...pinned, ...runningApps()])].filter((id) => byId.has(id));
        const ids = [
            ...dockOrder.filter((id) => available.includes(id)),
            ...available.filter((id) => !dockOrder.includes(id)),
        ];
        dockOrder = [...ids, ...dockOrder.filter((id) => !ids.includes(id) && byId.has(id))];
        dockApps.innerHTML = ids.map((id) => {
            const app = byId.get(id);
            const classes = [
                'dock-app-wrap',
                app.instances.length ? 'is-running' : '',
                id === currentId ? 'is-current' : '',
            ].filter(Boolean).join(' ');
            const count = app.instances.length > 1
                ? '<span class="dock-instance-count">' + app.instances.length + '</span>' : '';
            const badge = appBadges.get(id);
            const badgeMarkup = badge == null || badge === '' || badge === false
                ? '' : '<span class="dock-instance-count" title="App status">' +
                    escapeHtml(typeof badge === 'object' ? badge.text || badge.count || '•' : badge) + '</span>';
            return '<span class="' + classes + '" draggable="true" data-dock-drag-id="' + escapeHtml(id) + '">' +
                '<button class="dock-app-button" type="button" data-app-id="' + escapeHtml(id) +
                '" aria-label="Open ' + escapeHtml(app.name) + '" data-dock-tooltip="' +
                escapeHtml(app.name) + '">' + iconMarkup(app.icon) + count + badgeMarkup + '</button></span>';
        }).join('');
        closeButton.disabled = !currentInstanceId;
        refreshIcons();
    }

    function launcherApps() {
        const term = search.value.trim().toLowerCase();
        return apps.filter((app) => {
            const inCategory = activeCategory === 'All' || app.category === activeCategory;
            const haystack = (app.name + ' ' + app.description + ' ' + app.category).toLowerCase();
            return inCategory && (!term || haystack.includes(term));
        });
    }

    function instanceControls(app) {
        const switches = app.instances.slice(0, 4).map((instance, index) =>
            '<button class="launcher-instance" type="button" data-app-id="' + escapeHtml(app.id) +
            '" data-instance-id="' + escapeHtml(instance.id) + '">' +
            escapeHtml(app.singleton ? 'Open' : 'Window ' + (index + 1)) + '</button>'
        ).join('');
        const create = app.instanceMode === 'multiple'
            ? '<button class="launcher-instance launcher-instance-new" type="button" data-new-app-id="' +
              escapeHtml(app.id) + '">+ New</button>' : '';
        return switches || create ? '<div class="launcher-instances">' + switches + create + '</div>' : '';
    }

    function renderLauncher() {
        const visible = launcherApps();
        launcherGrid.innerHTML = visible.map((app) =>
            '<article class="launcher-app" role="listitem">' +
              '<button class="launcher-app-open" type="button" data-app-id="' + escapeHtml(app.id) + '">' +
                '<span class="launcher-app-icon">' + iconMarkup(app.icon) + '</span>' +
                '<span class="launcher-app-name">' + escapeHtml(app.name) + '</span>' +
                '<span class="launcher-app-description">' + escapeHtml(app.description) + '</span>' +
                '<span class="launcher-app-meta">' + escapeHtml(app.category) +
                (app.singleton ? ' · Single instance' : ' · Multiple instances') +
                (app.instances.length ? ' · Running ' + app.instances.length : '') + '</span>' +
              '</button>' + instanceControls(app) +
              '<button class="launcher-pin' + (pinned.includes(app.id) ? ' is-pinned' : '') +
              '" type="button" data-pin-id="' + escapeHtml(app.id) + '" aria-label="' +
              (pinned.includes(app.id) ? 'Unpin ' : 'Pin ') + escapeHtml(app.name) + '" title="' +
              (pinned.includes(app.id) ? 'Unpin from Dock' : 'Pin to Dock') + '">' +
              iconMarkup('pin') + '</button>' +
            '</article>'
        ).join('');
        launcherEmpty.hidden = visible.length !== 0;
        refreshIcons();
    }

    function renderCategories() {
        const categories = ['All', ...new Set(['TestFlight', ...apps.map((app) => app.category)])];
        categoryHost.innerHTML = categories.map((category) =>
            '<button class="launcher-category' + (category === activeCategory ? ' is-active' : '') +
            '" type="button" data-category="' + escapeHtml(category) + '">' + escapeHtml(category) + '</button>'
        ).join('');
    }

    function openLauncher() {
        launcher.classList.add('is-open');
        launcher.setAttribute('aria-hidden', 'false');
        root.querySelectorAll('[data-shell-action="launcher"]').forEach((button) => button.setAttribute('aria-expanded', 'true'));
        setDockVisible(true);
        renderCategories();
        renderLauncher();
        loadCatalog({ quiet: true }).then(() => {
            if (launcher.classList.contains('is-open')) {
                renderCategories();
                renderLauncher();
            }
        }).catch(() => {});
        setTimeout(() => search.focus(), 30);
    }

    function closeLauncher() {
        launcher.classList.remove('is-open');
        launcher.setAttribute('aria-hidden', 'true');
        root.querySelectorAll('[data-shell-action="launcher"]').forEach((button) => button.setAttribute('aria-expanded', 'false'));
        setDockVisible(false);
    }

    function closeControl() {
        control.classList.remove('is-open');
        control.setAttribute('aria-hidden', 'true');
        setDockVisible(false);
    }

    function trustLabel(pkg) {
        const signature = pkg.verification?.signature || {};
        const audit = pkg.verification?.audit || {};
        if (signature.trust === 'trusted' && audit.decision === 'approve') return ['Verified', ''];
        if (audit.decision === 'reject' || signature.trust === 'revoked') return ['Blocked', 'danger'];
        return ['Review', 'warning'];
    }

    function metadataRows(values) {
        return '<dl class="control-meta">' + values.map((item) =>
            '<dt>' + escapeHtml(item[0]) + '</dt><dd>' + escapeHtml(item[1] == null ? '—' : item[1]) + '</dd>'
        ).join('') + '</dl>';
    }

    function renderRecovery() {
        const safe = controlSnapshot.safe_mode || {};
        const conflicts = (controlSnapshot.patches || []).filter((patch) => patch.status === 'conflicted');
        return '<section class="control-section"><p class="control-section-title">Safe Mode</p>' +
            '<article class="control-card"><div class="control-card-head"><div><h2>' +
            (safe.active ? 'Safe Mode is active' : 'Normal mode') + '</h2><p>' +
            (safe.active ? 'Local Agent and App patches are disabled. Built-in recovery controls remain available.' :
                'Installed definitions and approved local patches are active.') + '</p></div><span class="control-pill ' +
            (safe.active ? 'warning' : '') + '">' + (safe.active ? 'Protected' : 'Healthy') + '</span></div>' +
            metadataRows([['Reason', safe.reason || '—'], ['Updated', safe.updated_at || '—']]) +
            '<div class="control-actions"><button class="control-action ' + (safe.active ? '' : 'danger') +
            '" type="button" data-safe-mode="' + (safe.active ? 'off' : 'on') + '">' +
            (safe.active ? 'Leave Safe Mode' : 'Enter Safe Mode') + '</button></div></article></section>' +
            '<section class="control-section"><p class="control-section-title">Recovery summary</p>' +
            '<article class="control-card"><div class="control-card-head"><div><h2>' + conflicts.length +
            ' unresolved Patch conflict' + (conflicts.length === 1 ? '' : 's') + '</h2><p>' +
            (conflicts.length ? 'Conflicted definitions remain inactive until explicitly resolved.' :
                'No Patch conflict is blocking activation.') + '</p></div></div></article></section>';
    }

    function renderTrust() {
        const packages = controlSnapshot.packages || [];
        if (!packages.length) return '<p class="control-empty">No third-party Agent or App packages are installed.</p>';
        return '<section class="control-section"><p class="control-section-title">Installed source packages</p>' +
            packages.map((pkg) => {
                const trust = trustLabel(pkg);
                const manifest = pkg.manifest || {};
                const signature = pkg.verification?.signature || {};
                const audit = pkg.verification?.audit || {};
                const dependencies = manifest.services?.require || manifest.dependencies || [];
                const permissions = manifest.permissions || [];
                return '<article class="control-card"><div class="control-card-head"><div><h3>' +
                    escapeHtml(manifest.name || pkg.key) + '</h3><p>' + escapeHtml(pkg.kind + ' · ' + pkg.key +
                    ' · ' + pkg.version) + '</p></div><span class="control-pill ' + trust[1] + '">' + trust[0] +
                    '</span></div>' + metadataRows([
                        ['Publisher', pkg.publisher], ['Package status', pkg.status],
                        ['Signature trust', signature.trust || 'unknown'], ['Audit', audit.decision || 'review'],
                        ['Entry renderer', manifest.entry?.kind || '—'], ['Mini-Entry', manifest.mini_entry?.kind || '—'],
                        ['Permissions', Array.isArray(permissions) ? permissions.join(', ') || 'None declared' : JSON.stringify(permissions)],
                        ['Dependencies', Array.isArray(dependencies) ? dependencies.join(', ') || 'None declared' : JSON.stringify(dependencies)],
                    ]) + '<details><summary class="control-action">Audit evidence</summary><pre class="control-code">' +
                    escapeHtml(JSON.stringify(pkg.verification, null, 2)) + '</pre></details></article>';
            }).join('') + '</section>';
    }

    function renderPatches() {
        const patches = controlSnapshot.patches || [];
        if (!patches.length) return '<p class="control-empty">No local Agent or App patches are installed.</p>';
        return '<section class="control-section"><p class="control-section-title">Local Patch stack</p>' +
            patches.map((patch) => {
                const conflict = patch.conflict || {};
                const tone = patch.status === 'conflicted' ? 'danger' :
                    (patch.status === 'needs-review' ? 'warning' : '');
                const actions = patch.status === 'conflicted' ?
                    '<div class="control-actions">' +
                    '<button class="control-action primary" data-patch-resolution="preserve-local" data-patch-id="' + escapeHtml(patch.id) + '">Keep local change</button>' +
                    '<button class="control-action" data-patch-resolution="accept-upstream" data-patch-id="' + escapeHtml(patch.id) + '">Accept upstream</button>' +
                    '<button class="control-action danger" data-patch-resolution="disable" data-patch-id="' + escapeHtml(patch.id) + '">Disable Patch</button></div>' : '';
                return '<article class="control-card"><div class="control-card-head"><div><h3>' +
                    escapeHtml(patch.intent || patch.id) + '</h3><p>' + escapeHtml(patch.kind + ' · ' + patch.key +
                    ' · stack ' + patch.stack_order) + '</p></div><span class="control-pill ' + tone + '">' +
                    escapeHtml(patch.status) + '</span></div>' + metadataRows([
                        ['Conflict code', conflict.code || '—'], ['Target', conflict.target || '—'],
                        ['Policy', conflict.policy || '—'], ['Base digest', patch.base_digest],
                    ]) + (patch.conflict ? '<pre class="control-code">' + escapeHtml(JSON.stringify(patch.conflict, null, 2)) + '</pre>' : '') +
                    actions + '</article>';
            }).join('') + '</section>';
    }

    function renderApprovals() {
        if (!approvalSnapshot.length) {
            return '<p class="control-empty">No App or Agent is waiting for approval.</p>';
        }
        return '<section class="control-section"><p class="control-section-title">Waiting for your decision</p>' +
            approvalSnapshot.map((item) => {
                const riskTone = item.risk_level === 'critical' || item.risk_level === 'high'
                    ? 'danger' : item.risk_level === 'medium' ? 'warning' : '';
                const scopes = item.source_kind === 'agent_run'
                    ? [['once', 'Allow once'], ['session', 'Session'], ['agent', 'This Agent'], ['app', 'This App']]
                    : [['once', 'Allow once'], ['session', 'Session'], ['app', 'This App']];
                const allow = scopes.map((scope) =>
                    '<button class="control-action ' + (scope[0] === 'once' ? 'primary' : '') +
                    '" data-approval-id="' + escapeHtml(item.id) + '" data-approval-decision="approve" data-approval-scope="' +
                    scope[0] + '">' + scope[1] + '</button>'
                ).join('');
                return '<article class="control-card"><div class="control-card-head"><div><h3>' +
                    escapeHtml(item.title || 'Capability request') + '</h3><p>' +
                    escapeHtml(item.prompt || 'Capability access requested') +
                    '</p></div><span class="control-pill ' + riskTone + '">' +
                    escapeHtml((item.risk_level || 'low') + ' risk') + '</span></div>' +
                    metadataRows([
                        ['Source', item.source_kind === 'agent_run' ? 'AgentRun' : 'App Bridge'],
                        ['Capabilities', (item.capabilities || []).join(', ') || '—'],
                        ['Tool', item.tool_name || '*'],
                        ['Effects', (item.effects || []).join(', ') || 'read-only / unspecified'],
                        ['Resource', Object.keys(item.resource_selector || {}).length
                            ? JSON.stringify(item.resource_selector) : 'No resource selector'],
                        ['Deadline', item.deadline_at || '—'],
                    ]) + '<div class="control-actions">' + allow +
                    '<button class="control-action danger" data-approval-id="' + escapeHtml(item.id) +
                    '" data-approval-decision="deny" data-approval-scope="once">Deny</button></div></article>';
            }).join('') + '</section>';
    }

    function renderGrants() {
        if (!grantSnapshot.length) {
            return '<p class="control-empty">No active capability grants.</p>';
        }
        return '<section class="control-section"><p class="control-section-title">Active GrantLeases</p>' +
            grantSnapshot.map((grant) =>
                '<article class="control-card"><div class="control-card-head"><div><h3>' +
                escapeHtml((grant.capabilities || []).join(', ') || 'Capability grant') + '</h3><p>' +
                escapeHtml(grant.scope + ' · ' + grant.tool_pattern) +
                '</p></div><span class="control-pill">Active</span></div>' + metadataRows([
                    ['Scope identity', grant.scope_id],
                    ['AppInstance', grant.app_instance_id],
                    ['Session', grant.session_id],
                    ['Resource', Object.keys(grant.resource_selector || {}).length
                        ? JSON.stringify(grant.resource_selector) : 'All requested resources'],
                    ['Issued by', grant.issued_by],
                    ['Expires', grant.expires_at || 'Until revoked'],
                ]) + '<div class="control-actions"><button class="control-action danger" data-revoke-grant="' +
                escapeHtml(grant.id) + '">Revoke Grant</button></div></article>'
            ).join('') + '</section>';
    }

    function renderControl() {
        root.querySelectorAll('[data-control-tab]').forEach((button) =>
            button.classList.toggle('is-active', button.dataset.controlTab === controlTab));
        if (!controlSnapshot) {
            controlContent.innerHTML = '<div class="control-loading">Loading trusted system state…</div>';
            return;
        }
        controlContent.innerHTML = controlTab === 'approvals' ? renderApprovals() :
            controlTab === 'grants' ? renderGrants() :
            controlTab === 'trust' ? renderTrust() :
            controlTab === 'patches' ? renderPatches() : renderRecovery();
        refreshIcons();
    }

    async function refreshControl() {
        const snapshots = await Promise.all([
            request('/admin/api/shell/control'),
            request('/admin/api/shell/approvals'),
            request('/admin/api/shell/grant-leases'),
        ]);
        controlSnapshot = snapshots[0];
        approvalSnapshot = snapshots[1].items || [];
        grantSnapshot = snapshots[2].items || [];
        const conflicts = (controlSnapshot.patches || []).filter((patch) => patch.status === 'conflicted').length;
        const alerts = conflicts + approvalSnapshot.length;
        controlAlert.hidden = alerts === 0;
        controlAlert.textContent = alerts > 9 ? '9+' : String(alerts);
        renderControl();
    }

    async function openControl() {
        control.classList.add('is-open');
        control.setAttribute('aria-hidden', 'false');
        setDockVisible(true);
        renderControl();
        try { await refreshControl(); }
        catch (error) { controlContent.innerHTML = '<p class="control-empty">System state unavailable: ' + escapeHtml(error.message) + '</p>'; }
    }

    function framedUrl(url, token, instanceId) {
        const parsed = new URL(url, window.location.origin);
        const values = new URLSearchParams(parsed.hash.slice(1));
        values.set('ai2apps-mount', token);
        values.set('ai2apps-instance', instanceId);
        parsed.hash = values.toString();
        return parsed.pathname + parsed.search + parsed.hash;
    }

    function newMountToken() {
        return crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random();
    }

    function postFrameLifecycle(record, type) {
        if (!record?.frame.contentWindow) return;
        record.frame.contentWindow.postMessage({
            type,
            mountToken: record.mountToken,
            instanceId: record.instanceId,
            appId: record.appId,
        }, '*');
    }

    function broadcastAccountChanged() {
        framePool.forEach((record) => {
            if (!record?.frame.contentWindow) return;
            record.frame.contentWindow.postMessage({
                type: 'ai2apps.host.account-changed',
                mountToken: record.mountToken,
                instanceId: record.instanceId,
                appId: record.appId,
            }, '*');
        });
    }

    function accountBoundaryKey(result) {
        if (!result?.principal_actor_user_id) return null;
        return [
            result.principal_actor_user_id,
            result.principal_role || '',
            result.principal_membership_epoch || 0,
        ].join(':');
    }

    function installSpareFrame() {
        const blank = document.createElement('iframe');
        blank.className = 'app-frame';
        blank.allow = 'clipboard-read; clipboard-write';
        blank.referrerPolicy = 'same-origin';
        blank.hidden = true;
        appStage.insertBefore(blank, loading);
        frame = blank;
        spareFrame = blank;
    }

    async function rebuildForPrincipalChange() {
        const previousAppId = currentId;
        ++launchSequence;
        currentMountToken = null;
        currentInstanceId = null;
        appBadges.clear();
        closeControl();
        framePool.forEach((record) => {
            record.frame.src = 'about:blank';
            record.frame.remove();
        });
        framePool.clear();
        if (spareFrame?.isConnected) spareFrame.remove();
        installSpareFrame();
        currentId = '';
        pinned = [];
        dockOrder = [];
        warmApps = [];
        showHome({ navigate: false });
        await loadCatalog({ quiet: true, fallback: false });
        const target = byId.has(previousAppId)
            ? previousAppId
            : (byId.has('ai2apps.general-chat') ? 'ai2apps.general-chat' : 'ai2apps.account');
        if (byId.has(target)) await launch(target, { navigate: true });
        else showHome({ navigate: true });
    }

    function synchronizeAccountBoundary() {
        principalBoundarySync = principalBoundarySync.then(async () => {
            const result = await refreshAccountStatus();
            const nextBoundary = accountBoundaryKey(result);
            if (!nextBoundary) return;
            if (principalBoundary === null) {
                principalBoundary = nextBoundary;
                return;
            }
            if (nextBoundary === principalBoundary) return;
            principalBoundary = nextBoundary;
            await rebuildForPrincipalChange();
        }).catch((error) => showToast('Unable to apply account access: ' + error.message));
        return principalBoundarySync;
    }

    function markFrameReady(record) {
        record.loaded = true;
        record.frame.classList.add('is-ready');
        if (record.instanceId === currentInstanceId) {
            loading.hidden = true;
            sendHostContext();
            postFrameLifecycle(record, 'ai2apps.host.activate');
        }
    }

    function attachFrame(frameElement, record) {
        frameElement.addEventListener('load', () => markFrameReady(record));
    }

    function watchFrameReadiness(record, remainingChecks = 100) {
        if (record.loaded || !record.frame.isConnected || remainingChecks <= 0) return;
        try {
            const frameLocation = record.frame.contentWindow?.location.href || 'about:blank';
            if (frameLocation !== 'about:blank' &&
                    record.frame.contentDocument?.readyState === 'complete') {
                markFrameReady(record);
                return;
            }
        } catch (_) { /* cross-origin frames must report readiness through load */ }
        window.setTimeout(() => watchFrameReadiness(record, remainingChecks - 1), 100);
    }

    function acquireFrame(record) {
        let frameElement = spareFrame;
        if (frameElement) {
            spareFrame = null;
        } else {
            frameElement = document.createElement('iframe');
            frameElement.className = 'app-frame';
            frameElement.referrerPolicy = 'same-origin';
            appStage.insertBefore(frameElement, loading);
        }
        frameElement.allow = record.appId === 'ai2apps.general-chat'
            ? 'clipboard-read; clipboard-write; microphone'
            : 'clipboard-read; clipboard-write';
        frameElement.hidden = true;
        attachFrame(frameElement, record);
        return frameElement;
    }

    function updateRoute(app, instanceId, options) {
        if (options && options.navigate === false) return;
        const route = app.instanceMode === 'multiple'
            ? '/apps/' + encodeURIComponent(app.id) + '/instances/' + encodeURIComponent(instanceId)
            : '/apps/' + encodeURIComponent(app.id);
        window.history.pushState({ appId: app.id, instanceId }, '', route);
    }

    function showHome(options) {
        ++launchSequence;
        const previous = framePool.get(currentInstanceId);
        if (previous) {
            previous.lastUsed = Date.now();
            previous.frame.hidden = true;
            previous.frame.setAttribute('aria-hidden', 'true');
            postFrameLifecycle(previous, 'ai2apps.host.background');
        }
        currentId = '';
        currentInstanceId = null;
        currentMountToken = null;
        home.hidden = false;
        currentName.textContent = tr('shell.home.name');
        closeButton.disabled = true;
        loading.hidden = true;
        renderDock();
        renderHomeApps();
        closeLauncher();
        closeDockContextMenu();
        if (!options || options.navigate !== false) {
            window.history.pushState({ home: true }, '', '/');
        }
    }

    function activateFrameRecord(app, record, options) {
        const previous = framePool.get(currentInstanceId);
        if (previous && previous.instanceId !== record.instanceId) {
            previous.lastUsed = Date.now();
            previous.frame.hidden = true;
            previous.frame.setAttribute('aria-hidden', 'true');
            postFrameLifecycle(previous, 'ai2apps.host.background');
        }
        currentId = app.id;
        currentInstanceId = record.instanceId;
        currentMountToken = record.mountToken;
        home.hidden = true;
        frame = record.frame;
        record.lastUsed = Date.now();
        frame.hidden = false;
        frame.removeAttribute('aria-hidden');
        currentName.textContent = app.name;
        closeButton.disabled = false;
        frame.title = app.name;
        loading.hidden = Boolean(record.loaded);
        // Firefox can restore a same-origin iframe before the refreshed outer shell
        // reattaches its load listener. Treat that already-complete document as ready.
        if (!record.loaded) {
            try {
                if (frame.contentDocument?.readyState === 'complete') markFrameReady(record);
            } catch (_) { /* cross-origin frames must report readiness through load */ }
        }
        if (record.loaded) {
            frame.classList.add('is-ready');
            sendHostContext();
            postFrameLifecycle(record, 'ai2apps.host.activate');
        }
        renderDock();
        closeLauncher();
        closeDockContextMenu();
        updateRoute(app, record.instanceId, options);
    }

    function evictFrameRecord(record) {
        if (!record || record.instanceId === currentInstanceId) return;
        postFrameLifecycle(record, 'ai2apps.host.before-evict');
        framePool.delete(record.instanceId);
        record.frame.src = 'about:blank';
        record.frame.remove();
        request('/admin/api/shell/app-instances/' + encodeURIComponent(record.instanceId) + '/suspend', {
            method: 'POST',
        }).catch(() => {});
    }

    function isFrameCacheExempt(record) {
        return persistentFrameApps.has(record.appId) ||
            pinned.includes(record.appId) ||
            warmApps.includes(record.appId);
    }

    function enforceFrameCacheLimit() {
        const pooledRecords = Array.from(framePool.values()).filter((record) => !isFrameCacheExempt(record));
        if (pooledRecords.length <= frameCacheLimit) return;
        const candidates = pooledRecords
            .filter((record) => record.instanceId !== currentInstanceId)
            .sort((left, right) => {
                const leftProtected = appBadges.has(left.appId);
                const rightProtected = appBadges.has(right.appId);
                if (leftProtected !== rightProtected) return leftProtected ? 1 : -1;
                return left.lastUsed - right.lastUsed;
            });
        let pooledCount = pooledRecords.length;
        while (pooledCount > frameCacheLimit && candidates.length) {
            evictFrameRecord(candidates.shift());
            pooledCount -= 1;
        }
    }

    function displayEntry(app, entry, options) {
        const cached = framePool.get(entry.instance_id);
        if (cached) {
            activateFrameRecord(app, cached, options);
            return;
        }
        const record = {
            appId: app.id,
            instanceId: entry.instance_id,
            mountToken: newMountToken(),
            frame: null,
            loaded: false,
            lastUsed: Date.now(),
            contentUrl: entry.content_url,
        };
        record.frame = acquireFrame(record);
        framePool.set(record.instanceId, record);
        if (entry.renderer === 'sandbox') {
            record.frame.setAttribute('sandbox', 'allow-scripts allow-forms allow-downloads');
        } else {
            record.frame.removeAttribute('sandbox');
        }
        record.frame.classList.remove('is-ready');
        record.frame.src = framedUrl(entry.content_url, record.mountToken, record.instanceId);
        activateFrameRecord(app, record, options);
        watchFrameReadiness(record);
        enforceFrameCacheLimit();
    }

    async function launch(appId, options) {
        if (homeAppsLocked && appId !== 'ai2apps.account') {
            showToast('Sign in to your Core account to open Apps');
            return;
        }
        const app = byId.get(appId);
        if (!app) {
            showToast('App is not installed');
            return;
        }
        const requestedInstanceId = options && options.instanceId;
        if (currentMountToken && frame.getAttribute('src') &&
                !(options && options.newInstance) && appId === currentId &&
                (!requestedInstanceId || requestedInstanceId === currentInstanceId)) {
            closeLauncher();
            closeDockContextMenu();
            setDockVisible(true);
            return;
        }
        const sequence = ++launchSequence;
        try {
            let instanceId = options && options.instanceId;
            if (!instanceId && !(options && options.newInstance) && app.instances.length) {
                instanceId = app.instances[0].id;
            }
            const cached = instanceId && framePool.get(instanceId);
            if (cached && !(options && options.newInstance)) {
                activateFrameRecord(app, cached, options);
                await request('/admin/api/shell/app-instances/' + encodeURIComponent(instanceId) + '/focus', {
                    method: 'POST',
                });
                loadCatalog({ quiet: true });
                return;
            }
            const entry = instanceId
                ? await request('/admin/api/shell/app-instances/' + encodeURIComponent(instanceId) + '/focus', { method: 'POST' })
                : await request('/admin/api/shell/apps/' + encodeURIComponent(appId) + '/launch', { method: 'POST' });
            if (sequence !== launchSequence) return;
            displayEntry(app, entry, options);
            await loadCatalog({ quiet: true });
        } catch (error) {
            if (sequence !== launchSequence) return;
            const staleInstanceId = options?.instanceId || app.instances[0]?.id;
            if (staleInstanceId && error.status === 404) {
                app.instances = app.instances.filter(
                    (instance) => instance.id !== staleInstanceId
                );
                const staleFrame = framePool.get(staleInstanceId);
                if (staleFrame) {
                    staleFrame.frame.src = 'about:blank';
                    staleFrame.frame.remove();
                    framePool.delete(staleInstanceId);
                }
                try {
                    const entry = await request(
                        '/admin/api/shell/apps/' + encodeURIComponent(appId) + '/launch',
                        { method: 'POST' },
                    );
                    if (sequence !== launchSequence) return;
                    displayEntry(app, entry, options);
                    await loadCatalog({ quiet: true });
                    return;
                } catch (retryError) {
                    error = retryError;
                }
            }
            loading.hidden = true;
            showToast('Unable to open ' + app.name + ': ' + error.message);
        }
    }

    async function createMiniMount(options) {
        const appId = String(options.appId || '');
        const app = byId.get(appId);
        if (!app) throw new Error('Mini-Entry App is not installed');
        let instanceId = options.targetInstanceId || app.instances[0]?.id;
        let entry;
        if (instanceId) {
            entry = await request('/admin/api/shell/app-instances/' + encodeURIComponent(instanceId) + '/focus', { method: 'POST' });
        } else {
            entry = await request('/admin/api/shell/apps/' + encodeURIComponent(appId) + '/launch', { method: 'POST' });
            instanceId = entry.instance_id;
        }
        const mount = await jsonRequest(
            '/admin/api/shell/app-instances/' + encodeURIComponent(instanceId) + '/mounts',
            'POST',
            {
                placement: options.placement === 'sidebar' ? 'sidebar' : 'inline',
                interaction_session_id: options.sessionId || null,
                context: {
                    message_id: options.messageId || null,
                    requested_by: options.requestedBy || currentInstanceId,
                },
            }
        );
        mount.mountToken = crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random();
        frame.contentWindow.postMessage({
            type: 'ai2apps.host.mini-entry-mounted',
            mountToken: currentMountToken,
            instanceId: currentInstanceId,
            mount: mount,
        }, '*');
        await loadCatalog({ quiet: true });
        return mount;
    }

    function hostContext() {
        const app = byId.get(currentId);
        const instance = app?.instances.find((item) => item.id === currentInstanceId);
        return {
            type: 'ai2apps.host.context',
            mountToken: currentMountToken,
            instanceId: currentInstanceId,
            appId: currentId,
            homeSessionId: instance?.home_session_id || null,
            theme: document.documentElement.dataset.theme || 'light',
            locale: document.documentElement.lang || 'en',
            visibility: document.visibilityState,
            dockMode: mode,
            safeArea: { top: mode === 'docked' ? 66 : 0, right: 0, bottom: 0, left: 0 },
        };
    }

    function sendHostContext() {
        if (frame.contentWindow && currentMountToken && currentInstanceId) {
            frame.contentWindow.postMessage(hostContext(), '*');
        }
    }

    function respondToFrame(message, ok, result, error) {
        if (!message.requestId) return;
        frame.contentWindow.postMessage({
            type: 'ai2apps.host.response',
            mountToken: currentMountToken,
            instanceId: currentInstanceId,
            requestId: message.requestId,
            ok: ok,
            result: result,
            error: error,
        }, '*');
    }

    function respondToBridgeTarget(target, ok, result, error) {
        if (!target || !target.requestId) return;
        target.source.postMessage({
            type: 'ai2apps.host.response',
            mountToken: target.mountToken,
            instanceId: target.instanceId,
            requestId: target.requestId,
            ok: ok,
            result: result,
            error: error,
        }, '*');
    }

    function settleCapabilityWaiter(approvalId, result) {
        const target = capabilityBridgeWaiters.get(approvalId);
        if (!target) return;
        capabilityBridgeWaiters.delete(approvalId);
        const requestResult = result.request || {};
        respondToBridgeTarget(target, true, {
            status: requestResult.status,
            requestId: requestResult.id || approvalId,
            scope: requestResult.decision_scope || null,
            grant: result.grant || null,
        });
    }

    async function closeCurrent() {
        if (!currentInstanceId) return;
        await closeApp(currentId, { force: false });
    }

    function closeDockContextMenu() {
        contextAppId = null;
        dockContextDismiss.hidden = true;
        dockContextMenu.hidden = true;
        dockContextMenu.classList.remove('is-open');
    }

    function hideDockTooltip() {
        clearTimeout(dockTooltipTimer);
        dockTooltipHost.hidden = true;
        dockTooltipHost.classList.remove('is-visible');
    }

    function showDockTooltip(button) {
        hideDockTooltip();
        dockTooltipTimer = setTimeout(() => {
            if (!button.isConnected) return;
            const bounds = button.getBoundingClientRect();
            dockTooltipHost.textContent = button.dataset.dockTooltip || '';
            dockTooltipHost.hidden = false;
            const width = dockTooltipHost.offsetWidth;
            dockTooltipHost.style.left = Math.max(
                8,
                Math.min(bounds.left + bounds.width / 2 - width / 2, window.innerWidth - width - 8)
            ) + 'px';
            dockTooltipHost.style.top = (bounds.bottom + 7) + 'px';
            requestAnimationFrame(() => dockTooltipHost.classList.add('is-visible'));
        }, 70);
    }

    function openDockContextMenu(appId, event) {
        const app = byId.get(appId);
        if (!app) return;
        contextAppId = appId;
        dockContextMenu.querySelector('[data-context-name]').textContent = app.name;
        const icon = dockContextMenu.querySelector('[data-context-icon]');
        icon.setAttribute('data-lucide', safeIcon(app.icon));
        dockContextMenu.querySelector('[data-context-pin-label]').textContent =
            pinned.includes(appId) ? 'Remove from Dock' : 'Keep in Dock';
        dockContextMenu.querySelector('[data-context-warm-label]').textContent =
            warmApps.includes(appId) ? 'Allow Eviction' : 'Keep Warm';
        dockContextMenu.querySelectorAll('[data-dock-menu-action="close"], [data-dock-menu-action="force-close"]')
            .forEach((button) => { button.disabled = app.instances.length === 0; });
        dockContextDismiss.hidden = false;
        dockContextMenu.hidden = false;
        dockContextMenu.classList.add('is-open');
        const width = 218;
        const height = app.instances.length ? 306 : 258;
        dockContextMenu.style.left = Math.max(8, Math.min(event.clientX, window.innerWidth - width - 8)) + 'px';
        dockContextMenu.style.top = Math.max(8, Math.min(event.clientY, window.innerHeight - height - 8)) + 'px';
        refreshIcons();
        dockContextMenu.querySelector('[data-dock-menu-action="switch"]').focus();
    }

    function reloadApp(appId) {
        const app = byId.get(appId);
        if (!app) return;
        const instanceId = appId === currentId ? currentInstanceId : app.instances[0]?.id;
        const record = instanceId && framePool.get(instanceId);
        if (!record) {
            launch(appId);
            return;
        }
        record.loaded = false;
        record.frame.classList.remove('is-ready');
        if (record.instanceId === currentInstanceId) loading.hidden = false;
        record.frame.src = framedUrl(record.contentUrl, record.mountToken, record.instanceId);
        showToast('Reloading ' + app.name);
    }

    async function closeApp(appId, options) {
        const app = byId.get(appId);
        if (!app || !app.instances.length) return;
        const force = Boolean(options && options.force);
        const closingCurrent = appId === currentId;
        const instanceIds = app.instances.map((instance) => instance.id);
        const records = instanceIds.map((instanceId) => framePool.get(instanceId)).filter(Boolean);
        if (!force) {
            records.forEach((record) => postFrameLifecycle(record, 'ai2apps.host.before-close'));
            await new Promise((resolve) => setTimeout(resolve, 160));
        }
        if (closingCurrent && force) {
            ++launchSequence;
            currentMountToken = null;
            currentInstanceId = null;
            loading.hidden = false;
        }
        if (force) records.forEach((record) => { record.frame.src = 'about:blank'; });
        try {
            await Promise.all(instanceIds.map((instanceId) => request(
                '/admin/api/shell/app-instances/' + encodeURIComponent(instanceId),
                { method: 'DELETE' }
            )));
            if (closingCurrent) {
                currentInstanceId = null;
                currentMountToken = null;
            }
            records.forEach((record) => {
                framePool.delete(record.instanceId);
                record.frame.src = 'about:blank';
                record.frame.remove();
            });
            await loadCatalog({ quiet: true });
            if (closingCurrent) {
                const next = pinned.find((id) => id !== appId && byId.has(id)) || 'ai2apps.dashboard';
                await launch(next);
            }
            showToast(force ? 'App force closed' : 'App closed');
        } catch (error) {
            showToast('Unable to close App: ' + error.message);
        }
    }

    root.addEventListener('click', (event) => {
        const dockMenuButton = event.target.closest('[data-dock-menu-action]');
        if (dockMenuButton) {
            const action = dockMenuButton.dataset.dockMenuAction;
            const appId = contextAppId;
            closeDockContextMenu();
            if (!appId) return;
            if (action === 'switch') launch(appId);
            if (action === 'pin') {
                pinned = pinned.includes(appId) ? pinned.filter((id) => id !== appId) : [...pinned, appId];
                persist();
                if (!pinned.includes(appId)) enforceFrameCacheLimit();
                renderDock();
                if (launcher.classList.contains('is-open')) renderLauncher();
                showToast(pinned.includes(appId) ? 'Pinned to Dock' : 'Removed from Dock');
            }
            if (action === 'warm') {
                warmApps = warmApps.includes(appId)
                    ? warmApps.filter((id) => id !== appId)
                    : [...warmApps, appId];
                persist();
                if (!warmApps.includes(appId)) enforceFrameCacheLimit();
                showToast(warmApps.includes(appId) ? 'App will stay warm' : 'App may be evicted');
            }
            if (action === 'reload') reloadApp(appId);
            if (action === 'close') closeApp(appId, { force: false });
            if (action === 'force-close') closeApp(appId, { force: true });
            return;
        }
        const pinButton = event.target.closest('[data-pin-id]');
        if (pinButton) {
            const appId = pinButton.dataset.pinId;
            pinned = pinned.includes(appId) ? pinned.filter((id) => id !== appId) : [...pinned, appId];
            persist();
            if (!pinned.includes(appId)) enforceFrameCacheLimit();
            renderDock();
            renderLauncher();
            showToast(pinned.includes(appId) ? 'Pinned to Dock' : 'Removed from Dock');
            return;
        }
        const newButton = event.target.closest('[data-new-app-id]');
        if (newButton) {
            launch(newButton.dataset.newAppId, { newInstance: true });
            return;
        }
        const actionButton = event.target.closest('[data-shell-action]');
        if (actionButton) {
            const action = actionButton.dataset.shellAction;
            if (action === 'home') showHome();
            if (action === 'launcher') launcher.classList.contains('is-open') ? closeLauncher() : openLauncher();
            if (action === 'account') launch('ai2apps.account');
            if (action === 'close-launcher') closeLauncher();
            if (action === 'control') control.classList.contains('is-open') ? closeControl() : openControl();
            if (action === 'close-control') closeControl();
            if (action === 'close-current') closeCurrent();
            if (action === 'toggle-mode') {
                mode = mode === 'docked' ? 'immersive' : 'docked';
                updateMode();
                showToast(mode === 'immersive' ? 'Immersive mode' : 'Dock always visible');
            }
            return;
        }
        const homeAppButton = event.target.closest('[data-home-app-id]');
        if (homeAppButton) {
            launch(homeAppButton.dataset.homeAppId);
            return;
        }
        const controlTabButton = event.target.closest('[data-control-tab]');
        if (controlTabButton) {
            controlTab = controlTabButton.dataset.controlTab;
            renderControl();
            return;
        }
        const approvalButton = event.target.closest('[data-approval-id]');
        if (approvalButton) {
            approvalButton.disabled = true;
            const approvalId = approvalButton.dataset.approvalId;
            jsonRequest('/admin/api/shell/approvals/' + encodeURIComponent(approvalId) + '/decide', 'POST', {
                decision: approvalButton.dataset.approvalDecision,
                scope: approvalButton.dataset.approvalScope || 'once',
            }).then(async (result) => {
                settleCapabilityWaiter(approvalId, result);
                await refreshControl();
                showToast(result.request?.status === 'approved'
                    ? 'Capability approved; work resumed' : 'Capability denied');
            }).catch((error) => {
                approvalButton.disabled = false;
                showToast('Approval failed: ' + error.message);
            });
            return;
        }
        const revokeButton = event.target.closest('[data-revoke-grant]');
        if (revokeButton) {
            revokeButton.disabled = true;
            jsonRequest('/admin/api/shell/grant-leases/' + encodeURIComponent(revokeButton.dataset.revokeGrant) + '/revoke', 'POST', {
                reason: 'user-revoked-from-system-control',
            }).then(async () => {
                await refreshControl();
                showToast('Capability grant revoked');
            }).catch((error) => {
                revokeButton.disabled = false;
                showToast('Grant revocation failed: ' + error.message);
            });
            return;
        }
        const safeButton = event.target.closest('[data-safe-mode]');
        if (safeButton) {
            const active = safeButton.dataset.safeMode === 'on';
            safeButton.disabled = true;
            jsonRequest('/admin/api/shell/safe-mode', 'POST', {
                active: active,
                reason: active ? 'user-request-from-system-control' : 'user-restored-normal-mode',
            }).then(async (result) => {
                await refreshControl();
                await loadCatalog({ quiet: true });
                showToast(active
                    ? 'Safe Mode enabled · ' + (result.revoked_grants || 0) + ' grants revoked · ' +
                        (result.stopped_processes || 0) + ' processes stopped'
                    : 'Normal mode restored; revoked grants stay revoked');
            }).catch((error) => showToast('Safe Mode change failed: ' + error.message));
            return;
        }
        const patchButton = event.target.closest('[data-patch-resolution]');
        if (patchButton) {
            patchButton.disabled = true;
            jsonRequest('/admin/api/shell/local-patches/' + encodeURIComponent(patchButton.dataset.patchId) + '/resolve', 'POST', {
                resolution: patchButton.dataset.patchResolution,
            }).then(async (result) => {
                await refreshControl();
                await loadCatalog({ quiet: true });
                showToast(result.activated
                    ? 'Patch resolved and package activated'
                    : 'Patch decision saved; resolve the remaining conflicts');
            }).catch((error) => showToast('Patch resolution failed: ' + error.message));
            return;
        }
        const appButton = event.target.closest('[data-app-id]');
        if (appButton) {
            if (suppressDockClick && appButton.closest('.dock-apps')) return;
            launch(appButton.dataset.appId, { instanceId: appButton.dataset.instanceId || null });
        }
        const categoryButton = event.target.closest('[data-category]');
        if (categoryButton) {
            activeCategory = categoryButton.dataset.category;
            renderCategories();
            renderLauncher();
        }
    });

    dockApps.addEventListener('contextmenu', (event) => {
        const item = event.target.closest('[data-dock-drag-id]');
        if (!item) return;
        event.preventDefault();
        hideDockTooltip();
        openDockContextMenu(item.dataset.dockDragId, event);
    });
    dockContextDismiss.addEventListener('pointerdown', (event) => {
        // Keep the dismiss layer mounted for the complete pointer gesture so the
        // click cannot be retargeted to the App iframe or another control below it.
        event.preventDefault();
        event.stopPropagation();
    });
    dockContextDismiss.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        closeDockContextMenu();
    });
    dockContextDismiss.addEventListener('contextmenu', (event) => {
        event.preventDefault();
        event.stopPropagation();
        closeDockContextMenu();
    });
    dockApps.addEventListener('pointerover', (event) => {
        const button = event.target.closest('[data-dock-tooltip]');
        if (button && !button.contains(event.relatedTarget)) showDockTooltip(button);
    });
    dockApps.addEventListener('pointerout', (event) => {
        const button = event.target.closest('[data-dock-tooltip]');
        if (button && !button.contains(event.relatedTarget)) hideDockTooltip();
    });
    dockApps.addEventListener('dragstart', (event) => {
        const item = event.target.closest('[data-dock-drag-id]');
        if (!item) return;
        dockDraggingId = item.dataset.dockDragId;
        suppressDockClick = true;
        item.classList.add('is-dragging');
        event.dataTransfer.effectAllowed = 'move';
        event.dataTransfer.setData('text/plain', dockDraggingId);
        hideDockTooltip();
        closeDockContextMenu();
    });
    dockApps.addEventListener('dragover', (event) => {
        const target = event.target.closest('[data-dock-drag-id]');
        if (!target || !dockDraggingId || target.dataset.dockDragId === dockDraggingId) return;
        event.preventDefault();
        event.dataTransfer.dropEffect = 'move';
        const bounds = target.getBoundingClientRect();
        target.classList.toggle('drop-after', event.clientX > bounds.left + bounds.width / 2);
        target.classList.toggle('drop-before', event.clientX <= bounds.left + bounds.width / 2);
    });
    dockApps.addEventListener('dragleave', (event) => {
        const target = event.target.closest('[data-dock-drag-id]');
        if (target) target.classList.remove('drop-before', 'drop-after');
    });
    dockApps.addEventListener('drop', (event) => {
        const target = event.target.closest('[data-dock-drag-id]');
        if (!target || !dockDraggingId) return;
        event.preventDefault();
        const targetId = target.dataset.dockDragId;
        const visibleIds = Array.from(dockApps.querySelectorAll('[data-dock-drag-id]'))
            .map((item) => item.dataset.dockDragId).filter((id) => id !== dockDraggingId);
        let index = visibleIds.indexOf(targetId);
        const bounds = target.getBoundingClientRect();
        if (event.clientX > bounds.left + bounds.width / 2) index += 1;
        visibleIds.splice(index, 0, dockDraggingId);
        dockOrder = [...visibleIds, ...dockOrder.filter((id) => !visibleIds.includes(id))];
        persist();
        renderDock();
        setTimeout(() => { suppressDockClick = false; }, 0);
    });
    dockApps.addEventListener('dragend', () => {
        dockDraggingId = null;
        dockApps.querySelectorAll('.is-dragging, .drop-before, .drop-after')
            .forEach((item) => item.classList.remove('is-dragging', 'drop-before', 'drop-after'));
        setTimeout(() => { suppressDockClick = false; }, 0);
    });
    document.addEventListener('pointerdown', (event) => {
        hideDockTooltip();
        if (!dockContextMenu.hidden && !event.target.closest('.dock-context-menu')) closeDockContextMenu();
    });

    search.addEventListener('input', renderLauncher);
    root.querySelector('.dock-hot-zone').addEventListener('pointerenter', () => setDockVisible(true));
    root.querySelector('.app-dock').addEventListener('pointerenter', () => setDockVisible(true));
    root.querySelector('.app-dock').addEventListener('pointerleave', () => setDockVisible(false));
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !dockContextMenu.hidden) closeDockContextMenu();
        else if (event.key === 'Escape' && launcher.classList.contains('is-open')) closeLauncher();
        else if (event.key === 'Escape' && control.classList.contains('is-open')) closeControl();
    });
    window.addEventListener('popstate', (event) => {
        const parts = window.location.pathname.split('/').filter(Boolean);
        if (!parts.length) {
            showHome({ navigate: false });
            return;
        }
        const appId = decodeURIComponent(parts[1] || 'ai2apps.dashboard');
        const instanceId = parts[2] === 'instances' ? decodeURIComponent(parts[3] || '') : null;
        launch((event.state && event.state.appId) || appId, {
            instanceId: (event.state && event.state.instanceId) || instanceId,
            navigate: false,
        });
    });
    window.addEventListener('message', async (event) => {
        if (event.source !== frame.contentWindow) return;
        const message = event.data || {};
        if (message.mountToken !== currentMountToken || message.instanceId !== currentInstanceId) return;
        if (event.origin !== window.location.origin && event.origin !== 'null') return;
        const bridgeTarget = {
            source: event.source,
            mountToken: message.mountToken,
            instanceId: message.instanceId,
            requestId: message.requestId,
        };
        try {
            if (message.type === 'ai2apps.shell.ready') {
                const activeRecord = framePool.get(currentInstanceId);
                if (activeRecord) markFrameReady(activeRecord);
                else sendHostContext();
            }
            else if (message.type === 'ai2apps.shell.request-dock') setDockVisible(true);
            else if (message.type === 'ai2apps.shell.set-title' && typeof message.title === 'string') {
                currentName.textContent = message.title.slice(0, 80);
                frame.title = message.title.slice(0, 80);
            } else if (message.type === 'ai2apps.shell.set-badge') {
                const value = message.badge;
                const badgeAppId = byId.has(message.targetAppId) ? message.targetAppId : currentId;
                appBadges.set(badgeAppId, typeof value === 'object' ? {
                    text: String(value.text || value.count || '').slice(0, 8),
                    tone: ['info', 'warning', 'danger'].includes(value.tone) ? value.tone : 'info',
                } : String(value == null ? '' : value).slice(0, 8));
                renderDock();
            } else if (message.type === 'ai2apps.account.changed') {
                broadcastAccountChanged();
                await synchronizeAccountBoundary();
            } else if (message.type === 'ai2apps.shell.open-launcher') openLauncher();
            else if (message.type === 'ai2apps.shell.navigate') {
                const parsed = new URL(String(message.path || ''), window.location.origin);
                const parts = parsed.pathname.split('/').filter(Boolean);
                const appId = parts[0] === 'apps' ? decodeURIComponent(parts[1] || '') : '';
                if (parsed.origin !== window.location.origin || appId !== currentId) throw new Error('Navigation escaped App scope');
                const instanceId = parts[2] === 'instances' ? decodeURIComponent(parts[3] || '') : null;
                await launch(appId, { instanceId: instanceId, navigate: true });
                respondToFrame(message, true, { appId: appId, instanceId: currentInstanceId });
            } else if (message.type === 'ai2apps.shell.open-entry') {
                const appId = String(message.appId || currentId);
                await launch(appId, { instanceId: message.targetInstanceId || null });
                respondToFrame(message, true, { appId: appId, instanceId: currentInstanceId });
            } else if (message.type === 'ai2apps.shell.mount-mini-entry') {
                const mount = await createMiniMount(message);
                respondToFrame(message, true, mount);
            } else if (message.type === 'ai2apps.shell.create-agent-run') {
                const subjectInstanceId = String(message.subjectInstanceId || currentInstanceId);
                const run = await jsonRequest('/admin/api/shell/app-instances/' + encodeURIComponent(subjectInstanceId) + '/agent-runs', 'POST', {
                    session_id: message.sessionId,
                    agent: message.agent || 'ai2apps.general-agent',
                    input: message.input || {},
                    idempotency_key: message.idempotencyKey || null,
                    priority: Number.isInteger(message.priority) ? message.priority : 0,
                });
                respondToFrame(message, true, run);
            } else if (message.type === 'ai2apps.shell.request-capability') {
                const subjectInstanceId = String(message.subjectInstanceId || currentInstanceId);
                const capabilities = Array.isArray(message.capabilities)
                    ? message.capabilities.map(String).filter(Boolean)
                    : [String(message.capability || '')].filter(Boolean);
                if (!capabilities.length) throw new Error('Capability name is required');
                const approval = await jsonRequest(
                    '/admin/api/shell/app-instances/' + encodeURIComponent(subjectInstanceId) + '/capability-requests',
                    'POST',
                    {
                        session_id: message.sessionId || null,
                        mount_id: message.mountId || null,
                        capabilities: capabilities,
                        tool_name: String(message.toolName || '*'),
                        effects: Array.isArray(message.effects) ? message.effects.map(String) : [],
                        resource_selector: message.resourceSelector || {},
                        reason: String(message.reason || ('Allow this App to use ' + capabilities.join(', ') + '?')),
                        timeout_seconds: Number.isInteger(message.timeoutSeconds) ? message.timeoutSeconds : 600,
                    }
                );
                capabilityBridgeWaiters.set(approval.id, bridgeTarget);
                controlTab = 'approvals';
                openControl();
                showToast('Capability approval required');
            } else if (message.type === 'ai2apps.shell.export-artifact') {
                respondToFrame(message, true, { status: 'requires-host-picker', artifactId: message.artifactId || null });
            } else if (message.type === 'ai2apps.shell.close') {
                if (message.mountId) {
                    await request('/admin/api/shell/app-mounts/' + encodeURIComponent(message.mountId), { method: 'DELETE' });
                    frame.contentWindow.postMessage({
                        type: 'ai2apps.host.mini-entry-unmounted', mountToken: currentMountToken,
                        instanceId: currentInstanceId, mountId: message.mountId,
                    }, '*');
                    respondToFrame(message, true, { status: 'unmounted' });
                } else {
                    respondToFrame(message, true, { status: 'closing' });
                    await closeCurrent();
                }
            }
        } catch (error) {
            respondToFrame(message, false, null, error.message || String(error));
            showToast(error.message || String(error));
        }
    });

    document.addEventListener('visibilitychange', () => {
        sendHostContext();
        if (document.visibilityState === 'visible') synchronizeAccountBoundary();
    });

    async function initialize() {
        // Apply the stored visual mode without overwriting Dock state before it is restored.
        applyDesktopDeviceLabel();
        await applyDesktopClientVersion();
        updateMode({ persist: false });
        await loadCatalog();
        if (currentId) await launch(currentId, { instanceId: currentInstanceId, navigate: false });
        else showHome({ navigate: false });
        refreshControl().catch(() => {});
        await synchronizeAccountBoundary();
        window.setInterval(synchronizeAccountBoundary, 60 * 1000);
    }

    initialize();
})();
