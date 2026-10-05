(() => {
    'use strict';
    const API = '/v1/platform';
    const state = {
        context: Object.fromEntries(new URLSearchParams(location.hash.slice(1))),
        page: null, drafts: [], draft: null, capabilityId: null, recipe: null,
        client: null, busy: false, run: null, contextRevision: 0,
        resultMode: 'json', presentations: new Map(), review: null, previousReview: null,
        exploration: null, contextPinned: false, attachments: [],
    };
    const $ = selector => document.querySelector(selector);
    const $$ = selector => [...document.querySelectorAll(selector)];
    const translationFallbacks = {
        en: {
            'agent.mini.delete': 'Delete',
            'agent.mini.delete_confirm': 'Delete Agent “{name}”?',
            'agent.mini.deleted': 'Agent deleted.',
            'agent.mini.close': 'Close',
            'agent.mini.result': 'Result',
            'agent.mini.json_view': 'JSON',
            'agent.mini.ai_beautify': 'Beautify with AI',
            'agent.mini.ai_view': 'AI view',
            'agent.mini.ai_beautifying': 'Creating an AI presentation…',
            'agent.mini.ai_beautified': 'AI presentation ready.',
            'agent.mini.standard_model_not_configured': 'No model is configured for Standard tasks.',
            'agent.mini.standard_model_unavailable': 'The model configured for Standard tasks is unavailable.',
            'agent.mini.invalid_presentation_spec': 'The model returned an invalid presentation description.',
            'agent.mini.other_fields': 'Other fields',
            'agent.mini.review_title': 'Compile Review',
            'agent.mini.review_json': 'Inspect Source and compiled IR',
            'agent.mini.review_feedback': 'Changes for the whole flow',
            'agent.mini.review_feedback_placeholder': 'For example: handle missing dates and keep image_url.',
            'agent.mini.review_revise': 'Revise entire flow with AI',
            'agent.mini.review_approve': 'Approve Review',
            'agent.mini.review_approved': 'Review approved. This version can now be added.',
            'agent.mini.review_ready': 'The run succeeded and the current flow compiled. Review every step.',
            'agent.mini.review_revising': 'Revising and recompiling the entire flow…',
            'agent.mini.review_revised': 'A new revision is ready for Review.',
            'agent.mini.review_wait_hint': 'AI is updating and compiling the flow. Please wait…',
            'agent.mini.review_failed': 'Flow update failed. Your feedback has been kept.',
            'agent.mini.before_compile': 'Before compile',
            'agent.mini.after_compile': 'After compile',
            'agent.mini.changed': 'Changed',
            'agent.mini.valid': 'valid',
            'agent.mini.invalid': 'invalid',
            'agent.mini.exploration_title': 'Exploratory build',
            'agent.mini.exploration_observe': 'Observe',
            'agent.mini.exploration_model': 'Model',
            'agent.mini.exploration_propose': 'Propose',
            'agent.mini.exploration_preflight': 'Preflight',
            'agent.mini.exploration_execute': 'Execute',
            'agent.mini.exploration_evaluate': 'Evaluate',
            'agent.mini.exploration_distill': 'Distill',
            'agent.mini.exploration_complete': 'Complete',
            'agent.mini.exploration_budget': '{count}/{max} actions',
            'agent.mini.exploration_stopped': 'Exploration stopped.',
            'agent.mini.exploration_limit': 'Exploration reached its action budget.',
            'agent.mini.exploration_successful_steps': '{count} successful steps',
            'agent.mini.exploration_compiled_steps': '{count} compiled steps',
            'agent.mini.exploration_goal_satisfied': 'Goal satisfied',
            'agent.mini.exploration_restricted': 'Restricted',
            'agent.mini.exploration_failed': 'Failed',
            'agent.mini.status_running': 'Running',
            'agent.mini.status_awaiting_review': 'Awaiting review',
            'agent.mini.status_approved': 'Approved',
            'agent.mini.status_failed': 'Failed',
        },
        zh: {
            'agent.mini.delete': '删除',
            'agent.mini.delete_confirm': '确定删除智能体“{name}”吗？',
            'agent.mini.deleted': '智能体已删除。',
            'agent.mini.close': '关闭',
            'agent.mini.result': '执行结果',
            'agent.mini.json_view': 'JSON',
            'agent.mini.ai_beautify': 'AI 美化',
            'agent.mini.ai_view': 'AI 视图',
            'agent.mini.ai_beautifying': '正在生成 AI 展示…',
            'agent.mini.ai_beautified': 'AI 展示已生成。',
            'agent.mini.standard_model_not_configured': '尚未为“标准任务”配置模型。',
            'agent.mini.standard_model_unavailable': '“标准任务”配置的模型当前不可用。',
            'agent.mini.invalid_presentation_spec': '模型返回的展示描述格式无效。',
            'agent.mini.other_fields': '其他字段',
            'agent.mini.review_title': '编译 Review',
            'agent.mini.review_json': '查看 Source 与编译 IR',
            'agent.mini.review_feedback': '对整个流程的修改意见',
            'agent.mini.review_feedback_placeholder': '例如：发布日期缺失时也要保留文章，并确保输出 image_url。',
            'agent.mini.review_revise': '让 AI 调整整个流程',
            'agent.mini.review_approve': '通过 Review',
            'agent.mini.review_approved': 'Review 已通过，可以加入网站智能体。',
            'agent.mini.review_ready': '试运行成功，当前流程已通过编译。请逐步 Review。',
            'agent.mini.review_revising': '正在调整并重新编译整个流程…',
            'agent.mini.review_revised': '新版本已生成，请重新 Review。',
            'agent.mini.review_wait_hint': 'AI 正在修改和编译流程，请稍候…',
            'agent.mini.review_failed': '流程调整失败，修改意见已保留。',
            'agent.mini.before_compile': '编译前',
            'agent.mini.after_compile': '编译后',
            'agent.mini.changed': '已变化',
            'agent.mini.valid': '有效',
            'agent.mini.invalid': '无效',
            'agent.mini.exploration_title': '探索式制作',
            'agent.mini.exploration_observe': '观察',
            'agent.mini.exploration_model': '模型',
            'agent.mini.exploration_propose': '提议',
            'agent.mini.exploration_preflight': '预检',
            'agent.mini.exploration_execute': '执行',
            'agent.mini.exploration_evaluate': '评价',
            'agent.mini.exploration_distill': '沉淀',
            'agent.mini.exploration_complete': '完成',
            'agent.mini.exploration_budget': '{count}/{max} 个动作',
            'agent.mini.exploration_stopped': '探索已停止。',
            'agent.mini.exploration_limit': '探索已达到动作预算上限。',
            'agent.mini.exploration_successful_steps': '{count} 个成功步骤',
            'agent.mini.exploration_compiled_steps': '{count} 个已编译步骤',
            'agent.mini.exploration_goal_satisfied': '目标已满足',
            'agent.mini.exploration_restricted': '操作受限',
            'agent.mini.exploration_failed': '失败',
            'agent.mini.status_running': '运行中',
            'agent.mini.status_awaiting_review': '等待审核',
            'agent.mini.status_approved': '已通过',
            'agent.mini.status_failed': '失败',
        },
    };
    const tr = (key, values = {}) => {
        let text = typeof window.t === 'function' ? window.t(key) : key;
        if (text === key) {
            const language = document.documentElement.lang.toLowerCase().startsWith('zh')
                ? 'zh' : 'en';
            text = translationFallbacks[language][key] || key;
        }
        return Object.entries(values).reduce(
            (result, [name, value]) => result.replaceAll(`{${name}}`, String(value)),
            text);
    };
    const statusText = status => {
        const key = 'agent.mini.status_' + String(status || '');
        const translated = tr(key);
        return translated === key ? String(status || '') : translated;
    };
    function setContextPinned(pinned) {
        const next = Boolean(pinned);
        if (state.contextPinned === next) return;
        state.contextPinned = next;
        const fragment = new URLSearchParams(location.hash.slice(1));
        if (next) fragment.set('agent_context_lock', '1');
        else fragment.delete('agent_context_lock');
        const suffix = fragment.toString();
        history.replaceState(history.state, '',
            location.pathname + location.search + (suffix ? '#' + suffix : ''));
    }

    let noticeTimer = null;
    function notice(text, tone = 'info') {
        const node = $('#agent-notice');
        if (noticeTimer !== null) {
            window.clearTimeout(noticeTimer);
            noticeTimer = null;
        }
        node.hidden = !text;
        node.dataset.tone = tone;
        $('#agent-notice-text').textContent = text || '';
        const timeout = {success: 4000, warning: 8000, error: 12000}[tone] || 0;
        if (text && timeout) {
            noticeTimer = window.setTimeout(() => notice(''), timeout);
        }
    }
    async function api(path, options = {}) {
        const response = await fetch(API + path, {
            credentials: 'same-origin', ...options,
            headers: {'Content-Type': 'application/json', ...(options.headers || {})},
        });
        const body = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = body.error?.message || body.message || body.detail?.message ||
                body.detail || response.statusText;
            const error = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
            error.code = body.error?.code || body.detail?.code || '';
            error.details = body.error?.details || body.detail?.details || {};
            throw error;
        }
        return body;
    }
    function cloneSource() {
        return state.draft?.source ? structuredClone(state.draft.source) : {
            schema: 'ai2apps.web-agent-source/v1', name: 'New Agent',
            description: '', site_scope: [], inputs: {}, outputs: {}, steps: [],
        };
    }
    function savedForMenu(draft) {
        return draft?.source?.authoring?.saved !== false;
    }
    function capabilities() {
        const items = state.draft?.source?.capabilities;
        return Array.isArray(items) ? items : [];
    }
    function currentCapability() {
        const items = capabilities();
        if (!items.length) return state.draft?.source || null;
        return items.find(item => item.id === state.capabilityId) || items[0];
    }
    function pageScope() {
        try {
            const url = new URL(state.page?.url || state.context.url);
            return ['http:', 'https:'].includes(url.protocol) ? url.origin + '/**' : '';
        }
        catch (_) { return ''; }
    }
    function normalizedStep(step, index) {
        return {
            name: String(step?.name || 'step-' + (index + 1)),
            desc: String(step?.desc || ''),
            ...(step?.operation ? {operation: step.operation} : {}),
            ...(step?.ai && typeof step.ai === 'object' ? {ai: structuredClone(step.ai)} : {}),
            ...(step?.when ? {when: structuredClone(step.when)} : {}),
            target: step?.target && typeof step.target === 'object' ? step.target : {},
            arguments: step?.arguments && typeof step.arguments === 'object' ? step.arguments : {},
            execution: step?.execution || {mode: 'adaptive'},
            interaction: step?.interaction || {profile: 'natural'},
            on: step?.on || {success: 'done', failed: 'failed'},
        };
    }
    function editorSource() {
        const source = cloneSource();
        source.name = $('#agent-name').value.trim() || 'New Site Agent';
        source.site_scope = $('#agent-scope').value.split(/[,\n]/).map(v => v.trim()).filter(Boolean);
        const capability = currentCapability();
        const inputs = readParameterDefinitions(capability?.inputs);
        const nextSteps = $$('.agent-step').map((node, index) => normalizedStep({
            ...(capability?.steps?.[index] || {}),
            name: node.querySelector('[data-field=name]').value.trim() || 'step-' + (index + 1),
            desc: node.querySelector('[data-field=desc]').value.trim(),
            target: node._target || {},
            ...(node.querySelector('[data-field=tier]') ? {ai: {
                ...capability.steps[index].ai,
                tier: node.querySelector('[data-field=tier]').value,
            }} : {}),
            on: {
                ...(capability?.steps?.[index]?.on || {}),
                success: node.querySelector('[data-field=success]').value.trim() || 'done',
                failed: node.querySelector('[data-field=failed]').value.trim() || 'failed',
            },
        }, index));
        if (Array.isArray(source.capabilities)) {
            const selected = source.capabilities.find(item => item.id === (state.capabilityId || capability?.id));
            if (selected) { selected.steps = nextSteps; selected.inputs = inputs; }
        } else { source.steps = nextSteps; source.inputs = inputs; }
        return source;
    }
    function parameterValue(type, value) {
        if (type === 'boolean') {
            if (![true, false, 'true', 'false'].includes(value)) throw new Error(tr('agent.mini.invalid_parameter'));
            return value === true || value === 'true';
        }
        if (['number', 'integer'].includes(type)) {
            const number = Number(value);
            if (value === '' || !Number.isFinite(number) || (type === 'integer' && !Number.isInteger(number)))
                throw new Error(tr('agent.mini.invalid_parameter'));
            return number;
        }
        if (type === 'object') {
            const object = JSON.parse(value);
            if (!object || typeof object !== 'object' || Array.isArray(object)) throw new Error(tr('agent.mini.invalid_parameter'));
            return object;
        }
        return String(value);
    }
    function readParameterDefinitions(previous = {}) {
        const properties = {}, required = [];
        $$('#agent-parameter-definitions .agent-parameter').forEach(row => {
            const key = row.querySelector('[data-key]').value.trim();
            if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key) || ['__proto__','constructor','prototype'].includes(key) || Object.hasOwn(properties, key))
                throw new Error(tr('agent.mini.invalid_parameter'));
            const type = row.querySelector('[data-type]').value;
            const property = {...previous.properties?.[key], type,
                title: row.querySelector('[data-label]').value.trim() || key};
            delete property.default;
            const value = row.querySelector('[data-default]').value;
            if (value !== '') property.default = parameterValue(type, value);
            properties[key] = property;
            if (row.querySelector('[data-required]').checked) required.push(key);
        });
        return {...previous, type:'object', properties, required};
    }
    function renderInputFields(container, schema = {}) {
        container.replaceChildren();
        if (!Object.keys(schema.properties || {}).length) {
            const empty = document.createElement('p'); empty.textContent = tr('agent.mini.no_parameters');
            container.append(empty); return;
        }
        const title = document.createElement('strong'); title.textContent = tr('agent.mini.run_parameters');
        container.append(title);
        Object.entries(schema.properties).forEach(([key, property]) => {
            const label = document.createElement('label'); label.className = 'agent-field';
            const text = document.createElement('span'); text.textContent = (property.title || key) + (schema.required?.includes(key) ? ' *' : '');
            const input = document.createElement(property.type === 'boolean' || property.enum ? 'select' : 'input');
            input.dataset.parameter = key;
            if (property.type === 'boolean' || property.enum) {
                input.add(new Option('', ''));
                (property.enum || [true, false]).forEach(value => input.add(new Option(String(value), String(value))));
            } else input.type = ['integer','number'].includes(property.type) ? 'number' : 'text';
            input.value = property.default == null ? '' : property.type === 'object' ? JSON.stringify(property.default) : String(property.default);
            if (property['x-ai2apps-file']) {
                input.type = 'hidden';
                const filename = document.createElement('small'); filename.textContent = property.default?.name || property.default?.url || '';
                const picker = document.createElement('input'); picker.type = 'file';
                picker.setAttribute('aria-label', text.textContent);
                picker.onchange = () => withBusy(async () => {
                    if (!picker.files[0]) return;
                    const file = await uploadAgentFile(picker.files[0]);
                    input.value = JSON.stringify(file); filename.textContent = file.name;
                });
                const url = document.createElement('input'); url.type = 'url'; url.placeholder = tr('agent.mini.file_url');
                url.onchange = () => withBusy(async () => {
                    if (!url.value) return;
                    const parsed = new URL(url.value);
                    if (!['https:','http:'].includes(parsed.protocol)) throw new Error(tr('agent.mini.invalid_parameter'));
                    input.value = JSON.stringify({url:parsed.href,name:parsed.pathname.split('/').pop() || 'File'});
                    filename.textContent = parsed.href;
                });
                const gallery = document.createElement('button'); gallery.type = 'button'; gallery.textContent = tr('agent.mini.choose_gallery');
                gallery.onclick = async () => {
                    const assets = await window.AI2AppsGalleryPicker.open({multiple:false});
                    if (assets.length) await withBusy(async () => {
                        const file = fileReference(await api('/gallery/assets/'+encodeURIComponent(assets[0].id)));
                        input.value = JSON.stringify(file); filename.textContent = file.name;
                    });
                };
                label.append(filename,picker,gallery,url);
            }
            label.append(text, input); container.append(label);
        });
    }
    function readInputFields(container, schema = {}) {
        const values = {};
        container.querySelectorAll('[data-parameter]').forEach(input => {
            const key = input.dataset.parameter, property = schema.properties[key];
            if (input.value === '') {
                if (schema.required?.includes(key)) throw new Error(tr('agent.mini.parameter_required', {name:property.title || key}));
                return;
            }
            const value = parameterValue(property.type, input.value);
            if (property.enum && !property.enum.includes(value)) throw new Error(tr('agent.mini.invalid_parameter'));
            values[key] = value;
        });
        return values;
    }
    function renderParameters() {
        const schema = currentCapability()?.inputs || {};
        const list = $('#agent-parameter-definitions'); list.replaceChildren();
        Object.entries(schema.properties || {}).forEach(([key, property]) => {
            const row = document.createElement('div'); row.className = 'agent-parameter';
            row.dataset.originalKey = key;
            row.innerHTML = '<input data-key><input data-label><select data-type></select><input data-default><label><input data-required type="checkbox"><span></span></label><button type="button">×</button>';
            [['data-key',key,'parameter_name'],['data-label',property.title || key,'parameter_label'],['data-default',property.default == null ? '' : typeof property.default === 'object' ? JSON.stringify(property.default) : String(property.default),'parameter_default']].forEach(([attr,value,label]) => {
                const input = row.querySelector('['+attr+']'); input.value = value; input.placeholder = tr('agent.mini.'+label); input.setAttribute('aria-label', input.placeholder);
            });
            const type = row.querySelector('[data-type]');
            ['string','integer','number','boolean','object'].forEach(value => type.add(new Option(tr('agent.mini.type_'+value), value)));
            type.value = property.type || 'string';
            row.querySelector('[data-required]').checked = schema.required?.includes(key) || false;
            row.querySelector('span').textContent = tr('agent.mini.parameter_required_label');
            row.querySelector('button').onclick = () => withBusy(async () => {
                if (JSON.stringify(currentCapability().steps).includes('${input.'+key+'}'))
                    throw new Error(tr('agent.mini.parameter_in_use'));
                row.remove(); syncEditor(); renderParameters(); renderSteps();
            });
            row.onchange = () => withBusy(async () => {
                const next = row.querySelector('[data-key]').value.trim();
                // Validate before modifying references or discarding editor values.
                readParameterDefinitions(schema);
                syncEditor();
                if (next !== row.dataset.originalKey) {
                    const before = '${input.'+row.dataset.originalKey+'}', after = '${input.'+next+'}';
                    const replace = value => typeof value === 'string' ? value.replaceAll(before, after) :
                        Array.isArray(value) ? value.map(replace) : value && typeof value === 'object' ?
                            Object.fromEntries(Object.entries(value).map(([k,v]) => [k,replace(v)])) : value;
                    currentCapability().steps = currentCapability().steps.map(replace);
                    row.dataset.originalKey = next;
                }
                renderInputFields($('#agent-build-inputs'), currentCapability().inputs); renderSteps();
            });
            list.append(row);
        });
        renderInputFields($('#agent-build-inputs'), schema);
    }
    function syncEditor() {
        if (!state.draft) return;
        state.draft.source = editorSource();
        state.draft.name = state.draft.source.name;
        state.draft.site_scope = state.draft.source.site_scope;
    }
    function renderSteps() {
        const list = $('#agent-steps');
        list.replaceChildren();
        const steps = currentCapability()?.steps || [];
        steps.forEach((raw, index) => {
            const step = normalizedStep(raw, index);
            const node = document.createElement('article');
            node.className = 'agent-step';
            node._target = step.target;
            node.innerHTML =
                `<div class="agent-step-head"><strong></strong><span></span><button data-action="up" title="${tr('agent.mini.move_up')}">↑</button><button data-action="down" title="${tr('agent.mini.move_down')}">↓</button><button data-action="remove" title="${tr('agent.mini.remove')}">×</button></div>` +
                `<input data-field="name" aria-label="${tr('agent.mini.step_name')}">` +
                `<textarea data-field="desc" rows="3" aria-label="${tr('agent.mini.step_description')}" placeholder="${tr('agent.mini.step_placeholder')}"></textarea>` +
                `<div class="agent-transition"><label>${tr('agent.mini.success')} → <input data-field="success"></label><label>${tr('agent.mini.failure')} → <input data-field="failed"></label></div>` +
                `<div class="agent-step-actions"><button data-action="pick">${tr('agent.mini.pick')}</button><button data-action="preview">${tr('agent.mini.preview')}</button><button data-action="run">${tr('agent.mini.run_step')}</button></div>`;
            node.querySelector('.agent-step-head strong').textContent = 'Step ' + (index + 1);
            node.querySelector('.agent-step-head span').textContent =
                step.ai?.tier ? `AI · ${step.ai.tier}` :
                    (step.target?.accessible_name || step.target?.intent || '');
            node.querySelector('[data-field=name]').value = step.name;
            node.querySelector('[data-field=desc]').value = step.desc;
            node.querySelector('[data-field=success]').value = step.on.success || 'done';
            node.querySelector('[data-field=failed]').value = step.on.failed || 'failed';
            if (step.ai && step.operation?.startsWith('ai.')) {
                const label = document.createElement('label'); label.className = 'agent-field';
                const title = document.createElement('span'); title.textContent = tr('agent.mini.step_model');
                const select = tierSelect(step.ai.tier); select.dataset.field = 'tier';
                select.onchange = () => syncEditor();
                label.append(title, select); node.append(label);
            }
            if (!step.operation || step.operation === 'input' || step.arguments?.value !== undefined) {
                const binding = document.createElement('select');
                binding.setAttribute('aria-label', tr('agent.mini.bind_parameter'));
                binding.add(new Option(tr('agent.mini.fixed_value'), ''));
                Object.entries(currentCapability()?.inputs?.properties || {}).forEach(([key, property]) =>
                    binding.add(new Option(property.title || key, key)));
                binding.value = /^\$\{input\.([A-Za-z_][A-Za-z0-9_]*)\}$/.exec(String(step.arguments?.value || ''))?.[1] || '';
                const fixed = document.createElement('input'); fixed.value = binding.value ? '' : String(step.arguments?.value || '');
                fixed.placeholder = tr('agent.mini.fixed_value'); fixed.hidden = Boolean(binding.value);
                const update = () => {syncEditor(); const target = currentCapability().steps[index];
                    target.arguments.value = binding.value ? '${input.'+binding.value+'}' : fixed.value;
                    fixed.hidden = Boolean(binding.value);};
                binding.onchange = update; fixed.onchange = update;
                node.append(binding, fixed);
            }
            node.querySelector('[data-action=remove]').onclick = () => {
                syncEditor();
                state.draft.source.steps.splice(index, 1);
                renderSteps();
            };
            node.querySelector('[data-action=up]').disabled = index === 0;
            node.querySelector('[data-action=down]').disabled = index === steps.length - 1;
            node.querySelector('[data-action=up]').onclick = () => moveStep(index, -1);
            node.querySelector('[data-action=down]').onclick = () => moveStep(index, 1);
            node.querySelector('[data-action=pick]').onclick = () => pickTarget(index);
            node.querySelector('[data-action=preview]').onclick = () => runEditorStep(index, true);
            node.querySelector('[data-action=run]').onclick = () => runEditorStep(index, false);
            list.append(node);
        });
        if (!steps.length) list.innerHTML = `<p class="agent-empty">${tr('agent.mini.empty_steps')}</p>`;
    }
    function renderDraft() {
        if (!state.draft) return;
        $('#agent-name').value = state.draft.name;
        $('#agent-scope').value = (state.draft.site_scope || []).join(', ');
        const select = $('#agent-capability');
        select.replaceChildren();
        const items = capabilities();
        if (items.length) {
            if (!items.some(item => item.id === state.capabilityId)) state.capabilityId = items[0].id;
            items.forEach(item => select.add(new Option(item.title || item.name || item.id, item.id)));
            select.value = state.capabilityId;
        } else {
            select.add(new Option(state.draft.name, 'legacy'));
            state.capabilityId = null;
        }
        renderParameters();
        renderSteps();
    }
    function renderList() {
        const list = $('#agent-list');
        list.replaceChildren();
        state.drafts.forEach(draft => {
            const item = document.createElement('button');
            item.className = 'agent-list-item';
            item.innerHTML = '<span><strong></strong><small></small></span><i>›</i>';
            item.querySelector('strong').textContent = draft.name;
            item.querySelector('small').textContent =
                tr('agent.mini.capabilities_count', { count: draft.source?.capabilities?.length || 1, status: draft.status });
            item.onclick = () => openDraft(draft.id);
            list.append(item);
        });
        if (!state.drafts.length) {
            list.innerHTML = `<p class="agent-empty">${tr('agent.mini.empty_agents')}</p>`;
        }
    }
    async function refreshDrafts() {
        state.drafts = ((await api('/agent-drafts')).items || []).filter(savedForMenu);
        renderList();
    }
    function switchMode(mode) {
        $('#agent-run-panel').hidden = false;
        $('#agent-build-panel').hidden = mode !== 'build';
        if (mode === 'build') $('#agent-build-panel').scrollIntoView({block:'start'});
    }

    function fileReference(asset) {
        return {asset_id:asset.id, url:API+'/gallery/assets/'+encodeURIComponent(asset.id)+'/content',
            name:asset.name, media_type:asset.media_type, size_bytes:asset.size_bytes};
    }
    async function addAgentAttachments(files = [], ids = []) {
        const uniqueIds = [...new Set(ids)].filter(id => !state.attachments.some(item => item.asset_id === id));
        if (state.attachments.length + files.length + uniqueIds.length > 8) throw new Error(tr('agent.mini.too_many_files'));
        // Resolve Gallery references through the owner-authenticated API, never trust drag metadata.
        const references = await Promise.all(uniqueIds.map(async id => fileReference(await api('/gallery/assets/'+encodeURIComponent(id)))));
        state.attachments.push(...references); renderAttachments();
        for (const file of files) {
            const reference = await uploadAgentFile(file);
            if (!state.attachments.some(item => item.asset_id === reference.asset_id)) state.attachments.push(reference);
            renderAttachments();
        }
    }
    async function chooseGalleryAttachments() {
        const assets = await window.AI2AppsGalleryPicker.open({multiple:true,maxSelection:8-state.attachments.length});
        if (assets.length) await withBusy(() => addAgentAttachments([],assets.map(asset => asset.id)));
    }
    async function uploadAgentFile(file) {
        if (file.size > (file.type.startsWith('image/') ? 8 : 25) * 1024 * 1024) throw new Error(tr('agent.mini.file_too_large'));
        const body = new FormData(); body.append('file', file); body.append('sourceAppId', 'ai2apps.agents');
        const response = await fetch(API+'/gallery/assets/import', {method:'POST', credentials:'same-origin', body});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error?.message || result.detail || response.statusText);
        const asset = result.asset;
        return fileReference(asset);
    }
    function renderAttachments() {
        const list = $('#agent-attachments'); list.replaceChildren();
        state.attachments.forEach((attachment, index) => {
            const row = document.createElement('div'); row.className = 'agent-section-title';
            const name = document.createElement('span'); name.textContent = attachment.name;
            const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×';
            remove.setAttribute('aria-label',tr('agent.mini.remove_attachment'));
            remove.onclick = () => { state.attachments.splice(index,1); renderAttachments(); };
            row.append(name,remove); list.append(row);
        });
    }
    function builderSelection() {
        const value = $('#agent-builder-model').value;
        return value.startsWith('model:') ? {model:value.slice(6), model_tier:'standard'} :
            {model:'', model_tier:value.slice(5) || 'standard'};
    }
    function tierSelect(value = 'standard') {
        const select = document.createElement('select');
        ['simple','standard','complex'].forEach(tier => select.add(new Option(tr('agent.mini.tier_'+tier), tier)));
        select.value = value; select.setAttribute('aria-label', tr('agent.mini.step_model'));
        return select;
    }
    function builderModelSupportsVisionChat(model) {
        if (!model || !model.id) return false;
        const type = String(model.model_type || model.type || '').toLowerCase();
        const capabilities = model.capabilities;
        let chat = false, vision = type === 'vlm';
        if (Array.isArray(capabilities)) {
            const declared = capabilities.map(value => String(value).toLowerCase());
            chat = declared.some(value => ['conversation', 'chat', 'chat_completions'].includes(value));
            if (!declared.length) chat = type === 'vlm';
            vision ||= declared.some(value => ['image_recognition', 'image_input', 'vision', 'multimodal'].includes(value));
        } else if (capabilities && typeof capabilities === 'object') {
            const chatKeys = ['conversation', 'chat', 'chatCompletions', 'chat_completions'];
            const declaredChat = chatKeys.filter(key => key in capabilities);
            chat = declaredChat.length ? declaredChat.some(key => capabilities[key] === true)
                : capabilities.textOutput === true || (type === 'vlm' && capabilities.imageOutput !== true
                    && capabilities.imageGeneration !== true && capabilities.audioOutput !== true && capabilities.videoOutput !== true);
            vision ||= ['imageInput', 'image_input', 'image_recognition', 'vision', 'multimodal'].some(key => capabilities[key] === true);
        } else chat = type === 'vlm';
        const modalities = model.input_modalities || model.modalities;
        vision ||= Array.isArray(modalities) && modalities.some(value => String(value).toLowerCase() === 'image');
        if (Array.isArray(model.endpoints) && !model.endpoints.includes('chat_completions')) return false;
        return chat && vision;
    }
    async function loadBuilderModels() {
        const selected = $('#agent-builder-model').value;
        try {
            const response = await fetch('/v1/models', {credentials:'include'});
            if (!response.ok) return;
            const catalog = await response.json();
            const select = $('#agent-builder-model');
            select.querySelectorAll('optgroup').forEach(group => group.remove());
            const group = document.createElement('optgroup'); group.label = tr('agent.mini.available_models');
            (catalog.data || []).filter(builderModelSupportsVisionChat).forEach(model => group.append(new Option(model.id, 'model:'+model.id)));
            if (group.children.length) select.append(group);
            select.value = [...select.options].some(option => option.value === selected) ? selected : 'tier:standard';
        } catch (_) { /* System Task choices remain available. */ }
    }
    async function createDraft(name = 'New Agent', description = '', steps = []) {
        const scope = pageScope();
        const source = {
            schema: 'ai2apps.site-agent-source/v1', name, description,
            site_scope: scope ? [scope] : [],
            capabilities: [{id:'run', name:'site.run', title:description || 'Run',
                description, inputs:{type:'object',properties:{}},
                outputs:{type:'object',properties:{}}, steps:steps.map(normalizedStep)}],
        };
        source.authoring = {saved: false};
        state.draft = {
            id: null, revision: 0, status: 'editing', active_generation_id: null,
            name, description, site_scope: source.site_scope, source,
        };
        state.capabilityId = 'run';
        renderDraft();
        return state.draft;
    }
    async function openDraft(id) {
        state.draft = await api('/agent-drafts/' + encodeURIComponent(id));
        state.capabilityId = state.draft.source?.capabilities?.[0]?.id || null;
        renderDraft();
        switchMode('build');
    }
    async function persistDraft({explicit = false} = {}) {
        if (!state.draft) await createDraft();
        syncEditor();
        const source = state.draft.source;
        source.authoring = {
            ...(source.authoring || {}),
            saved: explicit || source.authoring?.saved === true,
        };
        if (!state.draft.id) {
            state.draft = await api('/agent-drafts', {
                method: 'POST',
                body: JSON.stringify({
                    name: source.name, description: source.description || '',
                    site_scope: source.site_scope, source,
                }),
            });
        } else {
            state.draft = await api('/agent-drafts/' + encodeURIComponent(state.draft.id), {
                method: 'PATCH',
                body: JSON.stringify({
                    expected_revision: state.draft.revision,
                    name: source.name, site_scope: source.site_scope, source,
                }),
            });
        }
        renderDraft();
        await refreshDrafts();
        if (explicit) notice(tr('agent.mini.saved'), 'success');
        return state.draft;
    }
    async function saveDraft() {
        return persistDraft({explicit: true});
    }
    async function deleteDraft() {
        if (!state.draft) return;
        const name = state.draft.name || state.draft.source?.name || 'Agent';
        if (!window.confirm(tr('agent.mini.delete_confirm', {name}))) return;
        if (state.draft.id) {
            await api('/agent-drafts/' + encodeURIComponent(state.draft.id) + '/archive', {
                method: 'POST',
                body: JSON.stringify({expected_revision: state.draft.revision}),
            });
        }
        state.draft = null;
        state.capabilityId = null;
        await refreshDrafts();
        switchMode('run');
        notice(tr('agent.mini.deleted'), 'success');
    }
    function scopeAllows(url, scopes) {
        if (!scopes?.length) return true;
        let destination;
        try { destination = new URL(url); } catch (_) { return false; }
        if (!['http:', 'https:'].includes(destination.protocol)) return false;
        const glob = (value, pattern) => new RegExp('^' + pattern
            .replace(/[.+?^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*') + '$').test(value);
        return scopes.some(scope => {
            try {
                const allowed = new URL(scope);
                return destination.protocol === allowed.protocol && destination.port === allowed.port &&
                    glob(destination.hostname, allowed.hostname) &&
                    glob(destination.pathname + (allowed.search ? destination.search : ''), allowed.pathname + allowed.search);
            } catch (_) { return false; }
        });
    }
    async function client() {
        if (state.client) return state.client;
        const revision = state.contextRevision;
        const candidate = new window.AI2AppsBiDi.AI2AppsPageClient({...state.context});
        state.client = candidate;
        try {
            await candidate.connect();
            candidate.connection.socket.addEventListener('close', () => {
                if (state.client === candidate) state.client = null;
            }, {once: true});
            const page = await candidate.pageState();
            if (revision !== state.contextRevision || state.client !== candidate) {
                await candidate.connection.close().catch(() => {});
                throw new Error('The current browser page changed');
            }
            state.page = page;
            return candidate;
        } catch (error) {
            if (state.client === candidate) state.client = null;
            throw error;
        }
    }
    function intent(step) {
        return step.target?.accessible_name || step.target?.intent || step.description || '';
    }
    function interactionPolicy(step, target) {
        const text = [step.description, intent(step), target?.name, target?.role]
            .filter(Boolean).join(' ').toLowerCase();
        if (/captcha|verify you are human|验证码|机器人验证/.test(text)) {
            return {outcome: 'needs_user', reason: 'captcha'};
        }
        if (/paywall|checkout|purchase|buy now|subscribe to continue|付款|支付|购买|付费墙|订阅后继续/.test(text)) {
            return {outcome: 'restricted', reason: 'payment_or_paywall'};
        }
        if (/terms of service|privacy terms|legal agreement|服务条款|法律条款|隐私条款/.test(text) &&
            /accept|agree|同意|接受/.test(text)) {
            return {outcome: 'needs_user', reason: 'legal_consent'};
        }
        return null;
    }
    function inputValue(step) {
        if (step.arguments?.value != null) return String(step.arguments.value);
        const match = step.description.match(/[“"']([^”"']+)[”"']/);
        return match ? match[1] : '';
    }
    function resolveInput(value, invocationInput) {
        if (Array.isArray(value)) return value.map(item => resolveInput(item, invocationInput));
        if (value && typeof value === 'object') return Object.fromEntries(
            Object.entries(value).map(([key, item]) => {
                if (key === 'url' && typeof item === 'string' && !/^\$\{input\.[^}]+\}$/.test(item)) {
                    return [key, item.replace(/\$\{input\.([a-zA-Z0-9_.-]+)\}/g,
                        (_match, path) => encodeURIComponent(String(resolveInput('${input.'+path+'}', invocationInput))))];
                }
                return [key, resolveInput(item, invocationInput)];
            }));
        if (typeof value !== 'string') return value;
        const exact = value.match(/^\$\{input\.([a-zA-Z0-9_.-]+)\}$/);
        const lookup = path => {
            const value = path.split('.').reduce((item, key) =>
                item && Object.hasOwn(item, key) ? item[key] : undefined, invocationInput);
            if (value === undefined) throw new Error(tr('agent.mini.parameter_required', {name:path}));
            return value;
        };
        if (exact) return lookup(exact[1]);
        return value.replace(/\$\{input\.([a-zA-Z0-9_.-]+)\}/g,
            (_match, path) => String(lookup(path) ?? ''));
    }
    async function execute(step, preview = false, scopes = null) {
        const bidi = await client();
        const before = await bidi.pageState();
        const effectiveScopes = scopes || state.draft?.site_scope || [];
        const op = step.operation;
        const searchEnter = ['input', 'click'].includes(op) &&
            requestedSearchInteraction(step, state.exploration?.goal || state.review?.source?.description || state.draft?.description || '', before.url) &&
            /press.*enter|回车/i.test(step.description || '');
        // Navigation enters the authorized site; it need not start there.
        // Validate its destination before preview or any browser mutation.
        const navigationURL = op === 'open' ? step.arguments?.url ||
            (step.description.match(/https?:\/\/[^\s，。]+/) || [])[0] : null;
        if (op === 'open' && !navigationURL) {
            return {outcome: 'needs_user', evidence: {reason: 'url_required', before}};
        }
        if (op === 'open' && !scopeAllows(navigationURL, effectiveScopes)) {
            return {outcome: 'restricted', evidence: {reason: 'navigation_outside_scope', url: navigationURL, before}};
        }
        if (op !== 'open' && !scopeAllows(before.url, effectiveScopes)) {
            return {outcome: 'restricted', evidence: {reason: 'site_scope', before}};
        }
        if (preview && ['open', 'read_results', 'page_access', 'click', 'delete', 'input', 'hover', 'scroll'].includes(op)) {
            const target = ['click', 'delete', 'input', 'hover'].includes(op)
                ? await bidi.findTarget(intent(step), {operation:searchEnter ? 'input' : op}) : null;
            return {
                outcome: target === null && ['click', 'delete', 'input', 'hover'].includes(op)
                    ? 'not_found' : 'success',
                evidence: {preview: true, operation: op, target, before},
            };
        }
        let result;
        if (op === 'page_access') result = await bidi.handlePageAccess();
        else if (op === 'read_results') {
            result = await bidi.readResultPages(step.arguments?.items, step.arguments?.limit || 3);
            if (!result.articles.length) return {outcome:'failed', evidence:{operation:op, result, before}};
        } else if (op === 'extract_list') {
            result = await bidi.extractArticleList(Number(step.arguments?.limit || 50));
        } else if (op === 'inspect') {
            const query = intent(step);
            result = query ? {page: before, target: await bidi.findTarget(query)} : {page: before};
        } else if (['click', 'delete', 'hover', 'input'].includes(op)) {
            // Fail closed from the authored intent before resolving or touching a
            // page element.  A missing/renamed button must not downgrade an
            // explicit legal-consent, CAPTCHA, or payment request to not_found.
            const requestedPolicy = interactionPolicy(step, null);
            if (requestedPolicy) {
                return {outcome: requestedPolicy.outcome,
                    evidence: {...requestedPolicy, before}};
            }
            const target = await bidi.findTarget(intent(step), {operation:searchEnter ? 'input' : op});
            if (!target) return {outcome: 'not_found', evidence: {operation: op, intent: intent(step), before}};
            const policy = interactionPolicy(step, target);
            if (policy) return {outcome: policy.outcome, evidence: {...policy, target, before}};
            if ((op === 'input' || searchEnter) && target.sensitive) {
                return {outcome: 'needs_user', evidence: {reason: 'sensitive_input', target, before}};
            }
            await bidi.naturalPointer(target, {
                click: op !== 'hover', hoverMs: op === 'hover' ? 650 : 0,
                seed: Number(step.source_index || 0) + 7,
            });
            if (op === 'input') {
                const value = inputValue(step);
                const submitSearch = requestedSearchInteraction(step, state.exploration?.goal || state.review?.source?.description || state.draft?.description || '', before.url) &&
                    /\bsubmit\b|press.*enter|提交|回车/i.test(step.description || '');
                if (!value && !submitSearch) return {outcome: 'needs_user', evidence: {reason: 'input_value_required', target, before}};
                await bidi.typeText(value, {replace:Boolean(value), submit:submitSearch});
            }
            if (op === 'click' && searchEnter) await bidi.typeText('', {submit:true});
            result = {target, interaction_profile: 'natural'};
        } else if (op === 'scroll') {
            const delta = Number(step.arguments?.delta_y || 620);
            await bidi.scroll(delta);
            result = {delta_y: delta, interaction_profile: 'natural'};
        } else if (op === 'open') {
            const url = navigationURL;
            await bidi.connection.command('browsingContext.navigate', {
                context: bidi.contextId, url, wait: 'complete',
            }, 30000);
            result = {url};
        } else if (op === 'complete') result = {complete: true};
        else return {outcome: 'failed', evidence: {reason: 'unsupported_operation', operation: op}};
        const after = await bidi.pageState();
        return {outcome: result?.classification === 'needs_user' ? 'needs_user' :
            result?.classification === 'restricted' ? 'restricted' : 'success',
            evidence: {operation: op, result, before, after}};
    }
    async function saveEvidence(step, execution, runId = null) {
        if (!state.draft?.id) return;
        const page = execution.evidence?.after || execution.evidence?.before || state.page || {};
        await api('/agent-drafts/' + encodeURIComponent(state.draft.id) +
            '/steps/' + encodeURIComponent(step.id) + '/evidence', {
            method: 'POST',
            body: JSON.stringify({
                outcome: execution.outcome,
                evidence: execution.evidence,
                generation_id: state.draft.active_generation_id,
                run_id: runId,
                page_fingerprint: page.fingerprint || '',
            }),
        });
    }
    async function plannedStep(index) {
        syncEditor();
        await persistDraft();
        const sourceStep = currentCapability().steps[index];
        const plan = await api('/agent-drafts/' + encodeURIComponent(state.draft.id) +
            '/steps/' + encodeURIComponent(sourceStep.name) + '/plan?capability_id=' +
            encodeURIComponent(state.capabilityId || ''), {method: 'POST', body: '{}'});
        if (!plan.valid || !plan.step) {
            const errors = (plan.report?.errors || []).map(item => item.code).join(', ');
            throw new Error(tr('agent.mini.invalid_step', { error: errors || 'invalid step' }));
        }
        return plan.step;
    }
    async function runEditorStep(index, preview) {
        return withBusy(async () => {
            const input = readInputFields($('#agent-build-inputs'), currentCapability()?.inputs);
            const step = resolveInput(await plannedStep(index), input);
            notice(tr(preview ? 'agent.mini.previewing' : 'agent.mini.running', { step: step.id }));
            const result = await execute(step, preview);
            await saveEvidence(step, result);
            notice(step.id + ' → ' + result.outcome, result.outcome === 'success' ? 'success' : 'warning');
            return result;
        });
    }
    function renderRun(run) {
        if (run?.id !== state.run?.id) state.resultMode = 'json';
        state.run = run;
        const panel = $('#agent-run-status');
        panel.hidden = !run;
        if (!run) {
            $('#agent-run-handoff').hidden = true;
            renderRunResult(null);
            return;
        }
        $('#agent-run-label').textContent = 'AgentRun · ' + run.status;
        $('#agent-run-detail').textContent = run.id + ' · step ' + (run.current_step || 0);
        $('#agent-run-pause').hidden = !['queued', 'planning', 'running'].includes(run.status);
        $('#agent-run-continue').hidden = !['waiting_input', 'interrupted'].includes(run.status);
        $('#agent-run-stop').hidden = ['completed', 'failed', 'cancelled'].includes(run.status);
        $('#agent-run-handoff').hidden = run.status !== 'completed';
        renderRunResult(run);
    }

    function addExplorationEvent(phase, title, detail = '', tone = '') {
        if (!state.exploration) return;
        state.exploration.events.push({phase, title, detail, tone});
        renderExploration();
    }

    function renderExploration() {
        const exploration = state.exploration;
        const panel = $('#agent-exploration');
        panel.hidden = !exploration;
        if (!exploration) return;
        $('#agent-exploration-summary').textContent = tr('agent.mini.exploration_budget', {
            count: exploration.attempts.length, max: exploration.maxSteps,
        });
        const status = $('#agent-exploration-state');
        status.textContent = statusText(exploration.status);
        status.dataset.status = exploration.status;
        $('#agent-exploration-stop').hidden = exploration.status !== 'running';
        const timeline = $('#agent-exploration-timeline');
        timeline.replaceChildren();
        exploration.events.forEach(event => {
            const item = document.createElement('article');
            item.className = 'agent-exploration-event' + (event.tone ? ' ' + event.tone : '');
            const marker = document.createElement('span');
            marker.textContent = tr('agent.mini.exploration_' + event.phase);
            const body = document.createElement('div');
            const title = document.createElement('strong');
            title.textContent = event.title;
            const detail = document.createElement('small');
            detail.textContent = event.detail;
            body.append(title, detail);
            item.append(marker, body);
            timeline.append(item);
        });
        timeline.lastElementChild?.scrollIntoView?.({block: 'nearest'});
    }

    function navigationMentionedInGoal(step, goal) {
        if (step.operation !== 'open') return false;
        let host;
        try {
            const url = new URL(step.arguments?.url || '');
            if (!['http:', 'https:'].includes(url.protocol)) return false;
            host = url.hostname.toLowerCase().replace(/^www\./, '');
        } catch (_) { return false; }
        const text = String(goal || '').toLowerCase();
        const domains = text.match(/(?:https?:\/\/)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?::\d+)?/g) || [];
        if (domains.some(domain => {
            try { return new URL(/^https?:/.test(domain) ? domain : 'https://' + domain)
                .hostname.replace(/^www\./, '') === host; }
            catch (_) { return false; }
        })) return true;
        const names = {
            'google.com': ['google', '谷歌'], 'google.cn': ['google', '谷歌'],
            'bing.com': ['bing', '必应'], 'baidu.com': ['baidu', '百度'],
            'wikipedia.org': ['wikipedia', '维基百科'],
            'youtube.com': ['youtube'], 'github.com': ['github'],
            'openai.com': ['openai'], 'reddit.com': ['reddit'],
            'taobao.com': ['淘宝', 'taobao'], 'jd.com': ['京东'],
        };
        return (names[host] || (host.endsWith('.wikipedia.org') ? names['wikipedia.org'] : []))
            .some(name => /[^a-z]/.test(name) ? text.includes(name) :
                new RegExp('(^|[^a-z0-9])' + name + '([^a-z0-9]|$)').test(text));
    }

    function requestedSearchInteraction(step, goal, pageURL) {
        if (!['input', 'click'].includes(step.operation) || !/搜索|查询|\bsearch\b|\bfind\b/i.test(goal)) return false;
        let url;
        try { url = new URL(pageURL); } catch (_) { return false; }
        if (!['http:', 'https:'].includes(url.protocol) ||
            !['google.com', 'google.cn', 'bing.com', 'baidu.com'].includes(
                url.hostname.toLowerCase().replace(/^www\./, ''))) return false;
        const target = step.target?.accessible_name || step.target?.intent || '';
        const text = target + ' ' + (step.description || '');
        if (/delete|publish|send|purchase|pay|checkout|login|sign.?in|password|captcha|authorize|agree|accept|删除|发布|发送|购买|支付|登录|密码|验证码|授权|同意|接受/i.test(text)) return false;
        return /搜索|查询|\bsearch\b|\bquery\b/i.test(target || step.description || '');
    }

    function explorationActionNeedsConfirmation(step, decision, goal = '', pageURL = '') {
        if (navigationMentionedInGoal(step, goal)) return false;
        // A requested search includes entering the query and submitting it.
        // The generic server "submit" flag also covers search forms; target
        // resolution and sensitive-input/interaction policy still run below.
        if (requestedSearchInteraction(step, goal, pageURL)) return false;
        if (decision.confirmation?.required) return true;
        return ['open', 'page_access', 'click', 'input', 'hover', 'delete']
            .includes(String(step.operation || ''));
    }

    async function distillExploration() {
        const exploration = state.exploration;
        addExplorationEvent('distill', tr('agent.mini.exploration_distill'),
            tr('agent.mini.exploration_successful_steps', {
                count: exploration.attempts.filter(item => item.outcome === 'success').length,
            }));
        const result = await api('/agent-explorations/distill', {
            method: 'POST',
            body: JSON.stringify({
                goal: exploration.goal,
                attachments: exploration.attachments,
                name: exploration.name,
                page: {url: state.page?.url || state.context.url || '', title: state.page?.title || ''},
                attempts: exploration.attempts,
            }),
        });
        state.recipe = result.recipe;
        state.review = result.review;
        rememberRecipe();
        state.previousReview = null;
        exploration.status = 'awaiting_review';
        addExplorationEvent('complete', tr('agent.mini.exploration_complete'),
            tr('agent.mini.exploration_compiled_steps', {
                count: result.review.steps?.length || 0,
            }), 'success');
        $('#agent-recipe-confirm').hidden = false;
        renderRecipeReview();
        const last = [...exploration.attempts].reverse().find(item =>
            item.outcome === 'success' && item.evidence?.result !== undefined);
        if (last) {
            state.run = {
                id: 'exploration-' + Date.now(), status: 'completed',
                ephemeral: true,
                output: {result: last.evidence.result},
            };
            renderRunResult(state.run);
        }
        notice(tr('agent.mini.review_ready'), 'success');
        return result;
    }

    async function startExploration(goal) {
        setContextPinned(true);
        const name = goal.slice(0, 42);
        // An exploratory build is its own foreground activity.  Do not leave a
        // previously restored AgentRun card above the new result/review flow;
        // that stale status makes a successful exploration look cancelled or
        // failed.  A real recipe test will render its own AgentRun again.
        renderRun(null);
        state.recipe = null;
        state.review = null;
        state.previousReview = null;
        $('#agent-recipe-confirm').hidden = true;
        renderRecipeReview();
        state.exploration = {
            goal, name, attachments:state.attachments.map(file => file.asset_id), status: 'running', cancelled: false,
            scopes: pageScope() ? [pageScope()] : [],
            maxSteps: 12, attempts: [], events: [],
            modelSelection: builderSelection(),
        };
        renderExploration();
        try {
        for (let index = 0; index < state.exploration.maxSteps; index++) {
            if (state.exploration.cancelled) {
                state.exploration.status = 'cancelled';
                addExplorationEvent('evaluate', tr('agent.mini.exploration_stopped'), '', 'warning');
                setContextPinned(false);
                return null;
            }
            const observation = await (await client()).explorationObservation();
            state.page = {url: observation.url, title: observation.title,
                fingerprint: observation.fingerprint};
            addExplorationEvent('observe', observation.title || observation.url,
                `${observation.control_count} controls · ${observation.text_length} chars`);
            const decision = await api('/agent-explorations/next', {
                method: 'POST',
                body: JSON.stringify({
                    goal, name, attachments:state.exploration.attachments, ...state.exploration.modelSelection,
                    page: {url: observation.url, title: observation.title},
                    observation: {
                        fingerprint: observation.fingerprint,
                        text_length: observation.text_length,
                        link_count: observation.link_count,
                        button_count: observation.button_count,
                        control_count: observation.control_count,
                    },
                    attempts: state.exploration.attempts,
                }),
            });
            if (decision.decision === 'complete') {
                addExplorationEvent('evaluate',
                    decision.reason || tr('agent.mini.exploration_goal_satisfied'), '', 'success');
                return distillExploration();
            }
            const step = decision.compiled_step;
            if (decision.model_escalated) {
                addExplorationEvent('model', tr('models.defaults.work_complex.title'),
                    decision.model_id || '', 'warning');
            }
            addExplorationEvent('propose', step.description || step.id,
                decision.reason || decision.expected_effect || '');
            addExplorationEvent('preflight', `${step.operation} · ${step.effect}`,
                decision.preflight?.source_digest || '', 'success');
            if (explorationActionNeedsConfirmation(step, decision, goal, observation.url)) {
                const approved = window.confirm(
                    `${step.description || step.operation}\n\n${decision.expected_effect || ''}`);
                if (!approved) {
                    state.exploration.attempts.push({
                        proposal_id: decision.proposal_id,
                        source_step: decision.source_step,
                        outcome: 'restricted', evidence: {reason: 'user_denied_confirmation'},
                    });
                    addExplorationEvent('evaluate', tr('agent.mini.exploration_restricted'),
                        'User denied confirmation', 'warning');
                    continue;
                }
            }
            addExplorationEvent('execute', step.description || step.operation,
                decision.expected_effect || '');
            // Reaching here means navigation was explicitly requested or its
            // confirmation was approved. Carry that grant across later steps.
            if (step.operation === 'open') {
                const destination = new URL(step.arguments?.url || '');
                if (['http:', 'https:'].includes(destination.protocol)) {
                    const scope = destination.origin + '/**';
                    if (!state.exploration.scopes.includes(scope)) state.exploration.scopes.push(scope);
                }
            }
            const execution = await execute(step, false, state.exploration.scopes);
            state.exploration.attempts.push({
                proposal_id: decision.proposal_id,
                source_step: decision.source_step,
                compiled_step: decision.compiled_step,
                expected_effect: decision.expected_effect,
                outcome: execution.outcome,
                evidence: execution.evidence,
            });
            addExplorationEvent('evaluate', execution.outcome,
                execution.evidence?.reason || execution.evidence?.after?.fingerprint || '',
                execution.outcome === 'success' ? 'success' : 'warning');
            if (execution.outcome === 'needs_user' || execution.outcome === 'restricted') {
                state.exploration.status = execution.outcome;
                renderExploration();
                notice(tr('agent.mini.needs_user'), 'warning');
                return null;
            }
        }
        state.exploration.status = 'budget_exhausted';
        addExplorationEvent('evaluate', tr('agent.mini.exploration_limit'), '', 'warning');
        throw new Error(tr('agent.mini.exploration_limit'));
        } catch (error) {
            if (state.exploration?.status === 'running') {
                state.exploration.status = 'failed';
                addExplorationEvent('evaluate', tr('agent.mini.exploration_failed'),
                    error.message || String(error), 'error');
                renderExploration();
            }
            setContextPinned(false);
            throw error;
        }
    }

    function sameReviewStep(left, right) {
        if (!left || !right) return false;
        return JSON.stringify({source:left.source, compiled:left.compiled}) ===
            JSON.stringify({source:right.source, compiled:right.compiled});
    }

    function reviewStepText(step, compiled = false) {
        const value = compiled ? step.compiled : step.source;
        if (!value) return tr('agent.mini.invalid');
        const lines = [];
        if (!compiled && value.description) lines.push(value.description);
        lines.push(`${compiled ? 'operation' : 'operation hint'}: ${value.operation || '—'}`);
        if (compiled) {
            lines.push(`effect: ${value.effect || '—'}`);
            lines.push(`mode: ${value.mode || '—'}`);
        } else if (value.ai?.tier) lines.push(`AI: ${value.ai.tier}`);
        if (value.target && Object.keys(value.target).length) {
            lines.push(`target: ${JSON.stringify(value.target)}`);
        }
        if (value.arguments && Object.keys(value.arguments).length) {
            lines.push(`arguments: ${JSON.stringify(value.arguments)}`);
        }
        if (value.when) lines.push(`when: ${JSON.stringify(value.when)}`);
        if (value.on && Object.keys(value.on).length) {
            lines.push(`on: ${JSON.stringify(value.on)}`);
        }
        return lines.join('\n');
    }

    function renderRecipeReview() {
        const review = state.review;
        const panel = $('#agent-recipe-review');
        panel.hidden = !review;
        if (!review) return;
        const valid = Boolean(review.compiler?.valid);
        const effects = review.compiler?.effects || [];
        $('#agent-review-summary').textContent =
            `v${review.source_revision} · ${valid ? tr('agent.mini.valid') : tr('agent.mini.invalid')} · ${effects.join(', ') || 'read'}`;
        const status = $('#agent-review-status');
        status.textContent = statusText(review.status);
        status.dataset.status = review.status;
        const list = $('#agent-review-steps');
        list.replaceChildren();
        (review.steps || []).forEach((step, index) => {
            const previous = state.previousReview?.steps?.find(item =>
                item.mapping?.compiled_step_id === step.mapping?.compiled_step_id ||
                item.index === step.index);
            const changed = Boolean(state.previousReview) && !sameReviewStep(previous, step);
            const card = document.createElement('article');
            card.className = 'agent-review-step' + (changed ? ' changed' : '');
            const header = document.createElement('header');
            const title = document.createElement('strong');
            title.textContent = `${index + 1}. ${step.source?.name || step.compiled?.id || 'Step'}`;
            header.append(title);
            if (changed) {
                const badge = document.createElement('span');
                badge.textContent = tr('agent.mini.changed');
                header.append(badge);
            }
            const grid = document.createElement('div');
            grid.className = 'agent-review-compare';
            [[tr('agent.mini.before_compile'), false], [tr('agent.mini.after_compile'), true]]
                .forEach(([label, compiled]) => {
                    const side = document.createElement('section');
                    const heading = document.createElement('small');
                    heading.textContent = label;
                    const pre = document.createElement('pre');
                    pre.textContent = reviewStepText(step, compiled);
                    side.append(heading, pre);
                    grid.append(side);
                });
            card.append(header, grid);
            if (step.source?.operation?.startsWith('ai.')) {
                const label = document.createElement('label'); label.className = 'agent-field';
                const title = document.createElement('span'); title.textContent = tr('agent.mini.step_model');
                const select = tierSelect(step.source.ai?.tier);
                select.onchange = () => withBusy(async () => {
                    let result;
                    try { result = await api('/agent-recipes/'+encodeURIComponent(state.recipe.id)+'/steps/model-tier', {
                        method:'POST', body:JSON.stringify({expected_revision:state.review.source_revision, step_index:index, tier:select.value}),
                    }); } catch (error) { renderRecipeReview(); throw error; }
                    state.previousReview = state.review; state.recipe = result.recipe; state.review = result.review;
                    renderRecipeReview(); notice(tr('agent.mini.step_model_saved'), 'success');
                });
                label.append(title, select); card.append(label);
            }
            list.append(card);
        });
        $('#agent-review-source').textContent = JSON.stringify(review.source, null, 2);
        $('#agent-review-ir').textContent = JSON.stringify(review.compiled_ir, null, 2);
        renderInputFields($('#agent-recipe-inputs'), review.source?.inputs);
        const approved = review.status === 'approved';
        $('#agent-review-approve').disabled = approved || !valid;
        $('#agent-review-revise').disabled = !valid;
        $('#agent-review-commit').hidden = !approved;
    }

    async function loadRecipeReview() {
        if (!state.recipe) return null;
        state.review = await api('/agent-recipes/' + encodeURIComponent(state.recipe.id) + '/review');
        renderRecipeReview();
        return state.review;
    }
    function rememberRecipe() {
        const url = new URL(location.href);
        if (state.recipe) url.searchParams.set('recipe_id', state.recipe.id);
        else url.searchParams.delete('recipe_id');
        history.replaceState(history.state, '', url.pathname + url.search + url.hash);
    }

    function reviewProgress(phase, detail) {
        const overlay = $('#agent-review-progress');
        const waiting = phase === 'waiting';
        overlay.hidden = false;
        overlay.dataset.phase = phase;
        $('.agent-mini').inert = true;
        $('#agent-review-progress-title').textContent = tr(waiting
            ? 'agent.mini.review_revising'
            : phase === 'success' ? 'agent.mini.review_revised' : 'agent.mini.review_failed');
        $('#agent-review-progress-detail').textContent = detail || tr('agent.mini.review_wait_hint');
        const close = $('#agent-review-progress-close');
        close.hidden = waiting;
        if (!waiting) close.focus();
    }

    async function reviseRecipeReview() {
        if (!state.recipe || !state.review) return;
        const feedback = $('#agent-review-feedback').value.trim();
        if (!feedback) return;
        reviewProgress('waiting');
        const previous = state.review;
        try {
            const result = await api('/agent-recipes/' + encodeURIComponent(state.recipe.id) +
                '/review/revisions', {method:'POST', body:JSON.stringify({
                    expected_revision: state.review.source_revision,
                    feedback,
                    ...builderSelection(),
                    locale: document.documentElement.lang || 'en',
                })});
            state.recipe = result.recipe;
            state.previousReview = previous;
            state.review = result.review;
            $('#agent-review-feedback').value = '';
            renderRecipeReview();
            reviewProgress('success', `v${result.review.source_revision} · ${previous.steps.length} → ${result.review.steps.length}`);
        } catch (error) {
            const report = error.details?.report?.errors || [];
            const details = report.map(item => item.message || item.code).filter(Boolean).join('\n');
            reviewProgress('error', [error.message, details].filter(Boolean).join('\n'));
        }
    }

    async function approveRecipeReview() {
        if (!state.recipe || !state.review) return;
        const result = await api('/agent-recipes/' + encodeURIComponent(state.recipe.id) +
            '/review/approve', {method:'POST', body:JSON.stringify({
                expected_revision: state.review.source_revision,
            })});
        state.recipe = result.recipe;
        state.review = result.review;
        renderRecipeReview();
        notice(tr('agent.mini.review_approved'), 'success');
    }
    function resultFromRun(run) {
        if (!run || run.status !== 'completed') return null;
        if (run.output && Object.hasOwn(run.output, 'result')) return run.output.result;
        const evidence = Array.isArray(run.output?.evidence) ? run.output.evidence : [];
        for (let index = evidence.length - 1; index >= 0; index--) {
            const entry = evidence[index];
            if (entry?.evidence && Object.hasOwn(entry.evidence, 'result')) {
                return entry.evidence.result;
            }
        }
        return run.output || null;
    }
    function valueAtPath(value, path) {
        if (path === '$') return {found: true, value};
        const parts = (path.startsWith('$.') ? path.slice(2) : path).split('.');
        let current = value;
        for (const part of parts) {
            if (!current || typeof current !== 'object' || !Object.hasOwn(current, part)) {
                return {found: false, value: null};
            }
            current = current[part];
        }
        return {found: true, value: current};
    }
    function safeMediaUrl(value) {
        try {
            const url = new URL(String(value), state.page?.url || location.href);
            return ['http:', 'https:'].includes(url.protocol) ? url.href : '';
        } catch (_) { return ''; }
    }
    function displayValue(value) {
        if (value === null) return 'null';
        if (value === undefined) return '';
        if (typeof value === 'object') return JSON.stringify(value, null, 2);
        return String(value);
    }
    function appendPresentedValue(parent, value, field) {
        const node = document.createElement(field.primary ? 'strong' : 'span');
        if (field.format === 'link') {
            const url = safeMediaUrl(value);
            if (url) {
                const link = document.createElement('a');
                link.href = url;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                link.textContent = displayValue(value);
                node.append(link);
            } else node.textContent = displayValue(value);
        } else if (field.format === 'image') {
            const url = safeMediaUrl(value);
            if (url) {
                const image = document.createElement('img');
                image.src = url;
                image.alt = field.label;
                image.loading = 'lazy';
                image.referrerPolicy = 'no-referrer';
                node.append(image);
            } else node.textContent = displayValue(value);
        } else if (field.format === 'number' && typeof value === 'number') {
            node.textContent = new Intl.NumberFormat(document.documentElement.lang).format(value);
        } else {
            node.textContent = displayValue(value);
            if (field.format === 'badge') node.classList.add('agent-result-badge');
        }
        parent.append(node);
    }
    function unmappedRecord(row, fields) {
        if (!row || typeof row !== 'object' || Array.isArray(row)) return null;
        const mapped = new Set(fields.map(field => field.path.replace(/^\$\.?/, '').split('.')[0]));
        const entries = Object.entries(row).filter(([key]) => !mapped.has(key));
        return entries.length ? Object.fromEntries(entries) : null;
    }
    function appendUnmapped(parent, row, spec) {
        if (!spec.show_unmapped_fields) return;
        const rest = unmappedRecord(row, spec.fields);
        if (!rest) return;
        const details = document.createElement('details');
        const label = document.createElement('summary');
        label.textContent = tr('agent.mini.other_fields');
        const pre = document.createElement('pre');
        pre.textContent = JSON.stringify(rest, null, 2);
        details.append(label, pre);
        parent.append(details);
    }
    function renderPresentation(result, spec, content) {
        const target = valueAtPath(result, spec.data_path).value;
        const rows = spec.view === 'key_value' ? [target] : target;
        if (spec.view === 'table') {
            const wrapper = document.createElement('div');
            wrapper.className = 'agent-result-table-wrap';
            const table = document.createElement('table');
            const head = document.createElement('thead');
            const heading = document.createElement('tr');
            const includeOther = spec.show_unmapped_fields &&
                rows.some(row => unmappedRecord(row, spec.fields));
            spec.fields.forEach(field => {
                const cell = document.createElement('th');
                cell.textContent = field.label;
                heading.append(cell);
            });
            if (includeOther) {
                const cell = document.createElement('th');
                cell.textContent = tr('agent.mini.other_fields');
                heading.append(cell);
            }
            head.append(heading);
            const body = document.createElement('tbody');
            rows.forEach(row => {
                const line = document.createElement('tr');
                spec.fields.forEach(field => {
                    const cell = document.createElement('td');
                    const found = valueAtPath(row, field.path);
                    if (found.found) appendPresentedValue(cell, found.value, field);
                    line.append(cell);
                });
                if (includeOther) {
                    const cell = document.createElement('td');
                    const rest = unmappedRecord(row, spec.fields);
                    cell.textContent = rest ? JSON.stringify(rest, null, 2) : '';
                    line.append(cell);
                }
                body.append(line);
            });
            table.append(head, body);
            wrapper.append(table);
            content.append(wrapper);
        } else if (spec.view === 'key_value') {
            const list = document.createElement('dl');
            list.className = 'agent-result-kv';
            spec.fields.forEach(field => {
                const found = valueAtPath(target, field.path);
                if (!found.found) return;
                const term = document.createElement('dt');
                term.textContent = field.label;
                const detail = document.createElement('dd');
                appendPresentedValue(detail, found.value, field);
                list.append(term, detail);
            });
            content.append(list);
            appendUnmapped(content, target, spec);
        } else {
            const list = document.createElement(spec.view === 'list' ? 'ol' : 'div');
            list.className = spec.view === 'list' ? 'agent-result-list' : 'agent-result-cards';
            rows.forEach(row => {
                const item = document.createElement(spec.view === 'list' ? 'li' : 'article');
                spec.fields.forEach(field => {
                    const found = valueAtPath(row, field.path);
                    if (!found.found) return;
                    const line = document.createElement('div');
                    const label = document.createElement('small');
                    label.textContent = field.label;
                    line.append(label);
                    appendPresentedValue(line, found.value, field);
                    item.append(line);
                });
                appendUnmapped(item, row, spec);
                list.append(item);
            });
            content.append(list);
        }
    }
    function renderRunResult(run) {
        const panel = $('#agent-run-result');
        const content = $('#agent-run-result-content');
        const summary = $('#agent-run-result-summary');
        const result = resultFromRun(run);
        panel.hidden = result === null || result === undefined;
        content.replaceChildren();
        summary.textContent = '';
        if (panel.hidden) return;
        const items = Array.isArray(result?.items) ? result.items :
            (Array.isArray(result) ? result : null);
        if (items) summary.textContent = tr('agent.mini.result_count', {count: items.length});
        const spec = state.presentations.get(run.id);
        $('#agent-result-json').classList.toggle('active', state.resultMode === 'json');
        $('#agent-result-ai').classList.toggle('active', state.resultMode === 'ai');
        $('#agent-result-ai').textContent = spec ? tr('agent.mini.ai_view') : tr('agent.mini.ai_beautify');
        if (state.resultMode === 'ai' && spec) {
            if (spec.title) $('#agent-run-result-title').textContent = spec.title;
            renderPresentation(result, spec, content);
            return;
        }
        $('#agent-run-result-title').textContent = tr('agent.mini.result');
        const pre = document.createElement('pre');
        pre.className = 'agent-pretty-json';
        pre.textContent = JSON.stringify(result, null, 2) ?? String(result);
        content.append(pre);
    }
    async function beautifyRunResult() {
        if (!state.run || resultFromRun(state.run) == null) return;
        const existing = state.presentations.get(state.run.id);
        if (existing) {
            state.resultMode = 'ai';
            renderRunResult(state.run);
            return;
        }
        notice(tr('agent.mini.ai_beautifying'));
        try {
            const presentationPath = state.run.ephemeral && state.recipe?.id
                ? '/agent-recipes/' + encodeURIComponent(state.recipe.id) + '/presentation'
                : '/agent-draft-runs/' + encodeURIComponent(state.run.id) + '/presentation';
            const response = await api(presentationPath, {
                method: 'POST',
                body: JSON.stringify({locale: document.documentElement.lang || 'en'}),
            });
            state.presentations.set(state.run.id, response.presentation);
            state.resultMode = 'ai';
            renderRunResult(state.run);
            notice(tr('agent.mini.ai_beautified'), 'success');
        } catch (error) {
            state.resultMode = 'json';
            renderRunResult(state.run);
            const localized = [
                'standard_model_not_configured', 'standard_model_unavailable',
                'invalid_presentation_spec',
            ].includes(error.code) ? tr('agent.mini.' + error.code) : (error.message || String(error));
            const reason = error.code === 'invalid_presentation_spec' ? error.details?.reason : '';
            throw new Error(reason ? `${localized}\n${reason}` : localized);
        }
    }
    async function driveRun() {
        if (!state.run) return;
        setContextPinned(true);
        try {
        for (let poll = 0; poll < 180; poll++) {
            const run = await api('/agent-draft-runs/' + encodeURIComponent(state.run.id));
            renderRun(run);
            if (['completed', 'failed', 'cancelled'].includes(run.status)) {
                notice(run.status === 'completed' ? tr('agent.mini.run_complete') :
                    tr('agent.mini.run_failed', { status: run.status, error: run.error?.message || '' }),
                    run.status === 'completed' ? 'success' : 'warning');
                if (run.status === 'completed' && state.recipe) {
                    await loadRecipeReview();
                    notice(tr('agent.mini.review_ready'), 'success');
                } else {
                    setContextPinned(false);
                }
                return run;
            }
            const interaction = (run.interactions || []).find(item =>
                item.status === 'pending' && item.request?.control === 'browser_bidi_action');
            const confirmation = (run.interactions || []).find(item =>
                item.status === 'pending' && item.request?.control === 'agent_confirmation');
            if (confirmation) {
                const approved = window.confirm(
                    confirmation.request?.summary || confirmation.prompt || 'Confirm action?');
                await api('/agent-draft-runs/' + encodeURIComponent(run.id) +
                    '/interactions/' + encodeURIComponent(confirmation.id) + '/respond', {
                    method: 'POST',
                    body: JSON.stringify({
                        response: {decision: approved ? 'approve' : 'deny'},
                        response_id: crypto.randomUUID(),
                    }),
                });
                continue;
            }
            if (interaction) {
                if (interaction.request.draft_id &&
                    (!state.draft || state.draft.id !== interaction.request.draft_id)) {
                    state.draft = await api('/agent-drafts/' +
                        encodeURIComponent(interaction.request.draft_id));
                    renderDraft();
                }
                const step = resolveInput(interaction.request.step,
                    interaction.request.invocation_input || {});
                notice(tr('agent.mini.executing', { step: step.id }));
                const result = await execute(step, Boolean(interaction.request.preview),
                    interaction.request.site_scope || []);
                if (interaction.request.draft_id) await saveEvidence(step, result, run.id);
                if (result.outcome === 'needs_user') {
                    notice(tr('agent.mini.needs_user'), 'warning');
                    renderRun(run);
                    return run;
                }
                await api('/agent-draft-runs/' + encodeURIComponent(run.id) +
                    '/interactions/' + encodeURIComponent(interaction.id) + '/respond', {
                    method: 'POST',
                    body: JSON.stringify({
                        response: result,
                        response_id: crypto.randomUUID(),
                    }),
                });
                continue;
            }
            await new Promise(resolve => setTimeout(resolve, 350));
        }
        throw new Error(tr('agent.mini.timeout'));
        } catch (error) {
            if (!(state.recipe && state.review)) setContextPinned(false);
            throw error;
        }
    }
    async function runAll(preview = false) {
        return withBusy(async () => {
            const input = readInputFields($('#agent-build-inputs'), currentCapability()?.inputs);
            await persistDraft();
            const created = await api('/agent-drafts/' + encodeURIComponent(state.draft.id) +
                '/runs', {
                method: 'POST',
                body: JSON.stringify({
                    preview,
                    input,
                    capability_id: state.capabilityId,
                    browser_context: {
                        bidi_context: state.context.bidi_context || '',
                        url: state.page?.url || state.context.url || '',
                    },
                }),
            });
            renderRun(created);
            notice(tr('agent.mini.run_created'));
            return driveRun();
        });
    }
    async function pickTarget(index) {
        return withBusy(async () => {
            notice(tr('agent.mini.pick_prompt'));
            const picked = await (await client()).pickElement();
            if (!picked) throw new Error(tr('agent.mini.no_element'));
            const node = $$('.agent-step')[index];
            node._target = picked;
            node.querySelector('.agent-step-head span').textContent =
                picked.accessible_name || picked.tag;
            syncEditor();
            notice(tr('agent.mini.target_saved'), 'success');
        });
    }
    function moveStep(index, delta) {
        syncEditor();
        const steps = currentCapability().steps;
        const destination = index + delta;
        if (destination < 0 || destination >= steps.length) return;
        [steps[index], steps[destination]] = [steps[destination], steps[index]];
        renderSteps();
    }
    async function compileAndActivate() {
        return withBusy(async () => {
            await saveDraft();
            const generation = await api('/agent-drafts/' + encodeURIComponent(state.draft.id) +
                '/compile', {method: 'POST', body: '{}'});
            if (generation.status === 'failed') {
                const errors = (generation.report?.errors || []).map(item => item.code).join(', ');
                throw new Error(tr('agent.mini.compile_failed', { error: errors }));
            }
            state.draft = await api('/agent-drafts/' + encodeURIComponent(state.draft.id));
            state.draft = await api('/agent-drafts/' + encodeURIComponent(state.draft.id) +
                '/generations/' + encodeURIComponent(generation.id) + '/activate',
                {method: 'POST', body: '{}'});
            await refreshDrafts();
            renderDraft();
            notice(tr('agent.mini.compile_ready'), 'success');
        });
    }
    async function withBusy(action) {
        if (state.busy) return;
        state.busy = true;
        document.documentElement.classList.add('busy');
        try { return await action(); }
        catch (error) { notice(error.message || String(error), 'error'); }
        finally {
            state.busy = false;
            document.documentElement.classList.remove('busy');
        }
    }
    async function quickRun(event) {
        event.preventDefault();
        const description = $('#agent-quick-input').value.trim();
        if (!description) return;
        await withBusy(() => startExploration(description));
    }
    async function runRecipe() {
        if (!state.recipe) return;
        const created = await api('/agent-recipes/' + encodeURIComponent(state.recipe.id) + '/runs', {
            method:'POST', body:JSON.stringify({input:readInputFields($('#agent-recipe-inputs'), state.review?.source?.inputs),browser_context:{
                bidi_context:state.context.bidi_context || '', url:state.page?.url || state.context.url || '',
            }})
        });
        // Recipe creation returns a compact dispatch receipt (`run_id`), while
        // the run UI and polling loop consume the full AgentRun shape (`id`).
        // Hydrate the receipt before rendering so we never poll `/undefined`.
        const runId = created.id || created.run_id;
        if (!runId) throw new Error('Agent run was created without an id');
        const run = created.id ? created :
            await api('/agent-draft-runs/' + encodeURIComponent(runId));
        renderRun(run); notice(tr('agent.mini.recipe_testing')); return driveRun();
    }
    async function commitRecipe(mode) {
        if (!state.recipe) return;
        const result = await api('/agent-recipes/' + encodeURIComponent(state.recipe.id) + '/commit', {
            method:'POST', body:JSON.stringify({mode})
        });
        state.draft = result.site_agent;
        state.capabilityId = result.recipe.committed_capability_id;
        state.recipe = null; state.review = null; state.previousReview = null;
        rememberRecipe();
        $('#agent-recipe-confirm').hidden = true; renderRecipeReview();
        setContextPinned(false);
        await refreshDrafts(); renderDraft(); switchMode('build');
        notice(tr('agent.mini.capability_added'), 'success');
    }
    function bind() {
        $('#agent-editor-close').onclick = () => switchMode('run');
        $('#agent-notice-close').onclick = () => notice('');
        $('#agent-notice-close').setAttribute('aria-label', tr('agent.mini.close'));
        $('#agent-run-result-title').textContent = tr('agent.mini.result');
        $('#agent-result-json').textContent = tr('agent.mini.json_view');
        $('#agent-result-ai').textContent = tr('agent.mini.ai_beautify');
        $('#agent-result-json').onclick = () => {
            state.resultMode = 'json';
            renderRunResult(state.run);
        };
        $('#agent-result-ai').onclick = () => withBusy(beautifyRunResult);
        $('#agent-result-clear').onclick = () => {
            state.presentations.clear();
            renderRun(null);
        };
        $('#agent-quick-form').onsubmit = quickRun;
        $('#agent-attach-button').onclick = () => $('#agent-attach-input').click();
        $('#agent-gallery-button').onclick = chooseGalleryAttachments;
        $('#agent-attach-input').onchange = () => withBusy(async () => {
            try { await addAgentAttachments([...$('#agent-attach-input').files]); }
            finally { $('#agent-attach-input').value = ''; }
        });
        const attachmentZone = $('#agent-quick-form');
        attachmentZone.addEventListener('dragover', event => {
            if (!window.AI2AppsGalleryPicker.acceptsDrop(event.dataTransfer)) return;
            event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; attachmentZone.classList.add('agent-drop-active');
        });
        attachmentZone.addEventListener('dragleave',event => {if (!attachmentZone.contains(event.relatedTarget)) attachmentZone.classList.remove('agent-drop-active');});
        attachmentZone.addEventListener('drop', event => {
            if (!window.AI2AppsGalleryPicker.acceptsDrop(event.dataTransfer)) return;
            event.preventDefault(); attachmentZone.classList.remove('agent-drop-active');
            if (state.busy) return;
            const transfer = event.dataTransfer;
            const files = [...transfer.files];
            // Drag data is available only during the drop event.
            let ids;
            try { ids = window.AI2AppsGalleryPicker.droppedAssetIds(transfer); }
            catch (error) {void withBusy(async () => {throw error;}); return;}
            void withBusy(() => addAgentAttachments(ids.length ? [] : files, ids));
        });
        $('#agent-recipe-test').onclick = () => withBusy(runRecipe);
        $('#agent-infer-parameters').onclick = () => withBusy(async () => {
            if (!state.recipe || !state.review) return;
            const result = await api('/agent-recipes/' + encodeURIComponent(state.recipe.id) + '/parameters/infer', {
                method:'POST', body:JSON.stringify({expected_revision:state.review.source_revision}),
            });
            state.previousReview = state.review; state.recipe = result.recipe; state.review = result.review;
            renderRecipeReview();
        });
        $('#agent-exploration-stop').onclick = () => {
            if (state.exploration) state.exploration.cancelled = true;
        };
        $('#agent-review-progress-close').onclick = () => {
            $('#agent-review-progress').hidden = true;
            $('.agent-mini').inert = false;
            $('#agent-review-revise').focus();
        };
        $('#agent-review-revise').onclick = () => withBusy(reviseRecipeReview);
        $('#agent-review-approve').onclick = () => withBusy(approveRecipeReview);
        $('#agent-recipe-merge').onclick = () => withBusy(() => commitRecipe('merge'));
        $('#agent-recipe-create').onclick = () => withBusy(() => commitRecipe('create'));
        $('#agent-capability').onchange = event => { syncEditor(); state.capabilityId=event.target.value; renderParameters(); renderSteps(); };
        $('#agent-add-capability').onclick = () => {
            syncEditor();
            if (!Array.isArray(state.draft.source.capabilities)) return notice(tr('agent.mini.migrate_first'), 'warning');
            let n=state.draft.source.capabilities.length+1, id='capability-'+n;
            state.draft.source.capabilities.push({id, name:'site.'+id, title:'New capability',
                description:'', inputs:{type:'object',properties:{}}, outputs:{type:'object',properties:{}}, steps:[]});
            state.capabilityId=id; renderDraft();
        };
        $('#agent-refresh').onclick = () => withBusy(() => initialize({restoreCompleted:false}));
        $('#agent-new-from-run').onclick = () => withBusy(async () => {
            await createDraft(); switchMode('build');
        });
        $('#agent-add-step').onclick = () => {
            syncEditor();
            const steps = currentCapability().steps;
            const n = steps.length + 1;
            steps.push(normalizedStep({
                name: 'step-' + n, desc: '',
                on: {success: 'done', failed: 'failed'},
            }, n - 1));
            renderSteps();
        };
        $('#agent-add-parameter').onclick = () => withBusy(async () => {
            syncEditor(); const capability = currentCapability();
            capability.inputs ||= {type:'object',properties:{}};
            capability.inputs.properties ||= {};
            let index = 1; while (capability.inputs.properties['value_'+index]) index++;
            capability.inputs.properties['value_'+index] = {type:'string',title:tr('agent.mini.parameter_label')};
            renderParameters(); renderSteps();
        });
        $('#agent-save').onclick = () => withBusy(saveDraft);
        $('#agent-delete').onclick = () => withBusy(deleteDraft);
        $('#agent-preview').onclick = () => runAll(true);
        $('#agent-run-all').onclick = () => runAll(false);
        $('#agent-compile').onclick = compileAndActivate;
        $('#agent-run-pause').onclick = () => withBusy(async () => {
            renderRun(await api('/agent-draft-runs/' + encodeURIComponent(state.run.id) + '/pause',
                {method: 'POST', body: '{}'}));
            notice(tr('agent.mini.paused'), 'warning');
        });
        $('#agent-run-stop').onclick = () => withBusy(async () => {
            renderRun(await api('/agent-draft-runs/' + encodeURIComponent(state.run.id) + '/cancel',
                {method: 'POST', body: '{}'}));
            notice(tr('agent.mini.stopped'), 'warning');
        });
        $('#agent-run-continue').onclick = () => withBusy(async () => {
            if (state.run?.status === 'interrupted') {
                renderRun(await api('/agent-draft-runs/' + encodeURIComponent(state.run.id) + '/resume',
                    {method: 'POST', body: JSON.stringify({})}));
            }
            return driveRun();
        });
        $('#agent-send-chat').onclick = () => withBusy(async () => {
            if (!state.run) return;
            await api('/agent-draft-runs/' + encodeURIComponent(state.run.id) +
                '/chat-context', {method: 'POST', body: '{}'});
            notice(tr('agent.mini.sent_chat'), 'success');
        });
        $('#agent-save-knowledge').onclick = () => withBusy(async () => {
            if (!state.run) return;
            await api('/agent-draft-runs/' + encodeURIComponent(state.run.id) +
                '/knowledge', {method: 'POST', body: JSON.stringify({
                    bucket_id: $('#agent-knowledge-bucket').value || null,
                    title: (state.draft?.name || 'Agent') + ' result',
                })});
            notice(tr('agent.mini.saved_knowledge'), 'success');
        });
    }
    async function initialize({restoreCompleted = true} = {}) {
        if (!restoreCompleted) {
            state.presentations.clear();
            state.resultMode = 'json';
            renderRun(null);
        }
        notice(tr('agent.mini.connecting'));
        await state.client?.connection?.close();
        state.client = null;
        await api('/site-agents/reconcile', {method:'POST', body:'{}'}).catch(() => ({}));
        await refreshDrafts();
        await loadBuilderModels();
        try {
            const buckets = (await api('/knowledge/buckets')).items || [];
            $('#agent-knowledge-bucket').replaceChildren(
                new Option(tr('agent.mini.default_bucket'), ''),
                ...buckets.map(bucket => new Option(bucket.name, bucket.id)),
            );
        } catch (_) { /* The default Knowledge target remains usable. */ }
        let bidiReady = false;
        try {
            const bidi = await client();
            state.page = await bidi.pageState();
            bidiReady = true;
            notice('');
        } catch (error) {
            state.client = null;
            state.page = {
                title: state.context.title || tr('agent.mini.current_page'),
                url: state.context.url || '',
            };
            notice(error.message || String(error), 'warning');
        }
        const runs = await api('/agent-draft-runs?limit=10');
        const resumable = (runs.items || []).find(item =>
            ['queued', 'planning', 'running', 'waiting_input', 'interrupted'].includes(item.status));
        if (resumable) {
            renderRun(resumable);
            if (bidiReady && resumable.status !== 'interrupted') void driveRun();
        } else if (restoreCompleted && runs.items?.[0]) {
            renderRun(runs.items[0]);
        }
        const recipeId = new URL(location.href).searchParams.get('recipe_id');
        if (recipeId) {
            state.recipe = {id:recipeId};
            try { await loadRecipeReview(); $('#agent-recipe-confirm').hidden = false; }
            catch (error) { state.recipe = null; rememberRecipe(); notice(error.message, 'warning'); }
        }
    }
    function contextKey(context = state.context) {
        return `${String(context?.bidi_context || '')}\n${String(context?.url || '')}`;
    }
    function contextIsWebPage(context = state.context) {
        try { return ['http:', 'https:'].includes(new URL(String(context?.url || '')).protocol); }
        catch (_) { return false; }
    }
    async function applyBrowserContext(detail) {
        const previousKey = contextKey();
        state.context = {...state.context, ...(detail || {})};
        if (contextKey() === previousKey) return;
        const revision = ++state.contextRevision;
        const previousClient = state.client;
        state.client = null;
        state.page = null;
        await previousClient?.connection?.close().catch(() => {});
        if (revision !== state.contextRevision) return;
        if (!contextIsWebPage()) {
            state.page = {
                title: state.context.title || tr('agent.mini.current_page'),
                url: state.context.url || '',
            };
            notice('');
            return;
        }
        notice(tr('agent.mini.connecting'));
        try {
            await client();
            if (revision === state.contextRevision) notice('');
        } catch (error) {
            if (revision !== state.contextRevision) return;
            state.page = {
                title: state.context.title || tr('agent.mini.current_page'),
                url: state.context.url || '',
            };
            notice(error.message || String(error), 'warning');
        }
    }
    document.addEventListener('DOMContentLoaded', () => {
        bind();
        $('#agent-delete').textContent = tr('agent.mini.delete');
        if (window.lucide) window.lucide.createIcons();
        withBusy(() => initialize({restoreCompleted:new URL(location.href).searchParams.get('ai2apps_sidebar_refresh') !== '1'}));
    });
    window.addEventListener('ai2apps:browser-context', event => {
        void applyBrowserContext(event.detail || {});
    });
    window.addEventListener('pagehide', () => {
        setContextPinned(false);
        void state.client?.connection?.close();
    });
})();
