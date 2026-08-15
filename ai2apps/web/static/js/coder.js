(function () {
    'use strict';

    const app = document.querySelector('.coder-app');
    if (!app || !window.Terminal || !window.FitAddon || !window.ace) return;
    const tree = app.querySelector('[data-coder-tree]');
    const empty = app.querySelector('.coder-empty');
    const emptyTitle = empty.querySelector('[data-empty-title]');
    const emptyDescription = empty.querySelector('[data-empty-description]');
    const emptyAction = empty.querySelector('[data-empty-action]');
    const title = app.querySelector('[data-current-title]');
    const meta = app.querySelector('[data-current-meta]');
    const status = app.querySelector('[data-status]');
    const sidebarToggle = app.querySelector('[data-action="toggle-sidebar"]');
    const filesButton = app.querySelector('[data-action="files"]');
    const deleteEntryButton = app.querySelector('[data-action="delete-entry"]');
    const validateButton = app.querySelector('[data-action="validate"]');
    const testButton = app.querySelector('[data-action="test"]');
    const buildButton = app.querySelector('[data-action="build"]');
    const testflightButton = app.querySelector('[data-action="testflight"]');
    const runComponentButton = app.querySelector('[data-action="run-component"]');
    const stopComponentButton = app.querySelector('[data-action="stop-component"]');
    const forkButton = app.querySelector('[data-action="fork"]');
    const reconnectButton = app.querySelector('[data-action="reconnect"]');
    const stopButton = app.querySelector('[data-action="stop"]');
    const projectDialog = document.querySelector('[data-project-dialog]');
    const projectForm = document.querySelector('[data-project-form]');
    const threadDialog = document.querySelector('[data-thread-dialog]');
    const threadForm = document.querySelector('[data-thread-form]');
    const modelSource = threadForm.querySelector('[data-model-source]');
    const modelRow = threadForm.querySelector('[data-model-row]');
    const modelSelect = threadForm.querySelector('[data-model-select]');
    const modelHint = threadForm.querySelector('[data-model-hint]');
    const agentSelect = threadForm.querySelector('[data-agent-select]');
    const terminalHost = document.getElementById('coder-terminal-host');
    const devPreview = app.querySelector('[data-dev-preview]');
    const coderIde = app.querySelector('[data-coder-ide]');
    const fileTree = app.querySelector('[data-file-tree]');
    const editorPath = app.querySelector('[data-editor-path]');
    const editorDirty = app.querySelector('[data-editor-dirty]');
    const editorMode = app.querySelector('[data-editor-mode]');
    const saveFileButton = app.querySelector('[data-action="save-file"]');
    const refreshFilesButton = app.querySelector('[data-action="refresh-files"]');
    const contextMenu = document.querySelector('[data-context-menu]');
    const reportDialog = document.querySelector('[data-report-dialog]');
    const reportTitle = reportDialog.querySelector('[data-report-title]');
    const reportOutput = reportDialog.querySelector('[data-report-output]');
    const terminal = new Terminal({ cursorBlink: true, convertEol: false, scrollback: 10000, fontSize: 13, theme: { background: '#0c0d10', foreground: '#d8d8dc', cursor: '#a98cff', selectionBackground: '#7656e855' } });
    const fitAddon = new FitAddon.FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(document.getElementById('coder-terminal-host'));
    ace.config.set('basePath', '/admin/static/vendor/ace');
    const codeEditor = ace.edit('coder-editor');
    codeEditor.setTheme('ace/theme/one_dark');
    codeEditor.setOptions({
        fontSize: 13,
        showPrintMargin: false,
        useWorker: false,
        enableBasicAutocompletion: false,
        enableLiveAutocompletion: false,
        displayIndentGuides: true,
        showFoldWidgets: true
    });
    codeEditor.session.setMode('ace/mode/text');
    codeEditor.setReadOnly(true);

    let projects = [];
    let threads = [];
    let agents = [];
    let ai2appsModels = [];
    let defaultProjectRoot = '';
    let activeThreadId = null;
    let activeProjectId = null;
    let activeComponentId = null;
    let pendingProjectId = null;
    let socket = null;
    let currentFilePath = null;
    let fileDirty = false;
    let settingEditorValue = false;
    let contextTarget = null;

    function escapeHtml(value) {
        return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
            return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char];
        });
    }

    async function api(url, options) {
        const response = await fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json', 'Content-Type': 'application/json' }, ...(options || {}) });
        if (!response.ok) {
            let message = 'HTTP ' + response.status;
            try { const body = await response.json(); message = body.detail?.message || body.detail || message; } catch (_) { /* retain status */ }
            throw new Error(message);
        }
        if (response.status === 204) return null;
        return response.json();
    }

    function activeThread() { return threads.find(function (item) { return item.id === activeThreadId; }); }
    function projectFor(thread) { return projects.find(function (item) { return item.id === thread?.project_id; }); }
    function activeProject() { return projects.find(function (item) { return item.id === activeProjectId; }); }
    function activeComponent() { return (activeProject()?.components || []).find(function (item) { return item.id === activeComponentId; }); }
    function activeDevSession() { return (activeProject()?.dev_sessions || []).find(function (item) { return item.component_id === activeComponentId && item.status === 'running'; }); }

    function componentIcon(kind) {
        return ({ app: 'panels-top-left', 'mini-app': 'panel-top', agent: 'bot', service: 'server', error: 'triangle-alert' })[kind] || 'box';
    }

    function showReport(heading, value) {
        reportTitle.textContent = heading;
        reportOutput.textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
        reportDialog.showModal();
    }

    function showTerminal() {
        devPreview.hidden = true;
        devPreview.removeAttribute('src');
        coderIde.hidden = true;
        terminalHost.hidden = false;
    }

    function showEmpty(heading, description, showAction) {
        emptyTitle.textContent = heading;
        emptyDescription.textContent = description;
        emptyAction.hidden = !showAction;
        empty.hidden = false;
    }

    function updateProjectActions() {
        const project = activeProject();
        const component = activeComponent();
        const ai2apps = project?.kind === 'ai2apps';
        validateButton.disabled = !ai2apps;
        testButton.disabled = !project;
        filesButton.disabled = !project;
        buildButton.disabled = !ai2apps;
        testflightButton.disabled = !ai2apps;
        runComponentButton.disabled = !ai2apps || !component?.runnable;
        stopComponentButton.disabled = !activeDevSession();
        deleteEntryButton.disabled = !activeThreadId && (!activeProjectId || Boolean(activeComponentId));
    }

    function fileMode(path) {
        const name = String(path || '').toLowerCase();
        const extension = name.includes('.') ? name.split('.').pop() : '';
        const modes = {
            json: ['json', 'JSON'], yaml: ['yaml', 'YAML'], yml: ['yaml', 'YAML'],
            js: ['javascript', 'JavaScript'], mjs: ['javascript', 'JavaScript'], cjs: ['javascript', 'JavaScript'],
            ts: ['typescript', 'TypeScript'], tsx: ['typescript', 'TypeScript'],
            py: ['python', 'Python'], html: ['html', 'HTML'], htm: ['html', 'HTML'],
            css: ['css', 'CSS'], md: ['markdown', 'Markdown'], markdown: ['markdown', 'Markdown'],
            sh: ['sh', 'Shell'], zsh: ['sh', 'Shell'], bash: ['sh', 'Shell'],
            go: ['golang', 'Go'], rs: ['rust', 'Rust'], java: ['java', 'Java'],
            c: ['c_cpp', 'C'], cc: ['c_cpp', 'C++'], cpp: ['c_cpp', 'C++'], h: ['c_cpp', 'C/C++'],
            xml: ['xml', 'XML'], svg: ['xml', 'SVG']
        };
        return modes[extension] || (['dockerfile', 'makefile'].includes(name.split('/').pop()) ? ['sh', 'Shell'] : ['text', 'Plain Text']);
    }

    function setFileDirty(value) {
        fileDirty = Boolean(value);
        editorDirty.hidden = !fileDirty;
        saveFileButton.disabled = !currentFilePath || !fileDirty;
    }

    function canLeaveFile() {
        if (!fileDirty) return true;
        if (!window.confirm('Discard unsaved changes to ' + currentFilePath + '?')) return false;
        setFileDirty(false);
        return true;
    }

    async function loadDirectory(path, host) {
        const project = activeProject();
        if (!project) return;
        host.innerHTML = '<div class="coder-file-message">Loading…</div>';
        try {
            const result = await api('/admin/api/coder/projects/' + encodeURIComponent(project.id) + '/files?path=' + encodeURIComponent(path));
            host.innerHTML = result.items.map(function (item) {
                const icon = item.kind === 'directory' ? 'folder' : 'file-code-2';
                return '<div class="coder-file-node"><button class="coder-file-row ' + item.kind + '" data-file-path="' + escapeHtml(item.path) + '" data-file-kind="' + item.kind + '">' +
                    '<i data-lucide="' + icon + '"></i><span>' + escapeHtml(item.name) + '</span></button>' +
                    (item.kind === 'directory' ? '<div class="coder-file-children" data-file-children hidden></div>' : '') + '</div>';
            }).join('') || '<div class="coder-file-message">Empty directory</div>';
            if (window.lucide) window.lucide.createIcons();
        } catch (error) {
            host.innerHTML = '<div class="coder-file-message">' + escapeHtml(error.message) + '</div>';
        }
    }

    async function openProjectFile(path) {
        const project = activeProject();
        if (!project || !canLeaveFile()) return;
        status.textContent = 'Opening File';
        try {
            const result = await api('/admin/api/coder/projects/' + encodeURIComponent(project.id) + '/file?path=' + encodeURIComponent(path));
            currentFilePath = result.path;
            const mode = fileMode(result.path);
            settingEditorValue = true;
            codeEditor.session.setMode('ace/mode/' + mode[0]);
            codeEditor.setValue(result.content, -1);
            codeEditor.clearSelection();
            settingEditorValue = false;
            codeEditor.setReadOnly(false);
            editorPath.textContent = result.path;
            editorMode.textContent = mode[1];
            setFileDirty(false);
            status.textContent = 'Editing';
            fileTree.querySelectorAll('.coder-file-row').forEach(function (row) {
                row.classList.toggle('active', row.dataset.filePath === path);
            });
            codeEditor.focus();
        } catch (error) { status.textContent = error.message; }
    }

    async function showProjectFiles(projectId, initialPath) {
        if (!canLeaveFile()) return;
        const project = projects.find(function (item) { return item.id === projectId; });
        if (!project) return;
        const changedProject = activeProjectId !== projectId;
        disconnect();
        activeThreadId = null;
        activeProjectId = projectId;
        activeComponentId = null;
        terminalHost.hidden = true;
        devPreview.hidden = true;
        devPreview.removeAttribute('src');
        empty.hidden = true;
        coderIde.hidden = false;
        title.textContent = project.name + ' · Files';
        meta.textContent = project.root_path;
        status.textContent = 'Files';
        forkButton.disabled = true; reconnectButton.disabled = true; stopButton.disabled = true;
        render();
        if (changedProject) {
            currentFilePath = null;
            settingEditorValue = true;
            codeEditor.setValue('', -1);
            settingEditorValue = false;
            codeEditor.setReadOnly(true);
            editorPath.textContent = 'No file selected';
            editorMode.textContent = 'Plain Text';
            setFileDirty(false);
        }
        await loadDirectory('.', fileTree);
        codeEditor.resize();
        if (initialPath) await openProjectFile(initialPath);
    }

    async function saveCurrentFile() {
        const project = activeProject();
        if (!project || !currentFilePath || !fileDirty) return;
        status.textContent = 'Saving';
        try {
            await api('/admin/api/coder/projects/' + encodeURIComponent(project.id) + '/file', {
                method: 'PUT',
                body: JSON.stringify({ path: currentFilePath, content: codeEditor.getValue() })
            });
            setFileDirty(false);
            status.textContent = 'Saved';
        } catch (error) { status.textContent = error.message; }
    }

    function usableAi2AppsModel(model) {
        const type = String(model.model_type || model.config_model_type || '').toLowerCase();
        return !model.is_hidden && !model.is_helper && !['audio', 'audio_tts', 'audio_stt', 'embedding', 'reranker', 'markitdown'].includes(type);
    }

    function renderAi2AppsModels() {
        const groups = [
            ['local', 'Local models'],
            ['cloud', 'Cloud models'],
            ['fusion', 'Fusion models']
        ];
        const grouped = { local: [], cloud: [], fusion: [] };
        ai2appsModels.forEach(function (model) {
            const source = model.source_type === 'cloud' ? 'cloud' : (model.source_type === 'fusion' ? 'fusion' : 'local');
            grouped[source].push(model);
        });
        const options = groups.map(function (group) {
            const items = grouped[group[0]];
            if (!items.length) return '';
            return '<optgroup label="' + group[1] + '">' + items.map(function (model) {
                const alias = model.settings?.model_alias || model.model_alias || '';
                const name = alias || model.display_name || model.id;
                const detail = name === model.id ? '' : ' — ' + model.id;
                const favorite = model.is_favorite ? '★ ' : '';
                return '<option value="' + escapeHtml(model.id) + '">' + favorite + escapeHtml(name + detail) + '</option>';
            }).join('') + '</optgroup>';
        }).join('');
        modelSelect.innerHTML = options || '<option value="">No available AI2Apps models</option>';
        modelHint.textContent = ai2appsModels.length
            ? ai2appsModels.length + ' available model' + (ai2appsModels.length === 1 ? '' : 's') + ' · local, cloud, and Fusion'
            : 'Configure or enable a model in Models first.';
        updateModelSource();
    }

    function updateModelSource() {
        const enabled = modelSource.value === 'ai2apps';
        modelRow.hidden = !enabled;
        modelSelect.disabled = !enabled || !ai2appsModels.length;
    }

    async function loadAi2AppsModels() {
        try {
            const data = await api('/admin/api/models');
            const catalog = (data.models || []).flatMap(function (model) {
                const profiles = (model.exposed_profiles || []).filter(function (profile) { return profile.model_id; }).map(function (profile) {
                    return {
                        ...model,
                        id: profile.model_id,
                        display_name: profile.display_name || profile.api_name || profile.name || profile.model_id,
                        exposed_profiles: [],
                        is_profile: true
                    };
                });
                return [model, ...profiles];
            });
            ai2appsModels = catalog.filter(usableAi2AppsModel).sort(function (left, right) {
                if (Boolean(left.is_favorite) !== Boolean(right.is_favorite)) return left.is_favorite ? -1 : 1;
                return String(left.display_name || left.id).localeCompare(String(right.display_name || right.id));
            });
            renderAi2AppsModels();
        } catch (error) {
            ai2appsModels = [];
            modelSelect.innerHTML = '<option value="">Models unavailable</option>';
            modelHint.textContent = error.message;
            updateModelSource();
        }
    }

    function render() {
        tree.innerHTML = projects.map(function (project) {
            const children = threads.filter(function (thread) { return thread.project_id === project.id; });
            return '<section class="coder-project"><button class="coder-project-head" data-project-id="' + escapeHtml(project.id) + '">' +
                '<i data-lucide="folder"></i><strong title="' + escapeHtml(project.root_path) + '">' + escapeHtml(project.name) + '</strong>' +
                '<span class="add-thread" data-new-thread="' + escapeHtml(project.id) + '" title="New Thread"><i data-lucide="plus"></i></span></button>' +
                '<div class="coder-components">' + (project.components || []).map(function (component) {
                    return '<button class="coder-component' + (component.id === activeComponentId && project.id === activeProjectId ? ' active' : '') + '" data-component-id="' + escapeHtml(component.id) + '" data-component-project="' + escapeHtml(project.id) + '">' +
                        '<i data-lucide="' + componentIcon(component.kind) + '"></i><strong title="' + escapeHtml(component.id) + '">' + escapeHtml(component.name) + '</strong><small>' + escapeHtml(component.kind) + '</small></button>';
                }).join('') + '</div>' +
                '<div class="coder-threads">' + children.map(function (thread) {
                    return '<button class="coder-thread ' + escapeHtml(thread.status) + (thread.id === activeThreadId ? ' active' : '') + '" data-thread-id="' + escapeHtml(thread.id) + '">' +
                        '<span class="coder-thread-dot"></span><strong>' + escapeHtml(thread.title) + '</strong><small>' + escapeHtml(thread.agent) + (thread.model ? ' · ' + escapeHtml(thread.model) : '') + '</small></button>';
                }).join('') + '</div></section>';
        }).join('');
        if (!projects.length) tree.innerHTML = '<div class="coder-tree-empty">No Projects yet</div>';
        if (window.lucide) window.lucide.createIcons();
        updateProjectActions();
    }

    function disconnect() {
        if (socket) { socket.onclose = null; socket.close(); socket = null; }
    }

    function connect(thread) {
        disconnect();
        terminal.reset();
        if (!thread?.terminal_session_id) return;
        status.textContent = 'Connecting';
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        socket = new WebSocket(protocol + '//' + location.host + '/admin/api/terminal/sessions/' + encodeURIComponent(thread.terminal_session_id) + '/stream');
        socket.binaryType = 'arraybuffer';
        socket.onopen = function () { status.textContent = 'Connected'; resize(); };
        socket.onmessage = function (event) {
            if (typeof event.data === 'string') {
                try { const item = JSON.parse(event.data); if (item.type === 'exit') status.textContent = 'Exited'; } catch (_) { /* output is normally binary */ }
            } else { terminal.write(new Uint8Array(event.data)); }
        };
        socket.onclose = function () { status.textContent = 'Disconnected'; };
    }

    async function activate(threadId) {
        if (!canLeaveFile()) return;
        activeThreadId = threadId;
        let thread = activeThread();
        if (!thread) return;
        const project = projectFor(thread);
        activeProjectId = project.id;
        activeComponentId = null;
        showTerminal();
        title.textContent = thread.title;
        meta.textContent = project.root_path + ' · ' + thread.agent + (thread.model ? ' · ' + thread.model : ' · CLI default model');
        empty.hidden = true;
        forkButton.disabled = false;
        reconnectButton.disabled = false;
        stopButton.disabled = false;
        render();
        if (!thread.terminal_session_id || thread.status !== 'running') {
            status.textContent = 'Starting';
            try {
                const updated = await api('/admin/api/coder/threads/' + encodeURIComponent(thread.id) + '/start', { method: 'POST', body: '{}' });
                threads = threads.map(function (item) { return item.id === updated.id ? updated : item; });
                thread = updated;
                render();
            } catch (error) { status.textContent = error.message; return; }
        }
        connect(thread);
    }

    function selectProject(projectId) {
        if (!canLeaveFile()) return;
        const project = projects.find(function (item) { return item.id === projectId; });
        if (!project) return;
        disconnect();
        activeThreadId = null;
        activeProjectId = projectId;
        activeComponentId = null;
        showTerminal();
        terminal.reset();
        title.textContent = project.name;
        meta.textContent = project.root_path + (project.kind === 'ai2apps' ? ' · AI2Apps Project' : ' · General software');
        status.textContent = 'Project';
        showEmpty('Project ready', project.kind === 'ai2apps'
            ? 'Select a component to validate, preview, test, or build it. Create a Thread when you want a coding Agent.'
            : 'Create a Thread to work on this software Project with a coding Agent.', false);
        forkButton.disabled = true; reconnectButton.disabled = true; stopButton.disabled = true;
        render();
    }

    function selectComponent(projectId, componentId) {
        if (!canLeaveFile()) return;
        const project = projects.find(function (item) { return item.id === projectId; });
        const component = (project?.components || []).find(function (item) { return item.id === componentId; });
        if (!project || !component) return;
        disconnect();
        activeThreadId = null;
        activeProjectId = projectId;
        activeComponentId = componentId;
        title.textContent = component.name;
        meta.textContent = component.id + ' · ' + component.kind + ' · ' + component.version;
        forkButton.disabled = true; reconnectButton.disabled = true; stopButton.disabled = true;
        empty.hidden = true;
        terminalHost.hidden = true;
        coderIde.hidden = true;
        const session = activeDevSession();
        if (session) {
            empty.hidden = true;
            devPreview.src = session.preview_url + '?reload=' + Date.now();
            devPreview.hidden = false;
            status.textContent = 'DEV Running';
        } else {
            devPreview.hidden = true;
            devPreview.removeAttribute('src');
            showEmpty(
                component.runnable ? 'Ready for source preview' : component.name,
                component.runnable
                    ? 'Run this component directly from the Project directory. Packaging and installation are not required.'
                    : 'This component is included in Project validation, tests, and the development Bundle.',
                false
            );
            status.textContent = component.runnable ? 'Ready to Run' : 'Validate / Test';
        }
        render();
    }

    function resize() {
        try { fitAddon.fit(); } catch (_) { return; }
        if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'resize', cols: terminal.cols, rows: terminal.rows }));
    }
    terminal.onData(function (data) { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'input', data: data })); });
    new ResizeObserver(resize).observe(document.getElementById('coder-terminal-host'));
    codeEditor.session.on('change', function () {
        if (!settingEditorValue && currentFilePath) setFileDirty(true);
    });
    codeEditor.commands.addCommand({
        name: 'saveProjectFile',
        bindKey: { win: 'Ctrl-S', mac: 'Command-S' },
        exec: saveCurrentFile
    });

    async function load() {
        try {
            const data = await api('/admin/api/coder');
            projects = data.projects; threads = data.threads; agents = data.agents;
            defaultProjectRoot = data.default_project_root || '';
            const rootHint = projectForm.querySelector('[data-project-root-hint]');
            if (rootHint && defaultProjectRoot) rootHint.textContent = 'Relative to ' + defaultProjectRoot;
            agentSelect.innerHTML = agents.map(function (agent) { return '<option value="' + escapeHtml(agent.id) + '"' + (agent.installed ? '' : ' disabled') + '>' + escapeHtml(agent.name) + (agent.installed ? '' : ' (not installed)') + '</option>'; }).join('');
            render();
            loadAi2AppsModels();
        } catch (error) { status.textContent = error.message; }
    }

    tree.addEventListener('click', function (event) {
        const add = event.target.closest('[data-new-thread]');
        if (add) {
            event.stopPropagation(); pendingProjectId = add.dataset.newThread;
            const project = projects.find(function (item) { return item.id === pendingProjectId; });
            threadForm.reset(); threadForm.querySelector('[data-thread-project]').textContent = project.name;
            updateModelSource(); threadDialog.showModal(); return;
        }
        const component = event.target.closest('[data-component-id]');
        if (component) {
            selectComponent(component.dataset.componentProject, component.dataset.componentId);
            return;
        }
        const thread = event.target.closest('[data-thread-id]');
        if (thread) activate(thread.dataset.threadId);
        else {
            const project = event.target.closest('[data-project-id]');
            if (project) selectProject(project.dataset.projectId);
        }
    });
    fileTree.addEventListener('click', async function (event) {
        const row = event.target.closest('[data-file-path]');
        if (!row) return;
        if (row.dataset.fileKind === 'directory') {
            const children = row.parentElement.querySelector('[data-file-children]');
            if (!children.hidden) { children.hidden = true; return; }
            children.hidden = false;
            if (!children.dataset.loaded) {
                children.dataset.loaded = '1';
                await loadDirectory(row.dataset.filePath, children);
            }
            return;
        }
        await openProjectFile(row.dataset.filePath);
    });

    function hideContextMenu() { contextMenu.hidden = true; contextTarget = null; }

    tree.addEventListener('contextmenu', function (event) {
        const thread = event.target.closest('[data-thread-id]');
        const component = event.target.closest('[data-component-id]');
        const project = event.target.closest('[data-project-id]');
        if (!thread && !component && !project) return;
        event.preventDefault();
        if (thread) contextTarget = { type: 'thread', id: thread.dataset.threadId };
        else if (component) contextTarget = { type: 'component', id: component.dataset.componentId, projectId: component.dataset.componentProject };
        else contextTarget = { type: 'project', id: project.dataset.projectId };
        contextMenu.querySelector('[data-context-action="files"]').hidden = contextTarget.type === 'thread';
        contextMenu.querySelector('[data-context-action="validate"]').hidden = contextTarget.type !== 'project';
        contextMenu.querySelector('[data-context-action="run"]').hidden = contextTarget.type !== 'component';
        contextMenu.querySelector('[data-context-action="fork"]').hidden = contextTarget.type !== 'thread';
        contextMenu.querySelector('[data-context-action="stop"]').hidden = contextTarget.type !== 'thread';
        contextMenu.querySelector('[data-context-action="delete"]').hidden = contextTarget.type === 'component';
        contextMenu.querySelector('[data-context-action="delete"] span').textContent = contextTarget.type === 'project' ? 'Remove Project' : 'Delete Thread';
        contextMenu.hidden = false;
        const width = 190; const height = contextMenu.offsetHeight;
        contextMenu.style.left = Math.min(event.clientX, window.innerWidth - width - 8) + 'px';
        contextMenu.style.top = Math.min(event.clientY, window.innerHeight - height - 8) + 'px';
    });
    document.addEventListener('click', function (event) {
        if (!event.target.closest('[data-context-menu]')) hideContextMenu();
    });
    window.addEventListener('blur', hideContextMenu);

    document.querySelectorAll('[data-action="new-project"]').forEach(function (button) { button.addEventListener('click', function () {
        projectForm.reset();
        const pathInput = projectForm.elements.root_path;
        pathInput.placeholder = defaultProjectRoot ? defaultProjectRoot + '/my-app' : 'my-app';
        projectDialog.showModal();
    }); });
    modelSource.addEventListener('change', updateModelSource);
    function updateSidebarToggle() {
        const collapsed = app.classList.contains('sidebar-collapsed');
        sidebarToggle.title = collapsed ? 'Show Project sidebar' : 'Collapse Project sidebar';
        sidebarToggle.innerHTML = '<i data-lucide="' + (collapsed ? 'panel-left-open' : 'panel-left-close') + '"></i>';
        if (window.lucide) window.lucide.createIcons();
        setTimeout(function () { resize(); codeEditor.resize(); }, 190);
    }
    if (localStorage.getItem('ai2apps-coder-sidebar') === 'collapsed') app.classList.add('sidebar-collapsed');
    updateSidebarToggle();
    sidebarToggle.addEventListener('click', function () {
        app.classList.toggle('sidebar-collapsed');
        localStorage.setItem('ai2apps-coder-sidebar', app.classList.contains('sidebar-collapsed') ? 'collapsed' : 'open');
        updateSidebarToggle();
    });
    filesButton.addEventListener('click', function () {
        const project = activeProject();
        if (project) showProjectFiles(project.id);
    });
    refreshFilesButton.addEventListener('click', function () { loadDirectory('.', fileTree); });
    saveFileButton.addEventListener('click', saveCurrentFile);
    projectForm.addEventListener('submit', async function (event) {
        if (event.submitter?.value !== 'create') return;
        event.preventDefault(); const data = new FormData(projectForm); const errorHost = projectForm.querySelector('.coder-dialog-error'); errorHost.textContent = '';
        try {
            const project = await api('/admin/api/coder/projects', { method: 'POST', body: JSON.stringify({ name: data.get('name'), root_path: data.get('root_path'), kind: data.get('kind'), create_directory: data.get('create_directory') === 'on', bootstrap: data.get('bootstrap') === 'on' }) });
            projects.unshift(project); projectDialog.close(); render();
        } catch (error) { errorHost.textContent = error.message; }
    });
    threadForm.addEventListener('submit', async function (event) {
        if (event.submitter?.value !== 'create') return;
        event.preventDefault(); const data = new FormData(threadForm); const errorHost = threadForm.querySelector('.coder-dialog-error'); errorHost.textContent = '';
        try {
            const thread = await api('/admin/api/coder/projects/' + encodeURIComponent(pendingProjectId) + '/threads', { method: 'POST', body: JSON.stringify({ title: data.get('title'), agent: data.get('agent'), model_source: data.get('model_source'), model: data.get('model') || '' }) });
            threads.unshift(thread); threadDialog.close(); render(); activate(thread.id);
        } catch (error) { errorHost.textContent = error.message; }
    });
    forkButton.addEventListener('click', async function () {
        const thread = activeThread(); if (!thread) return;
        try { const fork = await api('/admin/api/coder/threads/' + encodeURIComponent(thread.id) + '/fork', { method: 'POST', body: '{}' }); threads.unshift(fork); render(); activate(fork.id); } catch (error) { status.textContent = error.message; }
    });

    async function deleteThreadEntry(threadId) {
        const thread = threads.find(function (item) { return item.id === threadId; });
        if (!thread || !window.confirm('Delete Thread “' + thread.title + '”? The Project files will not be changed.')) return;
        try {
            await api('/admin/api/coder/threads/' + encodeURIComponent(thread.id), { method: 'DELETE' });
            const projectId = thread.project_id;
            threads = threads.filter(function (item) { return item.id !== thread.id; });
            activeThreadId = null;
            selectProject(projectId);
        } catch (error) { status.textContent = error.message; }
    }

    async function removeProjectEntry(projectId) {
        const project = projects.find(function (item) { return item.id === projectId; });
        if (!project || !window.confirm('Remove Project “' + project.name + '” from Coder? Its directory and files will be kept.')) return;
        try {
            await api('/admin/api/coder/projects/' + encodeURIComponent(project.id), { method: 'DELETE' });
            projects = projects.filter(function (item) { return item.id !== project.id; });
            threads = threads.filter(function (item) { return item.project_id !== project.id; });
            disconnect();
            activeThreadId = null; activeProjectId = null; activeComponentId = null;
            currentFilePath = null; setFileDirty(false);
            showTerminal(); terminal.reset();
            title.textContent = 'No Thread selected';
            meta.textContent = 'Add a Project, then create a Thread';
            status.textContent = 'Idle';
            showEmpty('Start coding with an Agent CLI', 'Each Project maps to a directory. Threads keep running while Coder is in the background.', true);
            forkButton.disabled = true; reconnectButton.disabled = true; stopButton.disabled = true;
            render();
        } catch (error) { status.textContent = error.message; }
    }

    deleteEntryButton.addEventListener('click', function () {
        if (activeThreadId) deleteThreadEntry(activeThreadId);
        else if (activeProjectId && !activeComponentId) removeProjectEntry(activeProjectId);
    });

    contextMenu.addEventListener('click', async function (event) {
        const action = event.target.closest('[data-context-action]')?.dataset.contextAction;
        const target = contextTarget;
        if (!action || !target) return;
        hideContextMenu();
        if (action === 'files') {
            if (target.type === 'project') await showProjectFiles(target.id);
            else {
                const project = projects.find(function (item) { return item.id === target.projectId; });
                const component = (project?.components || []).find(function (item) { return item.id === target.id; });
                const prefix = project?.root_path ? project.root_path.replace(/\/$/, '') + '/' : '';
                const manifest = component?.manifest_path?.startsWith(prefix) ? component.manifest_path.slice(prefix.length) : null;
                await showProjectFiles(target.projectId, manifest);
            }
        } else if (action === 'validate') {
            selectProject(target.id); validateButton.click();
        } else if (action === 'run') {
            selectComponent(target.projectId, target.id); runComponentButton.click();
        } else if (action === 'fork') {
            try {
                const fork = await api('/admin/api/coder/threads/' + encodeURIComponent(target.id) + '/fork', { method: 'POST', body: '{}' });
                threads.unshift(fork); render(); activate(fork.id);
            } catch (error) { status.textContent = error.message; }
        } else if (action === 'stop') {
            try {
                const updated = await api('/admin/api/coder/threads/' + encodeURIComponent(target.id) + '/stop', { method: 'POST', body: '{}' });
                threads = threads.map(function (item) { return item.id === updated.id ? updated : item; });
                if (activeThreadId === target.id) { disconnect(); status.textContent = 'Stopped'; }
                render();
            } catch (error) { status.textContent = error.message; }
        } else if (action === 'delete') {
            if (target.type === 'thread') await deleteThreadEntry(target.id);
            else if (target.type === 'project') await removeProjectEntry(target.id);
        }
    });
    reconnectButton.addEventListener('click', function () { const thread = activeThread(); if (thread) connect(thread); });
    stopButton.addEventListener('click', async function () {
        const thread = activeThread(); if (!thread) return;
        try { const updated = await api('/admin/api/coder/threads/' + encodeURIComponent(thread.id) + '/stop', { method: 'POST', body: '{}' }); threads = threads.map(function (item) { return item.id === updated.id ? updated : item; }); disconnect(); status.textContent = 'Stopped'; render(); } catch (error) { status.textContent = error.message; }
    });
    validateButton.addEventListener('click', async function () {
        const project = activeProject(); if (!project) return;
        status.textContent = 'Validating';
        try {
            const result = await api('/admin/api/coder/projects/' + encodeURIComponent(project.id) + '/validate', { method: 'POST', body: '{}' });
            status.textContent = result.valid ? 'Valid' : 'Invalid';
            showReport('Validation · ' + project.name, result);
        } catch (error) { status.textContent = error.message; }
    });
    testButton.addEventListener('click', async function () {
        const project = activeProject(); if (!project) return;
        status.textContent = 'Testing';
        try {
            const result = await api('/admin/api/coder/projects/' + encodeURIComponent(project.id) + '/test', { method: 'POST', body: '{}' });
            status.textContent = result.ok ? (result.skipped ? 'No Tests' : 'Tests Passed') : 'Tests Failed';
            showReport('Tests · ' + project.name, result.output || result);
        } catch (error) { status.textContent = error.message; }
    });
    buildButton.addEventListener('click', async function () {
        const project = activeProject(); if (!project) return;
        status.textContent = 'Building';
        try {
            const result = await api('/admin/api/coder/projects/' + encodeURIComponent(project.id) + '/build', { method: 'POST', body: '{}' });
            status.textContent = 'Bundle Ready';
            showReport('Development Bundle · ' + project.name, result);
        } catch (error) { status.textContent = error.message; }
    });
    testflightButton.addEventListener('click', async function () {
        const project = activeProject(); if (!project) return;
        status.textContent = 'Submitting TestFlight';
        try {
            const result = await api('/admin/api/coder/projects/' + encodeURIComponent(project.id) + '/testflight', { method: 'POST', body: '{}' });
            status.textContent = 'TestFlight Ready';
            showReport('TestFlight · ' + project.name, result);
        } catch (error) { status.textContent = error.message; }
    });
    runComponentButton.addEventListener('click', async function () {
        const project = activeProject(); const component = activeComponent();
        if (!project || !component) return;
        status.textContent = 'Starting DEV';
        try {
            const session = await api('/admin/api/coder/projects/' + encodeURIComponent(project.id) + '/dev-sessions', { method: 'POST', body: JSON.stringify({ component_id: component.id }) });
            project.dev_sessions = (project.dev_sessions || []).filter(function (item) { return item.id !== session.id; });
            project.dev_sessions.push(session);
            devPreview.src = session.preview_url + '?reload=' + Date.now();
            devPreview.hidden = false;
            empty.hidden = true;
            terminalHost.hidden = true;
            status.textContent = 'DEV Running';
            render();
        } catch (error) { status.textContent = error.message; }
    });
    stopComponentButton.addEventListener('click', async function () {
        const project = activeProject(); const session = activeDevSession();
        if (!project || !session) return;
        try {
            await api('/admin/api/coder/dev-sessions/' + encodeURIComponent(session.id), { method: 'DELETE' });
            project.dev_sessions = (project.dev_sessions || []).filter(function (item) { return item.id !== session.id; });
            devPreview.hidden = true;
            devPreview.removeAttribute('src');
            showEmpty('Development Session stopped', 'Run the component again to reopen its source preview.', false);
            status.textContent = 'DEV Stopped';
            render();
        } catch (error) { status.textContent = error.message; }
    });
    window.addEventListener('message', function (event) { if (event.origin !== location.origin) return; if (event.data?.type === 'ai2apps.host.activate') setTimeout(resize, 50); });
    load();
}());
