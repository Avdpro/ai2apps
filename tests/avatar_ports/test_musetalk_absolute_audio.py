import importlib.util
from pathlib import Path
import numpy as np
import pytest
import mlx.core as mx

path=Path(__file__).resolve().parents[2] / 'packages/ai2apps-model-musetalk-mlx/src/musetalk_mlx/whisper/audio2feature.py'
spec=importlib.util.spec_from_file_location('avatar_audio_feature_test',path)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

@pytest.mark.parametrize('start,end', [(0,39),(187,340),(711,735),(1400,1440),(1440,1457)])
def test_window_matches_full_global_audio_features(start,end):
    # At 30 seconds the encoder moves to a new chunk; retained lip features
    # must still match the full-track result across that boundary.
    n=61*16000
    stacked=mx.array(np.arange(3100*2*3,dtype=np.float32).reshape(1,3100,2,3))
    full=mod.get_whisper_chunk(stacked,n,fps=24)
    first=max(0,(start*50//24-6)//1500)*1500
    stop=min(3100,((end*50//24+10+1499)//1500)*1500)
    actual=mod.get_whisper_frame_range(stacked[:,first:stop],n,start,end,feature_offset=first)
    np.testing.assert_array_equal(np.array(actual),np.array(full[start:end]))

def test_partial_last_frame_and_missing_context():
    n=16000+17
    stacked=mx.ones((1,1500,2,3))
    full=mod.get_whisper_chunk(stacked,n,fps=24)
    last=mod.get_whisper_frame_range(stacked,n,23,25)
    np.testing.assert_array_equal(np.array(last[0]),np.array(last[1]))
    np.testing.assert_array_equal(np.array(last[0]),np.array(full[-1]))
    with pytest.raises(ValueError,match='context'):
        mod.get_whisper_frame_range(stacked[:,20:40],n,15,20,feature_offset=20)
