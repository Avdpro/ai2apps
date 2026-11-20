(() => {
    'use strict';
    const miniAppId = 'ai2apps.imagine.comic-translation';
    const studioId = 'ai2apps.imagine-studio';
    (window.AI2AppsMiniAppBridges ||= new Map()).set(miniAppId, async (request, {base, signal, readAsset}) => {
        const root = base + '/comic-translation';
        let path, body, headers;
        if (request.action === 'reference') {
            const id = request.assetId;
            if (!/^[\w-]{1,200}$/.test(id || '')) throw Error('Invalid Gallery image');
            return readAsset({source: 'gallery', assetId: id});
        }
        if (request.action === 'models') {
            path = '/models';
        } else if (['analyze', 'recognize', 'recognize-vertical'].includes(request.action)) {
            if (!(request.file instanceof Blob) || !request.file.size || request.file.size > 16 * 1024 ** 2) {
                throw Error('Image must be between 1 byte and 16 MiB');
            }
            body = new FormData();
            body.append('file', request.file, 'comic.png');
            path = '/image/' + request.action;
        } else if (request.action === 'translate') {
            body = JSON.stringify(request.settings);
            if (!body || body.length > 300_000) throw Error('Dialogue and glossary are too large');
            headers = {'Content-Type': 'application/json'};
            path = '/translate';
        } else if (request.action === 'export') {
            const {files, format} = request;
            if (!['png', 'html'].includes(format) || !Array.isArray(files) || files.length < 1 ||
                files.length > (format === 'png' ? 50 : 1) ||
                files.some(file => !(file instanceof Blob) || !file.size) ||
                files.reduce((total, file) => total + file.size, 0) > 64 * 1024 ** 2) {
                throw Error('Invalid export or size exceeds 64 MiB');
            }
            body = new FormData();
            files.forEach(file => body.append('files', file, 'comic.' + format));
            path = '/export/' + format;
        } else throw Error('Unknown comic operation');
        const response = await fetch(root + path, {method: body ? 'POST' : 'GET', body, headers,
            credentials: 'same-origin', cache: 'no-store', signal});
        const result = await response.json();
        if (!response.ok) {
            const message = result.error?.message ?? result.detail;
            throw Error(typeof message === 'string' && message ? message : `HTTP ${response.status}`);
        }
        if (request.action === 'export') {
            window.dispatchEvent(new CustomEvent('ai2apps:studio-output', {detail: {studioId, miniAppId, result}}));
        }
        return result;
    });
})();
