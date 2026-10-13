import json
from dataclasses import asdict
from pathlib import Path
from io import BytesIO
import math
import struct
import wave

import av
import numpy as np
import pytest
from PIL import Image

from ai2apps.studio.frozen_time import camera_plan
from ai2apps.studio.frozen_time_pipeline import encode_frames, export_video, mux_soundtrack
from ai2apps.studio.frozen_time_conversion import convert_saved


def count(path):
    with av.open(str(path)) as container:
        return sum(1 for _ in container.decode(video=0))


def wav_samples(seconds, rate=48_000):
    buffer=BytesIO()
    with wave.open(buffer,'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(rate)
        output.writeframes(b''.join(struct.pack('<h',round(8000*math.sin(2*math.pi*440*i/rate))) for i in range(round(seconds*rate))))
    return buffer.getvalue()


@pytest.mark.parametrize('seconds',[0.4,3.0])
def test_mp4_soundtrack_keeps_video_duration_and_bounds_audio(tmp_path,seconds):
    video=tmp_path/'output.mp4'
    encode_frames(video,(np.zeros((32,32,3),dtype='uint8') for _ in range(48)),32,32)
    before=count(video)
    audio=tmp_path/'selected.audio';audio.write_bytes(wav_samples(seconds))
    mux_soundtrack(video,audio,lambda:False)
    with av.open(str(video)) as container:
        assert len(container.streams.video)==len(container.streams.audio)==1
        assert len(list(container.decode(video=0)))==before
    with av.open(str(video)) as container:
        samples=sum(frame.samples for frame in container.decode(audio=0))
    assert 0<samples<=round(2*48_000)+2048
    if seconds<2:
        assert samples<48_000


@pytest.mark.asyncio
async def test_conversion_preserves_existing_mp4_soundtrack(tmp_path):
    source=tmp_path/'source';source.mkdir()
    encode_frames(source/'raw.mp4',(np.zeros((32,32,3),dtype='uint8') for _ in range(73)),32,32)
    Image.new('RGB',(64,48),'orange').save(source/'input.png')
    plan=camera_plan('vertical')
    (source/'conversion.json').write_text(json.dumps({'schema':1,'plan':[asdict(k) for k in plan]}))
    source_video=source/'output.mp4'
    export_video(source/'raw.mp4',source_video,source/'poster.jpg',plan,'mp4',lambda:False)
    audio=tmp_path/'selected.wav';audio.write_bytes(wav_samples(5))
    mux_soundtrack(source_video,audio,lambda:False)
    target=tmp_path/'target';target.mkdir()
    await convert_saved(source,target,'mp4','mp4',lambda:False)
    with av.open(str(target/'output.mp4')) as container:
        assert len(container.streams.audio)==1
        assert count(target/'output.mp4')==count(source_video)


@pytest.mark.asyncio
async def test_convert_retained_result_between_all_formats(tmp_path):
    source=tmp_path/'source';source.mkdir()
    encode_frames(source/'raw.mp4',(np.full((32,32,3),i*3,dtype='uint8') for i in range(73)),32,32)
    Image.new('RGB',(64,48),'orange').save(source/'input.png')
    plan=camera_plan('vertical')
    (source/'conversion.json').write_text(json.dumps({'schema':1,'plan':[asdict(k) for k in plan]}))
    before=(source/'raw.mp4').read_bytes()
    for output,expected in [('live-photo',109),('html',73),('mp4',109)]:
        target=tmp_path/output;target.mkdir()
        artifacts=await convert_saved(source,target,output,'mp4',lambda:False)
        assert count(target/'output.mp4')==expected
        assert (target/'raw.mp4').read_bytes()==before
        if output=='live-photo':
            assert {'live-photo.zip','LivePhoto.jpg','LivePhoto.mov'} <= {a[0] for a in artifacts}
            assert Image.open(target/'LivePhoto.jpg').size==(64,48)
        if output=='html':
            assert 'data:video/mp4;base64,' in (target/'output.html').read_text()
        source=target


@pytest.mark.asyncio
async def test_legacy_live_can_convert_without_resampling_return_path(tmp_path):
    source=tmp_path/'old';source.mkdir()
    raw=tmp_path/'raw.mp4'
    encode_frames(raw,(np.full((32,32,3),i*3,dtype='uint8') for i in range(73)),32,32)
    export_video(raw,source/'output.mp4',source/'poster.jpg',camera_plan('vertical'),'live-photo',lambda:False)
    mp4=tmp_path/'mp4';mp4.mkdir()
    await convert_saved(source,mp4,'mp4','live-photo',lambda:False)
    assert (source/'output.mp4').read_bytes()==(mp4/'output.mp4').read_bytes()
    html=tmp_path/'html';html.mkdir()
    await convert_saved(mp4,html,'html','mp4',lambda:False)
    assert count(html/'output.mp4')==73
    again=tmp_path/'again';again.mkdir()
    await convert_saved(html,again,'mp4','html',lambda:False)
    assert (again/'output.mp4').read_bytes()==(mp4/'output.mp4').read_bytes()


@pytest.mark.asyncio
@pytest.mark.parametrize('return_origin',[True,False])
async def test_custom_90_frame_conversion_retains_trajectory_and_filters(tmp_path,return_origin):
    from ai2apps.studio.frozen_time import CameraKey
    from ai2apps.studio.frozen_time_editor import frame_order
    plan=tuple(CameraKey(yaw=(i-44)*10/(44 if i<=44 else 45),brightness=1-abs(i-44)*.2/(44 if i<=44 else 45)) for i in range(90))
    source=tmp_path/'source';source.mkdir()
    encode_frames(source/'raw.mp4',(np.full((32,32,3),100,dtype='uint8') for _ in range(90)),32,32)
    Image.new('RGB',(48,32),'orange').save(source/'input.png')
    metadata={'schema':2,'plan':[asdict(k) for k in plan],'playback':list(frame_order(plan,return_origin)),'poster':44}
    (source/'conversion.json').write_text(json.dumps(metadata))
    for output in ['mp4','html','mp4']:
        target=tmp_path/(output+str(len(list(tmp_path.iterdir()))));target.mkdir()
        await convert_saved(source,target,output,'mp4',lambda:False)
        assert count(target/'output.mp4')==(90 if output=='html' else len(frame_order(plan,return_origin)))
        assert json.loads((target/'conversion.json').read_text())==metadata
        with av.open(str(target/'output.mp4')) as container:
            first=next(container.decode(video=0)).to_ndarray(format='rgb24')
            assert 75<=first.mean()<=85
        source=target
