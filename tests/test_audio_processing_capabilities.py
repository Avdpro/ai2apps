from __future__ import annotations

import pytest

from ai2apps.model_worker.audio_capabilities import (
    AudioCapabilitiesError,
    default_audio_capabilities,
    validate_audio_capabilities,
)


def _separation_capabilities():
    return {
        "schema": "ai2apps.audio-capabilities/v1",
        "operations": ["audio_process"],
        "formats": {"input": ["wav", "flac"], "output": ["wav"]},
        "streaming": {"mode": "unsupported", "formats": []},
        "processing": {
            "separation": {
                "mode": "native",
                "native_stems": ["drums", "bass", "other", "vocals"],
                "default_profile": "dialogue_background",
                "preserves_timeline": True,
                "max_input_channels": 2,
                "profiles": [
                    {
                        "id": "music_4stem",
                        "mode": "native",
                        "stems": ["drums", "bass", "other", "vocals"],
                    },
                    {
                        "id": "dialogue_background",
                        "mode": "pipeline",
                        "stems": ["dialogue", "background"],
                        "derivation": {
                            "dialogue": "vocals",
                            "background": "mixture_minus_dialogue",
                        },
                    },
                ],
            }
        },
    }


def test_audio_processing_defaults_to_unsupported_separation():
    result = default_audio_capabilities("audio_processing")
    assert result is not None
    assert result["processing"]["separation"]["mode"] == "unsupported"
    assert result["processing"]["voice_training"]["mode"] == "unsupported"
    assert result["processing"]["voice_conversion"]["mode"] == "unsupported"


def test_audio_processing_accepts_native_voice_training():
    capabilities = _separation_capabilities()
    capabilities["operations"].append("audio_voice_training")
    capabilities["processing"]["voice_training"] = {
        "mode": "native",
        "input_sources": ["dataset_zip"],
        "controls": ["epochs", "batch_size", "precision"],
        "output": "voice_bundle",
    }
    result = validate_audio_capabilities(capabilities, model_type="audio_processing")
    assert result["operations"] == ["audio_process", "audio_voice_training"]
    assert result["processing"]["voice_training"]["output"] == "voice_bundle"


def test_seed_vc_voice_conversion_capability_is_validated():
    capabilities = _separation_capabilities()
    capabilities["processing"]["voice_conversion"] = {
        "mode": "native",
        "target_sources": ["reference_audio"],
        "controls": [
            "diffusion_steps",
            "guidance_intelligibility",
            "guidance_similarity",
            "length_adjust",
            "seed",
        ],
        "profiles": [
            {"id": "timbre", "mode": "native"},
            {"id": "voice", "mode": "native"},
        ],
    }
    result = validate_audio_capabilities(capabilities, model_type="audio_processing")
    conversion = result["processing"]["voice_conversion"]
    assert conversion["target_sources"] == ["reference_audio"]
    assert [profile["id"] for profile in conversion["profiles"]] == ["timbre", "voice"]


def test_voice_conversion_requires_target_source_when_supported():
    capabilities = _separation_capabilities()
    capabilities["processing"]["voice_conversion"] = {
        "mode": "native",
        "target_sources": [],
        "profiles": [{"id": "timbre", "mode": "native"}],
    }
    with pytest.raises(AudioCapabilitiesError, match="requires target_sources"):
        validate_audio_capabilities(capabilities, model_type="audio_processing")


def test_separation_profiles_are_validated_and_preserved():
    result = validate_audio_capabilities(
        _separation_capabilities(), model_type="audio_processing"
    )
    separation = result["processing"]["separation"]
    assert separation["default_profile"] == "dialogue_background"
    assert separation["profiles"][1]["derivation"]["background"] == (
        "mixture_minus_dialogue"
    )


def test_separation_rejects_unknown_default_profile():
    capabilities = _separation_capabilities()
    capabilities["processing"]["separation"]["default_profile"] = "missing"
    with pytest.raises(AudioCapabilitiesError, match="default_profile"):
        validate_audio_capabilities(capabilities, model_type="audio_processing")


def test_separation_rejects_duplicate_stems():
    capabilities = _separation_capabilities()
    capabilities["processing"]["separation"]["profiles"][0]["stems"] = [
        "vocals",
        "vocals",
    ]
    with pytest.raises(AudioCapabilitiesError, match="duplicates"):
        validate_audio_capabilities(capabilities, model_type="audio_processing")


def test_separation_fallback_policy_requires_default_profile():
    capabilities = _separation_capabilities()
    separation = capabilities["processing"]["separation"]
    separation.pop("default_profile")
    separation["unsupported_profile_policy"] = "default_profile"
    with pytest.raises(AudioCapabilitiesError, match="required by fallback policy"):
        validate_audio_capabilities(capabilities, model_type="audio_processing")
