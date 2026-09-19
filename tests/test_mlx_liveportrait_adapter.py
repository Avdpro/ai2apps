import pytest

from experiments.mlx_faceswap.worker_adapter import (
    MLXLivePortraitAdapter,
    UnsupportedControlError,
    _boolean,
)


def test_adapter_resolves_operation_specific_defaults():
    image = MLXLivePortraitAdapter._parameters({}, "image_edit")
    video = MLXLivePortraitAdapter._parameters({}, "video_generation")
    assert image == {
        "precision": "fp32",
        "motion_mode": "absolute",
        "motion_multiplier": 1.0,
        "crop_only": False,
        "audio_output_mode": "none",
    }
    assert video["motion_mode"] == "relative"
    assert video["audio_output_mode"] == "auto"


@pytest.mark.parametrize(
    "operation,parameters,message",
    [
        ("video_generation", {"restore_strength": 0.5}, "restore_strength"),
        ("video_generation", {"motion_mode": "absolute"}, "relative"),
        ("image_edit", {"output_format": "jpeg"}, "output_format=png"),
    ],
)
def test_adapter_rejects_unsupported_controls(operation, parameters, message):
    with pytest.raises(UnsupportedControlError, match=message):
        MLXLivePortraitAdapter._parameters(parameters, operation)


def test_boolean_parser_is_explicit():
    assert _boolean("true", "crop_only") is True
    assert _boolean(False, "crop_only") is False
    with pytest.raises(ValueError, match="boolean"):
        _boolean(1, "crop_only")
