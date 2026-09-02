"""Strict Local validation for Cloud-authoritative multimodal pricing inputs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

CALCULATOR_CONTRACTS = {
    "tts_v1": ("audio_tts", "unicode_scalar", "audio_millisecond"),
    "image_v1": ("image_generation", "pixel", "pixel"),
    "video_v1": ("video_generation", "pixel_millisecond", "pixel_millisecond"),
}
QUALITY_VALUES = frozenset({"low", "mid", "high"})
PRIORITY_VALUES = frozenset({"standard", "plus_20", "plus_50", "double"})


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} is invalid")
    return value


def _decimal(value: Any, name: str, *, positive: bool = False) -> str:
    if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
        raise ValueError(f"{name} must be a base-10 integer string")
    if len(value) > 1 and value.startswith("0"):
        raise ValueError(f"{name} must be canonical")
    if positive and value == "0":
        raise ValueError(f"{name} must be positive")
    return value


def _quality(value: Any) -> str:
    if value not in QUALITY_VALUES:
        raise ValueError("quality is invalid")
    return value


def validate_pricing_input(calculator_type: str, value: Mapping[str, Any]) -> dict[str, Any]:
    if calculator_type not in CALCULATOR_CONTRACTS or not isinstance(value, Mapping):
        raise ValueError("calculatorType is unsupported")
    item = dict(value)
    if calculator_type == "tts_v1":
        if set(item) != {"unicodeScalarCount", "speedBps", "customSampleUsed", "quality"}:
            raise ValueError("TTS pricingInput fields are invalid")
        _integer(item["unicodeScalarCount"], "unicodeScalarCount", minimum=1)
        _integer(item["speedBps"], "speedBps", minimum=1)
        if not isinstance(item["customSampleUsed"], bool):
            raise ValueError("customSampleUsed is invalid")
    elif calculator_type == "image_v1":
        if set(item) != {"inputPixels", "outputWidth", "outputHeight", "imageCount", "customReferenceUsed", "quality"}:
            raise ValueError("image pricingInput fields are invalid")
        _integer(item["inputPixels"], "inputPixels")
        for name in ("outputWidth", "outputHeight", "imageCount"):
            _integer(item[name], name, minimum=1)
        if not isinstance(item["customReferenceUsed"], bool):
            raise ValueError("customReferenceUsed is invalid")
    else:
        if set(item) != {"inputPixelMilliseconds", "outputWidth", "outputHeight", "outputDurationMs", "videoCount", "outputAudio", "customReferenceUsed", "quality"}:
            raise ValueError("video pricingInput fields are invalid")
        _decimal(item["inputPixelMilliseconds"], "inputPixelMilliseconds")
        for name in ("outputWidth", "outputHeight", "outputDurationMs", "videoCount"):
            _integer(item[name], name, minimum=1)
        for name in ("outputAudio", "customReferenceUsed"):
            if not isinstance(item[name], bool):
                raise ValueError(f"{name} is invalid")
    _quality(item["quality"])
    return item


def validate_actual_usage(calculator_type: str, value: Mapping[str, Any]) -> dict[str, Any]:
    if calculator_type not in CALCULATOR_CONTRACTS or not isinstance(value, Mapping):
        raise ValueError("calculatorType is unsupported")
    item = dict(value)
    if calculator_type == "tts_v1":
        if set(item) != {"outputDurationMs"}:
            raise ValueError("TTS actualUsage fields are invalid")
        _integer(item["outputDurationMs"], "outputDurationMs", minimum=1)
    elif calculator_type == "image_v1":
        if set(item) != {"outputPixels", "imageCount"}:
            raise ValueError("image actualUsage fields are invalid")
        _decimal(item["outputPixels"], "outputPixels", positive=True)
        _integer(item["imageCount"], "imageCount", minimum=1)
    else:
        if set(item) != {"outputPixelMilliseconds", "videoCount", "audioDurationMs"}:
            raise ValueError("video actualUsage fields are invalid")
        _decimal(item["outputPixelMilliseconds"], "outputPixelMilliseconds", positive=True)
        _decimal(item["audioDurationMs"], "audioDurationMs")
        _integer(item["videoCount"], "videoCount", minimum=1)
    return item


@dataclass(frozen=True, slots=True)
class MultimodalComputeQuote:
    id: str
    rate_card_id: str
    calculator_type: str
    pricing_input: dict[str, Any]
    bounded_usage: dict[str, Any]
    minimum_charge_minor: str
    maximum_charge_minor: str
    buyer_maximum_minor: str
    expires_at: str

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> "MultimodalComputeQuote":
        if not isinstance(value, Mapping):
            raise ValueError("Cloud quote is invalid")
        try:
            quote_id = str(UUID(str(value["id"])))
            rate_card_id = str(UUID(str(value["rateCardId"])))
        except (KeyError, ValueError) as error:
            raise ValueError("Cloud quote identity is invalid") from error
        calculator = value.get("calculatorType")
        pricing_input = validate_pricing_input(str(calculator), value.get("pricingInput"))
        bounded = value.get("boundedUsage")
        if not isinstance(bounded, Mapping):
            raise ValueError("Cloud quote boundedUsage is invalid")
        for name in ("minimumChargeMinor", "maximumChargeMinor", "buyerMaximumMinor"):
            _decimal(value.get(name), name, positive=True)
        expires_at = value.get("expiresAt")
        if not isinstance(expires_at, str) or not expires_at:
            raise ValueError("Cloud quote expiry is invalid")
        if value.get("consumedAt") is not None:
            raise ValueError("Cloud returned an already consumed quote")
        return cls(
            quote_id, rate_card_id, str(calculator), pricing_input, dict(bounded),
            str(value["minimumChargeMinor"]), str(value["maximumChargeMinor"]),
            str(value["buyerMaximumMinor"]), expires_at,
        )
