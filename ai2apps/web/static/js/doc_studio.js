(() => {
    'use strict';

    const $ = selector => document.querySelector(selector);
    const tr = (zh, en) => document.documentElement.lang.startsWith('zh') ? zh : en;
    const prefix = '/v1/platform/doc-studio';
    const appId = 'ai2apps.doc-studio';
    const miniAppId = 'ai2apps.doc-studio.write-article';
    const translationId = 'ai2apps.doc-studio.translate-document';
    const storage = key => 'ai2apps.doc-studio.' + key;
    const projectSelect = $('#ds-project');
    const importForm = $('#ds-import');
    const generateForm = $('#ds-generate');
    const editor = $('#ds-editor');
    const blocksRoot = $('#ds-blocks');
    const versionSelect = $('#ds-version');
    const running = task => ['queued', 'running', 'waiting_resource', 'waiting_user', 'cancelling'].includes(task.status);
    let projects = [], projectId = '', project = null, pack = null, readingPack = '', lastPack = '';
    let version = null, changeSequence = 0, versionSequence = 0, updating = false;
    let draftBlocks = [], initialLayout = '', savingDraft = false, importingImage = false;
    let importTask = sessionStorage.getItem(storage('import-task')) || '';
    let latestImport = null, lastMaterialSnapshot = '';
    const requestKeys = new Map();

    function showError(error) {
        if (workspace === translationId) {
            translator.error(error);
            return;
        }
        const node = $('#ds-error');
        node.textContent = error?.message || '';
        node.hidden = !error;
    }
    async function api(path, body, method = body === undefined ? 'GET' : 'POST') {
        const response = await fetch(prefix + path, {
            method, credentials: 'same-origin', cache: 'no-store',
            ...(body === undefined ? {} : {
                ...(body instanceof FormData ? {body} : {
                    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
                }),
            }),
        });
        if (response.status === 204) return;
        const data = await response.json();
        if (!response.ok) {
            const detail = Array.isArray(data.detail) ? data.detail.map(item => item.msg).join('\n') : data.detail;
            const error = new Error(typeof detail === 'string' ? detail : tr('请求失败', 'Request failed'));
            error.status = response.status;
            throw error;
        }
        return data;
    }
    async function submit(path, fields) {
        const signature = JSON.stringify([path, fields]);
        const key = requestKeys.get(signature) || crypto.randomUUID();
        requestKeys.set(signature, key);
        try {
            const value = await api(path, {...fields, request_id: key});
            requestKeys.delete(signature);
            return value;
        } catch (error) {
            if (error.status && error.status < 500) requestKeys.delete(signature);
            throw error;
        }
    }
    const formatLabel = target => ({'image/png': 'PNG', 'application/zip': 'ZIP',
        'translation-txt': 'TXT', 'translation-md': 'Markdown',
        'translation-docx': 'DOCX', 'translation-pdf': 'PDF'})[target]
        || [...generateForm.elements.target.options].find(option => option.value === target)?.textContent || target;
    const output = window.AI2AppsStudioDocumentOutput($('[data-studio-output]'), {
        tr, formatLabel, busy: running, error: showError,
        taskNames: {
            'doc_studio.import': ['导入素材', 'Import materials'],
            'doc_studio.generate': ['生成稿件', 'Generate draft'],
            'doc_studio.export': ['渲染产物', 'Render output'],
            'doc_studio.rewrite_block': ['改写段落', 'Rewrite passage'],
            'doc_studio.translate': ['翻译文档', 'Translate document'],
        },
        cancel: async task => {
            await api('/tasks/' + task.id + '/cancel', {});
            await refresh();
        },
        canResume: task => task.kind === 'doc_studio.translate' && ['failed', 'interrupted'].includes(task.status),
        resume: async task => {
            await api('/translation/tasks/' + encodeURIComponent(task.id) + '/resume', {});
            await translator.refresh();
        },
    });
    const safe = callback => async event => {
        event?.preventDefault?.();
        showError(null);
        try { await callback(event); }
        catch (error) { showError(error); }
    };
    const layout = $('.ds-layout');
    const columns = [...document.querySelectorAll('[data-ds-column]')];
    const compact = window.matchMedia('(max-width: 1120px)');

    function setColumn(button, open) {
        layout.toggleAttribute('data-' + button.dataset.dsColumn + '-closed', !open);
        button.setAttribute('aria-expanded', String(open));
    }
    function resetColumns() {
        for (const button of columns) setColumn(button, !compact.matches);
    }
    for (const button of columns) {
        button.onclick = () => {
            const open = button.getAttribute('aria-expanded') === 'false';
            if (open && compact.matches) {
                for (const other of columns) if (other !== button) setColumn(other, false);
            }
            setColumn(button, open);
        };
    }
    resetColumns();
    compact.addEventListener('change', resetColumns);

    const tabs = [...$('.vs-sidebar-switch').querySelectorAll('[role="tab"]')];
    const galleryFrame = $('#ds-gallery-frame');
    const galleryStatus = $('#ds-gallery-status');
    const galleryRetry = $('#ds-gallery-retry');
    let mountingGallery = false;

    async function mountGallery() {
        if (mountingGallery || galleryFrame.hasAttribute('src')) return;
        mountingGallery = true;
        galleryStatus.hidden = false;
        galleryStatus.textContent = tr('正在载入素材库…', 'Loading Gallery…');
        galleryRetry.hidden = true;
        const fallback = '/admin/app-content/ai2apps.gallery?surface=mini';
        try {
            const bridge = window.ai2appsShell;
            let url = fallback;
            if (bridge?.mountMiniEntry) {
                const mount = await bridge.mountMiniEntry({
                    appId: 'ai2apps.gallery', placement: 'sidebar', requestedBy: 'ai2apps.doc-studio',
                });
                if (!mount?.content_url) throw new Error(tr('无法打开素材库。', 'Gallery could not be opened.'));
                url = mount.content_url;
            }
            galleryFrame.src = url;
        } catch (error) {
            if (/AI2Apps Host did not respond|Unsupported host mount/i.test(error.message)) {
                galleryFrame.src = fallback;
            } else {
                galleryStatus.textContent = error.message;
                galleryRetry.hidden = false;
            }
        } finally {
            mountingGallery = false;
            galleryFrame.hidden = !galleryFrame.hasAttribute('src');
            if (!galleryFrame.hidden) galleryStatus.hidden = true;
        }
    }
    let activeSidebar = tabs[0].id;
    function selectSidebar(tab) {
        if (tab.disabled) return;
        activeSidebar = tab.id;
        for (const item of tabs) {
            const active = item === tab;
            item.classList.toggle('active', active);
            item.setAttribute('aria-selected', String(active));
            item.tabIndex = active ? 0 : -1;
            document.getElementById(item.getAttribute('aria-controls')).hidden = !active;
        }
        if (tab.id === 'ds-gallery-tab') void mountGallery();
        if (tab.id === 'ds-chat-tab') void mountChat();
    }
    for (const tab of tabs) {
        tab.onclick = () => selectSidebar(tab);
        tab.onkeydown = event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
            event.preventDefault();
            const step = event.key === 'ArrowLeft' ? -1 : 1;
            const next = event.key === 'Home' ? tabs[0] : event.key === 'End' ? tabs.at(-1) :
                tabs[(tabs.indexOf(tab) + step + tabs.length) % tabs.length];
            selectSidebar(next);
            next.focus();
        };
    }
    galleryRetry.onclick = mountGallery;
    $('#ds-open-gallery').onclick = async () => {
        try {
            if (window.ai2appsShell?.openEntry) {
                await window.ai2appsShell.openEntry({appId: 'ai2apps.gallery'});
            } else {
                window.open('/apps/ai2apps.gallery', '_blank', 'noopener');
            }
        } catch (error) {
            galleryStatus.textContent = error.message;
            galleryStatus.hidden = false;
        }
    };
    $('#ds-writer').onclick = () => {
        selectWorkspace();
    };

    const chatFrame = $('#ds-chat-frame');
    const chatStatus = $('#ds-chat-status');
    const chatRetry = $('#ds-chat-retry');
    const portable = ['style', 'target', 'language'];
    const cardsId = 'ai2apps.imagine.article-cards';
    const draftFields = [...portable, 'guidance', 'base_version_id'];
    let chat = null, chatOpening = false, chatEpoch = 0;

    function resetChat() {
        chatEpoch++;
        chatOpening = false;
        chat?.dispose();
        chat = null;
        chatFrame.hidden = true;
        chatFrame.removeAttribute('src');
        chatRetry.hidden = true;
        chatStatus.hidden = false;
        chatStatus.textContent = tr('请先选择一个文章工程。', 'Select an article project first.');
    }

    function generationFields(keys) {
        return Object.fromEntries(keys.map(key => [key, generateForm.elements[key].value]));
    }

    async function mountChat() {
        if (workspace === translationId || workspace === cardsId) return mountOtherChat(workspace);
        if (workspace !== miniAppId || chatOpening || chat || !project) return;
        const id = project.id;
        const epoch = chatEpoch;
        const current = () => project?.id === id && chatEpoch === epoch;
        chatOpening = true;
        chatStatus.hidden = false;
        chatFrame.title = tr('撰写文章 Mini-Chat', 'Write article Mini-Chat');
        chatStatus.textContent = tr('正在打开工程对话…', 'Opening project Chat…');
        chatRetry.hidden = true;
        const assertCurrent = () => {
            if (!current()) throw Error(tr('文章工程已切换。', 'The article project changed.'));
        };
        try {
            const controller = await window.AI2AppsAppChat.create({
                appId, registration: appId + '.chat', restoreLast: false,
                title: tr('撰写文章', 'Write article'),
                scope: () => ({mini_app_id: miniAppId, project_id: id}),
                readUI() {
                    assertCurrent();
                    return {
                        miniAppId, project: {id, title: project.title},
                        editable_fields: [...draftFields, ...(version && !dirty() ? ['title', 'content'] : [])],
                        draft: {...generationFields(draftFields), ...(version ? {
                            version_id: version.id,
                            title: editor.elements.title.value,
                            content_excerpt: draftText().slice(0, 4000),
                        } : {})},
                        versions: project.versions.slice(0, 15).map(({id, title, target}) => ({id, title, target})),
                        outputs: project.outputs.slice(0, 15).map(({id, name, target}) => ({id, name, target})),
                    };
                },
                async applyUI(args) {
                    assertCurrent();
                    if (args.action === 'select_output') {
                        if (!output.select(args.output_id)) throw Error('Output is no longer available');
                        if (compact.matches) setColumn(columns[0], false);
                        setColumn(columns[1], true);
                    } else if (args.action === 'update_draft') {
                        if (savingDraft) throw Error(tr('稿件正在保存，请稍后再试。', 'The draft is being saved. Try again shortly.'));
                        const changes = Object.entries(args.values).map(([key, value]) => {
                            if (key === 'content' && version && !dirty() && typeof value === 'string' &&
                                value.trim() && value.length <= (version.target === 'x-long-post' ? 26000 : 24000)) {
                                return () => replaceDraftText(value);
                            }
                            const field = draftFields.includes(key) ? generateForm.elements[key] :
                                version && !dirty() && key === 'title' ? editor.elements.title : null;
                            const next = key === 'base_version_id' && value === null ? '' : value;
                            if (!field || typeof next !== 'string' ||
                                (field.options && ![...field.options].some(option => option.value === next)) ||
                                (field.maxLength >= 0 && next.length > field.maxLength)) {
                                throw Error(tr('该字段不可修改，请先保存当前编辑或选择有效的值。', 'Field unavailable. Save the current edit or select a valid value.'));
                            }
                            return () => { field.value = next; };
                        });
                        for (const apply of changes) apply();
                    } else {
                        throw Error('Unsupported writing UI action');
                    }
                    return {applied: true, project_id: id};
                },
                onSettled: () => current() && refresh(),
                scopeNote: tr('仅操作当前文章工程。任务和产物在「预览与输出」中查看。', 'This Chat controls the selected article project. Track jobs and artifacts in Preview & Output.'),
            });
            if (!current()) { controller.dispose(); return; }
            chat = controller;
            chatFrame.src = controller.url();
            controller.bind(chatFrame);
            chatFrame.hidden = false;
            chatStatus.hidden = true;
        } catch (error) {
            if (current()) {
                chatStatus.textContent = error.message;
                chatRetry.hidden = false;
            }
        } finally {
            if (current()) chatOpening = false;
        }
    }
    resetChat();
    chatRetry.onclick = mountChat;
    window.addEventListener('pagehide', () => chat?.dispose(), {once: true});

    const instanceId = new URLSearchParams(location.hash.slice(1)).get('ai2apps-instance');
    const packageFrame = $('#ds-package-frame');
    const packageList = $('#ds-package-mini-apps');
    const miniAppList = $('#ds-mini-apps');
    const catalogError = $('#ds-package-list-error');
    const packageCardTemplate = $('#ds-package-mini-card');
    const packageStatus = $('#ds-package-status');
    let favorites = new Set();
    try {
        const saved = JSON.parse(localStorage.getItem(storage('mini-app-favorites')) || '[]');
        if (Array.isArray(saved)) favorites = new Set(saved);
    } catch (_) { /* Favorites remain usable when persistence is unavailable. */ }

    function updateMiniAppCard(card) {
        const active = card.dataset.miniApp === workspace;
        card.classList.toggle('active', active);
        const select = card.querySelector('.is-mini-select');
        if (active) select.setAttribute('aria-current', 'page');
        else select.removeAttribute('aria-current');
        const name = select.querySelector('strong').textContent;
        const favorite = card.querySelector('button.is-mini-favorite');
        favorite.setAttribute('aria-label', tr(`收藏 Mini-App · ${name}`, `Favorite Mini-App · ${name}`));
        favorite.setAttribute('aria-pressed', String(favorites.has(card.dataset.miniApp)));
    }

    miniAppList.addEventListener('click', event => {
        const favorite = event.target.closest('button.is-mini-favorite');
        if (!favorite) return;
        const card = favorite.closest('[data-mini-app]');
        const id = card.dataset.miniApp;
        if (favorites.has(id)) favorites.delete(id);
        else favorites.add(id);
        try { localStorage.setItem(storage('mini-app-favorites'), JSON.stringify([...favorites])); }
        catch (_) { /* The current page still reflects the change. */ }
        updateMiniAppCard(card);
    });
    let selectedPackage = '', mountedPackage = '', mountSequence = 0, packageOutputs = [];
    let mountedPackageRevision = '', pendingPackage = '', packageItems = [], packageSelection = 0;
    let workspace = miniAppId;
    const translator = window.AI2AppsDocStudioTranslation?.({
        api, tr, languages: generateForm.elements.language, setBusy, onUpdate: updateOutput,
    });
    let cardsState = null;
    let cardsLoaded = Promise.resolve();
    async function cardsRequest(action, values, revision) {
        await cardsLoaded;
        const frame = packageFrame.contentWindow;
        const src = packageFrame.src;
        if (workspace !== cardsId || mountedPackage !== cardsId || !frame) throw Error('Article Cards is not mounted');
        return new Promise((resolve, reject) => {
            const channel = new MessageChannel();
            const finish = (error, state) => {
                clearTimeout(timer);
                packageFrame.removeEventListener('load', changed);
                channel.port1.close();
                if (error) reject(error); else resolve(state);
            };
            const changed = () => finish(Error('Article Cards mount changed'));
            const timer = setTimeout(() => finish(Error('Article Cards did not respond')), 3500);
            packageFrame.addEventListener('load', changed, {once:true});
            channel.port1.onmessage = ({data}) => {
                if (workspace !== cardsId || frame !== packageFrame.contentWindow || src !== packageFrame.src) return changed();
                if (data?.error || !Number.isInteger(data?.state?.revision)) return finish(Error(data?.error || 'Invalid editor state'));
                cardsState = data.state;
                finish(null, cardsState);
            };
            frame.postMessage({type:'ai2apps:article-cards-state/v1', action, values, revision}, '*', [channel.port2]);
        });
    }

    async function mountOtherChat(id) {
        if (chatOpening || chat || (id === cardsId && mountedPackage !== cardsId)) return;
        const epoch = chatEpoch;
        const current = () => workspace === id && chatEpoch === epoch;
        chatOpening = true;
        chatRetry.hidden = true;
        chatStatus.textContent = tr('正在打开对话…', 'Opening Chat…');
        const translating = id === translationId;
        chatFrame.title = translating ? tr('翻译文档 Mini-Chat', 'Translate document Mini-Chat')
            : tr('文章卡片 Mini-Chat', 'Article Cards Mini-Chat');
        const check = () => { if (!current()) throw Error('Mini-App changed'); };
        try {
            const controller = await window.AI2AppsAppChat.create({
                appId, registration: appId + (translating ? '.translation-chat' : '.cards-chat'),
                restoreLast: false, title: $('#ds-workspace-title').textContent,
                scope: () => ({mini_app_id:id}),
                async readUI() {
                    check();
                    if (translating) return translator.readUI();
                    const {draft: {article, ...draft}, revision} = await cardsRequest('read');
                    return {...draft, revision, article_excerpt: article.slice(0, 6000)};
                },
                async applyUI(args) {
                    check();
                    if (args.action !== 'update_draft') throw Error('Unsupported editor action');
                    if (translating) translator.apply(args.values);
                    else {
                        const state = await cardsRequest('read');
                        check();
                        await cardsRequest('apply', args.values, state.revision);
                    }
                    return {applied:true};
                },
                onSettled: () => current() && (translating ? translator.refresh() : refreshPackageOutputs()),
                scopeNote: tr('此对话仅操作当前 Mini-App。', 'This Chat controls the current Mini-App.'),
            });
            if (!current()) { controller.dispose(); return; }
            chat = controller;
            chatFrame.src = controller.url();
            controller.bind(chatFrame);
            chatFrame.hidden = false;
            chatStatus.hidden = true;
        } catch (error) {
            if (current()) { chatStatus.textContent = error.message; chatRetry.hidden = false; }
        } finally {
            if (current()) chatOpening = false;
        }
    }

    function selectWorkspace(item) {
        packageSelection++;
        if (workspace !== (item?.id || miniAppId)) resetChat();
        workspace = item?.id || miniAppId;
        const translating = workspace === translationId;
        selectedPackage = translating ? '' : item?.id || '';
        const title = $('#ds-workspace-title');
        title.textContent = item?.name || tr('撰写文章', 'Write article');
        $('#ds-workspace').dataset.miniAppId = workspace;
        $('#ds-writer-body').hidden = workspace !== miniAppId;
        $('#ds-translation-body').hidden = !translating;
        $('#ds-package-body').hidden = !selectedPackage;
        miniAppList.querySelectorAll('[data-mini-app]').forEach(updateMiniAppCard);
        if (compact.matches) setColumn(columns[0], false);
        $('#ds-workspace').scrollTop = 0;
        title.focus({preventScroll: true});
        const chatTab = $('#ds-chat-tab');
        chatTab.disabled = ![miniAppId, translationId, cardsId].includes(workspace);
        if (chatTab.disabled && activeSidebar === chatTab.id) selectSidebar(tabs[0]);
        const shortcut = $('#ds-asc-bot');
        if (shortcut.onclick) shortcut.hidden = chatTab.disabled;
        if (!chatTab.disabled && activeSidebar === chatTab.id) void mountChat();
        updateOutput();
    }
    $('#ds-translator').onclick = () => {
        if (!translator) return;
        selectWorkspace({id: translationId, name: tr('翻译文档', 'Translate document')});
        void translator.open();
    };

    async function openPackage(item) {
        const sameWorkspace = workspace === item.id;
        if (!sameWorkspace) selectWorkspace(item);
        const revision = window.AI2AppsStudioPackages?.revision(item) || '';
        if ((mountedPackage === item.id && mountedPackageRevision === revision) || pendingPackage === item.id) return;
        const sequence = ++mountSequence;
        pendingPackage = item.id;
        if (sameWorkspace) resetChat();
        mountedPackage = '';
        cardsState = null;
        packageFrame.hidden = true;
        packageFrame.removeAttribute('src');
        packageStatus.hidden = false;
        packageStatus.textContent = tr('正在打开 Mini-App…', 'Opening Mini-App…');
        try {
            const mount = await window.AI2AppsStudioMiniApps.mount(appId, item.id);
            if (sequence !== mountSequence || workspace !== item.id) return;
            packageFrame.title = item.name;
            cardsLoaded = new Promise(resolve => {
                const timer = setTimeout(resolve, 3500);
                packageFrame.addEventListener('load', () => {
                    clearTimeout(timer);
                    resolve();
                    if (sequence === mountSequence && activeSidebar === 'ds-chat-tab') void mountChat();
                }, {once:true});
            });
            packageFrame.src = mount.content_url;
            packageFrame.hidden = false;
            packageStatus.hidden = true;
            mountedPackageRevision = window.AI2AppsStudioPackages?.revision(item, mount) || '';
            mountedPackage = item.id;
        } catch (error) {
            if (sequence === mountSequence) packageStatus.textContent = error.message;
        } finally {
            if (sequence === mountSequence) pendingPackage = '';
        }
    }

    let packageCatalogRequest;
    function refreshPackages() {
        if (!instanceId) return;
        packageCatalogRequest ??= loadPackages().finally(() => { packageCatalogRequest = null; });
        return packageCatalogRequest;
    }

    let packageReadiness = {};
    function showCatalogError(error, retry = false) {
        catalogError.querySelector('p').textContent = error.message;
        $('#ds-package-retry').hidden = !retry;
        catalogError.hidden = false;
    }

    async function loadPackages() {
        try {
            const sdk = window.AI2AppsStudioMiniApps;
            const [catalog, readiness] = await Promise.all([
                sdk.list(appId),
                sdk.readiness(appId).catch(() => packageReadiness),
            ]);
            packageReadiness = readiness;
            const items = catalog.items.filter(item => item.source === 'package' && item.entry?.kind === 'sandbox');
            if (selectedPackage && !items.some(item => item.id === selectedPackage)) {
                mountSequence++;
                pendingPackage = '';
                selectWorkspace();
            }
            if (mountedPackage && !items.some(item => item.id === mountedPackage)) {
                mountedPackage = '';
                packageFrame.removeAttribute('src');
            }
            packageItems = items;
            const signature = JSON.stringify(items.map(item => [
                item.id, item.name, item.description, item.icon, item.version, readiness[item.id],
            ]));
            if (packageList.dataset.signature !== signature) {
                packageList.replaceChildren(...items.map(item => {
                    const card = packageCardTemplate.content.firstElementChild.cloneNode(true);
                    card.dataset.miniApp = item.id;
                    card.querySelector('.vs-pipeline-icon i').dataset.lucide = item.icon || 'layers';
                    card.querySelector('strong').textContent = item.name;
                    card.querySelector('small').textContent = item.description || '';
                    card.querySelector('.ds-mini-version').textContent = item.version || '';
                    const ready = readiness[item.id] === true;
                    card.querySelector('.ds-mini-status').textContent = ready
                        ? tr('依赖已就绪', 'Dependencies ready') : tr('需要配置', 'Setup required');
                    card.querySelector('button.is-mini-favorite').hidden = !ready;
                    card.querySelector('.studio-mini-status').hidden = ready;
                    card.querySelector('.is-mini-select').onclick = () => void selectPackage(item.id);
                    updateMiniAppCard(card);
                    return card;
                }));
                packageList.dataset.signature = signature;
                window.lucide?.createIcons();
            }
            $('#ds-mini-app-count').textContent = String(items.length + 2);
            catalogError.hidden = true;
        } catch (error) {
            showCatalogError(error, true);
        }
    }

    async function selectPackage(id) {
        const sequence = ++packageSelection;
        await refreshPackages();
        const item = packageItems.find(candidate => candidate.id === id);
        if (sequence === packageSelection && item) await openPackage(item);
    }

    const stopPackageActivation = window.AI2AppsStudioPackages?.watchActivation(async () => {
        const id = selectedPackage;
        await refreshPackages();
        if (id && selectedPackage === id) {
            const item = packageItems.find(candidate => candidate.id === id);
            if (item) await openPackage(item);
        }
    });
    window.addEventListener('pagehide', () => stopPackageActivation?.(), {once: true});

    miniAppList.querySelectorAll('[data-mini-app]').forEach(updateMiniAppCard);
    $('#ds-package-retry').onclick = refreshPackages;
    miniAppList.addEventListener('studio-install-mini-apps', async () => {
        try {
            await window.AI2AppsStudioPackages.install(appId, refreshPackages);
        } catch (error) {
            showCatalogError(error);
        }
    });
    miniAppList.addEventListener('studio-customize-mini-app', async () => {
        try {
            await window.AI2AppsCapabilities.openMiniAppCustomization({placement: appId});
        } catch (error) {
            showCatalogError(error);
        }
    });
    window.addEventListener('focus', refreshPackages);
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) void refreshPackages();
    });

    let outputSequence = 0;
    async function refreshPackageOutputs() {
        if (!instanceId) return;
        const sequence = ++outputSequence;
        const response = await fetch(prefix + '/mini-app-outputs', {
            credentials: 'same-origin', cache: 'no-store', headers: {'X-AI2Apps-App-Instance': instanceId},
        });
        if (!response.ok) throw Error(tr('无法读取 Mini-App 产物。', 'Could not load Mini-App outputs.'));
        const result = await response.json();
        if (sequence !== outputSequence) return;
        packageOutputs = result.items || [];
        updateOutput();
    }
    window.addEventListener('ai2apps:studio-output', event => {
        if (event.detail?.studioId === appId) {
            void refreshPackageOutputs().catch(error => {
                packageStatus.textContent = error.message;
                packageStatus.hidden = false;
            });
        }
    });
    if (instanceId && window.AI2AppsAppState && window.AI2AppsAppShortcuts) {
        const state = window.AI2AppsAppState;
        const binding = state.register({
            target: {app_id: appId, mini_app_id: null, contract_version: 1},
            instanceId,
            revision: () => JSON.stringify([projectId, generationFields(portable)]),
            capture: () => generationFields(portable),
            validate(values) {
                for (const key of portable) {
                    if (![...generateForm.elements[key].options].some(option => option.value === values[key])) {
                        throw Error('Writing preset option is unavailable');
                    }
                }
            },
            apply(values) {
                for (const key of portable) generateForm.elements[key].value = values[key];
            },
        });
        const translationBinding = state.register({
            target:{app_id:appId, mini_app_id:translationId, contract_version:1}, instanceId,
            activate:async () => { selectWorkspace({id:translationId, name:tr('翻译文档', 'Translate document')}); await translator.open(); },
            capture:() => translator.settings(), revision:() => JSON.stringify(translator.readUI()),
            validate(values) {
                if (workspace !== translationId) throw Error('Open Translate document');
                translator.validate(values);
            },
            apply:values => translator.apply(values),
        });
        const cardsBinding = state.register({
            target:{app_id:appId, mini_app_id:cardsId, contract_version:1}, instanceId,
            activate:async () => {
                const item = (await window.AI2AppsStudioMiniApps.list(appId)).items.find(item => item.id === cardsId);
                if (!item) throw Error('Article Cards is unavailable');
                await openPackage(item);
                await cardsRequest('read');
            },
            capture:() => cardsState?.settings,
            revision:() => JSON.stringify([packageFrame.src, cardsState?.revision]),
            dirty:() => Boolean(cardsState?.draft?.article),
            validate() {
                if (workspace !== cardsId || !cardsState?.settings) throw Error('Choose a built-in Article Cards template');
            },
            apply:values => cardsRequest('apply', values, cardsState.revision),
        });
        const shortcut = $('#ds-asc-bot');
        shortcut.hidden = false;
        shortcut.onclick = safe(async () => {
            shortcut.disabled = true;
            try {
                if (workspace === cardsId) await cardsRequest('read');
                await window.AI2AppsAppShortcuts.capture(
                    workspace === cardsId ? cardsBinding : workspace === translationId ? translationBinding : binding);
            }
            finally { shortcut.disabled = false; }
        });
        window.addEventListener('pagehide', () => {
            for (const target of [binding, translationBinding, cardsBinding]) target.dispose();
        }, {once: true});
    }

    const projectPath = id => '/projects/' + encodeURIComponent(id);
    function options(select, items, label, selected) {
        select.replaceChildren(...(label ? [new Option(label, '')] : []),
            ...items.map(item => new Option(item.title, item.id)));
        if ([...select.options].some(option => option.value === selected)) select.value = selected;
    }
    function dirty() {
        return version && (editor.elements.title.value !== version.title || JSON.stringify(layoutPayload()) !== initialLayout);
    }
    function discard() {
        return !dirty() || window.confirm(tr('放弃尚未保存的稿件修改？', 'Discard unsaved draft edits?'));
    }
    function setBusy(form, value) {
        form.querySelector('button[type=submit]').disabled = value;
    }
    const galleryMime = 'application/x-ai2apps-gallery-asset';
    const materialMime = 'application/x-ai2apps-doc-studio-image';
    const isImageRow = block => block.type === 'image_row';
    const supportsLayout = draft => Array.isArray(draft?.blocks);
    const imageFields = ({asset_id, alt = ''}) => ({asset_id, alt: alt.slice(0, 1000)});
    function layoutPayload() {
        return draftBlocks.flatMap(block => {
            if (isImageRow(block)) return [{type: block.type, images: block.images.map(imageFields)}];
            return block.text.trim() ? [{type: block.type, text: block.text.trim()}] : [];
        });
    }
    function draftText() {
        return layoutPayload().filter(block => !isImageRow(block)).map(block => {
            if (block.type === 'list') return block.text.split('\n').map(item => '- ' + item).join('\n');
            return ({heading: '## ', quote: '> '}[block.type] || '') + block.text;
        }).join('\n\n');
    }
    function parseDraftText(value) {
        const incoming = [];
        for (const raw of value.split(/\r?\n/)) {
            const line = raw.trim();
            if (!line) continue;
            const bullet = line.match(/^(?:[-*]|\d+\.) +(.+)$/);
            const heading = line.match(/^#{1,3} +(.+)$/);
            if (bullet && incoming.at(-1)?.type === 'list') incoming.at(-1).text += '\n' + bullet[1];
            else if (bullet) incoming.push({type: 'list', text: bullet[1]});
            else if (heading) incoming.push({type: 'heading', text: heading[1]});
            else if (line.startsWith('> ')) incoming.push({type: 'quote', text: line.slice(2)});
            else incoming.push({type: 'paragraph', text: line});
        }
        return incoming;
    }
    function replaceDraftText(value) {
        const incoming = parseDraftText(value);
        const layout = [];
        for (const block of draftBlocks) {
            if (isImageRow(block)) layout.push(block);
            else if (incoming.length) layout.push(incoming.shift());
        }
        const lastText = layout.findLastIndex(block => !isImageRow(block));
        layout.splice(lastText + 1, 0, ...incoming);
        draftBlocks = layout;
        renderBlocks();
    }
    function blockButton(label, callback) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = label;
        button.onclick = callback;
        return button;
    }
    function removeBlock(block) {
        draftBlocks.splice(draftBlocks.indexOf(block), 1);
        renderBlocks();
    }
    function dropTarget(node, before, beside = null) {
        const canDrop = transfer => !savingDraft && !importingImage && supportsLayout(version) &&
            [materialMime, galleryMime].some(type => transfer?.types.includes(type));
        node.ondragover = event => {
            if (!canDrop(event.dataTransfer)) return;
            event.preventDefault();
            event.stopPropagation();
            event.dataTransfer.dropEffect = 'copy';
            node.classList.add('ds-drop-active');
        };
        node.ondragleave = event => {
            if (!(event.relatedTarget instanceof Node) || !node.contains(event.relatedTarget)) {
                node.classList.remove('ds-drop-active');
            }
        };
        node.ondrop = safe(async event => {
            node.classList.remove('ds-drop-active');
            const transfer = event.dataTransfer;
            if (!canDrop(transfer)) return;
            event.stopPropagation();
            const current = version, id = projectId;
            if (draftBlocks.reduce((count, block) => count + (block.images?.length || 0), 0) >= 20) {
                throw Error(tr('每版稿件最多插入 20 张图片。', 'A draft version supports up to 20 images.'));
            }
            const materialId = transfer.getData(materialMime);
            let image;
            if (materialId) {
                image = project.materials.flatMap(item => item.images).find(item => item.asset_id === materialId);
                if (!image) throw Error(tr('这张图片不属于当前工程。', 'This image is unavailable in the current project.'));
            } else {
                const kind = transfer.getData('application/x-ai2apps-gallery-kind');
                if (kind && kind !== 'image') throw Error(tr('请拖入 Gallery 图片。', 'Drag an image from Gallery.'));
                importingImage = true;
                try {
                    image = await api(projectPath(id) + '/images/gallery', {asset_id: transfer.getData(galleryMime)});
                } finally { importingImage = false; }
            }
            if (current !== version || id !== projectId || savingDraft) return;
            const position = before ? draftBlocks.indexOf(before) : draftBlocks.length;
            if (position < 0) return;
            if (beside) {
                const index = before.images.indexOf(beside);
                if (index < 0) return;
                before.images.splice(index + 1, 0, imageFields(image));
            } else {
                draftBlocks.splice(position, 0, {type: 'image_row', images: [imageFields(image)]});
            }
            renderBlocks();
        });
    }
    function rewriteDialog(block) {
        const current = version, id = projectId;
        window.AI2AppsTextInputDialog.open({
            title: tr('AI 改写选中的段落', 'Rewrite selected passage with AI'),
            label: tr('改写指令', 'Revision instructions'), value: '', maxLength: 2000,
            submitLabel: tr('生成改写', 'Generate revision'), cancelLabel: tr('取消', 'Cancel'),
            async onSubmit(instruction) {
                if (version !== current || !draftBlocks.includes(block) || savingDraft) {
                    throw Error(tr('当前段落已切换，请重新选择。', 'Select the passage again.'));
                }
                const original = block.text;
                block.rewrite = {original};
                renderRewrite(block);
                try {
                    const task = await submit(projectPath(id) + '/rewrite-block', {
                        version_id: current.id, block: {type: block.type, text: original}, instruction,
                    });
                    block.rewrite.task = task;
                    renderRewrite(block);
                    await refresh();
                } catch (error) {
                    if (!block.rewrite.task) block.rewrite = null;
                    renderRewrite(block);
                    throw error;
                }
            },
        });
    }
    function renderRewrite(block) {
        const {rewrite, rewritePanel, rewriteButton, input} = block;
        const task = rewrite?.task;
        const pending = rewrite && (!task || running(task));
        rewriteButton.disabled = Boolean(pending) || !block.text.trim();
        rewritePanel.replaceChildren();
        if (pending) rewritePanel.textContent = tr('正在改写这一段…', 'Rewriting this passage…');
        if (task?.status !== 'completed' || !task.result?.text) return;
        const preview = document.createElement('p');
        preview.textContent = task.result.text;
        const apply = blockButton(tr('采用改写', 'Apply revision'), () => {
            if (block.text !== rewrite.original) return;
            block.text = input.value = task.result.text;
            block.rewrite = null;
            renderRewrite(block);
        });
        apply.disabled = block.text !== rewrite.original;
        const dismiss = blockButton(tr('关闭改写预览', 'Dismiss revision'), () => {
            block.rewrite = null;
            renderRewrite(block);
        });
        rewritePanel.append(preview);
        if (apply.disabled) rewritePanel.append(tr('这段文字已修改，改写结果可供参考。', 'This passage has changed. The revision is available for reference.'));
        rewritePanel.append(apply, dismiss);
    }
    function updateRewrites(tasks) {
        for (const block of draftBlocks) {
            const task = tasks.find(item => item.id === block.rewrite?.task?.id);
            if (task && task.status !== block.rewrite.task.status) {
                block.rewrite.task = task;
                renderRewrite(block);
            }
        }
    }
    function renderBlocks() {
        const fragment = document.createDocumentFragment();
        let passage = 0;
        for (const block of [...draftBlocks, null]) {
            const gap = document.createElement('div');
            gap.className = 'ds-block-gap';
            const add = blockButton('+', () => {
                const inserted = {type: 'paragraph', text: ''};
                draftBlocks.splice(block ? draftBlocks.indexOf(block) : draftBlocks.length, 0, inserted);
                renderBlocks();
                inserted.input.focus();
            });
            add.title = tr('插入段落', 'Insert paragraph');
            add.setAttribute('aria-label', add.title);
            gap.append(add);
            dropTarget(gap, block);
            fragment.append(gap);
            if (!block) break;
            const node = document.createElement('div');
            if (isImageRow(block)) {
                node.className = 'ds-image-row';
                for (const image of block.images) {
                    const figure = document.createElement('figure');
                    const img = document.createElement('img');
                    img.src = prefix + projectPath(projectId) + '/images/' + encodeURIComponent(image.asset_id);
                    img.alt = image.alt;
                    img.draggable = false;
                    const caption = document.createElement('figcaption');
                    caption.textContent = image.alt;
                    const remove = blockButton(tr('移除图片', 'Remove image'), () => {
                        block.images.splice(block.images.indexOf(image), 1);
                        if (!block.images.length) removeBlock(block);
                        else renderBlocks();
                    });
                    figure.append(img, caption, remove);
                    dropTarget(figure, block, image);
                    node.append(figure);
                }
            } else {
                node.className = 'ds-text-block';
                const label = document.createElement('label');
                const type = {heading: tr('标题', 'Heading'), list: tr('列表', 'List'),
                    quote: tr('引用', 'Quote'), paragraph: tr('段落', 'Paragraph')}[block.type];
                label.textContent = type + ' ' + ++passage;
                const input = document.createElement('textarea');
                input.value = block.text;
                input.rows = Math.max(2, Math.min(12, block.text.split('\n').reduce(
                    (lines, line) => lines + Math.max(1, Math.ceil(line.length / 64)), 0)));
                label.append(input);
                const actions = document.createElement('div');
                actions.className = 'ds-block-actions';
                const rewriteButton = blockButton(tr('AI 改写', 'Rewrite with AI'), () => rewriteDialog(block));
                if (supportsLayout(version)) actions.append(rewriteButton);
                actions.append(blockButton(tr('移除', 'Remove'), () => removeBlock(block)));
                const rewritePanel = document.createElement('div');
                rewritePanel.className = 'ds-rewrite';
                rewritePanel.setAttribute('aria-live', 'polite');
                Object.assign(block, {input, rewritePanel, rewriteButton});
                input.oninput = () => { block.text = input.value; renderRewrite(block); };
                node.append(label, actions, rewritePanel);
                renderRewrite(block);
            }
            fragment.append(node);
        }
        blocksRoot.replaceChildren(fragment);
    }
    function materialThumbnail(image, fallback) {
        const img = document.createElement('img');
        img.src = image.preview_url;
        img.alt = image.alt || fallback;
        img.title = img.alt;
        img.loading = 'lazy';
        img.draggable = true;
        img.addEventListener('dragstart', event => {
            event.dataTransfer.effectAllowed = 'copy';
            event.dataTransfer.setData(materialMime, image.asset_id);
        });
        return img;
    }
    function renderMaterials(materials) {
        const snapshot = JSON.stringify(materials);
        if (lastMaterialSnapshot === snapshot) return;
        lastMaterialSnapshot = snapshot;
        const thumbnails = new Map();
        $('#ds-materials').replaceChildren(...materials.map(item => {
            const detail = document.createElement('details');
            const summary = document.createElement('summary');
            summary.textContent = item.title + (item.active ? '' : tr(' · 旧素材版本', ' · Earlier snapshot'));
            detail.append(summary);
            for (const source of item.sources) {
                const link = document.createElement('a');
                link.href = source.url;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.textContent = source.title;
                detail.append(link);
            }
            for (const image of item.images) {
                if (image.preview_url) {
                    if (!thumbnails.has(image.asset_id)) thumbnails.set(image.asset_id, materialThumbnail(image, item.title));
                    detail.append(materialThumbnail(image, item.title));
                } else if (image.error) {
                    const reason = document.createElement('small');
                    reason.textContent = tr('缺少图片', 'Missing image') + ' · ' + (image.alt || image.url) + ' · ' + image.error;
                    const line = document.createElement('p');
                    line.append(reason);
                    detail.append(line);
                }
            }
            return detail;
        }));
        $('#ds-editor-material-images').replaceChildren(...thumbnails.values());
    }
    function updateOutput() {
        const translation = translator?.snapshot();
        const artifacts = [...(project?.outputs || []), ...packageOutputs, ...(translation?.outputs || [])]
            .sort((left, right) => right.created_at.localeCompare(left.created_at));
        const translationTasks = translation?.tasks || [];
        const articleTasks = project?.tasks || [];
        const tasks = workspace === translationId ? [...translationTasks, ...articleTasks] : [...articleTasks, ...translationTasks];
        output.update(workspace === translationId ? translationId : projectId, artifacts,
            latestImport && !tasks.some(task => task.id === latestImport.id) ? [latestImport, ...tasks] : tasks);
    }
    function render() {
        $('#ds-empty').hidden = !!(project || pack || importTask);
        $('#ds-author').hidden = !project;
        $('#ds-rename-project').disabled = $('#ds-delete-project').disabled = !project;
        const hasMaterials = Boolean(project?.materials?.length);
        $('#ds-no-materials').hidden = hasMaterials;
        generateForm.hidden = !hasMaterials;
        if (activeSidebar === 'ds-chat-tab') void mountChat();
        renderMaterials(project?.materials || []);
        const items = project?.versions || [];
        const names = items.map(item => ({...item, title: `${item.title} · ${formatLabel(item.target)} · ${new Date(item.created_at).toLocaleString()}`}));
        const sig = JSON.stringify(names);
        if (versionSelect.dataset.signature !== sig) {
            const baseSelect = generateForm.elements.base_version_id;
            options(baseSelect, names, tr('从工程素材开始', 'Start from project materials'), baseSelect.value);
            options(versionSelect, names, '', version?.id);
            versionSelect.dataset.signature = sig;
        }
        editor.hidden = !version || !project;
        $('#ds-legacy-editor-note').hidden = supportsLayout(version);
        $('#ds-layout-editor-note').hidden = !supportsLayout(version);
        $('#ds-editor-materials').hidden = !supportsLayout(version) || !$('#ds-editor-material-images').childElementCount;
        const tasks = project?.tasks || [];
        updateRewrites(tasks);
        updateOutput();
    }
    async function loadVersion(id) {
        const sequence = ++versionSequence;
        const current = projectId;
        const data = id ? await api(projectPath(current) + '/versions/' + encodeURIComponent(id)) : null;
        if (sequence !== versionSequence || current !== projectId) return;
        version = data;
        draftBlocks = [];
        if (version) {
            versionSelect.value = id;
            editor.elements.title.value = version.title;
            draftBlocks = supportsLayout(version) ? version.blocks.map(block => {
                if (block.type === 'image') return {type: 'image_row', images: [imageFields(block)]};
                if (isImageRow(block)) return {type: block.type, images: block.images.map(imageFields)};
                return {type: block.type, text: block.type === 'list' ? block.items.join('\n') : block.text};
            }) : parseDraftText(version.content);
            initialLayout = JSON.stringify(layoutPayload());
            $('#ds-text-output-note').hidden = version.target === 'html';
            renderBlocks();
        }
        render();
    }
    async function loadProject(id) {
        const sequence = ++changeSequence;
        ++versionSequence;
        resetChat();
        projectId = id;
        version = null;
        draftBlocks = [];
        project = null;
        projectSelect.value = id;
        sessionStorage.setItem(storage('project'), id);
        render();
        if (id) {
            const data = await api(projectPath(id));
            if (sequence !== changeSequence) return;
            project = data;
            await loadVersion(project.versions[0]?.id);
        }
    }
    async function loadProjects() {
        projects = await api('/projects');
        options(projectSelect, projects, tr('选择工程', 'Select a project'), projectId);
        if (!importForm.hidden && pack) {
            options(importForm.elements.project_id, projects, tr('新建工程', 'New project'), importForm.elements.project_id.value);
        }
    }
    function showPack() {
        $('#ds-incoming').hidden = !pack;
        if (!pack) return;
        options(importForm.elements.project_id, projects, tr('新建工程', 'New project'), '');
        importForm.elements.title.value = pack.entries[0]?.title.slice(0, 160) || '';
        $('#ds-import-title').hidden = false;
        $('#ds-pack-entries').replaceChildren(...pack.entries.map(item => {
            const row = document.createElement('li');
            row.textContent = item.title + tr(` · ${item.images} 张图`, ` · ${item.images} images`);
            return row;
        }));
        setBusy(importForm, Boolean(importTask));
    }
    async function readPack() {
        const url = new URL(location.href);
        const reference = url.searchParams.get('pack') || sessionStorage.getItem(storage('incoming'));
        if (!reference || reference === readingPack || reference === lastPack) return;
        readingPack = reference;
        try {
            pack = await api('/packs/' + encodeURIComponent(reference));
            lastPack = reference;
            showPack();
            render();
        } finally { readingPack = ''; }
    }
    function clearPack() {
        const current = pack?.id;
        pack = null;
        if (sessionStorage.getItem(storage('incoming')) === current) sessionStorage.removeItem(storage('incoming'));
        const url = new URL(location.href);
        if (url.searchParams.get('pack') === current) {
            url.searchParams.delete('pack');
            history.replaceState(null, '', url);
        }
        lastPack = '';
        showPack();
        render();
    }
    async function refresh() {
        if (updating) return;
        updating = true;
        try {
            if (workspace === translationId || translator?.snapshot().tasks.some(running)) {
                await translator.refresh().catch(translator.error);
            }
            if (importTask) {
                const task = await api('/tasks/' + encodeURIComponent(importTask));
                if (task.id !== importTask) return;
                latestImport = task;
                if (!running(task)) {
                    importTask = '';
                    sessionStorage.removeItem(storage('import-task'));
                    setBusy(importForm, false);
                    if (task.status === 'completed') {
                        const incoming = sessionStorage.getItem(storage('import-pack'));
                        if (pack?.id === incoming) clearPack();
                        await loadProjects();
                        if (!dirty()) await loadProject(task.result.project_id);
                    }
                    sessionStorage.removeItem(storage('import-pack'));
                }
            }
            const id = projectId;
            const sequence = changeSequence;
            if (id && project) {
                let data;
                try { data = await api(projectPath(id)); }
                catch (error) {
                    if (error.status !== 404) throw error;
                    if (sequence === changeSequence) {
                        await loadProject('');
                        await loadProjects();
                    }
                    return;
                }
                if (sequence !== changeSequence) return;
                const added = data.versions[0]?.id && data.versions[0].id !== project.versions[0]?.id;
                project = data;
                if (added && !dirty() && !savingDraft && !importingImage) {
                    const newest = data.versions[0].id;
                    await loadVersion(newest);
                    if (version?.id === newest && data.tasks.some(task => task.kind === 'doc_studio.generate' &&
                        task.status === 'completed' && task.result?.version_id === newest)) {
                        editor.scrollIntoView({block: 'start'});
                    }
                }
            }
            render();
        } finally { updating = false; }
    }
    function projectNameDialog(rename) {
        const current = project;
        if (rename ? !current : !discard()) return;
        showError(null);
        window.AI2AppsTextInputDialog.open({
            title: rename ? tr('改名文章工程', 'Rename article project') : tr('新建文章工程', 'New article project'),
            label: tr('工程名称', 'Project name'), value: rename ? current.title : '', maxLength: 160,
            submitLabel: rename ? tr('保存', 'Save') : tr('创建', 'Create'),
            cancelLabel: tr('取消', 'Cancel'),
            async onSubmit(title) {
                if (rename) {
                    const updated = await api(projectPath(current.id), {title}, 'PATCH');
                    if (project?.id === updated.id) project.title = updated.title;
                    await loadProjects();
                } else {
                    const created = await submit('/projects', {title});
                    await loadProjects();
                    await loadProject(created.id);
                }
            },
        });
    }
    $('#ds-create-project').onclick = () => projectNameDialog(false);
    $('#ds-rename-project').onclick = () => projectNameDialog(true);

    const deleteDialog = $('#ds-delete-dialog');
    const deleteSubmit = deleteDialog.querySelector('button[type=submit]');
    const deleteCancel = $('#ds-delete-cancel');
    const deleteError = $('#ds-delete-error');
    let deleteTarget = null;

    $('#ds-delete-project').onclick = () => {
        if (!project) return;
        deleteTarget = project.id;
        deleteError.hidden = true;
        $('#ds-delete-description').textContent = tr(
            `将永久删除「${project.title}」及工程内的素材、稿件版本和产物。`,
            `Permanently delete “${project.title}”, its project materials, saved drafts and outputs?`);
        deleteDialog.showModal();
    };
    deleteCancel.onclick = () => deleteDialog.close();
    deleteDialog.oncancel = event => { if (deleteSubmit.disabled) event.preventDefault(); };
    deleteDialog.querySelector('form').onsubmit = async event => {
        event.preventDefault();
        if (deleteSubmit.disabled || !deleteTarget) return;
        const id = deleteTarget;
        deleteSubmit.disabled = deleteCancel.disabled = true;
        deleteError.hidden = true;
        try {
            await api(projectPath(id), undefined, 'DELETE');
            deleteDialog.close();
            if (projectId === id) await loadProject('');
            await loadProjects();
            if (!projectId && projects.length) await loadProject(projects[0].id);
        } catch (error) {
            deleteError.textContent = error.message;
            deleteError.hidden = false;
            if (!deleteDialog.open) showError(error);
        } finally {
            deleteSubmit.disabled = deleteCancel.disabled = false;
        }
    };

    projectSelect.onchange = safe(async () => {
        if (discard()) await loadProject(projectSelect.value);
        else projectSelect.value = projectId;
    });
    versionSelect.onchange = safe(async () => {
        if (discard()) await loadVersion(versionSelect.value);
        else versionSelect.value = version.id;
    });
    importForm.elements.project_id.onchange = () => {
        $('#ds-import-title').hidden = !!importForm.elements.project_id.value;
    };
    $('#ds-dismiss').onclick = clearPack;
    importForm.onsubmit = safe(async () => {
        const id = pack?.id;
        if (!id || importTask) return;
        setBusy(importForm, true);
        try {
            const projectId = importForm.elements.project_id.value || null;
            const task = await submit('/imports', {
                pack_id: id, project_id: projectId,
                title: projectId ? null : importForm.elements.title.value.trim() || null,
            });
            importTask = task.id;
            latestImport = task;
            sessionStorage.setItem(storage('import-task'), task.id);
            sessionStorage.setItem(storage('import-pack'), id);
            render();
        } finally { setBusy(importForm, Boolean(importTask)); }
    });
    generateForm.onsubmit = safe(async () => {
        setBusy(generateForm, true);
        try {
            const fields = Object.fromEntries(new FormData(generateForm));
            fields.base_version_id ||= null;
            await submit(projectPath(projectId) + '/generate', fields);
            await refresh();
        } finally { setBusy(generateForm, false); }
    });
    editor.onsubmit = safe(async () => {
        if (!version || savingDraft || importingImage) return;
        const id = projectId;
        const current = version;
        const blocks = layoutPayload();
        if (!blocks.some(block => !isImageRow(block))) {
            throw Error(tr('请保留至少一段正文。', 'Keep at least one text block in the draft.'));
        }
        savingDraft = true;
        setBusy(editor, true);
        blocksRoot.inert = true;
        editor.elements.title.readOnly = true;
        try {
            const result = await submit(projectPath(id) + '/versions/' + current.id, {
                title: editor.elements.title.value,
                ...(supportsLayout(current) ? {blocks} : {
                    content: JSON.stringify(blocks) === initialLayout ? current.content : draftText(),
                }),
            });
            if (projectId !== id) return;
            if (version === current) await loadVersion(result.id);
            await refresh();
        } finally {
            savingDraft = false;
            blocksRoot.inert = false;
            editor.elements.title.readOnly = false;
            setBusy(editor, false);
        }
    });
    $('#ds-export').onclick = safe(async event => {
        if (!version || !discard()) return;
        const button = event.currentTarget;
        button.disabled = true;
        try {
            await submit(projectPath(projectId) + '/export', {version_id: version.id});
            await refresh();
        } finally { button.disabled = false; }
    });
    generateForm.elements.language.value = [...generateForm.elements.language.options].some(
        option => option.value === document.documentElement.lang) ? document.documentElement.lang : 'en';

    function resumeImport() {
        const taskId = sessionStorage.getItem(storage('import-task'));
        if (taskId && importTask !== taskId) {
            importTask = taskId;
            latestImport = null;
            setBusy(importForm, true);
            void refresh().catch(showError);
        }
    }
    window.addEventListener('ai2apps:host-context', () => {
        resumeImport();
        void readPack().catch(showError);
    });
    window.addEventListener('storage', event => {
        if (event.key === storage('incoming')) void readPack().catch(showError);
        if (event.key === storage('import-task')) resumeImport();
    });
    void (async () => {
        await loadProjects();
        const previous = sessionStorage.getItem(storage('project'));
        await loadProject(projects.some(item => item.id === previous) ? previous : projects[0]?.id || '');
        await readPack();
        await refresh();
    })().catch(showError);
    void refreshPackages();
    void refreshPackageOutputs().catch(showError);
    window.setInterval(() => {
        if (document.visibilityState !== 'hidden') void refresh().catch(error => {
            if (error.status === 404 && importTask) {
                importTask = '';
                sessionStorage.removeItem(storage('import-task'));
                setBusy(importForm, false);
            }
            showError(error);
        });
    }, 2500);
})();
