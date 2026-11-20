"""Static capability declaration for the MLX HTDemucs prototype."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

_HTDEMUCS_CAPABILITIES: dict[str, Any] = {
    "schema": "ai2apps.audio-capabilities/v1",
    "operations": ["audio_process"],
    "languages": [],
    "formats": {
        "input": ["wav", "pcm", "mp3", "m4a", "aac", "flac", "ogg", "opus", "webm"],
        "output": ["wav"],
    },
    "streaming": {"mode": "unsupported", "formats": []},
    "processing": {
        "separation": {
            "mode": "native",
            "native_stems": ["drums", "bass", "other", "vocals"],
            "default_profile": "dialogue_background",
            "unsupported_profile_policy": "reject",
            "preserves_timeline": True,
            "max_input_channels": 2,
            "sample_rates": [44100],
            "profiles": [
                {
                    "id": "music_4stem",
                    "mode": "native",
                    "stems": ["drums", "bass", "other", "vocals"],
                },
                {
                    "id": "vocals_instrumental",
                    "mode": "pipeline",
                    "stems": ["vocals", "instrumental"],
                    "derivation": {
                        "vocals": "vocals",
                        "instrumental": "mixture_minus_vocals",
                    },
                },
                {
                    "id": "dialogue_background",
                    "mode": "pipeline",
                    "stems": ["dialogue", "background"],
                    "derivation": {
                        "dialogue": "vocals",
                        "background": "mixture_minus_dialogue",
                    },
                    "limitations": ["dialogue_is_approximated_by_the_vocals_stem"],
                },
            ],
        }
    },
}


def htdemucs_audio_capabilities() -> dict[str, Any]:
    """Return a caller-owned copy suitable for a signed model declaration."""
    return deepcopy(_HTDEMUCS_CAPABILITIES)


def separation_profile(capabilities: dict[str, Any], profile_id: str) -> dict[str, Any]:
    profiles = capabilities["processing"]["separation"]["profiles"]
    for profile in profiles:
        if profile["id"] == profile_id:
            return deepcopy(profile)
    raise ValueError(f"Unsupported separation profile: {profile_id}")
