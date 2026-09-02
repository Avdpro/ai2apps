(() => {
    'use strict';
    const API = '/v1/platform/gallery';

    function tr(key, values = {}) {
        let text = typeof window.t === 'function' ? window.t(key) : key;
        Object.entries(values).forEach(([name, value]) => { text = text.replaceAll(`{${name}}`, String(value)); });
        return text;
    }

    async function request(path, options) {
        const response = await fetch(API + path, { credentials: 'same-origin', headers: { Accept: 'application/json', ...((options?.body && !(options.body instanceof FormData)) ? { 'Content-Type': 'application/json' } : {}) }, ...(options || {}), body: options?.body && !(options.body instanceof FormData) ? JSON.stringify(options.body) : options?.body });
        if (response.status === 204) return null;
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const code = payload?.error?.code || payload?.detail?.code || '';
            const key = code ? `gallery.error.api.${code}` : '';
            const localized = key ? tr(key) : '';
            throw new Error((localized && localized !== key) ? localized : (payload?.error?.message || payload?.detail?.message || tr('gallery.error.request_failed')));
        }
        return payload;
    }

    function decodeBase64(value) {
        const binary = atob(String(value || ''));
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
        return bytes;
    }

    window.galleryApp = function () { return {
        tr,
        collections: [], assets: [], selectedCollectionId: 'recent', selectedIds: [], selectionOperation: 'copy', targetCollectionId: '', search: '', kind: '', view: 'grid', loading: true, busy: false, notice: '', noticeTone: '', noticeTimer: null, creatingCollection: false, newCollectionName: '', newCollectionKind: 'custom', draggedAssetId: null, dragStartedAt: 0, hostMessageHandler: null, keyboardHandler: null, clientEnvironment: 'browser', surface: 'full',
        pageContext: null, isBrowserSidebar: false, pageClient: null, browserDrag: null, browserMediaImportPromise: null, browserImportStage: '', browserImportProgress: 0,
        previewAsset: null, previewZoom: 1, previewPanX: 0, previewPanY: 0, previewPanStart: null, previewRenaming: false, previewName: '', previewSavingName: false,
        async init() {
            this.clientEnvironment = this.$root?.dataset?.clientEnvironment || 'browser';
            this.surface = this.$root?.dataset?.gallerySurface || 'full';
            const browserParams = new URLSearchParams(window.location.hash.slice(1));
            if (this.surface === 'mini-entry' && browserParams.get('bidi_context')) {
                this.isBrowserSidebar = true;
                this.pageContext = {
                    bidi_context: browserParams.get('bidi_context') || '',
                    url: browserParams.get('url') || '',
                    title: browserParams.get('title') || '',
                };
                // Connect only when a page transfer starts.  Firefox exposes one
                // native BiDi Session, so an idle Gallery must not occupy it.
            }
            if (this.surface === 'preview') {
                this.selectedCollectionId = this.$root?.dataset?.previewCollectionId || 'recent';
                this.kind = this.$root?.dataset?.previewKind || '';
                this.search = this.$root?.dataset?.previewSearch || '';
            }
            this.hostMessageHandler = event => {
                if (event.origin === window.location.origin && event.source === window.parent && event.data?.type === 'ai2apps.gallery.refresh') this.loadAssets();
            };
            this.keyboardHandler = event => this.handlePreviewKey(event);
            window.addEventListener('message', this.hostMessageHandler);
            window.addEventListener('keydown', this.keyboardHandler);
            window.addEventListener('beforeunload', () => this.cleanup(), { once: true });
            await this.refresh();
            if (this.surface === 'preview') await this.openRequestedPreview();
        },
        get selectedCollection() { return this.collections.find(item => item.id === this.selectedCollectionId) || this.collections[0]; },
        get selectedCollectionName() { return this.collectionName(this.selectedCollection); },
        get systemCollections() { return this.collections.filter(item => item.kind === 'system'); },
        get userCollections() { return this.collections.filter(item => item.kind !== 'system'); },
        get writableCollections() { return this.collections.filter(item => item.id !== 'recent' && item.system_key !== 'trash' && item.id !== this.selectedCollectionId); },
        get canMoveFromCurrent() { return this.selectedCollectionId !== 'recent' && this.selectedCollection?.system_key !== 'trash'; },
        get canRemoveFromCurrent() { return this.canMoveFromCurrent; },
        get previewIndex() { return this.previewAsset ? this.assets.findIndex(item => item.id === this.previewAsset.id) : -1; },
        get hasPreviousPreview() { return this.previewIndex > 0; },
        get hasNextPreview() { return this.previewIndex >= 0 && this.previewIndex < this.assets.length - 1; },
        get previewPosition() { return this.previewIndex < 0 ? '' : `${this.previewIndex + 1} / ${this.assets.length}`; },
        get browserImportStatusText() {
            if (this.browserImportStage === 'reading') return tr('gallery.mini.import.reading', { progress: this.browserImportProgress });
            if (this.browserImportStage === 'saving') return tr('gallery.mini.import.saving');
            return tr('gallery.mini.import.accepted');
        },
        get previewImageTransform() { return `transform:translate3d(${this.previewPanX}px,${this.previewPanY}px,0) scale(${this.previewZoom});cursor:${this.previewZoom > 1 ? (this.previewPanStart ? 'grabbing' : 'grab') : 'zoom-in'}`; },
        async refresh() { await this.loadCollections(); await this.loadAssets(); },
        async loadCollections() { try { this.collections = (await request('/collections')).items || []; if (!this.collections.some(item => item.id === this.selectedCollectionId)) this.selectedCollectionId = 'recent'; if (this.selectedIds.length) this.ensureSelectionTarget(); this.$nextTick(() => window.lucide?.createIcons()); } catch (error) { this.fail(error); } },
        async loadAssets() { this.loading = true; this.selectedIds = []; this.targetCollectionId = ''; this.notifyActiveCollection(); const params = new URLSearchParams({ collectionId: this.selectedCollectionId, ...(this.kind ? { kind: this.kind } : {}), ...(this.search.trim() ? { search: this.search.trim() } : {}) }); try { this.assets = (await request('/assets?' + params)).items || []; } catch (error) { this.fail(error); } finally { this.loading = false; this.$nextTick(() => window.lucide?.createIcons()); } },
        async selectCollection(collection) { this.selectedCollectionId = collection.id; this.selectionOperation = 'copy'; this.targetCollectionId = ''; await this.loadAssets(); },
        async createCollection() { if (!this.newCollectionName || this.busy) return; this.busy = true; try { const created = await request('/collections', { method: 'POST', body: { name: this.newCollectionName, kind: this.newCollectionKind } }); this.newCollectionName = ''; this.creatingCollection = false; await this.loadCollections(); await this.selectCollection(created); this.success(tr('gallery.success.collection_created')); } catch (error) { this.fail(error); } finally { this.busy = false; } },
        async deleteCollection(collection) {
            if (!collection || collection.kind === 'system' || collection.system_key || this.busy) return;
            const name = this.collectionName(collection);
            if (!confirm(tr('gallery.confirm.delete_collection', { name }))) return;
            this.busy = true;
            try {
                await request(`/collections/${encodeURIComponent(collection.id)}`, { method: 'DELETE' });
                if (this.selectedCollectionId === collection.id) {
                    this.selectedCollectionId = 'recent';
                    this.selectedIds = [];
                    this.targetCollectionId = '';
                    await this.loadAssets();
                }
                await this.loadCollections();
                this.success(tr('gallery.success.collection_deleted', { name }));
            } catch (error) { this.fail(error); } finally { this.busy = false; }
        },
        async importFiles(files, overrideCollectionId = null, sourceAppId = 'host.import', sourceRef = '') { const selected = Array.from(files || []); if (!selected.length) return false; this.busy = true; let imported = 0; const collectionId = overrideCollectionId || this.selectedCollectionId; try { for (const file of selected) { const form = new FormData(); form.append('file', file, file.name); if (collectionId && collectionId !== 'recent') form.append('collectionId', collectionId); form.append('sourceAppId', sourceAppId); if (sourceRef) form.append('sourceRef', sourceRef); await request('/assets/import', { method: 'POST', body: form }); imported += 1; } await this.loadCollections(); if (overrideCollectionId && overrideCollectionId !== this.selectedCollectionId) this.selectedCollectionId = overrideCollectionId; await this.loadAssets(); this.success(tr('gallery.success.imported', { count: imported })); return true; } catch (error) { this.fail(error); return false; } finally { this.busy = false; } },
        droppedMediaURLs(event) {
            const transfer = event.dataTransfer;
            const candidates = [];
            const add = value => {
                const raw = String(value || '').trim();
                if (!raw) return;
                try {
                    const resolved = new URL(raw, this.pageContext?.url || window.location.origin).href;
                    if (!candidates.includes(resolved)) candidates.push(resolved);
                } catch (_) {}
            };
            const uriList = String(transfer?.getData('text/uri-list') || '').split('\n').filter(line => line && !line.startsWith('#'));
            const mozURL = String(transfer?.getData('text/x-moz-url') || '').split('\n')[0] || '';
            const html = String(transfer?.getData('text/html') || '');
            if (html) {
                const parsed = new DOMParser().parseFromString(html, 'text/html');
                for (const media of parsed.querySelectorAll('img,video,audio,video source,audio source')) {
                    for (const attribute of ['src', 'data-src', 'data-lazy-src', 'data-original']) add(media.getAttribute(attribute));
                    for (const attribute of ['srcset', 'data-srcset']) {
                        const entries = String(media.getAttribute(attribute) || '').split(',').map(item => item.trim().split(/\s+/)[0]).filter(Boolean);
                        for (const entry of entries.reverse()) add(entry);
                    }
                }
            }
            // Firefox supplies the enclosing anchor as text/uri-list when an
            // image inside a link is dragged.  Prefer the actual media element
            // from text/html; the navigation URL is only a fallback.
            for (const item of uriList) add(item);
            add(mozURL);
            const plain = String(transfer?.getData('text/plain') || '').trim();
            if (/^(?:https?:|blob:|data:(?:image|video|audio)\/)/i.test(plain)) add(plain);
            return candidates;
        },
        async dropFiles(event) {
            if (event.dataTransfer?.files?.length) return this.importFiles(event.dataTransfer.files);
            const raw = event.dataTransfer?.getData('application/x-ai2apps-video-artifact');
            if (raw) {
                try { await this.importArtifactReference(JSON.parse(raw)); } catch (error) { this.fail(error); }
                return;
            }
            const uris = this.droppedMediaURLs(event);
            const uri = uris[0] || '';
            const historyUrl = (() => {
                try {
                    const value = new URL(uri, window.location.origin);
                    return value.origin === window.location.origin && /^\/v1\/platform\/imagine-studio\/results\/isr_[0-9a-f]{32}\/content$/.test(value.pathname) ? value.href : '';
                } catch (_) { return ''; }
            })();
            if (!uri.startsWith('data:image/') && !historyUrl) {
                if (this.isBrowserSidebar && uris.length) return this.importBrowserPageMedia(uris);
                return;
            }
            try {
                const response = await fetch(historyUrl || uri, { credentials: 'same-origin' });
                if (!response.ok) throw new Error(tr('gallery.error.drop_image_read', { status: response.status }));
                const blob = await response.blob();
                if (!String(blob.type || '').startsWith('image/')) throw new Error(tr('gallery.error.drop_image_type'));
                const fallbackName = `imagine-studio-${Date.now()}.${blob.type === 'image/jpeg' ? 'jpg' : (blob.type.split('/')[1] || 'png')}`;
                const name = String(event.dataTransfer?.getData('text/plain') || fallbackName).replace(/[\\/]/g, '-');
                await this.importFiles([new File([blob], name, { type: blob.type })], null, 'ai2apps.imagine-studio');
            } catch (error) { this.fail(error); }
        },
        async ensureBrowserPageClient() {
            await this.syncBrowserPageContext();
            if (!this.isBrowserSidebar || !this.pageContext?.bidi_context || !window.AI2AppsBiDi?.AI2AppsPageClient) {
                throw new Error(tr('gallery.error.browser_context_unavailable'));
            }
            if (this.pageClient?.contextId) return this.pageClient;
            await this.pageClient?.connection?.close().catch(() => {});
            this.pageClient = new window.AI2AppsBiDi.AI2AppsPageClient(this.pageContext);
            try {
                await this.pageClient.connect();
                return this.pageClient;
            } catch (error) {
                await this.pageClient.connection.close().catch(() => {});
                this.pageClient = null;
                throw error;
            }
        },
        async syncBrowserPageContext() {
            if (!this.isBrowserSidebar) return;
            const params = new URLSearchParams(window.location.hash.slice(1));
            const next = {
                bidi_context: params.get('bidi_context') || '',
                url: params.get('url') || '',
                title: params.get('title') || '',
            };
            if (!next.bidi_context) return;
            const changed = !this.pageContext || Object.keys(next).some(key => next[key] !== this.pageContext[key]);
            if (!changed) return;
            await this.pageClient?.connection?.close().catch(() => {});
            this.pageClient = null;
            this.pageContext = next;
        },
        async importBrowserPageMedia(uris) {
            // Firefox can emit more than one drop notification for the same
            // native drag.  Sharing the operation prevents one handler from
            // ending the single BiDi session while the other is still reading.
            if (this.browserMediaImportPromise) return this.browserMediaImportPromise;
            const operation = this.performBrowserPageMediaImport(uris);
            this.browserMediaImportPromise = operation;
            try { return await operation; }
            finally {
                if (this.browserMediaImportPromise === operation) this.browserMediaImportPromise = null;
            }
        },
        async performBrowserPageMediaImport(uris) {
            let transfer = null;
            let client = null;
            const statusStartedAt = Date.now();
            try {
                this.dismissNotice();
                this.browserImportStage = 'resolving';
                this.browserImportProgress = 0;
                this.$nextTick(() => window.lucide?.createIcons());
                let lastError = null;
                // A previously unloading mini-entry or another short-lived
                // sidebar operation may still own Firefox's native session.
                // Reconnect once after cleanup instead of surfacing that race.
                for (let attempt = 0; attempt < 2; attempt += 1) {
                    try {
                        client = await this.ensureBrowserPageClient();
                        transfer = await client.beginPageResourceTransfer(uris);
                        break;
                    } catch (error) {
                        lastError = error;
                        await client?.connection?.close().catch(() => {});
                        if (this.pageClient === client) this.pageClient = null;
                        client = null;
                        if (attempt === 0 && /disconnected|not ready|unavailable|timed out/i.test(String(error?.message || error))) {
                            await new Promise(resolve => setTimeout(resolve, 300));
                            continue;
                        }
                        throw error;
                    }
                }
                if (!transfer) throw lastError || new Error(tr('gallery.error.browser_media_read'));
                this.browserImportStage = 'reading';
                const parts = [];
                let offset = 0;
                while (offset < transfer.size) {
                    const chunk = await client.readPageResourceChunk(transfer.token, offset);
                    parts.push(decodeBase64(chunk.base64));
                    if (chunk.next_offset <= offset) throw new Error(tr('gallery.error.browser_media_read'));
                    offset = chunk.next_offset;
                    this.browserImportProgress = transfer.size ? Math.min(100, Math.round(offset / transfer.size * 100)) : 100;
                }
                const file = new File(parts, transfer.name, {type: transfer.media_type});
                this.browserImportStage = 'saving';
                this.browserImportProgress = 100;
                return await this.importFiles([file], null, 'ai2apps.browser-sidebar', transfer.url);
            } catch (error) {
                this.fail(new Error(`${tr('gallery.error.browser_media_read')} ${error?.message || error}`));
                return false;
            } finally {
                if (transfer?.token && client) await client.endPageResourceTransfer(transfer.token).catch(() => {});
                await client?.connection?.close().catch(() => {});
                if (this.pageClient === client) this.pageClient = null;
                const remaining = Math.max(0, 600 - (Date.now() - statusStartedAt));
                if (remaining) await new Promise(resolve => setTimeout(resolve, remaining));
                this.browserImportStage = '';
                this.browserImportProgress = 0;
            }
        },
        async importArtifactReference(reference) {
            const sessionId = String(reference?.sessionId || '');
            const artifactId = String(reference?.artifactId || '');
            if (!sessionId || !artifactId) throw new Error(tr('gallery.error.artifact_invalid'));
            this.busy = true;
            try {
                await request(`/assets/import-artifact/${encodeURIComponent(sessionId)}/${encodeURIComponent(artifactId)}`, {
                    method: 'POST',
                    body: {
                        collectionId: this.selectedCollectionId === 'recent' ? null : this.selectedCollectionId,
                        name: reference.name || null,
                        sourceAppId: reference.sourceAppId || 'ai2apps.video-studio',
                    },
                });
                await this.loadCollections(); await this.loadAssets();
            } finally { this.busy = false; }
        },
        activeCollectionChanged() { this.notifyActiveCollection(); return this.loadAssets(); },
        notifyActiveCollection() {
            if (window.parent === window) return;
            window.parent.postMessage({
                type: 'ai2apps.gallery.collection-changed',
                collectionId: this.selectedCollectionId,
                collectionName: this.selectedCollectionName,
            }, window.location.origin);
        },
        cleanup() {
            if (this.hostMessageHandler) window.removeEventListener('message', this.hostMessageHandler);
            if (this.keyboardHandler) window.removeEventListener('keydown', this.keyboardHandler);
            if (this.noticeTimer) window.clearTimeout(this.noticeTimer);
            document.body.style.overflow = '';
            void this.pageClient?.connection?.close().catch(() => {});
            this.pageClient = null;
        },
        async previewAssetFromMini(asset) {
            if (Date.now() - this.dragStartedAt < 500) return;
            try {
                const options = {
                    assetId: asset?.id || '', collectionId: this.selectedCollectionId,
                    kind: this.kind, search: this.search,
                };
                const bridge = window.parent !== window && window.parent.ai2appsShell
                    ? window.parent.ai2appsShell : window.ai2appsShell;
                if (!bridge?.openGalleryPreview) throw new Error(tr('gallery.error.preview_unsupported'));
                await bridge.openGalleryPreview(options);
            } catch (error) { this.fail(error); }
        },
        async openRequestedPreview() {
            const assetId = this.$root?.dataset?.previewAssetId || '';
            if (!assetId) return;
            try {
                const asset = this.assets.find(item => item.id === assetId)
                    || await request(`/assets/${encodeURIComponent(assetId)}`);
                await this.preloadPreviewAsset(asset);
                this.openPreview(asset);
                await this.waitForPreviewPaint(asset);
                window.parent.postMessage({ type: 'ai2apps.gallery.preview-ready' }, window.location.origin);
            } catch (error) {
                this.fail(error);
                window.parent.postMessage({ type: 'ai2apps.gallery.preview-error', error: error?.message || String(error) }, window.location.origin);
            }
        },
        preloadPreviewAsset(asset) {
            if (!['image', 'video', 'audio'].includes(asset?.kind)) return Promise.resolve();
            return new Promise(resolve => {
                const media = asset.kind === 'image' ? new Image() : document.createElement(asset.kind);
                const done = () => { window.clearTimeout(timer); resolve(); };
                const readyEvent = asset.kind === 'image' ? 'load' : 'loadedmetadata';
                const timer = window.setTimeout(done, 3000);
                media.addEventListener(readyEvent, done, { once: true });
                media.addEventListener('error', done, { once: true });
                media.src = this.contentUrl(asset);
                if (asset.kind !== 'image') media.load();
            });
        },
        async waitForPreviewPaint(asset) {
            await new Promise(resolve => this.$nextTick(resolve));
            const media = asset?.kind === 'image' ? this.$refs.previewImage
                : asset?.kind === 'video' ? this.$refs.previewVideo
                    : asset?.kind === 'audio' ? this.$refs.previewAudio : null;
            if (asset?.kind === 'image' && media?.decode) await media.decode().catch(() => {});
            if (['video', 'audio'].includes(asset?.kind) && media && media.readyState < 1) {
                await new Promise(resolve => {
                    const timer = window.setTimeout(resolve, 2000);
                    media.addEventListener('loadedmetadata', () => { window.clearTimeout(timer); resolve(); }, { once: true });
                    media.addEventListener('error', () => { window.clearTimeout(timer); resolve(); }, { once: true });
                });
            }
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
            this.$refs.previewDialog?.focus({ preventScroll: true });
        },
        openPreview(asset) {
            this.previewAsset = asset;
            this.previewRenaming = false;
            this.previewName = asset?.name || '';
            this.resetPreviewTransform();
            document.body.style.overflow = 'hidden';
            this.$nextTick(() => window.lucide?.createIcons());
        },
        closePreview() {
            if (this.surface === 'preview') {
                window.parent.postMessage({ type: 'ai2apps.gallery.preview-close' }, window.location.origin);
                return;
            }
            this.previewAsset = null; this.previewRenaming = false; this.previewPanStart = null;
            document.body.style.overflow = '';
        },
        movePreview(delta) {
            const nextIndex = this.previewIndex + Number(delta || 0);
            if (nextIndex < 0 || nextIndex >= this.assets.length) return;
            this.openPreview(this.assets[nextIndex]);
        },
        handlePreviewKey(event) {
            if (!this.previewAsset) return;
            if (event.key === 'Escape') { this.closePreview(); return; }
            if (event.target?.matches?.('input,textarea,select')) return;
            if (event.key === 'ArrowLeft') this.movePreview(-1);
            else if (event.key === 'ArrowRight') this.movePreview(1);
            else if (this.previewAsset.kind === 'image' && ['+', '='].includes(event.key)) this.changePreviewZoom(.25);
            else if (this.previewAsset.kind === 'image' && event.key === '-') this.changePreviewZoom(-.25);
        },
        beginPreviewRename() {
            this.previewName = this.previewAsset?.name || '';
            this.previewRenaming = true;
            this.$nextTick(() => { this.$refs.previewNameInput?.focus(); this.$refs.previewNameInput?.select(); window.lucide?.createIcons(); });
        },
        async savePreviewName() {
            if (!this.previewAsset || !this.previewName.trim() || this.previewSavingName) return;
            if (this.previewName.trim() === this.previewAsset.name) { this.previewRenaming = false; return; }
            this.previewSavingName = true;
            try {
                const updated = await request(`/assets/${encodeURIComponent(this.previewAsset.id)}`, { method: 'PATCH', body: { name: this.previewName.trim() } });
                const index = this.assets.findIndex(item => item.id === updated.id);
                if (index >= 0) this.assets[index] = updated;
                this.previewAsset = updated; this.previewName = updated.name; this.previewRenaming = false;
                this.$nextTick(() => window.lucide?.createIcons());
            } catch (error) { this.fail(error); } finally { this.previewSavingName = false; }
        },
        changePreviewZoom(delta) {
            this.previewZoom = Math.max(.25, Math.min(6, Math.round((this.previewZoom + delta) * 100) / 100));
            if (this.previewZoom <= 1) { this.previewPanX = 0; this.previewPanY = 0; }
        },
        togglePreviewZoom() {
            if (this.previewAsset?.kind !== 'image') return;
            if (this.previewZoom > 1) this.resetPreviewTransform();
            else this.previewZoom = 2;
        },
        wheelPreview(event) { this.changePreviewZoom(event.deltaY < 0 ? .25 : -.25); },
        resetPreviewTransform() { this.previewZoom = 1; this.previewPanX = 0; this.previewPanY = 0; this.previewPanStart = null; },
        startPreviewPan(event) {
            if (this.previewAsset?.kind !== 'image') return;
            if (this.previewZoom <= 1) return;
            this.previewPanStart = { x: event.clientX, y: event.clientY, panX: this.previewPanX, panY: this.previewPanY, pointerId: event.pointerId };
            event.currentTarget.setPointerCapture?.(event.pointerId);
        },
        movePreviewPan(event) {
            if (!this.previewPanStart || event.pointerId !== this.previewPanStart.pointerId) return;
            this.previewPanX = this.previewPanStart.panX + event.clientX - this.previewPanStart.x;
            this.previewPanY = this.previewPanStart.panY + event.clientY - this.previewPanStart.y;
        },
        endPreviewPan(event) {
            if (!this.previewPanStart) return;
            event.currentTarget.releasePointerCapture?.(event.pointerId);
            this.previewPanStart = null;
        },
        downloadAsset(event, asset) {
            if (!asset) { event.preventDefault(); return; }
            // Keep native anchor navigation: Desktop routes it to macOS Save As,
            // while a regular browser owns its standard download flow.
        },
        async dropOnCollection(event, collection) { if (collection.id === 'recent' || collection.system_key === 'trash') return; if (event.dataTransfer?.files?.length) return this.importFiles(event.dataTransfer.files, collection.id); const assetId = event.dataTransfer?.getData('application/x-ai2apps-gallery-asset') || this.draggedAssetId; if (!assetId) return; try { await request(`/collections/${encodeURIComponent(collection.id)}/assets/${encodeURIComponent(assetId)}`, { method: 'POST' }); await this.loadCollections(); this.success(tr('gallery.success.copied_to', { name: this.collectionName(collection) })); } catch (error) { this.fail(error); } },
        toggleAsset(asset, event) { const additive = event?.metaKey || event?.ctrlKey || event?.shiftKey; if (!additive && !this.selectedIds.includes(asset.id)) this.selectedIds = [asset.id]; else if (this.selectedIds.includes(asset.id)) this.selectedIds = this.selectedIds.filter(id => id !== asset.id); else this.selectedIds = [...this.selectedIds, asset.id]; if (this.selectedIds.length) this.ensureSelectionTarget(); else this.targetCollectionId = ''; this.$nextTick(() => window.lucide?.createIcons()); },
        dragAsset(event, asset) { this.draggedAssetId = asset.id; this.dragStartedAt = Date.now(); event.dataTransfer.effectAllowed = 'copyMove'; event.dataTransfer.setData('application/x-ai2apps-gallery-asset', asset.id); event.dataTransfer.setData('text/plain', asset.name); if (!this.isBrowserSidebar) event.dataTransfer.setData('text/uri-list', new URL(this.contentUrl(asset), window.location.origin).href); if (this.isBrowserSidebar) { const token = crypto.randomUUID(); event.dataTransfer.setData('application/x-ai2apps-gallery-drop-token', token); this.browserDrag = {token, assetId: asset.id, armPromise: this.ensureBrowserPageClient().then(client => client.armGalleryAssetDrop(token))}; } },
        async finishBrowserAssetDrag(asset) {
            const active = this.browserDrag;
            this.browserDrag = null;
            if (!this.isBrowserSidebar || !active || active.assetId !== asset.id) return;
            try {
                await active.armPromise;
                let state = null;
                for (let attempt = 0; attempt < 12; attempt += 1) {
                    state = await this.pageClient.galleryAssetDropState(active.token);
                    if (state.dropped) break;
                    await new Promise(resolve => setTimeout(resolve, 80));
                }
                if (!state?.dropped) { await this.pageClient.cancelGalleryAssetDrop(active.token); return; }
                const transfer = await request(`/assets/${encodeURIComponent(asset.id)}/browser-transfer`, {method: 'POST'});
                await this.pageClient.applyGalleryAssetDrop(active.token, [transfer.path]);
                this.success(tr('gallery.success.sent_to_page'));
            } catch (error) { try { await this.pageClient?.cancelGalleryAssetDrop(active.token); } catch (_) {} this.fail(error); }
            finally { await this.pageClient?.connection?.close().catch(() => {}); this.pageClient = null; }
        },
        async dropBeforeAsset(event, target) { const assetId = event.dataTransfer?.getData('application/x-ai2apps-gallery-asset') || this.draggedAssetId; if (!assetId || assetId === target.id || this.selectedCollection?.sort_mode !== 'manual') return; const ids = this.assets.map(item => item.id); const from = ids.indexOf(assetId), to = ids.indexOf(target.id); if (from < 0 || to < 0) return; ids.splice(to, 0, ids.splice(from, 1)[0]); this.assets = ids.map(id => this.assets.find(item => item.id === id)); try { await request(`/collections/${encodeURIComponent(this.selectedCollectionId)}/order`, { method: 'PUT', body: { asset_ids: ids } }); } catch (error) { this.fail(error); await this.loadAssets(); } },
        ensureSelectionTarget() { if (!this.writableCollections.some(item => item.id === this.targetCollectionId)) this.targetCollectionId = (this.writableCollections.find(item => item.system_key === 'personal') || this.writableCollections[0])?.id || ''; },
        selectionOperationChanged() { if (this.selectionOperation === 'move' && !this.canMoveFromCurrent) this.selectionOperation = 'copy'; this.ensureSelectionTarget(); this.$nextTick(() => window.lucide?.createIcons()); },
        async executeSelectedTransfer() { const ids = [...this.selectedIds]; if (!ids.length || !this.targetCollectionId) return; const operation = this.selectionOperation === 'move' && this.canMoveFromCurrent ? 'move' : 'copy'; this.busy = true; try { for (const assetId of ids) await request(`/collections/${encodeURIComponent(this.targetCollectionId)}/assets/${encodeURIComponent(assetId)}`, { method: 'POST' }); if (operation === 'move') { for (const assetId of ids) await request(`/collections/${encodeURIComponent(this.selectedCollectionId)}/assets/${encodeURIComponent(assetId)}`, { method: 'DELETE' }); } this.success(tr(operation === 'move' ? 'gallery.success.transferred_move' : 'gallery.success.transferred_copy', { count: ids.length })); this.selectedIds = []; this.targetCollectionId = ''; await this.loadCollections(); if (operation === 'move') await this.loadAssets(); } catch (error) { this.fail(error); } finally { this.busy = false; } },
        async copySelected() { this.selectionOperation = 'copy'; return this.executeSelectedTransfer(); },
        async removeSelectedFromCurrent() { await this.batch(async id => request(`/collections/${encodeURIComponent(this.selectedCollectionId)}/assets/${encodeURIComponent(id)}`, { method: 'DELETE' }), tr('gallery.success.removed')); },
        async trashSelected() { await this.batch(id => request(`/assets/${encodeURIComponent(id)}/trash`, { method: 'POST' }), tr('gallery.success.trashed')); },
        async restoreSelected() { await this.batch(id => request(`/assets/${encodeURIComponent(id)}/restore`, { method: 'POST' }), tr('gallery.success.restored')); },
        async deleteSelected() { if (!confirm(tr('gallery.confirm.delete', { count: this.selectedIds.length }))) return; await this.batch(id => request(`/assets/${encodeURIComponent(id)}`, { method: 'DELETE' }), tr('gallery.success.deleted')); },
        async batch(action, message) { const ids = [...this.selectedIds]; if (!ids.length) return; this.busy = true; try { for (const id of ids) await action(id); this.selectedIds = []; await this.refresh(); this.success(message); } catch (error) { this.fail(error); } finally { this.busy = false; } },
        openAsset(asset) { window.open(this.contentUrl(asset), '_blank', 'noopener'); },
        openFullGallery() {
            const bridge = window.parent !== window && window.parent.ai2appsShell
                ? window.parent.ai2appsShell
                : window.ai2appsShell;
            return bridge?.openEntry({ appId: 'ai2apps.gallery' });
        },
        contentUrl(asset, download = false) { return `${API}/assets/${encodeURIComponent(asset.id)}/content${download ? '?download=true' : ''}`; },
        collectionName(collection) { return collection?.system_key ? tr(`gallery.collection.${collection.system_key}`) : (collection?.name || ''); },
        collectionIcon(collection) { return collection.system_key === 'recent' ? 'clock-3' : collection.system_key === 'downloads' ? 'download' : collection.system_key === 'public' ? 'globe-2' : collection.system_key === 'personal' ? 'user-round' : collection.system_key === 'trash' ? 'trash-2' : 'folder'; },
        assetIcon(asset) { return asset.kind === 'audio' ? 'audio-lines' : asset.kind === 'web' ? 'panel-top' : asset.kind === 'document' ? 'file-text' : 'file'; },
        kindLabel(kind) { return kind ? tr(`gallery.kind.${kind}`) : ''; },
        extension(name) { const part = String(name || '').split('.').pop(); return part && part !== name ? part.slice(0, 8).toUpperCase() : 'FILE'; },
        formatSize(value) { const bytes = Number(value || 0); if (bytes < 1024) return bytes + ' B'; if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'; if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB'; return (bytes / 1073741824).toFixed(1) + ' GB'; },
        formatTime(value) { if (!value) return ''; const date = new Date(value); const today = new Date(); const locale = document.documentElement.lang || navigator.language; return date.toDateString() === today.toDateString() ? date.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' }) : date.toLocaleDateString(locale, { month: 'short', day: 'numeric' }); },
        showNotice(message, tone, timeoutMs) {
            if (this.noticeTimer) window.clearTimeout(this.noticeTimer);
            this.notice = message;
            this.noticeTone = tone;
            this.noticeTimer = window.setTimeout(() => this.dismissNotice(), timeoutMs);
            this.$nextTick(() => window.lucide?.createIcons());
        },
        dismissNotice() {
            if (this.noticeTimer) window.clearTimeout(this.noticeTimer);
            this.noticeTimer = null;
            this.notice = '';
            this.noticeTone = '';
        },
        success(message) { this.showNotice(message, 'success', 3000); },
        fail(error) { this.showNotice(error?.message || String(error), 'error', 7000); },
    }; };
})();
