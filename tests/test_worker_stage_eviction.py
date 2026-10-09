"""Generation and live-state gates in the actual Supervisor eviction method."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest
from ai2apps.packages.supervisor import ManagedServiceSupervisor
from ai2apps.packages.models import PackageError


def supervisor(snapshot):
    value=object.__new__(ManagedServiceSupervisor)
    value._generations={'worker':7}
    value._evicted={}
    value._live={'worker':SimpleNamespace(package=SimpleNamespace(protocol='ai2apps-model-worker/v1'))}
    value.worker_snapshot=AsyncMock(return_value=snapshot)
    value.stop=AsyncMock()
    value.packages=SimpleNamespace(append_log=Mock())
    return value


@pytest.mark.asyncio
@pytest.mark.parametrize('snapshot,code',[
    ({'activeRequests':1,'queuedRequests':0},'worker_busy'),
    ({'activeRequests':0,'queuedRequests':1},'worker_busy'),
    ({'activeRequests':None,'queuedRequests':None},'worker_state_unavailable'),
])
async def test_live_worker_must_be_known_idle(snapshot,code):
    value=supervisor(snapshot)
    with pytest.raises(PackageError) as error:
        await value.evict('worker',reason='stage_complete',expected_generation=7)
    assert error.value.code==code
    value.stop.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('advance_generation',[False,True])
async def test_replacement_during_snapshot_is_never_stopped(advance_generation):
    value=supervisor({})
    replacement=SimpleNamespace(package=SimpleNamespace(protocol='ai2apps-model-worker/v1'))
    async def snapshot(package):
        value._live['worker']=replacement
        if advance_generation:value._generations['worker']=8
        return {'activeRequests':0,'queuedRequests':0}
    value.worker_snapshot=snapshot
    with pytest.raises(PackageError) as error:
        await value.evict('worker',reason='stage_complete',expected_generation=7)
    assert error.value.code=='worker_generation_conflict'
    assert value._live['worker'] is replacement
    value.stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_same_idle_generation_uses_standard_stop_and_audit():
    value=supervisor({'activeRequests':0,'queuedRequests':0})
    result=await value.evict('worker',reason='stage_complete',expected_generation=7)
    value.stop.assert_awaited_once_with('worker')
    value.packages.append_log.assert_called_once()
    assert result['state']=='evicted' and result['generation']==7
