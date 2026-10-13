import json
import numpy as np
import pytest
from ai2apps.studio.frozen_time import CameraKey,FRAME_COUNTS
from ai2apps.studio.frozen_time_editor import frame_order,apply_filters,RANGES
from ai2apps.studio.frozen_time_editor import parse_frame_plan

def test_frame_plan_validates_without_interpolating_or_changing_playback():
    data={'schema':'ai2apps.camera-frames/v1','frames':[CameraKey(i/10).__dict__ for i in range(73)],'playback':list(range(73))+[71,60,5],'poster':5}
    assert parse_frame_plan(json.dumps(data))==data
    for bad in (-1,73,True,1.5):
        copy={**data,'playback':list(range(73))+[bad]}
        with pytest.raises(ValueError):parse_frame_plan(json.dumps(copy))
    with pytest.raises(ValueError):parse_frame_plan(json.dumps({'keys':[],'return_origin':False}))
    with pytest.raises(ValueError):parse_frame_plan('')

@pytest.mark.parametrize('field',RANGES)
def test_frame_plan_rejects_untrusted_values(field):
    data={'schema':'ai2apps.camera-frames/v1','frames':[CameraKey(0).__dict__.copy() for _ in range(73)],'playback':list(range(73)),'poster':36}
    data['frames'][0][field]=float('nan')
    with pytest.raises(ValueError):parse_frame_plan(json.dumps(data))

def trajectory(frames=73,count=5):
    neutral=round((count-2)/(count-1)*(frames-1))
    plan=[CameraKey(0 if i<=neutral else 10*(i-neutral)/(frames-1-neutral)).__dict__ for i in range(frames)]
    return {'schema':'ai2apps.camera-frames/v1','frames':plan,'playback':list(range(frames))+list(range(frames-2,neutral-1,-1)),'poster':neutral}

@pytest.mark.parametrize('frames',FRAME_COUNTS)
@pytest.mark.parametrize('count',(3,5,7))
def test_curves_and_return_latest_origin(frames,count):
    data=parse_frame_plan(json.dumps(trajectory(frames,count)))
    plan=tuple(CameraKey(**k) for k in data['frames'])
    assert len(plan)==frames and plan[-1].yaw==10
    order=tuple(data['playback'])
    assert order[:frames]==tuple(range(frames))
    assert plan[order[-1]]==CameraKey(0)
    assert order[-1]==round((count-2)/(count-1)*(frames-1))
    assert len(frame_order(plan,False))==frames
    assert all(0<=k.yaw<=10 for k in plan)

@pytest.mark.parametrize('field',RANGES)
def test_reject_out_of_range(field):
    data=trajectory();data['frames'][1][field]=RANGES[field][1]+1
    with pytest.raises(ValueError):parse_frame_plan(json.dumps(data))

def test_host_does_not_impose_origin_business_rules():
    data=trajectory()
    for k in data['frames']:k['saturation']=.8
    assert parse_frame_plan(json.dumps(data))==data

@pytest.mark.parametrize('bad',[None,True,float('nan'),'3'])
def test_reject_non_numeric(bad):
    data=trajectory();data['frames'][0]['yaw']=bad
    with pytest.raises(ValueError):parse_frame_plan(json.dumps(data))

def test_neutral_filters_exact_and_filters_effective():
    image=np.zeros((32,32,3),dtype='uint8');image[:16,:,0]=120
    np.testing.assert_array_equal(apply_filters(image,CameraKey(0)),image)
    assert apply_filters(image,CameraKey(0,exposure=1))[0,0,0]==240
    assert apply_filters(image,CameraKey(0,saturation=0))[0,0,0]==apply_filters(image,CameraKey(0,saturation=0))[0,0,1]
    assert apply_filters(image,CameraKey(0,blur=3))[16,0,0]>0

def test_host_rejects_keyframes_instead_of_interpreting_them():
    with pytest.raises(ValueError):parse_frame_plan(json.dumps({'keys':[],'return_origin':True,'frames':73}))
