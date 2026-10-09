"""Search-result DOM reader shared by platform WebAgents, over native BiDi.

No search API credentials are needed. Provider-specific selectors are hints;
semantic heading links remain the fallback when presentation markup changes.
"""
SEARCH_RESULTS_SCRIPT = r'''function(provider, limit, query){
    const expected=provider==='google'?/(^|\.)google\.[a-z.]+$/:/(^|\.)bing\.com$/;
    if(!expected.test(location.hostname)||location.pathname!=='/search')return {items:[],reason:'unexpected_search_page'};
    const visible=n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden';};
    const items=[],seen=new Set();
    const headings=[...document.querySelectorAll('main h3,#search h3,#rso h3,#b_results h2,li.b_algo h2,[role=main] h2,[role=main] h3')];
    if(!headings.length)headings.push(...document.querySelectorAll('h2,h3'));
    for(const heading of headings){
        if(!visible(heading)||heading.closest('header,nav,footer,[role=navigation],[data-text-ad],[data-ad],.b_ad'))continue;
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
        }catch(_){continue;}
        if(!['http:','https:'].includes(url.protocol)||url.username||url.password||expected.test(url.hostname))continue;
        url.hash='';const href=url.href,title=(heading.innerText||heading.textContent||'').replace(/\s+/g,' ').trim();
        if(!title||seen.has(href))continue;
        seen.add(href);
        const root=heading.closest('li.b_algo,.MjjYud,[data-hveid]');
        const snippet=root?.querySelector('.VwiC3b,.b_caption p,[data-sncf]');
        items.push({title,url:href,summary:(snippet?.innerText||'').replace(/\s+/g,' ').trim()});
        if(items.length>=limit)break;
    }
    return {query,provider,items,count:items.length,page_url:location.href,page_title:document.title,
        ...(items.length?{}:{reason:'no_valid_search_results'})};
}'''
