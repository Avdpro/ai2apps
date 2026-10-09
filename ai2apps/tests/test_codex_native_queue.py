import pytest
from ai2apps.codex.native_queue import find_turn, progress
from ai2apps.codex.manager import CodexManager


def test_live_interrupted_is_not_terminal_and_final_requires_end_time():
    turn={'status':'interrupted','completedAt':None,'items':[{'type':'agentMessage','text':'Working'}]}
    assert progress(turn)[0]=='running'
    turn.update(status='completed',completedAt=100)
    assert progress(turn)[:2]==('ended','Working')
    turn['status']='failed'
    assert progress(turn)[0]=='failed'


@pytest.mark.asyncio
async def test_match_only_user_marker_across_pages():
    class Client:
        async def call(self, method, params):
            if 'cursor' not in params:
                return {'data':[{'id':'other','items':[{'type':'agentMessage','text':'[AI2Apps run:r]'}]}], 'nextCursor':'next'}
            return {'data':[{'id':'target','items':[{'type':'userMessage','content':[{'type':'text','text':'[AI2Apps run:r]\nTask'}]}]}]}
    assert (await find_turn(Client(),'thread','[AI2Apps run:r]'))['id']=='target'


@pytest.mark.asyncio
async def test_persist_intent_then_enqueue_once_then_watch(monkeypatch):
    m=CodexManager();events=[]
    async def update(status, **fields):events.append(fields)
    async def enqueue(thread,message,model):
        assert events[-1]['native_delivery']=='pending'
        assert message.startswith('[AI2Apps run:r]\nTask')
        assert 'ai2apps-result' in message
        return 'message-id'
    async def watch(thread,marker,callback):
        assert events[-1]['native_message_id']=='message-id'
        events.append({'watched':marker})
    monkeypatch.setattr('ai2apps.codex.native_queue.enqueue',enqueue)
    monkeypatch.setattr(m,'watch_native',watch)
    await m.native_run('r','thread','Task','',update)
    assert events[-1]=={'watched':'[AI2Apps run:r]'}


@pytest.mark.asyncio
async def test_delivery_uncertainty_does_not_resend(monkeypatch):
    m=CodexManager();calls=[];events=[]
    async def enqueue(*args):calls.append(1);raise TimeoutError('unknown delivery')
    async def watch(*args):pass
    async def update(status,**fields):events.append(fields)
    monkeypatch.setattr('ai2apps.codex.native_queue.enqueue',enqueue)
    monkeypatch.setattr(m,'watch_native',watch)
    await m.native_run('r','thread','Task','',update)
    assert calls==[1] and events[-1]['native_delivery']=='unknown'
    await m.resume_native('thread','[AI2Apps run:r]',update)
    assert calls==[1] and not m.jobs and not m.desktop_threads
