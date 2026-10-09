(function () {
    'use strict';
    function node(tag, text, cls) {
        const el = document.createElement(tag);
        if (text) el.textContent = text;
        if (cls) el.className = cls;
        return el;
    }
    function render(root, space, options = {}) {
        root.replaceChildren();
        root.className = 'visitor-page theme-' + (['violet','ocean','sand'].includes(space.theme) ? space.theme : 'violet');
        const hero = node('header', '', 'visitor-hero');
        hero.append(node('span', 'AI2APPS · 访客空间', 'visitor-eyebrow'), node('h1', space.title), node('p', space.description));
        root.append(hero);
        const cards = node('section', '', 'visitor-cards');
        const visibleCards=(space.cards || []).filter(card=>!card.hidden);
        for (const card of visibleCards) {
            const item = node('article', '', 'visitor-card');
            item.append(node('span', {text:'笔记',link:'链接',app:'应用'}[card.kind], 'visitor-eyebrow'), node('h2',card.title), node('p',card.text));
            if (card.kind === 'link') {
                const link = node('a','打开链接','visitor-button');
                try { const url = new URL(card.url); if (url.protocol === 'https:' && !url.username && !url.password) link.href=url.href; } catch (_) {}
                link.target='_blank';link.rel='noopener noreferrer';
                if (options.preview) link.addEventListener('click',event=>event.preventDefault());
                item.append(link);
            }
            if (card.kind === 'app') {
                const button=node('button',options.preview?'应用预览卡片':'打开应用','visitor-button');
                button.disabled=!!options.preview;
                button.addEventListener('click',()=>options.open?.(card));item.append(button);
            }
            cards.append(item);
        }
        if (!visibleCards.length) cards.append(node('p','这里还没有添加内容。','visitor-empty'));
        root.append(cards,node('footer','由 AI2Apps 提供访问连接 · 内容由空间主人发布'));
    }
    window.renderVisitorSpace=render;
    if (!document.querySelector('[data-visitor-public]')) return;
    const root=document.getElementById('visitor-root'),status=document.getElementById('status');
    const fragment=new URLSearchParams(location.hash.slice(1));
    const handoff=fragment.get('handoff');history.replaceState(null,'',location.pathname);
    const recovery=document.getElementById('space-recovery');
    let recoveryUrl=null;
    function setRecovery(value){
        try{
            const url=new URL(value);
            if(url.origin!=='https://coder.ai2apps.com' || !/^\/u\/[0-9a-f-]{36}$/.test(url.pathname) || url.search || url.hash || url.username || url.password) return;
            recoveryUrl=url.href;recovery.href=recoveryUrl;
            try{sessionStorage.setItem('ai2apps.visitor.url',recoveryUrl);}catch(_){}
        }catch(_){}
    }
    let revision=null,timer,expiry,stopped=false,initializing=true,refreshing=false,lastReading=0,leaseDeadline=0,sessionDeadline=0,sessionProtocol=null;
    function stop(){
        stopped=true;clearTimeout(timer);clearTimeout(expiry);root.replaceChildren();
        document.getElementById('visitor-player').replaceChildren();
        status.textContent=recoveryUrl?'空间已关闭或访问已结束，请重新进入。':'连接未能完成，请重新扫描空间主人的个人链接二维码。';recovery.hidden=!recoveryUrl;
    }
    async function request(path,body){
        const r=await fetch(path,{method:body?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
        if(!r.ok){const error=new Error('unavailable');error.status=r.status;throw error;}return r.json();
    }
    async function refresh(){
        if(stopped||refreshing)return;
        refreshing=true;clearTimeout(timer);
        try{
            const reading=sessionProtocol==='personal-space-anonymous-session-v1' && document.visibilityState==='visible' && Date.now()-lastReading>=60000;
            const state=await request('/v1/mobile/space/bootstrap',reading?{}:undefined);
            if(reading)lastReading=Date.now();
            if(stopped)return;
            setRecovery(state.userUrl);
            status.textContent='';sessionProtocol=state.sessionProtocol;leaseDeadline=state.expiresAt*1000;sessionDeadline=Math.min(state.absoluteExpiresAt||state.expiresAt,state.idleExpiresAt||state.expiresAt)*1000;root.hidden=false;document.getElementById('visitor-player').hidden=false;clearTimeout(expiry);expiry=setTimeout(refresh,Math.max(1000,leaseDeadline-Date.now()));
            if(revision!==state.revision){
                document.getElementById('visitor-player').replaceChildren();revision=state.revision;
                render(root,state.space,{open:card=>{
                    const player=document.getElementById('visitor-player');player.replaceChildren();
                    const close=node('button','返回空间','visitor-button');close.onclick=()=>player.replaceChildren();
                    const frame=node('iframe');frame.title=card.title||'访客应用';frame.setAttribute('sandbox','allow-scripts');
                    frame.src='/mobile/space/app/'+revision+'/'+encodeURIComponent(card.appKey)+'/'+card.binding.entry.split('/').map(encodeURIComponent).join('/');
                    player.append(close,frame);player.scrollIntoView({behavior:'smooth'});
                }});
            }
            history.replaceState(null,'','/mobile/space/home');timer=setTimeout(refresh,10000);
        }catch(error){
            if((error.status>=400&&error.status<500&&error.status!==429)||(sessionDeadline&&Date.now()>=sessionDeadline)){stop();}
            else{status.textContent='连接恢复中…';if(Date.now()>=leaseDeadline){root.hidden=true;document.getElementById('visitor-player').hidden=true;}timer=setTimeout(refresh,10000);}
        }finally{refreshing=false;}
    }
    try{setRecovery(sessionStorage.getItem('ai2apps.visitor.url'));}catch(_){}
    window.addEventListener('pageshow',()=>{if(!stopped&&!initializing)refresh();});
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&!stopped&&!initializing){clearTimeout(timer);refresh();}});
    (async()=>{try{if(handoff)await request('/v1/mobile/space/exchange',{handoff,...(document.querySelector('[data-visitor-session]')?{protocol:'personal-space-anonymous-session-v1'}:document.querySelector('[data-anonymous]')?{protocol:'personal-space-anonymous-v1'}:{})});initializing=false;await refresh();}catch(_){initializing=false;stop();}})();
})();
