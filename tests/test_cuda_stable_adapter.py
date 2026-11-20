import asyncio
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_stable_adapter import CudaStableAdapter, MODELS, REVISION
from ai2apps.model_worker import ModelWorkerRequest, ModelWorkerError


def payload(**kwargs):
    return dict(model='ai2apps.model.stable-audio-cuda/music',task='music',prompt='Piano',duration=10,**kwargs)


@pytest.mark.parametrize('change',[{'duration':0.9},{'duration':121},{'task':'sound_effects'},
    {'schema':'ai2apps.audio-generation/v2','duration_mode':'auto','duration':None},
    {'steps':True},{'stream':True},{'reference_audio':'file'}])
def test_rejects_unsupported_requests(change):
    p=payload();p.update(change)
    if change.get('duration_mode')=='auto':p.pop('duration')
    with pytest.raises(ModelWorkerError):CudaStableAdapter.parameters(p)


def test_full_mac_step_and_duration_bounds():
    for steps in (1,8,100):
        for duration in (1,120):
            p=payload(steps=steps);p['duration']=duration
            assert CudaStableAdapter.parameters(p)['steps']==steps


def test_native_writer_drains_before_cancelled_output_cleanup(tmp_path):
    context=SimpleNamespace(checkpoint_for=lambda _:SimpleNamespace(path=tmp_path,repo_id='stabilityai/stable-audio-3-optimized',revision=REVISION))
    adapter=CudaStableAdapter(context)
    entered,release=threading.Event(),threading.Event()
    targets=[]
    def render(work,event):
        targets.append(work.output);work.output.write_bytes(b'partial');entered.set()
        assert release.wait(3)
        work.output.write_bytes(b'late write')
    adapter._owner.render=render
    async def run():
        req=ModelWorkerRequest('audio_generate',payload(),'cancel',output_root=tmp_path)
        job=asyncio.create_task(adapter.invoke(req))
        assert await asyncio.to_thread(entered.wait,2)
        job.cancel();await asyncio.sleep(.01);job.cancel();await asyncio.sleep(.01)
        assert targets[0].exists() and not job.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):await job
        assert not targets[0].exists()
    asyncio.run(run())


def test_sfx_task_and_lyrics_contract():
    p=payload();p.update(model='ai2apps.model.stable-audio-cuda/sfx',task='sound_effects')
    assert CudaStableAdapter.parameters(p)['task']=='sound_effects'
    p['task']='music'
    with pytest.raises(ModelWorkerError):CudaStableAdapter.parameters(p)
    p=payload(lyrics='some words')
    with pytest.raises(ModelWorkerError):CudaStableAdapter.parameters(p)
