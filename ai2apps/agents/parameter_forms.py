"""Trusted, Run-owned parameter form descriptors shared by Apps and Mini-Apps."""
from dataclasses import dataclass, replace
from typing import Callable
from jsonschema import Draft202012Validator
from .models import InteractionAction, InteractionKind, InteractionStatus

FORM_TOOL = 'app.collect_parameters'

@dataclass(frozen=True)
class ParameterForm:
    key: str
    app_id: str
    schema: dict
    fields: tuple = ()
    mini_app_id: str | None = None
    version: int = 1
    capability: str | None = None
    mode: str = 'configure'
    describe: Callable | None = None
    prepare_values: Callable | None = None
    validate: Callable | None = None
    complete: Callable | None = None
    priority: int = 0
    provider_version: str | None = None
    prompt: dict | str = '填写参数 / Complete parameters'
    related_capabilities: tuple = ()
    switch_values: Callable | None = None
    continuation: str | None = None
    display_name: dict | str | None = None
    summary: dict | str | None = None
    agent_context: dict | None = None


FORMS = {}
def register_form(form):
    if form.key in FORMS: raise ValueError('Form already registered')
    from ai2apps.services.aaat import validate_declaration
    form=replace(form,agent_context=validate_declaration(form.agent_context))
    Draft202012Validator.check_schema(form.schema)
    if not form.fields: form=replace(form,fields=tuple(schema_fields(form.schema)))
    if {f['key'] for f in form.fields} != set(form.schema['properties']): raise ValueError('Fields and schema disagree')
    if any(f['type'] not in {'text','number','boolean','select','asset','model','json'} for f in form.fields): raise ValueError('Unsupported field')
    if form.mode not in {'configure', 'execute'}: raise ValueError('Invalid completion mode')
    if form.mode == 'execute' and not form.complete: raise ValueError('Execution callback required')
    FORMS[form.key] = form


def resolve_form(arguments, pinned=None, database=None, scope=None):
    capability=arguments['capability']
    provider=pinned or arguments.get('provider')
    candidates=[f for f in FORMS.values() if (f.capability or f.key)==capability or f.key==capability]
    if provider: candidates=[f for f in candidates if f.key==provider]
    if database is not None and scope is not None:
        with database.transaction() as db:
            disabled={r['provider'] for r in db.execute('SELECT provider FROM capability_provider_settings WHERE actor=? AND installation=? AND enabled=0',(scope.actor_user_id,scope.installation_id))}
        candidates=[f for f in candidates if f.key not in disabled]
    if not candidates: raise ValueError('No registered parameter declaration for '+capability)
    health={}
    if database is not None and scope is not None and not pinned:
        import time
        with database.transaction() as db:
            rows=db.execute('SELECT * FROM capability_provider_health WHERE actor=? AND installation=? AND capability=?',
                (scope.actor_user_id,scope.installation_id,capability)).fetchall()
        health={(r['provider'],r['version']):dict(r) for r in rows}
        candidates=[f for f in candidates if health.get((f.key,f.provider_version),{}).get('unavailable_until',0)<=time.time()]
        if not candidates: raise ValueError('No available parameter provider')
    return sorted(candidates,key=lambda f:(-health.get((f.key,f.provider_version),{}).get('success_at',0),-f.priority,f.key))[0]

def schema_fields(schema):
    fields=[]
    for key, spec in schema.get('properties',{}).items():
        field={'key':key,'label':spec.get('title',key),'type':'select' if 'enum' in spec else {'integer':'number','number':'number','boolean':'boolean','object':'json','array':'json'}.get(spec.get('type'),'text')}
        asset = spec.get('x-ai2apps-asset') or spec.get('items', {}).get('x-ai2apps-asset')
        if asset:
            field.update(type='asset', storage=asset.get('storage','artifact'), accept=asset.get('accept',''), references=bool(asset.get('references')),
                multiple=spec.get('type')=='array', minItems=spec.get('minItems',0), maxItems=spec.get('maxItems',20 if spec.get('type')=='array' else 1))
        if 'enum' in spec: field['options']=[{'value':v,'label':str(v)} for v in spec['enum']]
        if 'default' in spec: field['default']=spec['default']
        fields.append(field)
    return fields

def present_fields(fields, labels=None, option_labels=None):
    """Apply owner-supplied presentation without changing parameter identities."""
    from copy import deepcopy
    result=deepcopy(list(fields))
    for field in result:
        key=field['key']
        if key in (labels or {}):field['label']=labels[key]
        for option in field.get('options',[]):
            if option['value'] in (option_labels or {}).get(key,{}):
                option['label']=option_labels[key][option['value']]
    return result


def required_fields(schema, values):
    """Top-level required fields for the current conditional schema branch."""
    keys=set(schema.get('required',[]))
    for branch in schema.get('allOf',[]):keys.update(required_fields(branch,values))
    if 'if' in schema:
        branch=schema.get('then' if Draft202012Validator(schema['if']).is_valid(values) else 'else',{})
        keys.update(required_fields(branch,values))
    for key, dependencies in schema.get('dependentRequired',{}).items():
        if key in values:keys.update(dependencies)
    for key, branch in schema.get('dependentSchemas',{}).items():
        if key in values:keys.update(required_fields(branch,values))
    return sorted(keys)


def diagnostics(schema, values):
    required=required_fields(schema,values)
    missing=[key for key in required if key not in values]
    invalid=[{'field':'.'.join(map(str,e.path)), 'message':e.message} for e in Draft202012Validator(schema).iter_errors(values) if e.validator!='required' or e.path]
    return {'required_fields':required,'missing':missing,'invalid':invalid}


def tool_schema():
    return {'type':'object','properties':{'request_id':{'type':'string','minLength':1,'maxLength':128},'capability':{'type':'string','minLength':1,'maxLength':256},'provider':{'type':'string','minLength':1,'maxLength':256},'values':{'type':'object'},'initial_values':{'type':'object'}},'required':['request_id','capability'],'not':{'required':['values','initial_values']},'additionalProperties':False}


def confirmed_form_invocation(context, form, arguments, database, call_id):
    """Reuse a Run-owned exact confirmation, never model-supplied confirmation flags.

    A durable claim binds a receipt to the scheduler's original invocation key.
    A receipt already claimed by another invocation cannot authorize a new call.
    Owner-specific invocation policies remain authoritative and use their own path.
    """
    import json
    from .form_continuation import selected_form
    from ai2apps.core import RepositoryError
    capability=form.capability or form.key
    candidates=[i for i in context.interactions if i.run_id==context.run.id and
        i.request.get('control')=='parameter_form' and i.request.get('capability')==capability]
    if not candidates:return None
    item=max(candidates,key=lambda i:i.created_at)
    result=(item.response or {}).get('result',{})
    if item.status is not InteractionStatus.SUBMITTED or (item.response or {}).get('status')!='completed':return None
    if not result.get('user_confirmed') or not result.get('configure_only') or result.get('executed_in_app'):return None
    if result.get('capability')!=capability or result.get('provider')!=form.key:return None
    try:selected=selected_form(database,item)
    except (RepositoryError,ValueError):return None
    if (selected.key,selected.version,selected.provider_version)!=(form.key,form.version,form.provider_version):return None
    if arguments.get('provider',form.key)!=form.key:return None
    def payload(value):
        value=dict(value)
        nested=value.pop('parameters',{})
        value.pop('provider',None)
        if not isinstance(nested,dict):return None
        value.update(nested)
        return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))
    if payload(arguments)!=payload(result.get('arguments',{})):return None
    with database.transaction() as db:
        claim=db.execute('SELECT call_id FROM agent_parameter_invocations WHERE interaction_id=?',(item.id,)).fetchone()
    if claim and claim['call_id']!=call_id and not rejected_before_dispatch(database,item.id,claim['call_id']):return None
    return item.id


def rejected_before_dispatch(database, interaction_id, call_id):
    """A proven parameter rejection does not consume execution consent."""
    import json
    with database.transaction() as db:
        step=db.execute('SELECT s.status,s.error_json FROM run_steps s JOIN agent_interactions i ON i.run_id=s.run_id WHERE i.id=? AND s.action_key=?', (interaction_id,call_id)).fetchone()
    if not step or step['status']!='failed':return False
    error=json.loads(step['error_json'] or '{}')
    return error.get('code')=='invalid_tool_arguments' and error.get('phase')=='prepare'


def claim_form_invocation(database, interaction_id, call_id):
    """Atomic single-invocation consumption; replay of the same action is safe."""
    # Reserve the writer before reading: concurrent deferred readers cannot all
    # upgrade to writers, even with SQLite's busy timeout.
    with database.transaction(write=True) as db:
        previous=db.execute('SELECT call_id FROM agent_parameter_invocations WHERE interaction_id=?',(interaction_id,)).fetchone()
        if previous and previous['call_id']!=call_id and rejected_before_dispatch(database,interaction_id,previous['call_id']):
            db.execute('UPDATE agent_parameter_invocations SET call_id=? WHERE interaction_id=? AND call_id=?',(call_id,interaction_id,previous['call_id']))
        db.execute('INSERT OR IGNORE INTO agent_parameter_invocations(interaction_id,call_id) VALUES (?,?)',(interaction_id,call_id))
        return db.execute('SELECT call_id FROM agent_parameter_invocations WHERE interaction_id=?',(interaction_id,)).fetchone()['call_id']==call_id

def form_action(context, arguments, *, database=None, scope=None):
    Draft202012Validator(tool_schema()).validate(arguments)
    prior=context.interaction('form:'+arguments['request_id'])
    form=resolve_form(arguments,prior.ui_hints.get('provider') if prior else None,database,scope)
    if 'values' in arguments and 'initial_values' in arguments: raise ValueError('Use values or initial_values, not both')
    request={'control':'parameter_form','version':form.version,**arguments}
    existing=context.interaction('form:'+arguments['request_id'])
    if existing:
        if existing.request != request: raise ValueError('Form request changed')
        if existing.status is InteractionStatus.SUBMITTED:return None
        if existing.status is not InteractionStatus.PENDING:raise ValueError('Form is closed')
    prompt_labels=(form.prompt if isinstance(form.prompt,dict) else None)
    if form.prompt=='填写参数 / Complete parameters':
        prompt_labels={'zh':'准备调用','en':'Prepare call'} if form.describe and not form.schema.get('properties') else {'zh':'补充调用参数','en':'Complete call parameters'} if diagnostics(form.schema,arguments.get('values',arguments.get('initial_values',{})))['missing'] else {'zh':'确认调用参数','en':'Confirm call parameters'}
    return InteractionAction(request_key='form:'+arguments['request_id'],kind=InteractionKind.FORM,
        prompt=(prompt_labels.get('en','Complete parameters') if prompt_labels else form.prompt),request=request,
        response_schema={'type':'object','properties':{'status':{'enum':['completed','cancelled']},'result':{'type':'object'}},'required':['status','result'],'additionalProperties':False},
        ui_hints={'control':'parameter_form','prompt_labels':prompt_labels,'app_id':form.app_id,'mini_app_id':form.mini_app_id,'provider':form.key,'provider_version':form.provider_version})

def install_parameter_forms(agents,services,registry,*,service_id,provider_key,capability_router=None):
    with agents.database.transaction() as db:
        db.execute('CREATE TABLE IF NOT EXISTS agent_parameter_drafts (interaction_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, values_json TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS agent_parameter_choices (interaction_id TEXT PRIMARY KEY, provider TEXT NOT NULL, version INTEGER NOT NULL, app_id TEXT NOT NULL, mini_app_id TEXT, provider_version TEXT, drafts_json TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS agent_parameter_handoffs (interaction_id TEXT PRIMARY KEY, provider TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL, studio_run_id TEXT, app_instance_id TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS agent_parameter_invocations (interaction_id TEXT PRIMARY KEY, call_id TEXT NOT NULL)')
    def result(arguments,context):
        from ai2apps.services import ToolProviderError
        run=agents.get_run(context.trace_id)
        if run.session_id!=context.session_id:raise ToolProviderError('Session mismatch')
        item=next((i for i in agents.list_interactions(run.id) if i.request_key=='form:'+arguments['request_id']),None)
        if not item or item.status is not InteractionStatus.SUBMITTED or item.request!={'control':'parameter_form','version':resolve_form(arguments, item.ui_hints.get('provider') if item else None).version,**arguments}:raise ToolProviderError('Complete the form first')
        return item.response
    services.ensure_tool(service_id=service_id,qualified_name=FORM_TOOL,display_name='App parameter form',description='Collect missing or invalid parameters for a registered capability in a durable Chat form. Pass capability as a string, optional provider and known values. The selected App or Mini-App declaration supplies fields, defaults, model constraints and completion behavior. A completed form has already been submitted by the user; do not ask them to confirm the same parameters again. Before requesting a form, briefly explain which App/Mini-App you will call and which inputs need completion or confirmation. Configure-only results contain the exact user-confirmed arguments to pass unchanged to the returned provider; do not add optional fields or substitute defaults after confirmation; changed arguments require fresh confirmation; execution results contain the completed operation result. Cancellation is not success.',input_schema=tool_schema(),output_schema={'type':'object'},effects=(),timeout_ms=10000)
    registry.bind_tool(FORM_TOOL,provider_key=provider_key,handler=result)
    def catalog(arguments,context):
        from .app_interactions import CAPABILITIES
        capability=arguments.get('capability')
        forms=[{'capability':f.capability or f.key,'provider':f.key,'app_id':f.app_id,'mini_app_id':f.mini_app_id,
            'display_name':f.display_name,'summary':f.summary,'agent_context':f.agent_context,
            'mode':f.mode,'schema':f.schema,'dynamic':bool(f.describe),'fields':f.fields} for f in FORMS.values()
            if not capability or capability in (f.capability,f.key)]
        handoffs=[{'capability':d.key,'app_id':d.app_id,'mini_app_id':d.mini_app_id,'schema':d.parameter_schema,'mode':'handoff','agent_context':d.agent_context}
            for d in CAPABILITIES.values() if not capability or capability==d.key]
        providers=[]
        if capability_router is not None:
            providers=[p for p in capability_router.inspect(context.actor_user_id,context.installation_id)
                if not capability or capability in (p['capability'],p['id'])]
        if not capability:
            # Discovery is a brief inventory. Full declarations are selection scoped.
            for item in [*forms,*handoffs,*providers]:
                item['has_agent_context']=bool(item.pop('agent_context',None))
        return {'forms':forms,'interactions':handoffs,'providers':providers}
    services.ensure_tool(service_id=service_id,qualified_name='app.describe',display_name='Discover App interactions',
        description='Discover registered App and Mini-App capability strings, providers and parameter declarations. Optional capability filters results. Use app.collect_parameters for forms or app.interact for handoffs. Dynamic schemas are resolved by the selected provider when opening the form.',
        input_schema={'type':'object','properties':{'capability':{'type':'string'}},'additionalProperties':False},output_schema={'type':'object'},effects=(),timeout_ms=10000)
    registry.bind_tool('app.describe',provider_key=provider_key,handler=catalog)

