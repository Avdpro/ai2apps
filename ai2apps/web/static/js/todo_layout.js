(function () {
    const workspace = document.getElementById('todo-workspace');
    const key = 'ai2apps.todo.column-widths.v1';
    const defaults = {left: 340, right: 420};
    let preferred = {...defaults};
    try {
        const saved = JSON.parse(localStorage.getItem(key));
        for (const side of ['left', 'right']) {
            if (Number.isFinite(saved?.[side])) preferred[side] = Math.max(240, Math.min(640, saved[side]));
        }
    } catch (_) {}
    const handles = {};
    let drag = null;
    const visible = side => !workspace.classList.contains(side + '-collapsed');
    function fit() {
        const style = getComputedStyle(workspace);
        const gap = parseFloat(style.columnGap) || 0;
        const width = workspace.clientWidth;
        const compact = width <= 960;
        const sides = ['left', 'right'].filter(visible);
        const available = width - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) - gap * sides.length - 320;
        const total = sides.reduce((sum, side) => sum + preferred[side], 0);
        const scale = total > available ? Math.max(0, available / total) : 1;
        for (const side of ['left', 'right']) {
            const value = compact ? preferred[side] : Math.floor(preferred[side] * scale);
            workspace.style.setProperty('--' + side, value + 'px');
            const handle = handles[side];
            handle.hidden = compact || !visible(side);
            handle.setAttribute('aria-valuenow', String(value));
            const panel = workspace.querySelector(side === 'left' ? '.todo-sidebar' : '.todo-detail');
            const root = workspace.getBoundingClientRect(), rect = panel.getBoundingClientRect();
            handle.style.left = ((side === 'left' ? rect.right + gap / 2 : rect.left - gap / 2) - root.left - 6) + 'px';
        }
    }
    function save() { try { localStorage.setItem(key, JSON.stringify(preferred)); } catch (_) {} }
    function finish(event) {
        if (!drag || event.pointerId !== drag.id) return;
        drag = null;
        workspace.classList.remove('resizing-columns');
        save();
    }
    for (const side of ['left', 'right']) {
        const handle = document.createElement('div');
        handle.className = 'todo-column-resizer';
        handle.tabIndex = 0;
        handle.setAttribute('role', 'separator');
        handle.setAttribute('aria-orientation', 'vertical');
        handle.setAttribute('aria-label', document.documentElement.lang.startsWith('zh') ? (side === 'left' ? '调整左侧栏宽度' : '调整右侧栏宽度') : `Resize ${side} sidebar`);
        handle.setAttribute('aria-valuemin', '240');
        handle.setAttribute('aria-valuemax', '640');
        workspace.append(handle);
        handles[side] = handle;
        handle.onpointerdown = event => {
            if (event.button !== 0) return;
            event.preventDefault();
            drag = {side, id: event.pointerId, x: event.clientX, width: parseFloat(getComputedStyle(workspace).getPropertyValue('--' + side))};
            handle.setPointerCapture(event.pointerId);
            workspace.classList.add('resizing-columns');
        };
        handle.onpointermove = event => {
            if (!drag || drag.id !== event.pointerId) return;
            preferred[side] = Math.max(240, Math.min(640, drag.width + (event.clientX - drag.x) * (side === 'left' ? 1 : -1)));
            fit();
        };
        handle.onpointerup = finish;
        handle.onpointercancel = finish;
        handle.onlostpointercapture = finish;
        handle.ondblclick = () => { preferred[side] = defaults[side]; fit(); save(); };
        handle.onkeydown = event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home'].includes(event.key)) return;
            event.preventDefault();
            preferred[side] = event.key === 'Home' ? defaults[side] : Math.max(240, Math.min(640, preferred[side] + (event.key === 'ArrowRight' ? 16 : -16) * (side === 'left' ? 1 : -1)));
            fit(); save();
        };
    }
    new ResizeObserver(fit).observe(workspace);
    new MutationObserver(fit).observe(workspace, {attributes: true, attributeFilter: ['class']});
    fit();
})();
