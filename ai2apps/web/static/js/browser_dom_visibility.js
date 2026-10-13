// Shared DOM visibility policy for BiDi SDK readers and native input targets.
// A rendered box does not establish visibility: hidden duplicate controls may
// retain size, text and stale selected classes. Follow composed ancestors too.
function ai2appsDOMVisible(element, {requireBox = true, viewport = false} = {}) {
    if (!element) return false;
    let opacity = 1;
    for (let node = element; node; node = node.parentElement || node.getRootNode?.()?.host) {
        const style = getComputedStyle(node);
        if (node.hidden || node.inert || node.getAttribute?.('aria-hidden') === 'true' ||
            style.display === 'none' || style.visibility === 'hidden' ||
            style.visibility === 'collapse' || style.contentVisibility === 'hidden') return false;
        const alpha = Number(style.opacity === '' || style.opacity == null ? 1 : style.opacity);
        if (Number.isFinite(alpha)) opacity *= alpha;
        if (opacity < 0.05) return false;
    }
    if (!requireBox) return true;
    const rect = element.getBoundingClientRect();
    if (!(rect.width > 0 && rect.height > 0)) return false;
    return !viewport || (rect.right > 0 && rect.bottom > 0 && rect.left < innerWidth && rect.top < innerHeight);
}
