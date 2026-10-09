const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const helpers=source.slice(source.indexOf('    function mountRecipeEditor('),source.indexOf('    function renderRecipeReview('));
function harness(){
 const nodes=new Map(),classes=new Set(),calls=[];
 const state={recipe:{id:'recipe'},review:{recipe_id:'recipe',source_revision:1,source:{name:'Example',site_scope:['https://example.com/**'],inputs:{type:'object',properties:{query:{type:'string'}}},variables:{type:'object',properties:{index:{type:'integer',default:0}}},steps:[{name:'read'}]},compiler:{valid:true},compiled_ir:{steps:[{id:'read'}]}}};
 const env={state,structuredClone,JSON,encodeURIComponent,document:{documentElement:{classList:{add:x=>classes.add(x),remove:x=>classes.delete(x)}}},$:key=>{if(!nodes.has(key))nodes.set(key,{append(child){this.child=child;},hidden:true});return nodes.get(key);},renderDraft:()=>calls.push('render'),editorSource:()=>state.draft.source,refreshEditorCompilation(){},syncEditor(){},persistExplorationCheckpoint:async()=>calls.push('checkpoint')};
 vm.runInNewContext(helpers,env);env.renderRecipeReview=()=>env.mountRecipeEditor(state.review);
 return {env,state,calls,nodes,classes};
}
test('Recipe mounts the actual shared editor, preserving parameters, variables and unsaved edits on same-revision redraw',()=>{
 const {env,state,calls,nodes,classes}=harness();env.mountRecipeEditor(state.review);
 assert.ok(classes.has('agent-recipe-editing'));assert.equal(nodes.get('#agent-review-steps').child,nodes.get('#agent-build-panel'));
 assert.equal(state.draft.source.inputs.properties.query.type,'string');assert.equal(state.draft.source.variables.properties.index.default,0);
 state.draft.source.steps[0].name='edited';env.mountRecipeEditor(state.review);
 assert.equal(state.draft.source.steps[0].name,'edited');assert.equal(calls.filter(x=>x==='render').length,1);
});
test('saving edited Recipe sends complete Source with optimistic revision and invalidates approval',async()=>{
 const {env,state,calls}=harness();env.mountRecipeEditor(state.review);state.draft.source.steps[0].name='edited';
 env.api=async(path,options)=>{assert.equal(path,'/agent-recipes/recipe/source');assert.equal(options.method,'PATCH');const body=JSON.parse(options.body);assert.equal(body.expected_revision,1);assert.equal(body.source.variables.properties.index.default,0);return {recipe:{id:'recipe',status:'draft'},review:{...state.review,source:body.source,source_revision:2,status:'awaiting_review'}};};
 await env.saveRecipeEditor();assert.equal(state.review.source_revision,2);assert.equal(state.review.status,'awaiting_review');assert.equal(state.draft.source.steps[0].name,'edited');assert.ok(calls.includes('checkpoint'));
});
test('Recipe trial uses shared editor inputs after saving edits and participates in Shell return flow',async()=>{
 const code=source.slice(source.indexOf('    async function runRecipe()'),source.indexOf('    async function commitRecipe('));
 const events=[],state={recipe:{id:'recipe'},context:{bidi_context:'tab',url:'https://example.com'}};
 const env={state,URL,location:{href:'https://local/?workspace_editor=1'},encodeURIComponent,JSON,saveRecipeEditor:async()=>events.push('save'),ensureWorkspaceBrowserContext:async()=>events.push('context'),currentCapability:()=>({inputs:{properties:{query:{type:'string'}}}}),$:key=>key,readInputFields:(element)=>{assert.equal(element,'#agent-build-inputs');return {query:'watch'};},api:async(path,options)=>{events.push('run');assert.equal(JSON.parse(options.body).input.query,'watch');return {id:'run'};},renderRun(){},notice(){},tr:x=>x,driveRun:async()=>events.push('drive')};
 vm.runInNewContext(code,env);await env.runRecipe();assert.deepEqual(events,['save','context','run','drive']);assert.equal(state.workspaceTestRunId,'run');
});
test('review redraw keeps the shared editor connected across AI revisions and same-version refreshes',()=>{
 const {env,state,nodes,calls}=harness();
 const editor=env.$('#agent-build-panel'),list=env.$('#agent-review-steps');
 editor.connected=true;
 list.append=child=>{assert.ok(child,'editor must still be queryable');list.child=child;child.connected=true;};
 list.replaceChildren=()=>{if(list.child)list.child.connected=false;list.child=null;};
 const lookup=env.$;
 env.$=key=>key==='#agent-build-panel'&&!editor.connected?null:lookup(key);
 for(const key of ['#agent-review-status','#agent-recipe-inputs'])lookup(key).dataset={};
 lookup('#agent-recipe-inputs').closest=()=>({hidden:false});
 env.tr=x=>x;env.statusText=x=>x;
 vm.runInNewContext(source.slice(source.indexOf('    function renderRecipeReview('),source.indexOf('    async function loadRecipeReview(')),env);
 env.renderRecipeReview();assert.equal(list.child,editor);
 state.review={...state.review,source_revision:2,source:{...state.review.source,steps:[{name:'open'},{name:'extract'}]}};
 env.renderRecipeReview();assert.equal(list.child,editor);assert.equal(state.draft.source.steps.length,2);
 state.draft.source.steps[0].name='unsaved';env.renderRecipeReview();
 assert.equal(state.draft.source.steps[0].name,'unsaved');assert.equal(calls.filter(x=>x==='render').length,2);
});
test('Recipe dispatch receipt is hydrated before execution and retry resumes the same run',async()=>{
 const code=source.slice(source.indexOf('    async function runRecipe()'),source.indexOf('    async function commitRecipe('));
 const state={recipe:{id:'recipe'},context:{bidi_context:'tab',profile_key:'test-profile'}},events=[];
 let posts=0;
 const env={state,URL,location:{href:'https://local/?workspace_editor=1'},encodeURIComponent,JSON,
 saveRecipeEditor:async()=>{},ensureWorkspaceBrowserContext:async()=>{},currentCapability:()=>({inputs:{}}),$:x=>x,readInputFields:()=>({}),
 api:async(path,opts)=>{events.push(path);if(opts){posts++;assert.equal(JSON.parse(opts.body).browser_context.profile_key,'test-profile');return {run_id:'run',status:'queued'};}assert.equal(path,'/agent-draft-runs/run');return {id:'run',status:'waiting_input'};},
 renderRun:r=>{assert.equal(r.id,'run');state.run=r;},notice(){},tr:x=>x,driveRun:async resume=>events.push(resume?'resume':'drive')};
 vm.runInNewContext(code,env);await env.runRecipe();await env.runRecipe();
 assert.equal(posts,1);assert.equal(state.workspaceTestRunId,'run');assert.equal(events.at(-1),'resume');
});

test('unchanged normalized editor preserves approval on commit preparation and object key reorder',async()=>{
 const {env,state}=harness();
 // Simulate the real form adding execution/target defaults to raw exploration Source.
 env.editorSource=()=>({...state.draft.source,steps:state.draft.source.steps.map(step=>({
   target:{},execution:{mode:'adaptive'},...step})),variables:{properties:{},type:'object'}});
 env.syncEditor=()=>{state.draft.source=env.editorSource();};
 state.review.status='approved';env.mountRecipeEditor(state.review);
 let patches=0;env.api=async()=>{patches++;throw Error('unchanged editor must not save');};
 await env.saveRecipeEditor();
 // The server serializes dictionaries in sorted order; the form need not.
 state.draft.source=JSON.parse(JSON.stringify(state.draft.source,(key,value)=>value));
 state.draft.source.steps[0]={name:'read',execution:{mode:'adaptive'},target:{}};
 await env.saveRecipeEditor();
 assert.equal(patches,0);assert.equal(state.review.status,'approved');assert.equal(state.review.source_revision,1);
});

test('approved normalized Recipe commits without creating an unapproved source revision',async()=>{
 const {env,state}=harness();state.review.status='approved';
 env.editorSource=()=>({...state.draft.source,variables:{type:'object',properties:{}},steps:[{name:'read',target:{}}]});
 env.syncEditor=()=>{state.draft.source=env.editorSource();};env.mountRecipeEditor(state.review);
 const requests=[];env.api=async(path)=>{requests.push(path);assert.equal(path,'/agent-recipes/recipe/commit');return {site_agent:{id:'draft'},recipe:{committed_capability_id:'list'}};};
 Object.assign(env,{rememberRecipe(){},renderRecipeReview(){},setContextPinned(){},refreshDrafts:async()=>{},
 loadEditorCompilation:async()=>{state.compiledDraft=null;},switchMode(){},notice(){},tr:x=>x});
 vm.runInNewContext(source.slice(source.indexOf('    async function commitRecipe('),source.indexOf('    function bind()')),env);
 await env.commitRecipe('merge');assert.equal(requests.length,1);assert.equal(state.draft.id,'draft');assert.equal(state.recipe,null);
});
