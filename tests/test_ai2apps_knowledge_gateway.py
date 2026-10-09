"""Knowledge's sync bridge must preserve Host auth, identity and model leases."""
import asyncio
import threading
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from fastapi.responses import JSONResponse
from ai2apps.model_invocation import ModelInvocationService


@dataclass
class Model:
    id: str = 'e5/default'
    service_key: str = 'e5'
    endpoint: str = 'http://127.0.0.1:1'
    model_type: str = 'embedding'
    metadata: object = None
    scheduler: object = None
    runtime: object = None
    internal_headers: object = None


@pytest.mark.asyncio
async def test_sync_bridge_reuses_admitted_model_and_then_foreground(monkeypatch):
    import ai2apps.model_invocation as module
    events = []
    class Lease:
        async def release(self, **kwargs): events.append(('release', kwargs))
    class Scheduler:
        async def acquire(self, *args, **kwargs):
            events.append(('acquire', args)); return Lease()
    scheduler = Scheduler()
    model = Model(scheduler=scheduler, runtime=object(), internal_headers={'Authorization':'Bearer fixture'})
    service = ModelInvocationService(SimpleNamespace(worker_scheduler=scheduler))
    monkeypatch.setattr(service, '_require_model', lambda _: model)
    async def ready(selected):
        events.append(('ready', selected.id)); return selected
    async def proxy(selected, operation, payload, **kwargs):
        assert selected.internal_headers == model.internal_headers
        assert selected.scheduler is None and selected.runtime is None
        events.append(('proxy', operation))
        return JSONResponse({'data': []})
    monkeypatch.setattr(module, 'ensure_package_model_ready', ready)
    monkeypatch.setattr(module, 'proxy_package_json', proxy)
    loop = asyncio.get_running_loop()
    callback = lambda: service.invoke_sync_json(loop, model.id, 'embeddings', {'input':['hi']})
    assert await service.run_background_sync(model.id, callback) == {'data': []}
    assert [e[0] for e in events] == ['acquire','ready','proxy','release']
    assert events[-1][1] == {'failed':False}
    # Context is reset after indexing; standalone queries must acquire normally.
    async def foreground(*args, **kwargs):
        assert kwargs['context'] == 'trusted-principal'
        return JSONResponse({'foreground':True})
    monkeypatch.setattr(service, 'invoke_foreground_json', foreground)
    assert await asyncio.to_thread(service.invoke_sync_json, loop, model.id,
        'embeddings', {}, context='trusted-principal') == {'foreground':True}
    with pytest.raises(RuntimeError, match='worker thread'):
        callback()


@pytest.mark.asyncio
async def test_cancelled_sync_callback_retains_lease_until_thread_finishes(monkeypatch):
    import ai2apps.model_invocation as module
    entered, finish = threading.Event(), threading.Event()
    released = []
    class Lease:
        async def release(self, **kwargs): released.append(kwargs)
    class Scheduler:
        async def acquire(self, *args, **kwargs): return Lease()
    service = ModelInvocationService(SimpleNamespace(worker_scheduler=Scheduler()))
    monkeypatch.setattr(service, '_require_model', lambda _: Model())
    async def ready(model): return model
    monkeypatch.setattr(module, 'ensure_package_model_ready', ready)
    def callback():
        entered.set()
        assert finish.wait(3)
    task = asyncio.create_task(service.run_background_sync('e5/default', callback))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await asyncio.sleep(.02)
        assert not released and not task.done()
        task.cancel()
        await asyncio.sleep(.02)
        assert not released
    finally:
        finish.set()
    with pytest.raises(asyncio.CancelledError): await task
    assert released == [{'failed':True}]

@pytest.mark.asyncio
async def test_knowledge_provider_uses_gateway_for_query_and_passages():
    from ai2apps.knowledge.runtime import KnowledgePackageRuntime, _search_principal
    from ai2apps.identity import RequestPrincipal
    calls = []
    class Gateway:
        def invoke_sync_json(self, loop, model_id, operation, body, **options):
            calls.append((loop, model_id, operation, body, options))
            return {'data':[{'index':i,'embedding':[0.0]*384} for i in range(len(body['input']))]}
    knowledge = KnowledgePackageRuntime(object(), object(),
        runtime=SimpleNamespace(model_invocations=Gateway()), embedding_backend='cuda')
    knowledge._loop = asyncio.get_running_loop()
    principal = RequestPrincipal.legacy_local()
    token = _search_principal.set(principal)
    try:
        assert len(await asyncio.to_thread(knowledge.retriever.embedding_provider.embed, ['query'])) == 1
    finally:
        _search_principal.reset(token)
    assert len(await asyncio.to_thread(knowledge.indexer.embedding_provider.embed, ['document'])) == 1
    assert [c[3]['input_type'] for c in calls] == ['query','passage']
    assert all(c[1] == knowledge.embedding_model_id and c[2] == 'embeddings' for c in calls)
    assert calls[0][4]['context'].actor_user_id == principal.actor_user_id
    assert calls[1][4]['context'] is None
