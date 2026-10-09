(() => {
    'use strict';
    const API = '/v1/platform';
    const state = {
        context: Object.fromEntries(new URLSearchParams(location.hash.slice(1))),
        page: null, drafts: [], draft: null, capabilityId: null, recipe: null,
        client: null, busy: false, run: null, contextRevision: 0, unloading: false,
        resultMode: 'json', presentations: new Map(), review: null, previousReview: null,
        exploration: null, contextPinned: false, executionContextPinned: false, editorContextPinned: false, pendingBrowserContext: null, attachments: [], compiledDraft: null, localTestVariables: null, localTestOutputs: {},
    };
    const $ = selector => document.querySelector(selector);
    const $$ = selector => [...document.querySelectorAll(selector)];
    const translationFallbacks = {
        en: {
            'agent.mini.step_name_prefix': 'Step-{number}: ',
            'agent.mini.compiled_stale': 'Last compiled result · recompile after editing',
            'agent.mini.not_compiled': 'No compiled result for this step',
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
            'agent.mini.step_chat': "AI conversation",
            'agent.mini.step_chat_help': "Describe changes to this step. Review and apply the proposal; saving and running remain separate.",
            'agent.mini.step_chat_placeholder': "For example: skip upload when the attachment list is empty.",
            'agent.mini.step_chat_send': "Send",
            'agent.mini.step_chat_apply': "Apply to this step",
            'agent.mini.step_chat_proposal': "Proposed step",
            'agent.mini.step_chat_you': "You",
            'agent.mini.step_chat_working': "Generating…",
            'agent.mini.step_chat_stale': "The editor changed. Generate a new proposal before applying.",
            'agent.mini.step_chat_applied': "Applied to the editor. Save or compile when ready.",
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
            'agent.mini.status_committed': 'Added to website Agent',
            'agent.mini.review_approving': 'Approving…',
            'agent.mini.status_failed': 'Failed',
        },
        zh: {
            'agent.mini.step_name_prefix': '步骤-{number}: ',
            'agent.mini.compiled_stale': '上次编译结果 · 修改后需重新编译',
            'agent.mini.not_compiled': '此步骤暂无编译结果',
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
            'agent.mini.step_chat': "AI 对话修改",
            'agent.mini.step_chat_help': "描述此步骤的修改要求，可继续对话调整。检查后应用到编辑器，再保存或编译。",
            'agent.mini.step_chat_placeholder': "例如：附件数组为空时跳过上传。",
            'agent.mini.step_chat_send': "发送",
            'agent.mini.step_chat_apply': "应用到此步骤",
            'agent.mini.step_chat_proposal': "修改后的步骤",
            'agent.mini.step_chat_you': "我",
            'agent.mini.step_chat_working': "正在生成…",
            'agent.mini.step_chat_stale': "编辑内容已经变化，请重新生成修改建议。",
            'agent.mini.step_chat_applied': "已应用到编辑器，请按需保存或编译。",
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
            'agent.mini.status_committed': '已加入网站智能体',
            'agent.mini.review_approving': '正在提交审核…',
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
        state.executionContextPinned = Boolean(pinned);
        const next = state.executionContextPinned || state.editorContextPinned;
        if (state.contextPinned === next) return;
        state.contextPinned = next;
        const fragment = new URLSearchParams(location.hash.slice(1));
        if (next) fragment.set('agent_context_lock', '1');
        else fragment.delete('agent_context_lock');
        const suffix = fragment.toString();
        history.replaceState(history.state, '',
            location.pathname + location.search + (suffix ? '#' + suffix : ''));
        if (!next && state.pendingBrowserContext) {
            const pending = state.pendingBrowserContext; state.pendingBrowserContext = null;
            void applyBrowserContext(pending);
        }
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
        if(options.method && options.method !== 'GET' && /^\/agent-(?:drafts|recipes)(?:\/|$)/.test(path))
            window.frameElement?.ai2appsWorkspaceChanged?.();
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
    function readVariableDefinitions() {
        const schema = {type:'object', properties:{}, additionalProperties:false};
        $$('#agent-variable-definitions .agent-variable-definition').forEach(row => {
            const name = row.querySelector('[data-variable=name]').value.trim();
            if (!/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(name) || name.startsWith('__') || schema.properties[name])
                throw new Error(tr('agent.mini.invalid_variable_name'));
            const type = row.querySelector('[data-variable=type]').value;
            const prop = {...row._schema, type,
                title:row.querySelector('[data-variable=title]').value.trim(),
                description:row.querySelector('[data-variable=description]').value.trim()};
            delete prop.default; delete prop.initial;
            const value = row.querySelector('[data-variable=initial]').value;
            if (row.querySelector('[data-variable=mode]').value === 'expression') prop.initial = value;
            else prop.default = type === 'string' ? value : JSON.parse(value);
            schema.properties[name] = prop;
        });
        return schema;
    }
    function renderVariables() {
        const host = $('#agent-variable-definitions'); host.replaceChildren();
        const schema = currentCapability()?.variables || {type:'object',properties:{}};
        Object.entries(schema.properties || {}).forEach(([name, prop]) => {
            const row = document.createElement('div'); row.className = 'agent-variable-definition agent-parameter-grid';
            row._schema = structuredClone(prop);
            const field = (key, label, value, tag='input') => {
                const wrap = document.createElement('label'); wrap.className = 'agent-field';
                const title = document.createElement('span'); title.textContent = label;
                const control = document.createElement(tag); control.dataset.variable = key;
                control.setAttribute('aria-label',label); control.value = value;
                wrap.append(title,control); row.append(wrap); return control;
            };
            field('name',tr('agent.mini.variable_name'),name);
            field('title',tr('agent.mini.parameter_label'),prop.title || '');
            const type = field('type',tr('agent.mini.parameter_type'),'','select');
            ['string','integer','number','boolean','array','object','null'].forEach(t=>type.add(new Option(t,t)));
            type.value = prop.type || 'string';
            field('description',tr('agent.mini.parameter_description'),prop.description || '');
            const mode = field('mode',tr('agent.mini.initial_value'),'','select');
            mode.add(new Option(tr('agent.mini.fixed_value'),'fixed'));
            mode.add(new Option(tr('agent.mini.expression'),'expression')); mode.value = prop.initial ? 'expression' : 'fixed';
            const initial = field('initial',tr('agent.mini.initial_value'),prop.initial ||
                (prop.type === 'string' ? (prop.default || '') : JSON.stringify(prop.default ??
                    ({integer:0,number:0,boolean:false,array:[],object:{},null:null}[prop.type]))));
            initial.placeholder = 'input.items / 0 / []';
            type.onchange = () => {
                if (mode.value === 'fixed') initial.value = type.value === 'string' ? '' :
                    JSON.stringify({integer:0,number:0,boolean:false,array:[],object:{},null:null}[type.value]);
            };
            const remove = document.createElement('button'); remove.type='button'; remove.textContent=tr('agent.mini.remove');
            remove.onclick = () => {row.remove(); syncEditor(); state.localTestVariables=null; state.localTestOutputs={}; renderSteps();};
            row.append(remove); host.append(row);
        });
    }
    function readLocalArguments(node, step) {
        if (step.operation === 'assign') return {assignments:[...node.querySelectorAll('[data-assignment-row]')].map(row=>({
            variable:row.querySelector('[data-assignment=variable]').value,
            expression:row.querySelector('[data-assignment=expression]').value.trim()}))};
        if (step.operation === 'condition') return {expression:node.querySelector('[data-field=expression]').value.trim()};
        const url = node.querySelector('[data-field=target-url]');
        return url ? {...step.arguments,url:url.value.trim()} : step.arguments || {};
    }
    function renderLocalArguments(node, step) {
        const panel = document.createElement('section'); panel.className='agent-local-arguments';
        const help = document.createElement('small'); help.textContent=tr('agent.mini.expression_help'); panel.append(help);
        if (step.operation === 'condition') {
            const input=document.createElement('input'); input.dataset.field='expression'; input.value=step.arguments?.expression || '';
            input.setAttribute('aria-label',tr('agent.mini.condition_expression')); input.placeholder='vars.index < len(input.items)'; panel.append(input);
        } else {
            const rows=document.createElement('div'); panel.append(rows);
            const addRow = value => {
                const row=document.createElement('div'); row.dataset.assignmentRow=''; row.className='agent-transition';
                const select=document.createElement('select'); select.dataset.assignment='variable';
                select.setAttribute('aria-label',tr('agent.mini.assignment_variable'));
                Object.entries(currentCapability()?.variables?.properties || {}).forEach(([key,prop])=>select.add(new Option(prop.title ? `${prop.title} (${key})` : key,key)));
                select.value=value.variable || select.options[0]?.value || '';
                const expression=document.createElement('input'); expression.dataset.assignment='expression'; expression.value=value.expression || '';
                expression.setAttribute('aria-label',tr('agent.mini.expression')); expression.placeholder='vars.index + 1';
                const remove=document.createElement('button'); remove.type='button'; remove.textContent='×'; remove.onclick=()=>{row.remove();syncEditor();};
                row.append(select,expression,remove); rows.append(row);
            };
            (step.arguments?.assignments?.length ? step.arguments.assignments : [{}]).forEach(addRow);
            const add=document.createElement('button'); add.type='button'; add.textContent=tr('agent.mini.add_assignment'); add.onclick=()=>addRow({}); panel.append(add);
        }
        node.append(panel);
    }
    function editorSource() {
        const source = cloneSource();
        source.name = $('#agent-name').value.trim() || 'New Site Agent';
        source.description = $('#agent-working-goal').value.trim();
        source.site_scope = $('#agent-scope').value.split(/[,\n]/).map(v => v.trim()).filter(Boolean);
        const capability = currentCapability();
        const inputs = readParameterDefinitions(capability?.inputs);
        const variables = readVariableDefinitions();
        const nextSteps = $$('.agent-step').map((node, index) => normalizedStep({
            ...(capability?.steps?.[index] || {}),
            name: node.querySelector('[data-field=name]').value.trim() || 'step-' + (index + 1),
            desc: node.querySelector('[data-field=desc]').value.trim(),
            target: node._target || {},
            arguments: readLocalArguments(node, capability?.steps?.[index] || {}),
            ...(node._callArguments ? {operation:'agent.call', arguments:node._callArguments} : {}),
            execution: {...(typeof capability?.steps?.[index]?.execution === 'object' ? capability.steps[index].execution : {}),
                mode: ['assign','condition'].includes(capability?.steps?.[index]?.operation) ? 'compiled' :
                    node.querySelector('[data-field=compile]').checked ? 'adaptive' : 'interpreted'},
            ...(node.querySelector('[data-field=tier]') ? {ai: {
                ...(capability?.steps?.[index]?.ai || {}),
                ...(node.querySelector('[data-field=ai-instruction]') ? {instruction:node.querySelector('[data-field=ai-instruction]').value,
                    output_schema:JSON.parse(node.querySelector('[data-field=ai-schema]').value)} : {}),
                tier: node.querySelector('[data-field=tier]').value,
            }} : {}),
            on: {
                ...(capability?.steps?.[index]?.on || {}),
                ...(capability?.steps?.[index]?.on?.true !== undefined
                    ? {true:node.querySelector('[data-field=success]').value.trim() || 'done'}
                    : {success:node.querySelector('[data-field=success]').value.trim() || 'done'}),
                ...(node.querySelector('[data-field=false]') ? {false:node.querySelector('[data-field=false]').value.trim() || 'failed'} : {}),
                failed: node.querySelector('[data-field=failed]').value.trim() || 'failed',
            },
        }, index));
        if (Array.isArray(source.capabilities)) {
            const selected = source.capabilities.find(item => item.id === (state.capabilityId || capability?.id));
            if (selected) {
                selected.title = $('#agent-capability-title')?.value.trim() || selected.title;
                selected.description = $('#agent-capability-description')?.value.trim() || '';
                selected.working_goal = $('#agent-capability-working-goal')?.value.trim() || '';
                selected.steps = nextSteps; selected.inputs = inputs; selected.variables = variables; }
        } else {
            const title = $('#agent-capability-title')?.value.trim();
            if (title) source.provenance = {...source.provenance, capability_metadata:{title,
                description:$('#agent-capability-description')?.value.trim() || ''}};
            source.working_goal = $('#agent-capability-working-goal')?.value.trim() || '';
            source.steps = nextSteps; source.inputs = inputs; source.variables = variables;
        }
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
        if (type === 'array') {
            const array = JSON.parse(value);
            if (!Array.isArray(array)) throw new Error(tr('agent.mini.invalid_parameter'));
            return array;
        }
        if (type === 'object') {
            const object = JSON.parse(value);
            if (!object || typeof object !== 'object' || Array.isArray(object)) throw new Error(tr('agent.mini.invalid_parameter'));
            return object;
        }
        return String(value);
    }
    function orderedParameters(schema = {}) {
        const properties = schema.properties || {};
        const keys = [...new Set([...(schema['x-ai2apps-order'] || []), ...Object.keys(properties)])];
        return keys.filter(key => Object.hasOwn(properties, key)).map(key => [key, properties[key]]);
    }
    function readParameterDefinitions(previous = {}) {
        const properties = {}, required = [];
        $$('#agent-parameter-definitions .agent-parameter').forEach(row => {
            const key = row.querySelector('[data-key]').value.trim();
            if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key) || ['__proto__','constructor','prototype'].includes(key) || Object.hasOwn(properties, key))
                throw new Error(tr('agent.mini.invalid_parameter'));
            const selectedType = row.querySelector('[data-type]').value;
            const type = selectedType === 'files' ? 'array' : selectedType === 'file' ? 'object' : selectedType;
            const property = {...previous.properties?.[key], type,
                title: row.querySelector('[data-label]').value.trim() || key,
                description: row.querySelector('[data-description]').value.trim()};
            if (['file','files'].includes(selectedType)) {
                property['x-ai2apps-file'] = true;
                if (selectedType === 'files') property.items = {type:'object', 'x-ai2apps-file':true};
            } else delete property['x-ai2apps-file'];
            delete property.default;
            const value = row.querySelector('[data-default]').value;
            if (value !== '') property.default = parameterValue(type, value);
            properties[key] = property;
            if (row.querySelector('[data-required]').checked) required.push(key);
        });
        return {...previous, type:'object', properties, required, 'x-ai2apps-order':Object.keys(properties)};
    }
    function renderInputFields(container, schema = {}) {
        container.replaceChildren();
        if (!Object.keys(schema.properties || {}).length) {
            const empty = document.createElement('p'); empty.textContent = tr('agent.mini.no_parameters');
            container.append(empty); return;
        }
        const title = document.createElement('strong'); title.textContent = tr('agent.mini.run_parameters');
        container.append(title);
        orderedParameters(schema).forEach(([key, property]) => {
            const label = document.createElement('label'); label.className = 'agent-field';
            const text = document.createElement('span'); text.textContent = (property.title || key) + (schema.required?.includes(key) ? ' *' : '');
            const input = document.createElement(property.type === 'boolean' || property.enum ? 'select' : 'input');
            input.dataset.parameter = key;
            if (property.type === 'boolean' || property.enum) {
                input.add(new Option('', ''));
                (property.enum || [true, false]).forEach(value => input.add(new Option(String(value), String(value))));
            } else input.type = ['integer','number'].includes(property.type) ? 'number' : 'text';
            input.value = property.default == null ? '' : ['object','array'].includes(property.type) ? JSON.stringify(property.default) : String(property.default);
            if (property['x-ai2apps-file']) {
                const multiple = property.type === 'array';
                input.type = 'hidden';
                let files = multiple ? [...(property.default || [])] : property.default ? [property.default] : [];
                const cards = document.createElement('div'); cards.className = 'agent-attachments';
                const update = () => {
                    input.value = files.length ? JSON.stringify(multiple ? files : files[0]) : multiple ? '[]' : '';
                    cards.replaceChildren();
                    files.forEach((file, index) => {
                        const card = document.createElement('div'); card.className = 'agent-attachment-card';
                        const preview = document.createElement('div'); preview.className = 'agent-attachment-preview';
                        if (/^(image|video)\//.test(file.media_type || '')) {
                            const media = document.createElement(file.media_type.startsWith('video/') ? 'video' : 'img');
                            media.src = file.url; media.alt = file.name || tr('agent.mini.type_file');
                            if (media.tagName === 'VIDEO') {media.muted = true; media.preload = 'metadata';}
                            preview.append(media);
                        } else preview.textContent = '📄';
                        const name = document.createElement('span'); name.className = 'agent-attachment-name';
                        name.textContent = file.name || file.url || tr('agent.mini.type_file'); name.title = name.textContent;
                        const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×';
                        remove.className = 'agent-attachment-remove'; remove.setAttribute('aria-label',tr('agent.mini.remove_named_attachment', {name:name.textContent}));
                        remove.onclick = () => {files.splice(index,1); update();};
                        card.append(preview,name,remove); cards.append(card);
                    });
                };
                const add = added => { files = multiple ? [...files,...added].filter((file,index,all) =>
                    all.findIndex(other => (other.asset_id || other.url) === (file.asset_id || file.url)) === index) : added.slice(0,1); update(); };
                const picker = document.createElement('input'); picker.type = 'file'; picker.multiple = multiple; picker.hidden = true;
                picker.onchange = () => withBusy(async () => {add(await Promise.all([...picker.files].map(uploadAgentFile))); picker.value = '';});
                const choose = document.createElement('button'); choose.type = 'button'; choose.textContent = tr('agent.mini.add_attachment');
                choose.onclick = () => picker.click();
                const gallery = document.createElement('button'); gallery.type = 'button'; gallery.textContent = tr('agent.mini.choose_gallery');
                gallery.onclick = async () => {
                    const assets = await window.AI2AppsGalleryPicker.open({multiple});
                    if (assets.length) await withBusy(async () => add(await Promise.all(assets.map(async asset =>
                        fileReference(await api('/gallery/assets/'+encodeURIComponent(asset.id)))))));
                };
                const url = document.createElement('input'); url.type = 'url'; url.placeholder = tr('agent.mini.file_url');
                const addUrl = document.createElement('button'); addUrl.type = 'button'; addUrl.textContent = tr('agent.mini.add_link');
                addUrl.onclick = () => withBusy(async () => {const parsed = new URL(url.value);
                    if (!['http:','https:'].includes(parsed.protocol)) throw new Error(tr('agent.mini.invalid_parameter'));
                    add([{url:parsed.href,name:parsed.pathname.split('/').pop() || tr('agent.mini.type_file')}]); url.value = '';});
                label.append(cards,picker,choose,gallery,url,addUrl); update();
            } else if (property.type === 'array') {
                input.type = 'hidden';
                let values = [...(property.default || [])];
                const rows = document.createElement('div');
                const update = () => {
                    input.value = JSON.stringify(values); rows.replaceChildren();
                    values.forEach((value,index) => {
                        const row = document.createElement('div'); row.className = 'agent-array-row';
                        const field = document.createElement('input'); field.value = typeof value === 'object' ? JSON.stringify(value) : String(value);
                        field.setAttribute('aria-label',(property.title || key)+' '+(index+1));
                        field.onchange = () => {values[index] = parameterValue(property.items?.type || 'string',field.value); input.value = JSON.stringify(values);};
                        const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = '×';
                        remove.onclick = () => {values.splice(index,1); update();}; row.append(field,remove); rows.append(row);
                    });
                };
                const add = document.createElement('button'); add.type = 'button'; add.textContent = tr('agent.mini.add_item');
                add.onclick = () => {values.push(property.items?.type === 'object' ? {} : property.items?.type === 'boolean' ? false : ['number','integer'].includes(property.items?.type) ? 0 : ''); update();};
                label.append(rows,add); update();
            }
            const details = document.createElement('small');
            details.textContent = key + ' · ' + (property['x-ai2apps-file'] ? property.type === 'array' ? tr('agent.mini.type_files') : tr('agent.mini.type_file') : property.type || 'string') + (property.description ? ' · '+property.description : '');
            label.prepend(text,details); label.append(input); container.append(label);

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
        orderedParameters(schema).forEach(([key, property]) => {
            const row = document.createElement('div'); row.className = 'agent-parameter';
            row.dataset.originalKey = key;
            row.innerHTML = '<input data-key><input data-label><input data-description ><select data-type></select><input data-default><label><input data-required type="checkbox"><span></span></label><button type="button">×</button>';
            [['data-key',key,'parameter_name'],['data-label',property.title || key,'parameter_label'],['data-default',property.default == null ? '' : typeof property.default === 'object' ? JSON.stringify(property.default) : String(property.default),'parameter_default']].forEach(([attr,value,label]) => {
                const input = row.querySelector('['+attr+']'); input.value = value; input.placeholder = tr('agent.mini.'+label); input.setAttribute('aria-label', input.placeholder);
            });
            row.querySelector('[data-description]').value = property.description || '';
            row.querySelector('[data-description]').placeholder = tr('agent.mini.parameter_description');
            row.querySelector('[data-description]').placeholder = tr('agent.mini.parameter_description');
            const type = row.querySelector('[data-type]');
            ['string','integer','number','boolean','object','array','file','files'].forEach(value => type.add(new Option(tr('agent.mini.type_'+value), value)));
            type.value = property['x-ai2apps-file'] ? property.type === 'array' ? 'files' : 'file' : property.type || 'string';
            row.querySelector('[data-required]').checked = schema.required?.includes(key) || false;
            row.querySelector('span').textContent = tr('agent.mini.parameter_required_label');
            // Persistent labels remain visible after values replace placeholders.
            [['data-key',tr('agent.mini.parameter_name')],['data-label',tr('agent.mini.parameter_label')],
                ['data-description',tr('agent.mini.parameter_description')],['data-type',tr('agent.mini.parameter_type')],['data-default',tr('agent.mini.parameter_default')]].forEach(([attr,title]) => {
                const input = row.querySelector('['+attr+']');
                const label = document.createElement('label'); label.className = 'agent-parameter-field';
                const caption = document.createElement('span'); caption.textContent = title;
                input.setAttribute('aria-label',title);
                input.before(label); label.append(caption,input);
            });
            const removeParameter = row.querySelector('button');
            removeParameter.setAttribute('aria-label',tr('agent.mini.parameter_delete'));
            removeParameter.title = tr('agent.mini.parameter_delete');
            const actions = document.createElement('div'); actions.className = 'agent-parameter-actions';
            removeParameter.before(actions);
            for (const [direction, symbol, label] of [[-1,'↑','move_up'],[1,'↓','move_down']]) {
                const move = document.createElement('button'); move.type = 'button'; move.textContent = symbol;
                move.title = tr('agent.mini.'+label); move.setAttribute('aria-label',move.title);
                const index = orderedParameters(schema).findIndex(([name]) => name === key);
                move.disabled = direction < 0 ? index === 0 : index === orderedParameters(schema).length-1;
                move.onclick = () => withBusy(async () => {
                    const sibling = direction < 0 ? row.previousElementSibling : row.nextElementSibling;
                    if (!sibling) return;
                    if (direction < 0) sibling.before(row); else sibling.after(row);
                    syncEditor(); renderParameters(); renderSteps();
                });
                actions.append(move);
            }
            actions.append(removeParameter);
            let parameterErrorTimer = null;
            const dismissParameterError = () => {
                if (parameterErrorTimer !== null) window.clearTimeout(parameterErrorTimer);
                parameterErrorTimer = null;
                row.querySelector('.agent-parameter-error')?.remove();
            };
            removeParameter.onclick = () => withBusy(async () => {
                syncEditor();
                const name = row.querySelector('[data-key]').value.trim();
                const title = row.querySelector('[data-label]').value.trim();
                const capability = currentCapability();
                dismissParameterError();
                const usesParameter = value => {
                    const references = JSON.stringify(value) || '';
                    return ['}', '.', '['].some(suffix => references.includes('${input.'+name+suffix));
                };
                const bindings = (capability.steps || []).filter(usesParameter).map(step => step.name || step.id || step.desc);
                if (usesParameter(capability.variables)) bindings.push(tr('agent.mini.variables'));
                if (bindings.length) {
                    const message = document.createElement('div');
                    message.className = 'agent-parameter-error';
                    message.setAttribute('role','alert');
                    const text = document.createElement('span');
                    text.textContent = tr('agent.mini.parameter_in_use') + ' ' + bindings.join('、');
                    const close = document.createElement('button');
                    close.type = 'button';
                    close.textContent = '×';
                    close.setAttribute('aria-label', tr('agent.mini.close'));
                    close.onclick = dismissParameterError;
                    message.append(text, close);
                    row.append(message);
                    parameterErrorTimer = window.setTimeout(dismissParameterError, 12000);
                    message.scrollIntoView({block:'nearest'});
                    return;
                }
                if (!window.confirm(tr('agent.mini.parameter_delete_confirm', {name:title && title !== name ? title+' ('+name+')' : name}))) return;
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
        refreshEditorCompilation();
        if (state.recipe && state.recipeEditorId === state.recipe.id &&
            recipeSourceSignature(state.draft.source) !== (state.recipeEditorBaseline || recipeSourceSignature(state.review?.source))) {
            $('#agent-review-status').textContent = tr('agent.mini.review_required');
            $('#agent-review-status').dataset.status = 'awaiting_review';
            $('#agent-review-commit').hidden = true;
            $('#agent-review-approve').disabled = false;
        }
    }
    function editorCompiledStep(generation, capabilityId, name) {
        if (!generation?.ir || generation.status === 'failed') return null;
        const capabilities = generation.ir.capabilities;
        const ir = Array.isArray(capabilities) && capabilities.length
            ? capabilities.find(item => item.id === capabilityId || item.name === capabilityId)
            : generation.ir;
        return ir?.steps?.find(item => item.id === name) || null;
    }
    async function loadEditorCompilation() {
        const draft = state.draft;
        state.compiledDraft = null;
        if (!draft?.id) return;
        const generations = await api('/agent-drafts/' + encodeURIComponent(draft.id) + '/generations');
        if (state.draft?.id !== draft.id) return;
        let generation = generations.find(item => item.id === draft.active_generation_id) ||
            generations.find(item => item.source_revision === draft.revision && item.status !== 'failed');
        // Older saved Agents may contain Source only (Recipe commit did not create a generation).
        // Compile the persisted revision for inspection, without activation or browser execution.
        if (!generation && savedForMenu(draft)) {
            generation = await api('/agent-drafts/' + encodeURIComponent(draft.id) + '/compile',
                {method:'POST', body:'{}'});
            if (state.draft?.id !== draft.id) return;
            if (generation.status === 'failed') {
                notice(tr('agent.mini.compile_failed', {error:(generation.report?.errors || [])
                    .map(item => item.code).join(', ')}), 'warning');
                generation = null;
            }
        }
        state.compiledDraft = generation ? {draftId:draft.id, generation,
            source:structuredClone(draft.source)} : null;
    }
    function refreshEditorCompilation() {
        const saved = state.compiledDraft;
        let edited = false;
        try {
            edited = Boolean(saved?.source && JSON.stringify(editorSource()) !== saved.editorSource);
        } catch (_) { edited = true; }
        const stale = edited || saved?.generation.source_revision !== state.draft?.revision;
        $$('#agent-steps [data-compiled-status]').forEach(label => {
            label.textContent = tr(stale ? 'agent.mini.compiled_stale' : 'agent.mini.after_compile');
        });
    }
    const stepConversations = new Map();
    function renderStepConversation(node, index, step) {
        const key = JSON.stringify([state.draft?.id, state.capabilityId, step.name]);
        if (!stepConversations.has(key)) stepConversations.set(key, {messages:[], prompt:'', proposal:null});
        const chat = stepConversations.get(key);
        const panel = document.createElement('details'); panel.className = 'agent-step-chat';
        const summary = document.createElement('summary'); summary.textContent = tr('agent.mini.step_chat');
        const help = document.createElement('small'); help.textContent = tr('agent.mini.step_chat_help');
        const history = document.createElement('div'); history.className = 'agent-step-chat-history';
        history.setAttribute('role','log'); history.setAttribute('aria-live','polite');
        const prompt = document.createElement('textarea'); prompt.rows = 3;
        prompt.placeholder = tr('agent.mini.step_chat_placeholder'); prompt.maxLength=8000; prompt.value = chat.prompt;
        prompt.setAttribute('aria-label',tr('agent.mini.step_chat_placeholder'));
        prompt.oninput = () => {chat.prompt=prompt.value;};
        const model = tierSelect(chat.tier || 'standard');
        model.setAttribute('aria-label',tr('agent.mini.builder_model')); model.onchange = () => {chat.tier=model.value;};
        const send = document.createElement('button'); send.type='button'; send.textContent=tr('agent.mini.step_chat_send');
        const apply = document.createElement('button'); apply.type='button'; apply.textContent=tr('agent.mini.step_chat_apply');
        const preview = document.createElement('details');
        const previewTitle=document.createElement('summary'); previewTitle.textContent=tr('agent.mini.step_chat_proposal');
        const content=document.createElement('pre'); preview.append(previewTitle,content);
        const paint = () => {
            history.replaceChildren();
            chat.messages.forEach(message => {
                const entry=document.createElement('p');
                const who=document.createElement('strong'); who.textContent=message.role==='user' ? tr('agent.mini.step_chat_you') : 'AI';
                const text=document.createElement('span'); text.textContent=message.display || message.content;
                entry.append(who,text); history.append(entry);
            });
            apply.hidden=preview.hidden=!chat.proposal;
            content.textContent=chat.proposal ? JSON.stringify(chat.proposal.step,null,2) : '';
        };
        send.onclick = () => withBusy(async () => {
            const feedback=prompt.value.trim(); if (!feedback) return;
            syncEditor();
            const source=structuredClone(state.draft.source);
            const base=JSON.stringify(source), draftId=state.draft.id, capabilityId=state.capabilityId;
            const messages=chat.messages.slice(-10).map(({role,content})=>({role,content:content.slice(0,16000)}));
            chat.messages.push({role:'user',content:feedback}); chat.proposal=null; paint();
            send.disabled=true; send.textContent=tr('agent.mini.step_chat_working');
            try {
                const response=await api('/agent-steps/revisions',{method:'POST',body:JSON.stringify({
                    source,capability_id:capabilityId,step_index:index,feedback,messages,model_tier:model.value})});
                chat.messages.push({role:'assistant',content:JSON.stringify({step:response.step,message:response.message}),display:response.message});
                chat.proposal={step:response.step,base,draftId,capabilityId};
                if (prompt.value.trim()===feedback) {chat.prompt=''; prompt.value='';}
            } catch(error) {
                // Keep the user's text for retry; errors are not fed back as AI instructions.
                chat.messages.pop(); throw error;
            } finally {send.disabled=false; send.textContent=tr('agent.mini.step_chat_send');paint();}
        });
        apply.onclick = () => withBusy(async () => {
            syncEditor(); const proposal=chat.proposal;
            if (!proposal || state.draft?.id!==proposal.draftId || state.capabilityId!==proposal.capabilityId ||
                JSON.stringify(state.draft.source)!==proposal.base) throw new Error(tr('agent.mini.step_chat_stale'));
            currentCapability().steps[index]=structuredClone(proposal.step);
            chat.proposal=null; state.localTestVariables=null;state.localTestOutputs={};
            renderSteps();
            $('#agent-steps').children[index].open=true;
            notice(tr('agent.mini.step_chat_applied'),'success');
        });
        panel.append(summary,help,history,prompt,model,send,preview,apply); node.append(panel); paint();
    }

    function refreshStepTransitions() {
        const nodes = [...$('#agent-steps').children].filter(node => node.matches('.agent-step'));
        const destinations = nodes.map((node,index) => ({name:node.querySelector('[data-field=name]').value.trim() || 'step-'+(index+1),index}));
        nodes.forEach(node => node.querySelectorAll('select[data-field=success],select[data-field=failed],select[data-field=false]').forEach(select => {
            const value = select.value || select.dataset.destination;
            select.replaceChildren(new Option(tr('agent.mini.transition_done'),'done'),new Option(tr('agent.mini.transition_failed'),'failed'));
            destinations.forEach(({name,index}) => {if (!['done','failed'].includes(name)) select.add(new Option('Step '+(index+1)+' · '+name,name));});
            if (value && ![...select.options].some(option => option.value === value)) {
                const missing = new Option(tr('agent.mini.transition_missing', {name:value}),value); missing.disabled = true; select.add(missing);
            }
            select.value = value;
        }));
    }
    function renderSteps() {
        const list = $('#agent-steps');
        const expanded = new Set([...list.querySelectorAll('.agent-step[open]')].map(node => node.querySelector('[data-field=name]')?.value));
        list.replaceChildren();
        const steps = currentCapability()?.steps || [];
        steps.forEach((raw, index) => {
            const step = normalizedStep(raw, index);
            const node = document.createElement('details');
            node.className = 'agent-step';
            node.open = expanded.has(step.name);
            node._target = step.target;
            const condition = ['ai.classify','condition'].includes(step.operation) || step.on.false !== undefined;
            const local = ['assign','condition'].includes(step.operation);
            node.innerHTML =
                `<div class="agent-step-head"><strong></strong><span></span><button data-action="up" title="${tr('agent.mini.move_up')}">↑</button><button data-action="down" title="${tr('agent.mini.move_down')}">↓</button><button data-action="remove" title="${tr('agent.mini.remove')}">×</button></div>` +
                `<input data-field="name" aria-label="${tr('agent.mini.step_name')}">` +
                `<textarea data-field="desc" rows="3" aria-label="${tr('agent.mini.step_description')}" placeholder="${tr('agent.mini.step_placeholder')}"></textarea>` +
                `<div class="agent-transition"><label>${tr(condition ? 'agent.mini.branch_true' : 'agent.mini.success')} → <select data-field="success"></select></label><label>${tr('agent.mini.failure')} → <select data-field="failed"></select></label></div>` +
                `<div class="agent-step-actions"><button data-action="pick">${tr('agent.mini.pick')}</button><button data-action="preview">${tr('agent.mini.preview')}</button><button data-action="run">${tr('agent.mini.run_step')}</button></div>`;
            node.querySelector('.agent-step-head strong').textContent = 'Step ' + (index + 1);
            node.querySelector('.agent-step-head span').textContent =
                step.ai?.tier ? `AI · ${step.ai.tier}` :
                    (step.target?.accessible_name || step.target?.intent || '');
            node.querySelector('[data-field=name]').value = step.name;
            node.querySelector('[data-field=desc]').value = step.desc;
            node.querySelector('[data-field=success]').dataset.destination = step.on.true || step.on.success || 'done';
            if (condition) {
                const transition = document.createElement('label');
                const title = document.createElement('span'); title.textContent = tr('agent.mini.branch_false') + ' → ';
                const input = document.createElement('select'); input.dataset.field = 'false';
                input.setAttribute('aria-label',tr('agent.mini.branch_false')); input.dataset.destination = step.on.false || 'failed';
                transition.append(title,input);
                const transitions = node.querySelector('.agent-transition');
                transitions.insertBefore(transition, transitions.lastElementChild);
            }
            node.querySelector('[data-field=failed]').dataset.destination = step.on.failed || 'failed';
            const summary = document.createElement('summary'); summary.className = 'agent-step-summary';
            const summaryName = document.createElement('strong');
            const summaryDescription = document.createElement('span');
            const updateSummary = () => {
                summaryName.textContent = tr('agent.mini.step_name_prefix', {number: index + 1}) + node.querySelector('[data-field=name]').value.trim();
                summaryDescription.textContent = node.querySelector('[data-field=desc]').value.trim();
            };
            summary.append(summaryName, summaryDescription); node.prepend(summary);
            node.querySelector('[data-field=name]').addEventListener('input', () => {updateSummary(); refreshStepTransitions();});
            node.querySelector('[data-field=desc]').addEventListener('input', updateSummary);
            updateSummary();
            const typeLabel=document.createElement('label'); typeLabel.className='agent-field';
            const typeTitle=document.createElement('span'); typeTitle.textContent=tr('agent.mini.step_type');
            const stepType=document.createElement('select'); stepType.setAttribute('aria-label',tr('agent.mini.step_type'));
            [['', 'browser_auto'],['open','open'],['inspect','inspect'],['input','input'],['click','click'],['hover','hover'],
                ['scroll','scroll'],['read_page','read_page'],['extract_list','extract_list'],['read_results','read_results'],['page_access','page_access'],
                ['ai.classify','ai_condition'],['ai.extract','ai_extract'],['ai.transform','ai_transform'],
                ['assign','assign'],['condition','condition'],['agent.call','call'],['approval','approval'],['delete','delete'],['complete','complete']]
                .forEach(([value,key])=>stepType.add(new Option(tr('agent.mini.step_type_'+key),value)));
            stepType.value=step.operation || ''; typeLabel.append(typeTitle,stepType); node.insertBefore(typeLabel,node.querySelector('[data-field=name]'));
            stepType.onchange=()=>withBusy(async()=>{
                syncEditor(); const target=currentCapability().steps[index]; const previous=target.operation; const next=stepType.value;
                if (next) target.operation=next; else delete target.operation;
                if (['assign','condition','agent.call'].includes(next) || ['assign','condition','agent.call'].includes(previous)) target.arguments={};
                if (next==='assign') target.arguments={assignments:[{variable:Object.keys(currentCapability().variables?.properties || {})[0] || '',expression:'0'}]};
                if (next==='condition') target.arguments={expression:'true'};
                if (['condition','ai.classify'].includes(next)) {target.on.true=target.on.true || target.on.success || 'done'; target.on.false ||= 'failed'; delete target.on.success;}
                else {target.on.success=target.on.success || target.on.true || 'done';delete target.on.true;delete target.on.false;}
                if (next.startsWith('ai.')) target.ai={tier:target.ai?.tier || 'standard',instruction:target.desc || 'Describe the condition or transformation',
                    output_schema:next==='ai.classify' ? {type:'object',properties:{outcome:{type:'string',enum:['true','false','failed']}},required:['outcome']} : {type:'object'}};
                else delete target.ai;
                if (next==='agent.call') target.arguments={agent_id:'',capability:'',parameters:{}};
                renderSteps();
            });
            if (['open','read_page'].includes(step.operation)) {
                const url = document.createElement('input'); url.dataset.field = 'target-url';
                url.setAttribute('aria-label',tr('agent.mini.url_label'));
                url.placeholder = tr('agent.mini.url_placeholder'); url.value = step.arguments?.url || '';
                url.onchange = () => syncEditor(); node.append(url);
            }
            if (local) renderLocalArguments(node,step);
            if (step.operation === 'agent.call') {
                node._callArguments = structuredClone(step.arguments);
                const select = document.createElement('select');
                select.setAttribute('aria-label', tr('agent.mini.call_capability'));
                select.add(new Option(step.arguments.capability || tr('agent.mini.choose_capability'), 'current'));
                const params = document.createElement('textarea'); params.rows = 3;
                params.setAttribute('aria-label', tr('agent.mini.parameter_mapping'));
                params.value = JSON.stringify(step.arguments.parameters || {}, null, 2);
                const help = document.createElement('small');
                help.textContent = tr('agent.mini.mapping_help');
                params.onchange = () => withBusy(async () => {
                    const value = JSON.parse(params.value);
                    if (!value || Array.isArray(value) || typeof value !== 'object') throw new Error(tr('agent.mini.mapping_invalid'));
                    node._callArguments.parameters = value; syncEditor();
                });
                node.append(select, params, help);
                void api('/agent-capabilities?url=' + encodeURIComponent(state.page?.url || state.context.url || ''))
                    .then(response => {
                        const available = response.items || [];
                        available.forEach((item, i) => select.add(new Option(item.description || item.name, String(i))));
                        select.onchange = () => {
                            const item = available[Number(select.value)];
                            if (!item) return;
                            node._callArguments = {agent_id:item.agent_id, capability:item.name,
                                generation_id:item.generation_id, parameters:{}};
                            params.value = '{}'; help.textContent = JSON.stringify(item.input_schema || {}, null, 2);
                            syncEditor();
                        };
                    }).catch(error => notice(error.message, 'warning'));
            }
            {
                const compileLabel = document.createElement('label'); compileLabel.className = 'agent-field agent-checkbox-field';
                const compile = document.createElement('input'); compile.type = 'checkbox'; compile.dataset.field = 'compile';
                compile.checked = (typeof step.execution === 'string' ? step.execution : step.execution?.mode) !== 'interpreted';
                compile.disabled = local; if (local) compile.checked=true;
                compile.onchange = () => syncEditor();
                compileLabel.append(compile, document.createTextNode(tr('agent.mini.compile_step')));
                const help = document.createElement('small'); help.textContent = tr(local ? 'agent.mini.local_step_help' : 'agent.mini.compile_step_help');
                node.append(compileLabel, help);
                const label = document.createElement('label'); label.className = 'agent-field';
                const title = document.createElement('span'); title.textContent = tr('agent.mini.step_model');
                const select = tierSelect(step.ai?.tier || 'standard'); select.dataset.field = 'tier';
                select.onchange = () => syncEditor();
                label.append(title, select); if (!local) node.append(label);
                if (step.operation?.startsWith('ai.')) {
                    const instruction=document.createElement('textarea'); instruction.rows=3; instruction.dataset.field='ai-instruction';
                    instruction.setAttribute('aria-label',tr('agent.mini.ai_instruction')); instruction.value=step.ai?.instruction || step.desc;
                    const schema=document.createElement('textarea'); schema.rows=3; schema.dataset.field='ai-schema';
                    schema.setAttribute('aria-label',tr('agent.mini.ai_schema')); schema.value=JSON.stringify(step.ai?.output_schema || {type:'object'},null,2);
                    node.append(instruction,schema);
                }
            }
            if (!local && (!step.operation || step.operation === 'input' || step.arguments?.value !== undefined)) {
                const binding = document.createElement('select');
                binding.setAttribute('aria-label', tr('agent.mini.bind_parameter'));
                binding.add(new Option(tr('agent.mini.fixed_value'), ''));
                Object.entries(currentCapability()?.inputs?.properties || {}).forEach(([key, property]) =>
                    binding.add(new Option(property.title || key, key)));
                Object.entries(currentCapability()?.variables?.properties || {}).forEach(([key, property]) =>
                    binding.add(new Option(tr('agent.mini.variables')+' · '+(property.title || key), 'vars:'+key)));
                const bound = /^\$\{(input|vars)\.([A-Za-z_][A-Za-z0-9_]*)\}$/.exec(String(step.arguments?.value || ''));
                binding.value = bound ? (bound[1] === 'vars' ? 'vars:' : '')+bound[2] : '';
                const fixed = document.createElement('input'); fixed.value = binding.value ? '' : String(step.arguments?.value || '');
                fixed.placeholder = tr('agent.mini.fixed_value'); fixed.setAttribute('aria-label',tr('agent.mini.fixed_value')); fixed.hidden = Boolean(binding.value);
                const update = () => {syncEditor(); const target = currentCapability().steps[index];
                    target.arguments.value = binding.value ? (binding.value.startsWith('vars:') ? '${vars.'+binding.value.slice(5)+'}' : '${input.'+binding.value+'}') : fixed.value;
                    fixed.hidden = Boolean(binding.value);
                    if (fixed.parentElement?.matches('label.agent-field')) fixed.parentElement.hidden = fixed.hidden;};
                binding.onchange = update; fixed.onchange = update;
                node.append(binding, fixed);
            }
            node.querySelector('[data-action=remove]').onclick = () => {
                syncEditor();
                currentCapability().steps.splice(index, 1);
                renderSteps();
            };
            node.querySelector('[data-action=up]').disabled = index === 0;
            node.querySelector('[data-action=down]').disabled = index === steps.length - 1;
            node.querySelector('[data-action=up]').onclick = () => moveStep(index, -1);
            node.querySelector('[data-action=down]').onclick = () => moveStep(index, 1);
            node.querySelector('[data-action=pick]').hidden = local;
            node.querySelector('[data-action=pick]').onclick = () => pickTarget(index);
            node.querySelector('[data-action=preview]').onclick = () => checkSteps(index);
            node.querySelector('[data-action=run]').onclick = () => runEditorStep(index, false);
            const saved = state.compiledDraft;
            const compiled = saved?.draftId === state.draft?.id
                ? editorCompiledStep(saved.generation, state.capabilityId, step.name) : null;
            const section = document.createElement(compiled ? 'details' : 'section');
            section.className = 'agent-step-compilation';
            const label = document.createElement(compiled ? 'summary' : 'strong');
            if (compiled) {
                label.dataset.compiledStatus = '';
                label.textContent = tr('agent.mini.after_compile');
                const pre = document.createElement('pre');
                pre.textContent = JSON.stringify(compiled, null, 2);
                section.append(label, pre);
            } else {
                label.textContent = tr('agent.mini.not_compiled'); section.append(label);
            }
            node.append(section);
            renderStepConversation(node,index,step);
            // Visible labels keep field meanings clear even after a value is entered.
            node.querySelectorAll('input[aria-label],textarea[aria-label],select[aria-label]').forEach(input => {
                if (input.closest('label')) return;
                const field = document.createElement('label'); field.className = 'agent-field';
                const caption = document.createElement('span'); caption.textContent = input.getAttribute('aria-label');
                field.hidden = input.hidden;
                input.before(field); field.append(caption,input);
            });
            const identity = document.createElement('div'); identity.className = 'agent-step-identity';
            const nameLabel = node.querySelector('[data-field=name]').closest('label');
            typeLabel.before(identity); identity.append(typeLabel,nameLabel);
            list.append(node);
        });
        if (!steps.length) list.innerHTML = `<p class="agent-empty">${tr('agent.mini.empty_steps')}</p>`;
        refreshStepTransitions();
        list.querySelectorAll('select[data-field=success],select[data-field=failed],select[data-field=false]').forEach(select => {
            select.onchange = () => {select.dataset.destination = select.value; syncEditor();};
        });
        refreshEditorCompilation();
    }
    function ensureCapabilitySource() {
        const source=state.draft.source;
        if(Array.isArray(source.capabilities))return;
        const metadata=source.provenance?.capability_metadata || {};
        const cap={id:'main',name:'site.main',title:metadata.title || source.name,
            description:metadata.description || source.description || '',working_goal:source.working_goal || ''};
        delete source.working_goal;
        for(const key of ['inputs','outputs','variables','steps','fixtures','validators']) {
            if(source[key]!==undefined){cap[key]=source[key];delete source[key];}
        }
        source.schema='ai2apps.site-agent-source/v1';source.capabilities=[cap];state.capabilityId=cap.id;
    }
    function renderCapabilityDetails() {
        if($('#agent-new-capability-panel').open)$('#agent-new-capability-panel').close();
        const cap = currentCapability();
        const metadata = cap?.provenance?.capability_metadata;
        $('#agent-capability-title').value = metadata?.title || cap?.title || cap?.name || '';
        $('#agent-capability-description').value = metadata?.description || cap?.description || '';
        $('#agent-capability-working-goal').value = cap?.working_goal || '';
        $('#agent-capability-details').hidden = Array.isArray(state.draft.source.capabilities) && !capabilities().length;
        $('#agent-delete-capability').hidden = Array.isArray(state.draft.source.capabilities) && !capabilities().length;
    }
    async function loadCapabilityTemplates() {
        if (state.capabilityTemplates) return;
        const response = await api('/agent-capabilities');
        state.capabilityTemplates = (response.items || []).filter(item=>item.builtin);
        const select = $('#agent-capability-template');
        state.capabilityTemplates.forEach((item,index)=>select.add(new Option(item.title || item.name,String(index))));
    }
    function renderDraft() {
        if (!state.draft) return;
        $('#agent-name').value = state.draft.name;
        $('#agent-working-goal').value = state.draft.source?.description || state.draft.description || '';
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
        renderCapabilityDetails();
        void loadCapabilityTemplates().catch(error=>notice(error.message,'warning'));
        renderParameters();
        renderVariables();
        state.localTestVariables=null; state.localTestOutputs={};
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
        if (mode === 'build') document.documentElement.classList.remove('agent-workspace-create');
        state.editorContextPinned = mode === 'build';
        setContextPinned(state.executionContextPinned);
        $('#agent-run-panel').hidden = false;
        $('#agent-build-panel').hidden = mode !== 'build';
        updateRunHandoff();
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
            const row = document.createElement('div'); row.className = 'agent-attachment-card';
            row.tabIndex = 0;
            const preview = document.createElement('div'); preview.className = 'agent-attachment-preview';
            const type = attachment.media_type || '';
            if (type.startsWith('image/') || type.startsWith('video/')) {
                const media = document.createElement(type.startsWith('image/') ? 'img' : 'video');
                media.src = attachment.url;
                if (media.tagName === 'IMG') { media.alt = ''; media.loading = 'lazy'; }
                else { media.muted = true; media.preload = 'metadata'; media.playsInline = true; }
                preview.append(media);
                if (type.startsWith('video/')) {
                    const badge = document.createElement('span'); badge.className = 'agent-attachment-badge';
                    badge.textContent = '▶'; badge.setAttribute('aria-hidden','true'); preview.append(badge);
                }
            } else {
                const icon = document.createElement('i');
                icon.setAttribute('data-lucide',type.startsWith('audio/') ? 'audio-lines' : 'file-text');
                preview.append(icon);
            }
            const name = document.createElement('span'); name.className = 'agent-attachment-name'; name.textContent = attachment.name;
            const tip = document.createElement('span'); tip.className = 'agent-attachment-tooltip'; tip.textContent = attachment.name;
            tip.id = 'agent-attachment-tip-' + index; tip.setAttribute('role','tooltip');
            row.setAttribute('aria-describedby',tip.id);
            const remove = document.createElement('button'); remove.className = 'agent-attachment-remove';
            remove.type = 'button'; remove.textContent = '×';
            remove.setAttribute('aria-label',tr('agent.mini.remove_attachment') + ': ' + attachment.name);
            remove.onclick = () => { state.attachments.splice(index,1); renderAttachments(); };
            preview.append(name); row.append(preview,remove,tip); list.append(row);
        });
        window.lucide?.createIcons();
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
        state.compiledDraft = null;
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
        switchMode('build');
        state.draft = await api('/agent-drafts/' + encodeURIComponent(id));
        state.capabilityId = state.draft.source?.capabilities?.[0]?.id || null;
        await loadEditorCompilation();
        renderDraft();
        if (state.compiledDraft) {
            state.compiledDraft.editorSource = JSON.stringify(editorSource());
            refreshEditorCompilation();
        }
        switchMode('build');
    }
    async function persistDraft({explicit = false} = {}) {
        if (!state.draft) await createDraft();
        syncEditor();
        const source = state.draft.source;
        source.authoring = {
            ...(source.authoring || {}),
            saved: state.recipe && state.recipeEditorId === state.recipe.id ? false : explicit || source.authoring?.saved === true,
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
        if (state.recipe && state.recipeEditorId === state.recipe.id) {
            await saveRecipeEditor(); notice(tr('agent.mini.saved'), 'success'); return state.draft;
        }
        const draft = await persistDraft({explicit: true});
        await loadEditorCompilation(); renderSteps();
        if (state.compiledDraft) state.compiledDraft.editorSource = JSON.stringify(editorSource());
        refreshEditorCompilation();
        return draft;
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
                // Firefox rejects wildcard hosts in URL(), although scopes use URL globs.
                const marker = 'ai2apps-scope-wildcard';
                if (typeof scope !== 'string' || scope.includes(marker)) return false;
                const allowed = new URL(scope.replace(/\*/g, marker));
                const pattern = value => value.replaceAll(marker, '*');
                return destination.protocol === allowed.protocol && destination.port === allowed.port &&
                    glob(destination.hostname, pattern(allowed.hostname)) &&
                    glob(destination.pathname + (allowed.search ? destination.search : ''), pattern(allowed.pathname + allowed.search));
            } catch (_) { return false; }
        });
    }
    function profileSelectionLocked() {
        return state.busy || Boolean(state.run && !state.run.ephemeral &&
            !['completed', 'failed', 'cancelled'].includes(state.run.status)) ||
            ['running', 'needs_user', 'restricted', 'interrupted'].includes(state.exploration?.status);
    }
    async function loadWorkspaceProfiles() {
        const field = $('#agent-profile-field');
        field.hidden = !new URL(location.href).searchParams.has('workspace_editor');
        $('#agent-restart-actions').hidden = field.hidden;
        if (field.hidden) return;
        const profiles = await api('/client/browser-profiles');
        state.workspaceProfiles = profiles;
        state.workspaceStartUrl ||= state.context.url;
        const select = $('#agent-profile');
        select.replaceChildren();
        for (const profile of profiles) {
            const option = document.createElement('option');
            option.value = profile.key; option.textContent = profile.name || profile.key;
            select.append(option);
        }
        select.value = state.context.profile_key || 'default';
        select.disabled = profileSelectionLocked();
    }
    async function selectWorkspaceProfile(profileKey) {
        if (profileSelectionLocked()) { $('#agent-profile').value = state.context.profile_key || 'default'; return; }
        if (!state.workspaceProfiles?.some(profile => profile.key === profileKey)) return;
        if (profileKey === state.context.profile_key) return;
        if (state.client) await state.client.connection.close();
        state.client = null;
        state.contextRevision++;
        state.context = {...state.context, profile_key:profileKey, bidi_context:'', url:state.workspaceStartUrl};
        state.page = {url:state.workspaceStartUrl, title:state.context.title || ''};
        state.localTestVariables = null; state.localTestOutputs = {};
        state.recipeRun = null;
        const fragment = new URLSearchParams(location.hash.slice(1));
        fragment.set('profile_key', profileKey); fragment.delete('bidi_context');
        history.replaceState(history.state, '', location.pathname + location.search + '#' + fragment);
    }
    async function restartWorkspaceEditor() {
        if (state.busy) return;
        const savedId = new URL(location.href).searchParams.get('draft_id');
        if (!window.confirm(tr(savedId ? 'agent.mini.reopen_confirm' : 'agent.mini.recreate_confirm'))) return;
        return withBusy(async () => {
            // Cancel only runs owned by this editor before clearing their UI references.
            const runIds = new Set([state.run && !state.run.ephemeral ? state.run.id : null,
                state.recipeRun?.runId, state.exploration?.pendingCall?.run_id].filter(Boolean));
            for (const id of runIds) {
                const run = await api('/agent-draft-runs/' + encodeURIComponent(id));
                if (!['completed', 'failed', 'cancelled'].includes(run.status))
                    await api('/agent-draft-runs/' + encodeURIComponent(id) + '/cancel', {method:'POST', body:'{}'});
            }
            const goal = state.exploration?.goal || $('#agent-quick-input').value;
            if (state.exploration) {
                state.exploration.cancelled = true; state.exploration.status = 'cancelled';
                clearTimeout(state.exploration.loginTimer);
                await persistExplorationCheckpoint();
            }
            state.exploration = null; state.recipe = null; state.review = null; state.previousReview = null;
            state.recipeEditorId = null; state.recipeEditorKey = null; state.recipeRun = null;
            state.workspaceTestRunId = null; state.compiledDraft = null;
            state.localTestVariables = null; state.localTestOutputs = {};
            renderRun(null); renderExploration(); renderRecipeReview();
            const url = new URL(location.href); url.searchParams.delete('recipe_id');
            history.replaceState(history.state, '', url.pathname + url.search + url.hash);
            if (savedId) {
                await openDraft(savedId);
            } else {
                state.draft = null; state.capabilityId = null;
                switchMode('run');
                document.documentElement.classList.add('agent-workspace-create');
                $('#agent-create-domain').textContent = state.context.title || new URL(state.context.url).hostname;
                $('#agent-quick-input').placeholder = tr('agent.mini.create_goal_placeholder');
                $('#agent-quick-form button[type=submit]').textContent = tr('agent.mini.start_build');
                $('#agent-quick-input').value = goal || '';
                renderAttachments();
                $('#agent-quick-input').focus();
                $('#agent-quick-form').scrollIntoView({block:'start'});
            }
            setContextPinned(false);
            notice(tr('agent.mini.restarted'), 'success');
        });
    }
    async function ensureWorkspaceBrowserContext(validate = false) {
        if ((!validate && state.context.bidi_context) || !new URL(location.href).searchParams.has('workspace_editor')) return;
        const prepare = window.frameElement?.ai2appsEnsureBrowserContext;
        if (typeof prepare !== 'function') throw new Error(tr('agent.mini.page_disconnected'));
        const context = await prepare(state.context.profile_key || 'default');
        if (state.context.bidi_context !== context.bidi_context && state.client) {
            await state.client.connection.close().catch(() => {});
            state.client = null; state.contextRevision++;
        }
        state.context = {...state.context, ...context};
        state.page = {url:context.url, title:state.context.title || ''};
    }
    async function client() {
        await ensureWorkspaceBrowserContext();
        if (state.client) return state.client;
        const revision = state.contextRevision;
        const candidate = new window.AI2AppsBiDi.AI2AppsPageClient({...state.context});
        state.client = candidate;
        try {
            await candidate.connect();
            if (!state.context.profile_key) {
                // Profile identity comes from protected native bootstrap, never focus/URL matching.
                try {
                    const tree = await candidate.connection.command('browsingContext.getTree', {maxDepth:0});
                    const current = (tree.contexts || []).find(item => item.context === candidate.contextId);
                    if (current?.userContext) {
                        const profiles = await api('/client/browser-profiles');
                        for (const profile of profiles) {
                            const binding = await api('/client/browser-profiles/' + encodeURIComponent(profile.key) + '/binding', {method:'POST',body:'{}'});
                            if (binding.user_context === current.userContext) { state.context.profile_key = profile.key; break; }
                        }
                    }
                } catch (_) { /* Older native snapshots conservatively share the default admission bucket. */ }
            }
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
    function assistanceMessage(reason) {
        const messages = {sensitive_input:tr('agent.mini.assist_sensitive'),
            captcha:tr('agent.mini.assist_captcha'),
            legal_consent:tr('agent.mini.assist_consent')};
        return messages[reason] || tr('agent.mini.assist_other', {reason:reason || tr('agent.mini.check_page')});
    }
    function inputValue(step) {
        for (const key of ['value', 'text', 'content']) {
            if (step.arguments?.[key] != null) return String(step.arguments[key]);
        }
        const match = step.description.match(/[“"']([^”"']+)[”"']/);
        return match ? match[1] : '';
    }
    function resolveInput(value, invocationInput, variables = {}, outputs = {}) {
        const env={input:invocationInput,vars:variables,steps:outputs};
        const lookup=path=>{
            const found=path.split('.').reduce((item,key)=>item != null && Object.hasOwn(item,key) ? item[key] : undefined,env);
            if (found === undefined) throw new Error(tr('agent.mini.parameter_required',{name:path}));
            return structuredClone(found);
        };
        if (Array.isArray(value)) return value.map(item=>resolveInput(item,invocationInput,variables,outputs));
        if (value && typeof value==='object') return Object.fromEntries(Object.entries(value).map(([key,item])=>{
            if (key==='url' && typeof item==='string' && !/^\$\{(?:input|vars|steps)\.[^}]+\}$/.test(item))
                return [key,item.replace(/\$\{((?:input|vars|steps)\.[a-zA-Z0-9_.-]+)\}/g,(_m,path)=>encodeURIComponent(String(lookup(path))))];
            return [key,resolveInput(item,invocationInput,variables,outputs)];
        }));
        if (typeof value!=='string') return value;
        const exact=value.match(/^\$\{((?:input|vars|steps)\.[a-zA-Z0-9_.-]+)\}$/);
        if (exact) return lookup(exact[1]);
        return value.replace(/\$\{((?:input|vars|steps)\.[a-zA-Z0-9_.-]+)\}/g,(_m,path)=>String(lookup(path)));
    }
    async function execute(step, preview = false, scopes = null, attachmentIds = []) {
        const bidi = await client();
        const original = bidi.contextId;
        try {
            if (step.browser_context && step.browser_context !== original) {
                const windows = await bidi.relatedWindowObservations();
                if (!windows.some(window => window.context === step.browser_context)) {
                    return {outcome:'failed', evidence:{reason:'unrelated_or_closed_window'}};
                }
                bidi.contextId = step.browser_context;
            }
            const mode = step.mode || (typeof step.execution === 'string' ? step.execution : step.execution?.mode) || 'adaptive';
            if (!preview && mode === 'interpreted' && !step.operation?.startsWith('ai.') && step.operation !== 'agent.call')
                return await executeAIStep(step, scopes, attachmentIds).catch(error => ({outcome:'retryable_error', evidence:{reason:'ai_step_model_failed',detail:error.message,code:error.code,model_failures:error.details?.attempts}}));
            const result = await executeInContext(step, preview, scopes, attachmentIds);
            if (!preview && mode === 'adaptive' && ['not_found','retryable_error','failed'].includes(result.outcome) &&
                !step.operation?.startsWith('ai.') && !['agent.call','complete'].includes(step.operation))
                return await executeAIStep(step, scopes, attachmentIds, result).catch(error => ({outcome:'retryable_error', evidence:{reason:'ai_step_model_failed',detail:error.message,code:error.code,model_failures:error.details?.attempts,compiled_failure:result}}));
            return result;
        } finally { bidi.contextId = original; }
    }
    function stepWorkingGoal(step) {
        if (Object.prototype.hasOwnProperty.call(step, 'working_goal')) return step.working_goal || '';
        return currentCapability()?.working_goal?.trim() || state.draft?.source?.description || state.exploration?.goal || '';
    }
    async function executeAIStep(step, scopes, attachmentIds, failure = null) {
        const bidi = await client();
        const attempts = failure ? [{source_step:step, outcome:failure.outcome, evidence:failure.evidence}] : [];
        const supplied = [...new Set([...attachmentIds, ...state.attachments.map(file => file.asset_id),
            ...(state.draft?.source?.provenance?.attachments || []).map(file => file.asset_id)])].filter(Boolean);
        const goal = `Capability work goal / guidance:\n${stepWorkingGoal(step)}\n\n` +
            `Complete only this Agent step: ${step.description || step.desc || step.id || step.name}.\n` +
            `Resolved arguments: ${JSON.stringify(step.arguments || {})}.\n` +
            'Inspect the current state before acting. Prior failed actions may have partially succeeded; ' +
            'never repeat a completed send, publish, delete or upload. Do not perform later Agent steps.' +
            (step.arguments?.read_only ? '\nYou are already executing light exploration. Use concrete browser actions (inspect, extract_list, scroll, open, hover, click, page_access, or input into an observed search field for the requested search). Do not call light-explore recursively or delegate to another Agent. The ONLY permitted agent.call is builtin:web:clear-blockers / web.clear-blockers when a new observed overlay blocks progress. Once the requested information is visible, finish with complete; the parent will extract the answer.' : '');
        for (let index = 0; index < 8; index++) {
            if (state.unloading) return {outcome:'retryable_error', evidence:{reason:'sidebar_unloading', attempts}};
            const observation = await bidi.explorationObservation();
            observation.context = bidi.contextId;
            observation.html_truncated = Boolean(observation.htmlTruncated);
            observation.windows = await bidi.relatedWindowObservations();
            const decision = await api('/agent-explorations/next', {method:'POST', body:JSON.stringify({
                goal, name:step.id || step.name || 'Agent step', model_tier:step.ai?.tier || 'standard',
                allow_model_escalation:false, verify_goal_with_ai:true, attachments:supplied,
                page:{url:observation.url,title:observation.title}, observation, attempts,
            })});
            if (decision.decision === 'complete') {
                const completed = [...attempts].reverse().find(attempt => attempt.outcome === 'success' &&
                    attempt.evidence && Object.prototype.hasOwnProperty.call(attempt.evidence, 'result'));
                const listStep = (step.authored_operation || step.operation) === 'extract_list';
                const listResult = listStep && [...attempts].reverse().find(attempt => attempt.outcome === 'success' &&
                    Array.isArray(attempt.evidence?.result?.items));
                let output = listResult ? listResult.evidence.result : completed?.evidence.result;
                if (listStep && !Array.isArray(output?.items)) {
                    // Seeing links in DOM is not the structured list promised by this step.
                    output = await bidi.extractArticleList(Number(step.arguments?.limit || 50));
                }
                return {outcome:'success', evidence:{
                    operation:step.operation, ai_tier:step.ai?.tier || 'standard', attempts,
                    result:output ?? {outcome:'success',context:bidi.contextId,url:(await bidi.pageState()).url},
                    before:failure?.evidence?.before, after:await bidi.pageState()}};
            }
            if (decision.decision === 'needs_user') return {outcome:'needs_user', evidence:{
                reason:decision.reason, assistance_kind:decision.assistance_kind, attempts}};
            if (!decision.compiled_step) return {outcome:'failed',evidence:{reason:'ai_step_no_action',attempts}};
            const action = {...decision.compiled_step, mode:'compiled',
                browser_context:decision.browser_context || observation.context};
            if(step.arguments?.read_only) action.arguments={...action.arguments,foundation_read_only:true,foundation_search_goal:step.arguments.goal};
            if (explorationActionNeedsConfirmation(action, decision, goal, observation.url) &&
                !window.confirm(`${action.description || action.operation}\n\n${decision.expected_effect || ''}`))
                return {outcome:'restricted',evidence:{reason:'user_denied_confirmation',attempts}};
            if (step.arguments?.read_only || step.arguments?.preparation_only) {
                const permitted=step.arguments.read_only
                    ? ['inspect','extract_list','scroll','open','hover','click','page_access','agent.call','input']
                    : ['inspect','input','hover','click','scroll'];
                if(!permitted.includes(action.operation)) return {outcome:'restricted',evidence:{reason:'foundation_action_outside_contract',attempts}};
                if(action.operation==='agent.call' && (!step.arguments.clear_blockers ||
                    action.arguments?.agent_id!=='builtin:web:clear-blockers' || action.arguments?.capability!=='web.clear-blockers'))
                    return {outcome:'restricted',evidence:{reason:'foundation_call_outside_contract',proposed_action:action,attempts}};
                const label=[intent(action),action.description].join(' ');
                if(action.operation==='click'&&/buy|purchase|checkout|subscribe|upgrade|pay now|place order|send|publish|delete|accept.*terms|购买|支付|付款|订阅|升级|下单|发送|发布|删除|同意.*协议/i.test(label))
                    return {outcome:'restricted',evidence:{reason:'foundation_consequential_action',attempts}};
            }
            if(action.operation!=='agent.call'&&(step.arguments?.read_only||step.arguments?.preparation_only)) action.arguments={...action.arguments,foundation_read_only:Boolean(step.arguments.read_only),foundation_preparation_only:Boolean(step.arguments.preparation_only),foundation_search_goal:step.arguments.read_only?step.arguments.goal:undefined};
            const result = await execute(action, false, scopes, supplied);
            attempts.push({source_step:decision.source_step, compiled_step:action,
                outcome:result.outcome, evidence:result.evidence});
            if (['needs_user','restricted'].includes(result.outcome)) return result;
        }
        return {outcome:'failed', evidence:{reason:'ai_step_action_limit', attempts}};
    }
    async function executeInContext(step, preview = false, scopes = null, attachmentIds = []) {
        if (step.operation === 'agent.call') return executeAgentCall(step, preview);
        const bidi = await client();
        const before = await bidi.pageState();
        const effectiveScopes = scopes || state.draft?.site_scope || [];
        const op = step.operation;
        const searchEnter = ['input', 'click'].includes(op) &&
            requestedSearchInteraction(step, stepWorkingGoal(step), before.url) &&
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
        if (!['open','read_page'].includes(op) && !scopeAllows(before.url, effectiveScopes)) {
            return {outcome: 'restricted', evidence: {reason: 'site_scope', before}};
        }
        if (preview && ['open', 'read_page', 'wait_state', 'read_results', 'page_access', 'click', 'delete', 'input', 'hover', 'scroll'].includes(op)) {
            const target = ['click', 'delete', 'input', 'hover'].includes(op)
                ? await bidi.findTarget(intent(step), {operation:searchEnter ? 'input' : op}) : null;
            return {
                outcome: target === null && ['click', 'delete', 'input', 'hover'].includes(op)
                    ? 'not_found' : 'success',
                evidence: {preview: true, operation: op, target, before},
            };
        }
        if (['open','read_page','read_results','extract_list','inspect','page_access'].includes(op)) {
            const settings = await bidi.interactionSettings?.(navigationURL || step.arguments?.url || before.url);
            await bidi.interactionPause?.(settings?.interaction_mode || 'natural');
        }
        let result;
        if (op === 'read_page') {
            if (!scopeAllows(step.arguments?.url, effectiveScopes)) return {outcome:'restricted',evidence:{reason:'site_scope_mismatch'}};
            result=await bidi.readPage(step.arguments||{});
            return {outcome:['success','needs_user','restricted'].includes(result.outcome)?'success':'failed',evidence:{operation:op,result}};
        }
        if (op === 'wait_state') {
            result=await bidi.waitState(step.arguments?.target,step.arguments?.present!==false,step.arguments?.timeout_ms);
            return {outcome:result.ready?'success':'failed',evidence:{operation:op,result}};
        }
        if (op === 'page_access' && step.arguments?.url) return {outcome:'failed',
            evidence:{reason:'page_access_does_not_navigate_use_open', before}};
        if (op === 'page_access') result = await bidi.handlePageAccess();
        else if (op === 'read_results') {
            result = await bidi.readResultPages(step.arguments?.items, step.arguments?.limit || 3, {newTab:step.arguments?.new_tab === true, delayMs:step.arguments?.delay_ms || 0});
            if (!result.articles.length) return {outcome:'failed', evidence:{operation:op, result, before}};
        } else if (op === 'extract_list') {
            try {
                result = step.arguments?.site_extraction ? await bidi.executeExtractionStep(step) : await bidi.extractArticleList(Number(step.arguments?.limit || 50));
            } catch (error) {
                if (error.message !== 'site_rule_drift') throw error;
                return {outcome:'not_found',evidence:{operation:op,reason:'site_rule_drift',before}};
            }
        } else if (op === 'inspect') {
            const query = intent(step);
            result = {page: before, context:bidi.contextId, windows:await bidi.relatedWindowObservations(),
                ...(query ? {target:await bidi.findTarget(query)} : {})};
        } else if (['click', 'delete', 'hover', 'input'].includes(op)) {
            // Fail closed from the authored intent before resolving or touching a
            // page element.  A missing/renamed button must not downgrade an
            // explicit legal-consent, CAPTCHA, or payment request to not_found.
            const requestedPolicy = interactionPolicy(step, null);
            if (requestedPolicy) {
                return {outcome: requestedPolicy.outcome,
                    evidence: {...requestedPolicy, before}};
            }
            const assetIds = Array.isArray(step.arguments?.asset_ids) ? step.arguments.asset_ids.map(file => typeof file === 'object' ? file.asset_id : file) : step.arguments?.asset_ids;
            if (op === 'input' && Array.isArray(assetIds) && assetIds.length) {
                const allowed = new Set([...attachmentIds, ...state.attachments.map(file => file.asset_id),
                    ...(state.draft?.source?.provenance?.attachments || []).map(file => file.asset_id)]);
                if (assetIds.some(id => !allowed.has(id))) return {outcome:'failed',evidence:{reason:'attachment_not_supplied',before}};
                try {
                const transfers = await Promise.all(assetIds.map(id => api('/gallery/assets/' + encodeURIComponent(id) + '/browser-transfer', {method:'POST'})));
                const upload = await bidi.setAttachmentFiles(step.target?.ref || intent(step), transfers.map(file => file.path));
                if (!upload) return {outcome:'not_found',evidence:{reason:'file_input_not_found',before}};
                return {outcome:'success',evidence:{operation:op,result:upload,before,after:await bidi.pageState()}};
                } catch (error) { return {outcome:'failed',evidence:{reason:'attachment_upload_failed',detail:error.message,before}}; }
            }
            const target = await bidi.findTarget(intent(step), {operation:searchEnter ? 'input' : op});
            if (!target) return {outcome: 'not_found', evidence: {operation: op, intent: intent(step), before}};
            if ((step.arguments?.foundation_read_only || step.arguments?.foundation_preparation_only) && op==='click' &&
                /buy|purchase|checkout|subscribe|upgrade|pay|order|send|publish|delete|submit|购买|支付|付款|订阅|升级|下单|发送|发布|删除|提交/i.test(target.name||target.text||''))
                return {outcome:'restricted',evidence:{reason:'foundation_consequential_target',target,before}};
            if(step.arguments?.foundation_preparation_only && /press.*enter|submit|回车|提交/i.test(step.description||''))
                return {outcome:'restricted',evidence:{reason:'foundation_submission_disallowed',target,before}};
            if(op==='input'&&step.arguments?.foundation_read_only &&
                (!/搜索|查询|search|find/i.test(step.arguments.foundation_search_goal||'') || !isSearchField(target)))
                return {outcome:'restricted',evidence:{reason:'foundation_input_not_search',target,before}};
            const policy = interactionPolicy(step, target);
            if (policy) return {outcome: policy.outcome, evidence: {...policy, target, before}};
            if ((op === 'input' || searchEnter) && target.sensitive) {
                return {outcome: 'needs_user', evidence: {reason: 'sensitive_input', target, before}};
            }
            const windowsBefore = await bidi.relatedWindowObservations();
            const previous = state.exploration?.attempts?.at(-1);
            if (op === 'click' && windowsBefore.length && previous?.evidence?.result?.target?.ref === target.ref &&
                previous?.evidence?.before?.fingerprint === before.fingerprint) {
                return {outcome:'failed', evidence:{reason:'repeat_click_with_open_window', before,
                    windows:windowsBefore}};
            }
            const pointer = await bidi.naturalPointer(target, {
                click: op !== 'hover', hoverMs: op === 'hover' ? 650 : 0,
                seed: Number(step.source_index || 0) + 7,
            });
            if (op === 'input') {
                const value = inputValue(step);
                const submitSearch = requestedSearchInteraction(step, stepWorkingGoal(step), before.url) &&
                    /\bsubmit\b|press.*enter|提交|回车/i.test(step.description || '');
                if (!value && !submitSearch) return {outcome: 'failed', evidence: {reason: 'input_value_required', target, before}};
                await bidi.typeText(value, {replace:Boolean(value), submit:submitSearch});
            }
            if (op === 'click' && searchEnter) await bidi.typeText('', {submit:true});
            result = {target, interaction_profile: pointer?.profile || 'natural'};
            result.windows = await bidi.relatedWindowObservations();
            result.opened_contexts = result.windows.filter(window =>
                !windowsBefore.some(previous => previous.context === window.context)).map(window => window.context);
        } else if (op === 'scroll') {
            const delta = Number(step.arguments?.delta_y || 620);
            await bidi.scroll(delta);
            result = {delta_y: delta, interaction_profile: 'natural'};
        } else if (op === 'open') {
            const url = navigationURL;
            await bidi.connection.command('browsingContext.navigate', {
                context: bidi.contextId, url, wait: 'complete',
            }, 30000);
            const delayMs = Math.min(30000, Math.max(0, Number(step.arguments?.delay_ms ?? 3000)));
            await new Promise(resolve => setTimeout(resolve, delayMs));
            const readiness = await bidi.waitForStability(10000, {requireContent:true});
            result = {url, delay_ms:delayMs, stable:readiness.stable};
        } else if (op === 'complete') result = {complete: true};
        else return {outcome: 'failed', evidence: {reason: 'unsupported_operation', operation: op}};
        const after = await bidi.pageState();
        return {outcome: result?.classification === 'needs_user' ? 'needs_user' :
            result?.classification === 'restricted' ? 'restricted' : 'success',
            evidence: {operation: op, result, before, after}};
    }
    async function executeAgentCall(step, preview = false) {
        if (preview) return {outcome:'success', evidence:{preview:true, operation:'agent.call'}};
        const exploration = ['running','needs_user','interrupted'].includes(state.exploration?.status)
            ? state.exploration : null;
        const args = step.arguments || {};
        const outerPending=exploration?.pendingCall;
        const nested=Boolean(outerPending && (outerPending.step?.arguments?.agent_id!==args.agent_id ||
            outerPending.step?.arguments?.capability!==args.capability));
        const nestedKey=JSON.stringify([args.agent_id,args.capability,step.id||step.name,(await client()).contextId]);
        const savePending=value=>{
            if(!exploration)return;
            if(nested){exploration.nestedCalls ||= {};if(value)exploration.nestedCalls[nestedKey]=value;else delete exploration.nestedCalls[nestedKey];}
            else if(value)exploration.pendingCall=value;else delete exploration.pendingCall;
        };
        let pending = nested ? exploration.nestedCalls?.[nestedKey] : outerPending;
        if (!pending) {
            pending = {request_key:crypto.randomUUID(), step, awaitingAssistance:false};
            if (exploration) { savePending(pending); await persistExplorationCheckpoint(); }
        }
        if (!pending.run_id) {
            const bidi = await client();
            const created = await api('/agent-calls/runs', {method:'POST', body:JSON.stringify({
                agent_id:args.agent_id, capability:args.capability, generation_id:args.generation_id,
                input:args.parameters || {}, browser_context:{...state.context, bidi_context:bidi.contextId},
                session_id:pending.session_id, idempotency_key:pending.request_key,
            })});
            pending.run_id = created.run_id; pending.session_id = created.session_id;
            if (exploration) { savePending(pending); await persistExplorationCheckpoint(); }
        }
        const deadline = Date.now() + 180000;
        let runEvents = null, eventPending = false, eventWaiter = null;
        const observeBackend = () => {
            if (runEvents) return;
            runEvents = new EventSource('/v1/platform/agent-runs/' + encodeURIComponent(pending.run_id) + '/events');
            const changed = () => { eventPending = true; eventWaiter?.(); };
            for (const kind of ['agent.status','agent.run.running','agent.run.waiting_input','agent.run.completed',
                'agent.run.failed','agent.run.cancelled','agent.run.paused','agent.input.request','agent.approval.request','agent.interaction.submitted'])
                runEvents.addEventListener(kind, changed);
            runEvents.onopen = changed;
        };
        try {
        for (let poll = 0; Date.now() < deadline && poll < 600; poll++) {
            if (state.unloading || exploration?.cancelled) return {outcome:'failed', evidence:{reason:'agent_call_interrupted'}};
            const run = await api('/agent-draft-runs/' + encodeURIComponent(pending.run_id));
            if (run.status === 'completed') {
                if (exploration) { savePending(null); await persistExplorationCheckpoint(); }
                return {outcome:'success', evidence:{operation:'agent.call', result:run.output?.result || {},
                    run_id:run.id, capability:args.capability, after:await (await client()).pageState()}};
            }
            if (['failed','cancelled','interrupted'].includes(run.status)) return {outcome:'failed',
                evidence:{reason:run.error?.message || run.status, run_id:run.id}};
            const assistance = (run.interactions || []).find(item => item.status === 'pending' &&
                item.request?.control === 'browser_user_assistance');
            const action = (run.interactions || []).find(item => item.status === 'pending' &&
                (item.request?.control === 'agent_confirmation' || (run.input?.parameters?.execution_owner !== 'local' && item.request?.control === 'browser_bidi_action')));
            let interaction = action, result;
            if (assistance) {
                if (!pending.awaitingAssistance) {
                    pending.awaitingAssistance = true;
                    if (exploration) await persistExplorationCheckpoint();
                    else renderRun(run);
                    return {outcome:'needs_user', evidence:{reason:assistance.prompt, run_id:run.id}};
                }
                pending.awaitingAssistance = false;
                interaction = assistance; result = {continued:true};
            } else if (action?.request.control === 'agent_confirmation') {
                result = {decision:window.confirm(action.prompt) ? 'approve' : 'deny'};
            } else if (action) {
                result = await execute(resolveInput(action.request.step, action.request.invocation_input || {}),
                    Boolean(action.request.preview), action.request.site_scope || [],
                    Object.values(action.request.invocation_input || {}).flat().filter(value => value?.asset_id).map(value => value.asset_id));
                if (result.outcome === 'needs_user' || result.outcome === 'restricted') return result;
            }
            if (interaction && result) {
                await api('/agent-draft-runs/' + encodeURIComponent(run.id) + '/interactions/' +
                    encodeURIComponent(interaction.id) + '/respond', {method:'POST',
                    body:JSON.stringify({response:result,response_id:crypto.randomUUID()})});
            } else if (run.input?.parameters?.execution_owner === 'local') {
                observeBackend();
                if (!eventPending) await new Promise(resolve => {
                    const timer = setTimeout(resolve, Math.max(0, deadline-Date.now()));
                    eventWaiter = () => { clearTimeout(timer); resolve(); };
                });
                eventPending = false; eventWaiter = null;
            } else await new Promise(resolve => setTimeout(resolve, 350));
        }
        return {outcome:'failed', evidence:{reason:'agent_call_timeout',run_id:pending.run_id}};
        } finally { runEvents?.close(); }
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
        let plan = await api('/agent-drafts/' + encodeURIComponent(state.draft.id) +
            '/steps/' + encodeURIComponent(sourceStep.name) + '/plan?capability_id=' +
            encodeURIComponent(state.capabilityId || ''), {method: 'POST', body: '{}'});
        if (!plan.valid) {
            showStepExecution(index,tr('agent.mini.ai_preparing_arguments'));
            const response = await api('/agent-steps/revisions',{method:'POST',body:JSON.stringify({
                source:structuredClone(state.draft.source),capability_id:state.capabilityId,step_index:index,
                feedback:'Compile this step from its natural-language description and declared input parameters. Fix these validation errors: '+JSON.stringify(plan.report?.errors || [])+
                    '. Bind explicitly mentioned input parameters using ${input.NAME}. Preserve the step name, operation, description, graph transitions and unrelated settings. Do not execute actions or invent URLs. If the description is ambiguous, report the ambiguity rather than guessing.',
                messages:[],model_tier:builderSelection().model_tier})});
            currentCapability().steps[index] = response.step;
            renderSteps(); await persistDraft();
            plan = await api('/agent-drafts/'+encodeURIComponent(state.draft.id)+'/steps/'+encodeURIComponent(response.step.name)+
                '/plan?capability_id='+encodeURIComponent(state.capabilityId || ''),{method:'POST',body:'{}'});
        }
        if (!plan.valid || !plan.step) {
            const errors = (plan.report?.errors || []).map(item => item.code).join(', ');
            throw new Error(tr('agent.mini.invalid_step', { error: errors || 'invalid step' }));
        }
        return plan.step;
    }
    function showStepExecution(index, text, tone = 'info') {
        const node = $('#agent-steps').children[index];
        if (!node?.matches('.agent-step')) return;
        node.open = true;
        let status = node.querySelector('.agent-step-execution');
        if (!status) {
            status = document.createElement('div'); status.className = 'agent-step-execution';
            status.setAttribute('role','status'); status.setAttribute('aria-live','polite');
            node.querySelector('.agent-step-actions').after(status);
        }
        status.dataset.tone = tone; status.textContent = text;
    }
    async function checkSteps(index = null) {
        return withBusy(async () => {
            const source = editorSource();
            const response = await api('/agent-source/check', {method:'POST', body:JSON.stringify({source})});
            const errors = response.report?.errors || [];
            const selected = Array.isArray(source.capabilities)
                ? Math.max(0, source.capabilities.findIndex(item => item.id === state.capabilityId)) : -1;
            const prefix = selected < 0 ? '' : 'capabilities.' + selected + '.';
            const steps = (selected < 0 ? source : source.capabilities[selected])?.steps || [];
            const globalErrors = errors.filter(item => !/(^|\.)steps\.\d+(\.|$)/.test(item.path || ''));
            for (let i = 0; i < steps.length; i++) {
                if (index !== null && i !== index) continue;
                const path = prefix + 'steps.' + i;
                const related = errors.filter(item => item.path === path || item.path?.startsWith(path + '.'));
                const issues = [...globalErrors, ...related];
                showStepExecution(i, issues.length
                    ? issues.map(item => `${item.path}: ${item.message || item.code}`).join('\n')
                    : tr('agent.mini.check_passed'), issues.length ? 'error' : 'success');
            }
            const issues = index === null ? errors : errors.filter(item =>
                globalErrors.includes(item) || item.path === prefix + 'steps.' + index ||
                item.path?.startsWith(prefix + 'steps.' + index + '.'));
            notice(issues.length ? issues.map(item => `${item.path}: ${item.message || item.code}`).join('\n')
                : tr('agent.mini.check_passed'), issues.length ? 'error' : 'success');
            if (index === null) {
                const target = $('#agent-notice');
                target.setAttribute('tabindex', '-1'); target.focus({preventScroll:true});
                target.scrollIntoView({block:'start',behavior:'smooth'});
            }
            return response;
        });
    }
    async function runEditorStep(index, preview) {
        return withBusy(async () => {
            const previousPin = state.executionContextPinned;
            setContextPinned(true);
            showStepExecution(index, preview ? tr('agent.mini.preparing_preview') : tr('agent.mini.preparing_step'));
            try {
            const input = readInputFields($('#agent-build-inputs'), currentCapability()?.inputs);
            const planned = await plannedStep(index);
            showStepExecution(index, preview ? tr('agent.mini.previewing_step') : tr('agent.mini.executing_step'));
            if (state.localTestVariables === null && !["assign","condition"].includes(planned.operation)) {
                const initialized=await api("/agent-drafts/"+encodeURIComponent(state.draft.id)+"/variables/evaluate?capability_id="+encodeURIComponent(state.capabilityId || ""),
                    {method:"POST",body:JSON.stringify({input})});
                state.localTestVariables=initialized.variables;
            }
            const step = resolveInput(planned, input, state.localTestVariables || {}, state.localTestOutputs);
            notice(tr(preview ? 'agent.mini.previewing' : 'agent.mini.running', { step: step.id }));
            let result;
            if (['assign','condition'].includes(step.operation)) {
                result=await api('/agent-drafts/'+encodeURIComponent(state.draft.id)+'/steps/'+encodeURIComponent(step.id)+
                    '/evaluate?capability_id='+encodeURIComponent(state.capabilityId || ''), {method:'POST',body:JSON.stringify({input,
                        variables:state.localTestVariables,steps:state.localTestOutputs})});
                if (!preview && result.outcome !== 'failed') {
                    state.localTestVariables=result.variables;
                    state.localTestOutputs[step.id]={output:result.evidence?.result || {}};
                }
            } else {
                result = await execute(step, preview, null, Object.values(input).flatMap(value => Array.isArray(value) ? value : [value]).filter(value => value && typeof value === "object" && value.asset_id).map(value => value.asset_id));
            }
            await saveEvidence(step, result);
            const message = step.id + ' → ' + result.outcome;
            showStepExecution(index, message, result.outcome === 'success' ? 'success' : 'error');
            notice(message, result.outcome === 'success' ? 'success' : 'warning');
            return result;
            } catch (error) {
                showStepExecution(index, error.message || String(error), 'error');
                throw error;
            } finally { setContextPinned(previousPin); }
        });
    }
    function updateRunHandoff() {
        const editing = !$('#agent-build-panel').hidden ||
            new URL(location.href).searchParams.has('workspace_editor');
        $('#agent-run-handoff').hidden = editing || state.run?.status !== 'completed';
    }
    function renderRun(run) {
        if (run?.id !== state.run?.id) state.resultMode = 'json';
        state.run = run;
        $('#agent-profile').disabled = profileSelectionLocked();
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
        updateRunHandoff();
        renderRunResult(run);
    }

    let checkpointQueue = Promise.resolve();
    function persistExplorationCheckpoint() {
        if (!state.exploration || !state.context.bidi_context) return Promise.resolve();
        const {loginTimer, ...exploration} = state.exploration;
        const body = JSON.stringify({context:state.exploration.ownerContext || state.context.bidi_context,
            checkpoint:{version:1, exploration, attachments:state.attachments, recipe:state.recipe}});
        checkpointQueue = checkpointQueue.catch(() => {}).then(() =>
            api('/agent-explorations/checkpoint', {method:'POST', body}));
        return checkpointQueue;
    }
    async function restoreExplorationCheckpoint() {
        if (!state.context.bidi_context) return false;
        const saved = await api('/agent-explorations/checkpoint?context=' + encodeURIComponent(state.context.bidi_context));
        const checkpoint = saved.checkpoint;
        if (checkpoint?.version !== 1 || !checkpoint.exploration || checkpoint.exploration.status === 'cancelled') return false;
        state.exploration = checkpoint.exploration;
        state.exploration.ownerContext = state.context.bidi_context;
        state.attachments = checkpoint.attachments || [];
        state.recipe = checkpoint.recipe || null;
        const exploration = state.exploration;
        if (exploration.pendingStep || ['running','needs_user','restricted','interrupted'].includes(exploration.status)) {
            exploration.status = 'interrupted';
            exploration.cancelled = false;
            if (exploration.pendingStep && !exploration.pendingCall) {
                exploration.attempts.push({source_step:exploration.pendingStep, outcome:'unknown',
                    evidence:{reason:'sidebar_reloaded_during_action',
                        detail:'Action may already have executed. Inspect current page and verify its effect before repeating it, especially upload or publish.'}});
                delete exploration.pendingStep;
            }
            setContextPinned(true);
        }
        $('#agent-quick-input').value = exploration.goal || '';
        renderAttachments();
        renderExploration();
        if (state.recipe) {
            await loadRecipeReview();
        }
        notice(tr('agent.mini.exploration_restored'), 'warning');
        return true;
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
        void persistExplorationCheckpoint().catch(() => notice(tr('agent.mini.checkpoint_failed'), 'warning'));
        $('#agent-exploration-summary').textContent = tr('agent.mini.exploration_budget', {
            count: exploration.attempts.length, max: exploration.maxSteps,
        });
        const status = $('#agent-exploration-state');
        status.textContent = statusText(exploration.status);
        status.dataset.status = exploration.status;
        $('#agent-exploration-stop').hidden = !['running','needs_user','interrupted'].includes(exploration.status);
        $('#agent-exploration-resume').hidden = !['needs_user','interrupted','failed','budget_exhausted'].includes(exploration.status);
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
            'weibo.com': ['微博', 'weibo'], 's.weibo.com': ['微博', 'weibo'], 'weibo.cn': ['微博', 'weibo'],
            'm.weibo.cn': ['微博', 'weibo'],
        };
        return (names[host] || (host.endsWith('.wikipedia.org') ? names['wikipedia.org'] : []))
            .some(name => /[^a-z]/.test(name) ? text.includes(name) :
                new RegExp('(^|[^a-z0-9])' + name + '([^a-z0-9]|$)').test(text));
    }

    function isSearchField(target) {
        return target?.role==='searchbox' || /搜索|查询|\bsearch\b|\bquery\b/i.test(
            [target?.name,target?.text,target?.placeholder,target?.accessible_name].filter(Boolean).join(' '));
    }
    function requestedSearchInteraction(step, goal, pageURL) {
        goal=step.arguments?.foundation_search_goal || goal;
        if (!['input', 'click'].includes(step.operation) || !/搜索|查询|\bsearch\b|\bfind\b/i.test(goal)) return false;
        let url;
        try { url = new URL(pageURL); } catch (_) { return false; }
        if (!['http:', 'https:'].includes(url.protocol) ||
            !step.arguments?.foundation_read_only && !['google.com', 'google.cn', 'bing.com', 'baidu.com'].includes(
                url.hostname.toLowerCase().replace(/^www\./, ''))) return false;
        const target = step.target?.accessible_name || step.target?.intent || '';
        const text = target + ' ' + (step.description || '');
        if (/delete|publish|send|purchase|pay|checkout|login|sign.?in|password|captcha|authorize|agree|accept|删除|发布|发送|购买|支付|登录|密码|验证码|授权|同意|接受/i.test(text)) return false;
        return /搜索|查询|\bsearch\b|\bquery\b/i.test(target || step.description || '');
    }

    function explorationActionNeedsConfirmation(step, decision, goal = '', pageURL = '') {
        if (navigationMentionedInGoal(step, goal)) return false;
        // Opening a login dialog on the already authorized site is preparation.
        // Credential entry and verification still stop in interactionPolicy/execute.
        if (step.operation === 'click' &&
            /登录|登入|\blogin\b|\blog in\b|\bsign.?in\b/i.test(String(step.target?.accessible_name || step.target?.intent || '').trim()) &&
            /发布|发微博|发送|上传|登录|publish|post|send|upload|login|sign in/i.test(goal) &&
            !/支付|购买|授权|同意|pay|purchase|authorize|agree/i.test(intent(step))) return false;
        // A requested search includes entering the query and submitting it.
        // The generic server "submit" flag also covers search forms; target
        // resolution and sensitive-input/interaction policy still run below.
        if (requestedSearchInteraction(step, goal, pageURL)) return false;
        // Ordinary preparation is already authorized by the task. Gate only
        // explicit high-impact actions; prose mentioning publish is not a send.
        if (step.operation === 'delete' || step.operation === 'approval' || step.operation === 'open') return true;
        if (step.operation !== 'click') return false;
        const target = step.target?.accessible_name || step.target?.intent || '';
        return /购买|支付|授权|同意|接受|purchase|pay|checkout|authorize|agree|accept/i.test(target) ||
            (/^(发布|发送|提交|publish|send|submit|post)$/i.test(target.trim()) &&
             !/发布|发送|提交|发微博|publish|send|submit|post/i.test(goal));
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

    function windowObservationSignature(observation) {
        return JSON.stringify([observation.fingerprint, (observation.windows || []).map(window =>
            [window.context, window.fingerprint, window.error])]);
    }
    function watchLoginAssistance(observation, reason) {
        const exploration = state.exploration;
        const initial = windowObservationSignature(observation);
        const deadline = Date.now() + 10 * 60 * 1000;
        const poll = async () => {
            if (state.exploration !== exploration || exploration.status !== 'needs_user' ||
                exploration.cancelled || Date.now() > deadline) return;
            try {
                const bidi = await client();
                const current = await bidi.explorationObservation();
                current.windows = await bidi.relatedWindowObservations();
                // A changed document is evidence for the planner, never proof of login.
                if (windowObservationSignature(current) !== initial && !state.busy) {
                    await withBusy(() => startExploration(exploration.goal, true));
                    return;
                }
            } catch (_) { /* Manual Continue remains available after reconnect. */ }
            if (state.exploration === exploration && exploration.status === 'needs_user') {
                exploration.loginTimer = setTimeout(poll, 3000);
            }
        };
        clearTimeout(exploration.loginTimer);
        exploration.loginTimer = setTimeout(poll, 3000);
    }
    async function startExploration(goal, resume = false) {
        setContextPinned(true);
        const name = goal.slice(0, 42);
        if (!resume) {
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
            ownerContext:state.context.bidi_context, goal, name, attachments:state.attachments.map(file => file.asset_id), status: 'running', cancelled: false,
            scopes: pageScope() ? [pageScope()] : [],
            maxSteps: 12, attempts: [], events: [],
            modelSelection: builderSelection(),
        };
        }
        const exploration = state.exploration;
        clearTimeout(exploration.loginTimer);
        exploration.status = 'running';
        renderExploration();
        try {
        for (let index = exploration.attempts.length; index < exploration.maxSteps; index++) {
            if (exploration.cancelled) {
                exploration.status = 'cancelled';
                addExplorationEvent('evaluate', tr('agent.mini.exploration_stopped'), '', 'warning');
                setContextPinned(false);
                return null;
            }
            if (state.unloading || state.exploration !== exploration) return null;
            if (exploration.pendingCall) {
                const pending = exploration.pendingCall;
                const execution = await executeAgentCall(pending.step);
                if (execution.outcome === 'needs_user') {
                    exploration.status = 'needs_user'; renderExploration();
                    notice(execution.evidence?.reason || tr('agent.mini.needs_user'), 'warning');
                    await persistExplorationCheckpoint(); return null;
                }
                delete exploration.pendingCall;
                delete exploration.pendingStep;
                exploration.attempts.push({...pending.attempt, outcome:execution.outcome,evidence:execution.evidence});
                await persistExplorationCheckpoint();
                continue;
            }
            const observation = await (await client()).explorationObservation();
            if (state.unloading || state.exploration !== exploration) return null;
            observation.context = (await client()).contextId;
            observation.windows = await (await client()).relatedWindowObservations();
            if (state.unloading || state.exploration !== exploration) return null;
            state.page = {url: observation.url, title: observation.title,
                fingerprint: observation.fingerprint};
            addExplorationEvent('observe', observation.title || observation.url,
                `${observation.control_count} controls · ${observation.text_length} chars`);
            const decision = await api('/agent-explorations/next', {
                method: 'POST',
                body: JSON.stringify({
                    goal, name, attachments:exploration.attachments, ...exploration.modelSelection,
                    page: {url: observation.url, title: observation.title},
                    observation: {
                        context: observation.context,
                        windows: observation.windows,
                        fingerprint: observation.fingerprint,
                        text_length: observation.text_length,
                        link_count: observation.link_count,
                        button_count: observation.button_count,
                        control_count: observation.control_count,
                        text_sample: observation.text_sample,
                        controls: observation.controls,
                        file_inputs: observation.file_inputs,
                        html: observation.html,
                        html_truncated: observation.htmlTruncated,
                    },
                    attempts: exploration.attempts,
                }),
            });
            if (state.unloading || state.exploration !== exploration) return null;
            if (decision.decision === 'needs_user') {
                exploration.status = 'needs_user';
                addExplorationEvent('evaluate', tr('agent.mini.needs_user'), decision.reason || '', 'warning');
                notice(decision.reason || tr('agent.mini.needs_user'), 'warning');
                watchLoginAssistance(observation, decision.reason);
                return null;
            }
            if (decision.decision === 'complete') {
                addExplorationEvent('evaluate',
                    decision.reason || tr('agent.mini.exploration_goal_satisfied'), '', 'success');
                return distillExploration();
            }
            const step = {...decision.compiled_step, browser_context:decision.browser_context || observation.context};
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
                    exploration.attempts.push({
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
                    if (!exploration.scopes.includes(scope)) exploration.scopes.push(scope);
                }
            }
            exploration.pendingStep = decision.source_step;
            if (step.operation === 'agent.call') {
                exploration.pendingCall = {step, request_key:crypto.randomUUID(), awaitingAssistance:false,
                    attempt:{proposal_id:decision.proposal_id,source_step:decision.source_step,
                        compiled_step:decision.compiled_step,expected_effect:decision.expected_effect}};
            }
            await persistExplorationCheckpoint();
            const execution = await execute(step, false, exploration.scopes);
            if (state.unloading || state.exploration !== exploration) return null;
            delete exploration.pendingStep;
            if (execution.outcome === 'needs_user' && exploration.pendingCall) {
                exploration.pendingCall.attempt = {proposal_id:decision.proposal_id,
                    source_step:decision.source_step, compiled_step:decision.compiled_step,
                    expected_effect:decision.expected_effect};
                exploration.status = 'needs_user'; renderExploration();
                notice(execution.evidence?.reason || tr('agent.mini.needs_user'), 'warning');
                await persistExplorationCheckpoint(); return null;
            }
            exploration.attempts.push({
                proposal_id: decision.proposal_id,
                source_step: decision.source_step,
                compiled_step: decision.compiled_step,
                expected_effect: decision.expected_effect,
                outcome: execution.outcome,
                evidence: execution.evidence,
            });
            await persistExplorationCheckpoint();
            addExplorationEvent('evaluate', execution.outcome,
                execution.evidence?.reason || execution.evidence?.after?.fingerprint || '',
                execution.outcome === 'success' ? 'success' : 'warning');
            if (execution.outcome === 'needs_user' || execution.outcome === 'restricted') {
                exploration.status = execution.outcome;
                renderExploration();
                notice(assistanceMessage(execution.evidence?.reason), 'warning');
                return null;
            }
        }
        exploration.status = 'budget_exhausted';
        addExplorationEvent('evaluate', tr('agent.mini.exploration_limit'), '', 'warning');
        throw new Error(tr('agent.mini.exploration_limit'));
        } catch (error) {
            if (state.unloading || state.exploration !== exploration) return null;
            if (exploration.status === 'running') {
                exploration.status = 'failed';
                addExplorationEvent('evaluate', tr('agent.mini.exploration_failed'),
                    [error.message || String(error), ...(error.details?.attempts || []).map(attempt =>
                        [attempt.model_id, attempt.stage, attempt.reason, ...(attempt.report?.errors || []).map(item => item.message || item.code)].filter(Boolean).join(' · '))].join('\n'), 'error');
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

    function mountRecipeEditor(review) {
        const key = `${review.recipe_id}:${review.source_revision}`;
        const panel = $('#agent-build-panel');
        document.documentElement.classList.remove('agent-workspace-create');
        document.documentElement.classList.add('agent-recipe-editing');
        $('#agent-review-steps').append(panel);
        panel.hidden = false;
        if (state.recipeEditorKey === key) return;
        const previousDraft = state.recipeEditorId === review.recipe_id ? state.draft : null;
        state.recipeEditorId = review.recipe_id;
        state.recipeEditorKey = key;
        const source = structuredClone(review.source);
        state.draft = {...(previousDraft || {}), id:previousDraft?.id || null,
            revision:previousDraft?.revision || 0, status:'editing',
            name:source.name, site_scope:source.site_scope || [], source};
        state.capabilityId = source.capabilities?.[0]?.id || null;
        state.compiledDraft = {draftId:state.draft.id, source:structuredClone(source),
            generation:{source_revision:state.draft.revision, status:review.compiler.valid ? 'validated' : 'failed',
                ir:review.compiled_ir, report:review.compiler}};
        renderDraft();
        state.compiledDraft.editorSource = JSON.stringify(editorSource());
        // The rendered form supplies defaults and may reorder object keys.
        // Those display normalizations are not edits to the reviewed Source.
        state.recipeEditorBaseline = recipeSourceSignature(editorSource());
        refreshEditorCompilation();
    }
    function recipeSourceSignature(value) {
        const ordered = item => Array.isArray(item) ? item.map(ordered) :
            item && typeof item === 'object' ? Object.fromEntries(Object.keys(item).sort().map(key=>[key,ordered(item[key])])) : item;
        return JSON.stringify(ordered(value));
    }
    async function saveRecipeEditor() {
        if (!state.recipe || state.recipeEditorId !== state.recipe.id) return;
        syncEditor();
        const source = structuredClone(state.draft.source);
        if (recipeSourceSignature(source) === (state.recipeEditorBaseline || recipeSourceSignature(state.review.source))) return;
        const result = await api('/agent-recipes/'+encodeURIComponent(state.recipe.id)+'/source', {
            method:'PATCH',body:JSON.stringify({expected_revision:state.review.source_revision,source})});
        state.previousReview = state.review;
        state.recipe = result.recipe; state.review = result.review;
        renderRecipeReview();
        await persistExplorationCheckpoint();
    }

    function renderRecipeReview() {
        const review = state.review;
        const panel = $('#agent-recipe-review');
        panel.hidden = !review;
        if (!review) {
            document.documentElement.classList.remove('agent-recipe-editing');
            const editor = $('#agent-build-panel');
            if (editor.parentElement !== $('.agent-mini')) $('.agent-mini').append(editor);
            return;
        }
        const valid = Boolean(review.compiler?.valid);
        const effects = review.compiler?.effects || [];
        $('#agent-review-summary').textContent =
            `v${review.source_revision} · ${valid ? tr('agent.mini.valid') : tr('agent.mini.invalid')} · ${effects.join(', ') || 'read'}`;
        const status = $('#agent-review-status');
        const committed = review.recipe_status === 'committed' || state.recipe?.status === 'committed';
        status.textContent = statusText(committed ? 'committed' : review.status);
        status.dataset.status = committed ? 'approved' : review.status;
        // Keep the shared editor connected: clearing this container removes
        // #agent-build-panel before mountRecipeEditor can look it up again.
        // One authoring surface for both exploratory Recipes and saved Agents.
        mountRecipeEditor(review);
        $('#agent-review-source').textContent = JSON.stringify(review.source, null, 2);
        $('#agent-review-ir').textContent = JSON.stringify(review.compiled_ir, null, 2);
        $('#agent-recipe-inputs').closest('.agent-parameters').hidden = true;
        $('#agent-recipe-confirm').hidden = true;
        const approved = committed || review.status === 'approved';
        $('#agent-review-approve').disabled = approved || !valid;
        $('#agent-review-revise').disabled = committed;
        $('#agent-infer-parameters').disabled = committed;
        $('#agent-review-commit').hidden = committed || !approved;
    }

    async function loadRecipeReview() {
        if (!state.recipe) return null;
        const recipeId = state.recipe.id;
        const review = await api('/agent-recipes/' + encodeURIComponent(recipeId) + '/review');
        if (state.recipe?.id !== recipeId) return null;
        if (review.recipe_status) state.recipe.status = review.recipe_status;
        state.review = review;
        if (state.recipe.status === 'committed') state.review = {...review, status:'approved', recipe_status:'committed'};
        if (state.exploration && ['tested', 'committed'].includes(state.recipe.status)) {
            state.exploration.status = state.recipe.status === 'committed' ? 'committed' : 'approved';
            renderExploration();
        }
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
        await saveRecipeEditor();
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
        await saveRecipeEditor();
        const button = $('#agent-review-approve');
        button.disabled = true;
        button.textContent = tr('agent.mini.review_approving');
        try {
            const result = await api('/agent-recipes/' + encodeURIComponent(state.recipe.id) +
                '/review/approve', {method:'POST', body:JSON.stringify({
                    expected_revision: state.review.source_revision,
                })});
            state.recipe = result.recipe;
            state.review = result.review;
            if (state.exploration) {
                state.exploration.status = result.recipe.status === 'committed' ? 'committed' : 'approved';
                renderExploration();
                await persistExplorationCheckpoint();
            }
            notice(tr('agent.mini.review_approved'), 'success');
        } catch (error) {
            notice(error.message || String(error), 'error');
            $('#agent-notice').scrollIntoView({block:'nearest'});
        } finally {
            button.textContent = tr('agent.mini.review_approve');
            renderRecipeReview();
        }
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
    function focusRunOutcome(run) {
        if (state.run?.id !== run.id) return;
        const candidates = run.status === 'completed'
            ? ['#agent-run-result', '#agent-run-status']
            : ['#agent-notice', '#agent-run-status'];
        const target = candidates.map(selector => $(selector)).find(node => node && !node.hidden);
        if (!target) return;
        target.setAttribute('tabindex', '-1');
        target.focus({preventScroll: true});
        target.scrollIntoView({block: 'start', behavior: 'smooth'});
    }
    async function returnToWorkspace(run) {
        if (state.workspaceTestRunId !== run.id || state.run?.id !== run.id ||
            !['completed', 'failed', 'cancelled'].includes(run.status)) return;
        state.workspaceTestRunId = null;
        try { await window.frameElement?.ai2appsReturnToWorkspace?.(); }
        catch (error) { notice(tr('agent.mini.return_failed', {error:error.message}), 'warning'); }
    }
    async function watchLocalRun(runId, resumeAssistance = false) {
        // Local owns every browser action. Closing this observer has no effect
        // on execution; replayable SSE replaces status polling.
        return new Promise((resolve, reject) => {
            const stream = new EventSource('/v1/platform/agent-runs/' + encodeURIComponent(runId) + '/events');
            let busy = false, changed = false, closed = false;
            const close = () => { closed = true; stream.close(); window.removeEventListener('pagehide', close); };
            window.addEventListener('pagehide', close, {once:true});
            const refresh = async () => {
                if (closed) return;
                if (busy) { changed = true; return; }
                busy = true;
                try {
                    const run = await api('/agent-draft-runs/' + encodeURIComponent(runId));
                    if (state.run?.id !== runId) { close(); resolve(run); return; }
                    renderRun(run);
                    if (['completed','failed','cancelled','paused'].includes(run.status)) {
                        close(); setContextPinned(false);
                        if (run.status === 'completed' && state.recipe) {
                            await loadRecipeReview(); notice(tr('agent.mini.review_ready'), 'success');
                        }
                        await returnToWorkspace(run); focusRunOutcome(run); resolve(run); return;
                    }
                    const human = (run.interactions || []).find(item => item.status === 'pending' &&
                        ['browser_user_assistance','agent_confirmation'].includes(item.request?.control));
                    if (human) {
                        if (human.request.control === 'browser_user_assistance' && !resumeAssistance) {
                            notice(human.prompt, 'warning'); close(); resolve(run); return;
                        }
                        const response = human.request.control === 'agent_confirmation'
                            ? {decision:window.confirm(human.request.summary || human.prompt) ? 'approve' : 'deny'}
                            : {continued:true};
                        resumeAssistance = false;
                        await api('/agent-draft-runs/' + encodeURIComponent(runId) + '/interactions/' + encodeURIComponent(human.id) + '/respond',
                            {method:'POST',body:JSON.stringify({response,response_id:crypto.randomUUID()})});
                        changed = true;
                    }
                } catch (error) { close(); reject(error); }
                finally { busy = false; if (changed && !closed) { changed = false; void refresh(); } }
            };
            for (const kind of ['agent.status','agent.run.queued','agent.run.running','agent.run.waiting_input',
                'agent.run.completed','agent.run.failed','agent.run.cancelled','agent.run.paused',
                'agent.input.request','agent.approval.request','agent.interaction.submitted','agent.interaction.expired'])
                stream.addEventListener(kind, refresh);
            stream.onopen = refresh; // Fresh snapshot also covers replay compaction/reconnect.
            void refresh();
        });
    }
    async function driveRun(resumeAssistance = false) {
        if (!state.run) return;
        const runId = state.run.id;
        if (state.run.input?.parameters?.execution_owner === 'local') return watchLocalRun(runId, resumeAssistance);
        setContextPinned(true);
        try {
        for (let poll = 0; poll < 180; poll++) {
            if (state.run?.id !== runId) return;
            const run = await api('/agent-draft-runs/' + encodeURIComponent(runId));
            if (state.run?.id !== runId) return;
            renderRun(run);
            if (run.input?.parameters?.execution_owner === 'local') return watchLocalRun(runId, resumeAssistance);
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
                await returnToWorkspace(run);
                focusRunOutcome(run);
                return run;
            }
            const interaction = (run.interactions || []).find(item =>
                item.status === 'pending' && item.request?.control === 'browser_bidi_action');
            const assistance = (run.interactions || []).find(item => item.status === 'pending' &&
                item.request?.control === 'browser_user_assistance');
            if (assistance) {
                if (!resumeAssistance) { notice(assistance.prompt, 'warning'); return run; }
                resumeAssistance = false;
                await api('/agent-draft-runs/' + encodeURIComponent(run.id) + '/interactions/' +
                    encodeURIComponent(assistance.id) + '/respond', {method:'POST',
                    body:JSON.stringify({response:{continued:true},response_id:crypto.randomUUID()})});
                continue;
            }
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
                let result;
                try {
                    result = await execute(step, Boolean(interaction.request.preview),
                        interaction.request.site_scope || [], Object.values(interaction.request.invocation_input || {}).flatMap(value => Array.isArray(value) ? value : [value]).filter(value => value && typeof value === "object" && value.asset_id).map(value => value.asset_id));
                } catch (error) {
                    // Resolve the durable browser request even if its Tab disappeared.
                    // Do not silently replay an in-flight action in another document.
                    result = {outcome:'failed',evidence:{reason:'browser_execution_error',detail:error.message}};
                }
                if (interaction.request.draft_id) await saveEvidence(step, result, run.id);
                if (result.outcome === 'needs_user') {
                    notice(assistanceMessage(result.evidence?.reason), 'warning');
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
            if (state.recipe && state.recipeEditorId === state.recipe.id) return runRecipe();
            await ensureWorkspaceBrowserContext(true);
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
                        profile_key: state.context.profile_key || 'default',
                        url: state.page?.url || state.context.url || '',
                    },
                }),
            });
            if (new URL(location.href).searchParams.has('workspace_editor')) state.workspaceTestRunId = created.id;
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
            if (state.recipe && state.recipeEditorId === state.recipe.id) {
                await saveRecipeEditor();
                if (!state.review.compiler.valid) {
                    for (let index=0; index<(currentCapability()?.steps || []).length; index++) await plannedStep(index);
                    await saveRecipeEditor();
                }
                if (!state.review.compiler.valid) throw new Error(tr('agent.mini.compile_failed', {error:state.review.compiler.errors.map(item=>item.code).join(', ')}));
                notice(tr('agent.mini.compile_ready'), 'success'); return;
            }
            await persistDraft({explicit: true});
            let generation = await api('/agent-drafts/' + encodeURIComponent(state.draft.id) +
                '/compile', {method: 'POST', body: '{}'});
            if (generation.status === 'failed') {
                for (let index=0; index<(currentCapability()?.steps || []).length; index++) await plannedStep(index);
                generation = await api('/agent-drafts/'+encodeURIComponent(state.draft.id)+'/compile',{method:'POST',body:'{}'});
            }
            if (generation.status === 'failed') {
                const errors = (generation.report?.errors || []).map(item => item.code).join(', ');
                throw new Error(tr('agent.mini.compile_failed', { error: errors }));
            }
            state.draft = await api('/agent-drafts/' + encodeURIComponent(state.draft.id));
            state.draft = await api('/agent-drafts/' + encodeURIComponent(state.draft.id) +
                '/generations/' + encodeURIComponent(generation.id) + '/activate',
                {method: 'POST', body: '{}'});
            state.compiledDraft = {draftId:state.draft.id, generation,
                source:structuredClone(state.draft.source)};
            await refreshDrafts();
            renderDraft();
            state.compiledDraft.editorSource = JSON.stringify(editorSource());
            refreshEditorCompilation();
            notice(tr('agent.mini.compile_ready'), 'success');
        });
    }
    async function withBusy(action) {
        if (state.busy) return;
        state.busy = true;
        $('#agent-profile').disabled = true;
        $('#agent-restart').disabled = true;
        document.documentElement.classList.add('busy');
        try { return await action(); }
        catch (error) {
            notice(error.message || String(error), 'error');
            $('#agent-notice').scrollIntoView({behavior:'smooth', block:'nearest'});
        }
        finally {
            state.busy = false;
            $('#agent-profile').disabled = profileSelectionLocked();
            $('#agent-restart').disabled = false;
            document.documentElement.classList.remove('busy');
        }
    }
    async function quickRun(event) {
        event.preventDefault();
        const description = $('#agent-quick-input').value.trim();
        if (!description) return;
        await withBusy(async () => {
            await ensureWorkspaceBrowserContext(true);
            return startExploration(description);
        });
    }
    async function runRecipe() {
        if (!state.recipe) return;
        // A failed dispatch hydration must not create a second run on retry.
        if (state.recipeRun?.recipeId === state.recipe.id) {
            const existing = await api('/agent-draft-runs/' + encodeURIComponent(state.recipeRun.runId));
            if (!['completed', 'failed', 'cancelled'].includes(existing.status)) {
                if (new URL(location.href).searchParams.has('workspace_editor')) state.workspaceTestRunId = existing.id;
                renderRun(existing);
                return driveRun(true);
            }
        }
        await saveRecipeEditor();
        await ensureWorkspaceBrowserContext(true);
        const created = await api('/agent-recipes/' + encodeURIComponent(state.recipe.id) + '/runs', {
            method:'POST', body:JSON.stringify({input:readInputFields($('#agent-build-inputs'), currentCapability()?.inputs),browser_context:{
                bidi_context:state.context.bidi_context || '', profile_key:state.context.profile_key || 'default',
                url:state.page?.url || state.context.url || '',
            }})
        });
        // Recipe creation returns a compact dispatch receipt (`run_id`), while
        // the run UI and polling loop consume the full AgentRun shape (`id`).
        // Hydrate the receipt before rendering so we never poll `/undefined`.
        const runId = created.id || created.run_id;
        if (!runId) throw new Error('Agent run was created without an id');
        state.recipeRun = {recipeId:state.recipe.id, runId};
        const run = created.id ? created :
            await api('/agent-draft-runs/' + encodeURIComponent(runId));
        if (new URL(location.href).searchParams.has('workspace_editor')) state.workspaceTestRunId = run.id;
        renderRun(run); notice(tr('agent.mini.recipe_testing')); return driveRun();
    }
    async function commitRecipe(mode) {
        if (!state.recipe) return;
        await saveRecipeEditor();
        if (state.review.status !== 'approved') throw new Error(tr('agent.mini.review_required'));
        const result = await api('/agent-recipes/' + encodeURIComponent(state.recipe.id) + '/commit', {
            method:'POST', body:JSON.stringify({mode})
        });
        state.draft = result.site_agent;
        state.capabilityId = result.recipe.committed_capability_id;
        state.recipe = null; state.review = null; state.previousReview = null;
        rememberRecipe();
        if (state.exploration) {
            state.exploration.status = 'committed';
            renderExploration();
            await persistExplorationCheckpoint();
        }
        $('#agent-recipe-confirm').hidden = true; renderRecipeReview();
        setContextPinned(false);
        await refreshDrafts(); await loadEditorCompilation(); renderDraft();
        if (state.compiledDraft) state.compiledDraft.editorSource = JSON.stringify(editorSource());
        refreshEditorCompilation(); switchMode('build');
        notice(tr('agent.mini.capability_added'), 'success');
    }
    function bind() {
        $('#agent-add-variable').onclick=()=>withBusy(async()=>{
            syncEditor(); const capability=currentCapability(); capability.variables ||= {type:'object',properties:{}};
            let i=1;while(capability.variables.properties['variable_'+i]) i++;
            capability.variables.properties['variable_'+i]={type:'integer',default:0,title:'',description:''};
            renderVariables(); renderSteps();state.localTestVariables=null;state.localTestOutputs={};
        });
        $('#agent-reset-variables').onclick=()=>{state.localTestVariables=null;state.localTestOutputs={};notice(tr('agent.mini.test_variables_reset'),'success');};
        $('#agent-variable-definitions').addEventListener('change',()=>withBusy(async()=>{syncEditor();state.localTestVariables=null;state.localTestOutputs={};renderSteps();}));
        $('#agent-build-panel').addEventListener('input', refreshEditorCompilation);
        $('#agent-build-panel').addEventListener('change', refreshEditorCompilation);
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
            await saveRecipeEditor();
            const result = await api('/agent-recipes/' + encodeURIComponent(state.recipe.id) + '/parameters/infer', {
                method:'POST', body:JSON.stringify({expected_revision:state.review.source_revision}),
            });
            state.previousReview = state.review; state.recipe = result.recipe; state.review = result.review;
            renderRecipeReview();
        });
        $('#agent-exploration-resume').onclick = () => withBusy(() => startExploration(state.exploration.goal, true));
        $('#agent-exploration-stop').onclick = () => {
            if (state.exploration) {
                state.exploration.cancelled = true;
                if (state.exploration.pendingCall?.run_id) void api('/agent-draft-runs/' +
                    encodeURIComponent(state.exploration.pendingCall.run_id) + '/cancel',
                    {method:'POST',body:'{}'}).catch(error => notice(error.message, 'warning'));
                clearTimeout(state.exploration.loginTimer);
                if (['needs_user','interrupted'].includes(state.exploration.status)) {
                    state.exploration.status = 'cancelled'; renderExploration(); setContextPinned(false);
                }
            }
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
        $('#agent-capability').onchange = event => { syncEditor(); state.capabilityId=event.target.value; renderCapabilityDetails(); renderParameters(); renderVariables(); state.localTestVariables=null;state.localTestOutputs={}; renderSteps(); };
        $('#agent-capability-title').onchange = () => {syncEditor(); const option=$('#agent-capability').selectedOptions[0]; if(option)option.textContent=$('#agent-capability-title').value;};
        $('#agent-capability-description').onchange = () => syncEditor();
        $('#agent-capability-working-goal').onchange = () => syncEditor();
        $('#agent-delete-capability').onclick = () => {
            syncEditor(); ensureCapabilitySource(); const cap=currentCapability();
            if (!capabilities().length || !window.confirm(tr('agent.mini.delete_capability_confirm',{name:cap.title || cap.name}))) return;
            state.draft.source.capabilities=capabilities().filter(item=>item.id!==cap.id);
            state.capabilityId=null; renderDraft(); syncEditor();
        };
        $('#agent-add-capability').onclick = () => {
            $('#agent-capability-template').value='';
            $('#agent-new-capability-name').value='';
            $('#agent-new-capability-description').value='';
            $('#agent-custom-capability-fields').hidden=false;
            $('#agent-new-capability-panel').showModal();
            $('#agent-capability-template').focus();
        };
        $('#agent-cancel-capability').onclick = () => {
            $('#agent-new-capability-panel').close();
            $('#agent-add-capability').focus();
        };
        $('#agent-capability-template').onchange = () => {
            $('#agent-custom-capability-fields').hidden=$('#agent-capability-template').value!=='';
        };
        $('#agent-create-capability').onclick = () => {
            if($('#agent-capability-template').value==='' && !$('#agent-new-capability-name').value.trim()){
                $('#agent-new-capability-name').value='';
                $('#agent-new-capability-name').reportValidity();return;
            }
            syncEditor();
            ensureCapabilitySource();
            let n=state.draft.source.capabilities.length+1, id='capability-'+n;
            while(capabilities().some(item=>item.id===id))id='capability-'+(++n);
            const value=$('#agent-capability-template').value;
            const template=value===''?null:state.capabilityTemplates?.[Number(value)];
            const existing=template && capabilities().find(item=>item.name===template.name);
            if(existing){state.capabilityId=existing.id;$('#agent-new-capability-panel').close();renderDraft();return;}
            const schema=structuredClone(template?.input_schema || {type:'object',properties:{}});
            const mappings=Object.fromEntries(Object.keys(schema.properties || {}).map(key=>[key,'${input.'+key+'}']));
            state.draft.source.capabilities.push({id, name:template?.name || 'site.'+id,
                title:template?.title || $('#agent-new-capability-name').value.trim(), description:template?.description || $('#agent-new-capability-description').value.trim(),
                inputs:schema, outputs:structuredClone(template?.output_schema || {type:'object',properties:{}}),
                steps:template?[{name:'run',desc:template.description,operation:'agent.call',
                    arguments:{agent_id:template.agent_id,capability:template.name,generation_id:template.generation_id,parameters:mappings},
                    on:{success:'done',failed:'failed'}}]:[]});
            state.capabilityId=id; $('#agent-new-capability-panel').close(); renderDraft(); syncEditor();
        };
        $('#agent-refresh').onclick = () => withBusy(() => initialize({restoreCompleted:false}));
        $('#agent-new-from-run').onclick = () => withBusy(async () => {
            switchMode('build'); await createDraft();
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
        const addCall = document.createElement('button'); addCall.type = 'button';
        addCall.textContent = tr('agent.mini.call_agent');
        $('#agent-add-step').after(addCall);
        addCall.onclick = () => withBusy(async () => {
            syncEditor();
            const items = (await api('/agent-capabilities?url=' + encodeURIComponent(state.page?.url || state.context.url || ''))).items || [];
            if (!items.length) throw new Error(tr('agent.mini.no_callable_capability'));
            const item = items.find(item => item.name === 'site.ensure-login') || items[0];
            const steps = currentCapability().steps;
            steps.push(normalizedStep({name:'call-agent-' + (steps.length + 1),
                desc:tr('agent.mini.call_named_capability', {name:item.name}), operation:'agent.call', arguments:{
                    agent_id:item.agent_id, capability:item.name, generation_id:item.generation_id, parameters:{}},
                on:{success:'done',failed:'failed'}}, steps.length));
            renderSteps();
        });
        $('#agent-add-parameter').onclick = () => withBusy(async () => {
            syncEditor(); const capability = currentCapability();
            capability.inputs ||= {type:'object',properties:{}};
            capability.inputs.properties ||= {};
            let index = 1; while (capability.inputs.properties['value_'+index]) index++;
            capability.inputs['x-ai2apps-order'] = [...orderedParameters(capability.inputs).map(([key]) => key), 'value_'+index];
            capability.inputs.properties['value_'+index] = {type:'string',title:tr('agent.mini.parameter_label')};
            renderParameters(); renderSteps();
        });
        $('#agent-save').onclick = () => withBusy(saveDraft);
        $('#agent-delete').onclick = () => withBusy(deleteDraft);
        $('#agent-preview').onclick = () => checkSteps();
        $('#agent-run-all').onclick = () => runAll(false);
        $('#agent-compile').onclick = compileAndActivate;
        $('#agent-run-pause').onclick = () => withBusy(async () => {
            renderRun(await api('/agent-draft-runs/' + encodeURIComponent(state.run.id) + '/pause',
                {method: 'POST', body: '{}'}));
            notice(tr('agent.mini.paused'), 'warning');
        });
        $('#agent-restart').onclick = restartWorkspaceEditor;
        $('#agent-profile').onchange = event => selectWorkspaceProfile(event.target.value).catch(error => notice(error.message, 'error'));
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
            return driveRun(true);
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
        const workspace = new URL(location.href).searchParams;
        if (workspace.has('workspace_editor') || workspace.has('workspace_task')) {
            state.page = {url:state.context.url || '', title:state.context.title || ''};
            await refreshDrafts();
            await loadBuilderModels();
            await loadWorkspaceProfiles();
            if (workspace.has('workspace_editor')) {
                if (workspace.get('recipe_id')) {
                    state.recipe = {id:workspace.get('recipe_id')};
                    await loadRecipeReview();
                    setContextPinned(true, 'editor'); notice(''); return;
                }
                if (workspace.get('draft_id')) {
                    await openDraft(workspace.get('draft_id'));
                    if (workspace.get('capability_id')) {
                        state.capabilityId = workspace.get('capability_id'); renderDraft();
                    }
                } else if (workspace.has('workspace_create')) {
                    document.documentElement.classList.add('agent-workspace-create');
                    switchMode('run');
                    $('#agent-create-domain').textContent = state.context.title || new URL(state.context.url).hostname;
                    $('#agent-quick-input').placeholder = tr('agent.mini.create_goal_placeholder');
                    $('#agent-quick-form button[type=submit]').textContent = tr('agent.mini.start_build');
                    $('#agent-quick-input').focus();
                } else { switchMode('build'); await createDraft(); }
                setContextPinned(true, 'editor'); notice('');
                return;
            }
            await client();
            const taskId = workspace.get('workspace_task');
            const worker = workspace.get('worker');
            const run = await api('/agent-draft-runs/' + encodeURIComponent(workspace.get('run_id')));
            renderRun(run);
            const heartbeat = setInterval(() => {
                if (['completed','failed','cancelled'].includes(state.run?.status)) { clearInterval(heartbeat); return; }
                void api('/browser-workspace/tasks/' + encodeURIComponent(taskId) + '/heartbeat', {
                    method:'POST', body:JSON.stringify({worker}),
                }).catch(() => { clearInterval(heartbeat); state.run = null;
                    notice(tr('agent.mini.task_disconnected'), 'warning'); });
            }, 15000);
            window.addEventListener('pagehide', () => clearInterval(heartbeat), {once:true});
            try { await driveRun(); }
            catch(error) {
                clearInterval(heartbeat);
                await api('/browser-workspace/tasks/' + encodeURIComponent(taskId) + '/interrupt', {
                    method:'POST',body:JSON.stringify({worker,message:String(error.message).slice(0,1000)}),
                }).catch(() => {});
                throw error;
            }
            return;
        }
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
        const explorationRestored = await restoreExplorationCheckpoint().catch(() => false);
        const runs = await api('/agent-draft-runs?limit=10');
        const pageRuns = (runs.items || []).filter(run => runMatchesContext(run));
        const resumable = pageRuns.find(item =>
            ['queued', 'planning', 'running', 'waiting_input', 'interrupted'].includes(item.status));
        if (explorationRestored) {
            renderRun(null);
        } else if (resumable) {
            renderRun(resumable);
            if (bidiReady && resumable.status !== 'interrupted') void driveRun();
        } else if (restoreCompleted && pageRuns[0]) {
            renderRun(pageRuns[0]);
        }
        const recipeId = new URL(location.href).searchParams.get('recipe_id');
        if (recipeId) {
            state.recipe = {id:recipeId};
            try { await loadRecipeReview(); }
            catch (error) { state.recipe = null; rememberRecipe(); notice(error.message, 'warning'); }
        }
    }
    function contextKey(context = state.context) {
        return `${String(context?.bidi_context || '')}\n${String(context?.url || '')}`;
    }
    function runMatchesContext(run, context = state.context) {
        const owner = run?.input?.parameters?.browser_context;
        const currentId = String(context?.bidi_context || '');
        // A URL is not a Tab identity: two Tabs may show the same website.
        return !!currentId && String(owner?.bidi_context || '') === currentId;
    }
    function contextIsWebPage(context = state.context) {
        try { return ['http:', 'https:'].includes(new URL(String(context?.url || '')).protocol); }
        catch (_) { return false; }
    }
    async function applyBrowserContext(detail) {
        if (state.contextPinned) {
            state.pendingBrowserContext = {...(detail || {})};
            return;
        }
        const previousKey = contextKey();
        const previousTab = state.context.bidi_context;
        state.context = {...state.context, ...(detail || {})};
        if (contextKey() === previousKey) return;
        if (state.context.bidi_context !== previousTab) {
            if (state.exploration) {
                clearTimeout(state.exploration.loginTimer);
                state.exploration.status = 'interrupted';
                void persistExplorationCheckpoint().catch(() => {});
                state.exploration = null;
                renderExploration();
            }
            setContextPinned(false);
            state.presentations.clear();
            renderRun(null);
        }
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
        state.unloading = true;
        clearTimeout(state.exploration?.loginTimer);
        // Preserve the lease across reload; the restored checkpoint decides when to release it.
        void state.client?.connection?.close();
    });
})();
