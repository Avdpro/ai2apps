/* Navigation hints only. No form values, credentials, URLs or business replay. */
(() => {
    'use strict';
    const key = 'ai2apps.mobile.position.v1';
    const identifier = value => typeof value === 'string' && /^[A-Za-z0-9._:-]{1,256}$/.test(value);
    window.ai2appsMobilePosition = function (ownerURL, storage = sessionStorage) {
        let scope;
        try {
            const url = new URL(ownerURL);
            if (url.origin !== 'https://coder.ai2apps.com' || !/^\/u\/[0-9a-f-]{36}$/.test(url.pathname) ||
                url.search !== '?entry=owner-home' || url.hash || url.username || url.password) return null;
            scope = location.origin + url.pathname;
        } catch (_) { return null; }
        function read() {
            try {
                const value = JSON.parse(storage.getItem(key));
                if (value?.scope !== scope || !Number.isFinite(value.at) || Date.now()-value.at > 86400000 ||
                    value.at > Date.now() || !identifier(value.app)) return null;
                return {app:value.app, mini:identifier(value.mini) ? value.mini : null};
            } catch (_) { return null; }
        }
        function save(state) {
            try {
                if (!identifier(state?.appId)) { storage.removeItem(key); return; }
                storage.setItem(key, JSON.stringify({scope, at:Date.now(), app:state.appId,
                    mini:identifier(state.browserMiniApp) ? state.browserMiniApp : null}));
            } catch (_) { /* Storage is optional; the live page still works. */ }
        }
        return {read, save, clear(){try {storage.removeItem(key);} catch (_) {}}};
    };
})();

/* Temporary navigation diagnostics: no task text, URLs, IDs or form values. */
(() => {
    'use strict';
    // Temporary diagnostics are off after the mobile navigation verification.
    const MOBILE_NAV_TRACE_ENABLED=false;
    if(!MOBILE_NAV_TRACE_ENABLED)return;
    const documentId=crypto.randomUUID();
    const navigation=performance.getEntriesByType('navigation')[0]?.type||'navigate';
    const started=performance.now(), pending=[];
    let timer, sent=0, sequence=0, lastMove=0;
    const surface=document.getElementById('mobile-todo')?'todo':'shell';
    let session;
    try { session=window.top.__mobileNavigationTraceSession ||= crypto.randomUUID(); }
    catch (_) { session=crypto.randomUUID(); }
    function sample(event,persisted=null) {
        if(sent+pending.length>=1000||performance.now()-started>1800000)return;
        const visible=id=>{const el=document.getElementById(id);return el?!el.hidden:null;};
        const shown=selector=>{const el=document.querySelector(selector);return el?!el.hidden:null;};
        pending.push({event,document_id:documentId,persisted,navigation,seq:++sequence,at:performance.timeOrigin+performance.now(),mono:performance.now(),
            list:visible('list-view')??shown('.mobile-todo-list-frame'),detail:visible('detail-view')??shown('.mobile-todo-detail-frame'),stage:shown('.mobile-stage'),loading:shown('.mobile-loading'),
            route:history.state?.todoDetail||history.state?.ai2appsMobileTodo?.view==='detail'?'detail':history.state?.ai2appsMobileTodo?.view==='list'||history.state?.appId==='ai2apps.todo'?'list':'other',
            visible:document.visibilityState==='visible'});
        if(!timer)timer=setTimeout(flush,250);
    }
    function flush(){
        clearTimeout(timer);timer=null;
        if(!pending.length)return;
        const events=pending.splice(0,40);sent+=events.length;
        fetch('/v1/mobile/todo/navigation-trace',{method:'POST',credentials:'same-origin',keepalive:true,
            headers:{'Content-Type':'application/json'},body:JSON.stringify({session,surface,events})}).catch(()=>{});
        if(pending.length)timer=setTimeout(flush,250);
    }
    for(const name of ['touchstart','touchend','touchcancel','popstate','pageshow','pagehide','hashchange']){
        window.addEventListener(name,event=>{
            sample(name,typeof event.persisted==='boolean'?event.persisted:null);
            if(name==='popstate'||name==='pageshow')requestAnimationFrame(()=>{sample('frame1');requestAnimationFrame(()=>sample('frame2'));});
            if(name==='pagehide')flush();
        },{capture:true,passive:true});
    }
    window.addEventListener('touchmove',()=>{if(performance.now()-lastMove>80){lastMove=performance.now();sample('touchmove');}},{passive:true});
    document.addEventListener('visibilitychange',()=>{sample('visibility');if(document.hidden)flush();});
    const observer=new MutationObserver(records=>{
        if(records.some(r=>r.target.matches?.('#list-view,#detail-view,.mobile-stage,.mobile-loading,.mobile-app-frame')))sample('view-change');
    });
    observer.observe(document.body,{subtree:true,attributes:true,attributeFilter:['hidden','style','class']});
    sample('ready');
    setTimeout(()=>observer.disconnect(),1800000);
})();

(function () {
    'use strict';

    const root = document.getElementById('ai2apps-mobile');
    if (!root) return;

    const agentHome = root.dataset?.agentHome === 'true';
    const homePath = agentHome ? '/mobile/home' : '/mobile';
    let agentConnected = false;
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

    let catalogReady = false;
    let bootError = "应用列表尚未加载完成，请稍候。";
    let apps = [];
    let appsById = new Map();
    let mounts = new Map();
    let frames = new Map();
    let activeAppId = null;
    let pendingAppNavigation = null;
    let toastTimer = null;
    let sequence = 0;
    const warmFrameLimit = 4;

    function escapeHtml(value) {
        return String(value == null ? '' : value).replace(/[&<>"']/g, (character) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        })[character]);
    }

    function icon(name) {
        let safe = /^[a-z0-9-]{1,48}$/.test(name || '') ? name : 'app-window';
        if (safe === 'gallery-stacked-horizontal') safe = 'images';
        const key = safe.replace(/(^|-)([a-z0-9])/g, (_, prefix, letter) => letter.toUpperCase());
        if (window.lucide?.icons && !window.lucide.icons[key]) safe = 'app-window';
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
        const parsed = await response.json().catch(() => null);
        const payload = parsed || {};
        if (!response.ok) {
            // FRP can report transport failures as HTML 404. Only a structured
            // Local response can prove that an App instance no longer exists.
            if (response.status === 404 && (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))) {
                const error = new Error('设备中转暂不可用，请稍后重试。');
                error.status = 502;
                error.relayStatus = response.status;
                throw error;
            }
            const detail = payload.detail || payload.error?.message;
            const error = new Error(typeof detail === 'string' ? detail : detail?.message || ('Request failed (HTTP ' + response.status + ')'));
            error.status = response.status;
            throw error;
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
            description: document.body.dataset.ownerHome && item.app_key === 'ai2apps.general-chat'
                ? (document.documentElement.lang.startsWith('zh')
                    ? '文字聊天，历史记录保留在你的 Mac。'
                    : 'Text chat, with history kept on your Mac.')
                : item.description || '',
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

        const quickStartIds = new Set([
            'ai2apps.general-chat', 'ai2apps.intelligence',
            ...apps.slice(0, 4).map((app) => app.id),
        ]);
        for (const id of ['ai2apps.imagine-studio', 'ai2apps.readaloud', 'ai2apps.video-studio']) {
            quickStartIds.add(id);
        }
        const quickStartApps = Array.from(quickStartIds)
            .map((id) => apps.find((app) => app.id === id)).filter(Boolean);
        quickStartApps.push(...apps.filter(app=>!quickStartIds.has(app.id)));
        homeApps.innerHTML = quickStartApps.map((app) => (
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
        root.classList.toggle('mobile-dock-hidden', frames.get(activeAppId)?.dockVisible === false);
        root.classList.toggle('mobile-topbar-hidden', frames.get(activeAppId)?.topbarVisible === false);
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

    function appHistoryDepth() {
        const state=history.state;
        if(!state?.appId)return 0;
        return 1+(state.browserMiniApp||state.todoDetail ? 1 : Math.max(0,Number(state.intelDepth)||0));
    }

    function routeViaHome(appId) {
        if(!pendingAppNavigation && !leaveTodoDetail())return;
        closeOverlays();
        if(pendingAppNavigation){pendingAppNavigation.appId=appId;return;}
        sequence+=1; // Ignore a focus/open response belonging to the departing App.
        pendingAppNavigation={appId};
        history.go(-appHistoryDepth());
    }

    function hideInlineChat(){
        const chat=root.querySelector('[data-mobile-inline-agent]');
        if(chat&&!chat.hidden){chat.hidden=true;window.dispatchEvent(new CustomEvent('ai2apps-mobile-chat-visible',{detail:false}));}
    }

    function showHome(push) {
        if(push!==false && (pendingAppNavigation || history.state?.appId)){
            routeViaHome(null);return;
        }
        hideInlineChat();
        hideTodoDetail();
        sequence += 1;
        activeAppId = null;
        title.textContent = 'Mobile';
        home.hidden = false;
        stage.hidden = true;
        errorView.hidden = true;
        frames.forEach((record) => {
            record.frame.hidden = true;
            if(record.browserDetail)record.browserDetail.frame.hidden=true;
            record.frame.contentWindow?.postMessage({ type: 'ai2apps.host.background', mountToken: record.token }, '*');
        });
        closeOverlays();
        renderDock();
    }

    const notificationParams = new URLSearchParams(location.hash.slice(1));
    const notificationChannel = notificationParams.get("intelligence-channel");
    const notificationID = notificationParams.get('notification-id');
    window.addEventListener('message',event=>{
        const message=event.data,record=frames.get(activeAppId);
        if(!notificationID || !record || event.source!==record.frame.contentWindow || message?.type!=='ai2apps.notification.result' || message.mountToken!==record.token || message.id!==notificationID || !['opened','failed'].includes(message.status))return;
        window.__ai2appsNotificationStatus={id:notificationID,status:message.status};
    });
    function framedUrl(url, token, mount) {
        const parsed = new URL(url, window.location.origin);
        const hash = new URLSearchParams(parsed.hash.slice(1));
        hash.set('ai2apps-mount', token);
        hash.set('ai2apps-instance', mount.app_instance_id);
        hash.set('ai2apps-view-mount', mount.id);
        hash.set('ai2apps-surface', 'mobile');
        if (mount.app_key === 'ai2apps.intelligence' && notificationChannel) {
            hash.set('intelligence-channel', notificationChannel);
            if(notificationParams.get('intelligence-article'))hash.set('intelligence-article',notificationParams.get('intelligence-article'));
        }
        if(notificationID && mount.app_key===notificationParams.get('app')){
            for(const key of ['notification-id','notification-route','notification-resource','notification-session','notification-run'])if(notificationParams.get(key))hash.set(key,notificationParams.get(key));
        }
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
            record.browserDetail?.frame.remove();
            record.frame.remove();
            frames.delete(appId);
        }
    }

    function displayMount(app, mount, push) {
        hideInlineChat();
        if (push !== false) history.pushState({ appId: app.id, mobileRoot: true }, '', homePath + '#app=' + encodeURIComponent(app.id));
        hideTodoDetail();
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
            if(record.browserDetail)record.browserDetail.frame.hidden=true;
            record.frame.contentWindow?.postMessage({ type: 'ai2apps.host.background', mountToken: record.token }, '*');
        });

        let record = frames.get(app.id);
        if (!record || record.failed || record.mountId !== mount.id) {
            if (record) {record.browserDetail?.frame.remove();record.frame.remove();}
            const frame = document.createElement('iframe');
            const token = crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random();
            frame.className = 'mobile-app-frame';
            if(mount.renderer==='sandbox')frame.setAttribute('sandbox','allow-scripts allow-forms allow-downloads');
            frame.title = app.name;
            frame.allow = 'clipboard-read; clipboard-write';
            frame.referrerPolicy = 'same-origin';
            frame.addEventListener('load', () => {
                let documentReady = false;
                try {
                    const doc = frame.contentDocument;
                    if (doc?.URL === 'about:blank') return;
                    documentReady = Boolean(doc?.body?.children.length && doc.contentType === 'text/html');
                } catch (_) { /* A blocked iframe may expose no same-origin document. */ }
                documentReady = documentReady || Boolean(record.ready);
                record.loaded = documentReady;
                record.failed = !documentReady;
                if (activeAppId === app.id && frames.get(app.id) === record) {
                    loading.hidden = true;
                    errorView.hidden = documentReady;
                    if (!documentReady) errorMessage.textContent = '应用页面未能加载。请返回 Home 后重新打开；若持续出现，请检查设备连接。';
                }
            });
            record = { frame, token, renderer: mount.renderer, loaded: false, mountId: mount.id, instanceId: mount.app_instance_id, lastUsed: Date.now() };
            frames.set(app.id, record);
            frame.src = framedUrl(mount.content_url, token, mount);
            frameHost.appendChild(frame);
        }
        loading.hidden = Boolean(record.loaded || record.failed);
        if (record.failed) { errorView.hidden = false; errorMessage.textContent = '应用页面未能加载。请返回 Home 后重新打开。'; }
        record.lastUsed = Date.now();
        record.frame.hidden = false;
        if(record.inlineMiniApp)record.frame.contentWindow.ai2appsRestoreStudioSurface?.('library');
        record.frame.contentWindow?.postMessage({ type: 'ai2apps.host.activate', mountToken: record.token }, '*');
        closeOverlays();
        renderDock();
        trimFrames();
    }

    async function openApp(appId, push) {
        if (!catalogReady) { showToast(bootError); return; }
        const app = appsById.get(appId);
        if (!app) return showToast('This App is not Mobile Ready');
        if(push!==false){
            if(pendingAppNavigation){pendingAppNavigation.appId=appId;closeOverlays();return;}
            // Includes retained Mini-App details and an App whose first request is pending.
            if(history.state?.appId===appId){closeOverlays();return;}
            if(history.state?.appId){routeViaHome(appId);return;}
        }
        const requestId = ++sequence;
        // Commit history while the previous screen is still intact. WebKit
        // snapshots it here; showing the spinner first poisons the back preview.
        if (push !== false) history.pushState({ appId: app.id, mobileRoot: true }, '', homePath + '#app=' + encodeURIComponent(app.id));
        if(agentHome&&(agentConnected||window.AI2AppsAgentConnection?.status().expectedAgent)&&appId==='ai2apps.general-chat'){
            hideTodoDetail();frames.forEach(record=>{record.frame.hidden=true;if(record.browserDetail)record.browserDetail.frame.hidden=true;});
            const chat=root.querySelector('[data-mobile-inline-agent]');
            if(!chat)throw Error('Chat Shell surface unavailable');
            activeAppId=appId;title.textContent=app.name;home.hidden=true;stage.hidden=false;loading.hidden=true;errorView.hidden=true;chat.hidden=false;
            closeOverlays();renderDock();savePosition();window.dispatchEvent(new CustomEvent('ai2apps-mobile-chat-visible',{detail:true}));return;
        }
        const cached = frames.get(appId), cachedMount = mounts.get(appId);
        const warm = cached?.loaded && !cached.failed && cachedMount && cached.mountId === cachedMount.id;
        if (warm) {
            // Rebuild this App's history branch without navigating its live document.
            // Explicit browser Back still consumes these entries one level at a time.
            if (push !== false && appId === 'ai2apps.intelligence') {
                for (let depth=1; depth <= (cached.intelDepth || 0); depth++) {
                    history.pushState({appId, mobileRoot:true, intelDepth:depth}, '', location.href);
                }
            }
            displayMount(app, cachedMount, false);
        } else {
            loading.hidden = false;
            stage.hidden = false;
            home.hidden = true;
            closeOverlays();
        }
        try {
            const existing = mounts.get(appId);
            let mount;
            try {
                mount = await request(
                    existing
                        ? '/v1/mobile/app-instances/' + encodeURIComponent(existing.app_instance_id) + '/focus'
                        : '/v1/mobile/apps/' + encodeURIComponent(appId) + '/open',
                    { method: 'POST' }
                );
            } catch (error) {
                // A retained Mobile tab can outlive its server-side App instance.
                // Recover once through the normal authorized App opening route.
                if (!existing || error.status !== 404 || requestId !== sequence) throw error;
                mounts.delete(appId);
                const stale = frames.get(appId);
                stale?.browserDetail?.frame.remove();
                stale?.frame.remove();
                frames.delete(appId);
                mount = await request('/v1/mobile/apps/' + encodeURIComponent(appId) + '/open', {method:'POST'});
            }
            if (requestId !== sequence) return;
            if (warm && mount.id === cached.mountId && frames.get(appId) === cached) {
                mounts.set(appId, Object.assign(mount, {lastUsed:Date.now()}));
                return;
            }
            displayMount(app, Object.assign(mount, { lastUsed: Date.now() }), false);
        } catch (error) {
            if (requestId !== sequence) return;
            // A failed replacement cannot fall back to a frame already removed.
            if (warm && frames.get(appId) === cached && (!error.status || error.status === 429 || error.status >= 500)) return;
            const denied = frames.get(appId);
            if (warm && denied) {denied.browserDetail?.frame.remove();denied.frame.remove();frames.delete(appId);}
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
            if (record) {record.browserDetail?.frame.remove();record.frame.remove();}
            frames.delete(appId);
            if(appId==='ai2apps.todo'){(todoDetail?.surface||todoDetail?.frame)?.remove();todoDetail=null;}
            if (activeAppId === appId) showHome();
            renderDock();
            renderSwitcher();
        } catch (error) {
            showToast(error.message);
        }
    }

    // Trusted AI Browser keeps its library document intact; Shell owns detail
    // history and the sibling frame so native swipe never restores inner pixels.
    function mobileMiniAppNavigation(appId,sender,token,instanceId,action,id){
        if(!['ai2apps.ai-browser','ai2apps.imagine-studio','ai2apps.video-studio','ai2apps.readaloud'].includes(appId))return false;
        const record=frames.get(appId);
        if(!record||record.renderer==='sandbox'||
           token!==record.token||instanceId!==record.instanceId||
           (sender!==record.frame.contentWindow&&sender!==record.browserDetail?.frame.contentWindow))return false;
        if(action==='available')return true;
        if(action==='ready'){
            if(sender!==record.browserDetail?.frame.contentWindow)return false;
            record.browserDetail.ready=true;
            if(activeAppId===appId&&!record.browserDetail.frame.hidden&&history.state?.browserMiniApp===record.browserDetail.id)loading.hidden=true;
            return true;
        }
        if(activeAppId!==appId)return false;
        if(action==='back'){
            if(!history.state?.browserMiniApp)return false;
            if(history.state?.browserMiniApp&&!record.browserBackPending){record.browserBackPending=true;history.back();}
            return true;
        }
        if(action==='adopt-drag'){
            if(!['ai2apps.imagine-studio','ai2apps.video-studio','ai2apps.readaloud'].includes(appId)||typeof id!=='string'||!id||id.length>256)return false;
            if(sender===record.browserDetail?.frame.contentWindow)return history.state?.browserMiniApp===record.browserDetail.id;
            if(sender!==record.frame.contentWindow||typeof sender.ai2appsRestoreStudioSurface!=='function')return false;
            if(history.state?.studioInline&&history.state?.browserMiniApp===id)return true;
            record.inlineMiniApp=id;
            history.pushState({...history.state,appId,browserMiniApp:id,studioInline:true},'',location.href);
            record.browserBackPending=false;
            return true;
        }
        if(action!=='open'||sender!==record.frame.contentWindow||typeof id!=='string'||!id||id.length>256)return false;
        if(!record.browserDetail||record.browserDetail.id!==id){
            record.browserDetail?.frame.remove();
            const url=new URL(record.frame.src,location.href);
            if(url.origin!==location.origin)return false;
            const hash=new URLSearchParams(url.hash.slice(1));hash.set('ai2apps-browser-detail',id);url.hash=hash.toString();
            const frame=document.createElement('iframe');frame.className='mobile-app-frame';frame.title=appId==='ai2apps.ai-browser'?'AI Browser':'Studio';frame.referrerPolicy='same-origin';frame.allow='clipboard-read; clipboard-write';frame.hidden=true;
            frame.src=url.href;record.browserDetail={id,frame,ready:false};frameHost.appendChild(frame);
        }
        if (history.state?.appId !== appId || history.state?.browserMiniApp !== id) {
            history.pushState({...history.state,appId,browserMiniApp:id,studioInline:false},'',location.href);
        }
        record.browserBackPending=false;
        record.frame.hidden=true;record.browserDetail.frame.hidden=false;
        loading.hidden=record.browserDetail.ready;errorView.hidden=true;
        return true;
    };

    window.ai2appsMobileBrowserNavigation=(...args)=>mobileMiniAppNavigation('ai2apps.ai-browser',...args);
    window.ai2appsMobileStudioNavigation=(sender,token,instanceId,action,id,appId='ai2apps.imagine-studio')=>mobileMiniAppNavigation(appId,sender,token,instanceId,action,id);

    // Todo-only two-frame navigation experiment. No extra App mount is created.
    let todoDetail=null;
    function cancelTodoSlide(detail){
        if(detail?.animation){const animation=detail.animation;detail.animation=null;animation.cancel();}
    }
    function switchTodoFrame(detail,show,animate=false){
        cancelTodoSlide(detail);
        const frame=detail.frame,list=detail.record.frame,surface=detail.surface||frame;
        if(detail.surface)detail.surface.hidden=false;
        const motion=animate&&typeof surface.animate==='function'&&!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
        if(!motion){frame.hidden=!show;surface.hidden=!show;list.hidden=show;return;}
        // Keep the ready list underneath throughout the transition.
        list.hidden=false;frame.hidden=false;
        const animation=surface.animate([
            {transform:show?'translateX(100%)':'translateX(0)'},
            {transform:show?'translateX(0)':'translateX(100%)'}
        ],{duration:show?240:360,easing:show?'cubic-bezier(.22,.61,.36,1)':'cubic-bezier(.4,0,.2,1)',fill:'both'});
        detail.animation=animation;
        animation.finished.then(()=>{
            if(detail.animation!==animation)return;
            frame.hidden=!show;surface.hidden=!show;list.hidden=show;detail.animation=null;animation.cancel();
        }).catch(()=>{});
    }
    function hideTodoDetail(){if(todoDetail){cancelTodoSlide(todoDetail);todoDetail.frame.hidden=true;if(todoDetail.surface)todoDetail.surface.hidden=true;todoDetail.buttonBack=false;}}
    function leaveTodoDetail(){
        if(!todoDetail||todoDetail.frame.hidden)return true;
        try{return todoDetail.frame.contentWindow.mobileTodoCanLeave?.()!==false;}catch(_){return true;}
    }
    function presentTodoShell(detail){
        detail.placeholder.hidden=false;
        switchTodoFrame(detail,true,true);
        if(!history.state?.todoDetail)history.pushState({appId:'ai2apps.todo',mobileRoot:true,todoDetail:true},'',location.href);
        loading.hidden=true;errorView.hidden=true;
    }
    function openTodoDetail(record,message){
        if(!todoDetail&&history.state?.todoDetail)history.replaceState({appId:'ai2apps.todo',mobileRoot:true},'',location.href);
        if(todoDetail&&!leaveTodoDetail())return;
        if(todoDetail?.record===record){
            if(message.warm)return;
            todoDetail.requested=true;
            presentTodoShell(todoDetail);
            if(todoDetail.ready){
                todoDetail.frame.contentWindow.postMessage({...message,type:'ai2apps.todo.initialize-detail',mountToken:todoDetail.token},location.origin);
            }else todoDetail.pending=message;
            return;
        }
        (todoDetail?.surface||todoDetail?.frame)?.remove();
        record.frame.classList.add('mobile-todo-list-frame');
        const frame=document.createElement('iframe');
        frame.className='mobile-app-frame mobile-todo-detail-frame';frame.hidden=true;
        frame.title='Todo detail';frame.referrerPolicy='same-origin';
        const token=crypto.randomUUID(),url=new URL(record.frame.src,location.href);
        url.searchParams.set('todo_shell_detail','1');
        url.searchParams.set('todo_task',message.taskId||'');
        url.searchParams.set('todo_parent',message.parentId||'');
        url.searchParams.set('todo_directory',message.directoryId||'');
        const hash=new URLSearchParams(url.hash.slice(1));hash.set('ai2apps-mount',token);url.hash=hash.toString();
        const surface=document.createElement('div');surface.className='mobile-app-frame mobile-todo-surface';surface.hidden=true;
        const placeholder=document.createElement('div');placeholder.className='mobile-todo-placeholder';
        const back=document.createElement('button');back.type='button';back.textContent='‹';back.setAttribute('aria-label',document.documentElement.lang.startsWith('zh')?'返回列表':'Back to list');
        back.onclick=()=>{if(!todoDetail?.buttonBack){todoDetail.buttonBack=true;history.back();}};
        const bars=document.createElement('div');bars.className='mobile-todo-skeleton';bars.setAttribute('aria-busy','true');
        placeholder.append(back,bars);surface.append(frame,placeholder);
        todoDetail={frame,surface,placeholder,token,record,ready:false,pending:message.warm?null:message,requested:!message.warm};
        frameHost.appendChild(surface);frame.src=url.href;
        if(!message.warm)presentTodoShell(todoDetail);
    }
    window.addEventListener('message',event=>{
        if(event.origin!==location.origin)return;
        const m=event.data||{},record=frames.get('ai2apps.todo');
        if(!record||activeAppId!=='ai2apps.todo')return;
        if(event.source===record.frame.contentWindow&&m.mountToken===record.token&&m.instanceId===record.instanceId&&m.type==='ai2apps.todo.open-detail'){
            if(record.renderer==='sandbox')return;
            openTodoDetail(record,m);return;
        }
        const detail=todoDetail;
        if(!detail||detail.record!==record||event.source!==detail.frame.contentWindow||m.mountToken!==detail.token||m.instanceId!==record.instanceId)return;
        if(m.type==='ai2apps.todo.detail-ready'){
            detail.ready=true;
            if(detail.pending){
                const pending=detail.pending;detail.pending=null;
                detail.frame.contentWindow.postMessage({...pending,type:'ai2apps.todo.initialize-detail',mountToken:detail.token},location.origin);return;
            }
            detail.placeholder.hidden=true;
        }else if(m.type==='ai2apps.todo.detail-back'){if(!detail.buttonBack){detail.buttonBack=true;history.back();}}
        else if(m.type==='ai2apps.todo.changed')record.frame.contentWindow.postMessage({type:'ai2apps.todo.refresh',mountToken:record.token},location.origin);
        else if(m.type==='ai2apps.todo.detail-error'){detail.placeholder.hidden=true;showToast(m.message||'Unable to open Todo detail');if(history.state?.todoDetail)history.back();}
    });

    function sendBridgeResponse(frame, message, ok, result, error) {
        frame.postMessage({
            type: 'ai2apps.host.response', mountToken: message.mountToken,
            requestId: message.requestId, ok, result, error,
        }, '*');
    }

    window.addEventListener('message', async (event) => {
        const record = Array.from(frames.values()).find((item) => item.frame.contentWindow === event.source || item.browserDetail?.frame.contentWindow === event.source);
        if (!record || (event.origin !== window.location.origin && event.origin !== 'null')) return;
        const message = event.data || {};
        if (message.mountToken !== record.token || message.instanceId !== record.instanceId) return;
        if(activeAppId==='ai2apps.intelligence'&&record===frames.get(activeAppId)&&record.renderer!=='sandbox'){
            if(message.type==='ai2apps.intelligence.push'){
                const depth=Number(message.depth),current=Number(history.state?.intelDepth)||0;
                if(Number.isInteger(depth)&&depth===current+1&&depth<=20){record.intelDepth=depth;history.pushState({...history.state,appId:activeAppId,intelDepth:depth},'',location.href);}
                return;
            }
            if(message.type==='ai2apps.intelligence.back'){
                if(history.state?.intelDepth>0&&!record.intelBackPending){record.intelBackPending=true;history.back();}
                return;
            }
        }
        if (message.type === 'ai2apps.shell.ready') {
            let context={surface:'mobile'};
            if(record.renderer==='sandbox'){
                try {context=await request('/v1/mobile/app-mounts/'+encodeURIComponent(record.mountId)+'/bridge',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({method:'context'})});}
                catch(error){record.failed=true;loading.hidden=true;errorView.hidden=false;errorMessage.textContent=error.message;return;}
                record.ready=true;record.loaded=true;record.failed=false;
                if(frames.get(activeAppId)===record){loading.hidden=true;errorView.hidden=true;}
            }
            event.source.postMessage({
                type: 'ai2apps.host.context', mountToken: record.token, browserTask:record.browserTaskIntent||null,
                instanceId: record.instanceId, viewMountId: record.mountId,
                context,
            }, '*');
        } else if (message.type === 'ai2apps.shell.open-launcher') {
            openOverlay('launcher');
        } else if (message.type === 'ai2apps.shell.open-browser-task') {
            try{
                if(!/^btask_[a-zA-Z0-9_-]{1,120}$/.test(message.taskId||''))throw Error('Invalid browser task');
                history.pushState({appId:'ai2apps.ai-browser',mobileRoot:true},'',homePath+'#app=ai2apps.ai-browser');
                await openApp('ai2apps.ai-browser',false);
                const target=frames.get('ai2apps.ai-browser');if(!target)throw Error('Browser App is unavailable');
                target.browserTaskIntent={id:message.taskId};
                target.frame.contentWindow.postMessage({type:'ai2apps.host.context',mountToken:target.token,instanceId:target.instanceId,browserTask:target.browserTaskIntent},location.origin);
                sendBridgeResponse(event.source,message,true,{taskId:message.taskId});
            }catch(error){sendBridgeResponse(event.source,message,false,null,{message:error.message});}
        } else if (message.type === 'ai2apps.shell.open-chat-context') {
            if(record.renderer==='sandbox'||frames.get(activeAppId)!==record)return;
            try{
                if(!window.AI2AppsMobileOpenChatContext)throw Error('Open an authorized Agent connection to continue in Chat');
                const threadId=await window.AI2AppsMobileOpenChatContext(message.chatSeed);
                history.pushState({appId:'ai2apps.general-chat',mobileRoot:true},'',homePath+'#app=ai2apps.general-chat');
                await openApp('ai2apps.general-chat',false);
                const inline=root.querySelector('[data-mobile-inline-agent]');
                if(!inline||inline.hidden)throw Error('Open an authorized Agent connection to continue in Chat');
                sendBridgeResponse(event.source,message,true,{threadId});
            }catch(error){sendBridgeResponse(event.source,message,false,null,{message:error.message});}
        } else if (message.type === 'ai2apps.shell.set-dock-visible' || message.type === 'ai2apps.shell.set-topbar-visible') {
            if (record.renderer === 'sandbox' || frames.get(activeAppId) !== record || typeof message.visible !== 'boolean') return;
            record[message.type === 'ai2apps.shell.set-dock-visible' ? 'dockVisible' : 'topbarVisible'] = message.visible;
            renderDock();
        } else if (message.type === 'ai2apps.shell.request-dock') {
            record.dockVisible = true;
            renderDock();
            closeOverlays();
        } else if (message.type === 'ai2apps.shell.set-title' && typeof message.title === 'string') {
            title.textContent = message.title.slice(0, 80);
        } else if (message.type === 'ai2apps.shell.close') {
            await closeApp(Array.from(frames.entries()).find(([,item])=>item===record)?.[0]);
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
    let position = null, positionReady = false;
    function savePosition() { if (positionReady) position?.save(history.state); }
    for (const method of ['pushState', 'replaceState']) {
        const original = history[method];
        history[method] = function (...args) {
            const result = Reflect.apply(original, this, args);
            savePosition(); return result;
        };
    }
    window.addEventListener('pagehide', savePosition);
    window.addEventListener("popstate", savePosition);
    document.addEventListener('visibilitychange', savePosition);
    document.querySelector('[data-owner-logout]')?.addEventListener('click', () => {
        position?.clear(); positionReady = false;
    });

    window.addEventListener('popstate', (event) => {
        if(pendingAppNavigation){
            const target=pendingAppNavigation.appId;pendingAppNavigation=null;
            // Normalize an older session whose preceding entry was another App.
            if(event.state?.appId)history.replaceState({appId:null,mobileRoot:true},'',homePath);
            showHome(false);
            if(target)openApp(target);
            return;
        }
        const appId = event.state?.appId || new URLSearchParams(location.hash.slice(1)).get('app');
        const browserRecord=frames.get(appId);
        if(['ai2apps.imagine-studio','ai2apps.video-studio','ai2apps.readaloud'].includes(appId)&&browserRecord?.inlineMiniApp&&
           (event.state?.studioInline||!event.state?.browserMiniApp)){
            if(activeAppId!==appId){
                const app=appsById.get(appId),mount=mounts.get(appId);
                if(!app||!mount)return;
                sequence+=1;displayMount(app,mount,false);
            }
            browserRecord.browserBackPending=false;
            if(browserRecord.browserDetail)browserRecord.browserDetail.frame.hidden=true;
            browserRecord.frame.hidden=false;
            browserRecord.frame.contentWindow.ai2appsRestoreStudioSurface?.(event.state?.studioInline?'create':'library');
            loading.hidden=true;errorView.hidden=true;return;
        }
        if(['ai2apps.ai-browser','ai2apps.imagine-studio','ai2apps.video-studio','ai2apps.readaloud'].includes(appId)&&browserRecord?.browserDetail){
            if(activeAppId!==appId){
                const app=appsById.get(appId),mount=mounts.get(appId);
                if(!app||!mount)return;
                sequence+=1;displayMount(app,mount,false);
            }
            browserRecord.browserBackPending=false;
            const showing=event.state?.browserMiniApp===browserRecord.browserDetail.id;
            browserRecord.browserDetail.frame.hidden=!showing;
            browserRecord.frame.hidden=showing;
            loading.hidden=!showing||browserRecord.browserDetail.ready;errorView.hidden=true;return;
        }
        const intelRecord=frames.get('ai2apps.intelligence');
        if(activeAppId==='ai2apps.intelligence'&&appId==='ai2apps.intelligence'&&intelRecord){
            const depth=Number(event.state?.intelDepth)||0;
            const animate=!!intelRecord.intelBackPending;
            intelRecord.intelBackPending=false;intelRecord.intelDepth=depth;
            intelRecord.frame.contentWindow.postMessage({type:'ai2apps.intelligence.history',depth,animate,mountToken:intelRecord.token},location.origin);
            loading.hidden=true;errorView.hidden=true;return;
        }
        if(todoDetail&&activeAppId==='ai2apps.todo'){
            if(!event.state?.todoDetail&&!leaveTodoDetail()){
                todoDetail.buttonBack=false;
                history.pushState({appId:'ai2apps.todo',mobileRoot:true,todoDetail:true},'',location.href);return;
            }
            if(appId==='ai2apps.todo'){
                const showing=!!event.state?.todoDetail;
                const animateBack=!showing&&!!todoDetail.buttonBack;
                todoDetail.buttonBack=false;
                switchTodoFrame(todoDetail,showing,animateBack);
                loading.hidden=true;errorView.hidden=true;
                return;
            }
            hideTodoDetail();
        }

        // An inner page history traversal must not hide/reactivate the current
        // iframe or start another asynchronous focus request.
        const record = frames.get(appId);
        if (appId && appId === activeAppId && !stage.hidden && record?.loaded && !record.failed && !record.frame.hidden) return;
        const mount = mounts.get(appId), app = appsById.get(appId);
        if (app && mount && record?.loaded && !record.failed) {
            // Restore the cached screen in this popstate turn. Refocusing over
            // the network would replace the completed swipe with a loading UI.
            sequence += 1;
            displayMount(app, mount, false);
        } else if (appId) openApp(appId, false); else showHome(false);
    });

    async function boot() {
        try {
            if (!agentHome && await window.AI2AppsAgentConnection?.restoreShellEntry?.()) return;
            if (agentHome) {
                await window.AI2AppsAgentConnection?.ready;
                const connectionState=window.AI2AppsAgentConnection?.status();
                agentConnected=Boolean(connectionState?.agent);
                if(connectionState?.handoffFailed)throw Error(connectionState.error);
            }
            const fragment = new URLSearchParams(location.hash.slice(1));
            const handoff = fragment.get('handoff');
            if (handoff) {
                const memberHandoff = location.pathname === '/mobile/member/complete';
                history.replaceState(null, '', location.pathname);
                await request(memberHandoff ? '/v1/mobile/member-session/exchange' : '/v1/mobile/session/exchange', {
                    method: 'POST',
                    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
                    body: JSON.stringify({ handoff: handoff }),
                });
                location.replace('/mobile');
                return;
            }
            if (location.pathname === '/mobile/member/complete' || location.pathname === '/mobile/complete') {
                throw new Error('授权交接已失效，请返回扫码后的账户页面，重新点击“进入我的应用”。');
            }
            const [catalog, restored, owner] = await Promise.all([
                request('/v1/mobile/apps'),
                request('/v1/mobile/mounts'),
                document.body.dataset.ownerHome === 'true' ? request('/v1/mobile/owner-home/status') : agentHome ? request('/v1/mobile/owner-home/status').catch(()=>null) : null,
            ]);
            apps = (catalog.items || []).map(normalizeApp);
            appsById = new Map(apps.map((app) => [app.id, app]));
            (restored.items || []).forEach((mount, index) => {
                if (appsById.has(mount.app_key)) mounts.set(mount.app_key, Object.assign(mount, { lastUsed: Date.now() - index }));
            });
            catalogReady = true;
            if(agentHome){
                const note=root.querySelector('[data-agent-pair-note]');const issue=window.AI2AppsAgentConnection?.status().error;note.textContent=agentConnected?'应用与 Agent 均已连接。':issue?'应用已连接；Agent 未连接：'+issue:'应用已连接。';
                root.querySelector('.mobile-connection').textContent=agentConnected?'Apps · Agent':'Apps';
                if(owner?.authorized){document.body.dataset.ownerHome='true';const script=document.createElement('script');script.src='/mobile/static/js/owner_session.js';document.body.append(script);}
            }
            renderCatalog('');
            renderDock();
            position = owner ? window.ai2appsMobilePosition?.(owner.ownerAuthorizationUrl) : null;
            const saved = agentHome ? null : position?.read();
            const explicitApp = new URLSearchParams(location.hash.slice(1)).get('app');
            const appId = explicitApp || saved?.app;
            const mini = saved && saved.app === appId && !notificationID ? saved.mini : null;
            if (appId && appsById.has(appId)) {
                // A WebKit process recovery may retain the existing back list.
                // Reuse that branch; fresh authorization builds Home → App anew.
                if (history.state?.mobileRoot && history.state?.appId === appId) {
                    await openApp(appId, false);
                } else {
                    history.replaceState({appId:null,mobileRoot:true},'', homePath);showHome(false);
                    await openApp(appId);
                }
                const record = frames.get(appId);
                if (mini && record && !record.failed) {
                    mobileMiniAppNavigation(appId, record.frame.contentWindow, record.token, record.instanceId, 'open', mini);
                }
            } else {history.replaceState({appId:null,mobileRoot:true},'', homePath);showHome(false);}
            positionReady = true; savePosition();
        } catch (error) {
            if (agentHome && agentConnected) {
                const restoreChat=new URLSearchParams(location.hash.slice(1)).get('app')==='ai2apps.general-chat';
                // Agent authorization does not grant Owner App APIs. Keep Home usable
                // when that independent connection is absent; never proxy these requests.
                history.replaceState({appId:null,mobileRoot:true}, '', homePath);
                showHome(false);
                apps=[normalizeApp({app_key:'ai2apps.general-chat',display_name:'聊天',description:'Agent 对话已就绪',entry_source:'builtin',navigation:{icon:'message-square',category:'Chat'}})];appsById=new Map(apps.map(app=>[app.id,app]));catalogReady=true;renderCatalog('');renderDock();
                const access=document.createElement('a');access.className='mobile-home-app';access.href='/mobile';const heading=document.createElement('strong');heading.textContent='连接其他 App';const detail=document.createElement('small');detail.textContent='完成普通应用授权后恢复 App 列表；现有 Agent 连接保留。';access.append(heading,detail);homeApps.append(access);launcherGrid.append(access.cloneNode(true));
                root.querySelector('.mobile-hero-status').textContent = 'Agent 连接已就绪';
                root.querySelector('.mobile-connection').textContent = 'Agent';
                refreshIcons();
                if(restoreChat){const route=new URLSearchParams(location.hash.slice(1));route.set('app','ai2apps.general-chat');history.replaceState({appId:'ai2apps.general-chat',mobileRoot:true},'',homePath+'#'+route);await openApp('ai2apps.general-chat',false);}
                return;
            }
            bootError = error.message;
            homeApps.innerHTML = '<p class="mobile-empty">' + escapeHtml(bootError) + '</p>';
            const connection = root.querySelector('.mobile-connection');
            connection.textContent = '未连接';
            root.querySelector('.mobile-hero-status').textContent = '未能完成连接，请重新进入';
            root.querySelector('.mobile-activity-card').hidden = true;
            const reauthorize = root.querySelector('.mobile-reauthorize');
            if (reauthorize) reauthorize.hidden = false;
        }
        refreshIcons();
    }

    window.addEventListener('ai2apps-agent-connection-ready',()=>boot());
    async function restoreForegroundEntry() {
        if (document.visibilityState === 'hidden') return;
        if (!agentHome) { await window.AI2AppsAgentConnection?.restoreShellEntry?.(); return; }
        if (!agentConnected) {
            await window.AI2AppsAgentConnection?.pairPage();
            await boot();
        }
    }
    document.addEventListener('visibilitychange',restoreForegroundEntry);
    window.addEventListener('pageshow',event=>{ if(event.persisted)void restoreForegroundEntry(); });
    boot();
})();
