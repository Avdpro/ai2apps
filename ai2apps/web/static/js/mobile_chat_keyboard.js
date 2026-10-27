/* Shell-owned, transient layout only; never changes an App's dock preference. */
(() => {
    'use strict';
    const shell = document.getElementById('ai2apps-mobile');
    if (!shell) return;
    const viewport = window.visualViewport;
    let restingHeight = viewport?.height || window.innerHeight;
    let keyboardSeen = false;
    let dismissed = false;
    const chatInput = () => {
        const input = document.activeElement;
        return input?.matches('[data-mobile-chat-input]') && shell.contains(input) &&
            !input.closest('[hidden]') && input.getClientRects().length ? input : null;
    };
    function render() {
        shell.classList.toggle('mobile-chat-composing', !!chatInput() && !document.hidden && !dismissed);
    }
    document.addEventListener('focusin', event => {
        if (event.target.matches?.('[data-mobile-chat-input]')) {
            dismissed = false;
            keyboardSeen = false;
        }
        render();
    });
    document.addEventListener('focusout', () => {
        // Wait for the next focus target, including taps on composer controls.
        queueMicrotask(render);
    });
    function resized() {
        const height = viewport?.height || window.innerHeight;
        if (!chatInput()) {
            restingHeight = Math.max(restingHeight, height);
            keyboardSeen = false;
        } else if (restingHeight - height > 120) {
            keyboardSeen = true;
            dismissed = false;
        } else if (keyboardSeen && restingHeight - height < 60) {
            // iOS can dismiss its keyboard without blurring the textarea.
            dismissed = true;
            keyboardSeen = false;
        }
        render();
    }
    viewport?.addEventListener('resize', resized);
    window.addEventListener('resize', resized);
    window.addEventListener('orientationchange', () => {
        restingHeight = viewport?.height || window.innerHeight;
        keyboardSeen = false;
        render();
    });
    document.addEventListener('visibilitychange', render);
    // Switching Apps hides the inline Chat without necessarily blurring it.
    new MutationObserver(render).observe(shell, {subtree:true, attributes:true, attributeFilter:['hidden']});
    render();
})();
