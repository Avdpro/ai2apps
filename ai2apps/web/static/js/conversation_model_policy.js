/* Model names never imply Agent suitability. These flags belong to the catalog. */
(function (root) {
    'use strict';
    function agentEligible(model) {
        if (!model || model.is_hidden || model.is_helper || model.checkpoint_ready === false) return false;
        const raw = model.capabilities || [];
        const flags = new Set(Array.isArray(raw) ? raw : Object.keys(raw).filter(key => raw[key] === true));
        return (flags.has('work_standard') || flags.has('work_complex'))
            && flags.has('tool_calling_reliable')
            && ['llm', 'vlm', ''].includes(String(model.model_type || '').toLowerCase());
    }
    function agentSelectable(model) {
        return !!model && !model.is_hidden && !model.is_helper && model.checkpoint_ready !== false
            && model.source_type !== 'hf_cache'
            && ['llm', 'vlm', ''].includes(String(model.model_type || '').toLowerCase());
    }
    function agentDeclaration(model) {
        if (model.agent_capability_declaration) return model.agent_capability_declaration.status;
        if (agentEligible(model)) return 'qualified';
        const raw = model.capabilities || [];
        const keys = ['work_standard', 'work_complex', 'tool_calling_reliable'];
        const known = Array.isArray(raw) ? keys.some(key => raw.includes(key))
            : keys.some(key => typeof raw[key] === 'boolean');
        return known ? 'declared_insufficient' : 'undeclared';
    }
    function agentOptions(models) {
        const rank = {qualified: 0, declared_insufficient: 1, undeclared: 2};
        return (models || []).filter(agentSelectable).slice().sort((a,b) => rank[agentDeclaration(a)] - rank[agentDeclaration(b)]);
    }
    function agentDefault(models, preferred, workDefaults = []) {
        // A saved Agent default is an explicit user choice; quality filters apply only to fallback.
        if (preferred && (models || []).some(model => model.id === preferred && agentSelectable(model))) return preferred;
        const eligible = (models || []).filter(agentEligible);
        for (const id of [preferred, ...workDefaults]) {
            if (id && eligible.some(model => model.id === id)) return id;
        }
        // Stable catalog order resolves ties; no provider, price or model-name guess.
        return eligible[0]?.id || null;
    }
    const policy = {agentEligible, agentSelectable, agentDeclaration, agentOptions, agentDefault};
    root.AI2AppsConversationModelPolicy = policy;
    if (typeof module !== 'undefined') module.exports = policy;
})(globalThis);
