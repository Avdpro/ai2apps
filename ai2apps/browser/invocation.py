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
               parameters=None, source=None):
        from ai2apps.api.ownership import authorize_session
        from ai2apps.identity import IdentityRepository
        principal = IdentityRepository(self.runtime.database).local_principal_for(owner)
        authorize_session(self.runtime, principal, session_id)
        program = None
        if source is not None:
            compiled = compile_source(source)
            if not compiled.valid:
                raise ValueError('WebAgent program failed compilation preflight')
            program = compiled.ir
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
            if not capability:
                exports = generation.ir.get('capability_exports') or []
                if len(exports) > 1:
                    raise ValueError('Select an explicit WebAgent capability')
                capability = exports[0]['name'] if exports else f'agent.{agent_id}.run'
        return self.tasks.enqueue(owner, profile, agent_id, capability, generation_id,
            name, parameters or {}, session_id=session_id, idempotency_key=key,
            program=program, caller_app_id=caller_app_id)
