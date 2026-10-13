"""Shared Local WebAgent submission for trusted AI2Apps applications.

Applications submit work here; they never own a browser connection or execution
loop. BrowserTaskRepository is the single concurrency/admission authority.
"""
from .tasks import BrowserTaskRepository
from ai2apps.agent_builder.compiler import compile_source


class WebAgentInvocation:
    def __init__(self, runtime):
        self.runtime = runtime
        self.tasks = BrowserTaskRepository(runtime.database, runtime.events)

    def submit(self, *, owner, session_id, profile='default', name, key,
               caller_app_id, agent_id='', capability='', generation_id='',
               parameters=None, source=None, retain_pages_reason='', parent_task_id='', reuse_page=False, model_profile=None, parallel_limit=1):
        from ai2apps.api.ownership import authorize_session
        from ai2apps.identity import IdentityRepository
        principal = IdentityRepository(self.runtime.database).local_principal_for(owner)
        authorize_session(self.runtime, principal, session_id)
        program = None
        declared_model_profile = "normal"
        if source is not None:
            compiled = compile_source(source)
            if not compiled.valid:
                import json
                raise ValueError('WebAgent program failed compilation preflight: ' + json.dumps(compiled.report['errors'])[:800])
            program = compiled.ir
            declared_model_profile = program.get("model_profile", "normal")
        elif agent_id.startswith('builtin:web:'):
            from ai2apps.agent_builder.foundations import foundation_ir, GENERATION
            foundation_ir(agent_id, capability, generation_id or GENERATION)
            generation_id = generation_id or GENERATION
            program = compile_source({'agent_type':'web', 'steps':[{
                'name':'call', 'operation':'agent.call', 'desc':name,
                'arguments':{'agent_id':agent_id, 'capability':capability,
                    'generation_id':generation_id, 'parameters':parameters or {}},
                'on':{'success':'done','failed':'failed'}}]}).ir
        else:
            repository = self.runtime.agent_builder
            generation = repository.get_generation(generation_id, owner)
            if generation.draft_id != agent_id or generation.status.value != 'active':
                raise ValueError('WebAgent generation is not active for this owner')
            from ai2apps.agent_builder.service import capability_ir
            declared_model_profile = capability_ir(generation.ir, capability or None).get('model_profile', 'normal')
            if not capability:
                exports = generation.ir.get('capability_exports') or []
                if len(exports) > 1:
                    raise ValueError('Select an explicit WebAgent capability')
                capability = exports[0]['name'] if exports else f'agent.{agent_id}.run'
        model_profile = model_profile or declared_model_profile
        if declared_model_profile == 'privacy':
            model_profile = 'privacy'
        if model_profile not in {'normal', 'privacy'}:
            raise ValueError('Unknown model profile')
        if parent_task_id.startswith("btask_"):
            parent = self.tasks.get(owner, parent_task_id)
            if parent.get('browser_context', {}).get('model_profile') == 'privacy':
                model_profile = 'privacy'
        return self.tasks.enqueue(owner, profile, agent_id, capability, generation_id,
            name, parameters or {}, session_id=session_id, idempotency_key=key,
            program=program, caller_app_id=caller_app_id, retain_pages_reason=retain_pages_reason, parent_task_id=parent_task_id, reuse_page=reuse_page, model_profile=model_profile, parallel_limit=parallel_limit)
