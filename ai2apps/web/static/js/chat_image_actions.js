/* Chat image actions keep durable artifact identity across save and Gallery import. */
(() => {
    'use strict';
    function label(key) {
        const fullKey = 'chat.image.' + key;
        const translated = window.t?.(fullKey);
        if (translated && translated !== fullKey) return translated;
        const chinese = String(document.documentElement.lang).startsWith('zh');
        return {save: chinese ? '保存图片' : 'Save image', add_gallery: chinese ? '加入素材库' : 'Add to Gallery', added: chinese ? '已加入素材库' : 'Added to Gallery'}[key];
    }
    function reference(url) {
        const value = new URL(url, window.location.origin);
        if (value.origin !== window.location.origin) return null;
        const match = value.pathname.match(/^\/v1\/platform\/sessions\/([^/]+)\/artifacts\/([^/]+)\/download$/);
        return match ? {sessionId: decodeURIComponent(match[1]), artifactId: decodeURIComponent(match[2]), sourceAppId: 'ai2apps.general-chat'} : null;
    }
    async function checked(response) {
        if (response.ok) return response;
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload?.error?.message || payload?.detail?.message || `HTTP ${response.status}`);
    }
    async function imageBlob(url, apiKey) {
        const target = new URL(url, window.location.origin);
        const local = target.origin === window.location.origin;
        const response = await checked(await fetch(target.href, {credentials: local ? 'same-origin' : 'omit', headers: local && apiKey ? {Authorization: `Bearer ${apiKey}`} : {}}));
        const blob = await response.blob();
        if (!blob.type.startsWith('image/')) throw new Error('The source did not return an image.');
        return blob;
    }
    const filename = blob => `chat-image.${blob.type === 'image/jpeg' ? 'jpg' : (blob.type.split('/')[1] || 'png')}`;
    async function save(url, apiKey) {
        const blob = await imageBlob(url, apiKey);
        const objectUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = objectUrl; link.download = filename(blob);
        document.body.append(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(objectUrl), 30000);
    }
    async function addToGallery(url, apiKey) {
        const ref = reference(url);
        const headers = apiKey ? {Authorization: `Bearer ${apiKey}`} : {};
        let endpoint, body;
        if (ref) {
            endpoint = `/v1/platform/gallery/assets/import-artifact/${encodeURIComponent(ref.sessionId)}/${encodeURIComponent(ref.artifactId)}`;
            headers['Content-Type'] = 'application/json';
            body = JSON.stringify({sourceAppId: ref.sourceAppId});
        } else {
            const blob = await imageBlob(url, apiKey);
            endpoint = '/v1/platform/gallery/assets/import';
            body = new FormData(); body.append('file', blob, filename(blob)); body.append('sourceAppId', 'ai2apps.general-chat');
        }
        await checked(await fetch(endpoint, {method: 'POST', credentials: 'same-origin', headers, body}));
        document.querySelectorAll('iframe[data-mini-mount-id]').forEach(frame => frame.contentWindow?.postMessage({type: 'ai2apps.gallery.refresh'}, window.location.origin));
    }
    function drag(event, url) {
        const transfer = event.dataTransfer;
        if (!transfer) return;
        const ref = reference(url);
        transfer.effectAllowed = 'copy';
        transfer.clearData();
        if (ref) transfer.setData('application/x-ai2apps-session-artifact', JSON.stringify(ref));
        else if (String(url).startsWith('data:image/')) transfer.setData('text/uri-list', url);
        else { event.preventDefault(); return; }
        transfer.setData('text/plain', 'Chat image');
    }
    window.AI2AppsChatImages = {reference, save, addToGallery, drag, label};
})();
