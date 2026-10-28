/* Delegated hints also cover controls added by streamed messages and interactions. */
(function (root) {
    'use strict';
    function labelFor(control) {
        return (control.getAttribute('title') || control.getAttribute('aria-label') || control.innerText || '').trim();
    }
    function install(shell) {
        if (!shell || shell.dataset.buttonHintsInstalled) return;
        shell.dataset.buttonHintsInstalled = 'true';
        const tip = document.createElement('div');
        tip.className = 'chat-button-hint';
        tip.id = 'chat-button-hint';
        tip.setAttribute('role', 'tooltip');
        tip.hidden = true;
        document.body.appendChild(tip);
        let active = null, nativeTitle = null, describedBy = null;
        function hide() {
            if (active) {
                if (nativeTitle !== null && !active.hasAttribute('title')) active.setAttribute('title', nativeTitle);
                if (describedBy === null) active.removeAttribute('aria-describedby');
                else active.setAttribute('aria-describedby', describedBy);
            }
            active = null;
            tip.hidden = true;
        }
        function show(event) {
            const control = event.target.closest?.('button, select, [role="button"]');
            if (!control || !shell.contains(control) || control === active) return;
            hide();
            // Existing state-specific hints remain the source of truth.
            const existing = control.closest('.chat-hover-tip');
            if (existing?.getAttribute('data-tooltip') || control.hasAttribute('data-chat-tip')) return;
            const label = labelFor(control);
            if (!label) return;
            active = control;
            nativeTitle = control.getAttribute('title');
            describedBy = control.getAttribute('aria-describedby');
            control.removeAttribute('title');
            control.setAttribute('aria-describedby', [describedBy, tip.id].filter(Boolean).join(' '));
            tip.textContent = label;
            tip.hidden = false;
            const rect = control.getBoundingClientRect();
            const box = tip.getBoundingClientRect();
            tip.style.left = Math.max(8, Math.min(innerWidth - box.width - 8, rect.left + (rect.width - box.width) / 2)) + 'px';
            tip.style.top = (rect.top > box.height + 16 ? rect.top - box.height - 8 : rect.bottom + 8) + 'px';
        }
        shell.addEventListener('mouseover', show);
        shell.addEventListener('focusin', show);
        shell.addEventListener('mouseout', event => {
            if (active && !active.contains(event.relatedTarget)) hide();
        });
        shell.addEventListener('focusout', hide);
        shell.addEventListener('click', hide);
        shell.addEventListener('keydown', event => { if (event.key === 'Escape') hide(); });
        document.addEventListener('scroll', hide, true);
        root.addEventListener('resize', hide);
    }
    if (typeof module !== 'undefined') module.exports = {labelFor};
    root.AI2AppsChatButtonHints = {install};
})(typeof window !== 'undefined' ? window : globalThis);
