"""Host snapshot binding, without downloading weights or initializing CUDA."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from spark.cuda_musetalk_adapter import CudaMuseTalkAdapter, MODEL_ID
from ai2apps.model_worker import ModelWorkerError


def setup_request(tmp_path, auxiliaries):
    region_file = tmp_path / 'regions.json'
    region_file.write_text(json.dumps([{'box': [0, 0, 256, 256], 'mask_part': 'mask'}]))
    parts = {name: SimpleNamespace(path=region_file if name == 'regions' else tmp_path / name)
             for name in ('video', 'audio', 'regions', 'mask')}
    request = SimpleNamespace(request_id='snapshot-test', operation='video_generation',
        output_root=tmp_path, payload={'model': MODEL_ID, 'inputs': {
            'template_video': {'part_name': 'video'}, 'driving_audio': {'part_name': 'audio'},
            'regions': {'part_name': 'regions'}}}, part=parts.__getitem__)
    checkpoints = {MODEL_ID: SimpleNamespace(path=tmp_path / 'unet')}
    checkpoints.update({'ai2apps.model.musetalk-cuda/' + k: v for k, v in auxiliaries.items()})
    adapter = CudaMuseTalkAdapter(SimpleNamespace(checkpoint_for=checkpoints.get))
    calls = []
    async def capture(work):
        calls.append(work)
        return work
    adapter._owner.invoke = capture
    return adapter, request, calls, checkpoints


@pytest.mark.parametrize('aux', [
    {'vae': SimpleNamespace(path='vae')},
    {'vae': SimpleNamespace(path='vae'), 'whisper': SimpleNamespace(path=None)},
])
def test_partial_snapshot_activation_rejected_before_inference(tmp_path, aux):
    adapter, request, calls, _ = setup_request(tmp_path, aux)
    with pytest.raises(ModelWorkerError, match='required together'):
        asyncio.run(adapter.invoke(request))
    assert calls == []


def test_separate_snapshot_change_invalidates_resident_identity(tmp_path):
    adapter, request, _, checkpoints = setup_request(tmp_path, {
        'vae': SimpleNamespace(path=tmp_path/'vae-v1'),
        'whisper': SimpleNamespace(path=tmp_path/'whisper')})
    first = asyncio.run(adapter.invoke(request))
    checkpoints['ai2apps.model.musetalk-cuda/vae'] = SimpleNamespace(path=tmp_path/'vae-v2')
    second = asyncio.run(adapter.invoke(request))
    assert first.checkpoint == second.checkpoint
    assert first.whisper == second.whisper
    assert first.checkpoint_identity != second.checkpoint_identity
    assert second.vae == tmp_path/'vae-v2'


def test_existing_aggregate_fixture_remains_supported(tmp_path):
    adapter, request, _, _ = setup_request(tmp_path, {})
    work = asyncio.run(adapter.invoke(request))
    assert work.vae is None and work.whisper is None
    assert work.checkpoint == tmp_path/'unet'


def test_automatic_regions_accept_original_parser_snapshot(tmp_path):
    parser = tmp_path/'parser'
    detector = tmp_path/'detector'
    parser.mkdir(); detector.mkdir()
    (parser/'79999_iter.pth').write_bytes(b'fixture')
    (detector/'face_detection_yunet_2023mar.onnx').write_bytes(b'fixture')
    adapter, request, _, _ = setup_request(tmp_path, {
        'parser': SimpleNamespace(path=parser), 'detector': SimpleNamespace(path=detector)})
    request.payload['inputs'].pop('regions')
    work = asyncio.run(adapter.invoke(request))
    assert work.parser == parser/'79999_iter.pth'
    assert work.regions is None


def test_parser_snapshot_symlink_escape_rejected(tmp_path):
    parser = tmp_path/'parser'; parser.mkdir()
    detector = tmp_path/'detector'; detector.mkdir()
    external = tmp_path/'outside.pth'; external.write_bytes(b'fixture')
    (parser/'79999_iter.pth').symlink_to(external)
    (detector/'face_detection_yunet_2023mar.onnx').write_bytes(b'fixture')
    adapter, request, calls, _ = setup_request(tmp_path, {
        'parser': SimpleNamespace(path=parser), 'detector': SimpleNamespace(path=detector)})
    request.payload['inputs'].pop('regions')
    with pytest.raises(ModelWorkerError, match='outside snapshot'):
        asyncio.run(adapter.invoke(request))
    assert not calls


def test_host_frozen_video_roles_map_to_automatic_musetalk(tmp_path):
    parser = tmp_path/'parser'; parser.mkdir()
    detector = tmp_path/'detector'; detector.mkdir()
    (parser/'79999_iter.pth').write_bytes(b'fixture')
    (detector/'face_detection_yunet_2023mar.onnx').write_bytes(b'fixture')
    adapter, request, _, _ = setup_request(tmp_path, {
        'parser': SimpleNamespace(path=parser), 'detector': SimpleNamespace(path=detector)})
    request.payload = {'model': MODEL_ID, 'seed': 17, 'framespersecond': 25,
                       'audio_output_mode': 'preserve_driving_audio'}
    parts = {'source_video': SimpleNamespace(path=tmp_path/'frozen.mp4'),
             'audio': SimpleNamespace(path=tmp_path/'frozen.wav')}
    request.part = parts.__getitem__
    work = asyncio.run(adapter.invoke(request))
    assert work.video == tmp_path/'frozen.mp4'
    assert work.audio == tmp_path/'frozen.wav'
    assert work.parameters == {'seed': 17}
    assert work.regions is None


@pytest.mark.parametrize('unsupported', [
    {'framespersecond': 30}, {'output_format': 'webm'},
    {'audio_output_mode': 'none'}, {'resolution': '720p'}, {'duration': 5},
])
def test_host_controls_not_silently_ignored(tmp_path, unsupported):
    adapter, request, calls, _ = setup_request(tmp_path, {})
    request.payload = {'model': MODEL_ID, **unsupported}
    with pytest.raises(ModelWorkerError, match='Unsupported|duration follows'):
        asyncio.run(adapter.invoke(request))
    assert not calls


def test_real_host_defaulting_and_media_freezing_reach_adapter(tmp_path):
    from io import BytesIO
    from pathlib import Path
    import wave
    import av
    import numpy as np
    from ai2apps.video import VideoTaskManager
    from ai2apps.model_worker.video_capabilities import validate_video_capabilities

    caps = validate_video_capabilities(json.loads((Path(__file__).parents[1]/
        'packages/ai2apps-model-musetalk-cuda/META/video-capabilities.json').read_text()))
    model = SimpleNamespace(id=MODEL_ID, video_capabilities=caps, capabilities=[])
    payload = {'model': MODEL_ID, 'duration': 'auto', 'content': [
        {'type': 'video_url', 'role': 'source_video', 'video_url': {'url': 'multipart://video'}},
        {'type': 'audio_url', 'role': 'driving_audio', 'audio_url': {'url': 'multipart://audio'}}]}
    effective = VideoTaskManager._effective_request(payload, model)
    assert 'duration' not in effective and effective['framespersecond'] == 25
    video = BytesIO()
    with av.open(video, 'w', format='mp4') as container:
        stream = container.add_stream('libx264', rate=25)
        stream.width = stream.height = 32
        stream.pix_fmt = 'yuv420p'
        for _ in range(5):
            for packet in stream.encode(av.VideoFrame.from_ndarray(np.zeros((32,32,3), dtype=np.uint8),format='rgb24')):
                container.mux(packet)
        for packet in stream.encode():container.mux(packet)
    audio = BytesIO()
    with wave.open(audio,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000)
        wav.writeframes(b'\0\0'*3200)
    manager = object.__new__(VideoTaskManager)
    frozen, manifest = asyncio.run(manager._freeze_inputs(effective, tmp_path, {
        'video': ('template.mp4', video.getvalue(), 'video/mp4'),
        'audio': ('audio.wav', audio.getvalue(), 'audio/wav')}))
    parser = tmp_path/'parser';parser.mkdir()
    detector = tmp_path/'detector';detector.mkdir()
    (parser/'79999_iter.pth').write_bytes(b'fixture')
    (detector/'face_detection_yunet_2023mar.onnx').write_bytes(b'fixture')
    adapter, request, _, _ = setup_request(tmp_path, {
        'parser': SimpleNamespace(path=parser), 'detector': SimpleNamespace(path=detector)})
    request.payload = frozen
    parts = {r['part_name']:SimpleNamespace(path=tmp_path/r['path']) for r in manifest}
    request.part = parts.__getitem__
    work = asyncio.run(adapter.invoke(request))
    assert work.video.read_bytes() == video.getvalue()
    assert work.audio.read_bytes() == audio.getvalue()
    assert work.parameters == {'seed': 42} and work.regions is None
