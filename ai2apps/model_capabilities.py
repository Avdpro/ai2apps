"""Shared provider capability normalization for model routing and Studio catalogs."""
import re
from typing import Any


def cloud_model_capabilities(model: dict[str, Any]) -> set[str]:
    """Normalize provider metadata and conservative name hints for routing."""

    raw = model.get("capabilities")
    capabilities = {
        re.sub(r"(?<!^)(?=[A-Z])", "_", str(key)).lower().replace("-", "_")
        for key, enabled in (raw.items() if isinstance(raw, dict) else [])
        if enabled
    }
    if isinstance(raw, (list, tuple)):
        capabilities.update(str(value).lower().replace("-", "_") for value in raw)
    if capabilities.intersection({"image_input", "vision", "multimodal"}):
        capabilities.add("image_recognition")
    if isinstance(raw, dict) and raw.get("imageInput"):
        capabilities.add("image_recognition")
    text = " ".join(
        str(model.get(key) or "").lower() for key in ("id", "name")
    )
    if any(token in text for token in ("gpt-image", "dall-e", "imagen", "flux")):
        capabilities.add("image_generation")
    if any(token in text for token in ("sora", "veo", "video-generation", "video_gen")):
        capabilities.add("video_generation")
    if any(token in text for token in ("whisper", "transcribe", "speech-to-text", "asr")):
        capabilities.add("speech_recognition")
    if any(
        token in text
        for token in ("vision", "-vl", "gemini", "claude", "gpt-4", "gpt-5", "gpt-6")
    ):
        capabilities.add("image_recognition")
    if not capabilities.intersection(
        {"image_generation", "video_generation", "speech_recognition"}
    ):
        capabilities.add("work")
    return capabilities
