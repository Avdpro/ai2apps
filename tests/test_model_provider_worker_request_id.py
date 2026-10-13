import json
import httpx
import pytest
from ai2apps.model_providers import PackageModel, proxy_package_json, proxy_package_multipart
from ai2apps.worker_scheduler import WorkerJobScheduler

@pytest.mark.asyncio
@pytest.mark.parametrize('multipart', [False, True])
@pytest.mark.parametrize('operation', ['audio_speech', 'video_generation', 'video_upscaling'])
@pytest.mark.parametrize('explicit,body_id', [(None,'body-id'), ('explicit-cancel-id','body-id'), (None,None)])
async def test_worker_request_id_matches_scheduler_and_preserves_auth(monkeypatch,multipart,explicit,body_id,operation):
    tickets=[]
    class ObservedScheduler(WorkerJobScheduler):
        async def acquire(self,*args,**kwargs):
            lease=await super().acquire(*args,**kwargs)
            tickets.append(lease.ticket.request_id)
            return lease
    scheduler=ObservedScheduler()
    model=PackageModel(id='test/model',display_name='test',model_type='audio_tts',upstream_id='upstream',
        capabilities=(operation,),endpoints={operation:'/v1/test'},context_window=None,
        metadata={},audio_capabilities=None,video_capabilities=None,image_capabilities=None,
        service_key='test',provider_key='test',endpoint='http://worker',scheduler=scheduler,
        internal_headers={'Authorization':'Bearer fixture','X-Request-ID':'stale'})
    original=httpx.AsyncClient
    seen=[]
    def handler(request):
        seen.append(request.headers['x-request-id'])
        assert request.extensions['timeout'] == {
            'connect':15.0, 'read':14400.0 if operation in {'video_generation', 'video_upscaling'} else 300.0,
            'write':300.0, 'pool':300.0}
        assert request.headers['authorization']=='Bearer fixture'
        assert request.headers.get_list('x-request-id')==tickets
        if explicit or body_id:assert tickets==[explicit or body_id]
        else:assert tickets[0].startswith('request-')
        return httpx.Response(200,content=b'ok')
    monkeypatch.setattr('ai2apps.model_providers.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    body={'model':model.id,'input':'hello','idempotencyKey':body_id}
    files={}
    if multipart and operation == 'video_upscaling':
        import io
        import av
        import numpy as np
        buffer=io.BytesIO()
        with av.open(buffer, mode='w', format='matroska') as media:
            video=media.add_stream('ffv1', rate=1)
            video.width=video.height=16
            video.pix_fmt='yuv420p'
            frame=av.VideoFrame.from_ndarray(np.zeros((16,16,3),dtype=np.uint8),format='rgb24')
            for packet in video.encode(frame):media.mux(packet)
            for packet in video.encode():media.mux(packet)
        files={'video':('source.mkv',buffer.getvalue(),'video/x-matroska')}
    if multipart:result=await proxy_package_multipart(model,operation,data=body,files=files,request_id=explicit)
    else:result=await proxy_package_json(model,operation,body,request_id=explicit)
    assert result.status_code==200 and seen==tickets
    state=await scheduler.snapshot();assert state['running']==0 and state['completed']==1


@pytest.mark.asyncio
@pytest.mark.parametrize('multipart', [False, True])
@pytest.mark.parametrize('stream', [False, True])
@pytest.mark.parametrize('status,expected', [(200,'completed'), (499,'cancelled'), (503,'failed')])
async def test_worker_http_outcome_releases_slot_with_correct_counter(monkeypatch,multipart,stream,status,expected):
    scheduler=WorkerJobScheduler()
    model=PackageModel(id='test/model',display_name='test',model_type='audio_tts',upstream_id='upstream',
        capabilities=('audio_speech',),endpoints={'audio_speech':'/v1/audio/speech'},context_window=None,
        metadata={},audio_capabilities=None,video_capabilities=None,image_capabilities=None,
        service_key='test',provider_key='test',endpoint='http://worker',scheduler=scheduler)
    original=httpx.AsyncClient
    monkeypatch.setattr('ai2apps.model_providers.httpx.AsyncClient',lambda **kw:original(
        transport=httpx.MockTransport(lambda request:httpx.Response(status,content=b'fixture')),**kw))
    body={'model':model.id,'input':'hello','stream':'true' if stream else 'false'} if multipart else {'model':model.id,'input':'hello','stream':stream}
    if multipart:result=await proxy_package_multipart(model,'audio_speech',data=body,files={})
    else:result=await proxy_package_json(model,'audio_speech',body)
    assert result.status_code==status
    if stream:
        assert (await scheduler.snapshot())['running']==1
        assert b''.join([chunk async for chunk in result.body_iterator])==b'fixture'
    state=await scheduler.snapshot()
    assert state['running']==state['queued']==0
    assert {key:state[key] for key in ('completed','cancelled','failed')}=={key:int(key==expected) for key in ('completed','cancelled','failed')}


@pytest.mark.asyncio
async def test_context_bound_active_cancel_preserves_lease_and_rejects_other_actor(monkeypatch):
    from types import SimpleNamespace
    from dataclasses import replace
    from ai2apps.model_invocation import ModelInvocationService,ModelInvocationContext
    scheduler=WorkerJobScheduler()
    context=ModelInvocationContext(actor_user_id='alice',consumer_app_id='studio',session_id='session-a',installation_id='fixture',organization_id='fixture',billing_account_id='fixture',membership_epoch=1,authentication_type='fixture')
    model=PackageModel(id='test/model',display_name='test',model_type='audio_tts',upstream_id='upstream',capabilities=('audio_speech',),endpoints={'audio_speech':'/v1/audio/speech'},context_window=None,metadata={},audio_capabilities=None,video_capabilities=None,image_capabilities=None,service_key='test',provider_key='test',endpoint='http://127.0.0.1:12345',scheduler=scheduler)
    class Invocation(ModelInvocationService):
        def model(self,identity):return model
    invocation=Invocation(SimpleNamespace())
    from ai2apps.worker_scheduler import WorkloadClass
    lease=await scheduler.acquire('test',WorkloadClass.LOCAL_FOREGROUND,request_id='request',actor_id='alice',app_id='studio',session_id='session-a')
    seen=[];original=httpx.AsyncClient
    def handler(request):
        seen.append((request.method,request.url.path));return httpx.Response(200,json={'cancel_requested':True})
    monkeypatch.setattr('ai2apps.model_invocation.httpx.AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    assert not await invocation.cancel_request(model.id,'request',context=replace(context,actor_user_id='bob'))
    assert seen==[]
    assert not await invocation.cancel_request(model.id,'request',context=context) # active, not queue removal
    assert seen==[('DELETE','/v1/requests/request')]
    assert (await scheduler.snapshot())['running']==1
    await lease.release(cancelled=True)
