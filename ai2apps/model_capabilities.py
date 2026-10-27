"""Shared provider capability normalization for model routing and Studio catalogs."""
import re
from typing import Any


def agent_model_eligible(model: dict[str, Any]) -> bool:
    """Require catalog declarations; never infer suitability from a model name."""
    if any(model.get(key) for key in ("is_hidden", "is_helper")) or model.get("checkpoint_ready") is False:
        return False
    raw = model.get("capabilities") or []
    flags = {key for key, value in raw.items() if value is True} if isinstance(raw, dict) else set(raw)
    return (bool(flags & {"work_standard", "work_complex"}) and "tool_calling_reliable" in flags
            and str(model.get("model_type") or "").lower() in {"llm", "vlm", ""})


def agent_model_selectable(model: dict[str, Any]) -> bool:
    """Manual selection permits unknown quality, but never non-chat/hidden models."""
    return (not any(model.get(key) for key in ('is_hidden', 'is_helper'))
            and model.get('checkpoint_ready') is not False
            and model.get('source_type') != 'hf_cache'
            and str(model.get('model_type') or '').lower() in {'llm', 'vlm', ''})


def agent_capability_summary(model: dict[str, Any]) -> dict[str, Any]:
    """Report affirmative declarations and missing evidence, never infer quality."""
    raw = model.get('capabilities') or []
    if isinstance(raw, dict):
        raw = {re.sub(r'(?<!^)(?=[A-Z])', '_', str(key)).lower().replace('-', '_'): value for key, value in raw.items()}
    keys = ('work_standard', 'work_complex', 'tool_calling_reliable')
    def declared(key):
        if isinstance(raw, dict):
            value = raw.get(key)
            return value if isinstance(value, bool) else None
        return True if key in raw else None
    values = {key: declared(key) for key in keys}
    complete = (values['work_standard'] is True or values['work_complex'] is True) and values['tool_calling_reliable'] is True
    status = 'qualified' if complete else 'declared_insufficient' if any(v is not None for v in values.values()) else 'undeclared'
    return {'status': status, 'declarations': values, 'automatic_eligible': agent_model_eligible({**model, 'capabilities': raw})}


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
    if isinstance(raw, dict):
        # Quality claims must be literal affirmative declarations, not arbitrary
        # truthy strings/objects (for example "tool_calling_reliable": "unknown").
        for key in ("work_standard", "work_complex", "tool_calling_reliable"):
            declared = next((value for name, value in raw.items()
                            if re.sub(r"(?<!^)(?=[A-Z])", "_", str(name)).lower().replace("-", "_") == key), None)
            if declared is not True:
                capabilities.discard(key)
    if capabilities.intersection({"image_input", "vision", "multimodal"}):
        capabilities.add("image_recognition")
    if isinstance(raw, dict) and raw.get("imageInput"):
        capabilities.add("image_recognition")
    text = " ".join(
        str(model.get(key) or "").lower() for key in ("id", "name")
    )
    if any(token in text for token in ("gpt-image", "dall-e", "imagen", "flux")):
        capabilities.add("image_generation")
    # GPT Image supports reference-image editing as well as text-to-image.
    # An explicit capability declaration remains authoritative (including false).
    model_id = str(model.get("id") or "").lower().rsplit("/", 1)[-1]
    explicit_edit = isinstance(raw, dict) and any(k in raw for k in ("imageEdit", "image_edit", "image-edit"))
    if not explicit_edit and (model_id.startswith("gpt-image-") or model_id == "chatgpt-image-latest"):
        capabilities.add("image_edit")
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
