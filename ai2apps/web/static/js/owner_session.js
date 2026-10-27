/* Only rendered by a verified Owner Home response; status polling is not activity. */
(function () {
    'use strict';
    let stopped = false, checking = false, signingOut = false;
    const mobileShell = document.getElementById?.("ai2apps-mobile");
    let suspendedNotice = null;
    function suspendMobile() {
        if (suspendedNotice) return;
        mobileShell.inert = true; document.body.dataset.ownerSessionPaused = 'true';
        const notice = document.createElement("main");
        notice.className = "owner-recovery";
        notice.style.cssText = "position:fixed;inset:0;z-index:10000;overflow:auto";
        const card = document.createElement("section"), title = document.createElement("h1"), text = document.createElement("p");
        title.textContent = "连接需要恢复";
        text.textContent = "已保留当前页面。恢复登录后继续，不会重新提交任务。";
        card.append(title, text);
        if (resumeUrl || renewalUrl) {
            const link = document.createElement("a");
            link.href = resumeUrl || renewalUrl; link.target = "_top"; link.textContent = "恢复连接";
            card.append(link);
        }
        notice.append(card); document.body.append(notice); suspendedNotice = notice;
    }
    const resumeKey='ai2apps.owner.resume-url', attemptKey='ai2apps.owner.resume-at';
    function trustedResume(value){
        try {
            const url=new URL(value),q=url.searchParams;
            return url.origin==='https://coder.ai2apps.com' && /^\/u\/[0-9a-f-]{36}$/.test(url.pathname) && !url.username && !url.password && !url.hash &&
                [...q].length===3 && q.get('entry')==='owner-home' && q.get('resume')==='1' && q.get('device_origin')===location.origin ? url.href:null;
        } catch(_){return null;}
    }
    let resumeUrl=null;
    try {resumeUrl=trustedResume(sessionStorage.getItem(resumeKey));}catch(_){}
    function resume(){
        if(signingOut||!resumeUrl||document.visibilityState!=='visible')return false;
        try {
            const previous=Number(sessionStorage.getItem(attemptKey)||0);
            if(previous&&Date.now()-previous<300000)return false;
            sessionStorage.setItem(attemptKey,String(Date.now()));
            window.top.location.replace(resumeUrl);return true;
        } catch(_){return false;}
    }
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
    function lock(reason = 401) {
        if (stopped) return;
        // Mobile keeps its live frame tree on expiry. Do not replace it with
        // Home merely because the foreground lease probe returned 401.
        if (reason === 401 && mobileShell && !signingOut) { suspendMobile(); return; }
        suspendedNotice?.remove(); suspendedNotice = null; delete document.body.dataset.ownerSessionPaused;
        stopped = true;
        if(reason===0)document.body.dataset.ownerSessionEnded='logout';
        clearInterval(poll);
        clearTimeout(leaseTimer);
        if(reason===401&&resume())return;
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
        title.textContent = reason===403?'当前访问被拒绝':'重新连接你的应用';
        const text = document.createElement('p');
        text.textContent = renewalUrl
            ? '设备访问会话需要恢复。返回账户页面验证登录后，即可继续；这不一定表示账户登录已过期。'
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
        if (stopped||checking||document.visibilityState==='hidden') return;
        checking=true;
        const controller=new AbortController();
        const timeout=setTimeout(()=>controller.abort(),10000);
        try {
            const response = await fetch('/v1/mobile/owner-home/status', {credentials:'same-origin', cache:'no-store',signal:controller.signal});
            if (response.status===401||response.status===403) return lock(response.status);
            if (!response.ok) return; // Offline/5xx/429 is not loss of login authority.

            const state = await response.json();
            if (suspendedNotice) {
                const current = trustedUrl(state.ownerAuthorizationUrl);
                if (!current || current !== renewalUrl) return lock(403);
                suspendedNotice.remove(); suspendedNotice = null; mobileShell.inert = false; delete document.body.dataset.ownerSessionPaused;
            }
            if (state.ownerAuthorizationUrl) {
                const url = new URL(state.ownerAuthorizationUrl);
                if (trustedUrl(url.href)) {
                    renewalUrl = url.href;
                    try { sessionStorage.setItem(recoveryKey, renewalUrl); } catch (_) {}
                }
            }
            resumeUrl=signingOut?null:trustedResume(state.ownerResumeUrl);
            try {if(resumeUrl)sessionStorage.setItem(resumeKey,resumeUrl);else sessionStorage.removeItem(resumeKey);}catch(_){}
            clearTimeout(leaseTimer);
            // A suspended tab may resume after the server has already renewed this lease.
            // Revalidate online; only the server can decide whether authority ended.
            leaseTimer = setTimeout(status, Math.max(1000,state.leaseExpiresAt*1000-Date.now()));
        } catch (_) { /* Keep the document and retry the read-only probe. */ }
        finally {clearTimeout(timeout);checking=false;}
    }
    async function activity(event) {
        if (stopped || !event.isTrusted || document.visibilityState !== 'visible' || Date.now()-lastActivity < 30000) return;
        lastActivity = Date.now();
        try {
            const response = await fetch('/v1/mobile/owner-home/activity', {method:'POST', credentials:'same-origin'});
            if (response.status===401||response.status===403) lock(response.status);
        } catch (_) { /* Connectivity is retried by status polling. */ }
    }
    document.addEventListener('pointerdown',activity,{passive:true});
    document.addEventListener('keydown',activity,{passive:true});
    document.querySelector('[data-owner-logout]')?.addEventListener('click',async () => {
        signingOut=true;document.body.dataset.ownerSessionEnded='logout';
        resumeUrl=null;try {sessionStorage.removeItem(resumeKey);}catch(_){}
        // Failed delivery is not a successful logout. Keep the cookie so a
        // failed durable write can be retried without losing the session proof.
        const button=document.querySelector('[data-owner-logout]');
        if(button)button.disabled=true;
        try {
            const response=await fetch('/v1/mobile/owner-home/logout',{method:'POST',credentials:'same-origin'});
            if(!response.ok)throw new Error('logout');
            lock(0);
        } catch (_) {
            if(button){button.title='退出未完成，请重试 / Sign out failed. Please retry.';button.textContent='重试退出 / Retry sign out';}
        } finally {if(button)button.disabled=false;}
    });
    const poll = setInterval(status,15000);
    window.addEventListener('pageshow',status);
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') status();
    });
    status();
})();
