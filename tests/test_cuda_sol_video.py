"""Real media staging preserves non-8k+1 clips and fails before allocation."""
import sys
from fractions import Fraction
from pathlib import Path
import av
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_sol_video import stage_video


def clip(path,count=10,rate=24):
    with av.open(str(path),'w') as c:
        stream=c.add_stream('libx264',rate=rate);stream.width=46;stream.height=34;stream.pix_fmt='yuv420p'
        for i in range(count):
            f=av.VideoFrame.from_ndarray(np.full((34,46,3),(i*10)%256,np.uint8),format='rgb24')
            f.pts=i;f.time_base=Fraction(1,rate)
            for p in stream.encode(f):c.mux(p)
        for p in stream.encode():c.mux(p)


def test_tail_padding_keeps_all_original_frames(tmp_path):
    path=tmp_path/'input.mp4';clip(path);calls=[]
    with stage_video(path,tmp_path,lambda:None,lambda *x:calls.append(x)) as (pixels,info):
        assert calls==[(46,34,10)]
        assert info['frames']==10 and info['inference_frames']==17
        assert pixels.shape==(17,64,64,3)
        assert np.array_equal(pixels[10:],np.repeat(pixels[9:10],7,axis=0))
        assert np.array_equal(pixels[:,34:,45],np.repeat(pixels[:,33:34,45],30,axis=1))
        assert float(pixels[9,:34,:46].mean())>float(pixels[0,:34,:46].mean())
    assert not list(tmp_path.glob('sol-cuda-*'))


def test_memory_refusal_precedes_staging(tmp_path):
    path=tmp_path/'input.mp4';clip(path)
    def refuse(*args):raise MemoryError('admission denied')
    with pytest.raises(MemoryError):
        with stage_video(path,tmp_path,lambda:None,refuse):pass
    assert not list(tmp_path.glob('sol-cuda-*'))


def test_duration_limit_precedes_admission(tmp_path):
    path=tmp_path/'input.mp4';clip(path,61,1);calls=[]
    with pytest.raises(ValueError,match='60 seconds'):
        with stage_video(path,tmp_path,lambda:None,lambda *x:calls.append(x)):pass
    assert not calls


def test_whole_clip_is_refined_once_and_decode_windows_preserve_count(tmp_path,monkeypatch):
    import importlib.util
    from cuda_sol_video import upscale_video
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('sol_mac_video_engine',root/'packages/ai2apps-model-sol-refiner-mlx/src/upscale_engine.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setitem(sys.modules,'sol_mac_video_engine',module)
    source=tmp_path/'input.mp4';clip(source,60,24)
    class Runner:
        calls=0
        windows=[]
        def refine_latents(self,images,**kwargs):
            self.calls+=1
            assert len(images)==65
            return np.arange(9,dtype=np.float32).reshape(1,1,9,1,1)
        def decode_latents(self,raw,check):
            start=int(raw[0,0,0,0,0])*8
            count=(raw.shape[2]-1)*8+1
            self.windows.append((start,count))
            return np.broadcast_to(np.arange(start,start+count)[:,None,None,None]/255.,(count,128,128,3)).copy()
    runner=Runner();output=tmp_path/'out.mp4'
    metadata=upscale_video(source,output,'default',0,tmp_path,lambda:None,lambda _:None,runner,lambda *x:None)
    assert runner.calls==1 and len(runner.windows)>1
    assert metadata['frames']==60 and metadata['temporal_policy']=='whole_clip'
    with av.open(str(output)) as c:
        assert c.streams.video[0].average_rate==24
        frames=list(c.decode(video=0))
        assert len(frames)==60 and (frames[0].width,frames[0].height)==(92,68)
        assert abs(float(frames[-1].to_ndarray(format='rgb24').mean())-59)<4
    assert not list(tmp_path.glob('sol-*'))


def test_audio_packets_survive_cuda_video_workflow(tmp_path,monkeypatch):
    import importlib.util
    from cuda_sol_video import upscale_video
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('sol_mac_video_engine',root/'packages/ai2apps-model-sol-refiner-mlx/src/upscale_engine.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setitem(sys.modules,'sol_mac_video_engine',module)
    source=tmp_path/'audio.mp4'
    with av.open(str(source),'w') as c:
        vs=c.add_stream('libx264',rate=24);vs.width=vs.height=32;vs.pix_fmt='yuv420p'
        audio=c.add_stream('aac',rate=48000);audio.layout='mono'
        for i in range(10):
            f=av.VideoFrame.from_ndarray(np.full((32,32,3),80,np.uint8),format='rgb24');f.pts=i;f.time_base=Fraction(1,24)
            for p in vs.encode(f):c.mux(p)
        for p in vs.encode():c.mux(p)
        samples=(.2*np.sin(np.arange(20000)*.03)).astype(np.float32)
        for offset in range(0,len(samples),1024):
            f=av.AudioFrame.from_ndarray(samples[offset:offset+1024][None],format='fltp',layout='mono')
            f.sample_rate=48000;f.pts=offset;f.time_base=Fraction(1,48000)
            for p in audio.encode(f):c.mux(p)
        for p in audio.encode():c.mux(p)
    class Runner:
        def refine_latents(self,images,**kwargs):return np.zeros((1,1,3,1,1))
        def decode_latents(self,raw,check):return np.zeros((17,64,64,3))
    output=tmp_path/'out.mp4'
    metadata=upscale_video(source,output,'default',0,tmp_path,lambda:None,lambda _:None,Runner(),lambda *x:None)
    def packets(path):
        with av.open(str(path)) as c:
            return [(bytes(p),p.pts,p.dts,p.time_base) for p in c.demux(c.streams.audio[0])
                    if p.dts is not None and (p.pts is None or p.pts*p.time_base<Fraction(10,24))]
    assert packets(source)==packets(output)
    assert metadata['audio_preserved']
