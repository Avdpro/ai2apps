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
    let toastTimer = null;
    let sequence = 0;
    const warmFrameLimit = 2;

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
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
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

        const quickStartIds = new Set(apps.slice(0, 4).map((app) => app.id));
        for (const id of ['ai2apps.imagine-studio', 'ai2apps.readaloud', 'ai2apps.video-studio']) {
            quickStartIds.add(id);
        }
        const quickStartApps = Array.from(quickStartIds)
            .map((id) => apps.find((app) => app.id === id)).filter(Boolean);
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
        hideTodoDetail();
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
            record.frame.contentWindow?.postMessage({ type: 'ai2apps.host.background', mountToken: record.token }, '*');
        });

        let record = frames.get(app.id);
        if (!record || record.failed || record.mountId !== mount.id) {
            if (record) record.frame.remove();
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
            frameHost.appendChild(frame);
            frame.src = framedUrl(mount.content_url, token, mount);
        }
        loading.hidden = Boolean(record.loaded || record.failed);
        if (record.failed) { errorView.hidden = false; errorMessage.textContent = '应用页面未能加载。请返回 Home 后重新打开。'; }
        record.lastUsed = Date.now();
        record.frame.hidden = false;
        record.frame.contentWindow?.postMessage({ type: 'ai2apps.host.activate', mountToken: record.token }, '*');
        closeOverlays();
        renderDock();
        trimFrames();
        if (push !== false) history.pushState({ appId: app.id }, '', '/mobile#app=' + encodeURIComponent(app.id));
    }

    async function openApp(appId, push) {
        if (!catalogReady) { showToast(bootError); return; }
        const app = appsById.get(appId);
        if (!app) return showToast('This App is not Mobile Ready');
        const requestId = ++sequence;
        loading.hidden = false;
        stage.hidden = false;
        home.hidden = true;
        closeOverlays();
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
                stale?.frame.remove();
                frames.delete(appId);
                mount = await request('/v1/mobile/apps/' + encodeURIComponent(appId) + '/open', {method:'POST'});
            }
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
            if(appId==='ai2apps.todo'){(todoDetail?.surface||todoDetail?.frame)?.remove();todoDetail=null;}
            if (activeAppId === appId) showHome();
            renderDock();
            renderSwitcher();
        } catch (error) {
            showToast(error.message);
        }
    }

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
        if(!history.state?.todoDetail)history.pushState({appId:'ai2apps.todo',todoDetail:true},'',location.href);
        loading.hidden=true;errorView.hidden=true;
    }
    function openTodoDetail(record,message){
        if(!todoDetail&&history.state?.todoDetail)history.replaceState({appId:'ai2apps.todo'},'',location.href);
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
        todoDetail={frame,surface,placeholder,token,record,ready:false,requested:!message.warm};
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
        const record = Array.from(frames.values()).find((item) => item.frame.contentWindow === event.source);
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
                type: 'ai2apps.host.context', mountToken: record.token,
                instanceId: record.instanceId, viewMountId: record.mountId,
                context,
            }, '*');
        } else if (message.type === 'ai2apps.shell.open-launcher') {
            openOverlay('launcher');
        } else if (message.type === 'ai2apps.shell.request-dock') {
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
    window.addEventListener('popstate', (event) => {
        const appId = event.state?.appId || new URLSearchParams(location.hash.slice(1)).get('app');
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
                history.pushState({appId:'ai2apps.todo',todoDetail:true},'',location.href);return;
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
        if (appId) openApp(appId, false); else showHome(false);
    });

    async function boot() {
        try {
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
            const [catalog, restored] = await Promise.all([
                request('/v1/mobile/apps'),
                request('/v1/mobile/mounts'),
            ]);
            apps = (catalog.items || []).map(normalizeApp);
            appsById = new Map(apps.map((app) => [app.id, app]));
            (restored.items || []).forEach((mount, index) => {
                if (appsById.has(mount.app_key)) mounts.set(mount.app_key, Object.assign(mount, { lastUsed: Date.now() - index }));
            });
            catalogReady = true;
            renderCatalog('');
            renderDock();
            const appId = new URLSearchParams(location.hash.slice(1)).get('app');
            if (appId && appsById.has(appId)) openApp(appId, false);
            else showHome(false);
        } catch (error) {
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

    boot();
})();
