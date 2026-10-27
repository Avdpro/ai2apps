"""Boundary regressions for CUDA's reuse of the FlashHead Worker contract."""
import importlib.util
import types
from pathlib import Path

import pytest
from ai2apps.model_worker import ModelWorkerError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def adapter_module(monkeypatch):
    package = ROOT / 'packages/ai2apps-model-flashhead-mlx/src'
    spec = importlib.util.spec_from_file_location('flashhead_checkpoint', package / 'flashhead_mlx/checkpoint.py')
    checkpoint = importlib.util.module_from_spec(spec); spec.loader.exec_module(checkpoint)
    monkeypatch.setitem(__import__('sys').modules, 'flashhead_checkpoint', checkpoint)
    shared = types.ModuleType('flashhead_host_adapter')
    exec(compile((package / 'worker_adapter.py').read_text().replace('from flashhead_mlx.checkpoint import', 'from flashhead_checkpoint import'), str(package / 'worker_adapter.py'), 'exec'), shared.__dict__)
    monkeypatch.setitem(__import__('sys').modules, 'flashhead_host_adapter', shared)
    spec = importlib.util.spec_from_file_location('cuda_flashhead_test', ROOT / 'spark/cuda_flashhead_adapter.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('variant,limit,stride', [('lite',1500,24), ('pro',250,28)])
def test_chunk_boundaries_never_drop_or_duplicate_output_frames(adapter_module, variant, limit, stride):
    for frames in range(1, limit+1):
        padded, starts = adapter_module.chunk_layout(frames, variant)
        emitted = 0
        for index, start in enumerate(starts):
            assert start + 33 <= padded
            emitted += min(33 if index == 0 else stride, frames - emitted)
        assert emitted == frames
        assert padded >= frames
        assert padded == 33 or padded - stride < frames


@pytest.mark.parametrize('frames', [0, -1, 1501, True, 2.5])
def test_invalid_frame_counts(adapter_module, frames):
    with pytest.raises(ValueError): adapter_module.chunk_layout(frames)


def test_pro_not_silently_run_as_lite(adapter_module):
    context = types.SimpleNamespace(models=[{'id': adapter_module.SERVICE_ID + '/' + variant, 'upstream_id': variant} for variant in ('lite', 'pro')])
    adapter = adapter_module.CudaFlashHeadAdapter(context)
    assert adapter._model({'model': 'lite'}) == (adapter_module.SERVICE_ID + '/lite', 'lite')
    assert adapter._model({'model': 'pro'}) == (adapter_module.SERVICE_ID + '/pro', 'pro')
    with pytest.raises(ModelWorkerError) as error: adapter._model({'model': 'unsupported'})
    assert error.value.status_code == 404


def test_pro_duration_limit_is_independent_of_lite(adapter_module):
    with pytest.raises(ValueError): adapter_module.chunk_layout(251, 'pro')
    assert adapter_module.chunk_layout(251, 'lite')[0] >= 251

@pytest.mark.parametrize('fail', [False, True])
def test_request_rng_scope_restored_on_success_and_failure(adapter_module, monkeypatch, fail):
    import contextlib
    import sys
    state={'seed':91}
    @contextlib.contextmanager
    def fork_rng(*, devices):
        assert devices==[0]
        previous=state['seed']
        try:yield
        finally:state['seed']=previous
    fake=types.SimpleNamespace(random=types.SimpleNamespace(fork_rng=fork_rng),cuda=types.SimpleNamespace(current_device=lambda:0),manual_seed=lambda seed:state.update(seed=seed))
    monkeypatch.setitem(sys.modules,'torch',fake)
    pipeline=object.__new__(adapter_module.CudaFlashHeadPipeline)
    def generate(*args,**kwargs):
        assert state['seed']==kwargs['seed']==17
        if fail:raise RuntimeError('cancelled forward')
        return 'done'
    pipeline._generate=generate
    kwargs=dict(size=512,seed=17,steps=4,cancel_check=lambda:None,progress=lambda *_:None)
    if fail:
        with pytest.raises(RuntimeError,match='cancelled forward'):pipeline.generate(None,None,None,**kwargs)
    else:assert pipeline.generate(None,None,None,**kwargs)=='done'
    assert state['seed']==91

@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['allocator', 'accelerator', 'other'])
async def test_wrapped_cuda_oom_maps_to_503_and_unloads(adapter_module, monkeypatch, kind):
    import sys
    class OOM(RuntimeError):pass
    class Accelerator(RuntimeError):pass
    monkeypatch.setitem(sys.modules,'torch',types.SimpleNamespace(OutOfMemoryError=OOM,AcceleratorError=Accelerator))
    cause=OOM('allocation') if kind=='allocator' else Accelerator('CUDA error: out of memory' if kind=='accelerator' else 'CUDA error: invalid argument')
    async def invoke(self,request):
        try:raise cause
        except RuntimeError as error:raise ModelWorkerError('failed',code='generation_failed',status_code=500) from error
    monkeypatch.setattr(adapter_module.FlashHeadAdapter,'invoke',invoke)
    adapter=adapter_module.CudaFlashHeadAdapter(types.SimpleNamespace(models=[]))
    unloaded=[];adapter._unload=lambda:unloaded.append(True)
    with pytest.raises(ModelWorkerError) as caught:await adapter.invoke(None)
    assert caught.value.status_code==(500 if kind=='other' else 503)
    assert unloaded==([] if kind=='other' else [True])
    if kind!='other':assert cause.__traceback__ is None and cause.__notes__

@pytest.mark.asyncio
async def test_retained_cancel_exception_does_not_retain_native_closure(adapter_module, monkeypatch):
    import gc
    import weakref
    refs=[]
    class NativeTensor:pass
    def native():
        tensor=NativeTensor();refs.append(weakref.ref(tensor))
        def closure():return tensor
        try:raise RuntimeError('cancel boundary')
        except RuntimeError as error:
            raise ModelWorkerError('cancel',code='generation_cancelled') from error
    async def invoke(self,request):native()
    monkeypatch.setattr(adapter_module.FlashHeadAdapter,'invoke',invoke)
    adapter=adapter_module.CudaFlashHeadAdapter(types.SimpleNamespace(models=[]))
    with pytest.raises(ModelWorkerError) as held:await adapter.invoke(None)
    assert held.value.code=='request_cancelled' and held.value.status_code==499
    gc.collect()
    assert refs[0]() is None
    assert held.value.__cause__.__cause__.__notes__

@pytest.mark.asyncio
async def test_retained_task_cancellation_releases_native_closure(adapter_module, monkeypatch):
    import asyncio
    import gc
    import weakref
    refs=[]
    class NativeTensor:pass
    async def invoke(self,request):
        tensor=NativeTensor();refs.append(weakref.ref(tensor))
        def closure():return tensor
        raise asyncio.CancelledError()
    monkeypatch.setattr(adapter_module.FlashHeadAdapter,'invoke',invoke)
    adapter=adapter_module.CudaFlashHeadAdapter(types.SimpleNamespace(models=[]))
    with pytest.raises(asyncio.CancelledError) as held:await adapter.invoke(None)
    gc.collect()
    assert refs[0]() is None
    assert held.value.__notes__
