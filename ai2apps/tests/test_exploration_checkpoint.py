import json
import time
import pytest
from ai2apps.agent_builder.exploration_checkpoint import ExplorationCheckpointStore, MAX_BYTES, TTL_SECONDS

def test_restart_restores_only_same_owner_and_tab(tmp_path):
    store = ExplorationCheckpointStore(tmp_path)
    checkpoint = {'exploration': {'goal': 'Publish', 'pendingStep': {'operation':'click'}}, 'attachments': ['a']}
    store.save('alice', 'tab-a', checkpoint)
    restarted = ExplorationCheckpointStore(tmp_path)
    assert restarted.load('alice', 'tab-a') == checkpoint
    assert restarted.load('bob', 'tab-a') is None
    assert restarted.load('alice', 'tab-b') is None
    assert not list(tmp_path.glob('.checkpoint-*'))

def test_expired_or_corrupt_checkpoint_is_not_restored(tmp_path):
    store = ExplorationCheckpointStore(tmp_path)
    store.save('alice', 'tab-a', {})
    p=store.path('alice', 'tab-a')
    payload=json.loads(p.read_text());payload['saved_at']=time.time()-TTL_SECONDS-1;p.write_text(json.dumps(payload))
    assert store.load('alice','tab-a') is None
    assert not p.exists()
    p.write_text('invalid')
    assert store.load('alice','tab-a') is None

def test_oversized_checkpoint_rejected_before_write(tmp_path):
    store=ExplorationCheckpointStore(tmp_path)
    with pytest.raises(ValueError):
        store.save('alice','tab-a',{'value':'x'*MAX_BYTES})
    assert not list(tmp_path.iterdir())


def test_checkpoint_api_recovery_is_owner_bound(tmp_path):
    from dataclasses import replace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.config import PlatformConfig
    from ai2apps.identity import RequestPrincipal
    from ai2apps.platform_runtime import PlatformRuntime
    runtime=PlatformRuntime(PlatformConfig.from_base_path(tmp_path));runtime.start()
    principals=[RequestPrincipal.legacy_local()]
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:principals[0]))
    try:
        with TestClient(app) as client:
            payload={'context':'tab-a','checkpoint':{'version':1,'exploration':{'status':'running','goal':'Task'}}}
            assert client.post('/v1/platform/agent-explorations/checkpoint',json=payload).status_code==200
            assert client.get('/v1/platform/agent-explorations/checkpoint?context=tab-a').json()['checkpoint']==payload['checkpoint']
            assert client.get('/v1/platform/agent-explorations/checkpoint?context=tab-b').json()['checkpoint'] is None
            principals[0]=replace(principals[0],actor_user_id='another-user')
            assert client.get('/v1/platform/agent-explorations/checkpoint?context=tab-a').json()['checkpoint'] is None
    finally:
        runtime.stop()
