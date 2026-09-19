from __future__ import annotations

import pytest

from experiments.mlx_rvc.config import RVCConfig

V2_48K = [
    1025,
    32,
    192,
    192,
    768,
    2,
    6,
    3,
    0,
    "1",
    [3, 7, 11],
    [[1, 3, 5], [1, 3, 5], [1, 3, 5]],
    [12, 10, 2, 2],
    512,
    [24, 20, 4, 4],
    109,
    256,
    "48k",
]


def test_parses_v2_48k_legacy_config():
    config = RVCConfig.from_legacy(V2_48K, version="v2", uses_f0=True, speaker_count=3)

    assert config.sample_rate == 48_000
    assert config.hop_length == 480
    assert config.feature_channels == 768
    assert config.speaker_count == 3
    assert config.uses_f0 is True


def test_rejects_invalid_version_and_upsampling():
    with pytest.raises(ValueError, match="v1 or v2"):
        RVCConfig.from_legacy(V2_48K, version="v3", uses_f0=True)
    invalid = list(V2_48K)
    invalid[14] = [24]
    with pytest.raises(ValueError, match="equal"):
        RVCConfig.from_legacy(invalid, version="v2", uses_f0=True)
