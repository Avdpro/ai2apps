/* Model names never imply Agent suitability. These flags belong to the catalog. */
(function (root) {
    'use strict';
    function agentSummary(model) {
        const raw = model?.capabilities || [];
        const normalize = key => String(key).replace(/([A-Z])/g, '_$1').toLowerCase().replace(/-/g, '_');
        const declarations = {work_standard: null, work_complex: null, tool_calling_reliable: null};
        for (const [key, value] of (Array.isArray(raw) ? raw.map(key => [key, true]) : Object.entries(raw))) {
            const normalized = normalize(key);
            if (Object.hasOwn(declarations, normalized) && typeof value === 'boolean') declarations[normalized] = value;
        }
        // The server preserves explicit false values that the positive capability list cannot.
        const detailed = model?.agent_capability_declaration?.declarations;
        for (const key of Object.keys(declarations)) {
            if (detailed && Object.hasOwn(detailed, key) && (detailed[key] === null || typeof detailed[key] === 'boolean')) declarations[key] = detailed[key];
        }
        const capacity = declarations.work_standard === true || declarations.work_complex === true ? true
            : declarations.work_standard === false && declarations.work_complex === false ? false : null;
        const requirements = {task_complexity: capacity, tool_calling_reliable: declarations.tool_calling_reliable};
        const missing = Object.keys(requirements).filter(key => requirements[key] === null);
        const unsupported = Object.keys(requirements).filter(key => requirements[key] === false);
        return {declarations, missing, unsupported, status: unsupported.length ? 'declared_insufficient' : missing.length ? 'undeclared' : 'qualified'};
    }
    function agentEligible(model) {
        return agentSelectable(model) && agentSummary(model).status === 'qualified';
    }
    function agentSelectable(model) {
        return !!model && !model.is_hidden && !model.is_helper && model.checkpoint_ready !== false
            && model.source_type !== 'hf_cache'
            && ['llm', 'vlm', ''].includes(String(model.model_type || '').toLowerCase());
    }
    function agentDeclaration(model) {
        return agentSummary(model).status;
    }
    function agentNotice(model, {explicit = false, language = 'zh'} = {}) {
        const summary = agentSummary(model);
        if (summary.status === 'qualified') return '';
        const zh = String(language).startsWith('zh');
        const labels = zh ? {task_complexity: '中等或复杂任务能力（work_standard / work_complex）', tool_calling_reliable: '可靠工具调用（tool_calling_reliable）'}
            : {task_complexity: 'standard or complex tasks (work_standard / work_complex)', tool_calling_reliable: 'reliable tool calling (tool_calling_reliable)'};
        const parts = [];
        if (summary.unsupported.length) parts.push((zh ? '明确不支持：' : 'Explicitly unsupported: ') + summary.unsupported.map(key => labels[key]).join(zh ? '、' : ', '));
        if (summary.missing.length) parts.push((zh ? '尚未声明：' : 'Not declared: ') + summary.missing.map(key => labels[key]).join(zh ? '、' : ', '));
        const prefix = explicit ? (zh ? '保留你明确选择的模型。' : 'Keeping your explicitly selected model. ')
            : (zh ? '正在使用所配置的默认模型。' : 'Using the configured default model. ');
        return prefix + parts.join(zh ? '；' : '; ') + (zh ? '。自动选择条件未满足；未声明不等于不支持。' : '. Automatic selection requirements are unmet; missing declarations do not mean unsupported.');
    }
    function agentOptions(models) {
        const rank = {qualified: 0, declared_insufficient: 1, undeclared: 2};
        return (models || []).filter(agentSelectable).slice().sort((a,b) => rank[agentDeclaration(a)] - rank[agentDeclaration(b)]);
    }
    function agentDefault(models, preferred, workDefaults = [], apiDefault = null) {
        // A saved Agent default is an explicit user choice; quality filters apply only to fallback.
        if (preferred && (models || []).some(model => model.id === preferred && agentSelectable(model))) return preferred;
        // The account API default is the normal profile's chosen model, not a
        // capability guess. Never substitute another model when it is unavailable.
        if (!preferred && apiDefault) return (models || []).some(model =>
            model.id === apiDefault && agentSelectable(model)) ? apiDefault : null;
        const eligible = (models || []).filter(agentEligible);
        for (const id of [preferred, ...workDefaults]) {
            if (id && eligible.some(model => model.id === id)) return id;
        }
        // Stable catalog order resolves ties; no provider, price or model-name guess.
        return eligible[0]?.id || null;
    }
    const policy = {agentSummary, agentNotice, agentEligible, agentSelectable, agentDeclaration, agentOptions, agentDefault};
    root.AI2AppsConversationModelPolicy = policy;
    if (typeof module !== 'undefined') module.exports = policy;
})(globalThis);
