function xPostSnapshot(rule = null) {
    if (!['x.com','www.x.com'].includes(location.hostname)) throw Error('x_origin_required');
    const visible = n => !!n?.getBoundingClientRect().height;
    const query = (root, selector) => { try { return [...root.querySelectorAll(selector)]; } catch (_) { return []; } };
    const status = a => a?.pathname?.match(/^\/([A-Za-z0-9_]+)\/status\/(\d+)/);
    const permalink = root => query(root,'a[href]').find(a => status(a) && a.querySelector('time'));
    const semanticRoots = new Set();
    for (const a of query(document,'a[href]').filter(a => status(a) && a.querySelector('time'))) {
        let root = a.closest('article,[role="article"]');
        if (!root) {
            root = a.parentElement;
            for (let depth=0; depth<7 && root?.parentElement; depth++) {
                const parent=root.parentElement;
                const ids=new Set(query(parent,'a[href]').filter(a=>a.querySelector('time')).map(a=>status(a)?.[2]).filter(Boolean));
                if (ids.size>1 || parent.innerText?.length>20000) break;
                root=parent;
            }
        }
        if (root && visible(root)) semanticRoots.add(root);
    }
    const roots = rule ? query(document,rule.card).filter(visible) : [...semanticRoots];
    const items=[], seen=new Set(); let invalid=0;
    for (const card of roots) {
        const anchor=rule ? query(card,rule.link).find(a=>status(a) && a.querySelector('time')) : permalink(card);
        const match=status(anchor);
        if (!match || seen.has(match[2])) { invalid++; continue; }
        const textNode=rule ? query(card,rule.text).find(visible) : card.querySelector('[data-testid="tweetText"]') ||
            (query(card,'p,[lang]').filter(visible).length ? query(card,'p,[lang]') : query(card,'[dir="auto"]'))
                .filter(n=>visible(n) && !n.matches('[data-testid="User-Name"]') && !n.querySelector('time') && n.innerText?.trim())
                .sort((a,b)=>b.innerText.length-a.innerText.length)[0];
        const text=textNode?.innerText?.trim() || '';
        if (!text) { invalid++; continue; }
        seen.add(match[2]);
        const author=(rule ? query(card,rule.author)[0] : card.querySelector('[data-testid="User-Name"]'))?.innerText || match[1];
        const images=query(card,rule ? rule.photo : 'img').map(i=>({url:i.src,alt:i.alt||''})).filter(i=>i.url?.startsWith('https://pbs.twimg.com/media/')).slice(0,8);
        items.push({url:'https://x.com/'+match[1]+'/status/'+match[2],title:text.slice(0,160),text:text.slice(0,16000),author,published_at:anchor.querySelector('time')?.dateTime||'',post_id:match[2],images});
    }
    const expected=new Set([...semanticRoots].map(r=>status(permalink(r))?.[2]).filter(Boolean));
    const matched=[...expected].filter(id=>seen.has(id)).length;
    const valid=!!rule && items.length>0 && invalid<=Math.max(1,roots.length*.2) && (!expected.size || matched/expected.size>=.8);
    if (rule && !valid) { const fallback=xPostSnapshot(); return {...fallback,x_rule_valid:false}; }
    const observed={card:[],link:[],text:[],author:[],photo:[]};
    if (!rule) {
        const selector=n=>{
            for (const attr of ['data-testid','role','lang']) {
                if(n.hasAttribute(attr)) return n.localName+'['+attr+'="'+CSS.escape(n.getAttribute(attr))+'"]';
            }
            if(n.classList.length) return n.localName+'.'+[...n.classList].slice(0,2).map(CSS.escape).join('.');
            return n.localName;
        };
        const add=(field,sel,n)=>{
            if(sel.length>300 || observed[field].some(v=>v.selector===sel) || observed[field].length>=20)return;
            observed[field].push({selector:sel,sample:(n.innerText||n.alt||'').slice(0,1200),count:query(field==='card'?document:[...semanticRoots][0]||document,sel).length});
        };
        for(const root of semanticRoots) {
            add('card',selector(root),root);
            for(const n of query(root,'a[href]')) if(status(n) && n.querySelector('time'))add('link',selector(n),n);
            for(const n of query(root,'p,[lang],[dir="auto"],[data-testid]')) {
                if(!visible(n))continue;
                if(n.innerText?.trim() && !n.querySelector('time'))add('text',selector(n),n);
                if(n.innerText?.trim() && (n.querySelector('a[href]') || n.matches('[data-testid="User-Name"]')))add('author',selector(n),n);
            }
            for(const n of query(root,'img'))if(n.src?.startsWith('https://pbs.twimg.com/media/'))add('photo',selector(n),n);
        }
        // Optional fields may fall back to the permalink handle and absent photos.
        if(!observed.author.length)observed.author.push({selector:'a[href]',sample:'Permalink author handle fallback',count:1});
        if(!observed.photo.length)observed.photo.push({selector:'img',sample:'No post photo on observed cards',count:0});
    }
    return {url:location.href,items,x_rule_valid:valid,x_observed:rule?null:observed};
}
