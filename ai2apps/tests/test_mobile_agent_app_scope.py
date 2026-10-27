"""Mobile signing changes authentication, not the Desktop AaAT business catalog."""
from dataclasses import replace
import pytest
from ai2apps.identity import RequestPrincipal
from ai2apps.services import ToolCallContext, ToolProviderError
from ai2apps.remote.mobile_apps import MobileAppPolicy
from test_aaat_declaration_context import runtime
from test_aaat_execution_flow import register

@pytest.mark.asyncio
async def test_mobile_agent_reuses_all_desktop_registered_apps_without_mobile_ui_filter(runtime):
    calls=[]
    async def execute(args,context):
        calls.append(context.actor_user_id)
        return {'value':args['query']}
    for index in (1,2):
        name=f'test.remote_app_{index}'
        register(runtime,name,execute)
        provider=runtime.app_capability_router.providers[name+'.provider']
        runtime.app_capability_router.providers[provider.id]=replace(provider,app_id=f'arbitrary.installed.{index}')
        # Mobile UI exposure is independent of Agent execution on Desktop.
        MobileAppPolicy(runtime.database).set_enabled('local',provider.app_id,False)
    desktop=RequestPrincipal.legacy_local()
    mobile=replace(desktop,authentication_type='desktop_approved_agent',client_scope='mobile-agent')
    contexts=[ToolCallContext.from_principal(p,caller_id='ai2apps.general-agent') for p in (desktop,mobile)]
    catalogs=[{t.qualified_name for t in runtime.tools.list_tools(c,include_requiring_approval=True)} for c in contexts]
    assert catalogs[0]==catalogs[1]
    for name in ('test.remote_app_1','test.remote_app_2'):
        assert name in catalogs[1]
        result=await runtime.app_capability_router.invoke(name,{'query':'actual result'},contexts[1])
        assert result['value']=='actual result'
    assert calls==['local','local']
    runtime.app_capability_router.set_enabled('local','local','test.remote_app_2.provider',False)
    with pytest.raises(ToolProviderError):
        await runtime.app_capability_router.invoke('test.remote_app_2',{'query':'disabled'},contexts[1])
    assert len(calls)==2
