import pytest
import wave

from ai2apps.model_worker.cuda_video import CudaH3Adapter


@pytest.mark.parametrize('recipe,filename', [
    ('lightx2v-8step-v1.0-768p', 'minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors'),
    ('lightx2v-4step-v1.2-768p', 'minimax_h3_fl2v_turbo_4step_v1.2_768p_comfyui_bf16.safetensors'),
])
def test_turbo_overlay_requires_pinned_host_checkpoint_and_confined_file(tmp_path, recipe, filename):
    from types import SimpleNamespace
    from ai2apps.model_worker.h3_turbo import LORA_8STEP
    from ai2apps.model_worker.protocol import ModelWorkerError
    overlay = SimpleNamespace(path=tmp_path, repo_id='lightx2v/Minimax-h3-Turbo',
        revision='2f015e66b37c585cea9dc4ae6f1850ea8788e742')
    adapter = CudaH3Adapter(SimpleNamespace(checkpoint_for=lambda identity: overlay if identity == 'overlay' else None))
    spec = {'h3_variant': 'fl2va', 'h3_turbo': recipe, 'h3_lora_model_id': 'overlay'}
    (tmp_path / 'loras').mkdir()
    weight = tmp_path / 'loras' / filename
    weight.write_bytes(b'fixture')
    assert adapter.resolve_turbo(spec) == tmp_path
    overlay.revision = 'main'
    with pytest.raises(ModelWorkerError, match='revision mismatch'):
        adapter.resolve_turbo(spec)
    overlay.revision = '2f015e66b37c585cea9dc4ae6f1850ea8788e742'
    with pytest.raises(ModelWorkerError, match='Unsupported'):
        adapter.resolve_turbo({**spec, 'h3_variant': 'ref2va'})
    outside = tmp_path.parent / (tmp_path.name + '-outside')
    outside.write_bytes(b'fixture')
    weight.unlink()
    weight.symlink_to(outside)
    with pytest.raises(ModelWorkerError, match='layout'):
        adapter.resolve_turbo(spec)


@pytest.mark.parametrize('patch',[
    {'width':513},{'width':2048},{'height':True},{'steps':2.5},
    {'duration':float('nan')},{'duration':60},{'duration':True},{'seed':-1},{'fast':True},
])
def test_reject_geometry_and_unimplemented_modes(patch):
    with pytest.raises((ValueError,TypeError)):
        CudaH3Adapter.parameters({'prompt':'teapot',**patch})


def test_multipart_numbers_follow_video_contract():
    assert CudaH3Adapter.parameters({'prompt':'teapot','width':'512','height':'288',
        'duration':'2','steps':'8','seed':'42'})==('teapot',512,288,2.,8,42)


def test_reference_media_bounds_and_stream_type(tmp_path):
    path=tmp_path/'reference.wav'
    def write(seconds):
        with wave.open(str(path),'wb') as output:
            output.setparams((1,2,24000,0,'NONE','not compressed'))
            output.writeframes(b'\0\0'*(24000*seconds))
    write(2)
    CudaH3Adapter.validate_media(path,'audio')
    with pytest.raises(ValueError,match='no video stream'):
        CudaH3Adapter.validate_media(path,'video')
    write(16)
    with pytest.raises(ValueError,match='15.1 seconds'):
        CudaH3Adapter.validate_media(path,'audio')

@pytest.mark.parametrize('variant', ['fl2va','ref2va'])
def test_host_variant_identity_resolves_exact_canonical_checkpoint(variant):
    from types import SimpleNamespace
    calls=[]
    models=[{'id':'h3/'+v,'upstream_id':'Comfy-Org/MiniMax-H3/'+v,'h3_variant':v} for v in ('fl2va','ref2va')]
    def checkpoint(identity):
        calls.append(identity)
        return 'checkpoint:'+identity
    adapter=CudaH3Adapter(SimpleNamespace(models=models,checkpoint_for=checkpoint))
    for identity in ('h3/'+variant,'Comfy-Org/MiniMax-H3/'+variant):
        declaration,cp=adapter.resolve_model(identity)
        assert declaration['h3_variant']==variant and cp=='checkpoint:h3/'+variant
    assert calls==['h3/'+variant]*2


def test_shared_upstream_repo_cannot_silently_select_first_h3_variant():
    from types import SimpleNamespace
    from ai2apps.model_worker.protocol import ModelWorkerError
    models=[{'id':'h3/'+v,'upstream_id':'Comfy-Org/MiniMax-H3','h3_variant':v} for v in ('fl2va','ref2va')]
    def forbidden(identity):
        raise AssertionError('ambiguous model must not resolve a checkpoint')
    adapter=CudaH3Adapter(SimpleNamespace(models=models,checkpoint_for=forbidden))
    with pytest.raises(ModelWorkerError) as error:adapter.resolve_model('Comfy-Org/MiniMax-H3')
    assert error.value.code=='model_not_supported'

@pytest.mark.asyncio
async def test_stop_drains_active_and_queued_without_replacing_cancel_event(tmp_path, monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from ai2apps.model_worker import cuda_video
    from ai2apps.model_worker.protocol import ModelWorkerError
    entered, release = asyncio.Event(), asyncio.Event()
    instances=[]
    class Process:
        def __init__(self, runtime, checkpoint, data):
            self.root=tmp_path/f'child-{len(instances)}'
            (self.root/'input').mkdir(parents=True)
            self.stopped=False;self.calls=0
            instances.append(self)
        async def start(self): pass
        async def stop(self): self.stopped=True
        async def run(self, graph, event):
            self.calls+=1;entered.set()
            await release.wait()
            if event.is_set(): raise asyncio.CancelledError
            (self.root/'out.mp4').write_bytes(b'fixture artifact')
            return {'out':{'images':[{'filename':'out.mp4'}]}}
        def output_path(self, name, subfolder): return self.root/name
    monkeypatch.setattr(cuda_video,'H3Process',Process)
    monkeypatch.setenv('AI2APPS_INFERENCE_RUNTIME',str(tmp_path))
    checkpoint=SimpleNamespace(path=tmp_path/'checkpoint',repo_id='Comfy-Org/MiniMax-H3')
    adapter=CudaH3Adapter(SimpleNamespace(models=[{'id':'h3','h3_variant':'fl2va'}],checkpoint_for=lambda _:checkpoint,data_root=tmp_path))
    adapter.backend=lambda:SimpleNamespace(ModelSet=lambda *a:None,SamplingSettings=lambda **kw:None,snap_length=lambda n:n,build_video_graph=lambda *a,**kw:{})
    def request(identity):return SimpleNamespace(request_id=identity,operation='video_generation',payload={'model':'h3','prompt':'teapot'},output_root=tmp_path,parts={},progress=None)
    active=asyncio.create_task(adapter.invoke(request('same')))
    queued=stopping=None
    try:
        await asyncio.wait_for(entered.wait(),5)
        event=adapter.events['same']
        with pytest.raises(ModelWorkerError) as duplicate:await adapter.invoke(request('same'))
        assert duplicate.value.status_code==409 and adapter.events['same'] is event
        queued=asyncio.create_task(adapter.invoke(request('queued')))
        await asyncio.sleep(0)
        stopping=asyncio.create_task(adapter.stop())
        await asyncio.sleep(0)
        assert not stopping.done()
        with pytest.raises(ModelWorkerError) as late:await adapter.invoke(request('late'))
        assert late.value.status_code==503
        release.set()
        results=await asyncio.gather(active,queued,return_exceptions=True)
        assert all(isinstance(r,ModelWorkerError) and r.status_code==499 for r in results)
        await stopping
        assert adapter.events=={} and adapter.worker is None
        assert len(instances)==1 and instances[0].calls==1 and instances[0].stopped
        assert not instances[0].root.exists()
        await adapter.start()
        result=await adapter.invoke(request('recovery'))
        assert result.media_type=='video/mp4' and len(instances)==2
        await adapter.stop()
        assert instances[1].stopped
    finally:
        release.set()
        await asyncio.gather(*(t for t in (active,queued,stopping) if t),return_exceptions=True)
        await adapter.stop()

@pytest.mark.asyncio
@pytest.mark.parametrize('recipe,steps', [('lightx2v-4step-v1.2-768p',4), ('lightx2v-8step-v1.0-768p',8)])
async def test_turbo_recipe_controls_default_steps_and_rejects_wrong_steps(tmp_path, monkeypatch, recipe, steps):
    from types import SimpleNamespace
    from ai2apps.model_worker.protocol import ModelWorkerError
    model={'id':'turbo','h3_variant':'fl2va','h3_turbo':recipe}
    checkpoint=SimpleNamespace(path=tmp_path,repo_id='Comfy-Org/MiniMax-H3')
    adapter=CudaH3Adapter(SimpleNamespace(models=[model],checkpoint_for=lambda _:checkpoint))
    monkeypatch.setattr(adapter,'resolve_turbo',lambda _:tmp_path)
    # Reaching output-root validation proves omitted steps follow the selected recipe;
    # a mismatched explicit step count must be rejected before any child process.
    for explicit in (None, steps, 12-steps):
        payload={'model':'turbo','prompt':'teapot'}
        if explicit is not None:payload['steps']=explicit
        request=SimpleNamespace(request_id='request',operation='video_generation',payload=payload,output_root=None)
        with pytest.raises(ModelWorkerError) as caught:
            await adapter.invoke(request)
        assert caught.value.code == ('invalid_request' if explicit == 12-steps else 'runtime_protocol_error')

@pytest.mark.parametrize('variant', ['fl2va', 'ref2va'])
def test_h3_variant_survives_real_host_manifest_normalization(variant):
    from pathlib import Path
    from types import SimpleNamespace
    import yaml
    from ai2apps.model_providers import validate_package_models
    # Reuse a checked-in valid video declaration; exercise the actual Host
    # normalizer, whose output deliberately drops arbitrary top-level fields.
    template = yaml.safe_load((Path(__file__).resolve().parents[1] /
        'packages/ai2apps-model-flashhead-mlx/service.yaml').read_text())['models'][0]
    identity = 'ai2apps.model.minimax-h3-cuda/' + variant
    template.update(id=identity, upstream_id='Comfy-Org/MiniMax-H3/'+variant,
                    metadata={'h3_variant': variant}, h3_variant='discarded_legacy')
    normalized = validate_package_models('ai2apps.model.minimax-h3-cuda', [template],
        runtime_mode='managed_process', protocol='ai2apps-model-worker/v1')
    assert 'h3_variant' not in normalized[0]
    checkpoint = object()
    adapter = CudaH3Adapter(SimpleNamespace(models=normalized,
        checkpoint_for=lambda model: checkpoint if model==identity else None))
    resolved, found = adapter.resolve_model(identity)
    assert found is checkpoint and resolved['h3_variant'] == variant
    assert 'h3_variant' not in normalized[0]  # resolution does not mutate Host state


def test_h3_turbo_metadata_is_preserved_and_conflicts_rejected():
    from types import SimpleNamespace
    from ai2apps.model_worker.protocol import ModelWorkerError
    metadata = {'h3_variant':'fl2va', 'h3_turbo':'lightx2v-8step-v1.0-768p',
                'h3_lora_model_id':'h3/overlay'}
    model = {'id':'h3/turbo', 'metadata':metadata}
    adapter = CudaH3Adapter(SimpleNamespace(models=[model], checkpoint_for=lambda _:None))
    resolved, _ = adapter.resolve_model('h3/turbo')
    assert all(resolved[k]==v for k,v in metadata.items())
    model['h3_variant']='ref2va'
    with pytest.raises(ModelWorkerError, match='Conflicting'):
        adapter.resolve_model('h3/turbo')
