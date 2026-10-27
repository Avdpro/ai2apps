"""Durable, registered App/Mini-App interactions owned by the invoking Run.

Targets are trusted adapters, never model-provided URLs. A Mini-App adapter uses
app_id for its host and mini_app_id for the installed entry within that host.
"""
from dataclasses import dataclass, replace
from datetime import datetime, UTC
from jsonschema import Draft202012Validator, ValidationError
from ai2apps.core import ResourceConflictError, ResourceNotFoundError
from ai2apps.services import ToolProviderError
from .models import InteractionAction, InteractionKind, InteractionStatus

APP_INTERACT = 'app.interact'

@dataclass(frozen=True)
class InteractionCapability:
    key: str
    app_id: str
    parameter_schema: dict
    mini_app_id: str | None = None
    version: int = 1
    prompt: dict | str | None = None
    agent_context: dict | None = None

CAPABILITIES = {}
SCHEMA = {
    'type': 'object', 'properties': {
        'request_id': {'type': 'string', 'minLength': 1, 'maxLength': 128},
        'capability': {'type':'string','minLength':1,'maxLength':256},
        'parameters': {'type': 'object'},
    }, 'required': ['request_id', 'capability', 'parameters'], 'additionalProperties': False,
}
RESULT_SCHEMA = {
    'type': 'object', 'properties': {
        'status': {'enum': ['completed', 'cancelled']},
        'result': {'type': 'object'},
    }, 'required': ['status', 'result'], 'additionalProperties': False,
}


def register_capability(descriptor):
    """Trusted host/Package adapter registration, before installing the Tool catalog.

    Mini-Apps declare their owning host App as app_id. The host consumes
    appInteraction.miniAppId and mounts the declared entry using its normal
    authenticated mount broker; no URL or mount credentials come from the model.
    """
    if descriptor.key in CAPABILITIES:
        raise ValueError('App interaction capability is already registered')
    if not descriptor.app_id or '/' in descriptor.app_id or (descriptor.mini_app_id and '/' in descriptor.mini_app_id):
        raise ValueError('Expected installed App/Mini-App identifiers, not URLs')
    Draft202012Validator.check_schema(descriptor.parameter_schema)
    from ai2apps.services.aaat import validate_declaration
    descriptor=replace(descriptor,agent_context=validate_declaration(descriptor.agent_context))
    CAPABILITIES[descriptor.key] = descriptor


def tool_schema():
    return SCHEMA


def interaction_action(context, arguments):
    Draft202012Validator(tool_schema()).validate(arguments)
    capability = CAPABILITIES.get(arguments['capability'])
    if capability is None: raise ValidationError('Unregistered App interaction capability')
    Draft202012Validator(capability.parameter_schema).validate(arguments['parameters'])
    request = {'control': 'app_handoff', 'version': capability.version, **arguments}
    existing = context.interaction('app:' + arguments['request_id'])
    if existing:
        if existing.request != request:
            raise ValueError('request_id already belongs to another App interaction')
        if existing.status is InteractionStatus.SUBMITTED:
            return None
        if existing.status is not InteractionStatus.PENDING:
            raise ValueError('App interaction is no longer pending')
    labels=capability.prompt if isinstance(capability.prompt,dict) else ({'zh':'请在目标应用完成操作，然后返回继续任务。','en':'Complete the action in the target App, then return.'} if capability.prompt is None else None)
    return InteractionAction(
        request_key='app:' + arguments['request_id'], kind=InteractionKind.FORM,
        prompt=labels.get('en','Complete the action in the target App, then return.') if labels else capability.prompt,
        response_schema=RESULT_SCHEMA,
        ui_hints={'control': 'app_handoff', 'prompt_labels':labels,'app_id': capability.app_id,
                  'mini_app_id': capability.mini_app_id}, request=request,
    )


def require_handoff(agents, run_id, interaction_id, *, capability=None):
    run = agents.get_run(run_id)
    item = next((i for i in agents.list_interactions(run_id) if i.id == interaction_id), None)
    if not item or item.request.get('control') != 'app_handoff':
        raise ResourceNotFoundError('app_interaction', interaction_id)
    descriptor = CAPABILITIES.get(item.request.get('capability'))
    if not descriptor or item.request.get('version') != descriptor.version:
        raise ResourceConflictError('App interaction adapter is unavailable')
    if item.ui_hints.get('app_id') != descriptor.app_id or item.ui_hints.get('mini_app_id') != descriptor.mini_app_id:
        raise ResourceConflictError('App interaction target has changed')
    if capability and descriptor.key != capability:
        raise ResourceConflictError('App interaction target does not match')
    if item.status is InteractionStatus.PENDING and item.deadline_at <= datetime.now(UTC):
        raise ResourceConflictError('App interaction has expired')
    if item.status is InteractionStatus.PENDING and run.status.value != 'waiting_input':
        raise ResourceConflictError('Origin Run is no longer waiting for this interaction')
    return run, item, descriptor


def install_app_interactions(agents, services, registry, *, service_id, provider_key):
    def result(arguments, context):
        if not context.trace_id or not context.session_id:
            raise ToolProviderError('App interaction requires an Agent Run')
        run = agents.get_run(context.trace_id)
        if run.session_id != context.session_id:
            raise ToolProviderError('Origin Session mismatch')
        item = next((i for i in agents.list_interactions(run.id)
                     if i.request_key == 'app:' + arguments['request_id']), None)
        if not item or item.status is not InteractionStatus.SUBMITTED or item.request != {
            'control': 'app_handoff', 'version': CAPABILITIES[arguments['capability']].version, **arguments
        }:
            raise ToolProviderError('Complete the registered App interaction first')
        return item.response
    services.ensure_tool(
        service_id=service_id, qualified_name=APP_INTERACT, display_name='App interaction',
        description='Open the registered App or Mini-App interaction for the requested capability and wait durably. Pass a unique request_id and known parameters. The target declaration validates parameters and determines the trusted destination. Continue the original task using its returned result; cancelled is not success.',
        input_schema=tool_schema(), output_schema=RESULT_SCHEMA, effects=(), timeout_ms=10_000,
    )
    registry.bind_tool(APP_INTERACT, provider_key=provider_key, handler=result)
