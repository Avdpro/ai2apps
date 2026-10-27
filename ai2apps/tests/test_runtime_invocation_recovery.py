"""Restart recovery preserves real Session/App event ownership without replay."""
import pytest
from ai2apps.chat import ChatRepository
from ai2apps.config import PlatformConfig
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.services import ToolInvocationStatus

@pytest.mark.parametrize('bound_session',[False,True])
def test_interrupted_invocation_event_recovers_with_correct_app_owner(tmp_path,bound_session):
    runtime=PlatformRuntime(PlatformConfig.from_base_path(tmp_path));runtime.start()
    session=None
    if bound_session:
        thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Recovery fixture')
        session=thread.session
    tool=runtime.services.get_tool('system.echo')
    pending=runtime.services.create_invocation(tool=tool,provider_key='builtin:diagnostics',
        caller_id='agent:restart-fixture',session_id=session.id if session else None,
        trace_id='run_fixture',arguments={'value':'not executed'},timeout_ms=5000)
    runtime.stop()
    restarted=PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    try:
        restarted.start()
        record=restarted.services.get_invocation(pending.id)
        assert record.status is ToolInvocationStatus.INTERRUPTED
        assert record.error=={'code':'runtime_restarted'}
        event=restarted.events.latest_for_subject(tool.id,event_type='tool.invocation.interrupted')
        assert event.payload['invocation_id']==pending.id
        assert event.session_id==(session.id if session else None)
        assert event.app_instance_id==(session.app_instance_id if session else None)
    finally:restarted.stop()
