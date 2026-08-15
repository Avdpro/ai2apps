(function () {
    'use strict';

    const root = document.getElementById('ai2apps-mobile');
    if (!root) return;

    const home = root.querySelector('.mobile-home');
    const stage = root.querySelector('.mobile-stage');
    const frameHost = root.querySelector('.mobile-frame-host');
    const loading = root.querySelector('.mobile-loading');
    const errorView = root.querySelector('.mobile-error');
    const errorMessage = root.querySelector('[data-mobile-error-message]');
    const title = root.querySelector('[data-mobile-title]');
    const homeApps = root.querySelector('[data-mobile-home-apps]');
    const launcherGrid = root.querySelector('[data-mobile-launcher-grid]');
    const launcherEmpty = root.querySelector('[data-mobile-launcher-empty]');
    const search = root.querySelector('[data-mobile-search]');
    const recentDock = root.querySelector('[data-mobile-dock-recents]');
    const switcherList = root.querySelector('[data-mobile-switcher-list]');
    const switcherEmpty = root.querySelector('[data-mobile-switcher-empty]');
    const toast = root.querySelector('.mobile-toast');

    let apps = [];
    let appsById = new Map();
    let mounts = new Map();
    let frames = new Map();
    let activeAppId = null;
    let toastTimer = null;
    let sequence = 0;
    const warmFrameLimit = 2;

    function escapeHtml(value) {
        return String(value == null ? '' : value).replace(/[&<>"']/g, (character) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        })[character]);
    }

    function icon(name) {
        const safe = /^[a-z0-9-]{1,48}$/.test(name || '') ? name : 'app-window';
        return '<i data-lucide="' + safe + '"></i>';
    }

    function appIcon(app) {
        return '<span class="mobile-app-icon">' + icon(app.navigation?.icon) + '</span>';
    }

    function refreshIcons() {
        if (window.lucide) window.lucide.createIcons();
    }

    async function request(url, options) {
        const response = await fetch(url, Object.assign({
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
        }, options || {}));
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = payload.detail;
            throw new Error(typeof detail === 'string' ? detail : detail?.message || 'Request failed');
        }
        return payload;
    }

    function showToast(message) {
        toast.textContent = message;
        toast.classList.add('is-visible');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 2200);
    }

    function normalizeApp(item) {
        return {
            id: item.app_key,
            name: item.display_name || item.app_key,
            description: item.description || '',
            navigation: item.navigation || { icon: 'app-window', category: 'Apps' },
            instances: Array.isArray(item.instances) ? item.instances : [],
            renderer: item.mobile_renderer,
            entrySource: item.entry_source,
        };
    }

    function renderCatalog(filter) {
        const needle = String(filter || '').trim().toLowerCase();
        const visible = apps.filter((app) => !needle || (app.name + ' ' + app.description).toLowerCase().includes(needle));
        launcherGrid.innerHTML = visible.map((app) => (
            '<button class="mobile-launcher-app" type="button" data-mobile-app="' + escapeHtml(app.id) + '">' +
            appIcon(app) + '<strong>' + escapeHtml(app.name) + '</strong><small>' +
            escapeHtml(app.entrySource.replace('_', ' ')) + '</small></button>'
        )).join('');
        launcherEmpty.hidden = visible.length > 0;

        homeApps.innerHTML = apps.slice(0, 4).map((app) => (
            '<button class="mobile-home-app" type="button" data-mobile-app="' + escapeHtml(app.id) + '">' +
            appIcon(app) + '<strong>' + escapeHtml(app.name) + '</strong><small>' +
            escapeHtml(app.description || app.navigation.category) + '</small></button>'
        )).join('');
        refreshIcons();
    }

    function dockCandidates() {
        return Array.from(mounts.values())
            .filter((mount) => mount.app_key !== 'ai2apps.general-chat')
            .sort((a, b) => (b.lastUsed || 0) - (a.lastUsed || 0))
            .slice(0, 2);
    }

    function renderDock() {
        recentDock.innerHTML = dockCandidates().map((mount) => {
            const app = appsById.get(mount.app_key);
            if (!app) return '';
            return '<button class="mobile-dock-item' + (activeAppId === app.id ? ' is-active' : '') +
                '" type="button" data-mobile-app="' + escapeHtml(app.id) + '" data-running="true"><span>' +
                icon(app.navigation.icon) + '</span><small>' + escapeHtml(app.name) + '</small></button>';
        }).join('');
        root.querySelectorAll('.mobile-dock-item').forEach((button) => {
            const appId = button.dataset.mobileApp;
            const action = button.dataset.mobileAction;
            button.classList.toggle('is-active', action === 'home' ? activeAppId === null : appId === activeAppId);
            if (appId) button.dataset.running = mounts.has(appId) ? 'true' : 'false';
        });
        refreshIcons();
    }

    function renderSwitcher() {
        const running = Array.from(mounts.values()).sort((a, b) => (b.lastUsed || 0) - (a.lastUsed || 0));
        switcherList.innerHTML = running.map((mount) => {
            const app = appsById.get(mount.app_key);
            if (!app) return '';
            return '<article class="mobile-switcher-card"><button type="button" data-mobile-app="' +
                escapeHtml(app.id) + '">' + appIcon(app) + '<span class="mobile-switcher-card-copy"><strong>' +
                escapeHtml(app.name) + '</strong><small>' + escapeHtml(mount.entry_source.replace('_', ' ')) +
                ' · running</small></span></button><button class="mobile-switcher-close" type="button" data-mobile-close="' +
                escapeHtml(app.id) + '" aria-label="Close ' + escapeHtml(app.name) + '">' + icon('x') + '</button></article>';
        }).join('');
        switcherEmpty.hidden = running.length > 0;
        refreshIcons();
    }

    function closeOverlays() {
        root.querySelectorAll('.mobile-overlay').forEach((overlay) => {
            overlay.classList.remove('is-open');
            overlay.setAttribute('aria-hidden', 'true');
        });
    }

    function openOverlay(name) {
        closeOverlays();
        if (name === 'switcher') renderSwitcher();
        const overlay = root.querySelector('[data-mobile-overlay="' + name + '"]');
        if (!overlay) return;
        overlay.classList.add('is-open');
        overlay.setAttribute('aria-hidden', 'false');
        if (name === 'launcher') setTimeout(() => search.focus(), 80);
    }

    function showHome(push) {
        sequence += 1;
        activeAppId = null;
        title.textContent = 'Mobile';
        home.hidden = false;
        stage.hidden = true;
        errorView.hidden = true;
        frames.forEach((record) => {
            record.frame.hidden = true;
            record.frame.contentWindow?.postMessage({ type: 'ai2apps.host.background', mountToken: record.token }, '*');
        });
        closeOverlays();
        renderDock();
        if (push !== false) history.pushState({ appId: null }, '', '/mobile');
    }

    function framedUrl(url, token, mount) {
        const parsed = new URL(url, window.location.origin);
        const hash = new URLSearchParams(parsed.hash.slice(1));
        hash.set('ai2apps-mount', token);
        hash.set('ai2apps-instance', mount.app_instance_id);
        hash.set('ai2apps-view-mount', mount.id);
        hash.set('ai2apps-surface', 'mobile');
        parsed.hash = hash.toString();
        return parsed.pathname + parsed.search + parsed.hash;
    }

    function trimFrames() {
        const removable = Array.from(frames.entries())
            .filter(([appId]) => appId !== activeAppId)
            .sort((a, b) => (a[1].lastUsed || 0) - (b[1].lastUsed || 0));
        while (frames.size > warmFrameLimit && removable.length) {
            const [appId, record] = removable.shift();
            record.frame.contentWindow?.postMessage({ type: 'ai2apps.host.before-evict', mountToken: record.token }, '*');
            record.frame.remove();
            frames.delete(appId);
        }
    }

    function displayMount(app, mount, push) {
        activeAppId = app.id;
        mount.lastUsed = Date.now();
        mounts.set(app.id, mount);
        title.textContent = app.name;
        home.hidden = true;
        stage.hidden = false;
        errorView.hidden = true;
        loading.hidden = false;
        frames.forEach((record) => {
            record.frame.hidden = true;
            record.frame.contentWindow?.postMessage({ type: 'ai2apps.host.background', mountToken: record.token }, '*');
        });

        let record = frames.get(app.id);
        if (!record || record.mountId !== mount.id) {
            if (record) record.frame.remove();
            const frame = document.createElement('iframe');
            const token = crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random();
            frame.className = 'mobile-app-frame';
            frame.title = app.name;
            frame.allow = 'clipboard-read; clipboard-write';
            frame.referrerPolicy = 'same-origin';
            frame.addEventListener('load', () => { if (activeAppId === app.id) loading.hidden = true; });
            record = { frame, token, mountId: mount.id, instanceId: mount.app_instance_id, lastUsed: Date.now() };
            frames.set(app.id, record);
            frameHost.appendChild(frame);
            frame.src = framedUrl(mount.content_url, token, mount);
        }
        record.lastUsed = Date.now();
        record.frame.hidden = false;
        record.frame.contentWindow?.postMessage({ type: 'ai2apps.host.activate', mountToken: record.token }, '*');
        closeOverlays();
        renderDock();
        trimFrames();
        if (push !== false) history.pushState({ appId: app.id }, '', '/mobile#app=' + encodeURIComponent(app.id));
    }

    async function openApp(appId, push) {
        const app = appsById.get(appId);
        if (!app) return showToast('This App is not Mobile Ready');
        const requestId = ++sequence;
        loading.hidden = false;
        stage.hidden = false;
        home.hidden = true;
        closeOverlays();
        try {
            const existing = mounts.get(appId);
            const mount = await request(
                existing
                    ? '/v1/mobile/app-instances/' + encodeURIComponent(existing.app_instance_id) + '/focus'
                    : '/v1/mobile/apps/' + encodeURIComponent(appId) + '/open',
                { method: 'POST' }
            );
            if (requestId !== sequence) return;
            displayMount(app, Object.assign(mount, { lastUsed: Date.now() }), push);
        } catch (error) {
            if (requestId !== sequence) return;
            loading.hidden = true;
            errorView.hidden = false;
            errorMessage.textContent = error.message;
        }
    }

    async function closeApp(appId) {
        const mount = mounts.get(appId);
        if (!mount) return;
        try {
            await request('/v1/mobile/mounts/' + encodeURIComponent(mount.id), { method: 'DELETE' });
            mounts.delete(appId);
            const record = frames.get(appId);
            if (record) record.frame.remove();
            frames.delete(appId);
            if (activeAppId === appId) showHome();
            renderDock();
            renderSwitcher();
        } catch (error) {
            showToast(error.message);
        }
    }

    function sendBridgeResponse(frame, message, ok, result, error) {
        frame.postMessage({
            type: 'ai2apps.host.response', mountToken: message.mountToken,
            requestId: message.requestId, ok, result, error,
        }, '*');
    }

    window.addEventListener('message', async (event) => {
        const record = Array.from(frames.values()).find((item) => item.frame.contentWindow === event.source);
        if (!record || (event.origin !== window.location.origin && event.origin !== 'null')) return;
        const message = event.data || {};
        if (message.mountToken !== record.token || message.instanceId !== record.instanceId) return;
        if (message.type === 'ai2apps.shell.ready') {
            event.source.postMessage({
                type: 'ai2apps.host.context', mountToken: record.token,
                instanceId: record.instanceId, viewMountId: record.mountId,
                context: { surface: 'mobile' },
            }, '*');
        } else if (message.type === 'ai2apps.shell.open-launcher') {
            openOverlay('launcher');
        } else if (message.type === 'ai2apps.shell.request-dock') {
            closeOverlays();
        } else if (message.type === 'ai2apps.shell.set-title' && typeof message.title === 'string') {
            title.textContent = message.title.slice(0, 80);
        } else if (message.type === 'ai2apps.shell.close') {
            await closeApp(activeAppId);
            sendBridgeResponse(event.source, message, true, { closed: true });
        } else if (message.requestId) {
            sendBridgeResponse(event.source, message, false, null, {
                code: 'mobile_bridge_denied', message: 'This operation is not available on Mobile yet.',
            });
        }
    });

    root.addEventListener('click', (event) => {
        const close = event.target.closest('[data-mobile-close]');
        if (close) { event.stopPropagation(); closeApp(close.dataset.mobileClose); return; }
        const appButton = event.target.closest('[data-mobile-app]');
        if (appButton) { openApp(appButton.dataset.mobileApp); return; }
        const actionButton = event.target.closest('[data-mobile-action]');
        if (!actionButton) return;
        const action = actionButton.dataset.mobileAction;
        if (action === 'home') showHome();
        else if (action === 'launcher') openOverlay('launcher');
        else if (action === 'switcher') openOverlay('switcher');
        else if (action === 'close-overlays') closeOverlays();
    });

    search.addEventListener('input', () => renderCatalog(search.value));
    window.addEventListener('popstate', (event) => {
        const appId = event.state?.appId || new URLSearchParams(location.hash.slice(1)).get('app');
        if (appId) openApp(appId, false); else showHome(false);
    });

    async function boot() {
        try {
            const fragment = new URLSearchParams(location.hash.slice(1));
            const handoff = fragment.get('handoff');
            if (handoff) {
                history.replaceState(null, '', '/mobile/complete');
                await request('/v1/mobile/session/exchange', {
                    method: 'POST',
                    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
                    body: JSON.stringify({ handoff: handoff }),
                });
                location.replace('/mobile');
                return;
            }
            const [catalog, restored] = await Promise.all([
                request('/v1/mobile/apps'),
                request('/v1/mobile/mounts'),
            ]);
            apps = (catalog.items || []).map(normalizeApp);
            appsById = new Map(apps.map((app) => [app.id, app]));
            (restored.items || []).forEach((mount, index) => {
                if (appsById.has(mount.app_key)) mounts.set(mount.app_key, Object.assign(mount, { lastUsed: Date.now() - index }));
            });
            renderCatalog('');
            renderDock();
            const appId = new URLSearchParams(location.hash.slice(1)).get('app');
            if (appId && appsById.has(appId)) openApp(appId, false);
            else showHome(false);
        } catch (error) {
            homeApps.innerHTML = '<p class="mobile-empty">Mobile Apps are unavailable: ' + escapeHtml(error.message) + '</p>';
        }
        refreshIcons();
    }

    boot();
})();
