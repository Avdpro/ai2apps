from __future__ import annotations

import pytest

from ai2apps.model_worker.audio_capabilities import validate_audio_capabilities
from experiments.mlx_demucs.capabilities import (
    htdemucs_audio_capabilities,
    separation_profile,
)


def test_htdemucs_declares_native_and_derived_separation_profiles():
    capabilities = validate_audio_capabilities(
        htdemucs_audio_capabilities(), model_type="audio_processing"
    )
    separation = capabilities["processing"]["separation"]
    assert separation["native_stems"] == ["drums", "bass", "other", "vocals"]
    assert {item["id"] for item in separation["profiles"]} == {
        "music_4stem",
        "vocals_instrumental",
        "dialogue_background",
    }


def test_profile_selection_rejects_unsupported_topology():
    with pytest.raises(ValueError, match="Unsupported separation profile"):
        separation_profile(htdemucs_audio_capabilities(), "dialogue_music_effects")
