"""Discover-owned installation continuation using the existing durable form handoff."""
import json
from fastapi import HTTPException
from ai2apps.agents.parameter_forms import ParameterForm, FORMS
from ai2apps.agents.form_continuation import ADAPTERS, ContinuationAdapter
from ai2apps.apps.access import has_app_capability, APP_SYSTEM_MANAGE
from .capability_catalog import validate_target
from .installed_capabilities import inspect

KEY='ai2apps.discover.install'
SCHEMA={'type':'object','properties':{'installation_target':{'type':'object','properties':{k:{'type':'string'} for k in ('packageId','version','manifestSha256','artifactSha256')},'required':['packageId','version','manifestSha256','artifactSha256'],'additionalProperties':False},'requested_capability':{'type':'string','maxLength':120}},'required':['installation_target'],'additionalProperties':False}
CONTEXT={'schema':'ai2apps.aaat-declaration/v1','instructions':[
    'Use this installation handoff for an observed exact Discover candidate in the current Run. For a unique clearly fitting candidate, present the review directly without a preliminary installation question. The user selects and approves the exact release in Discover; ambiguous alternatives require user choice before installation. Installation never authorizes executing the new capability.',
    'Keep the original task and materials in this Run. Continue in Discover for signed Package review and installation. After returning, rediscover actual Providers, review their current declaration and collect any required business parameters before invoking.',
    'Cancelled, UI-only, unverified, unavailable or changed releases are not successful business execution. Do not reinstall, switch versions or retry uncertain business effects automatically.'],
    'result_semantics':{'executed_in_app':'Only the explicit Package installation/rediscovery step completed. The original business task still needs planning and its own authorization.'}}


def selected(runtime,run,values):
    target=validate_target(values['installation_target'])
    candidates=[c for step in runtime.agents.list_steps(run.id) if step.kind=='tool' and step.tool_name in ('discover.packages','discover.package_detail') and step.status.value=='completed' and isinstance(step.output,dict)
                for c in step.output.get('candidates',[]) if isinstance(c,dict)]
    # Bind to observed same-Run candidates; model JSON and excluded results cannot mint a target.
    if not any(c.get('installation_target')==target for c in candidates):
        raise HTTPException(409,'Select an exact candidate observed in this Run first')
    return target


def begin(runtime,principal,run,item,form,values):
    if not has_app_capability(principal,APP_SYSTEM_MANAGE):raise HTTPException(403,'Package management access required')
    return {'installation_target':selected(runtime,run,values),'requested_capability':values.get('requested_capability',''),
            'session_id':run.session_id,'actor_id':principal.actor_user_id,'installation_id':principal.installation_id}


def link(*args):raise HTTPException(422,'Package installation does not accept a Studio result')


def complete(runtime,principal,run,item,form,record):
    if not has_app_capability(principal,APP_SYSTEM_MANAGE):raise HTTPException(403,'Package management access required')
    payload=json.loads(record['payload_json'])
    if (payload['session_id'],payload['actor_id'],payload['installation_id'])!=(run.session_id,principal.actor_user_id,principal.installation_id):
        raise HTTPException(409,'Installation continuation identity changed')
    result=inspect(runtime,principal,payload['installation_target'])
    if result['status'] in ('not_installed','installed_release_differs','inactive_or_replaced','unavailable'):
        raise HTTPException(409,'The selected exact release is not active; installation continuation is preserved')
    expected=payload['requested_capability']
    available=[p for o in result['providers'] if o['interface_verified'] and (not expected or o['export']==expected) for p in o['registered_providers'] if p['enabled'] and p['status']=='registered']
    return {'capability':'discover.install','provider':KEY,'app_id':'ai2apps.discover',
        'installation_target':payload['installation_target'],'capability_discovery':result,
        'ready_providers':available,'original_task_ready':bool(available),'executed_in_app':True,'configure_only':False,
        'business_executed':False}


async def no_submit(runtime,principal,form,values,run):
    raise HTTPException(409,'Continue in Discover for signed Package review and installation')


async def describe(runtime,principal,form,values,item):
    return {'configuration_required':True,'handoff_only':True,
        'continue_label':{'zh':'前往 Discover 审核安装','en':'Review installation in Discover'},
        'handoff_message':{'zh':'请先在 Discover 审核并安装所选 Package。当前任务和参数会保留；安装完成后返回此处继续。','en':'Review and install the selected Package in Discover first. Your task and parameters are preserved; return here after installation to continue.'}}


def install():
    ADAPTERS[KEY]=ContinuationAdapter(begin,link,complete)
    FORMS[KEY]=ParameterForm(KEY,'ai2apps.discover',SCHEMA,fields=(
        {'key':'installation_target','type':'json','label':{'zh':'所选精确版本','en':'Selected exact release'}},
        {'key':'requested_capability','type':'text','label':{'zh':'需要的能力（可选）','en':'Required capability (optional)'}}),
        prompt={'zh':'在 Discover 审核安装','en':'Review installation in Discover'},capability='discover.install',continuation=KEY,
        version=1,provider_version='1',complete=no_submit,describe=describe,agent_context=CONTEXT,
        display_name={'zh':'安装所选能力','en':'Install selected capability'},
        summary={'zh':'保留当前任务，在 Discover 审核安装精确版本；返回后重新发现能力。','en':'Keep this task while reviewing the exact release in Discover; rediscover Providers after installation.'})
