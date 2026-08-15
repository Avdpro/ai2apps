(async function () {
    'use strict';
    const host = document.getElementById('app-view');

    function card(key, value) {
        const section = document.createElement('section');
        section.className = 'schema-card';
        const heading = document.createElement('h2');
        heading.className = 'schema-key';
        heading.textContent = key;
        const content = document.createElement('pre');
        content.className = 'schema-value';
        content.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
        section.append(heading, content);
        return section;
    }

    try {
        const response = await fetch(document.body.dataset.resourceUrl, {
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
        });
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const schema = await response.json();
        host.innerHTML = '';
        const title = document.createElement('h1');
        title.className = 'schema-title';
        title.textContent = schema.title || document.body.dataset.appName || 'App';
        host.appendChild(title);
        const values = schema.values || schema.properties || schema;
        if (values && typeof values === 'object' && !Array.isArray(values)) {
            Object.entries(values).forEach(([key, value]) => host.appendChild(card(key, value)));
        } else {
            host.appendChild(card('Value', values));
        }
    } catch (error) {
        host.innerHTML = '';
        const message = document.createElement('div');
        message.className = 'app-view-error';
        message.textContent = 'Unable to open this App schema: ' + error.message;
        host.appendChild(message);
    }
})();
