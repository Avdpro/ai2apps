from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).parents[1]/'spark'))
from cuda_ghostv2_engine import _image, _pixels


def test_official_quantization_truncates_half_steps_and_clamps():
    values=np.array([-2.,-1.,0.,1.,2.],dtype=np.float32)
    assert _pixels(values).tolist()==[0,0,127,255,255]


def test_official_normalization_order_and_bgr_conversion():
    image=np.zeros((256,256,3),dtype=np.uint8)
    image[:,:,0]=np.arange(256,dtype=np.uint8)[None,:]
    image[:,:,1]=127;image[:,:,2]=255
    actual=_image(image)
    expected=np.asarray(image/255.,dtype=np.float32)
    expected-=np.float32(.5);expected/=np.float32(.5)
    assert np.array_equal(actual,expected[...,::-1].transpose(2,0,1))
    assert actual.dtype==np.float32
