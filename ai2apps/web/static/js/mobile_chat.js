/* User-initiated reply actions; speech uses the authorized Desktop Chat API. */
(function(root){'use strict';
 class Controller {
  constructor(notify,requestSpeech){this.notify=notify;this.requestSpeech=requestSpeech;this.active=null;this.generation=0;}
  stop(){this.generation++;this.abort?.abort();this.abort=null;const active=this.active;this.active=null;this.player?.pause();this.player?.remove();this.player=null;this.finishPlayback?.();this.finishPlayback=null;if(this.url)URL.revokeObjectURL(this.url);this.url=null;active?.setPlaying(false);}
  async copy(text,button){
   if(!text.trim())return;
   try{
    try{if(!root.navigator.clipboard?.writeText)throw Error();await root.navigator.clipboard.writeText(text);}
    catch(_){const input=root.document.createElement('textarea'),focused=root.document.activeElement;input.value=text;input.setAttribute('readonly','');input.style.cssText='position:fixed;left:-10000px;top:0';root.document.body.append(input);try{input.select();input.setSelectionRange(0,text.length);if(!root.document.execCommand('copy'))throw Error();}finally{input.remove();focused?.focus?.({preventScroll:true});}}
    this.notify('已复制');root.AI2AppsChatFeedback?.show(button,true,true);
   }catch(_){this.notify('复制失败，请长按正文选择复制。');root.AI2AppsChatFeedback?.show(button,false,true);}
  }
  async speak(action,body){
   if(this.active===action){this.stop();return;}
   this.stop();
   action.setError('');
   const readable=body.cloneNode(true);readable.querySelectorAll('pre').forEach(n=>n.remove());
   const cleaned=(readable.innerText||readable.textContent||'').trim();
   if(!cleaned)return;
   const chunks=[],chars=Array.from(cleaned);while(chars.length){let end=Math.min(240,chars.length);if(end<chars.length){for(let i=end-1;i>=80;i--)if(/[。！？.!?；;\s]/.test(chars[i])){end=i+1;break;}}chunks.push(chars.splice(0,end).join(''));}
   const generation=this.generation;this.active=action;action.setPlaying(true);this.abort=new AbortController();
   try{
    for(const part of chunks){
     const blob=await this.requestSpeech(part,this.abort.signal);if(generation!==this.generation)return;
     const url=URL.createObjectURL(blob),player=root.document.createElement('audio');this.url=url;this.player=player;player.src=url;player.controls=true;player.className='mchat-speech-player';action.toolbar.after(player);
     await new Promise((resolve,reject)=>{this.finishPlayback=resolve;player.onended=resolve;player.onerror=()=>reject(Error('Desktop 音频播放失败。'));player.play().catch(error=>{if(error.name==='NotAllowedError')this.notify('音频已生成，请点击播放器开始朗读。');else reject(error);});});
     player.pause();player.remove();URL.revokeObjectURL(url);if(generation!==this.generation)return;this.player=null;this.url=null;this.finishPlayback=null;
    }
   }catch(error){if(generation===this.generation&&error.name!=='AbortError'){const message=error.message||'Desktop TTS 暂不可用，请在 Desktop 检查语音合成模型配置。';action.setError(message);this.notify(message);}}
   finally{if(generation===this.generation)this.stop();}
  }
  attach(body,parent){
   const toolbar=root.document.createElement('div');toolbar.className='mchat-message-actions';toolbar.setAttribute('role','group');toolbar.setAttribute('aria-label','回复操作');
   const button=(label,icon)=>{const b=root.document.createElement('button');b.type='button';b.title=label;b.setAttribute('aria-label',label);b.innerHTML='<i data-lucide="'+icon+'" aria-hidden="true"></i>';toolbar.append(b);return b;};
   const copy=button('复制回复','copy'),speech=button('朗读回复','volume-2'),error=root.document.createElement('p');error.className='mchat-speech-error';error.setAttribute('role','alert');error.hidden=true;
   const action={toolbar,setError(message){error.textContent=message;error.hidden=!message;},setPlaying(playing){speech.setAttribute('aria-label',playing?'停止朗读':'朗读回复');speech.title=playing?'停止朗读':'朗读回复';speech.setAttribute('aria-pressed',String(playing));speech.innerHTML='<i data-lucide="'+(playing?'square':'volume-2')+'" aria-hidden="true"></i>';root.lucide?.createIcons();},update(){toolbar.hidden=!String(body._messageText||'').trim();}};
   speech.setAttribute('aria-pressed','false');copy.onclick=()=>this.copy(String(body._messageText||''),copy);speech.onclick=()=>this.speak(action,body);
   parent.append(toolbar,error);action.update();return action;
  }
 }
 root.AI2AppsMobileMessageActions={Controller};
})(window);

(function () {
    'use strict';

    const root = document.querySelector('[data-mobile-chat]');
    if (!root) return;
    window.AI2APPS_MOBILE_SURFACE = true;
    if(root.dataset.agentSigned==='true'&&root.dataset.shellInline!=='true'&&location.pathname==='/mobile/agent-chat'){const params=new URLSearchParams(location.hash.slice(1));params.set('app','ai2apps.general-chat');location.replace('/mobile/home#'+params);return;}
    const $ = (selector) => root.querySelector(selector);
    const list = $('[data-mobile-chat-list]');
    const form = $('[data-mobile-chat-form]');
    const input = $('[data-mobile-chat-input]');
    const model = $('[data-mobile-chat-model]');
    let agentKey = '';
    const send = $('[data-mobile-chat-send]');
    const sendMarkup = send.innerHTML;
    const sendLabel = send.getAttribute('aria-label');
    const fileInput = $('[data-mobile-chat-file]');
    const attachmentsView = $('[data-mobile-chat-attachments]');
    const drawer = $('[data-mobile-chat-drawer]');
    const sessionList = $('[data-mobile-chat-session-list]');
    const title = $('[data-mobile-chat-title]');
    const status = $('[data-mobile-chat-status]');
    const statusTitle = $('[data-mobile-chat-status-title]');
    const statusDetail = $('[data-mobile-chat-status-detail]');
    const progress = $('[data-mobile-chat-progress]');
    const toast = $('[data-mobile-chat-toast]');

    const signedAgent = root.dataset.agentSigned === 'true';
    const agentEnabled = root.dataset.agentEnabled === 'true';
    const inlineShell=root.dataset.shellInline==='true';
    const runsContainer = $('[data-mobile-agent-runs]');
    let modelCatalog = [];
    let modelExplicit = false;
    const mobileAgent = new window.AI2AppsMobileAgentChat.Client({
        container: runsContainer, request, enabled: agentEnabled,
        async uploadMaterial(file,run){const uploaded=await uploadAttachment({file},run.session_id);idle();return {id:uploaded.id,name:uploaded.filename,media_type:uploaded.media_type,size_bytes:uploaded.size_bytes,storage:'reference'};},
        placeRun(card,run){
            const messages=[...list.querySelectorAll('.mchat-message')];
            const input=messages.find(n=>n.dataset.messageRunId===run.id&&n.dataset.messageRole==='user');
            const output=messages.find(n=>n.dataset.messageRunId===run.id&&n.dataset.messageRole==='assistant');
            if(input)input.after(card);
            else if(output)output.before(card);
            else {
                const next=messages.find(n=>n.dataset.messageCreatedAt&&run.created_at&&n.dataset.messageCreatedAt>run.created_at);
                if(next)next.before(card);else list.insertBefore(card,runsContainer.parentNode===list?runsContainer:null);
            }
        },
        async loadOwners(run){
            return request('/v1/mobile/agent-runs/'+encodeURIComponent(run.id)+'/owners');
        },
        onBusy(value) { busy = value; send.disabled = value; model.disabled = value; },
        async onComplete(run) {
            if (current?.id !== run.session_id) return;
            content = await request('/v1/mobile/chat/threads/' + encodeURIComponent(current.id) + '/content');
            current = content.thread;
            renderMessages();
        },
    });
    let threads = [];
    let current = null;
    let apiDefaultModel = "";
    let lastActiveModel = "";
    const threadModels = new Map();
    let content = null;
    let mode = agentEnabled ? 'agent' : 'chat';
    let attachments = [];
    let busy = false;
    let directGeneration = 0;
    let directTurnId = null;
    let composing = false;
    let compositionEndedAt = -Infinity;
    let toastTimer = null;
    const messageActions = window.AI2AppsMobileMessageActions ? new window.AI2AppsMobileMessageActions.Controller(notify,requestSpeech) : null;
    const terminalRunStates = new Set(['completed', 'failed', 'cancelled', 'interrupted']);

    function icons() {
        try { if (window.lucide) window.lucide.createIcons(); } catch (_) {}
    }

    function escapeHtml(value) {
        return String(value == null ? '' : value).replace(/[&<>"']/g, (character) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        })[character]);
    }

    async function request(url, options) {
        const transport = signedAgent && window.AI2AppsAgentConnection ? window.AI2AppsAgentConnection.signedFetch : fetch;
        const response = await transport(url, Object.assign({
            credentials: 'same-origin', headers: { Accept: 'application/json' },
        }, options || {}));
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = payload.detail;
            const message=typeof detail==='string'?detail:detail?.message||(Array.isArray(detail)?detail.map(item=>item.msg).filter(Boolean).join('; '):'')||payload.error?.message||'Request failed';
            throw new Error(message+' (HTTP '+response.status+')');
        }
        return payload;
    }

    async function requestSpeech(text,signal){
        if(!current?.id)throw Error('请先打开对话。');
        const transport=signedAgent&&window.AI2AppsAgentConnection?window.AI2AppsAgentConnection.signedFetch:fetch;
        const response=await transport('/v1/mobile/chat/threads/'+encodeURIComponent(current.id)+'/speech',{
            method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({text}),signal});
        if(!response.ok){const data=await response.json().catch(()=>({}));throw Error(typeof data.detail==='string'?data.detail:'Desktop TTS 暂不可用，请在 Desktop 安装或配置语音合成模型。');}
        if(!response.headers.get('content-type')?.startsWith('audio/'))throw Error('Desktop 返回了无效音频。');
        return response.blob();
    }

    function notify(message) {
        toast.textContent = message;
        toast.classList.add('is-visible');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.remove('is-visible'), 2600);
    }

    function working(headline, detail, value) {
        status.hidden = false;
        statusTitle.textContent = headline || 'AI is working';
        statusDetail.textContent = detail || '';
        progress.style.width = Math.max(8, Math.min(100, value == null ? 35 : value)) + '%';
    }

    function idle() { status.hidden = true; }

    function messageText(message) {
        if (typeof message.content === 'string') return message.content;
        if (!Array.isArray(message.content)) return '';
        return message.content.filter((part) => part?.type === 'text').map((part) => part.text || '').join('\n');
    }

    function messageFiles(message) {
        if (!Array.isArray(message.content)) return [];
        return message.content.flatMap((part) => {

            if (part?.type === 'file') return [part.file?.filename || 'Attachment'];
            return [];
        });
    }

    function renderMessageBody(node,text,markdown=false) {
        node._messageText=String(text||'');
        node._messageActions?.update();
        node.classList.toggle('mchat-markdown',markdown);
        if(!markdown||!window.marked||!window.DOMPurify){node.textContent=text||'';return;}
        node.innerHTML=window.DOMPurify.sanitize(window.marked.parse(text||'',{gfm:true,breaks:true,async:false}),{
            ALLOWED_TAGS:['p','br','strong','em','del','h1','h2','h3','h4','h5','h6','ul','ol','li','blockquote','pre','code','hr','a','table','thead','tbody','tr','th','td'],
            ALLOWED_ATTR:['href','title','start','colspan','rowspan'],
        });
        for(const link of node.querySelectorAll('a')){
            try{const url=new URL(link.getAttribute('href')||'',location.href);if(!['https:','http:'].includes(url.protocol))throw Error();link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';}
            catch(_){link.removeAttribute('href');}
        }
        for(const table of node.querySelectorAll('table')){const scroll=document.createElement('div');scroll.className='mchat-table-scroll';table.before(scroll);scroll.append(table);}
    }

    function addMessage(role, text, options) {
        const empty = list.querySelector('.mchat-empty');
        if (empty) empty.remove();
        const node = document.createElement('div');
        node.dataset.messageRole=role;
        if(options?.runId)node.dataset.messageRunId=options.runId;
        if(options?.createdAt)node.dataset.messageCreatedAt=options.createdAt;
        node.className = 'mchat-message ' + role + (options?.error ? ' error' : '');
        if (options?.agent) {
            const meta = document.createElement('span');
            meta.className = 'mchat-message-meta';
            meta.textContent = options.agent;
            node.appendChild(meta);
        }
        for (const image of (options?.images || []).filter(image=>!(options?.artifacts||[]).some(a=>a.artifact_id===image.artifact_id))) {
            const img = document.createElement('img');img.className='mchat-generated-image';img.alt=image.filename||'Generated image';img.loading='lazy';
            const failure=document.createElement('small');failure.hidden=true;failure.textContent='图片读取失败，请重新连接后刷新。';node.append(img,failure);
            const failed=(error)=>{img.hidden=true;failure.hidden=false;if(error instanceof Error)failure.textContent=error.message;};img.onerror=failed;
            if(signedAgent && options.runId && image.artifact_id){
                window.AI2AppsAgentConnection.artifactImage(options.runId,image.artifact_id).then(asset=>{if(!img.isConnected){asset.dispose();return;}const canvas=document.createElement('canvas');canvas.className=img.className;canvas.setAttribute('role','img');canvas.setAttribute('aria-label',img.alt);asset.paint(canvas).then(()=>{if(img.isConnected)img.replaceWith(canvas);}).catch(failed).finally(asset.dispose);}).catch(failed);
            }else if(typeof image.url==='string' && /^data:image\/(png|jpeg|webp);base64,/.test(image.url)){img.src=image.url;}
            else {failed();}
        }
        const copy = document.createElement('div');
        renderMessageBody(copy,text,role==='assistant'&&!options?.error);
        node.appendChild(copy);
        (options?.files || []).forEach((name) => {
            const note = document.createElement('span');
            note.className = 'mchat-file-note';
            note.textContent = '📎 ' + name;
            node.appendChild(note);
        });
        if (options?.artifacts && window.AI2AppsChatArtifacts) {
            const assets=document.createElement('div');node.append(assets);
            window.AI2AppsChatArtifacts.render(assets,options.artifacts,{signed:signedAgent,runId:options.runId,includeImages:true});
        }
        if (options?.views && window.AI2AppsResultViews) {
            const views = document.createElement('div');
            window.AI2AppsResultViews.render(views, options.views, signedAgent && options.runId ? {resolveImage:(_,vi,ii)=>window.AI2AppsAgentConnection.resultImage(options.runId,vi,ii)} : {});
            node.appendChild(views);
        }
        if(role==='assistant'&&!options?.error&&messageActions)copy._messageActions=messageActions.attach(copy,node);
        list.appendChild(node);
        if(copy._messageActions)icons();
        list.scrollTop = list.scrollHeight;
        return { node, copy };
    }

    function renderMessages() {
        messageActions?.stop();
        // Preserve live form nodes while rebuilding the persisted message stream.
        for(const card of mobileAgent.cards.values())card.remove();
        runsContainer.remove();
        list.innerHTML = '';
        const messages = content?.messages || [];
        if (!messages.length) {
            list.innerHTML = '<div class="mchat-empty"><i data-lucide="sparkles"></i><h1>Start a conversation</h1><p>This conversation stays on this client.</p></div>';
            icons();
            list.appendChild(runsContainer);
            mobileAgent.placeCards();
            return;
        }
        messages.forEach((message) => addMessage(message.role, messageText(message), {
            files: messageFiles(message),
            images: Array.isArray(message.content) ? message.content.filter(p=>p?.type==='image_url').map(p=>p.image_url||{}) : [],
            agent: message.metadata?.agent_run_id ? 'Agent' : null,
            views: message.metadata?.aaat_views || message.aaat_views,
            artifacts: message.metadata?.artifacts || message.artifacts,
            runId: message.metadata?.agent_run_id,
            createdAt: message.created_at,
        }));
        if(messages.length<=2&&Array.isArray(content?.session_metadata?.starterSuggestions)){
            const topics=document.createElement('div');topics.className='mchat-starter-topics';
            for(const topic of content.session_metadata.starterSuggestions.filter(q=>typeof q==='string'&&q.length<=500).slice(0,5)){
                const button=document.createElement('button');button.type='button';button.textContent=topic;
                button.onclick=()=>{input.value=topic;input.dispatchEvent(new Event('input'));input.focus();};topics.append(button);
            }
            list.append(topics);
        }
        list.appendChild(runsContainer);
        mobileAgent.placeCards();
    }

    function renderThreads() {
        const cn = (document.documentElement.lang || '').startsWith('zh');
        sessionList.innerHTML = threads.map((thread) => (
            '<div class="mchat-session-row"><button class="mchat-session' + (thread.id === current?.id ? ' is-active' : '') +
            '" type="button" data-thread-id="' + escapeHtml(thread.id) + '"><strong>' +
            escapeHtml(thread.title || 'New chat') + '</strong><small>' +
            new Date(thread.updated_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) +
            '</small></button><details class="mchat-session-menu"><summary aria-label="' + (cn ? '会话菜单' : 'Session menu') + '">⋯</summary><div class="mchat-session-menu-items">' +
            '<button type="button" data-thread-action="rename" data-thread-action-id="'+escapeHtml(thread.id)+'">'+(cn?'改名':'Rename')+'</button>'+
            '<button type="button" data-thread-action="delete" data-thread-action-id="'+escapeHtml(thread.id)+'">'+(cn?'删除':'Delete')+'</button></div></details></div>'
        )).join('');
    }

    let managingThread = false;
    let threadDialogOpen = false;
    function threadDialog(action, thread) {
        if(threadDialogOpen)return Promise.resolve(null);
        threadDialogOpen=true;
        const cn=(document.documentElement.lang||'').startsWith('zh'),rename=action==='rename';
        const previous=document.activeElement?.closest('.mchat-session-menu')?.querySelector('summary')||document.activeElement,overlay=document.createElement('div');overlay.className='mchat-thread-dialog';
        const panel=document.createElement('form');panel.className='mchat-thread-dialog-panel';panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');
        const heading=document.createElement('h2');heading.id='mchat-thread-dialog-title';heading.textContent=rename?(cn?'修改会话名称':'Rename session'):(cn?'删除会话？':'Delete session?');panel.setAttribute('aria-labelledby',heading.id);panel.append(heading);
        const field=rename?document.createElement('input'):document.createElement('p');
        if(rename){field.value=thread.title||'';field.maxLength=160;field.required=true;field.setAttribute('aria-label',heading.textContent);}
        else field.textContent=(thread.title||'New chat')+(cn?'\n会话将从列表中删除。':'\nThis session will be removed from the list.');
        panel.append(field);
        const buttons=document.createElement('div'),cancel=document.createElement('button'),accept=document.createElement('button');buttons.className='mchat-thread-dialog-actions';cancel.type='button';cancel.textContent=cn?'取消':'Cancel';cancel.dataset.threadDialogCancel='';accept.type='submit';accept.dataset.threadDialogAccept='';accept.textContent=rename?(cn?'保存':'Save'):(cn?'删除':'Delete');if(!rename)accept.className='is-danger';buttons.append(cancel,accept);panel.append(buttons);overlay.append(panel);root.append(overlay);
        return new Promise(resolve=>{
            const close=value=>{threadDialogOpen=false;overlay.remove();previous?.focus?.();resolve(value);};
            cancel.onclick=()=>close(null);overlay.onclick=e=>{if(e.target===overlay)close(null);};
            panel.onsubmit=e=>{e.preventDefault();if(rename&&!field.value.trim()){field.focus();return;}close(rename?field.value.trim():true);};
            panel.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();close(null);}else if(e.key==='Tab'){const nodes=rename?[field,cancel,accept]:[cancel,accept],i=nodes.indexOf(document.activeElement);if(e.shiftKey&&i===0){e.preventDefault();nodes.at(-1).focus();}else if(!e.shiftKey&&i===nodes.length-1){e.preventDefault();nodes[0].focus();}}};
            (rename?field:cancel).focus();if(rename)field.select();
        });
    }
    async function manageThread(action, id) {
        if (managingThread) return;
        const cn=(document.documentElement.lang||'').startsWith('zh');
        const thread=threads.find(t=>t.id===id);if(!thread)return;
        if(busy){notify(cn?'请等待当前回复结束后再操作。':'Wait for the current reply to finish.');return;}
        let nextTitle;
        if(action==='rename'){
            nextTitle=await threadDialog('rename',thread);
            if(nextTitle===null)return;nextTitle=nextTitle.trim();
            if(!nextTitle||nextTitle.length>160){notify(cn?'名称需为 1–160 个字符。':'Use a name of 1–160 characters.');return;}
        }else if(action==='delete'){
            if(!await threadDialog('delete',thread))return;
        }else return;
        managingThread=true;
        try{
            // Read fresh revision; never overwrite content to rename a thread.
            const loaded=await request('/v1/mobile/chat/threads/'+encodeURIComponent(id)+'/content');
            if(id===current?.id&&busy)throw Error(cn?'会话正在执行，请稍后再试。':'Session is busy. Try again later.');
            const path='/v1/mobile/chat/threads/'+encodeURIComponent(id);
            if(action==='delete'){
                const runs=await request(path+(agentEnabled?'/agent-runs':'/turns'));
                if((runs.items||[]).some(run=>!['completed','failed','cancelled','expired'].includes(run.status)))
                    throw Error(cn?'该会话仍有未结束任务，请先处理或停止任务。':'This session has unfinished tasks. Resolve or stop them first.');
            }
            const changed=await request(path+'/manage',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,expected_revision:loaded.thread.revision,...(action==='rename'?{title:nextTitle}:{})})});
            if(action==='rename'){
                threads=threads.map(t=>t.id===id?changed:t);
                if(current?.id===id){current=changed;content=loaded;content.thread=changed;title.textContent=changed.title;renderMessages();}
                renderThreads();
            }else{
                threads=threads.filter(t=>t.id!==id);threadModels.delete(id);
                if(current?.id===id){messageActions?.stop();mobileAgent.stop();current=null;content=null;
                    if(threads.length)await loadContent(threads[0]);else await newThread();
                }else renderThreads();
            }
        }catch(error){notify(error.message);}finally{managingThread=false;}
    }

    function chooseModel(saved, inherited) {
        const available = new Set(Array.from(model.options, option => option.value).filter(Boolean));
        return [saved, inherited, apiDefaultModel].find(id => id && available.has(id)) || '';
    }

    async function loadContent(thread) {
        if (busy && mode !== 'agent') return;
        messageActions?.stop();
        mobileAgent.stop();
        current = thread;
        title.textContent = thread.title || 'New chat';
        renderThreads();
        drawer.classList.remove('is-open');
        drawer.setAttribute('aria-hidden', 'true');
        working('Loading session', 'Syncing with this Mac', 20);
        try {
            const loaded = await request('/v1/mobile/chat/threads/' + encodeURIComponent(thread.id) + '/content');
            if(current?.id!==thread.id)return;
            content=loaded;
            current = content.thread;
            const saved = threadModels.get(current.id) || content.session_metadata?.mobile_model_id;
            model.value = chooseModel(saved, '');
            if (model.value) lastActiveModel = model.value;
            if (typeof modelExplicit !== 'undefined') modelExplicit = content.session_metadata?.mobile_model_explicit ?? Boolean(saved);
            if(typeof content.session_metadata?.agentMode==='boolean')setMode(content.session_metadata.agentMode?'agent':'chat');
            else {
                const messages = content.messages || [];
                const legacyAgent = messages.some(message => message.metadata?.agent_run_id || message.metadata?._agentRunId);
                setMode(agentEnabled && (signedAgent || !messages.length || legacyAgent) ? 'agent' : 'chat');
            }
            title.textContent = current.title || 'New chat';
            renderMessages();
            if (typeof mobileAgent !== 'undefined') await mobileAgent.restore(current.id);
            if (!signedAgent) await restoreDirectTurn().catch(error => notify(error.message));
        } finally { idle(); }
    }

    async function refreshThreads(preferredId) {
        const payload = await request('/v1/mobile/chat/threads');
        threads = payload.items || [];
        renderThreads();
        const selected = threads.find((item) => item.id === preferredId)
            || threads.find((item) => item.id === current?.id) || threads[0];
        if (selected) await loadContent(selected);
        else await newThread();
    }

    async function newThread() {
        if (busy && mode !== 'agent') return;
        mobileAgent.stop();
        working('Creating session', 'Saving on this Mac', 18);
        try {
            const thread = await request('/v1/mobile/chat/threads', {
                method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                body: JSON.stringify({ title: '', session_metadata: { agentMode: agentEnabled, mobile_model_id: chooseModel('', model.value || lastActiveModel) } }),
            });
            threads.unshift(thread);
            await loadContent(thread);
            input.focus();
        } catch (error) { notify(error.message); idle(); }
    }

    async function loadModels() {
        try {
            const payload = await request('/v1/mobile/models', { cache: 'no-store' });
            const items = (payload.data || []).filter((item) => {
                if (!item?.id || item.is_hidden || item.load_failed || item.checkpoint_ready === false) return false;
                const type = String(item.model_type || item.modelType || '').toLowerCase();
                if (type.startsWith('audio_') || ['embedding','reranker','image_generation','video_generation','text_to_speech','speech_to_text'].includes(type)) return false;
                if (item.source_type === 'fusion' || item.owned_by === 'ai2apps-fusion') return true;
                const caps = item.capabilities;
                if (Array.isArray(caps)) {
                    const names = caps.map(name => String(name).toLowerCase());
                    if (names.some(name => ['conversation','chat','chat_completions'].includes(name))) return true;
                    if (names.some(name => ['audio_generation','image_generation','video_generation','speech_to_text','text_to_speech','text_to_video','image_to_video','synchronized_audio','embedding','reranking'].includes(name))) return false;
                } else if (caps && typeof caps === 'object') {
                    if (['conversation','chat','chatCompletions','chat_completions'].some(name => caps[name] === true)) return true;
                    if (caps.text === false || ['imageGeneration','videoGeneration','speechGeneration','speechRecognition'].some(name => caps[name] === true && caps.text !== true)) return false;
                }
                return true;
            });
            const unique = new Map(items.map(item => [item.id, item]));
            if (apiDefaultModel && !unique.has(apiDefaultModel)) {
                const original = unique.get(apiDefaultModel.replace('cloud/ai2apps/', 'cloud/'));
                if (original) unique.set(apiDefaultModel, {...original, id:apiDefaultModel, display_name:(original.display_name || original.name || original.id) + ' (API Default)', identity:null});
            }
            items.splice(0, items.length, ...Array.from(unique.values()).sort((a,b) =>
                (Number(!!b.is_favorite)-Number(!!a.is_favorite)) ||
                (a.display_name || a.identity?.displayName || a.name || a.id).localeCompare(b.display_name || b.identity?.displayName || b.name || b.id, undefined, {sensitivity:'base'})));
            if (typeof modelCatalog !== 'undefined') modelCatalog = items;
            model.innerHTML = '<option value="" selected>Choose a chat model</option>' + items.map((item) => '<option value="' + escapeHtml(item.id) + '">' + escapeHtml(item.identity?.displayName || item.display_name || item.name || item.id) + '</option>').join('');
            if (!items.length) model.innerHTML = '<option value="">No models available</option>';
        } catch (error) {
            model.innerHTML = '<option value="">Models unavailable</option>';
            notify(error.message);
        }
    }

    async function loadAgents() {
        try {
            const payload = await request('/v1/mobile/agents');
            const items = (payload.items || []).filter((item) => item.status === 'enabled' && item.discoverable);
            const general = items.find((item) => item.agent_key === 'ai2apps.general-agent');
            agentKey = general?.agent_key || '';
        } catch (error) { agentKey = ''; }
    }

    function setMode(next) {
        if (busy || (next === 'agent' && !agentEnabled)) return;
        mode = next;
        if (mode === 'agent' && !modelExplicit) {
            model.value = window.AI2AppsConversationModelPolicy.agentDefault(modelCatalog, '', []) || '';
            if (!model.value) notify('没有声明支持可靠工具调用的中等复杂度模型，请明确选择模型。');
        }
        root.querySelectorAll('[data-mobile-chat-mode]').forEach((button) => button.classList.toggle('is-active', button.dataset.mobileChatMode === mode));
        model.hidden = false;
        input.placeholder = mode === 'agent' ? 'Give the Agent a task' : 'Message AI2Apps';
    }

    function fileData(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(new Error('Could not read ' + file.name));
            reader.readAsDataURL(file);
        });
    }

    function renderAttachments() {
        attachmentsView.hidden = !attachments.length;
        attachmentsView.innerHTML = attachments.map((item, index) => (
            '<div class="mchat-attachment"><i data-lucide="file"></i><span>' + escapeHtml(item.file.name) +
            '</span><button type="button" data-remove-attachment="' + index + '" aria-label="Remove"><i data-lucide="x"></i></button></div>'
        )).join('');
        icons();
    }

    async function addFiles(files) {
        if (busy) return notify('Please wait for the current upload or task');
        const selected = Array.from(files || []);
        if (attachments.length + selected.length > 5) return notify('Up to 5 attachments per message');
        for (const file of selected) {
            if (!file.size || file.size > 8 * 1024 ** 3) { notify(file.name + ' must be between 1 byte and 8 GiB'); continue; }
            attachments.push({ file }); // Keep the File/Blob; never read a whole video into memory.
        }
        fileInput.value = '';
        renderAttachments();
    }

    async function uploadAttachment(item, sessionId = current.id) {
        if (item.uploaded && item.sessionId === sessionId) return item.uploaded;
        const base = '/v1/mobile/chat/threads/' + encodeURIComponent(sessionId) + '/uploads';
        working('Uploading to Gallery', item.file.name + ' · 0%', 0);
        const upload = await request(base, {method:'POST', headers:{'Content-Type':'application/json'},
            body:JSON.stringify({filename:item.file.name, media_type:item.file.type || 'application/octet-stream', size_bytes:item.file.size})});
        let offset = 0;
        try {
            while (offset < item.file.size) {
                const end = Math.min(item.file.size, offset + Math.min(upload.chunk_bytes, 4 * 1024 ** 2));
                const result = await request(base + '/' + upload.id + '?offset=' + offset,
                    {method:'PUT', headers:{'Content-Type':'application/octet-stream'},body:item.file.slice(offset,end)});
                if (result.received_bytes !== end) throw Error('Upload progress mismatch');
                offset = end;
                const percent = Math.floor(offset / item.file.size * 100);
                working('Uploading to Gallery', item.file.name + ' · ' + percent + '% (' + offset + ' / ' + item.file.size + ' bytes)', percent);
            }
            working('Saving Gallery material', item.file.name, 100);
            item.uploaded = await request(base + '/' + upload.id + '/complete', {method:'POST'});
            item.sessionId = sessionId;
            return item.uploaded;
        } catch (error) {
            await request(base + '/' + upload.id + '/cancel', {method:'POST'}).catch(()=>{});
            throw error;
        }
    }

    async function buildContent(text) {
        if (!attachments.length) return text;
        const parts = [];
        for (const item of attachments) {
            const uploaded = await uploadAttachment(item);
            parts.push({type:'file',file:{filename:item.file.name,file_id:uploaded.id,storage:'reference',
                gallery_asset_id:uploaded.metadata?.gallery_asset_id}});
            // Preserve bounded vision input compatibility; video is always a file reference.
            if (item.file.type.startsWith('image/') && item.file.size <= 10 * 1024 ** 2)
                parts.push({type:'image_url',image_url:{url:await fileData(item.file)}});
        }
        if (text) parts.push({ type: 'text', text });
        return parts;
    }

    async function persist(messages, proposedTitle) {
        const payload = await request('/v1/mobile/chat/threads/' + encodeURIComponent(current.id) + '/content', {
            method: 'PUT', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify({
                expected_revision: content.thread.revision,
                title: proposedTitle == null ? current.title : proposedTitle,
                session_metadata: Object.assign({}, content.session_metadata || {}, { agentMode: mode === 'agent', last_surface: 'mobile', mobile_model_id: model.value, mobile_model_explicit: modelExplicit }),
                messages: messages.map((item) => ({ role: item.role, content: item.content, metadata: item.metadata || {} })),
            }),
        });
        content = payload;
        current = payload.thread;
        title.textContent = current.title || 'New chat';
        const index = threads.findIndex((item) => item.id === current.id);
        if (index >= 0) threads[index] = current;
        renderThreads();
    }

    async function directChat(text, richContent) {
        const userMessage = { role: 'user', content: richContent, metadata: { execution_mode: 'chat', surface: 'mobile' } };
        const nextMessages = (content.messages || []).concat(userMessage);
        const proposedTitle = current.title ? current.title : text.slice(0, 48);
        working('Saving message', 'Sharing with the Mac Chat App', 28);
        await persist(nextMessages, proposedTitle);
        const threadId = current.id;
        try {
            const run = await request('/v1/mobile/chat/threads/' + encodeURIComponent(threadId) + '/turns', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({request_id: crypto.randomUUID(), expected_revision: content.thread.revision,
                    request: {model: model.value, messages: nextMessages.map(({role,content}) => ({role,content})), temperature: null}}),
            });
            await observeDirectTurn(run);
        } catch (error) {
            // An uncertain POST may already have committed. Recover by reading;
            // never replay generation with a new key after a network failure.
            await restoreDirectTurn();
            throw error;
        }
    }

    async function restoreDirectTurn() {
        if (signedAgent || !current || directTurnId) return;
        const threadId = current.id;
        const state = await request('/v1/mobile/chat/threads/' + encodeURIComponent(threadId) + '/turns');
        if (current?.id !== threadId) return;
        const items = state.items || [];
        if (items.length) {
            content = await request('/v1/mobile/chat/threads/' + encodeURIComponent(threadId) + '/content');
            if (current?.id !== threadId) return;
            current = content.thread;
            renderMessages();
        }
        const active = items.find(run => !terminalRunStates.has(run.status));
        if (active) void observeDirectTurn(active).catch(error => notify(error.message));
    }

    async function observeDirectTurn(run) {
        const threadId = run.session_id;
        const generation = ++directGeneration;
        directTurnId = run.id;
        busy = true; send.disabled = false; model.disabled = true;
        send.textContent = '■'; send.setAttribute('aria-label', 'Stop reply');
        const answer = addMessage('assistant', '');
        try {
            while (generation === directGeneration && current?.id === threadId) {
                if (terminalRunStates.has(run.status)) {
                    const latest = await request('/v1/mobile/chat/threads/' + encodeURIComponent(threadId) + '/content');
                    if (generation !== directGeneration || current?.id !== threadId) return;
                    content = latest; current = latest.thread; renderMessages();
                    if (run.status === 'failed' || run.status === 'interrupted') notify(run.error?.message || run.status);
                    return;
                }
                const line = run.status_line || {};
                renderMessageBody(answer.copy, line.content?.completion_preview?.content || '', true);
                working(line.text || 'AI is processing', '回复正在后台生成，可离开此页面。', 50);
                await new Promise(resolve => setTimeout(resolve, 750));
                if (generation !== directGeneration) return;
                run = await request('/v1/mobile/chat/threads/' + encodeURIComponent(threadId) + '/turns/' + encodeURIComponent(run.id));
            }
        } finally {
            if (generation === directGeneration) {
                directTurnId = null;
                busy = false; send.disabled = false; model.disabled = false; idle();
                send.innerHTML = sendMarkup; send.setAttribute('aria-label', sendLabel || 'Send'); icons();
            }
        }
    }

    async function readChatReply(response, update) {
        let generated = '';
        function consume(payload) {
            if (payload.error) throw new Error(typeof payload.error === 'string' ? payload.error : payload.error.message || 'AI 回复失败，请重试。');
            const choice = payload.choices?.[0];
            const delta = choice?.delta || choice?.message || {};
            const cloud = delta.ai2apps_cloud;
            if (cloud?.phase === 'failed') {
                const failure = cloud.error || cloud;
                throw new Error(failure.message || failure.code || 'Cloud 请求失败，请重试。');
            }
            if (typeof delta.reasoning_content === 'string') update('', true);
            const text = typeof delta.content === 'string' ? delta.content
                : Array.isArray(delta.content) ? delta.content.filter(part => part?.type === 'text' || part?.type === 'output_text').map(part => typeof part.text === 'string' ? part.text : '').join('') : '';
            if (text) {
                generated += text;
                update(generated, false);
            }
        }
        if ((response.headers.get('content-type') || '').includes('application/json')) {
            consume(await response.json());
        } else {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            function line(value) {
                if (!value.startsWith('data:')) return;
                const data = value.slice(5).trim();
                if (!data || data === '[DONE]') return;
                let payload;
                try { payload = JSON.parse(data); }
                catch (_) { throw new Error('AI 回复格式异常，请重试。'); }
                consume(payload);
            }
            try {
                while (true) {
                    const result = await reader.read();
                    buffer += result.done ? decoder.decode() : decoder.decode(result.value, {stream:true});
                    const lines = buffer.split('\n');
                    buffer = lines.pop();
                    for (const value of lines) line(value);
                    if (result.done) { if (buffer) line(buffer); break; }
                }
            } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
        }
        if (!generated.trim()) throw new Error('AI 未返回可显示的回复，请重试或更换模型。');
        return generated;
    }

    async function agentRun(text, richContent) {
        if (!agentEnabled) throw Error('此连接尚未开放 Agent');
        list.appendChild(runsContainer);
        working('Starting Agent', 'Creating a durable run', 20);
        const runInput = { model: model.value };
        if (typeof richContent === 'string') runInput.prompt = text;
        else runInput.content = richContent;
        const inputNode=addMessage('user',text,{agent:'Agent'}).node;
        const run=await mobileAgent.start(current.id, runInput, agentKey, crypto.randomUUID());
        inputNode.dataset.messageRunId=run.id;
        mobileAgent.placeCards();
        idle();
    }

    async function submit() {
        const text = input.value.trim();
        if ((!text && !attachments.length) || busy || !current) return;
        if (mode === 'chat' && !model.value) return notify('Choose a model first');
        if (mode === 'agent' && !model.value) return notify('Choose an Agent model first');
        if (mode === 'agent' && !agentKey) return notify('通用 Agent 暂不可用，请稍后重试');
        busy = true;
        send.disabled = true;
        model.disabled = true;
        input.value = '';
        input.style.height = 'auto';
        const selectedAttachments = attachments.slice();
        try {
            const richContent = await buildContent(text);
            if (mode === 'chat') {
                addMessage('user', text, { files: selectedAttachments.map((item) => item.file.name) });
                await directChat(text, richContent);
            } else await agentRun(text, richContent);
            attachments = [];
            renderAttachments();
        } catch (error) {
            if (!input.value) input.value = text;
            try { await refreshThreads(current?.id); } catch (_) {}
            addMessage('error', error.message, { error: true });
            notify(error.message);
        } finally {
            busy = !!directTurnId || [...mobileAgent.runs.values()].some(run => !window.AI2AppsMobileAgentChat.terminal.has(run.status));
            send.disabled = busy && !directTurnId;
            model.disabled = busy;
            idle();
            input.focus();
        }
    }

    model.addEventListener('change', async () => {
        modelExplicit = true;
        if (signedAgent) { if (current) threadModels.set(current.id,model.value);lastActiveModel=model.value;return; }
        if (busy || !current || !content) return;
        const previous = content.session_metadata?.mobile_model_id || '';
        busy = true;
        model.disabled = true;
        try {
            await persist(content.messages || []);
            threadModels.set(current.id, model.value);
            lastActiveModel = model.value;
        } catch (error) {
            model.value = chooseModel(previous, '');
            notify(error.message);
        } finally { busy = false; model.disabled = false; }
    });

    send.addEventListener('click', event => {
        if (!directTurnId || !current) return;
        event.preventDefault();
        void request('/v1/mobile/chat/threads/' + encodeURIComponent(current.id) + '/turns/' + encodeURIComponent(directTurnId) + '/cancel', {method:'POST'})
            .catch(error => notify(error.message));
    });
    form.addEventListener('submit' , (event) => { event.preventDefault(); submit(); });
    input.addEventListener('compositionstart', () => { composing = true; });
    input.addEventListener('compositionend', () => { composing = false; compositionEndedAt = performance.now(); });
    input.addEventListener('keydown', (event) => {
        if (event.key !== 'Enter' || event.shiftKey) return;
        const justCommitted = performance.now() - compositionEndedAt < 100;
        if (composing || event.isComposing || event.keyCode===229 || justCommitted) return;
        event.preventDefault(); submit();
    });
    input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 112) + 'px'; });
    $('[data-mobile-chat-sessions]').addEventListener('click', () => { drawer.classList.add('is-open'); drawer.setAttribute('aria-hidden', 'false'); });
    root.querySelectorAll('[data-mobile-chat-close]').forEach((button) => button.addEventListener('click', () => { drawer.classList.remove('is-open'); drawer.setAttribute('aria-hidden', 'true'); }));
    root.querySelectorAll('[data-mobile-chat-new]').forEach((button) => button.addEventListener('click', newThread));
    root.querySelectorAll('[data-mobile-chat-mode]').forEach((button) => button.addEventListener('click', () => setMode(button.dataset.mobileChatMode)));
    $('[data-mobile-chat-attach]').addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', () => addFiles(fileInput.files));
    attachmentsView.addEventListener('click', (event) => { const button = event.target.closest('[data-remove-attachment]'); if (!button || busy) return; attachments.splice(Number(button.dataset.removeAttachment), 1); renderAttachments(); });
    sessionList.addEventListener('click', (event) => {
        const action=event.target.closest('[data-thread-action]');
        if(action){event.stopPropagation();action.closest('details').open=false;void manageThread(action.dataset.threadAction,action.dataset.threadActionId);return;}
        const button=event.target.closest('button[data-thread-id]');const thread=threads.find(item=>item.id===button?.dataset.threadId);
        if(thread&&!managingThread)loadContent(thread).catch(error=>notify(error.message));
    });
    sessionList.addEventListener('toggle',event=>{if(event.target.open)sessionList.querySelectorAll('details[open]').forEach(menu=>{if(menu!==event.target)menu.open=false;});},true);
    root.addEventListener('click',event=>{if(!event.target.closest('.mchat-session-menu'))sessionList.querySelectorAll('details[open]').forEach(menu=>menu.open=false);});

    let started=false,initialization=null;
    window.AI2AppsMobileOpenChatContext=async seed=>{
        seed=window.AI2AppsChatContext.normalize(seed);
        if(!agentEnabled)throw Error('An authorized Agent connection is required');
        if(!started)await initialize();else if(initialization)await initialization;
        const recipient=await request('/v1/mobile/chat/state');
        seed=window.AI2AppsChatContext.forRecipient(seed,recipient.app_instance_id);
        const created=await request('/v1/mobile/chat/threads',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(seed)});
        const id=created.id;
        const loaded=await request('/v1/mobile/chat/threads/'+encodeURIComponent(id)+'/content');
        if(loaded.thread?.id!==id||loaded.thread.status!=='active')throw Error('Chat thread is unavailable');
        await loadContent(loaded.thread);
        if(current?.id!==id)throw Error('Chat thread could not be opened');
        setMode('agent');return id;
    };
    const notificationRoute = new URLSearchParams(location.hash.slice(1));
    function reportNotification(status) {
        const id=notificationRoute.get('notification-id');
        if(!id)return;
        if(inlineShell)window.__ai2appsNotificationStatus={id,status};
        else window.parent.postMessage({type:'ai2apps.notification.result',id,status,mountToken:notificationRoute.get('ai2apps-mount')},'*');
    }
    async function restoreNotificationThread() {
        if(!notificationRoute.get('notification-id'))return false;
        const route=notificationRoute.get('notification-route');
        if(!['conversation','interaction'].includes(route))throw Error('Unsupported conversation notification');
        const id=notificationRoute.get(route==='interaction'?'notification-session':'notification-resource');
        if(!id)throw Error('Notification conversation is missing');
        // The content endpoint enforces the current actor AND client scope.
        // Never silently select another thread if the original is unavailable.
        const loaded=await request('/v1/mobile/chat/threads/'+encodeURIComponent(id)+'/content');
        if(loaded.thread?.id!==id || loaded.thread.status==='deleted' || loaded.thread.status==='archived')throw Error('Notification conversation is unavailable');
        await loadContent(loaded.thread);
        if(current?.id!==id || content?.thread?.id!==id)throw Error('Conversation could not be displayed');
        if(route==='interaction'){
            if(!agentEnabled)throw Error('此入口无法处理 Agent 交互，请使用已授权的 Agent 连接。');
            setMode('agent');
            await mobileAgent.focusInteraction(id,notificationRoute.get('notification-run'),notificationRoute.get('notification-resource'));
        }
        reportNotification('opened');
        return true;
    }
    function initialize(){started=true;
    return initialization=(signedAgent ? window.AI2AppsAgentConnection.resume().then(ok => { if (!ok) throw Error('请先扫描 Desktop Agent 二维码建立连接。'); return request('/v1/mobile/chat/state'); }) : request('/v1/mobile/chat/state'))
        .then(async (state) => {
            apiDefaultModel = state.api_default_model_id || '';
            await Promise.all([loadModels(), agentEnabled ? loadAgents() : Promise.resolve()]);
            setMode(agentEnabled ? 'agent' : 'chat');
            if (signedAgent) {
                const chatButton = root.querySelector('[data-mobile-chat-mode=chat]');
                if (chatButton) { chatButton.disabled = true; chatButton.title = '普通 Chat 使用原有 Owner 入口'; }
            }
            if(await restoreNotificationThread())return;
            return refreshThreads(state.selected_thread_id);
        })
        .catch((error) => { reportNotification('failed');started=false;idle();notify(error.message);const option=document.createElement('option');option.value='';option.textContent='连接未完成：'+error.message;model.replaceChildren(option); });
    }
    if(inlineShell){window.addEventListener('ai2apps-mobile-chat-visible',event=>{
        if(!event.detail){messageActions?.stop();mobileAgent.stop();return;}
        if(!started)void initialize();else if(current)loadContent(current).catch(error=>notify(error.message));
    });}else void initialize();
    const resumeAgentState = () => { if(signedAgent&&!started&&(!inlineShell||!root.closest('[data-mobile-inline-agent]').hidden)&&document.visibilityState!=='hidden'){void initialize();return;} if (current && (!inlineShell||!root.closest('[data-mobile-inline-agent]').hidden) && document.visibilityState !== 'hidden') { if (agentEnabled && !directTurnId) mobileAgent.restore(current.id); if (!signedAgent) void restoreDirectTurn().catch(error => notify(error.message)); } };
    window.addEventListener('online', resumeAgentState);
    document.addEventListener('visibilitychange', resumeAgentState);
    window.addEventListener('pagehide', () => { messageActions?.stop();mobileAgent.stop(); directGeneration++; directTurnId = null; });
    document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')messageActions?.stop();});
    window.addEventListener('pageshow', event => { if (event.persisted) resumeAgentState(); });
    icons();
})();
