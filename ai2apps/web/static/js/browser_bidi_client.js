(() => {
    'use strict';

    // The AceFox Sidebar owns the active-tab binding. Hash changes are useful
    // for the first Mini-Entry load, but do not reinitialize an already loaded
    // document, so translate the shell message into one shared DOM event for
    // Knowledge, Agent, Gallery, and future browser-aware Mini-Entries.
    window.addEventListener('message', event => {
        const payload = event.data;
        if (payload?.type !== 'ai2apps:browser-context') return;
        const context = payload.context;
        if (!context || typeof context !== 'object' || !String(context.bidi_context || '')) return;
        window.dispatchEvent(new CustomEvent('ai2apps:browser-context', {
            detail: {
                bidi_context: String(context.bidi_context || ''),
                url: String(context.url || ''),
                title: String(context.title || context.url || ''),
            },
        }));
    });

    class AI2AppsBiDiConnection {
        constructor() {
            this.socket = null;
            this.nextId = 1;
            this.pending = new Map();
            this.ownsSession = false;
        }
        async connect() {
            if (this.socket?.readyState === WebSocket.OPEN) return this;
            // Retry transport/session setup once with a new one-use ticket.
            // Never replay an already submitted browser action.
            for (let attempt = 0; attempt < 2; attempt++) {
                try {
                    return await this.connectOnce();
                } catch (error) {
                    await this.close();
                    if (attempt === 1 || error.authorizationDenied) throw error;
                    await new Promise(resolve => setTimeout(resolve, 1000));
                }
            }
        }
        async connectOnce() {
            const ticketResponse = await fetch('/v1/platform/browser/webdriver-bidi/ticket', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'},
                body: '{}',
            });
            if (!ticketResponse.ok) {
                const error = new Error('AceFox BiDi authorization is unavailable');
                error.authorizationDenied = [401, 403].includes(ticketResponse.status);
                throw error;
            }
            const {ticket} = await ticketResponse.json();
            const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
            this.socket = new WebSocket(
                `${scheme}//${location.host}/v1/platform/browser/webdriver-bidi?ticket=${encodeURIComponent(ticket)}`
            );
            const socket = this.socket;
            this.socket.addEventListener('message', event => {
                if (this.socket !== socket) return;
                let payload;
                try { payload = JSON.parse(event.data); } catch (_) { return; }
                const pending = this.pending.get(payload.id);
                if (!pending) return;
                this.pending.delete(payload.id);
                clearTimeout(pending.timer);
                if (payload.error) pending.reject(new Error(`${payload.error}: ${payload.message || ''}`));
                else pending.resolve(payload.result || {});
            });
            this.socket.addEventListener('close', () => {
                if (this.socket !== socket) return;
                for (const pending of this.pending.values()) {
                    clearTimeout(pending.timer);
                    pending.reject(new Error('AceFox BiDi is disconnected'));
                }
                this.pending.clear();
            });
            await new Promise((resolve, reject) => {
                const timer = setTimeout(() => reject(new Error('AceFox BiDi connection timed out')), 7000);
                this.socket.addEventListener('open', () => { clearTimeout(timer); resolve(); }, {once: true});
                this.socket.addEventListener('error', () => {
                    clearTimeout(timer);
                    reject(new Error('AceFox BiDi Gateway is unavailable'));
                }, {once: true});
                this.socket.addEventListener('close', () => {
                    clearTimeout(timer);
                    reject(new Error('AceFox BiDi Gateway is unavailable'));
                }, {once: true});
            });
            let status = await this.command('session.status', {});
            for (let attempt = 0; status.ready !== true && attempt < 48; attempt++) {
                await new Promise(resolve => setTimeout(resolve, 250));
                status = await this.command('session.status', {});
            }
            if (status.ready !== true) {
                this.socket.close();
                this.socket = null;
                throw new Error('AceFox BiDi is not ready');
            }
            await this.command('session.new', {capabilities: {alwaysMatch: {webSocketUrl: true}}});
            this.ownsSession = true;
            return this;
        }
        command(method, params, timeoutMs = 15000) {
            if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
                return Promise.reject(new Error('AceFox BiDi is disconnected'));
            }
            const id = this.nextId++;
            return new Promise((resolve, reject) => {
                const timer = setTimeout(() => {
                    this.pending.delete(id);
                    reject(new Error(`AceFox BiDi command timed out: ${method}`));
                }, timeoutMs);
                this.pending.set(id, {resolve, reject, timer});
                this.socket.send(JSON.stringify({id, method, params}));
            });
        }
        async close() {
            if (this.socket?.readyState === WebSocket.OPEN && this.ownsSession) {
                try {
                    await this.command('session.end', {}, 2000);
                } catch (_) {
                    // Closing the transport remains the fail-safe when upstream ended first.
                }
            }
            this.ownsSession = false;
            this.socket?.close();
            this.socket = null;
            for (const pending of this.pending.values()) {
                clearTimeout(pending.timer);
                pending.reject(new Error('AceFox BiDi is disconnected'));
            }
            this.pending.clear();
        }
    }

    class AI2AppsPageClient {
        constructor(boundContext) {
            this.boundContext = {...boundContext};
            this.connection = new AI2AppsBiDiConnection();
            this.contextId = '';
            this.createdContexts = new Map();
        }
        async connect() {
            await this.connection.connect();
            this.contextId = await this.resolveContext();
            return this;
        }
        async resolveContext() {
            const tree = await this.connection.command('browsingContext.getTree', {maxDepth: 1});
            const contexts = Array.isArray(tree.contexts) ? tree.contexts : [];
            const requested = String(this.boundContext.bidi_context || '');
            const expectedUrl = String(this.boundContext.url || '');
            const normalizeURL = value => {
                try {
                    const parsed = new URL(String(value || ''));
                    parsed.hash = '';
                    if (parsed.pathname.length > 1) parsed.pathname = parsed.pathname.replace(/\/+$/, '');
                    return parsed.href;
                } catch (_) { return String(value || ''); }
            };
            const expected = normalizeURL(expectedUrl);
            const requestedContext = contexts.find(item => item.context === requested);
            // An authorized Tab keeps its identity across navigation and login redirects.
            // Never rebind it to another Tab merely because an old URL matches.
            if (requestedContext) return requested;
            if (requested) throw new Error('The bound browser Tab is closed or unavailable');
            const matches = contexts.filter(item => normalizeURL(item.url) === expected);
            if (matches.length === 1) return matches[0].context;
            const expectedTitle = String(this.boundContext.title || '');
            const titleMatches = matches.filter(item => String(item.title || '') === expectedTitle);
            if (titleMatches.length === 1) return titleMatches[0].context;
            throw new Error('The current browser page changed; refresh the Sidebar context');
        }
        async callJSON(fn, args = [], timeoutMs = 15000) {
            const serializedArgs = JSON.stringify(args).replace(/</g, '\\u003c');
            const declaration = `async function(){const fn=(${fn});const value=await fn(...${serializedArgs});return JSON.stringify(value);}`;
            const result = await this.connection.command('script.callFunction', {
                functionDeclaration: declaration,
                target: {context: this.contextId},
                awaitPromise: true,
            }, timeoutMs);
            if (result.type === 'exception') {
                throw new Error(result.exceptionDetails?.text || 'Page script failed');
            }
            const value = result.result?.value;
            if (typeof value !== 'string') throw new Error('AceFox returned invalid page data');
            return JSON.parse(value);
        }
        async snapshot({maxItems = 150, maxText = 20000, maxHtml = 60000} = {}) {
            if (!this.snapshotSource) {
                const response = await fetch('/admin/static/js/browser_snapshot.js?v=upload-controls-2');
                if (!response.ok) throw new Error('Cannot load shared browser snapshot helper');
                this.snapshotSource = await response.text();
            }
            return this.callJSON(this.snapshotSource, [{maxItems, maxText, maxHtml, htmlMode:'visible'}], 30000);
        }
        async pageState() {
            const snapshot = await this.snapshot();
            return {...snapshot, text_length:snapshot.text.length, text_sample:snapshot.text,
                fingerprint:[snapshot.url,snapshot.items.length,snapshot.text.length,snapshot.html.length].join('|')};
        }
        async explorationObservation() {
            const snapshot = await this.pageState();
            const controls = snapshot.items.map(item => ({...item, name:item.text}));
            return {...snapshot, controls, control_count:controls.length,
                link_count:controls.filter(item => item.tag === 'a').length,
                button_count:controls.filter(item => item.tag === 'button' || item.role === 'button').length};
        }
        async relatedWindowObservations() {
            const tree = await this.connection.command('browsingContext.getTree', {maxDepth:0});
            const related = new Set([this.contextId]);
            for(const [child,parent] of this.createdContexts || []) if(parent===this.contextId) related.add(child);
            let changed = true;
            while (changed) {
                changed = false;
                for (const item of tree.contexts || []) {
                    if (related.has(item.originalOpener) && !related.has(item.context)) {
                        related.add(item.context); changed = true;
                    }
                }
            }
            const windows = [];
            for (const item of (tree.contexts || []).filter(item => item.context !== this.contextId && related.has(item.context)).slice(0,4)) {
                // Independent facade avoids changing the bound page during asynchronous reads.
                const reader = Object.assign(Object.create(Object.getPrototypeOf(this)), this, {contextId:item.context});
                try {
                    const observation = await reader.explorationObservation();
                    windows.push({context:item.context, originalOpener:item.originalOpener,
                        url:observation.url, title:observation.title, fingerprint:observation.fingerprint,
                        text_sample:observation.text_sample, controls:observation.controls,
                        html:observation.html, file_inputs:observation.file_inputs, control_count:observation.control_count});
                } catch (_) { windows.push({context:item.context, originalOpener:item.originalOpener,
                    url:item.url, error:'window_not_ready'}); }
            }
            return windows;
        }
        async waitForStability(timeoutMs=10000, {requireContent=false}={}) {
            const end=Date.now()+Math.min(30000,Math.max(500,Number(timeoutMs)||10000));
            let previous=null, consecutive=0;
            while(Date.now()<end){
                const page=await this.pageState();
                if(page.fingerprint===previous) consecutive++; else consecutive=0;
                const hasContent = Boolean(page.text_length || String(page.text || '').trim() || (page.items || []).length);
                if(consecutive>=2 && (!requireContent || hasContent)) return {stable:true,page};
                previous=page.fingerprint;
                await new Promise(resolve=>setTimeout(resolve,500));
            }
            return {stable:false,page:await this.pageState()};
        }
        async waitState(target, present=true, timeoutMs=10000) {
            const end=Date.now()+Math.min(30000,Math.max(500,Number(timeoutMs)||10000));
            while(Date.now()<end){
                const found=await this.findTarget(String(target));
                if(Boolean(found)===present) return {ready:true,present:Boolean(found),context:this.contextId,url:(await this.pageState()).url};
                await new Promise(resolve=>setTimeout(resolve,500));
            }
            return {ready:false,reason:'state_timeout',context:this.contextId};
        }
        async readPage(options={}) {
            if(['finish','close'].includes(options.phase)){
                const opened=options.opened||{};
                if(opened.context!==this.contextId) throw Error('read_context_mismatch');
                const temporary=opened.temporary===true;
                if(temporary&&this.createdContexts?.get(this.contextId)!==opened.original_context)
                    throw Error('untracked_read_context');
                const context=this.contextId, original=opened.original_context;
                const close=temporary&&(options.phase==='close'||options.close_tab!==false);
                try{
                    if(options.phase==='close') return {outcome:'success',tab_closed:close};
                    const currentURL=new URL((await this.pageState()).url);
                    if(!/^https?:$/.test(currentURL.protocol)||currentURL.username||currentURL.password||/^(localhost|127\.|0\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.|\[)/i.test(currentURL.hostname)||/\.local$/i.test(currentURL.hostname))
                        throw Error('public_http_url_required');
                    const page=await this.extractRenderedPage({maxChars:options.max_chars});
                    if(!page.text.trim()) return {outcome:'failed',reason:'empty_page',url:page.url};
                    return {...page,outcome:'success',context:close?original:context,read_context:context,tab_closed:close};
                }finally{
                    if(close){
                        try{await this.connection.command('browsingContext.close',{context});}
                        finally{this.createdContexts.delete(context);this.contextId=original;await this.connection.command('browsingContext.activate',{context:original});}
                    }
                }
            }
            const requirePublicURL=value=>{const url=new URL(value);
            if(!/^https?:$/.test(url.protocol)||url.username||url.password||/^(localhost|127\.|0\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.|\[)/i.test(url.hostname)||/\.local$/i.test(url.hostname))
                throw Error('public_http_url_required');
            return url;};
            const url=requirePublicURL(options.url);
            const original=this.contextId;let temporary=null, retained=false;
            try {
                if(options.new_tab!==false){
                    temporary=(await this.connection.command('browsingContext.create',{type:'tab',referenceContext:original,background:false})).context;
                    this.contextId=temporary;
                    this.createdContexts ||= new Map();this.createdContexts.set(temporary,original);
                }
                await this.connection.command('browsingContext.navigate',{context:this.contextId,url:url.href,wait:'complete'},30000);
                await new Promise(resolve=>setTimeout(resolve,Math.min(10000,Math.max(0,Number(options.delay_ms)||0))));
                if(options.youtube==='video')await this.callJSON(`function(){document.querySelectorAll('video').forEach(v=>v.pause());return true;}`);
                const stability=await this.waitForStability();
                if(!stability.stable) return {outcome:'failed',reason:'page_unstable',url:stability.page.url};
                requirePublicURL(stability.page.url);
                if(options.phase==='open'){
                    retained=Boolean(temporary);
                    return {outcome:'success',context:this.contextId,original_context:original,temporary:Boolean(temporary),url:stability.page.url};
                }
                const access=await this.handlePageAccess();
                if(['needs_user','restricted'].includes(access.classification)){
                    retained=Boolean(temporary&&access.classification==='needs_user');
                    return {outcome:access.classification,reason:access.reason,url:stability.page.url,context:this.contextId,tab_closed:Boolean(temporary&&!retained)};
                }
                let page;
                if(options.youtube==='feed'){
                    // SPA skeletons can be stable before their video cards arrive.
                    for(let attempt=0;attempt<4;attempt++){
                        page=await this.extractYouTubeFeed();
                        if(page.items.length)break;
                        if(attempt<3)await new Promise(resolve=>setTimeout(resolve,2500));
                    }
                    if(!page.items.length)return {outcome:'failed',reason:'未识别到 YouTube 视频列表，请检查频道地址或页面结构',url:page.url};
                }
                else if(options.youtube==='video')page=await this.extractYouTubeVideo();
                else if(options.site_extraction){
                    try{page=await this.executeExtractionStep({mode:'compiled',operation:'read_page',arguments:{site_extraction:options.site_extraction}});}
                    catch(_){page={...await this.extractRenderedPage({maxChars:options.max_chars}),extraction_fallback:true};}
                }else page=await this.extractRenderedPage({maxChars:options.max_chars});
                if(!options.youtube&&(options.include_cover||options.include_images)){try{page.cover_image=await this.extractLeadImage();if(options.include_images)page.images=page.cover_image.images||[];}catch(_){page.cover_image={url:'',method:'unavailable'};page.images=[];}}
                requirePublicURL(page.url);
                if(!page.text.trim()) return {outcome:'failed',reason:'empty_page',url:page.url};
                retained=Boolean(temporary&&options.close_tab===false);
                return {...page,outcome:'success',context:retained?this.contextId:original,read_context:this.contextId,tab_closed:Boolean(temporary&&!retained)};
            } finally {
                this.contextId=original;
                if(temporary&&!retained){try{await this.connection.command('browsingContext.close',{context:temporary});}finally{this.createdContexts?.delete(temporary);}}
                if(temporary&&!retained) await this.connection.command('browsingContext.activate',{context:original});
            }
        }
        async submitSocialSearch(query) {
            const target=await this.callJSON(`function(){
                if(location.hostname!=='s.weibo.com')throw Error('weibo_search_origin_required');
                const input=[...document.querySelectorAll('input:not([type=password]):not([type=hidden])')].filter(n=>{
                    const r=n.getBoundingClientRect(),style=getComputedStyle(n);return r.width>40&&r.height>10&&style.visibility==='visible'&&style.display!=='none'&&document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)===n;
                }).pop();
                if(!input)throw Error('未找到微博搜索输入框');const r=input.getBoundingClientRect();return {rect:{x:r.x,y:r.y,width:r.width,height:r.height}};
            }`);
            await this.naturalPointer(target);await this.typeText(query,{replace:true});
            const typed=await this.callJSON(`function(){return document.activeElement?.value||'';}`);
            if(typed!==query)throw Error('微博搜索框输入与目标话题不一致，已停止');
            const button=await this.callJSON(`function(){
                const n=[...document.querySelectorAll('button,a,[role=button]')].find(n=>n.innerText?.trim()==='搜索'&&n.getBoundingClientRect().width>0);
                if(!n)throw Error('未找到微博搜索按钮');const r=n.getBoundingClientRect();return {rect:{x:r.x,y:r.y,width:r.width,height:r.height}};
            }`);
            await this.naturalPointer(button);
            for(let attempt=0;attempt<12;attempt++){
                await new Promise(r=>setTimeout(r,700));const u=new URL((await this.pageState()).url);
                if(u.hostname==='s.weibo.com'&&u.pathname==='/weibo'&&u.searchParams.get('q')===query){await this.waitForStability();return;}
            }
            throw Error('微博搜索提交后未进入目标话题，已保留页面供检查');
        }
        async clickSocialPost(url) {
            const origin={context:this.contextId,url:(await this.pageState()).url};
            const before=new Set((await this.connection.command('browsingContext.getTree',{maxDepth:0})).contexts.map(c=>c.context));
            let target;
            for(let attempt=0;attempt<8;attempt++){
                target=await this.callJSON(`function(url){
                    if(!['weibo.com','www.weibo.com','s.weibo.com'].includes(location.hostname))throw Error('weibo_origin_required');
                    const wanted=new URL(url),links=[...document.querySelectorAll('a[href]')];
                    const n=links.find(a=>{try{const u=new URL(a.href);return ['weibo.com','www.weibo.com'].includes(u.hostname)&&u.pathname===wanted.pathname&&a.getBoundingClientRect().height>0;}catch(_){return false;}});
                    if(!n)throw Error('微博正文链接已离开列表，停止本轮');const r=n.getBoundingClientRect();
                    const inside=r.top>=90&&r.bottom<innerHeight-30;
                    const x=Math.max(1,Math.min(innerWidth-2,r.x+r.width/2)),y=r.y+r.height/2;
                    const hit=inside?document.elementFromPoint(x,y):null;
                    return {rect:{x:r.x,y:r.y,width:r.width,height:r.height},ready:inside&&(hit===n||n.contains(hit)),delta:r.top<90?-500:500};
                }`,[url]);
                if(target.ready)break;await this.scroll(target.delta);await new Promise(r=>setTimeout(r,900));
            }
            if(!target?.ready)throw Error('微博正文链接不可见或被遮挡，未执行点击');
            await this.naturalPointer(target);
            for(let attempt=0;attempt<12;attempt++){
                await new Promise(r=>setTimeout(r,500));
                const tree=(await this.connection.command('browsingContext.getTree',{maxDepth:0})).contexts;
                const wanted=new URL(url),matches=tree.filter(c=>{try{const u=new URL(c.url);return (c.context===origin.context||!before.has(c.context))&&['weibo.com','www.weibo.com'].includes(u.hostname)&&u.pathname===wanted.pathname;}catch(_){return false;}});
                if(matches.length>1)throw Error('微博点击产生多个匹配页面，已停止');
                if(matches.length===1){this.contextId=matches[0].context;origin.child=this.contextId!==origin.context?this.contextId:null;await this.connection.command('browsingContext.activate',{context:this.contextId});await new Promise(r=>setTimeout(r,1800));return origin;}
            }
            throw Error('点击微博后未到达目标正文，未改用直接 URL 访问');
        }
        async returnFromSocialPost(origin) {
            if(origin.child)await this.connection.command('browsingContext.close',{context:origin.child});
            else await this.connection.command('browsingContext.traverseHistory',{context:origin.context,delta:-1});
            this.contextId=origin.context;await this.connection.command('browsingContext.activate',{context:origin.context});
            await new Promise(r=>setTimeout(r,1200));
            if((await this.pageState()).url!==origin.url)throw Error('未返回原微博列表，停止后续采集');
        }
        async extractWeiboPosts() {
            return this.callJSON(`function(){
                if(!['weibo.com','www.weibo.com','s.weibo.com'].includes(location.hostname))throw Error('weibo_origin_required');
                const uid=location.hostname==='s.weibo.com'?null:location.pathname.match(/^\\/(?:u\\/)?([0-9]+)\\/?$/)?.[1];
                const seen=new Set(),items=[];
                for(const a of document.querySelectorAll('a[href]')){
                    let u;try{u=new URL(a.href);}catch(_){continue;}
                    if(!['weibo.com','www.weibo.com'].includes(u.hostname))continue;
                    const m=u.pathname.match(/^\\/([0-9]{5,20})\\/([A-Za-z0-9]{6,20})$/);
                    if(!m||seen.has(m[2])||(uid&&m[1]!==uid))continue;
                    const card=a.closest('article,.card-wrap,[mid]');if(!card)continue;
                    const body=card.querySelector('[node-type=feed_list_content_full]')||card.querySelector('[node-type=feed_list_content],.txt,[class*=wbtext]');
                    const text=(body?.innerText||'').trim();if(!text||/广告/.test(card.querySelector('.feed_ad')?.innerText||''))continue;
                    seen.add(m[2]);items.push({url:'https://weibo.com/'+m[1]+'/'+m[2],title:text.slice(0,160),text:text.slice(0,1500)});if(items.length>=30)break;
                }
                return {url:location.href,title:document.title,items};
            }`);
        }
        async extractWeiboDetail(url) {
            return this.callJSON(`function(url){
                const wanted=new URL(url),current=new URL(location.href);
                if(!['weibo.com','www.weibo.com'].includes(current.hostname)||current.pathname!==wanted.pathname)throw Error('微博正文地址不匹配');
                const card=document.querySelector('article')||document.querySelector('.card-wrap[mid]');
                if(!card)throw Error('未找到独立微博正文，拒绝采集整页');
                const body=card.querySelector('[node-type=feed_list_content_full]')||card.querySelector('[node-type=feed_list_content],.txt,[class*=wbtext]');
                const content=(body?.innerText||'').trim();if(!content)throw Error('微博正文尚未加载');
                const author=(card.querySelector('a[href*="/u/"],[class*=head_name],.name')?.innerText||'').trim();
                const date=[...card.querySelectorAll('a[href]')].find(a=>{try{return new URL(a.href).pathname===wanted.pathname;}catch(_){return false;}});
                const images=[],seen=new Set();for(const img of card.querySelectorAll('img')){
                    const src=img.currentSrc||img.src;let u;try{u=new URL(src,location.href);}catch(_){continue;}
                    if(/^(?:tvax|tva|tvaxww)\\d*\\.sinaimg\\.cn$/.test(u.hostname)||img.closest('[class*=avatar],[class*=Avatar],[class*=head]')||u.protocol!=='https:'||img.naturalWidth<160||img.naturalHeight<100||/avatar|profile|emoji|icon/i.test(u.pathname)||seen.has(u.href))continue;
                    seen.add(u.href);images.push({url:u.href,alt:(img.alt||'').slice(0,300)});if(images.length>=12)break;
                }
                for(const video of card.querySelectorAll('video[poster]')){
                    let poster;try{poster=new URL(video.poster,location.href);}catch(_){continue;}
                    if(poster.protocol==='https:'&&!seen.has(poster.href)){seen.add(poster.href);images.push({url:poster.href,alt:'微博视频封面（未转录视频）'});}
                }
                const title=(author?author+'：':'')+content.slice(0,120),published=date?.getAttribute('title')||date?.innerText||'';
                return {url:'https://weibo.com'+wanted.pathname,title,text:'微博作者：'+author+'\\n页面时间：'+published+'\\n资料范围：仅网页可见微博正文（可能截断），不包含评论或视频转录。\\n'+content.slice(0,16000),platform:'weibo',post_id:wanted.pathname.split('/').pop(),author:author.slice(0,200),published_at:published.slice(0,100),images,cover_image:{url:images[0]?.url||''}};
            }`,[url]);
        }
        async extractYouTubeFeed() {
            return this.callJSON(`function(){
                if(!['www.youtube.com','youtube.com','m.youtube.com'].includes(location.hostname))throw Error('youtube_origin_required');
                const root=document.querySelector('ytd-page-manager')||document.querySelector('main')||document.body;
                const seen=new Set(),items=[];
                for(const a of root.querySelectorAll('a#video-title-link,a#video-title,h3 a[href*="watch?v="],a.yt-lockup-metadata-view-model__title,a[href^="/shorts/"]')){
                    const u=new URL(a.href,location.href),id=u.pathname==='/watch'?u.searchParams.get('v'):u.pathname.startsWith('/shorts/')?u.pathname.split('/')[2]:null;
                    if(!id||!(/^[A-Za-z0-9_-]{11}$/).test(id)||seen.has(id))continue;
                    const card=a.closest('ytd-rich-item-renderer,ytd-grid-video-renderer,ytd-video-renderer,yt-lockup-view-model,ytm-shorts-lockup-view-model')||a;
                    if(card.closest('ytd-ad-slot-renderer,ytd-promoted-video-renderer'))continue;
                    const title=(a.getAttribute('title')||a.getAttribute('aria-label')||a.innerText||card.innerText||'').trim().slice(0,500);
                    if(!title)continue;seen.add(id);items.push({url:'https://www.youtube.com/watch?v='+id,title,text:(card.innerText||title).slice(0,1500)});
                    if(items.length>=30)break;
                }
                return {url:location.href,title:document.title,text:items.map(i=>i.title).join('\\n'),items,extraction_method:'youtube-dom-feed-v1'};
            }`);
        }
        async extractYouTubeVideo() {
            // Only ordinary, visible page controls; no private endpoints or credential extraction.
            const control=async kind=>this.callJSON(`function(kind){
                const root=document.querySelector('ytd-watch-metadata');if(!root)return null;
                const nodes=kind==='expand'?[...root.querySelectorAll('#description-inline-expander #expand,#description #expand')]:[...root.querySelectorAll('button,[role=button]')].filter(n=>/^(show transcript|显示转录文稿|显示文字记录|显示文字稿|顯示轉錄稿)$/i.test((n.innerText||n.getAttribute('aria-label')||'').trim()));
                const node=nodes.find(n=>!n.disabled);if(!node)return null;
                node.scrollIntoView({block:'center'});const r=node.getBoundingClientRect();
                if(r.width<2||r.height<2)return null;
                return {rect:{x:r.x,y:r.y,width:r.width,height:r.height}};
            }`,[kind]);
            for(const kind of ['expand','transcript']){
                const target=await control(kind);if(target){await this.naturalPointer(target);await new Promise(r=>setTimeout(r,1500));}
            }
            return this.callJSON(`function(){
                if(!['www.youtube.com','youtube.com','m.youtube.com'].includes(location.hostname))throw Error('youtube_origin_required');
                const id=new URL(location.href).searchParams.get('v');if(!id||!(/^[A-Za-z0-9_-]{11}$/).test(id))throw Error('youtube_video_id_missing');
                const root=document.querySelector('ytd-watch-metadata');
                const title=(root?.querySelector('h1')?.innerText||document.querySelector('meta[name="title"]')?.content||'').trim();
                const author=(document.querySelector('ytd-video-owner-renderer #channel-name')?.innerText||document.querySelector('link[itemprop="name"]')?.getAttribute('content')||'').trim();
                const description=(root?.querySelector('#description-inline-expander')?.innerText||root?.querySelector('#description')?.innerText||document.querySelector('meta[name="description"]')?.content||'').trim().slice(0,7000);
                const published=document.querySelector('meta[itemprop="datePublished"]')?.content||document.querySelector('meta[itemprop="uploadDate"]')?.content||'';
                const segments=[...document.querySelectorAll('ytd-transcript-segment-renderer')].filter(n=>n.getBoundingClientRect().height>0).map(n=>(n.innerText||'').trim());
                const transcript=segments.join('\\n').slice(0,12000),coverage=transcript?'transcript':'description';
                const unavailable=document.querySelector('#error-screen')?.innerText||'';
                if(unavailable.trim())throw Error('视频不可读取：'+unavailable.slice(0,200));
                if(!title)throw Error('未找到视频标题，请检查页面或登录状态');
                const text=['YouTube 视频：'+title,'作者：'+author,'页面发布日期：'+published,'资料范围：'+(transcript?'网页文字稿（可能不完整）':'仅标题与简介，未读取视频内容'),'简介：'+description,transcript?'文字稿：'+transcript:''].filter(Boolean).join('\\n\\n');
                const image=document.querySelector('meta[property="og:image"]')?.content||'';
                return {url:'https://www.youtube.com/watch?v='+id,title,text,platform:'youtube',post_id:id,author:author.slice(0,200),published_at:published,coverage,cover_image:{url:image,method:'metadata'},images:image?[{url:image,alt:title.slice(0,300)}]:[],extraction_method:'youtube-dom-video-v1'};
            }`);
        }
        async extractLeadImage() {
            return this.callJSON(`function(){
                const safe=value=>{try{const u=new URL(value,location.href),h=u.hostname.toLowerCase();
                    if(!value||!/^https?:$/.test(u.protocol)||u.username||u.password||
                       !h.includes('.')||/^(localhost|127\\.|0\\.|10\\.|192\\.168\\.|169\\.254\\.|172\\.(1[6-9]|2[0-9]|3[01])\\.|\\[)/.test(h)||
                       /\\.(local|internal|localhost)$/.test(h)||u.port&&!['80','443'].includes(u.port))return '';
                    return u.href.length<=4096?u.href:'';}catch(_){return '';}};
                const usable=image=>{const u=safe(image);return u&&!/(?:logo|favicon|sprite|placeholder|tracking|pixel)(?:[._/-]|$)/i.test(new URL(u).pathname)?u:'';};
                let lead=null;
                for(const selector of ['meta[property="og:image:secure_url"]','meta[property="og:image"]','meta[name="twitter:image"]','meta[property="twitter:image"]','meta[name="twitter:image:src"]']){
                    for(const meta of document.querySelectorAll(selector)){const url=usable(meta.content);if(url&&!lead)lead={url,method:'metadata'};}
                }
                const root=document.querySelector('article')||document.querySelector('main,[role=main],#content')||document.body;
                const images=[...root.querySelectorAll('img')].filter(img=>!img.closest('nav,footer,aside,[role=dialog],.related-posts,.related-articles,.advertisement,[class*=social-share]')).map((img,index)=>{
                    const r=img.getBoundingClientRect(),s=getComputedStyle(img);
                    if(s.display==='none'||s.visibility==='hidden')return null;
                    const w=Math.max(img.naturalWidth||0,Number(img.getAttribute('width'))||0,r.width),h=Math.max(img.naturalHeight||0,Number(img.getAttribute('height'))||0,r.height);
                    if(w<320||h<180||w/h>3.5||h/w>3)return null;
                    const url=usable(img.getAttribute('data-original'))||usable(img.getAttribute('data-src'))||usable(img.getAttribute('data-lazy-src'))||usable(img.currentSrc)||usable(img.getAttribute('src'));
                    return url?{url,alt:(img.getAttribute('alt')||'').slice(0,300),index,score:Math.min(w*h,1500000)/(1+index*.25)}:null;
                }).filter(Boolean).sort((a,b)=>b.score-a.score);
                lead ||= images.length?{url:images[0].url,method:'article-image'}:{url:'',method:'none'};
                const seen=new Set(),gallery=[];
                for(const item of [...(lead.url?[{url:lead.url,alt:document.title||''}]:[]),...images.sort((a,b)=>a.index-b.index)]){
                    if(seen.has(item.url))continue;seen.add(item.url);gallery.push({url:item.url,alt:item.alt});if(gallery.length>=24)break;
                }
                return {...lead,images:gallery};
            }`);
        }
        async observeExtractionRegions(kind, referenceURLs=[]) {
            return this.callJSON(`function(kind,referenceURLs){
                const references=new Set(referenceURLs);
                const visible=n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return r.width>2&&r.height>2&&s.visibility!=='hidden'&&s.display!=='none';};
                const selector=n=>{if(n.id&&!/\\d{5}/.test(n.id))return '#'+CSS.escape(n.id);
                    const classes=[...n.classList].filter(c=>!/(active|hover|selected|\\d{5})/.test(c)).slice(0,2);
                    return classes.length?n.tagName.toLowerCase()+classes.map(c=>'.'+CSS.escape(c)).join(''):n.tagName.toLowerCase();};
                const seen=new Set(),regions=[];
                for(const n of document.querySelectorAll('main,article,section,div,ul')){
                    if(!visible(n)||n.closest('nav,header,footer,aside,[role=dialog]'))continue;
                    const css=selector(n);if(!css||seen.has(css)||document.querySelectorAll(css).length!==1)continue;
                    const links=[...n.querySelectorAll('a[href]')].filter(a=>visible(a)&&(a.innerText||'').trim().length>=12);
                    const paragraphs=[...n.querySelectorAll('p')].filter(visible);
                    const text=(n.innerText||'').trim();
                    if(kind==='list'?(links.length<3||links.length>150):(text.length<300||text.length>60000||paragraphs.length<2))continue;
                    const sampleLinks=[...new Map(links.filter(a=>a.origin===location.origin&&a.pathname!==location.pathname).map(a=>[a.href,a])).values()].slice(0,20);
                    const matches=sampleLinks.filter(a=>references.has(a.href)).length;
                    if(kind==='list'&&references.size&&(matches<Math.min(2,references.size)||matches/Math.max(1,sampleLinks.length)<.6))continue;
                    seen.add(css);regions.push({selector:css,count:kind==='list'?links.length:paragraphs.length,
                        sample:kind==='list'?links.slice(0,8).map(a=>(a.innerText||'').trim()+' '+a.getAttribute('href')).join('\\n').slice(0,1800):text.slice(0,1500)});
                }
                regions.sort((a,b)=>kind==='list'?Math.abs(a.count-20)-Math.abs(b.count-20):a.count-b.count);
                return {url:location.href,regions:regions.slice(0,40)};
            }`,[kind,referenceURLs]);
        }
        async executeExtractionStep(step) {
            const rule=step?.arguments?.site_extraction;
            if(!['compiled','adaptive'].includes(step?.mode)||!rule||rule.schema!=='ai2apps.site-extraction/v1'||
                !['list','article'].includes(rule.kind)||step.operation!==(rule.kind==='list'?'extract_list':'read_page')||
                typeof rule.selector!=='string'||rule.selector.length>300)throw Error('invalid_extraction_step');
            const result=await this.callJSON(`function(rule){
                const origin=String(rule.origin||'').trim(),path=String(rule.path||'').trim();
                if((origin&&location.origin!==origin)||(path&&location.pathname!==path))return null;
                const visible=n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n);return r.width>2&&r.height>2&&s.visibility!=='hidden'&&s.display!=='none';};
                const roots=document.querySelectorAll(rule.selector);if(roots.length!==1||!visible(roots[0]))return null;
                const root=roots[0];
                if(root.closest('nav,header,footer,aside,[role=dialog]'))return null;
                if(rule.kind==='list'){
                    const items=[],seen=new Set();
                    for(const a of root.querySelectorAll('a[href]')){
                        if(!visible(a)||a.closest('nav,header,footer,aside'))continue;
                        let url;try{url=new URL(a.href);}catch(_){continue;}
                        const title=(a.innerText||a.getAttribute('aria-label')||'').trim().replace(/\\s+/g,' ');
                        if(url.origin!==location.origin||url.pathname===location.pathname||seen.has(url.href)||title.length<12||title.length>320||/\\/(?:category|tag|page|login|about)(?:\\/|$)/i.test(url.pathname))continue;
                        seen.add(url.href);items.push({url:url.href,title,text:''});if(items.length>=20)break;
                    }
                    return {url:location.href,items};
                }
                const clone=root.cloneNode(true);
                for(const n of clone.querySelectorAll('script,style,nav,header,footer,aside,form,input,textarea,[hidden],[aria-hidden=true],[role=dialog]'))n.remove();
                const text=(clone.textContent||'').trim().replace(/\\n[ \\t]+/g,'\\n');
                return {url:location.href,title:document.querySelector('h1')?.innerText||document.title,text:text.slice(0,10000),extraction_method:'compiled-site-agent'};
            }`,[rule]);
            if(!result||(rule.kind==='list'?(!Array.isArray(result.items)||!result.items.length):(typeof result.text!=='string'||result.text.length<300)))throw Error('site_rule_drift');
            return result;
        }
        async extractRenderedPage({maxChars=20000}={}) {
            maxChars=Math.min(100000,Math.max(100,Number(maxChars)||20000));
            let readability=null, warning=null;
            try {
                if(!this.readabilitySource){
                    const response=await fetch('/admin/static/js/readability.js?v=foundation-1');
                    if(!response.ok) throw Error('readability_source_unavailable');
                    this.readabilitySource=await response.text();
                }
                readability=await this.callJSON(`function(){${this.readabilitySource}
setReadablility();
                    const clone=document.cloneNode(true);
                    for(const node of clone.querySelectorAll('script,style,input,textarea,[hidden],[aria-hidden="true"]')) node.remove();
                    const article=new globalThis.__ai2appsReadability(clone).parse();
                    return article ? {title:article.title,text:article.textContent,url:location.href} : null;}`,[],30000);
            } catch(error){warning=String(error.message||error).slice(0,160);}
            if(readability&&String(readability.text||'').trim().length>=100)
                return {...readability,text:String(readability.text).trim().slice(0,maxChars),extraction_method:'readability'};

            const snapshot = await this.snapshot({maxText:maxChars});
            const selection = await this.callJSON(`function(){return (getSelection()?.toString()||'').trim().slice(0,20000);}`);
            return {url:snapshot.url,title:snapshot.title,selection,text:snapshot.text,
                extraction_method:'webdriver-bidi-cleaned-dom',fallback_reason:warning||'readability_empty_or_short'};
        }
        async beginPageResourceTransfer(urls, maxBytes = 64 * 1024 * 1024, preferExact = false) {
            return this.callJSON(`async function(urls,maxBytes,preferExact){
                const supplied=(Array.isArray(urls)?urls:[urls]).map(value=>String(value||'')).filter(Boolean);
                const absolute=value=>{try{return new URL(String(value||''),location.href).href}catch(_){return ''}};
                const suppliedSet=new Set(supplied.map(absolute).filter(Boolean));
                const rendered=[];
                const addRendered=value=>{const url=absolute(value);if(url&&!rendered.includes(url))rendered.push(url)};
                const mediaRecords=[];
                const declaredFrequency=new Map();
                for(const media of document.querySelectorAll('img,video,audio,source')){
                    const declared=[];
                    for(const attribute of ['src','data-src','data-lazy-src','data-original']){
                        const value=media.getAttribute(attribute);if(value)declared.push(absolute(value));
                    }
                    for(const attribute of ['srcset','data-srcset']){
                        for(const item of String(media.getAttribute(attribute)||'').split(',')){
                            const value=item.trim().split(/\\s+/)[0];if(value)declared.push(absolute(value));
                        }
                    }
                    const enclosingLink=absolute(media.closest?.('a[href]')?.href||'');
                    const uniqueDeclared=[...new Set(declared.filter(Boolean))];
                    for(const value of uniqueDeclared)declaredFrequency.set(value,(declaredFrequency.get(value)||0)+1);
                    mediaRecords.push({media,declared:uniqueDeclared,enclosingLink});
                }
                const linkMatches=mediaRecords.filter(record=>record.enclosingLink&&suppliedSet.has(record.enclosingLink));
                const directMatches=mediaRecords.filter(record=>{
                    const current=absolute(record.media.currentSrc||record.media.src||'');
                    if(current&&suppliedSet.has(current))return true;
                    return record.declared.some(value=>suppliedSet.has(value)&&declaredFrequency.get(value)===1);
                });
                // A lazy-loader placeholder can be shared by every card.  If
                // the drag also carries its enclosing link, that link is the
                // precise identity and must win over shared media attributes.
                for(const {media,declared} of (linkMatches.length?linkMatches:directMatches)){
                    addRendered(media.currentSrc);addRendered(media.src);
                    for(const value of declared){if(declaredFrequency.get(value)===1)addRendered(value)}
                }
                const candidates=preferExact?supplied:[...rendered,...supplied.filter(value=>!rendered.includes(absolute(value)))];
                let lastError=new Error('No browser media URL was provided');
                for(const candidate of candidates){
                    try{
                        const resource=new URL(candidate,location.href);
                        if(!/^(https?:|blob:|data:)$/.test(resource.protocol)) throw new Error('Only page media can be imported');
                        const response=await fetch(resource.href,{credentials:'include'});
                        if(!response.ok) throw new Error('Media request failed ('+response.status+')');
                        const blob=await response.blob();
                        if(!/^(image|video|audio)\\//i.test(blob.type||'')) throw new Error('The dropped resource is not image, video, or audio');
                        if(blob.size>Number(maxBytes||0)) throw new Error('The dropped media exceeds the Gallery import limit');
                        const bytes=new Uint8Array(await blob.arrayBuffer());
                        const token=crypto.randomUUID();
                        const transfers=window.__ai2appsGalleryResourceTransfers||=new Map();
                        transfers.set(token,{bytes,createdAt:Date.now()});
                        const extension=(blob.type.split('/')[1]||'bin').replace(/[^a-z0-9.+-]/gi,'').split('+')[0];
                        const rawName=/^https?:$/.test(resource.protocol)
                            ? decodeURIComponent(resource.pathname.split('/').pop()||'').replace(/[\\/]/g,'-').slice(0,180)
                            : '';
                        return {token,url:resource.href,size:blob.size,media_type:blob.type,
                            name:rawName||('web-media-'+Date.now()+'.'+extension)};
                    }catch(error){lastError=error;}
                }
                throw lastError;
            }`, [urls, maxBytes, preferExact], 120000);
        }
        async readPageResourceChunk(token, offset, length = 196608) {
            return this.callJSON(`function(token,offset,length){
                const transfer=window.__ai2appsGalleryResourceTransfers?.get(String(token||''));
                if(!transfer) throw new Error('The browser media transfer expired');
                const start=Math.max(0,Number(offset||0));
                const end=Math.min(transfer.bytes.length,start+Math.max(1,Number(length||1)));
                const chunk=transfer.bytes.subarray(start,end);
                let binary='';
                for(let index=0;index<chunk.length;index+=32768){
                    binary+=String.fromCharCode(...chunk.subarray(index,index+32768));
                }
                return {offset:start,next_offset:end,done:end>=transfer.bytes.length,base64:btoa(binary)};
            }`, [token, offset, length], 30000);
        }
        async endPageResourceTransfer(token) {
            return this.callJSON(`function(token){
                return Boolean(window.__ai2appsGalleryResourceTransfers?.delete(String(token||'')));
            }`, [token]);
        }
        async armGalleryAssetDrop(token) {
            return this.callJSON(`function(token){
                const key=String(token||'');
                const stores=window.__ai2appsGalleryDrops||=new Map();
                const previous=stores.get(key);previous?.cleanup?.();
                const state={token:key,target:null,dropped:false,createdAt:Date.now()};
                const matches=event=>{const types=[...(event.dataTransfer?.types||[])];
                    return types.includes('application/x-ai2apps-gallery-asset')||
                        types.includes('application/x-ai2apps-gallery-drop-token');};
                const over=event=>{if(!matches(event))return;event.preventDefault();
                    if(event.dataTransfer)event.dataTransfer.dropEffect='copy';};
                const drop=event=>{if(!matches(event))return;event.preventDefault();event.stopPropagation();
                    state.target=event.target;state.dropped=true;state.droppedAt=Date.now();state.cleanup();};
                state.cleanup=()=>{document.removeEventListener('dragover',over,true);document.removeEventListener('drop',drop,true);};
                stores.set(key,state);document.addEventListener('dragover',over,true);document.addEventListener('drop',drop,true);
                setTimeout(()=>state.cleanup(),30000);return {armed:true};
            }`, [token]);
        }
        async galleryAssetDropState(token) {
            return this.callJSON(`function(token){
                const state=window.__ai2appsGalleryDrops?.get(String(token||''));
                const target=state?.target;
                return {dropped:Boolean(state?.dropped),tag:target?.tagName?.toLowerCase?.()||'',
                    type:target?.getAttribute?.('type')||'',name:target?.getAttribute?.('name')||'',
                    accepts_files:Boolean(target?.matches?.('input[type=file]')||target?.closest?.('label')?.querySelector?.('input[type=file]'))};
            }`, [token]);
        }
        async cancelGalleryAssetDrop(token) {
            return this.callJSON(`function(token){
                const key=String(token||'');const stores=window.__ai2appsGalleryDrops;
                const state=stores?.get(key);state?.cleanup?.();return Boolean(stores?.delete(key));
            }`, [token]);
        }
        async applyGalleryAssetDrop(token, paths) {
            const targetResult = await this.connection.command('script.callFunction', {
                functionDeclaration: `function(token){const state=window.__ai2appsGalleryDrops?.get(String(token||''));
                    if(!state?.target)return null;const direct=state.target.matches?.('input[type=file]')?state.target:null;
                    return direct||state.target.closest?.('label')?.querySelector?.('input[type=file]')||state.target;}`,
                arguments: [{type: 'string', value: String(token || '')}],
                target: {context: this.contextId},
                awaitPromise: false,
                resultOwnership: 'root',
            });
            const target = targetResult?.result;
            if (!target?.sharedId) throw new Error('Drop the Gallery asset on a file upload or editor area');
            const descriptor = await this.galleryAssetDropState(token);
            if (descriptor.accepts_files || (descriptor.tag === 'input' && descriptor.type === 'file')) {
                await this.connection.command('input.setFiles', {
                    context: this.contextId,
                    element: {sharedId: target.sharedId},
                    files: paths,
                }, 30000);
                await this.callJSON(`function(token){window.__ai2appsGalleryDrops?.delete(String(token||''));}`, [token]);
                return {mode: 'file-input'};
            }
            const inputResult = await this.connection.command('script.callFunction', {
                functionDeclaration: `function(){const input=document.createElement('input');input.type='file';input.multiple=true;
                    input.hidden=true;document.documentElement.appendChild(input);return input;}`,
                target: {context: this.contextId},
                awaitPromise: false,
                resultOwnership: 'root',
            });
            const input = inputResult?.result;
            if (!input?.sharedId) throw new Error('Could not prepare the page file drop');
            await this.connection.command('input.setFiles', {
                context: this.contextId,
                element: {sharedId: input.sharedId},
                files: paths,
            }, 30000);
            await this.connection.command('script.callFunction', {
                functionDeclaration: `function(token,input,target){const state=window.__ai2appsGalleryDrops?.get(String(token||''));
                    const data=new DataTransfer();for(const file of input.files)data.items.add(file);
                    const event=new DragEvent('drop',{bubbles:true,cancelable:true,composed:true,dataTransfer:data});
                    target.dispatchEvent(event);input.remove();state?.cleanup?.();window.__ai2appsGalleryDrops?.delete(String(token||''));
                    return {fileCount:data.files.length,accepted:event.defaultPrevented};}`,
                arguments: [
                    {type: 'string', value: String(token || '')},
                    {sharedId: input.sharedId},
                    {sharedId: target.sharedId},
                ],
                target: {context: this.contextId},
                awaitPromise: false,
            });
            return {mode: 'drop-zone'};
        }
        async chooseAttachmentFiles(hint, paths) {
            const target=await this.findTarget(hint);
            if(!target?.rect)return null;
            const token=crypto.randomUUID();
            await this.callJSON(`function(token){
                if(window.__ai2appsFileChooser)throw Error('Another upload is pending');
                const proto=HTMLInputElement.prototype,click=proto.click,picker=proto.showPicker;
                const state={token,input:null};
                const capture=input=>{if(input.type==='file'){state.input=input;return true;}return false;};
                const wrappedClick=function(...args){if(!capture(this))return click.apply(this,args);};
                const wrappedPicker=function(...args){if(!capture(this))return picker.apply(this,args);};
                const listener=event=>{if(event.target instanceof HTMLInputElement && capture(event.target))event.preventDefault();};
                proto.click=wrappedClick;if(picker)proto.showPicker=wrappedPicker;
                document.addEventListener('click',listener,true);
                state.cleanup=()=>{if(proto.click===wrappedClick)proto.click=click;
                    if(proto.showPicker===wrappedPicker)proto.showPicker=picker;
                    document.removeEventListener('click',listener,true);clearTimeout(state.timer);
                    if(window.__ai2appsFileChooser===state)delete window.__ai2appsFileChooser;};
                state.timer=setTimeout(state.cleanup,10000);window.__ai2appsFileChooser=state;return true;
            }`,[token]);
            try{
                await this.naturalPointer(target);
                const result=await this.connection.command('script.callFunction',{
                    functionDeclaration:`async function(token){const deadline=Date.now()+4000;while(Date.now()<deadline){const state=window.__ai2appsFileChooser;if(state?.token!==token)return null;if(state.input)return state.input;await new Promise(r=>setTimeout(r,100));}return null;}`,
                    arguments:[{type:'string',value:token}],target:{context:this.contextId},awaitPromise:true,resultOwnership:'root'
                });
                if(!result.result?.sharedId)throw Error('Upload click did not open a file chooser; inspect the upload entry before retrying');
                await this.connection.command('input.setFiles',{context:this.contextId,element:{sharedId:result.result.sharedId},files:paths},30000);
                return {file_count:paths.length,target_ref:target.ref,method:'clicked-file-chooser'};
            }finally{
                await this.callJSON(`function(token){const state=window.__ai2appsFileChooser;if(state?.token===token)state.cleanup();}`,[token]);
            }
        }
        async setAttachmentFiles(hint, paths) {
            const {interaction_mode:mode}=await this.interactionSettings();
            if(mode==='natural')return this.chooseAttachmentFiles(hint,paths);
            const snapshot = await this.snapshot();
            const available = (snapshot.file_inputs || []).filter(item => !item.disabled);
            const matched = available.find(item => item.ref === hint || item.text === hint);
            const target = matched || (available.length === 1 ? available[0] : null);
            if (!target) return null;
            const result = await this.connection.command('script.callFunction', {
                functionDeclaration:`function(ref){const roots=[document];for(let i=0;i<roots.length;i++){
                    for(const el of roots[i].querySelectorAll('*'))if(el.shadowRoot)roots.push(el.shadowRoot);
                    for(const el of roots[i].querySelectorAll('input[type=file]'))if(el.getAttribute('data-ai2apps-ref')===ref)return el;}return null;}`,
                arguments:[{type:'string',value:target.ref}], target:{context:this.contextId},
                awaitPromise:false, resultOwnership:'root'
            });
            if (!result.result?.sharedId) return null;
            await this.connection.command('input.setFiles', {context:this.contextId,
                element:{sharedId:result.result.sharedId},files:paths},30000);
            return {file_count:paths.length, target_ref:target.ref, method:'native-bidi-setFiles'};
        }
        async findTarget(intent, {operation = ''} = {}) {
            const snapshot = await this.snapshot();
            const query = String(intent || '').toLowerCase().replace(/页面上的|按钮|输入框|the|button|field/g,'').trim();
            let best = null;
            for (const item of snapshot.items) {
                if (item.disabled) continue;
                if (operation === 'input' && !item.editable && item.role !== 'textbox') continue;
                const name = item.text || '', low = name.toLowerCase();
                let score = item.ref === intent ? 120 : query && low === query ? 100 :
                    query && low.includes(query) ? 70 : query && query.includes(low) && low.length > 1 ? 50 : 0;
                if (/搜索|search/.test(query) && (/search|搜索/.test(low) || item.type === 'search')) score += 45;
                if (!score) continue;
                const [x,y,width,height] = item.rect;
                const candidate = {...item,name,sensitive:item.sensitive || /password|one.?time|otp|验证码/i.test(name),
                    rect:{x,y,width,height},score};
                if (!best || candidate.score > best.score) best = candidate;
            }
            return best;
        }
        async interactionSettings(url = null) {
            const page = url ? {url} : await this.pageState();
            let domain;try {domain=new URL(page.url).hostname.replace(/^www\./,'');}catch(_){domain='';}
            if(!domain)return {interaction_mode:'natural'};
            this.interactionSettingsCache ||= new Map();
            const cached=this.interactionSettingsCache.get(domain);
            if(cached && Date.now()-cached.at<5000)return cached.value;
            const response=await fetch('/v1/platform/browser-workspace/domains/'+encodeURIComponent(domain)+'/settings',{credentials:'same-origin'});
            if(!response.ok)throw Error('Cannot load website interaction settings');
            const value=await response.json();
            this.interactionSettingsCache.set(domain,{at:Date.now(),value});return value;
        }
        async interactionPause(mode) {
            if(mode!=='fast')await new Promise(resolve=>setTimeout(resolve,350+Math.round(Math.random()*400)));
        }
        async naturalPointer(target, {click = true, hoverMs = 0, seed = 1} = {}) {
            if (!target?.rect) throw new Error('Target has no visible rectangle');
            const {interaction_mode:mode}=await this.interactionSettings();
            await this.interactionPause(mode);
            const rect = target.rect;
            const jitterX = ((seed * 17) % 21 - 10) / 100;
            const jitterY = ((seed * 29) % 21 - 10) / 100;
            const x = Math.round(rect.x + rect.width * (0.5 + jitterX));
            const y = Math.round(rect.y + rect.height * (0.5 + jitterY));
            const actions=[];
            const prior=this.pointerPositions?.get(this.contextId) || {x:0,y:0};
            const count=mode==='fast'?1:12;
            for(let i=1;i<=count;i++){
                const t=i/count, eased=mode==='fast'?t:t*t*(3-2*t);
                actions.push({type:'pointerMove',x:Math.round(prior.x+(x-prior.x)*eased),
                    y:Math.round(prior.y+(y-prior.y)*eased),duration:mode==='fast'?0:35,origin:'viewport'});
            }
            actions.push({type:'pause',duration:mode==='fast'?Math.max(0,hoverMs):Math.max(100,hoverMs)});
            if (click) actions.push({type:'pointerDown',button:0},
                {type:'pause',duration:mode==='fast'?0:70},{type:'pointerUp',button:0});
            await this.connection.command('input.performActions', {
                context:this.contextId,actions:[{type:'pointer',id:'ai2apps-natural-pointer',parameters:{pointerType:'mouse'},actions}],
            });
            this.pointerPositions ||= new Map();this.pointerPositions.set(this.contextId,{x,y});
            return {x,y,profile:mode};
        }
        async typeText(text, {replace = false, submit = false} = {}) {
            const {interaction_mode:mode}=await this.interactionSettings();
            await this.interactionPause(mode);
            const value=String(text || ''),characters=Array.from(value);
            const sendKeys=async (part,{clear=false,enter=false}={})=>{
                const actions=[];
                if(clear){
                    const modifier=/Mac/i.test(navigator.platform)?'\uE03D':'\uE009';
                    actions.push({type:'keyDown',value:modifier},{type:'keyDown',value:'a'},
                        {type:'keyUp',value:'a'},{type:'keyUp',value:modifier},
                        {type:'keyDown',value:'\uE003'},{type:'keyUp',value:'\uE003'});
                }
                for(const character of part){
                    actions.push({type:'keyDown',value:character});
                    if(mode!=='fast')actions.push({type:'pause',duration:40+Math.round(Math.random()*70)});
                    actions.push({type:'keyUp',value:character});
                }
                if(enter)actions.push({type:'keyDown',value:'\uE007'},{type:'keyUp',value:'\uE007'});
                if(actions.length)await this.connection.command('input.performActions',{
                    context:this.contextId,actions:[{type:'key',id:'ai2apps-natural-keyboard',actions}]
                },30000);
            };
            if(characters.length<=500){
                for(let offset=0;offset<Math.max(1,characters.length);offset+=150)
                    await sendKeys(characters.slice(offset,offset+150),{clear:replace&&offset===0,enter:submit&&offset+150>=characters.length});
                return;
            }
            const token=crypto.randomUUID();
            // Bulk insertion uses the browser editing command, never the system clipboard or HTML.
            // Bind the focused editor before changing anything; a focus/DOM change stops the sequence.
            await this.callJSON(`function(token,text,replace){
                let field=document.activeElement;while(field?.shadowRoot?.activeElement)field=field.shadowRoot.activeElement;
                const plain=field?.tagName==='TEXTAREA'||(field?.tagName==='INPUT'&&['text','search','url','tel','email',''].includes(field.type));
                if(!field||field.disabled||field.readOnly||(!plain&&!field.isContentEditable))throw Error('Long text requires an editable text field');
                if(typeof document.execCommand!=='function'||(document.queryCommandSupported&&!document.queryCommandSupported('insertText')))throw Error('This editor does not support bulk text insertion');
                if(plain){const selected=replace?field.value.length:(field.selectionEnd-field.selectionStart)||0;
                    if(field.maxLength>=0&&field.value.length-selected+text.length>field.maxLength)throw Error('Text exceeds this field’s maximum length');
                    if(field.tagName==='INPUT'&&/[\\r\\n]/.test(text))throw Error('Multiline text requires a multiline editor');}
                window.__ai2appsBulkInputs ||= new Map();window.__ai2appsBulkInputs.set(token,{field,expected:plain?(replace?text:field.value.slice(0,field.selectionStart)+text+field.value.slice(field.selectionEnd)):null});return true;
            }`,[token,value,replace]);
            try{
                const prefix=mode==='fast'?0:6,suffix=mode==='fast'?0:4;
                await this.insertTextChunk(token,'');
                await sendKeys(characters.slice(0,prefix),{clear:replace});
                let typed=prefix+suffix;
                for(let offset=prefix;offset<characters.length-suffix;){
                    const end=Math.min(offset+8192,characters.length-suffix);
                    await this.insertTextChunk(token,characters.slice(offset,end).join(''));
                    offset=end;
                    if(mode!=='fast'){
                        await new Promise(resolve=>setTimeout(resolve,120+Math.round(Math.random()*180)));
                        if(typed<16&&offset<characters.length-suffix){await this.insertTextChunk(token,'');await sendKeys([characters[offset++]]);typed++;}
                    }
                }
                await this.insertTextChunk(token,'');
                await sendKeys(suffix?characters.slice(-suffix):[]);
                await this.callJSON(`function(token){const state=window.__ai2appsBulkInputs?.get(token);
                    let focused=document.activeElement;while(focused?.shadowRoot?.activeElement)focused=focused.shadowRoot.activeElement;
                    if(!state?.field.isConnected||focused!==state.field)throw Error('Text editor changed before completion');
                    if(state.expected!==null&&state.field.value!==state.expected)throw Error('Editor changed the final text; inspect before submitting');return true;}`,[token]);
                if(submit)await sendKeys([],{enter:true});
            }finally{
                await this.callJSON(`function(token){window.__ai2appsBulkInputs?.delete(token);}`,[token]);
            }
        }
        async insertTextChunk(token, text) {
            return this.callJSON(`function(token,text){
                const field=window.__ai2appsBulkInputs?.get(token)?.field;
                let focused=document.activeElement;while(focused?.shadowRoot?.activeElement)focused=focused.shadowRoot.activeElement;
                if(!field||!field.isConnected||field.disabled||field.readOnly||focused!==field)throw Error('Text editor changed during input; inspect before continuing');
                if(!text)return {inserted:0};
                const plain=field.tagName==='TEXTAREA'||field.tagName==='INPUT';
                const expected=plain?field.value.slice(0,field.selectionStart)+text+field.value.slice(field.selectionEnd):null;
                if(!document.execCommand('insertText',false,text))throw Error('Bulk text insertion failed; inspect partial input before continuing');
                if(plain&&field.value!==expected)throw Error('Editor changed or truncated inserted text; inspect partial input before continuing');
                return {inserted:text.length};
            }`,[token,text]);
        }
        async scroll(deltaY = 620) {
            const {interaction_mode:mode}=await this.interactionSettings();
            await this.interactionPause(mode);
            await this.connection.command('input.performActions', {
                context: this.contextId,
                actions: [{type: 'wheel', id: 'ai2apps-natural-wheel', actions: [
                    {type: 'scroll', x: 0, y: 0, deltaX: 0, deltaY, duration: mode==='fast'?0:360, origin: 'viewport'},
                ]}],
            });
            if(mode!=='fast')await new Promise(resolve => setTimeout(resolve, 260));
        }
        async readResultPages(items, limit = 3, options = {}) {
            const initial = await this.pageState();
            const originalContext = this.contextId;
            const newTab = options.newTab === true;
            const delayMs = Math.min(10000, Math.max(0, Number(options.delayMs) || 0));
            const pause = () => delayMs ? new Promise(resolve => setTimeout(resolve, delayMs)) : Promise.resolve();
            const articles = [], failures = [], seen = new Set(), readUrls = new Set();
            const articleLimit = Math.min(5, Math.max(1, limit));
            const candidates = (Array.isArray(items) ? items : []).filter(item => {
                try {
                    const url = new URL(item.url);
                    if (!/^https?:$/.test(url.protocol) || url.username || url.password ||
                        /^(localhost|127\.|0\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.|\[)/i.test(url.hostname) ||
                        /\.local$/i.test(url.hostname) || seen.has(url.href)) return false;
                    seen.add(url.href); return true;
                } catch { return false; }
            }).slice(0, 5);
            try {
                for (const item of candidates) {
                    let temporaryContext = null;
                    try {
                        if (newTab) {
                            const created=await this.connection.command("browsingContext.create", {type:"tab",referenceContext:originalContext,background:false});
                            temporaryContext=created.context; this.contextId=temporaryContext;
                        }
                        await this.connection.command('browsingContext.navigate', {
                            context:this.contextId, url:item.url, wait:'complete',
                        }, 30000);
                        await pause();
                        const access = await this.handlePageAccess();
                        if (['needs_user', 'restricted'].includes(access?.classification)) {
                            failures.push({url:item.url, reason:access.reason}); continue;
                        }
                        const page = await this.extractRenderedPage();
                        if (readUrls.has(page.url)) continue;
                        const text = String(page.text || '').slice(0, 6000);
                        if (!text.trim()) { failures.push({url:item.url, reason:'empty_page'}); continue; }
                        readUrls.add(page.url);
                        articles.push({url:page.url, title:page.title, text});
                        if (articles.length >= articleLimit) break;
                    } catch (error) {
                        failures.push({url:item.url, reason:String(error.message || error).slice(0, 200)});
                    } finally {
                        if (temporaryContext) {
                            try { await this.connection.command("browsingContext.close", {context:temporaryContext}); }
                            catch (error) { failures.push({url:item.url,reason:"tab_close_failed: "+String(error.message || error).slice(0,150)}); }
                        }
                        this.contextId=originalContext;
                        if (newTab) await pause();
                    }
                }
            } finally {
                this.contextId=originalContext;
                if (newTab) await this.connection.command("browsingContext.activate",{context:originalContext});
                else await this.connection.command('browsingContext.navigate', {
                    context:this.contextId, url:initial.url, wait:'complete',
                }, 30000);
            }
            return {articles, failures};
        }

        async extractArticleList(limit = 50) {
            return this.callJSON(`function(limit){
                const visible=node=>{const r=node.getBoundingClientRect(),s=getComputedStyle(node);
                    return r.width>2&&r.height>2&&s.display!=='none'&&s.visibility!=='hidden';};
                const excluded=node=>Boolean(node.closest('header,nav,footer,[role=navigation],[role=banner],[role=contentinfo]'));
                const contentRoot=document.querySelector('main,[role=main],#content')||document.body;
                const searchPage=/(^|\\.)google\\.[a-z.]+$/.test(location.hostname)&&location.pathname==='/search';
                const headings=[...contentRoot.querySelectorAll('h1,h2,h3,h4')].filter(node=>visible(node)&&!excluded(node));
                const candidates=[];
                for(const heading of headings){
                    let link=heading.closest('a[href]')||heading.querySelector('a[href]');
                    if(!link){
                        let parent=heading.parentElement;
                        for(let depth=0;parent&&depth<4&&!link;depth++,parent=parent.parentElement){
                            const links=[...parent.querySelectorAll(':scope > a[href],:scope > * > a[href]')].filter(visible);
                            if(links.length===1) link=links[0];
                        }
                    }
                    if(link) candidates.push({heading,link});
                }
                for(const link of contentRoot.querySelectorAll('article a[href],[role=listitem] a[href],a[href]')){
                    if(!visible(link)||excluded(link)) continue;
                    const heading=link.querySelector('h1,h2,h3,h4')||
                        link.closest('article,[role=listitem],li')?.querySelector('h1,h2,h3,h4');
                    candidates.push({heading,link});
                }
                const items=[],seen=new Set();
                for(const candidate of candidates){
                    const {heading,link}=candidate;
                    const href=link.href||''; if(!/^https?:/.test(href)||seen.has(href)) continue;
                    const parsed=new URL(href);
                    if(searchPage){
                        if((parsed.origin===location.origin&&parsed.pathname!=='/goto')||!heading||heading.tagName!=='H3') continue;
                    } else if(parsed.origin!==location.origin||parsed.pathname===location.pathname||
                        /^\\/(?:|archives|category|tag|sections?|watchbrands?|about|login|sign-up)(?:\\/|$)/i.test(parsed.pathname)||
                        /\\/page\\/\\d+\\/?$/.test(parsed.pathname)) continue;
                    let title=(heading?.innerText||link.getAttribute('aria-label')||link.innerText||'')
                        .replace(/\\s+/g,' ').trim();
                    if(!title||title.length<12||title.length>320) continue;
                    let root=link.closest('article,[role=listitem],li');
                    if(!root){
                        root=link;
                        let parent=link.parentElement;
                        for(let depth=0;parent&&depth<5;depth++,parent=parent.parentElement){
                            const headingCount=parent.querySelectorAll('h1,h2,h3,h4').length;
                            const linkCount=parent.querySelectorAll('a[href]').length;
                            if(headingCount<=2&&linkCount<=4&&(parent.innerText||'').length>title.length){
                                root=parent;
                            }
                        }
                    }
                    const text=(root.innerText||link.innerText||'').replace(/\\s+/g,' ').trim();
                    const dateNode=root.querySelector?.('time,[class*=date],[class*=time],[class*=publish]');
                    const date=dateNode?.getAttribute?.('datetime')||dateNode?.innerText||
                        (text.match(/(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\\s+\\d{1,2},\\s+\\d{4}/i)||[])[0]||'';
                    const authorNode=root.querySelector?.('[rel=author],.author,[class*=author],[class*=byline]');
                    let author=(authorNode?.innerText||'').replace(/\\s+/g,' ').trim();
                    if(!author){
                        const beforeDate=date?text.slice(0,text.toLowerCase().lastIndexOf(String(date).toLowerCase())):text;
                        const tail=beforeDate.replace(title,'').trim();
                        const match=tail.match(/(?:^|\\s)([A-Z][A-Z '&.-]{2,50})$/);
                        author=match?.[1]?.trim()||'';
                    }
                    if(author&&date){
                        const dateAt=title.toLowerCase().lastIndexOf(String(date).toLowerCase());
                        const beforeDate=dateAt>0?title.slice(0,dateAt).replace(/\s+\d+\s*$/,'').trim():title;
                        const authorAt=beforeDate.toLowerCase().lastIndexOf(author.toLowerCase());
                        if(authorAt>=12) title=beforeDate.slice(0,authorAt).trim();
                    }
                    const image=root.querySelector?.('img');
                    const imageCandidates=[
                        image?.currentSrc,image?.src,
                        image?.getAttribute?.('data-src'),image?.getAttribute?.('data-lazy-src'),
                        image?.getAttribute?.('data-original'),
                        String(image?.getAttribute?.('srcset')||image?.getAttribute?.('data-srcset')||'')
                            .split(',').map(value=>value.trim().split(/\s+/)[0]).filter(Boolean).pop(),
                    ].filter(Boolean);
                    let imageUrl='';
                    for(const candidate of imageCandidates){
                        try{
                            const resolved=new URL(candidate,location.href);
                            if(/^https?:$/.test(resolved.protocol)){imageUrl=resolved.href;break;}
                        }catch(_){}
                    }
                    seen.add(href);items.push({title,url:href,image_url:imageUrl,
                        author:author.trim(),published_at:String(date).trim(),summary:text.slice(0,360)});
                    if(items.length>=limit) break;
                }
                return {action:'list',page_url:location.href,page_title:document.title,items};
            }`, [limit]);
        }
        async handlePageAccess() {
            // Dismiss only recognised consent UI, never unrelated page actions.
            // Re-observe after native input: sending a click is not proof of dismissal.
            const inspect = () => this.callJSON(`function(){
                const positive=/^(?:deny(?: all)?|reject(?: all)?(?: cookies)?|decline(?: all)?|only necessary|necessary only|reject optional cookies|拒绝(?:所有|全部)?|仅必要|只允许必要|关闭|close|not now|稍后|以后再说)$/i;
                const visible=node=>{const r=node.getBoundingClientRect(),s=getComputedStyle(node);
                    return r.width>2&&r.height>2&&r.right>0&&r.bottom>0&&r.left<innerWidth&&r.top<innerHeight&&
                        s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity)>0;};
                const consentText=/cookies?|privacy preferences|consent preferences|隐私偏好|隐私设置/i;
                const selector='#CybotCookiebotDialog,#onetrust-banner-sdk,#onetrust-consent-sdk,.qc-cmp2-container,[role=dialog],[aria-modal=true],[id*=cookie i],[class*=cookie-banner i],[class*=consent-banner i]';
                const panels=[...document.querySelectorAll(selector)].filter(node=>visible(node)&&consentText.test(node.innerText||''));
                for(const panel of panels){
                    for(const node of panel.querySelectorAll('button,[role=button],a')){
                        const name=(node.getAttribute('aria-label')||node.innerText||node.textContent||node.title||'').replace(/\s+/g,' ').trim();
                        if(!visible(node)||node.disabled||node.getAttribute('aria-disabled')==='true'||!positive.test(name))continue;
                        const r=node.getBoundingClientRect(),x=Math.max(0,r.left),y=Math.max(0,r.top);
                        const width=Math.min(innerWidth,r.right)-x,height=Math.min(innerHeight,r.bottom)-y;
                        const hit=document.elementFromPoint(x+width/2,y+height/2);
                        if(!hit||!(hit===node||node.contains(hit)))continue;
                        return {name,rect:{x,y,width,height},classification:'safe_dismiss'};
                    }
                }
                if(panels.length) return {classification:'needs_user',reason:'cookie_consent'};
                const text=(document.body?.innerText||'').slice(0,50000);
                if(/too many requests|unusual traffic|访问过于频繁|操作过于频繁|请求过于频繁/i.test(text))return {classification:'restricted',reason:'rate_limited'};
                if(/sign in to confirm you.re not a bot|登录以确认您不是机器人/i.test(text))return {classification:'needs_user',reason:'captcha'};
                if(/captcha|verify you are human|验证码|机器人验证/i.test(text)) return {classification:'needs_user',reason:'captcha'};
                if(/subscribe to continue|purchase to continue|订阅后继续|付费墙/i.test(text)) return {classification:'restricted',reason:'paywall'};
                return {classification:'none'};
            }`);
            let dismissed = false;
            for(let attempt=0;attempt<3;attempt++){
                const candidate=await inspect();
                if(candidate.classification!=='safe_dismiss') return {...candidate,dismissed};
                await this.naturalPointer(candidate,{seed:41+attempt});
                dismissed=true;
                await this.waitForStability(5000);
            }
            const remaining=await inspect();
            return remaining.classification==='safe_dismiss'
                ? {classification:'needs_user',reason:'cookie_consent',dismissed:false}
                : {...remaining,dismissed};
        }
        async pickElement() {
            return this.callJSON(`function(){
                return new Promise(resolve=>{
                    const style=document.createElement('style');
                    style.dataset.ai2appsPicker='1';
                    style.textContent='[data-ai2apps-pick-hover]{outline:2px solid #7c3aed!important;outline-offset:2px!important;cursor:crosshair!important}';
                    document.documentElement.appendChild(style);
                    let hovered=null;
                    const move=event=>{if(hovered) hovered.removeAttribute('data-ai2apps-pick-hover');
                        hovered=event.target;hovered?.setAttribute('data-ai2apps-pick-hover','1');};
                    const done=event=>{event.preventDefault();event.stopPropagation();event.stopImmediatePropagation();
                        const node=event.target,r=node.getBoundingClientRect();
                        const result={tag:node.tagName.toLowerCase(),role:node.getAttribute('role')||'',
                            accessible_name:(node.getAttribute('aria-label')||node.innerText||node.textContent||'').replace(/\\s+/g,' ').trim().slice(0,300),
                            id:node.id||'',name:node.getAttribute('name')||'',type:node.getAttribute('type')||'',
                            rect:{x:r.x,y:r.y,width:r.width,height:r.height}};
                        cleanup();resolve(result);};
                    const cleanup=()=>{document.removeEventListener('pointermove',move,true);document.removeEventListener('click',done,true);
                        hovered?.removeAttribute('data-ai2apps-pick-hover');style.remove();};
                    document.addEventListener('pointermove',move,true);document.addEventListener('click',done,true);
                    setTimeout(()=>{cleanup();resolve(null);},30000);
                });
            }`, [], 35000);
        }
    }

    window.AI2AppsBiDi = {AI2AppsBiDiConnection, AI2AppsPageClient};
})();
