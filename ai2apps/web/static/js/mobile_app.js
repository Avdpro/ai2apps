(function () {
    'use strict';
    window.AI2APPS_MOBILE_SURFACE = true;
    window._t = window._t || {};
    window.t = window.t || function (key) { return window._t[key] !== undefined ? window._t[key] : key; };
    try {
        var stored = localStorage.getItem('omlx-chat-theme');
        var theme = stored || 'auto';
        if (theme === 'auto') theme = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', theme);
    } catch (_) { /* storage may be unavailable in a private iframe */ }

    function processIcons() {
        if (typeof lucide === 'undefined' || !lucide.icons) return;
        document.querySelectorAll('i[data-lucide]').forEach(function (element) {
            var name = element.getAttribute('data-lucide');
            var pascal = name && name.replace(/(^|[-_ ])(\w)/g, function (_, separator, letter) { return letter.toUpperCase(); });
            var definition = pascal && lucide.icons[pascal];
            if (!definition) return;
            var svg = lucide.createElement(definition);
            Array.from(element.attributes).forEach(function (attribute) {
                if (attribute.name !== 'data-lucide') svg.setAttribute(attribute.name, attribute.value);
            });
            svg.classList.add('lucide', 'lucide-' + name);
            element.replaceWith(svg);
        });
    }
    document.addEventListener('DOMContentLoaded', processIcons);
    setInterval(processIcons, 400);
}());
