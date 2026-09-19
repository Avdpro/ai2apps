(function () {
    'use strict';

    if (!window.lucide?.icons) return;

    const icons = window.ai2appsIcons = window.ai2appsIcons || {};

    icons.GalleryStackedHorizontal = [
        'svg',
        {
            xmlns: 'http://www.w3.org/2000/svg',
            width: 24,
            height: 24,
            viewBox: '0 0 24 24',
            fill: 'none',
            stroke: 'currentColor',
            'stroke-width': 1.8,
            'stroke-linecap': 'round',
            'stroke-linejoin': 'round',
        },
        [
            ['path', { d: 'M18 4h1.5A2.5 2.5 0 0 1 22 6.5v11a2.5 2.5 0 0 1-2.5 2.5H18' }],
            ['path', { d: 'M14 4h1.5A2.5 2.5 0 0 1 18 6.5v11a2.5 2.5 0 0 1-2.5 2.5H14' }],
            ['rect', { x: 2, y: 4, width: 12, height: 16, rx: 2.5 }],
            ['circle', { cx: 5.9, cy: 8.1, r: 1.45, 'stroke-width': 1.3 }],
            ['path', { d: 'm3.5 17 3-3.4 2 2 1.6-1.7 2.4 3.1', 'stroke-width': 1.3 }],
        ],
    ];

}());
