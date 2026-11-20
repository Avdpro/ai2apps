import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[2] / "packages/ai2apps-model-musetalk-mlx/src"
    ),
)
from musetalk_mlx.prepare import mouth_mask
from musetalk_mlx.face_parsing import FaceParser
import mlx.core as mx


def test_mask_expands_lips_but_preserves_upper_face():
    labels = np.ones((512, 512), dtype=np.uint8)
    labels[330:350, 220:290] = 12
    mask = mouth_mask(labels)
    assert mask.shape == (256, 256) and mask.dtype == np.float32
    assert mask[170, 128] > 0.99
    assert mask[185, 128] > 0.1
    assert not mask[:140].any()
    assert not mask[:, -30:].any()
    assert np.all(np.isfinite(mask)) and mask.min() >= 0 and mask.max() <= 1


def test_missing_mouth_fails_instead_of_pasting_a_rectangle():
    with pytest.raises(ValueError, match="Mouth parsing failed"):
        mouth_mask(np.ones((512, 512), dtype=np.uint8))


def test_bilinear_align_corners_matches_known_ramp():
    with mx.stream(mx.cpu):
        x = mx.array([[[[0.0], [2.0]], [[4.0], [6.0]]]])
        y = np.array(FaceParser.bilinear(x, 3, 3))[0, :, :, 0]
    np.testing.assert_allclose(y, [[0, 1, 2], [2, 3, 4], [4, 5, 6]])
