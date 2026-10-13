"""Search-result DOM reader shared by platform WebAgents, over native BiDi.

No search API credentials are needed. Provider-specific selectors are hints;
semantic heading links remain the fallback when presentation markup changes.
"""
SEARCH_RESULTS_SCRIPT = r'''function(provider, limit, query, excludeAds=true){
    const config={
        google:{host:/(^|\.)google\.[a-z.]+$/,paths:['/search'],links:'main h3,#search h3,#rso h3'},
        bing:{host:/(^|\.)bing\.com$/,paths:['/search'],links:'#b_results h2,li.b_algo h2'},
        duckduckgo:{host:/(^|\.)duckduckgo\.com$/,paths:['/','/html/','/lite/'],links:'[data-testid="result-title-a"],a.result__a,.result-link'},
        brave:{host:/^search\.brave\.com$/,paths:['/search'],links:'.snippet a.heading-serp,.snippet .title,a[data-type="web"] .title'}
    };
    const c=config[provider],expected=c?.host;
    if(provider==='google'&&expected?.test(location.hostname)&&/^\/sorry(?:\/|$)/.test(location.pathname))
        return {provider,items:[],page_url:location.href,page_title:document.title,
            classification:'needs_user',reason:'captcha',assistance_kind:'captcha'};
    if(!c||!expected.test(location.hostname)||!c.paths.includes(location.pathname))return {provider,items:[],reason:'unexpected_search_page'};
    const visible=ai2appsDOMVisible;
    const items=[],seen=new Set();
    const headings=[...document.querySelectorAll(c.links)];
    if(!headings.length)headings.push(...document.querySelectorAll('h2,h3'));
    for(const heading of headings){
        if(!visible(heading)||heading.closest('header,nav,footer,[role=navigation]'))continue;
        const is_ad=!!heading.closest('[data-text-ad],[data-ad],.b_ad,.result--ad,[data-type="ad"],[data-testid="ad"]');
        if(excludeAds&&is_ad)continue;
        const link=heading.closest('a[href]')||heading.querySelector('a[href]');
        if(!link)continue;
        let url;
        try{
            url=new URL(link.href,location.href);
            if(provider==='google'&&expected.test(url.hostname)&&url.pathname==='/url')url=new URL(url.searchParams.get('q')||url.searchParams.get('url'));
            if(provider==='bing'&&expected.test(url.hostname)&&url.pathname.startsWith('/ck/')){
                const encoded=url.searchParams.get('u')||'';
                if(encoded.startsWith('a1'))url=new URL(new TextDecoder().decode(Uint8Array.from(atob(encoded.slice(2).replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0))));
            }
            if(provider==='duckduckgo'&&expected.test(url.hostname)&&url.searchParams.get('uddg'))url=new URL(url.searchParams.get('uddg'));
        }catch(_){continue;}
        // Google may expose an opaque signed /goto redirect rather than a direct URL.
        // Keep the observed link; do not invent or decode an encrypted destination.
        const googleRedirect=provider==='google'&&expected.test(url.hostname)&&url.pathname==='/goto'&&!!url.searchParams.get('url');
        if(!['http:','https:'].includes(url.protocol)||url.username||url.password||(expected.test(url.hostname)&&!googleRedirect))continue;
        url.hash='';const href=url.href,title=(heading.innerText||heading.textContent||'').replace(/\s+/g,' ').trim();
        if(!title||seen.has(href))continue;
        seen.add(href);
        const root=heading.closest('li.b_algo,.MjjYud,[data-hveid],.result,[data-testid="result"],.snippet');
        const snippet=root?.querySelector('.VwiC3b,.b_caption p,[data-sncf],.result__snippet,[data-testid="result-snippet"],.snippet-description,.snippet-content,.description')||(provider==='brave'?link.nextElementSibling:null);
        items.push({title,url:href,is_ad,summary:(snippet?.innerText||'').replace(/\s+/g,' ').trim()});
        if(items.length>=limit)break;
    }
    const text=(document.body?.innerText||'').slice(0,12000);
    const captcha=/验证码|安全验证|verify you are human|captcha|confirm you are a human|select all squares containing a duck/i.test(text);
    const empty=/no results found|no results were found|did not match any results|no more results found|没有找到相关结果/i.test(text);
    return {query,provider,items,count:items.length,page_url:location.href,page_title:document.title,
        ...(items.length?{}:captcha?{classification:'needs_user',reason:'captcha',assistance_kind:'captcha'}:empty?{empty:true}:{reason:'no_valid_search_results'})};
}'''

SITE_SEARCH_RESULTS_SCRIPT = r'''function(provider, limit, query, excludeAds=true){
    const config={
        wikipedia:{host:/(^|\.)wikipedia\.org$/,links:'.mw-search-result-heading a[href],.mw-search-result a[href]',card:'.mw-search-result',text:'.searchresult',valid:u=>u.pathname.startsWith('/wiki/')&&!decodeURIComponent(u.pathname.slice(6)).includes(':')},
        x:{host:/^(www\.)?(x|twitter)\.com$/,links:'article a[href*="/status/"]',card:'article',text:'[data-testid="tweetText"]',valid:u=>/^\/[^/]+\/status\/\d+\/?$/.test(u.pathname)},
        weibo:{host:/(^|\.)weibo\.com$/,links:'.card-wrap .from a[href],a[href][date]',card:'.card-wrap',text:'.txt',valid:u=>/^\/\d+\/[a-zA-Z0-9]+\/?$/.test(u.pathname)},
        xiaohongshu:{host:/(^|\.)(?:xiaohongshu|rednote)\.com$/,links:'section.note-item a[href],.note-item a[href]',card:'.note-item',text:'.title',valid:u=>/^\/(explore|search_result)\/[a-zA-Z0-9]+\/?$/.test(u.pathname)},
        youtube:{host:/(^|\.)youtube\.com$/,links:'ytd-video-renderer a#video-title',card:'ytd-video-renderer',text:'#description-text',valid:u=>u.pathname==='/watch'&&!!u.searchParams.get('v')},
        bilibili:{host:/(^|\.)bilibili\.com$/,links:'.bili-video-card a[href*="/video/"],.video-item a[href*="/video/"]',card:'.bili-video-card,.video-item',text:'.bili-video-card__info--tit,.title',valid:u=>/^\/video\/(BV[a-zA-Z0-9]+|av\d+)\/?$/.test(u.pathname)}
    };
    const c=config[provider];
    if(!c||!c.host.test(location.hostname))return {provider,query,items:[],reason:'unexpected_search_page'};
    const visible=ai2appsDOMVisible;
    const items=[],seen=new Set();
    let links=[...document.querySelectorAll(c.links)];
    if(!links.length)links=[...document.querySelectorAll('main a[href],[role="main"] a[href],a[href]')];
    for(const a of links){
        if(!visible(a)||a.closest('header,nav,footer,[role="navigation"]'))continue;
        let u;try{u=new URL(a.href,location.href);}catch(_){continue;}
        if(u.protocol!=='https:'||u.username||u.password||!c.host.test(u.hostname))continue;
        try{if(!c.valid(u))continue;}catch(_){continue;}
        const card=a.closest(c.card),body=card?.querySelector(c.text);
        const content=body?.innerText||(provider==='x'?card?.innerText:'')||a.innerText||a.textContent||'';
        // Only consume a real search document, not a redirected home timeline.
        if(provider==='x'&&location.pathname!=='/search')continue;
        // Simple multiword queries match terms independently, not an exact phrase.
        // Let the site's own query parser handle operators/quoted advanced queries.
        if(provider==='x'&&query&&!/["():]/.test(query)){
            const terms=query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
            if(!terms.every(term=>String(content).toLocaleLowerCase().includes(term)))continue;
        }
        const is_ad=!!card?.querySelector('[data-testid="placementTracking"],.ad-label,.sponsored-label,[data-ad]')||
            /^(promoted|sponsored|广告|推广)$/i.test((card?.querySelector('[data-testid="adLabel"],.advertisement-label')?.innerText||'').trim());
        if(excludeAds&&is_ad)continue;
        const video=['youtube','bilibili'].includes(provider);
        let title=(provider==='bilibili'?(body?.innerText||a.getAttribute?.('title')||a.innerText||a.textContent):provider==='wikipedia'||video?(a.innerText||a.textContent||body?.innerText):content).replace(/\s+/g,' ').trim();
        if(!title)continue;
        u.hash='';let key=u.origin+u.pathname+(provider==='youtube'?'?v='+u.searchParams.get('v'):'');
        if(seen.has(key))continue;seen.add(key);
        const value=selector=>(card?.querySelector(selector)?.innerText||'').replace(/\s+/g,' ').trim()||null;
        const image=(video?card?.querySelector('ytd-thumbnail img,.bili-video-card__cover img,.bili-video-card__image img,.cover img,picture img'):null)||card?.querySelector('img');
        const imageRaw=image?.currentSrc||image?.getAttribute?.('data-src')||image?.getAttribute?.('data-original')||image?.src||'';
        let imageURL='';try{if(imageRaw)imageURL=new URL(imageRaw,location.href).href;}catch(_){}
        const metadata=card?[...card.querySelectorAll?.('#metadata-line span')||[]].map(n=>(n.innerText||'').trim()):[];
        items.push({title:title.slice(0,280),url:u.href,is_ad,summary:(body?.innerText||'').replace(/\s+/g,' ').trim().slice(0,1200),
            kind:video?'video':['x','weibo','xiaohongshu'].includes(provider)?'post':'web',
            content:video?'':String(content).slice(0,2400),
            image_url:imageURL,
            author:value('[data-testid="User-Name"],.author-wrapper .name,#channel-name,.bili-video-card__info--author'),
            published_at:card?.querySelector('time')?.getAttribute?.('datetime')||metadata[1]||null,
            duration:video?value('ytd-thumbnail-overlay-time-status-renderer,.bili-video-card__stats__duration,.duration'):null,
            view_count:video?(metadata[0]||value('.bili-video-card__stats--left .bili-video-card__stats--item')):null,
            like_count:value('[data-testid="like"],[data-testid="unlike"],.like-wrapper .count,.like-count'),
            repost_count:value('[data-testid="retweet"],[data-testid="unretweet"],.repost-count'),
            comment_count:value('[data-testid="reply"],.comment-count')});
        if(items.length>=limit)break;
    }
    const text=(document.body?.innerText||'').slice(0,12000);
    const login=/\/(login|signin|i\/flow\/login)(\/|$)/i.test(location.pathname)||[...document.querySelectorAll('[role="dialog"],.login-container,.login-modal')].some(n=>visible(n)&&/登录|登入|sign in|log in/i.test(n.innerText||''));
    // XHS can gate search without opening a login modal; placeholder text is
    // absent from body.innerText. Only treat this as blocking when no notes exist.
    const loginHint=provider==='xiaohongshu'&&!items.length&&[...document.querySelectorAll('input[placeholder]')].some(n=>visible(n)&&/登录探索|登入探索|登录后搜索|sign in to search|log in to explore/i.test(n.getAttribute?.('placeholder')||''));
    const captcha=/验证码|安全验证|verify you are human|captcha/i.test(text);
    const unavailable=/something went wrong|try reloading|rate limit|too many requests|出错了|请求过于频繁/i.test(text);
    const empty=/没有找到|暂无搜索结果|没有相关|no results|did not match|There were no results/i.test(text);
    return {provider,query,items,count:items.length,page_url:location.href,page_title:document.title,
        ...(!items.length?(captcha||login||loginHint?{classification:'needs_user',reason:captcha?'captcha':'authentication',assistance_kind:captcha?'captcha':'authentication'}:empty?{empty:true}:unavailable?{reason:'provider_unavailable'}:{reason:text.trim()?'search_markup_unavailable':'search_page_not_loaded'}):{})};
}'''


XHS_NOTE_TARGET_SCRIPT = r'''function(url){
    const expected=new URL(url);
    const id=expected.pathname.split('/').filter(Boolean).pop();
    const a=[...document.querySelectorAll('.note-item a[href]')].find(a=>{
        const observed=new URL(a.href);
        const r=a.getBoundingClientRect();
        return ai2appsDOMVisible(a)&&observed.origin===expected.origin&&observed.pathname.split('/').filter(Boolean).pop()===id;
    });
    if(!a)return null;
    a.scrollIntoView({block:'center',behavior:'instant'});
    const r=a.getBoundingClientRect();
    const image=a.closest?.('.note-item')?.querySelector('.cover img,img');
    const ir=image?.complete&&image.naturalWidth&&ai2appsDOMVisible(image)?image.getBoundingClientRect():null;
    const cover=ir&&ir.width>0&&ir.height>0?{x:Math.max(0,ir.x),y:Math.max(0,ir.y),width:Math.min(ir.right,innerWidth)-Math.max(0,ir.x),height:Math.min(ir.bottom,innerHeight)-Math.max(0,ir.y)}:null;
    return r.width&&r.height?{rect:r.toJSON(),url:a.href,cover_rect:cover}:null;
}'''

XHS_NOTE_DETAIL_SCRIPT = r'''function(url){
    const expected=new URL(url).pathname.split('/').filter(Boolean).pop();
    const current=location.pathname.split('/').filter(Boolean).pop();
    if(current!==expected)return {ready:false};
    const root=[...document.querySelectorAll('#noteContainer,.note-container')].find(ai2appsDOMVisible);
    const body=[...root?.querySelectorAll('#detail-desc,.note-content .desc,.note-text .desc')||[]].find(ai2appsDOMVisible);
    const text=body?.innerText?.trim()||'';
    if(!root||!text)return {ready:false};
    const value=s=>root.querySelector(s)?.innerText?.trim()||null;
    return {ready:true,content:text.slice(0,2400),
      author:value('.author-container .username,.author .username'),
      published_at:value('.note-content .date,.note-text .date'),
      like_count:value('.interact-container .like-wrapper .count'),
      collect_count:value('.interact-container .collect-wrapper .count'),
      comment_count:value('.interact-container .chat-wrapper .count')};
}'''


XHS_SORT_STATE_SCRIPT = r'''function(order){
    if(!/(^|\.)(?:xiaohongshu|rednote)\.com$/.test(location.hostname)||location.pathname!='/search_result')return {invalid:true};
    const label={latest:'最新',general:'综合',likes:'最多点赞'}[order];
    const visible=ai2appsDOMVisible;
    const nodes=[...document.querySelectorAll('button,[role="tab"],[role="option"],span,div,a')].filter(n=>visible(n)&&n.children.length===0);
    const heading=nodes.find(n=>(n.innerText||'').trim()==='排序依据');
    let group=heading?.parentElement;
    for(let i=0;group&&i<3&&!/最新/.test(group.innerText||'');i++)group=group.parentElement;
    const option=group?nodes.find(n=>group.contains(n)&&(n.innerText||'').trim()===label):null;
    const selected=n=>{for(let p=n,i=0;p&&i<3;i++,p=p.parentElement){if((p.innerText||'').trim()===label&&(p.getAttribute('aria-selected')==='true'||p.getAttribute('aria-checked')==='true'||/(^|[\s_-])(active|selected|checked)([\s_-]|$)/i.test(p.className||'')))return true;}return false;};
    const filter=nodes.find(n=>['筛选','已筛选','排序'].includes((n.innerText||'').trim()));
    const target=n=>n?{rect:n.getBoundingClientRect().toJSON()}:null;
    const selectedOptions=group?nodes.filter(n=>group.contains(n)&&selected(n)):[];
    return {verified:!!option&&selected(option),option:target(option),filter:target(filter),selected_order:selectedOptions.length?label:null};
}'''


X_SEARCH_SORT_SCRIPT = r'''function(order, query){
    if(!/^(www\.)?(x|twitter)\.com$/.test(location.hostname)||location.pathname!='/search'||new URL(location.href).searchParams.get('q')!==query)return {invalid:true};
    const target=[...document.querySelectorAll('[role="tab"]')].filter(ai2appsDOMVisible).find(n=>{
        const a=n.matches('a')?n:n.querySelector('a[href]');
        const text=(n.innerText||'').trim().toLowerCase();
        const f=a?new URL(a.href,location.href).searchParams.get('f'):null;
        return order==='latest'?f==='live'||['latest','最新'].includes(text):f==='top'||['top','热门'].includes(text);
    });
    if(!target)return {};
    const rect=target.getBoundingClientRect();
    if(!rect.width||!rect.height)return {};
    return {verified:target.getAttribute('aria-selected')==='true',option:{rect:rect.toJSON()}};
}'''

VIDEO_COVER_TARGET_SCRIPT = r'''function(url){
    const link=[...document.querySelectorAll('ytd-video-renderer a#video-title,.bili-video-card a[href*="/video/"],.video-item a[href*="/video/"]')].find(a=>{
        try{const x=new URL(a.href),y=new URL(url);return x.origin===y.origin&&x.pathname===y.pathname&&x.searchParams.get('v')===y.searchParams.get('v');}catch(_){return false;}
    });
    const card=link?.closest('ytd-video-renderer,.bili-video-card,.video-item');
    const image=card?.querySelector('ytd-thumbnail img,.bili-video-card__cover img,.bili-video-card__image img,.cover img,picture img,img');
    if(!image||!ai2appsDOMVisible(image))return null;
    const r=image.getBoundingClientRect();
    if(r.top<0||r.bottom>innerHeight)return {scroll:r.top-(innerHeight-r.height)/2};
    if(!image.complete||!image.naturalWidth)return null;
    return {rect:{x:Math.max(0,r.x),y:Math.max(0,r.y),width:Math.min(r.right,innerWidth)-Math.max(0,r.x),height:Math.min(r.bottom,innerHeight)-Math.max(0,r.y)}};
}'''

XHS_LOGIN_STATE_SCRIPT = r'''function(){
    if(!/^(www\.)?(xiaohongshu|rednote)\.com$/.test(location.hostname))return {state:'unknown'};
    const visible=ai2appsDOMVisible;
    const controls=[...document.querySelectorAll('aside a,nav a,.side-bar a,.sidebar a,.user a,a.user,.user.side-bar-component')].filter(visible);
    const own=controls.some(a=>/\/(user\/profile|profile)\//.test(a.getAttribute('href')||'')&&/^(我|我的|个人主页|Me|Profile|My profile)$/i.test((a.innerText||'').trim()));
    if(own)return {state:'logged_in'};
    const gate=[...document.querySelectorAll('.login-container,.login-modal,[role="dialog"],button,.login-btn,.login-button')].some(n=>visible(n)&&/^(登录|登入|登录探索更多内容|Log in|Sign in|Login)$|登录探索更多内容|sign in to explore|log in to explore/i.test((n.innerText||'').trim()));
    return {state:gate?'logged_out':'unknown'};
}'''
