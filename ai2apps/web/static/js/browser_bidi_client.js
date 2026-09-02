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
            const ticketResponse = await fetch('/v1/platform/browser/webdriver-bidi/ticket', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {'Content-Type': 'application/json'},
                body: '{}',
            });
            if (!ticketResponse.ok) throw new Error('AceFox BiDi authorization is unavailable');
            const {ticket} = await ticketResponse.json();
            const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
            this.socket = new WebSocket(
                `${scheme}//${location.host}/v1/platform/browser/webdriver-bidi?ticket=${encodeURIComponent(ticket)}`
            );
            this.socket.addEventListener('message', event => {
                let payload;
                try { payload = JSON.parse(event.data); } catch (_) { return; }
                const pending = this.pending.get(payload.id);
                if (!pending) return;
                this.pending.delete(payload.id);
                clearTimeout(pending.timer);
                if (payload.error) pending.reject(new Error(`${payload.error}: ${payload.message || ''}`));
                else pending.resolve(payload.result || {});
            });
            await new Promise((resolve, reject) => {
                const timer = setTimeout(() => reject(new Error('AceFox BiDi connection timed out')), 7000);
                this.socket.addEventListener('open', () => { clearTimeout(timer); resolve(); }, {once: true});
                this.socket.addEventListener('error', () => {
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
            if (requestedContext && (!expected || normalizeURL(requestedContext.url) === expected)) return requested;
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
        async pageState() {
            return this.callJSON(`function(){
                const text=(document.body?.innerText||'').replace(/\\s+/g,' ').trim();
                return {url:location.href,title:document.title||location.href,
                    text_length:text.length,text_sample:text.slice(0,500),
                    fingerprint:[location.origin,location.pathname,document.querySelectorAll('*').length,
                        document.querySelectorAll('a').length,document.querySelectorAll('button').length].join('|')};
            }`);
        }
        async explorationObservation() {
            return this.callJSON(`function(){
                const text=(document.body?.innerText||'').replace(/\s+/g,' ').trim();
                const visible=node=>{const r=node.getBoundingClientRect(),s=getComputedStyle(node);
                    return r.width>2&&r.height>2&&s.visibility!=='hidden'&&s.display!=='none'&&Number(s.opacity)>0;};
                const controls=[...document.querySelectorAll('button,a,input,textarea,select,[role=button],[role=link]')]
                    .filter(visible).slice(0,80).map(node=>({
                        role:node.getAttribute('role')||node.tagName.toLowerCase(),
                        type:node.getAttribute('type')||'',
                        name:(node.getAttribute('aria-label')||node.getAttribute('title')||node.placeholder||
                            node.innerText||node.textContent||'').replace(/\s+/g,' ').trim().slice(0,160),
                    }));
                return {url:location.href,title:document.title||location.href,
                    text_length:text.length,text_sample:text.slice(0,1200),controls,
                    control_count:controls.length,link_count:document.querySelectorAll('a').length,
                    button_count:document.querySelectorAll('button,[role=button]').length,
                    fingerprint:[location.origin,location.pathname,document.querySelectorAll('*').length,
                        document.querySelectorAll('a').length,document.querySelectorAll('button').length].join('|')};
            }`);
        }
        async extractRenderedPage() {
            return this.callJSON(`async function(){
                await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
                await new Promise(resolve=>setTimeout(resolve,0));
                await new Promise(resolve=>requestAnimationFrame(resolve));
                const selection=(getSelection()?.toString()||'').trim().slice(0,20000);
                const text=(document.body?.innerText||document.documentElement?.innerText||'')
                    .replace(/\\n{3,}/g,'\\n\\n').trim().slice(0,1000000);
                return {url:location.href,title:document.title||location.href,selection,text,
                    extraction_method:'webdriver-bidi-rendered-text'};
            }`, [], 30000);
        }
        async beginPageResourceTransfer(urls, maxBytes = 64 * 1024 * 1024) {
            return this.callJSON(`async function(urls,maxBytes){
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
                const candidates=[...rendered,...supplied.filter(value=>!rendered.includes(absolute(value)))];
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
            }`, [urls, maxBytes], 120000);
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
        async findTarget(intent) {
            return this.callJSON(`function(intent){
                const q=String(intent||'').toLowerCase().replace(/页面上的|按钮|输入框|the|button|field/g,'').trim();
                const nodes=[...document.querySelectorAll('button,a,input,textarea,select,[role="button"],[role="link"],[tabindex]')];
                const visible=node=>{const r=node.getBoundingClientRect(),s=getComputedStyle(node);
                    return r.width>2&&r.height>2&&s.visibility!=='hidden'&&s.display!=='none'&&Number(s.opacity)>0;};
                const label=node=>[node.getAttribute('aria-label'),node.getAttribute('title'),node.placeholder,
                    node.value,node.innerText,node.textContent].filter(Boolean).join(' ').replace(/\\s+/g,' ').trim();
                let best=null;
                for(const node of nodes){
                    if(!visible(node)) continue;
                    const name=label(node),low=name.toLowerCase();
                    let score=q&&low===q?100:q&&low.includes(q)?70:q&&q.includes(low)&&low.length>1?50:0;
                    if(/搜索|search/.test(q)&&(/search|搜索/.test(low)||node.type==='search')) score+=45;
                    if(!score) continue;
                    const r=node.getBoundingClientRect();
                    const sensitive=node.matches('input[type=password]')||
                        /password|one.?time|otp|验证码/.test([node.name,node.id,node.autocomplete,name].join(' ').toLowerCase());
                    const candidate={name,tag:node.tagName.toLowerCase(),role:node.getAttribute('role')||'',
                        type:node.type||'',sensitive,rect:{x:r.x,y:r.y,width:r.width,height:r.height},score};
                    if(!best||candidate.score>best.score) best=candidate;
                }
                return best;
            }`, [intent]);
        }
        async naturalPointer(target, {click = true, hoverMs = 0, seed = 1} = {}) {
            if (!target?.rect) throw new Error('Target has no visible rectangle');
            const rect = target.rect;
            const jitterX = ((seed * 17) % 21 - 10) / 100;
            const jitterY = ((seed * 29) % 21 - 10) / 100;
            const x = Math.round(rect.x + rect.width * (0.5 + jitterX));
            const y = Math.round(rect.y + rect.height * (0.5 + jitterY));
            const actions = [
                {type: 'pointerMove', x, y, duration: 220, origin: 'viewport'},
                {type: 'pause', duration: Math.max(80, hoverMs || 90)},
            ];
            if (click) actions.push(
                {type: 'pointerDown', button: 0},
                {type: 'pause', duration: 70},
                {type: 'pointerUp', button: 0}
            );
            await this.connection.command('input.performActions', {
                context: this.contextId,
                actions: [{type: 'pointer', id: 'ai2apps-natural-pointer', parameters: {pointerType: 'mouse'}, actions}],
            });
            await new Promise(resolve => setTimeout(resolve, click ? 220 : hoverMs));
            return {x, y, profile: 'natural'};
        }
        async typeText(text) {
            const actions = [];
            for (const character of String(text || '').slice(0, 2000)) {
                actions.push({type: 'keyDown', value: character});
                actions.push({type: 'pause', duration: 25 + character.charCodeAt(0) % 45});
                actions.push({type: 'keyUp', value: character});
            }
            await this.connection.command('input.performActions', {
                context: this.contextId,
                actions: [{type: 'key', id: 'ai2apps-natural-keyboard', actions}],
            }, 30000);
        }
        async scroll(deltaY = 620) {
            await this.connection.command('input.performActions', {
                context: this.contextId,
                actions: [{type: 'wheel', id: 'ai2apps-natural-wheel', actions: [
                    {type: 'scroll', x: 0, y: 0, deltaX: 0, deltaY, duration: 360, origin: 'viewport'},
                ]}],
            });
            await new Promise(resolve => setTimeout(resolve, 260));
        }
        async extractArticleList(limit = 50) {
            return this.callJSON(`function(limit){
                const visible=node=>{const r=node.getBoundingClientRect(),s=getComputedStyle(node);
                    return r.width>2&&r.height>2&&s.display!=='none'&&s.visibility!=='hidden';};
                const excluded=node=>Boolean(node.closest('header,nav,footer,[role=navigation],[role=banner],[role=contentinfo]'));
                const contentRoot=document.querySelector('main,[role=main],#content')||document.body;
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
                    if(parsed.origin!==location.origin||parsed.pathname===location.pathname||
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
            const candidate = await this.callJSON(`function(){
                const positive=/reject|decline|only necessary|necessary only|拒绝|仅必要|只允许必要|关闭|close|not now|稍后|以后再说/i;
                const forbidden=/accept|agree|allow all|同意|接受|全部允许|terms|条款|subscribe|购买|支付/i;
                const visible=node=>{const r=node.getBoundingClientRect(),s=getComputedStyle(node);
                    return r.width>2&&r.height>2&&s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity)>0;};
                for(const node of document.querySelectorAll('button,[role=button],a')){
                    const name=[node.getAttribute('aria-label'),node.title,node.innerText,node.textContent].filter(Boolean).join(' ').replace(/\\s+/g,' ').trim();
                    if(!visible(node)||!positive.test(name)||forbidden.test(name)) continue;
                    const r=node.getBoundingClientRect();
                    return {name,rect:{x:r.x,y:r.y,width:r.width,height:r.height},classification:'safe_dismiss'};
                }
                const text=(document.body?.innerText||'').slice(0,50000);
                if(/captcha|verify you are human|验证码|机器人验证/i.test(text)) return {classification:'needs_user',reason:'captcha'};
                if(/subscribe to continue|purchase to continue|订阅后继续|付费墙/i.test(text)) return {classification:'restricted',reason:'paywall'};
                return {classification:'none'};
            }`);
            if (candidate.classification === 'safe_dismiss') {
                candidate.pointer = await this.naturalPointer(candidate, {seed: 41});
            }
            return candidate;
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
