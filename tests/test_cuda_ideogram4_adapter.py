import asyncio
import base64
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'spark'))
from cuda_ideogram4_adapter import CudaIdeogram4Adapter, MODEL, REPO, REVISION, parameters
from ai2apps.model_worker.protocol import ModelWorkerError, ModelWorkerRequest


@pytest.mark.parametrize('extra', [{'n': True}, {'stream': 0}, {'size': '255x256'}, {'seed': -1}, {'steps': 1.5}, {'quantization': 'q4'}, {'imageDataUrls': ['data:x']}])
def test_invalid_parameters(extra):
    with pytest.raises(ValueError):
        parameters({'prompt': 'teapot', **extra})


def test_literal_prompt_is_explicit_wrapper():
    import json
    result = parameters({'prompt': 'teapot'})
    caption = json.loads(result[0])
    assert caption['high_level_description'] == 'teapot'
    assert caption['compositional_deconstruction']['elements'][0]['desc'] == 'teapot'
    assert result[-1] == 'literal_wrapper'


def test_worker_cancellation_joins_thread_before_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr("cuda_ideogram4_adapter.verify_inputs", lambda *a, **kw: None)
    entered = threading.Event()
    exited = threading.Event()
    class Engine:
        calls = 0
        closed = False
        def __init__(self, *_): pass
        def generate(self, prompt, output, *, check, **kwargs):
            self.calls += 1
            if self.calls == 1:
                entered.set()
                try:
                    while True:
                        check()
                        threading.Event().wait(.005)
                finally: exited.set()
            Image.new('RGB', (256, 256), 'red').save(output)
        def close(self): self.closed = True
    checkpoint = SimpleNamespace(path=tmp_path, repo_id=REPO, revision=REVISION)
    context = SimpleNamespace(models=[{'id': MODEL}], package_root=tmp_path, checkpoint_for=lambda _: checkpoint)
    adapter = CudaIdeogram4Adapter(context, engine_factory=Engine)
    def request(identity):
        return ModelWorkerRequest('image_generation', {'model': MODEL, 'prompt': 'red', 'size': '256x256'}, identity, output_root=tmp_path)
    async def run():
        task = asyncio.create_task(adapter.invoke(request('first')))
        assert await asyncio.to_thread(entered.wait, 5)
        with pytest.raises(ModelWorkerError) as conflict:
            await adapter.invoke(request('first'))
        assert conflict.value.status_code == 409
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        assert exited.is_set() and not adapter.events and not adapter.lock.locked()
        result = await adapter.invoke(request('recovery'))
        assert base64.b64decode(result['data'][0]['b64_json']).startswith(b'\x89PNG')
        assert not list(tmp_path.glob('ideogram-*'))
        engine = adapter.engine
        await adapter.stop()
        assert engine.closed and adapter.engine is None
        with pytest.raises(ModelWorkerError) as stopping: await adapter.invoke(request('stopped'))
        assert stopping.value.status_code == 503
    asyncio.run(run())


def test_structured_caption_keeps_tokenizer_input():
    # Whitespace inside a structured prompt is part of the upstream text input.
    prompt = '{"high_level_description": "teapot", "compositional_deconstruction": {"background": "", "elements": []}}'
    result = parameters({'prompt': prompt})
    assert result[0] == prompt and result[-1] == 'structured'
