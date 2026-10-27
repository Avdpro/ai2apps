from dataclasses import replace
import pytest
from fastapi import HTTPException
from ai2apps.identity import IdentityRepository
from ai2apps.chat.repository import ChatRepository
from ai2apps.core import SessionStatus
from ai2apps.api.ownership import authorize_session,authorize_workload_session
from ai2apps.browser.invocation import WebAgentInvocation
from test_system_task_sessions import runtime,OWNER,OTHER

@pytest.mark.parametrize('scope',['owner-home','mobile-agent'])
def test_trusted_workload_keeps_mobile_session_without_widening_http_scope(runtime,scope):
    principal=IdentityRepository(runtime.database).local_principal_for(OWNER)
    mobile=replace(principal,client_scope=scope)
    chats=ChatRepository(runtime.database,runtime.events,principal=mobile)
    chats.create_thread(title='Home')
    thread,_=chats.create_thread(title='Mobile')
    with pytest.raises(HTTPException):authorize_session(runtime,principal,thread.session.id)
    restored=authorize_workload_session(runtime,principal,thread.session.id)
    assert restored.client_scope==scope and restored.actor_user_id==OWNER
    task=WebAgentInvocation(runtime).submit(owner=OWNER,session_id=thread.session.id,caller_app_id='fixture.reader',name='Read',key='read-'+scope,source={'agent_type':'web','steps':[{'name':'read','operation':'read_page','arguments':{'url':'https://example.com/'},'on':{'success':'done','failed':'failed'}}]})
    assert task['session_id']==thread.session.id and task['status']=='queued'
    with pytest.raises(HTTPException):authorize_session(runtime,principal,thread.session.id)
    other=IdentityRepository(runtime.database).local_principal_for(OTHER)
    with pytest.raises(HTTPException):authorize_workload_session(runtime,other,thread.session.id)
    chats.update_thread(thread.session.id,expected_revision=thread.session.revision,status=SessionStatus.ARCHIVED)
    with pytest.raises(HTTPException):authorize_workload_session(runtime,principal,thread.session.id)
