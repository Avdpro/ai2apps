const test = require('node:test'), assert = require('node:assert/strict');
const vm = require('node:vm'), fs = require('node:fs');
const source = fs.readFileSync(__dirname + '/../web/static/js/agent_mini.js', 'utf8');
const helpers = source.slice(source.indexOf('    function editorCompiledStep('), source.indexOf('    function renderSteps('));
function context(state, api = async () => []) {
    const labels = [{}];
    const ctx = {state, api, structuredClone, JSON, encodeURIComponent,
        editorSource:()=>state.draft.source, $$:()=>labels, tr:key=>key,
        savedForMenu:()=>true,notice:()=>{}};
    vm.runInNewContext(helpers + '\nglobalThis.helpers={editorCompiledStep,loadEditorCompilation,refreshEditorCompilation};', ctx);
    return {ctx, labels};
}
test('saved active generation wins over newer unactivated output; capability and step IDs select correct IR', async () => {
    const generation = {id:'active',source_revision:3,status:'active',ir:{capabilities:[
        {id:'other',steps:[{id:'upload',operation:'click'}]},
        {id:'publish',steps:[{id:'upload',operation:'upload',arguments:{files:'${input.attachments}'},mode:'adaptive',effect:'interact'}]}
    ]}};
    const draft = {id:'draft',revision:4,active_generation_id:'active',source:{}};
    let requested;
    const {ctx} = context({draft}, async url => {requested=url;return [{id:'new',source_revision:4,status:'validated'},generation];});
    await ctx.helpers.loadEditorCompilation();
    assert.equal(requested,'/agent-drafts/draft/generations');
    assert.equal(ctx.state.compiledDraft.generation.id,'active');
    const step = ctx.helpers.editorCompiledStep(generation,'publish','upload');
    assert.equal(step.operation,'upload');
    assert.equal(step.arguments.files,'${input.attachments}');
    assert.equal(ctx.helpers.editorCompiledStep(generation,'missing','upload'),null);
    assert.equal(ctx.helpers.editorCompiledStep(generation,'publish','renamed'),null);
});
test('legacy saved Source is compiled for inspection without activation or execution', async () => {
    const state = {draft:{id:'saved',revision:1,source:{}}}, requests=[];
    const {ctx} = context(state,async (url, options) => {
        requests.push([url,options?.method]);
        return url.endsWith('/generations') ? [] :
            {id:'compiled',source_revision:1,status:'validated',ir:{steps:[{id:'step',operation:'input'}]}};
    });
    await ctx.helpers.loadEditorCompilation();
    assert.deepEqual(requests,[['/agent-drafts/saved/generations',undefined],['/agent-drafts/saved/compile','POST']]);
    assert.equal(state.compiledDraft.generation.id,'compiled');
});
test('unsaved changes and older generations are labelled stale, while fresh output is current', () => {
    const draft = {revision:2,source:{name:'original'}};
    const {ctx,labels} = context({draft,compiledDraft:{source:{},generation:{source_revision:2},editorSource:JSON.stringify(draft.source)}});
    ctx.helpers.refreshEditorCompilation();
    assert.equal(labels[0].textContent,'agent.mini.after_compile');
    draft.source.name='changed'; ctx.helpers.refreshEditorCompilation();
    assert.equal(labels[0].textContent,'agent.mini.compiled_stale');
    draft.source.name='original'; draft.revision=3; ctx.helpers.refreshEditorCompilation();
    assert.equal(labels[0].textContent,'agent.mini.compiled_stale');
});
test('loading generations cannot attach another draft’s result after navigation', async () => {
    const state = {draft:{id:'first',revision:1,source:{}}};
    const {ctx} = context(state,async () => {
        state.draft={id:'second',revision:1,source:{}};
        return [{id:'old',source_revision:1,status:'validated'}];
    });
    await ctx.helpers.loadEditorCompilation();
    assert.equal(state.compiledDraft,null);
    assert.equal(ctx.helpers.editorCompiledStep({status:'failed',ir:{steps:[{id:'step'}]}},null,'step'),null);
    assert.equal(ctx.helpers.editorCompiledStep({status:'validated',ir:{steps:[{id:'step',operation:'open'}]}},null,'step').operation,'open');
});
