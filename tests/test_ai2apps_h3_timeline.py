import pytest
from ai2apps.avatar.h3_timeline import plan_h3_windows, sample_boundary

@pytest.mark.parametrize('rate', [16000, 32000, 44100, 48000])
@pytest.mark.parametrize('samples', [1, 1001, 32000, 204800, 1000000, 2880001])
def test_exact_coverage_and_conditioning(rate, samples):
    windows = plan_h3_windows(samples, rate)
    end = 0
    resampled = (samples * 32000 + rate - 1) // rate
    for w in windows:
        assert w.output_start == end
        assert w.keep_frames > 0
        assert (w.generate_frames - 5) % 17 == 0
        assert w.generate_frames * 40 % 24 == 0
        assert w.context_frames == (39 if w.index else 0)
        start, stop, pad = w.conditioning_span(resampled)
        assert stop - start + pad == w.audio_latents * 800
        assert stop <= resampled
        if pad:
            assert w == windows[-1]
        end = w.output_end
    assert end == (samples * 24 + rate - 1) // rate
    assert 0 <= end * rate - samples * 24 < rate


def test_thirty_second_seams():
    w = plan_h3_windows(30 * 48000, 48000)
    assert [x.start_frame for x in w] == [0, 153, 306, 459, 612]
    assert [x.generate_frames for x in w] == [192, 192, 192, 192, 141]
    assert w[-1].output_end == 720
    assert sum(x.keep_frames for x in w) == 720


def test_absolute_sample_rounding_does_not_accumulate():
    boundaries = [sample_boundary(i * 39, 44100) for i in range(1000)]
    assert {b-a for a,b in zip(boundaries,boundaries[1:])} == {71662, 71663}
    assert boundaries[-1] == (999 * 39 * 44100 * 2 + 24) // 48


@pytest.mark.parametrize('kwargs', [dict(window_frames=124), dict(context_frames=17), dict(window_frames=39), dict(window_frames=396), dict(total_samples=0), dict(sample_rate=0), dict(total_samples=True)])
def test_invalid_requests(kwargs):
    args = dict(total_samples=320000, sample_rate=32000)
    args.update(kwargs)
    with pytest.raises(ValueError):
        plan_h3_windows(**args)
