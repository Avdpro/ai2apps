"""Bridge any routed Provider parameter declaration to the shared Chat form."""
from fastapi import HTTPException
from ai2apps.services import ToolCallContext, ToolProviderError
from .parameter_forms import ParameterForm, FORMS, schema_fields

async def describe(runtime,principal,form,values,item):
    provider=runtime.app_capability_router.providers.get(form.key)
    if not provider: raise HTTPException(409,'Provider changed')
    if provider.id in runtime.app_capability_router.disabled(principal.actor_user_id,principal.installation_id):raise HTTPException(409,'Provider disabled')
    descriptor=await provider.describe(principal,values.get('model'))
    schema=descriptor['effective_schema']
    fields=descriptor.get('fields') or schema_fields(schema)
    if descriptor.get('models'):
        fields=[{**f,'type':'model'} if f['key']=='model' else f for f in fields]
    return {'schema':schema,'fields':fields,'models':descriptor.get('models',[]),
        'auto_submit_allowed':descriptor.get('auto_submit_allowed') is not False,
        'configuration_required':bool(descriptor.get('configuration_required')),'constraints':descriptor.get('constraints',{}),'warnings':descriptor.get('warnings',[]),
        **({'install':descriptor['install']} if descriptor.get('install') else {})}

async def complete(runtime,principal,form,values,run):
    provider=runtime.app_capability_router.providers[form.key]
    if provider.id in runtime.app_capability_router.disabled(principal.actor_user_id,principal.installation_id):raise HTTPException(409,'Provider disabled')
    try:
        if provider.prepare: values=await provider.prepare(values,ToolCallContext.from_principal(principal,caller_id='parameter-form'))
    except (ValueError,ToolProviderError) as error:raise HTTPException(422,str(error)) from error
    return {'capability':provider.capability,'provider':provider.id,
        'arguments':{**values,'provider':provider.id},'configure_only':True}

def register_provider_form(provider):
    if not provider.describe:return
    form=ParameterForm(provider.id,provider.app_id,{'type':'object','properties':{}},(),
        mini_app_id=provider.mini_app_id,version=1,capability=provider.capability,
        priority=provider.priority,provider_version=provider.version,describe=describe,complete=complete,
        related_capabilities=provider.related_capabilities,switch_values=provider.switch_values,continuation=provider.continuation,display_name=provider.display_name,summary=provider.summary,agent_context=provider.agent_context)
    existing=FORMS.get(provider.id)
    if existing and (existing.app_id,existing.mini_app_id)!=(form.app_id,form.mini_app_id):
        raise ValueError('Provider form owner collision')
    FORMS[provider.id]=form
