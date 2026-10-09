"""AAC priming must not shift driving speech relative to video frame zero."""
import importlib.util
import sys
from pathlib import Path

import av
import numpy as np
import soundfile as sf


def test_mp4_audio_starts_at_original_sample(tmp_path):
    path=Path(__file__).resolve().parents[1]/'packages/ai2apps-model-flashhead-mlx/src/flashhead_mlx/media.py'
    spec=importlib.util.spec_from_file_location('flashhead_media_timestamp_test',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
    try:spec.loader.exec_module(module)
    finally:sys.modules.pop(spec.name,None)
    rate=16000
    # Chirp avoids a periodic sine falsely passing after a full-cycle delay.
    time=np.arange(rate,dtype=np.float32)/rate
    source=.25*np.sin(2*np.pi*(200*time+900*time*time))
    audio=tmp_path/'input.wav';sf.write(audio,source,rate,subtype='FLOAT')
    frames=np.zeros((25,32,32,3),dtype=np.float32)
    output=module.write_mp4_with_audio(frames,audio,tmp_path/'output.mp4')
    with av.open(str(output)) as container:
        decoded=np.concatenate([f.to_ndarray().reshape(-1) for f in container.decode(audio=0)])
    assert len(decoded)>=len(source)
    assert np.corrcoef(source,decoded[:len(source)])[0,1]>.99
    with av.open(str(output)) as container:
        assert len(list(container.decode(video=0)))==25
