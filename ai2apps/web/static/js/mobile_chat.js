(function () {
    'use strict';

    const root = document.querySelector('[data-mobile-chat]');
    if (!root) return;
    const $ = (selector) => root.querySelector(selector);
    const list = $('[data-mobile-chat-list]');
    const form = $('[data-mobile-chat-form]');
    const input = $('[data-mobile-chat-input]');
    const model = $('[data-mobile-chat-model]');
    const agent = $('[data-mobile-chat-agent]');
    const send = $('[data-mobile-chat-send]');
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

    let threads = [];
    let current = null;
    let apiDefaultModel = "";
    let lastActiveModel = "";
    const threadModels = new Map();
    let content = null;
    let mode = 'chat';
    let attachments = [];
    let busy = false;
    let composing = false;
    let compositionEndedAt = -Infinity;
    let toastTimer = null;
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
        const response = await fetch(url, Object.assign({
            credentials: 'same-origin', headers: { Accept: 'application/json' },
        }, options || {}));
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = payload.detail;
            throw new Error(typeof detail === 'string' ? detail : detail?.message || 'Request failed');
        }
        return payload;
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
            if (part?.type === 'image_url') return ['Image'];
            if (part?.type === 'file') return [part.file?.filename || 'Attachment'];
            return [];
        });
    }

    function addMessage(role, text, options) {
        const empty = list.querySelector('.mchat-empty');
        if (empty) empty.remove();
        const node = document.createElement('div');
        node.className = 'mchat-message ' + role + (options?.error ? ' error' : '');
        if (options?.agent) {
            const meta = document.createElement('span');
            meta.className = 'mchat-message-meta';
            meta.textContent = options.agent;
            node.appendChild(meta);
        }
        const copy = document.createElement('span');
        copy.textContent = text || '';
        node.appendChild(copy);
        (options?.files || []).forEach((name) => {
            const note = document.createElement('span');
            note.className = 'mchat-file-note';
            note.textContent = '📎 ' + name;
            node.appendChild(note);
        });
        list.appendChild(node);
        list.scrollTop = list.scrollHeight;
        return { node, copy };
    }

    function renderMessages() {
        list.innerHTML = '';
        const messages = content?.messages || [];
        if (!messages.length) {
            list.innerHTML = '<div class="mchat-empty"><i data-lucide="sparkles"></i><h1>Start a conversation</h1><p>This conversation stays on this client.</p></div>';
            icons();
            return;
        }
        messages.forEach((message) => addMessage(message.role, messageText(message), {
            files: messageFiles(message),
            agent: message.metadata?.agent_run_id ? 'Agent' : null,
        }));
    }

    function renderThreads() {
        sessionList.innerHTML = threads.map((thread) => (
            '<button class="mchat-session' + (thread.id === current?.id ? ' is-active' : '') +
            '" type="button" data-thread-id="' + escapeHtml(thread.id) + '"><strong>' +
            escapeHtml(thread.title || 'New chat') + '</strong><small>' +
            new Date(thread.updated_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) +
            '</small></button>'
        )).join('');
    }

    function chooseModel(saved, inherited) {
        const available = new Set(Array.from(model.options, option => option.value).filter(Boolean));
        return [saved, inherited, apiDefaultModel].find(id => id && available.has(id)) || '';
    }

    async function loadContent(thread) {
        if (busy) return;
        current = thread;
        title.textContent = thread.title || 'New chat';
        renderThreads();
        drawer.classList.remove('is-open');
        drawer.setAttribute('aria-hidden', 'true');
        working('Loading session', 'Syncing with this Mac', 20);
        try {
            content = await request('/v1/mobile/chat/threads/' + encodeURIComponent(thread.id) + '/content');
            current = content.thread;
            const saved = threadModels.get(current.id) || content.session_metadata?.mobile_model_id;
            model.value = chooseModel(saved, '');
            if (model.value) lastActiveModel = model.value;
            title.textContent = current.title || 'New chat';
            renderMessages();
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
        if (busy) return;
        working('Creating session', 'Saving on this Mac', 18);
        try {
            const thread = await request('/v1/mobile/chat/threads', {
                method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                body: JSON.stringify({ title: '', session_metadata: { mobile_model_id: chooseModel('', model.value || lastActiveModel) } }),
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
            agent.innerHTML = items.map((item) => '<option value="' + escapeHtml(item.agent_key) + '">' + escapeHtml(item.display_name) + '</option>').join('');
            const general = items.find((item) => item.agent_key === 'ai2apps.general-agent');
            if (general) agent.value = general.agent_key;
            if (!items.length) agent.innerHTML = '<option value="">No Agents available</option>';
        } catch (error) { agent.innerHTML = '<option value="">Agents unavailable</option>'; }
    }

    function setMode(next) {
        mode = next;
        root.querySelectorAll('[data-mobile-chat-mode]').forEach((button) => button.classList.toggle('is-active', button.dataset.mobileChatMode === mode));
        model.hidden = mode === 'agent';
        agent.hidden = mode !== 'agent';
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
        const selected = Array.from(files || []);
        if (attachments.length + selected.length > 5) return notify('Up to 5 attachments per message');
        for (const file of selected) {
            if (file.size > 25 * 1024 * 1024) { notify(file.name + ' exceeds 25 MiB'); continue; }
            try { attachments.push({ file, data: await fileData(file) }); }
            catch (error) { notify(error.message); }
        }
        fileInput.value = '';
        renderAttachments();
    }

    async function buildContent(text) {
        if (!attachments.length) return text;
        const parts = [];
        for (const item of attachments) {
            const mime = item.file.type || 'application/octet-stream';
            if (mime.startsWith('image/')) {
                parts.push({ type: 'image_url', image_url: { url: item.data } });
            } else {
                working('Uploading attachment', item.file.name, 22);
                const uploaded = await request('/v1/mobile/chat/threads/' + encodeURIComponent(current.id) + '/attachments', {
                    method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
                    body: JSON.stringify({ filename: item.file.name, media_type: mime, data: item.data }),
                });
                parts.push({ type: 'file', file: { filename: item.file.name, file_data: item.data, file_id: uploaded.id } });
            }
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
                session_metadata: Object.assign({}, content.session_metadata || {}, { last_surface: 'mobile', mobile_model_id: model.value }),
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
        const answer = addMessage('assistant', '');
        working('AI is processing', 'Waiting for the model', 42);
        const response = await fetch('/v1/mobile/chat/completions', {
            method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
            body: JSON.stringify({ model: model.value, messages: nextMessages.map(({ role, content }) => ({ role, content })), stream: true, temperature: null }),
        });
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.detail || 'Chat request failed');
        }
        let generated = '';
        try {
            generated = await readChatReply(response, (text, reasoning) => {
                if (reasoning) working('AI is reasoning', 'Planning the response', 58);
                else {
                    answer.copy.textContent = text;
                    working('AI is responding', 'Streaming from this Mac', 76);
                    list.scrollTop = list.scrollHeight;
                }
            });
            await persist(nextMessages.concat({ role: 'assistant', content: generated, metadata: { surface: 'mobile' } }));
        } catch (error) {
            answer.node.remove();
            throw error;
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
        const optimistic = addMessage('user', text, { files: attachments.map((item) => item.file.name), agent: 'Agent task' });
        void optimistic;
        working('Starting Agent', 'Creating a durable run', 20);
        const runInput = { model: model.value || undefined };
        if (typeof richContent === 'string') runInput.prompt = text;
        else runInput.content = richContent;
        let run = await request('/v1/mobile/chat/threads/' + encodeURIComponent(current.id) + '/agent-runs', {
            method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
            body: JSON.stringify({ agent: agent.value || 'ai2apps.general-agent', input: runInput }),
        });
        while (!terminalRunStates.has(run.status)) {
            const line = run.status_line || {};
            working(line.text || 'Agent is working', run.status.replaceAll('_', ' '), line.progress == null ? 45 : line.progress * 100);
            await new Promise((resolve) => setTimeout(resolve, 750));
            run = await request('/v1/mobile/agent-runs/' + encodeURIComponent(run.id));
        }
        if (run.status !== 'completed') throw new Error(run.error?.message || 'Agent run ' + run.status);
        working('Agent completed', 'Syncing the result', 96);
        content = await request('/v1/mobile/chat/threads/' + encodeURIComponent(current.id) + '/content');
        current = content.thread;
        renderMessages();
    }

    async function submit() {
        const text = input.value.trim();
        if ((!text && !attachments.length) || busy || !current) return;
        if (mode === 'chat' && !model.value) return notify('Choose a model first');
        if (mode === 'agent' && !agent.value) return notify('Choose an Agent first');
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
            try { await refreshThreads(current?.id); } catch (_) {}
            addMessage('error', error.message, { error: true });
            notify(error.message);
        } finally {
            busy = false;
            send.disabled = false;
            model.disabled = false;
            idle();
            input.focus();
        }
    }

    model.addEventListener('change', async () => {
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
    attachmentsView.addEventListener('click', (event) => { const button = event.target.closest('[data-remove-attachment]'); if (!button) return; attachments.splice(Number(button.dataset.removeAttachment), 1); renderAttachments(); });
    sessionList.addEventListener('click', (event) => { const button = event.target.closest('[data-thread-id]'); const thread = threads.find((item) => item.id === button?.dataset.threadId); if (thread) loadContent(thread).catch((error) => notify(error.message)); });

    request('/v1/mobile/chat/state')
        .then(async (state) => {
            apiDefaultModel = state.api_default_model_id || '';
            await Promise.all([loadModels(), document.body.dataset.ownerHome ? Promise.resolve() : loadAgents()]);
            return refreshThreads(state.selected_thread_id);
        })
        .catch((error) => { idle(); notify(error.message); });
    icons();
})();
