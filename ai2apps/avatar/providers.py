"""Use signed video contracts rather than model names in Mini-Apps."""

from __future__ import annotations

from ai2apps.model_providers import list_package_models


def avatar_models(runtime):
    result = []
    for model in list_package_models(runtime):
        contract = model.video_capabilities or {}
        if (
            model.model_type != "video_generation"
            or "avatar_video" not in model.capabilities
        ):
            continue
        combinations = contract.get("content_combinations", [])
        if any(
            {item.get("role") for item in combo.get("required", [])}
            == {"reference_image", "driving_audio"}
            for combo in combinations
        ):
            result.append(model)
    # Recommendation is Host policy; the Package never names a model.
    return tuple(
        sorted(
            result,
            key=lambda model: (
                model.id != "ai2apps.model.flashhead-mlx/lite",
                model.display_name,
                model.id,
            ),
        )
    )


def maximum_audio_seconds(model):
    # Total job quota; H3 executes bounded windows within this input duration.
    from ai2apps.video.tasks import MAX_INPUT_BYTES

    from .segmented_inference import supports_segments

    # Studio normalizes to mono PCM16 at 16 kHz. Reserve the WAV header so
    # advertised jobs also fit the existing Host/Worker multipart boundary.
    normalized_audio_limit = (MAX_INPUT_BYTES - 44) // (16_000 * 2)
    host_limit = min(3600, normalized_audio_limit) if supports_segments(model) else 600
    return min(host_limit, model.video_capabilities["duration"]["maximum_seconds"] or host_limit)


def describe_model(model, *, ready):
    contract = model.video_capabilities
    return {
        "id": model.id,
        "label": model.display_name,
        "ready": bool(ready),
        "operation": "portrait_animation",
        "presets": [
            {"id": p["id"], "label": p["display_name"]} for p in contract["presets"]
        ],
        "resolutions": ["source", *contract["geometry"]["resolutions"]],
        "minimumSeconds": contract["duration"]["minimum_seconds"],
        "maximumSeconds": maximum_audio_seconds(model),
        "defaults": {
            "preset": contract["defaults"]["preset"],
            "resolution": "source",
        },
    }


def plan_portrait(model, *, preset, resolution, duration):
    """Validate and freeze executable settings before enqueueing a render."""
    contract = model.video_capabilities
    preset = preset or contract["defaults"]["preset"]
    resolution = resolution or "source"
    source_canvas = resolution == "source"
    if source_canvas:
        resolution = contract["defaults"]["resolution"]
    if preset not in {p["id"] for p in contract["presets"]}:
        raise ValueError("所选模型不支持此生成模式")
    if resolution not in contract["geometry"]["resolutions"]:
        raise ValueError("所选模型不支持此分辨率")
    bounds = contract["duration"]
    maximum = maximum_audio_seconds(model)
    if not bounds["minimum_seconds"] <= duration <= maximum:
        raise ValueError(
            f"音频时长须在 {bounds['minimum_seconds']:g} 至 {maximum:g} 秒之间"
        )
    return {
        "model": model.id,
        "preset": preset,
        "resolution": resolution,
        "avatar_output_mode": "source" if source_canvas else "crop",
    }
