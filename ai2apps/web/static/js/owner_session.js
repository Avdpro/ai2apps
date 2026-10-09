/* Only rendered by a verified Owner Home response; status polling is not activity. */
(function () {
    'use strict';
    let stopped = false;
    const recoveryKey = 'ai2apps.owner.recovery-url';
    function trustedUrl(value) {
        try {
            const url = new URL(value);
            return url.origin === 'https://coder.ai2apps.com' &&
                /^\/u\/[0-9a-f-]{36}$/.test(url.pathname) &&
                url.search === '?entry=owner-home' && !url.hash && !url.username && !url.password ? url.href : null;
        } catch (_) { return null; }
    }
    // Only a navigation hint, never an authorization credential. Survives a reload
    // whose first status request fails after a suspended mobile tab resumes.
    let renewalUrl = null;
    try { renewalUrl = trustedUrl(sessionStorage.getItem(recoveryKey)); } catch (_) {}
    let lastActivity = 0;
    let leaseTimer;
    function lock() {
        if (stopped) return;
        stopped = true;
        clearInterval(poll);
        clearTimeout(leaseTimer);
        document.activeElement?.blur?.();
        document.querySelectorAll('iframe').forEach((frame) => {
            try { frame.contentDocument?.activeElement?.blur?.(); } catch (_) {}
            frame.remove();
        });
        const message = document.createElement('main');
        message.className = 'owner-recovery';
        const card = document.createElement('section');
        const logo = document.createElement('img');
        logo.src = '/mobile/static/favicon.svg';
        logo.alt = '';
        logo.className = 'owner-recovery-logo';
        const brand = document.createElement('small');
        brand.textContent = 'AI2APPS';
        const title = document.createElement('h1');
        title.textContent = '重新连接你的应用';
        const text = document.createElement('p');
        text.textContent = renewalUrl
            ? '连接已结束。返回账户页面后，即可重新进入你的应用。'
            : '连接暂时不可用。请重试连接，或重新扫描 Home 中的个人链接二维码。';
        title.tabIndex = -1;
        card.append(logo, brand, title, text);
        if (renewalUrl) {
            const link = document.createElement('a');
            link.href = renewalUrl;
            link.target = '_top';
            link.textContent = '重新进入我的应用';
            card.append(link);
        } else {
            const retry = document.createElement('button');
            retry.textContent = '重试连接';
            retry.addEventListener('click', () => window.top.location.href = '/mobile/member/complete');
            card.append(retry);
        }
        const footnote = document.createElement('span');
        footnote.className = 'owner-recovery-footnote';
        footnote.textContent = '你的应用和数据仍保存在 Mac 上';
        message.append(card, footnote);
        document.body.replaceChildren(message);
        title.focus?.({preventScroll:true});
    }
    async function status() {
        if (stopped) return;
        try {
            const response = await fetch('/v1/mobile/owner-home/status', {credentials:'same-origin', cache:'no-store'});
            if (!response.ok) return lock();
            const state = await response.json();
            if (state.ownerAuthorizationUrl) {
                const url = new URL(state.ownerAuthorizationUrl);
                if (trustedUrl(url.href)) {
                    renewalUrl = url.href;
                    try { sessionStorage.setItem(recoveryKey, renewalUrl); } catch (_) {}
                }
            }
            clearTimeout(leaseTimer);
            // A suspended tab may resume after the server has already renewed this lease.
            // Revalidate online; only the server can decide whether authority ended.
            leaseTimer = setTimeout(status, Math.max(1000,state.leaseExpiresAt*1000-Date.now()));
        } catch (_) { lock(); }
    }
    async function activity(event) {
        if (stopped || !event.isTrusted || document.visibilityState !== 'visible' || Date.now()-lastActivity < 30000) return;
        lastActivity = Date.now();
        try {
            const response = await fetch('/v1/mobile/owner-home/activity', {method:'POST', credentials:'same-origin'});
            if (!response.ok) lock();
        } catch (_) { lock(); }
    }
    document.addEventListener('pointerdown',activity,{passive:true});
    document.addEventListener('keydown',activity,{passive:true});
    document.querySelector('[data-owner-logout]')?.addEventListener('click',async () => {
        try { await fetch('/v1/mobile/owner-home/logout',{method:'POST',credentials:'same-origin'}); }
        finally { lock(); }
    });
    const poll = setInterval(status,15000);
    window.addEventListener('pageshow',status);
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') status();
    });
    status();
})();
