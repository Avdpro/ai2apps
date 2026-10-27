"""Never emit a nonfinite fast frame or silently mask failed FP32 fallback."""
from pathlib import Path
import sys
import numpy as np
import pytest
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_avtr_pipeline import CudaAVTRPipeline

def pipeline(mode,reference_finite=True):
    p=object.__new__(CudaAVTRPipeline);p.renderer_mode=mode;p.render_fallbacks=0;p.check=lambda:None
    calls=[]
    def render(drive,*,fast=False):
        calls.append(fast)
        return torch.full((1,3,2,2),float('nan') if fast or not reference_finite else .5)
    p.render_reference=render
    return p,calls

def test_fast_nonfinite_frame_uses_fp32():
    p,calls=pipeline('fast');pixels=list(p.render_pixels(np.zeros((1,21,3))))
    assert calls==[True,False] and p.render_fallbacks==1
    assert pixels[0].dtype==np.uint8 and np.all(pixels[0]==127)

@pytest.mark.parametrize('mode',['fast','reference'])
def test_nonfinite_reference_is_not_emitted(mode):
    p,_=pipeline(mode,False)
    with pytest.raises(ValueError,match='Nonfinite'):list(p.render_pixels(np.zeros((1,21,3))))

def test_cancel_before_reference_fallback():
    p,calls=pipeline('fast');checks=0
    def check():
        nonlocal checks
        checks+=1
        if checks==2:raise InterruptedError('cancel')
    p.check=check
    with pytest.raises(InterruptedError):list(p.render_pixels(np.zeros((1,21,3))))
    assert calls==[True]
