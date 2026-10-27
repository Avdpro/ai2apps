"""Trusted capability providers with owner-scoped health and success preferences.

Only an explicit pre-execution Unavailable permits fallback. Timeout, rejection,
validation and unknown execution failures propagate: another provider could bill
or bypass a user's decision. Register adapters at startup, never from model JSON.
"""
from dataclasses import dataclass
from copy import deepcopy
import time
from typing import Callable
from ai2apps.services import ToolProviderError


class CapabilityInvocationError(ToolProviderError):
    def __init__(self, code, message, details):
        self.code, self.details, self.retryable = code, details, False
        super().__init__(message)


class ProviderUnavailable(ToolProviderError):
    """The adapter guarantees that no business operation was submitted."""


class ProviderIncompatible(ToolProviderError):
    """Preflight only: this request does not fit, without poisoning provider health."""


@dataclass(frozen=True)
class CapabilityProvider:
    id: str
    capability: str
    app_id: str
    handler: Callable
    mini_app_id: str | None = None
    priority: int = 0
    version: str = '1'
    describe: Callable | None = None
    prepare: Callable | None = None
    related_capabilities: tuple = ()
    switch_values: Callable | None = None
    continuation: str | None = None
    display_name: dict | str | None = None
    summary: dict | str | None = None
    agent_context: dict | None = None
    invocation_policy: Callable | None = None
    discovery_context: Callable | None = None


class CapabilityRouter:
    def __init__(self, database, *, clock=time.time, cooldown=300):
        self.database, self.clock, self.cooldown = database, clock, cooldown
        self.providers = {}
        self.execution_scope = None
        self.result_policies = {}
        with database.transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS capability_provider_settings (
                actor TEXT NOT NULL, installation TEXT NOT NULL, provider TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(actor,installation,provider))""")
            db.execute('''CREATE TABLE IF NOT EXISTS capability_provider_health (
                actor TEXT NOT NULL, installation TEXT NOT NULL, capability TEXT NOT NULL,
                provider TEXT NOT NULL, version TEXT NOT NULL, success_at REAL NOT NULL DEFAULT 0,
                unavailable_until REAL NOT NULL DEFAULT 0, reason TEXT NOT NULL DEFAULT '',
                PRIMARY KEY(actor,installation,capability,provider,version))''')

    def set_enabled(self, actor, installation, provider, enabled):
        if provider not in self.providers: raise ValueError('Unknown Provider')
        if not actor or not installation: raise ValueError('Provider settings require an actor and installation')
        with self.database.transaction() as db:
            db.execute("""INSERT INTO capability_provider_settings VALUES (?,?,?,?)
                ON CONFLICT(actor,installation,provider) DO UPDATE SET enabled=excluded.enabled""",
                (actor,installation,provider,int(enabled)))
        return {'provider':provider,'enabled':enabled}

    def disabled(self, actor, installation):
        with self.database.transaction() as db:
            return {r['provider'] for r in db.execute('SELECT provider FROM capability_provider_settings WHERE actor=? AND installation=? AND enabled=0',(actor,installation))}

    def register(self, provider):
        if provider.id in self.providers:
            raise ValueError('Duplicate capability provider')
        if not provider.app_id or not provider.capability or not callable(provider.handler):
            raise ValueError('Invalid capability provider')
        if provider.discovery_context is not None and not callable(provider.discovery_context):
            raise ValueError('Discovery Context requires a trusted callable adapter')
        from dataclasses import replace
        from .aaat import validate_declaration
        provider = replace(provider, agent_context=validate_declaration(provider.agent_context))
        from ai2apps.agents.provider_forms import register_provider_form
        register_provider_form(provider)
        self.providers[provider.id] = provider

    def unregister(self, identifier):
        """Revoke one runtime-owned Provider and its form; old receipts fail version guards."""
        provider = self.providers.pop(identifier, None)
        if provider is not None:
            from ai2apps.agents.parameter_forms import FORMS
            form = FORMS.get(identifier)
            if form and (form.app_id, form.mini_app_id, form.provider_version) == (provider.app_id, provider.mini_app_id, provider.version):
                FORMS.pop(identifier, None)
        return provider is not None

    def register_result_policy(self, policy):
        if policy.id in self.result_policies:raise ValueError('Duplicate App result policy')
        if not isinstance(policy.id,str) or not policy.id or len(policy.id)>128 or policy.id in {'content','message_id','usage','finish_reason','aaat_views'}:
            raise ValueError('Invalid App result policy identity')
        if not callable(policy.instruction) or not callable(policy.finalize) or (policy.preview is not None and not callable(policy.preview)):
            raise ValueError('App result policy requires trusted callbacks')
        if not policy.capabilities or not all(isinstance(n,str) and n and len(n)<=256 for n in policy.capabilities):
            raise ValueError('App result policy requires explicit capability scope')
        self.result_policies[policy.id]=policy

    def active_result_policies(self, steps):
        used={s.tool_name for s in steps if s.kind=='tool' and (getattr(s,'error',None) or {}).get('code')!='tool_declaration_required'}
        return [p for p in self.result_policies.values() if used.intersection(p.capabilities)]

    def project_result_views(self, steps):
        from .aaat import validate_view
        views={}
        for step in steps:
            if step.kind!='tool' or step.status.value!='completed' or not isinstance(step.output,dict):continue
            output=step.output
            provider=self.providers.get(output.get('provider'))
            if provider is None or provider.capability!=step.tool_name or 'aaat_view' not in output:continue
            from jsonschema import ValidationError
            try:view=validate_view(output['aaat_view'])
            except (ValidationError,ValueError):continue
            key=(provider.id,view['id'])
            views[key]={'view':view,'provider':provider.id,'provider_version':output.get('provider_version'),
                        'capability':step.tool_name,'step_id':step.id}
        return list(views.values())[-8:]

    def project_result_preview(self, step):
        return {p.id:value for p in self.active_result_policies((step,)) if p.preview is not None
            and (value:=p.preview(step)) is not None}

    def agent_contexts(self, tools, actor, installation, *, selected_capabilities=None, session_id=None):
        """Project trusted declarations only for available Tools and enabled Providers."""
        allowed={t.qualified_name for t in tools};disabled=self.disabled(actor,installation)
        groups={}
        import json
        for p in tuple(self.providers.values()):
            if self.execution_scope and not self.execution_scope.provider_visible(session_id, p):continue
            if p.capability not in allowed or p.id in disabled or not p.agent_context:continue
            if selected_capabilities is not None and p.capability not in selected_capabilities:continue
            key=(p.app_id,p.mini_app_id,json.dumps(p.agent_context,sort_keys=True))
            entry=groups.setdefault(key,{'app_id':p.app_id,'mini_app_id':p.mini_app_id,
                'trust':'trusted_app_declaration','declaration':deepcopy(p.agent_context),'providers':[]})
            entry['providers'].append({'id':p.id,'capability':p.capability,'version':p.version})
        return list(groups.values())

    def catalog(self):
        return [{'id': p.id, 'capability': p.capability, 'app_id': p.app_id,
                 'mini_app_id': p.mini_app_id, 'version': p.version,
                 'display_name': p.display_name, 'summary': p.summary,
                 'agent_context':deepcopy(p.agent_context), 'dynamic_discovery':bool(p.discovery_context)} for p in tuple(self.providers.values())]

    async def discovery_contexts(self, tools, scope, *, selected_capabilities=None):
        """Read bounded owner observations; never accept executable instructions.

        No cross-user cache: every observation is resolved under the current
        Session identity. Callbacks are registered host adapters, never model JSON.
        """
        import asyncio
        import inspect
        import json
        allowed = {tool.qualified_name for tool in tools if getattr(tool, 'enabled', True)}
        if not scope.actor_user_id or not scope.installation_id:
            return []
        disabled = self.disabled(scope.actor_user_id, scope.installation_id)
        result, seen, total = [], set(), 0
        deadline = asyncio.get_running_loop().time() + 2
        for provider in tuple(self.providers.values()):
            if self.execution_scope and not self.execution_scope.provider_visible(scope.session_id, provider):continue
            if (provider.capability not in allowed or provider.id in disabled or not provider.discovery_context
                    or (selected_capabilities is not None and provider.capability not in selected_capabilities)):
                continue
            key = (provider.app_id, provider.mini_app_id, id(provider.discovery_context))
            if key in seen:
                continue
            remaining = deadline - asyncio.get_running_loop().time()
            if len(seen) >= 8 or remaining <= 0:
                break
            seen.add(key)
            try:
                if inspect.iscoroutinefunction(provider.discovery_context):
                    value = await asyncio.wait_for(provider.discovery_context(scope), timeout=min(1, remaining))
                else:
                    value = await asyncio.wait_for(asyncio.to_thread(provider.discovery_context, scope), timeout=min(1, remaining))
                if not isinstance(value, dict):
                    raise ValueError('Discovery Context must be an object')
                encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
                size = len(encoded.encode())
                if size > 8192:
                    raise ValueError('Discovery Context exceeds 8 KiB')
                if total + size > 16384:
                    break
                total += size
                result.append({'provider': provider.id, 'provider_version': provider.version,
                               'app_id': provider.app_id, 'mini_app_id': provider.mini_app_id,
                               'observed_at': self.clock(), 'data_trust': 'untrusted', 'data': value})
            except asyncio.CancelledError:
                raise
            except Exception:
                # Failure details can contain private data or credentials.
                result.append({'provider': provider.id, 'provider_version': provider.version,
                               'app_id': provider.app_id, 'data_trust': 'untrusted', 'status': 'unavailable'})
        return result

    def inspect(self, actor, installation):
        with self.database.transaction() as db:
            rows = db.execute('SELECT * FROM capability_provider_health WHERE actor=? AND installation=?',
                              (actor, installation)).fetchall()
        health = {(r['capability'], r['provider'], r['version']): dict(r) for r in rows}
        disabled = self.disabled(actor, installation)
        result = []
        for capability in sorted({p.capability for p in tuple(self.providers.values())}):
            candidates = [p for p in tuple(self.providers.values()) if p.capability == capability]
            candidates.sort(key=lambda p: (health.get((capability,p.id,p.version),{}).get('success_at',0),p.priority), reverse=True)
            rank = 0
            for p in candidates:
                h = health.get((capability,p.id,p.version), {})
                remaining = max(0, h.get('unavailable_until', 0) - self.clock())
                enabled = p.id not in disabled
                if not remaining and enabled:
                    rank += 1
                result.append(dict(id=p.id, capability=capability, app_id=p.app_id,
                    mini_app_id=p.mini_app_id, priority=p.priority, version=p.version,
                    display_name=p.display_name, summary=p.summary, agent_context=deepcopy(p.agent_context),
                    rank=None if remaining or not enabled else rank, enabled=enabled, cooldown_seconds=round(remaining),
                    success_at=h.get('success_at', 0), reason=h.get('reason', ''),
                    status='disabled' if not enabled else 'cooldown' if remaining else 'registered', parameter_contract=bool(p.describe)))
        return result

    def invocation_error(self, capability, attempts, code, message):
        records = []
        for attempt in attempts:
            provider = self.providers.get(attempt['provider'])
            records.append({**attempt, 'app_id': provider.app_id if provider else None,
                'mini_app_id': provider.mini_app_id if provider else None,
                'phase': attempt.get('phase', 'prepare')})
        latest = records[-1] if records else {}
        return CapabilityInvocationError(code, message, {
            'capability': capability, 'provider_attempts': records,
            **{key: latest[key] for key in ('provider', 'app_id', 'mini_app_id', 'phase') if key in latest},
        })

    async def invoke(self, capability, arguments, context):
        if not context.actor_user_id or not context.installation_id:
            raise ToolProviderError('Capability invocation requires an actor and installation')
        if self.execution_scope:self.execution_scope.authorize(context,capability,arguments)
        scope = (context.actor_user_id, context.installation_id, capability)
        with self.database.transaction() as db:
            rows = db.execute('SELECT * FROM capability_provider_health WHERE actor=? AND installation=? AND capability=?', scope).fetchall()
        health = {(r['provider'], r['version']): dict(r) for r in rows}
        candidates = [p for p in tuple(self.providers.values()) if p.capability == capability
            and (not self.execution_scope or self.execution_scope.provider_visible(context.session_id, p))]
        candidates.sort(key=lambda p: (health.get((p.id,p.version),{}).get('success_at',0),p.priority), reverse=True)
        requested_provider = arguments.get('provider')
        if requested_provider:
            candidates = [p for p in candidates if p.id == requested_provider]
            if not candidates:
                raise CapabilityInvocationError('invalid_tool_arguments','Unknown Provider for capability',
                    {'phase':'prepare','capability':capability})
        payload = {k:v for k,v in arguments.items() if k not in ('provider','parameters')}
        extras = arguments.get('parameters',{})
        if not isinstance(extras,dict):
            raise CapabilityInvocationError('invalid_tool_arguments','Provider parameters must be an object; no operation was submitted',
                {'phase':'prepare','capability':capability})
        conflicts=set(extras) & (set(payload) | {'provider','parameters'})
        if conflicts:
            raise CapabilityInvocationError('invalid_tool_arguments',
                'Provider parameters conflict with common arguments: '+', '.join(sorted(conflicts))+'. Supply each field in exactly one location; no operation was submitted',
                {'phase':'prepare','capability':capability,'conflicting_fields':sorted(conflicts)})
        payload = {**payload, **extras}
        disabled=self.disabled(context.actor_user_id, context.installation_id)
        attempts=[]
        for provider in candidates:
            if provider.id in disabled:
                attempts.append({'provider':provider.id,'status':'disabled'});continue
            if health.get((provider.id,provider.version),{}).get('unavailable_until',0)>self.clock():
                attempts.append({'provider':provider.id,'status':'cooldown'});continue
            await context.report_progress('Using '+provider.id, progress=0.05, content={
                'provider': provider.id, 'app_id': provider.app_id, 'mini_app_id': provider.mini_app_id,
            })
            phase = 'prepare'
            try:
                try:
                    prepared = await provider.prepare(deepcopy(payload), context) if provider.prepare else deepcopy(payload)
                except ProviderIncompatible as error:
                    attempts.append({'provider':provider.id,'status':'incompatible','reason':str(error)[:500]})
                    continue
                if self.providers.get(provider.id) is not provider:
                    attempts.append({'provider':provider.id,'status':'unavailable','reason':'Provider registration changed before submission'});continue
                if provider.id in self.disabled(context.actor_user_id,context.installation_id):
                    attempts.append({'provider':provider.id,'status':'disabled'});continue
                phase = 'execute'
                result=await provider.handler(prepared,context)
                if isinstance(result,dict) and 'aaat_view' in result:
                    from .aaat import validate_view
                    from jsonschema import ValidationError
                    try:validate_view(result['aaat_view'])
                    except (ValidationError,ValueError) as error:
                        # Presentation rejection must not turn an executed operation
                        # into a retryable business failure. Keep the original result.
                        result={k:v for k,v in result.items() if k!='aaat_view'}
                        result['aaat_view_error']={'code':'invalid_result_view','message':str(error)[:500]}
                if isinstance(result,dict) and 'aaat_context' in result:
                    from .aaat import validate_result
                    validate_result(result['aaat_context'],provider,self.providers)
            except ProviderUnavailable as error:
                with self.database.transaction() as db:
                    db.execute('''INSERT INTO capability_provider_health(actor,installation,capability,provider,version,unavailable_until,reason)
                        VALUES (?,?,?,?,?,?,?) ON CONFLICT(actor,installation,capability,provider,version)
                        DO UPDATE SET unavailable_until=excluded.unavailable_until,reason=excluded.reason''',
                        (*scope,provider.id,provider.version,self.clock()+self.cooldown,str(error)[:500]))
                attempts.append({'provider':provider.id,'status':'unavailable','reason':str(error)[:500]})
                continue
            except Exception as error:
                attempts.append({'provider': provider.id, 'status': 'failed', 'phase': phase, 'reason': str(error)[:500]})
                from jsonschema import ValidationError
                code=('invalid_tool_arguments' if phase=='prepare' and isinstance(error,ValidationError)
                      else 'tool_timeout' if isinstance(error,TimeoutError) else 'provider_error')
                raise self.invocation_error(capability, attempts, code, str(error)) from error
            with self.database.transaction() as db:
                db.execute('''INSERT INTO capability_provider_health(actor,installation,capability,provider,version,success_at)
                    VALUES (?,?,?,?,?,?) ON CONFLICT(actor,installation,capability,provider,version)
                    DO UPDATE SET success_at=excluded.success_at,unavailable_until=0,reason='' ''',
                    (*scope,provider.id,provider.version,self.clock()))
            return {**result,'capability':capability,'provider':provider.id,'provider_version':provider.version,
                'provider_attempts':attempts+[{'provider':provider.id,'status':'succeeded'}]}
        incompatible = any(attempt['status'] == 'incompatible' for attempt in attempts)
        message = ('Provider parameter validation failed for ' if incompatible else 'No available provider for ') + capability
        reasons = '; '.join(attempt['provider'] + ': ' + attempt.get('reason', attempt['status']) for attempt in attempts)
        raise self.invocation_error(capability, attempts, 'provider_incompatible' if incompatible else 'provider_unavailable', message + ('; ' + reasons if reasons else ''))
