from fractions import Fraction
from pathlib import Path
import sys
import av
import numpy as np
import soundfile as sf
from scipy.signal import correlate,correlation_lags
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'packages/ai2apps-model-musetalk-mlx/src'))
from musetalk_mlx.media import write_mp4_chunks_with_audio


def test_stereo_aac_has_no_priming_delay_and_keeps_audio_tail(tmp_path):
    rate=22050;n=61653
    samples=np.zeros((n,2),np.float32)
    rng=np.random.default_rng(11)
    for channel,start in enumerate((1000,27000)):
        noise=rng.normal(size=9000)
        noise=np.convolve(noise,np.ones(7)/7,mode='same')*.2
        samples[start:start+9000,channel]=noise
    source=tmp_path/'source.wav';sf.write(source,samples,rate,subtype='FLOAT')
    target=tmp_path/'out.mp4'
    # A deliberately floor-rounded caller must not cause audio truncation.
    write_mp4_chunks_with_audio([np.zeros((67,32,32,3),np.float32)],source,target,fps=24)
    with av.open(str(target)) as c:
        frames=list(c.decode(video=0))
        assert [f.pts*f.time_base for f in frames]==[Fraction(i,24) for i in range(67)]
    with av.open(str(target)) as c:
        stream=c.streams.audio[0]
        assert len(stream.layout.channels)==2
        decoded=np.concatenate([f.to_ndarray() for f in c.decode(stream)],axis=1)
        assert abs(float(stream.duration*stream.time_base)-n/rate)<1/rate+.001
    for channel in (0,1):
        corr=correlate(decoded[channel],samples[:,channel],method='fft')
        lag=correlation_lags(decoded.shape[1],n)[np.argmax(corr)]
        assert abs(lag)<=2


def test_silent_segment_has_exact_frames_and_no_audio(tmp_path):
    target=tmp_path/'silent.mp4'
    write_mp4_chunks_with_audio([np.zeros((11,32,32,3),np.float32)],None,target,fps=24)
    with av.open(str(target)) as c:
        assert not c.streams.audio
        assert [f.pts*f.time_base for f in c.decode(video=0)]==[Fraction(i,24) for i in range(11)]
