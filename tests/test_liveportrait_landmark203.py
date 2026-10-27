"""Reject corrupt geometry before it reaches portrait warping."""
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from liveportrait_landmark203 import PortraitLandmark203

@pytest.mark.parametrize('bbox',[[0,0,0,10],[10,0,0,10],[0,0,float('nan'),10],[0,0,1]])
def test_invalid_bbox_never_runs_model(bbox):
    model=PortraitLandmark203.__new__(PortraitLandmark203)
    model.session=SimpleNamespace(run=lambda *_:pytest.fail('invalid box reached inference'))
    with pytest.raises(ValueError):model.landmarks(np.zeros((10,10,3),dtype=np.uint8),bbox)

@pytest.mark.parametrize('output',[np.zeros((1,202,2),dtype=np.float32),np.full((1,203,2),np.nan,dtype=np.float32)])
def test_bad_model_points_rejected(output):
    model=PortraitLandmark203.__new__(PortraitLandmark203)
    model.session=SimpleNamespace(run=lambda *_:[None,None,output])
    with pytest.raises(ValueError):model.landmarks(np.zeros((10,10,3),dtype=np.uint8),[0,0,10,10])
