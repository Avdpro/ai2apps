(() => {
    'use strict';
    function startReader() {
        const data = JSON.parse(document.getElementById('pages').textContent);
        const pages = data.pages, zh = data.locale === 'zh';
        const viewport = document.getElementById('viewport'), surface = document.getElementById('surface');
        const previous = document.getElementById('previous'), next = document.getElementById('next');
        const toggle = button => button.classList.toggle('original');
        const clamp = (value, lo, hi) => Math.max(lo, Math.min(hi, value));
        let page = 0, scale = 1, x = 0, y = 0, fittedWidth = 0, fittedHeight = 0;
        let gesture = null, moved = false;
        const pointers = new Map();

        function position() {
            const w = viewport.clientWidth, h = viewport.clientHeight;
            const bound = (v, extent, full) => extent <= full ? (full - extent) / 2 : clamp(v, full - extent, 0);
            x = bound(x, fittedWidth * scale, w);
            y = bound(y, fittedHeight * scale, h);
            surface.style.transform = `translate(${x}px,${y}px) scale(${scale})`;
        }
        function fit() {
            const {width, height} = pages[page];
            const s = Math.min(viewport.clientWidth / width, viewport.clientHeight / height, 1);
            fittedWidth = Math.max(1, width * s);
            fittedHeight = Math.max(1, height * s);
            Object.assign(surface.style, {width: fittedWidth + 'px', height: fittedHeight + 'px'});
            scale = 1;
            x = y = 0;
            position();
        }
        function show(index) {
            page = clamp(index, 0, pages.length - 1);
            const current = pages[page];
            const art = document.createElement('img');
            art.src = current.output;
            art.alt = (zh ? '译文漫画第 ' : 'Translated comic page ') + (page + 1);
            art.draggable = false;
            surface.replaceChildren(art);
            for (const [index, [left, top, right, bottom]] of current.boxes.entries()) {
                const width = right - left, height = bottom - top;
                const box = document.createElement('button');
                box.type = 'button';
                box.className = 'bubble';
                box.setAttribute('aria-label', (zh ? '切换原文，气泡 ' : 'Toggle original, bubble ') + (index + 1));
                Object.assign(box.style, {left: left * 100 + '%', top: top * 100 + '%',
                    width: width * 100 + '%', height: height * 100 + '%'});
                const source = document.createElement('div');
                source.className = 'source';
                source.setAttribute('aria-hidden', 'true');
                source.style.backgroundImage = `url(${current.original})`;
                source.style.backgroundSize = `${100 / width}% ${100 / height}%`;
                source.style.backgroundPosition = `${left / (1 - width || 1) * 100}% ${top / (1 - height || 1) * 100}%`;
                box.append(source);
                box.addEventListener('click', event => {
                    if (event.detail === 0) toggle(box);
                });
                surface.append(box);
            }
            previous.disabled = page === 0;
            next.disabled = page === pages.length - 1;
            document.getElementById('count').textContent = `${page + 1} / ${pages.length}`;
            fit();
        }
        function zoom(targetScale, atX, atY) {
            const target = clamp(targetScale, 1, 8);
            x = atX - (atX - x) * target / scale;
            y = atY - (atY - y) * target / scale;
            scale = target;
            position();
        }
        function point(event) {
            const rect = viewport.getBoundingClientRect();
            return {x: event.clientX - rect.left, y: event.clientY - rect.top};
        }
        const difference = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
        function rebase() {
            const [a, b] = pointers.values();
            if (!a) { gesture = null; return; }
            const center = b ? {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2} : a;
            gesture = {x, y, center, scale, distance: b ? difference(a, b) : 0};
        }
        viewport.addEventListener('pointerdown', event => {
            if (event.button !== 0 || pointers.size >= 2) return;
            if (!pointers.size) moved = false;
            pointers.set(event.pointerId, {...point(event), bubble: event.target.closest('.bubble')});
            if (pointers.size === 2) moved = true;
            viewport.setPointerCapture(event.pointerId);
            rebase();
        });
        viewport.addEventListener('pointermove', event => {
            if (!pointers.has(event.pointerId) || !gesture) return;
            pointers.set(event.pointerId, {...pointers.get(event.pointerId), ...point(event)});
            const [a, b] = pointers.values();
            const center = b ? {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2} : a;
            if (difference(center, gesture.center) > 5) moved = true;
            if (!moved) return;
            const ratio = b && gesture.distance > 0 ? difference(a, b) / gesture.distance : 1;
            scale = clamp(gesture.scale * ratio, 1, 8);
            x = center.x - (gesture.center.x - gesture.x) * scale / gesture.scale;
            y = center.y - (gesture.center.y - gesture.y) * scale / gesture.scale;
            position();
        });
        function release(event) {
            const active = pointers.get(event.pointerId);
            if (!active) return;
            pointers.delete(event.pointerId);
            if (event.type === 'pointerup' && !moved && active.bubble) toggle(active.bubble);
            rebase();
        }
        viewport.addEventListener('pointerup', release);
        viewport.addEventListener('pointercancel', release);
        viewport.addEventListener('lostpointercapture', release);
        viewport.addEventListener('wheel', event => {
            event.preventDefault();
            if (event.ctrlKey || event.metaKey || (!event.shiftKey && Math.abs(event.deltaY) >= Math.abs(event.deltaX))) {
                const {x, y} = point(event);
                zoom(scale * Math.exp(-event.deltaY * (event.deltaMode === 1 ? .07 : .008)), x, y);
            } else if (scale > 1) {
                x -= event.shiftKey ? event.deltaY : event.deltaX;
                y -= event.shiftKey ? 0 : event.deltaY;
                position();
            }
        }, {passive: false});
        previous.onclick = () => show(page - 1);
        next.onclick = () => show(page + 1);
        document.getElementById('reset').onclick = fit;
        function zoomCenter(ratio) {
            zoom(scale * ratio, viewport.clientWidth / 2, viewport.clientHeight / 2);
        }
        document.getElementById('plus').onclick = () => zoomCenter(1.3);
        document.getElementById('minus').onclick = () => zoomCenter(1 / 1.3);
        window.addEventListener('keydown', event => {
            if (event.key === 'ArrowLeft') show(page - 1);
            else if (event.key === 'ArrowRight') show(page + 1);
            else if (event.key === '+' || event.key === '=') zoomCenter(1.3);
            else if (event.key === '-') zoomCenter(1 / 1.3);
            else return;
            event.preventDefault();
        });
        window.addEventListener('resize', fit);
        show(0);
    }
    function readerHtml(pages, locale = 'en') {
        const zh = locale === 'zh';
        const title = zh ? '漫画阅读器' : 'Comic reader';
        const payload = JSON.stringify({pages, locale}).replace(/[<>&\u2028\u2029]/g, char =>
            '\\u' + char.charCodeAt(0).toString(16).padStart(4, '0'));
        return `<!doctype html>
<html lang="${zh ? 'zh-CN' : 'en'}"><head><meta charset="utf-8">
<meta name="generator" content="ai2apps-comic-reader/v1">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'nonce-ai2apps-reader'; base-uri 'none'; form-action 'none'">
<title>${title}</title><style>
*{box-sizing:border-box}body{margin:0;height:100vh;height:100dvh;display:grid;grid-template-rows:auto minmax(0,1fr);color:#f5f5f5;background:#18181b;font:15px system-ui,sans-serif}
nav{display:flex;justify-content:center;align-items:center;flex-wrap:wrap;gap:6px;padding:8px}
nav button{font:inherit;background:#333;color:inherit;border:1px solid #555;border-radius:8px;padding:7px 10px;min-height:40px}
nav button:disabled{opacity:.4}#count{padding:0 5px;white-space:nowrap}#viewport{position:relative;overflow:hidden;touch-action:none;overscroll-behavior:none;cursor:grab}
#viewport:active{cursor:grabbing}#surface{position:absolute;transform-origin:0 0;user-select:none}#surface img{display:block;width:100%;height:100%;pointer-events:none}
.bubble{position:absolute;background:none;border:0;padding:0;overflow:hidden;cursor:pointer}.source{position:absolute;inset:0;display:none;background-repeat:no-repeat}
.bubble.original .source{display:block}.bubble:focus-visible{outline:2px solid #6951ff;outline-offset:1px}
@media(hover:hover){.bubble:hover .source{display:block}}
</style></head><body><nav aria-label="${title}">
<button id="previous">${zh ? '上一页' : 'Previous'}</button><output id="count" aria-live="polite"></output><button id="next">${zh ? '下一页' : 'Next'}</button>
<button id="minus" aria-label="${zh ? '缩小' : 'Zoom out'}">−</button><button id="plus" aria-label="${zh ? '放大' : 'Zoom in'}">+</button>
<button id="reset">${zh ? '适合窗口' : 'Fit'}</button></nav>
<main id="viewport"><div id="surface"></div></main><script type="application/json" id="pages">${payload}<\/script>
<script nonce="ai2apps-reader">(${startReader.toString()})();<\/script></body></html>`;
    }
    window.ComicReader = {readerHtml};
})();
