"""Odd canvas/alpha/orientation must survive CUDA media preparation unchanged."""
import importlib.util
import sys
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sol_mac_image_engine',ROOT/'packages/ai2apps-model-sol-refiner-mlx/src/image_upscale_engine.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared);sys.modules['sol_mac_image_engine']=shared
sys.path.insert(0,str(ROOT/'spark'))
from cuda_sol_image import upscale_image


def test_odd_canvas_and_alpha_are_not_stretched_or_center_cropped(tmp_path):
    pixels=np.zeros((35,47,4),np.uint8)
    pixels[:,:,:3]=np.indices((35,47))[1][:,:,None]*4
    pixels[:,:,3]=np.indices((35,47))[0]*7
    source=tmp_path/'source.png';output=tmp_path/'out.png';Image.fromarray(pixels).save(source)
    def refine(frames,**kwargs):
        padded=np.array(frames[0]);assert padded.shape==(64,64,3)
        assert np.array_equal(padded[:35,:47],pixels[:,:,:3])
        assert np.array_equal(padded[35:,46],np.repeat(pixels[34:35,46,:3],29,axis=0))
        assert kwargs['width']==128 and kwargs['height']==128
        return np.repeat(np.repeat(padded,2,axis=0),2,axis=1)[None]/255.
    metadata=upscale_image(source,output,'default',0,lambda:None,lambda _:None,refine)
    result=np.array(Image.open(output));assert result.shape==(70,94,4)
    assert np.array_equal(result[:,:,:3],np.repeat(np.repeat(pixels[:,:,:3],2,axis=0),2,axis=1))
    expected=np.array(Image.fromarray(pixels[:,:,3]).resize((94,70),Image.Resampling.LANCZOS))
    assert np.array_equal(result[:,:,3],expected) and metadata['alpha_preserved']


def test_exif_orientation_is_applied_before_geometry(tmp_path):
    image=Image.new('RGB',(40,32),'red');exif=Image.Exif();exif[274]=6
    source=tmp_path/'source.jpg';image.save(source,exif=exif)
    def refine(frames,**kwargs):return np.zeros((1,kwargs['height'],kwargs['width'],3),np.float32)
    result=upscale_image(source,tmp_path/'out.png','default',0,lambda:None,lambda _:None,refine)
    assert (result['width'],result['height'])==(64,80)


def test_nonfinite_output_never_becomes_artifact(tmp_path):
    source=tmp_path/'source.png';Image.new('RGB',(32,32)).save(source);output=tmp_path/'out.png'
    with pytest.raises(ValueError):
        upscale_image(source,output,'default',0,lambda:None,lambda _:None,
                      lambda *a,**k:np.full((1,64,64,3),np.nan))
    assert not output.exists()
