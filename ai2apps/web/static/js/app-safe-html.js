(async function () {
    'use strict';
    const host = document.getElementById('app-view');
    try {
        const response = await fetch(document.body.dataset.resourceUrl, {
            credentials: 'same-origin',
            headers: { Accept: 'text/html' },
        });
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const source = await response.text();
        host.innerHTML = DOMPurify.sanitize(source, {
            USE_PROFILES: { html: true },
            FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form'],
            FORBID_ATTR: ['style'],
        });
    } catch (error) {
        host.innerHTML = '';
        const message = document.createElement('div');
        message.className = 'app-view-error';
        message.textContent = 'Unable to open this App view: ' + error.message;
        host.appendChild(message);
    }
})();
