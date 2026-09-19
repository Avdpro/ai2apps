import numpy as np

from experiments.mlx_faceswap.models import FaceDetection
from experiments.mlx_faceswap.tracking import TemporalFaceTracker


def face(x: float, score: float = 0.9) -> FaceDetection:
    return FaceDetection(
        bbox=np.array([x, 0, x + 10, 10], dtype=np.float32),
        score=score,
        landmarks=np.full((5, 2), x, dtype=np.float32),
    )


def test_tracker_preserves_identity_and_smooths_geometry():
    tracker = TemporalFaceTracker(smoothing=0.5)
    first = tracker.update([face(0), face(100)])
    assert [item.track_id for item in first] == [1, 2]

    second = tracker.update([face(2), face(102)])
    assert [item.track_id for item in second] == [1, 2]
    assert second[0].bbox[0] == 1
    assert second[1].bbox[0] == 101


def test_tracker_survives_short_detection_gap():
    tracker = TemporalFaceTracker(max_missed=1)
    tracker.update([face(0)])
    assert tracker.update([])[0].missed == 1
    assert tracker.update([]) == ()


def test_tracker_predicts_geometry_between_detection_frames():
    tracker = TemporalFaceTracker(smoothing=0.0, velocity_smoothing=0.0)
    tracker.update([face(0)])
    tracker.predict()
    tracker.update([face(4)])
    predicted = tracker.predict()[0]
    assert predicted.bbox[0] == 6
    np.testing.assert_allclose(predicted.landmarks, 6)
