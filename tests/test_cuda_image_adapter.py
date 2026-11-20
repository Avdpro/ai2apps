import base64
import io
import threading

import pytest
from PIL import Image

from ai2apps.model_worker.cuda_image import CudaFlux2KleinAdapter
from ai2apps.model_worker.protocol import ModelWorkerError


@pytest.mark.parametrize('patch', [{'size':'20000x512'}, {'guidance':float('nan')}, {'quantization':'q4'}, {'steps':0}])
def test_reject_unvalidated_image_options(patch):
    with pytest.raises(ValueError):
        CudaFlux2KleinAdapter.parameters({'prompt':'teapot', **patch})


def test_reference_requires_decodable_image_and_limit():
    invalid='data:image/png;base64,'+base64.b64encode(b'not an image').decode()
    with pytest.raises(ValueError, match='invalid reference'):
        CudaFlux2KleinAdapter.references({'imageDataUrls':[invalid]})
    output=io.BytesIO()
    Image.new('RGB',(32,32),'red').save(output,format='PNG')
    url='data:image/png;base64,'+base64.b64encode(output.getvalue()).decode()
    assert len(CudaFlux2KleinAdapter.references({'imageDataUrls':[url]*4}))==4
    with pytest.raises(ValueError, match='one to four'):
        CudaFlux2KleinAdapter.references({'imageDataUrls':[url]*5})


def test_cancellation_does_not_persist_to_next_request():
    event=threading.Event()
    event.set()
    with pytest.raises(ModelWorkerError) as error:
        CudaFlux2KleinAdapter.check_cancel(event)
    assert error.value.status_code==499
    CudaFlux2KleinAdapter.check_cancel(threading.Event())

@pytest.mark.asyncio
@pytest.mark.parametrize('variant', ['4B', '9B'])
async def test_active_duplicate_cannot_replace_cancellation_and_stop_drains(monkeypatch, variant):
    import asyncio
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    entered, release = threading.Event(), threading.Event()
    loads = []

    class Pipeline:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            assert kwargs['local_files_only'] is True
            assert ('scheduler' in kwargs) == (variant == '9B')
            loads.append(args)
            return cls()
        def to(self, device):
            return self
        def __call__(self, **kwargs):
            entered.set()
            assert release.wait(5), 'test failed to release generation thread'
            kwargs['callback_on_step_end'](self, 0, None, {})
            return SimpleNamespace(images=[Image.new('RGB', (256, 256), 'red')])

    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(
        bfloat16='bf16', cuda=SimpleNamespace(empty_cache=lambda: None),
        Generator=lambda device: SimpleNamespace(manual_seed=lambda seed: None)))
    def scheduler_from_config(config):
        assert config['shift'] == 3.0 and config['use_dynamic_shifting'] is True
        return object()
    monkeypatch.setitem(sys.modules, 'diffusers', SimpleNamespace(Flux2KleinPipeline=Pipeline,
        FlowMatchEulerDiscreteScheduler=SimpleNamespace(from_config=scheduler_from_config)))
    checkpoint = SimpleNamespace(path=Path('/test/fixed'),
        upstream_id=f'black-forest-labs/FLUX.2-klein-{variant}',
        repo_id=f'black-forest-labs/FLUX.2-klein-{variant}',
        revision=CudaFlux2KleinAdapter.KLEIN_9B_REVISION)
    adapter = CudaFlux2KleinAdapter(SimpleNamespace(checkpoint_for=lambda _: checkpoint))
    def request(identity):
        return SimpleNamespace(request_id=identity, operation='image_generation',
            payload={'model':'fixed', 'prompt':'red teapot', 'size':'256x256'}, progress=None)
    active = asyncio.create_task(adapter.invoke(request('same')))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        original_event = adapter.events['same']
        with pytest.raises(ModelWorkerError) as duplicate:
            await adapter.invoke(request('same'))
        assert duplicate.value.status_code == 409
        assert adapter.events['same'] is original_event
        queued = asyncio.create_task(adapter.invoke(request('queued')))
        await asyncio.sleep(0)
        stopping = asyncio.create_task(adapter.stop())
        await asyncio.sleep(0)
        assert not stopping.done()
        with pytest.raises(ModelWorkerError) as rejected:
            await adapter.invoke(request('late'))
        assert rejected.value.status_code == 503
        release.set()
        outcomes = await asyncio.gather(active, queued, return_exceptions=True)
        assert all(isinstance(e, ModelWorkerError) and e.status_code == 499 for e in outcomes)
        await stopping
        assert adapter.events == {} and adapter.pipeline is None
        assert len(loads) == 1  # queued request never entered model generation
        await adapter.start()
        recovered = await adapter.invoke(request('recovery'))
        assert recovered['image']['size'] == '256x256'
        assert len(loads) == 2
        await adapter.stop()
    finally:
        release.set()
        await asyncio.gather(active, return_exceptions=True)


@pytest.mark.parametrize('patch', [{'revision': 'main'}, {'repo_id': 'untrusted/model'},
                                 {'upstream_id': 'black-forest-labs/FLUX.2-klein-Base-9B'}])
def test_9b_rejects_unpinned_or_different_checkpoint(patch):
    from types import SimpleNamespace
    fields = dict(upstream_id=CudaFlux2KleinAdapter.KLEIN_9B,
                  repo_id=CudaFlux2KleinAdapter.KLEIN_9B,
                  revision=CudaFlux2KleinAdapter.KLEIN_9B_REVISION)
    with pytest.raises(ModelWorkerError) as error:
        CudaFlux2KleinAdapter.validate_checkpoint(SimpleNamespace(**(fields | patch)))
    assert error.value.code == 'model_not_supported'
