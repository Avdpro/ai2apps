import pytest
from ai2apps.studio.frozen_time import CAMERA_MODES, camera_plan, live_photo_frame_order, interactive_html


def test_interactive_monotonic_and_center():
    plan = camera_plan('orbit',output="html")
    assert len(plan) == 73
    assert (plan[0].yaw, plan[36].yaw, plan[-1].yaw) == (-10, 0, 10)
    assert all(a.yaw < b.yaw for a,b in zip(plan, plan[1:]))


@pytest.mark.parametrize('mode',CAMERA_MODES)
def test_html_respects_selected_camera_movement(mode):
    plan=camera_plan(mode,output='html',amplitude='large')
    if mode=='orbit':
        assert plan[0].yaw==-15 and plan[-1].yaw==15
    else:
        assert plan[0]==CAMERA_MODES[mode][0]
        assert plan[-1]==CAMERA_MODES[mode][-1]
        assert plan==camera_plan(mode,output='live-photo',amplitude='large')


@pytest.mark.parametrize("mode", CAMERA_MODES)
def test_live_tail_does_not_repeat_endpoint(mode):
    plan = camera_plan(mode)
    order = live_photo_frame_order(plan)
    assert order[:73] == tuple(range(73))
    assert all(a != b for a,b in zip(order, order[1:]))
    assert order[-1] >= 36 or mode=='push-orbit2'
    assert len(order) <= 109
    end=plan[order[-1]]
    assert end.yaw == end.pitch == 0 and end.radius == 1


def test_push_does_not_replay_distant_opening():
    plan=camera_plan("push-orbit")
    order=live_photo_frame_order(plan)
    assert plan[order[-1]].yaw == 0
    assert plan[order[-1]].radius == 1


@pytest.mark.parametrize('amplitude,angle', [('large',15),('medium',10),('small',5)])
def test_center_start_push_orbit_return(amplitude,angle):
    from ai2apps.studio.frozen_time import CameraKey
    plan=camera_plan('push-orbit2',amplitude=amplitude)
    assert plan[0]==CameraKey(0)
    assert plan[24].yaw==0 and plan[24].radius<1
    assert plan[48].yaw==-angle and plan[72].yaw==angle
    order=live_photo_frame_order(plan)
    assert order[73:85]==tuple(range(71,59,-1))
    assert order[85:]==tuple(range(23,-1,-1))
    assert plan[60]==plan[24]
    assert plan[order[-1]]==CameraKey(0)
    assert len(order)==109


def test_invalid_amplitude():
    with pytest.raises(ValueError): camera_plan(amplitude='huge')


def test_offline_html_and_bounded_media():
    html=interactive_html(b'\x00\x00\x00\x18ftypmp42')
    assert 'data:video/mp4;base64,' in html
    assert '__VIDEO_BASE64__' not in html
    assert '10000' in html and 'Drag me left or right' in html
    assert "connect-src 'none'" in html
    with pytest.raises(ValueError): interactive_html(b'<script>')


@pytest.mark.parametrize("frames",[0,8,9,72,74,10000,True])
def test_bad_frame_counts(frames):
    with pytest.raises(ValueError): camera_plan(frames=frames)
