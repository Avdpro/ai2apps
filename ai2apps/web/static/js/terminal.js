(function () {
    'use strict';

    const app = document.querySelector('.terminal-app');
    const host = document.getElementById('terminal-host');
    const empty = document.querySelector('.terminal-empty');
    const list = document.querySelector('.terminal-session-list');
    const dialog = document.querySelector('.new-terminal-dialog');
    const form = document.querySelector('.new-terminal-form');
    const closeDialog = document.querySelector('.close-terminal-dialog');
    const closeForm = document.querySelector('.close-terminal-form');
    const closeTerminalName = document.querySelector('[data-close-terminal-name]');
    const assistantButton = document.querySelector('[data-action="assistant"]');
    const assistantPanel = document.querySelector('.terminal-assistant');
    const assistantFrame = document.querySelector('[data-terminal-assistant-frame]');
    const assistantSession = document.querySelector('[data-assistant-session]');
    const status = document.querySelector('[data-status]');
    const currentTitle = document.querySelector('[data-current-title]');
    const currentCwd = document.querySelector('[data-current-cwd]');
    const closeButton = document.querySelector('[data-action="close"]');
    const sessions = new Map();
    let activeId = null;
    let socket = null;
    let reconnectTimer = null;
    let intentionalDisconnect = false;
    let reconnectAttempts = 0;
    let assistantLoaded = false;
    let assistantContextTimer = null;
    const maxAutoReconnects = 5;

    const terminal = new Terminal({
        cursorBlink: true,
        cursorStyle: 'block',
        fontFamily: 'SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        fontSize: 13,
        lineHeight: 1.18,
        scrollback: 10000,
        allowProposedApi: false,
        theme: {
            background: '#171719', foreground: '#e4e4e7', cursor: '#f4f4f5',
            selectionBackground: '#3f3f46', black: '#27272a', red: '#f87171',
            green: '#86efac', yellow: '#fde047', blue: '#93c5fd', magenta: '#d8b4fe',
            cyan: '#67e8f9', white: '#e4e4e7', brightBlack: '#71717a'
        }
    });
    const fitAddon = new FitAddon.FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(host);

    function iconify() {
        if (window.lucide) window.lucide.createIcons();
    }

    async function api(path, options) {
        const response = await fetch(path, Object.assign({
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' }
        }, options || {}));
        if (!response.ok) {
            let message = 'HTTP ' + response.status;
            try {
                const body = await response.json();
                message = body.detail && (body.detail.message || body.detail) || message;
            } catch (_) {}
            throw new Error(message);
        }
        return response.status === 204 ? null : response.json();
    }

    function basename(path) {
        const parts = String(path || '').split('/').filter(Boolean);
        return parts[parts.length - 1] || '/';
    }

    function renderSessions() {
        list.replaceChildren();
        Array.from(sessions.values()).forEach(function (session) {
            const row = document.createElement('button');
            row.type = 'button';
            row.className = 'session-row' + (session.id === activeId ? ' is-active' : '');
            row.dataset.sessionId = session.id;
            row.setAttribute('role', 'listitem');
            const icon = document.createElement('i');
            icon.dataset.lucide = 'square-terminal';
            const copy = document.createElement('span');
            copy.className = 'session-copy';
            const title = document.createElement('strong');
            title.textContent = session.title;
            const cwd = document.createElement('span');
            cwd.textContent = basename(session.cwd);
            copy.append(title, cwd);
            const state = document.createElement('span');
            state.className = 'session-state' + (session.status === 'running' ? '' : ' is-exited');
            row.append(icon, copy, state);
            row.addEventListener('click', function () { activate(session.id); });
            list.appendChild(row);
        });
        iconify();
    }

    function setConnection(label) {
        status.textContent = label;
    }

    function disconnect(intentional) {
        intentionalDisconnect = intentional;
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
        if (socket) {
            const previous = socket;
            socket = null;
            previous.close(1000, 'switching terminal');
        }
    }

    function socketUrl(sessionId) {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        return protocol + '//' + location.host + '/admin/api/terminal/sessions/' +
            encodeURIComponent(sessionId) + '/stream';
    }

    function connect(sessionId, manual) {
        if (!sessionId || sessionId !== activeId) return;
        if (manual) reconnectAttempts = 0;
        disconnect(false);
        intentionalDisconnect = false;
        setConnection('Connecting…');
        const connected = new WebSocket(socketUrl(sessionId));
        connected.binaryType = 'arraybuffer';
        socket = connected;
        connected.onopen = function () {
            if (socket !== connected) return;
            reconnectAttempts = 0;
            setConnection('Connected');
            resizeTerminal();
            terminal.focus();
        };
        connected.onmessage = function (event) {
            if (socket !== connected) return;
            if (event.data instanceof ArrayBuffer) {
                terminal.write(new Uint8Array(event.data));
                scheduleAssistantContext();
                return;
            }
            try {
                const message = JSON.parse(event.data);
                if (message.type === 'ready' && message.session) {
                    sessions.set(message.session.id, message.session);
                    renderSessions();
                } else if (message.type === 'exit') {
                    sessions.set(message.session.id, message.session);
                    renderSessions();
                    setConnection('Exited (' + message.exit_code + ')');
                } else if (message.type === 'error') {
                    setConnection(message.message || 'Terminal error');
                }
            } catch (_) {}
        };
        connected.onclose = function (event) {
            if (socket && socket !== connected) return;
            if (socket === connected) socket = null;
            if (sessionId !== activeId || intentionalDisconnect) return;
            setConnection(event.code === 4401 ? 'Authentication required' : 'Disconnected');
            const session = sessions.get(sessionId);
            if (session && session.status === 'running' && event.code !== 4401 && event.code !== 4404) {
                reconnectAttempts += 1;
                if (reconnectAttempts > maxAutoReconnects) {
                    setConnection('Connection unavailable');
                    return;
                }
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 15000);
                setConnection('Reconnecting…');
                reconnectTimer = setTimeout(function () { connect(sessionId, false); }, delay);
            }
        };
    }

    function activate(sessionId) {
        const session = sessions.get(sessionId);
        if (!session) return;
        activeId = sessionId;
        reconnectAttempts = 0;
        app.classList.remove('sidebar-open');
        terminal.reset();
        empty.hidden = true;
        currentTitle.textContent = session.title;
        currentCwd.textContent = session.cwd;
        closeButton.disabled = false;
        assistantButton.disabled = false;
        assistantButton.title = 'Terminal AI Assistant';
        renderSessions();
        connect(sessionId, false);
        scheduleAssistantContext();
    }

    function clearActive() {
        disconnect(true);
        activeId = null;
        terminal.reset();
        empty.hidden = false;
        currentTitle.textContent = 'No terminal';
        currentCwd.textContent = 'Select or create a session';
        closeButton.disabled = true;
        assistantButton.disabled = true;
        assistantButton.title = 'Select a terminal to use the AI Assistant';
        assistantSession.textContent = 'No terminal selected';
        clearTimeout(assistantContextTimer);
        assistantContextTimer = null;
        if (assistantLoaded && assistantFrame.contentWindow) {
            assistantFrame.contentWindow.postMessage({
                type: 'ai2apps.terminal.detach'
            }, location.origin);
        }
        setAssistantOpen(false);
        setConnection('Disconnected');
        renderSessions();
    }

    function resizeTerminal() {
        if (!activeId || empty.hidden === false) return;
        try { fitAddon.fit(); } catch (_) { return; }
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'resize', cols: terminal.cols, rows: terminal.rows }));
        }
    }

    function recentTranscript() {
        const buffer = terminal.buffer.active;
        const start = Math.max(0, buffer.length - 160);
        const lines = [];
        for (let index = start; index < buffer.length; index += 1) {
            const line = buffer.getLine(index);
            if (line) lines.push(line.translateToString(true));
        }
        return lines.join('\n').trimEnd().slice(-24000);
    }

    function sendAssistantContext() {
        clearTimeout(assistantContextTimer);
        assistantContextTimer = null;
        if (!assistantLoaded || !activeId || !assistantFrame.contentWindow) return;
        const session = sessions.get(activeId);
        if (!session) return;
        assistantSession.textContent = session.title + ' · ' + session.cwd;
        assistantFrame.contentWindow.postMessage({
            type: 'ai2apps.terminal.context',
            session: {
                id: session.id,
                title: session.title,
                cwd: session.cwd,
                status: session.status
            },
            transcript: recentTranscript()
        }, location.origin);
    }

    function scheduleAssistantContext() {
        if (!app.classList.contains('assistant-open')) return;
        clearTimeout(assistantContextTimer);
        assistantContextTimer = setTimeout(sendAssistantContext, 180);
    }

    function setAssistantOpen(open) {
        if (open && !activeId) return;
        app.classList.toggle('assistant-open', open);
        assistantPanel.setAttribute('aria-hidden', String(!open));
        assistantButton.setAttribute('aria-pressed', String(open));
        assistantButton.classList.toggle('is-active', open);
        if (open && !assistantLoaded) {
            assistantLoaded = true;
            assistantFrame.src = '/admin/chat?embedded=1&terminal_assistant=1';
        }
        if (open) scheduleAssistantContext();
        setTimeout(resizeTerminal, 240);
    }

    terminal.onData(function (data) {
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'input', data: data }));
        }
        scheduleAssistantContext();
    });
    const observer = new ResizeObserver(function () { resizeTerminal(); });
    observer.observe(host);

    async function loadSessions() {
        try {
            const result = await api('/admin/api/terminal/sessions');
            result.items.forEach(function (session) { sessions.set(session.id, session); });
            renderSessions();
            const running = result.items.find(function (session) { return session.status === 'running'; });
            const first = running || result.items[0];
            if (first) activate(first.id);
        } catch (error) {
            setConnection(error.message);
        }
    }

    async function createSession() {
        const data = new FormData(form);
        const errorHost = form.querySelector('.dialog-error');
        errorHost.textContent = '';
        try {
            fitAddon.fit();
            const session = await api('/admin/api/terminal/sessions', {
                method: 'POST',
                body: JSON.stringify({
                    title: data.get('title') || 'Terminal',
                    cwd: data.get('cwd') || null,
                    cols: Math.max(20, terminal.cols || 100),
                    rows: Math.max(5, terminal.rows || 30)
                })
            });
            sessions.set(session.id, session);
            dialog.close();
            activate(session.id);
        } catch (error) {
            errorHost.textContent = error.message;
        }
    }

    async function closeActive() {
        if (!activeId) return;
        const sessionId = activeId;
        try {
            await api('/admin/api/terminal/sessions/' + encodeURIComponent(sessionId), { method: 'DELETE' });
            sessions.delete(sessionId);
            const next = Array.from(sessions.values()).find(function (item) { return item.status === 'running'; }) || sessions.values().next().value;
            if (next) activate(next.id); else clearActive();
        } catch (error) {
            setConnection(error.message);
        }
    }

    function confirmCloseActive() {
        if (!activeId) return;
        const session = sessions.get(activeId);
        if (!session) return;
        closeTerminalName.textContent = session.title;
        closeDialog.showModal();
    }

    document.querySelectorAll('[data-action="new"]').forEach(function (button) {
        button.addEventListener('click', function () {
            form.querySelector('.dialog-error').textContent = '';
            dialog.showModal();
            setTimeout(function () { form.elements.title.select(); }, 0);
        });
    });
    document.querySelectorAll('[data-action="toggle-sidebar"]').forEach(function (button) {
        button.addEventListener('click', function () { app.classList.toggle('sidebar-open'); });
    });
    closeButton.addEventListener('click', confirmCloseActive);
    assistantButton.addEventListener('click', function () {
        setAssistantOpen(!app.classList.contains('assistant-open'));
    });
    document.querySelector('[data-action="close-assistant"]').addEventListener('click', function () {
        setAssistantOpen(false);
    });
    assistantFrame.addEventListener('load', scheduleAssistantContext);
    window.addEventListener('message', function (event) {
        if (event.origin !== location.origin || event.source !== assistantFrame.contentWindow) return;
        if (event.data && event.data.type === 'ai2apps.terminal.assistant-ready') {
            sendAssistantContext();
        }
    });
    closeForm.addEventListener('submit', async function (event) {
        if (!event.submitter || event.submitter.value !== 'close') return;
        event.preventDefault();
        event.submitter.disabled = true;
        try {
            await closeActive();
            closeDialog.close();
        } finally {
            event.submitter.disabled = false;
        }
    });
    document.querySelector('[data-action="reconnect"]').addEventListener('click', function () {
        if (activeId) connect(activeId, true);
    });
    form.addEventListener('submit', function (event) {
        if (!event.submitter || event.submitter.value === 'create') {
            event.preventDefault();
            createSession();
        }
    });
    window.addEventListener('beforeunload', function () { disconnect(true); });
    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) resizeTerminal();
    });

    iconify();
    empty.hidden = false;
    loadSessions();
})();
