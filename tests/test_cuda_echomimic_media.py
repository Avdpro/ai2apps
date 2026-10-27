"""Output ownership and real codec checks for EchoMimic CUDA media."""
from pathlib import Path
import sys
import av
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_echomimic_media import write_video


def frames(count=10):
    for i in range(count):
        yield np.full((32,32,3),i/10,np.float32)


def test_real_video_and_original_audio(tmp_path):
    wave = np.sin(np.arange(6400,dtype=np.float32)*np.float32(2*np.pi*440/16000))*.1
    target = write_video(frames(),wave,10,tmp_path/'out.mp4',lambda:None)
    with av.open(str(target)) as source:
        values=list(source.decode(video=0))
        assert len(values)==10
        assert [float(f.pts*f.time_base) for f in values]==pytest.approx(np.arange(10)/25)
    with av.open(str(target)) as source:
        stream=source.streams.audio[0]
        assert stream.sample_rate==16000 and stream.layout.name=='mono'
        decoded=np.concatenate([f.to_ndarray().ravel() for f in source.decode(audio=0)])[:6400]
        assert np.corrcoef(wave,decoded)[0,1]>.99
    assert not (tmp_path/'out.mp4.partial').exists()


def test_cancellation_removes_partial_output(tmp_path):
    checks=0
    def check():
        nonlocal checks
        checks+=1
        if checks==5:raise InterruptedError('cancel')
    with pytest.raises(InterruptedError):
        write_video(frames(),np.zeros(6400,np.float32),10,tmp_path/'out.mp4',check)
    assert list(tmp_path.iterdir())==[]


def test_reject_short_frame_stream_without_output(tmp_path):
    with pytest.raises(ValueError,match='frame count'):
        write_video(frames(9),np.zeros(6400,np.float32),10,tmp_path/'out.mp4',lambda:None)
    assert list(tmp_path.iterdir())==[]


def test_existing_output_is_preserved(tmp_path):
    path=tmp_path/'out.mp4';path.write_bytes(b'original')
    with pytest.raises(FileExistsError):
        write_video(frames(),np.zeros(6400,np.float32),10,path,lambda:None)
    assert path.read_bytes()==b'original'
