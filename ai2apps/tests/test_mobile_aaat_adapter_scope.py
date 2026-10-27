"""Exercise the outer App adapter as well as its downstream WebAgent guard."""
from dataclasses import replace
import pytest
from fastapi import HTTPException
from ai2apps.chat import ChatRepository
from ai2apps.core import ResourceNotFoundError
from ai2apps.identity import IdentityRepository, OrganizationType, MemberRole
from ai2apps.services import ToolCallContext, ToolProviderError
from ai2apps.services.aaat import principal_for
from ai2apps.api.ownership import authorize_session
from test_app_interactions import runtime


def mobile_context(runtime):
    identities = IdentityRepository(runtime.database)
    identities.bind_installation(installation_id='mobile-installation',cloud_device_id='mobile-device',
        organization_id='mobile-household',organization_type=OrganizationType.HOUSEHOLD,
        core_user_id='mobile-owner',billing_account_id='mobile-billing',access_epoch=1)
    local = identities.local_principal_for('mobile-owner')
    mobile = replace(local,client_scope='owner-home')
    thread,_ = ChatRepository(runtime.database,runtime.events,principal=mobile).create_thread(title='Phone adapter')
    context=ToolCallContext.from_principal(mobile,caller_id='fixture.mobile-client',
        session_id=thread.session.id,trace_id='mobile-adapter-test')
    return local,replace(context,invocation_id='mobile-adapter-invocation')


@pytest.mark.asyncio
async def test_mobile_outer_adapter_and_real_browser_submission(runtime,monkeypatch):
    local,context = mobile_context(runtime)
    assert principal_for(runtime,context).client_scope == 'owner-home'
    # A second provider exercises the common adapter without browser semantics.
    gallery = await runtime.app_capability_router.invoke('gallery.search',{},context)
    assert gallery['assets'] == []
    from ai2apps.browser import social
    from ai2apps.browser.tasks import BrowserTaskRepository
    observed=[]
    async def result(runtime_arg,task,ctx):
        persisted=BrowserTaskRepository(runtime.database,runtime.events).get(ctx.actor_user_id,task['id'])
        observed.append(persisted)
        return {'status':'not_found','candidates':[]}
    monkeypatch.setattr(social,'task_result',result)
    await runtime.app_capability_router.invoke('social.account',
        {'action':'resolve_account','platform':'x','query':'ElonMusk','profile':'default'},context)
    assert len(observed)==1
    assert observed[0]['session_id']==context.session_id
    assert observed[0]['profile_key']=='default'
    assert observed[0]['status']=='queued'
    with pytest.raises(HTTPException):authorize_session(runtime,local,context.session_id)


def test_adapter_rejects_forged_installation_and_foreign_session(runtime):
    local,context=mobile_context(runtime)
    with pytest.raises(ToolProviderError,match='Installation mismatch'):
        principal_for(runtime,replace(context,installation_id='other-installation'))
    desktop_thread,_=ChatRepository(runtime.database,runtime.events,principal=local).create_thread(title='Desktop')
    # Unknown or foreign references cannot supply a client scope.
    with pytest.raises(ResourceNotFoundError):principal_for(runtime,replace(context,session_id='missing-session'))
    identities=IdentityRepository(runtime.database)
    identities.upsert_membership(cloud_user_id='other-owner',role=MemberRole.MEMBER,status='active',membership_epoch=1)
    other=identities.local_principal_for('other-owner')
    foreign,_=ChatRepository(runtime.database,runtime.events,principal=other).create_thread(title='Other owner')
    with pytest.raises(ResourceNotFoundError):principal_for(runtime,replace(context,session_id=foreign.session.id))
    assert principal_for(runtime,replace(context,session_id=desktop_thread.session.id)).client_scope=='desktop'
