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
        "resolutions": list(contract["geometry"]["resolutions"]),
        "minimumSeconds": contract["duration"]["minimum_seconds"],
        "maximumSeconds": contract["duration"]["maximum_seconds"],
        "defaults": {
            "preset": contract["defaults"]["preset"],
            "resolution": contract["defaults"]["resolution"],
        },
    }


def plan_portrait(model, *, preset, resolution, duration):
    """Validate and freeze executable settings before enqueueing a render."""
    contract = model.video_capabilities
    preset = preset or contract["defaults"]["preset"]
    resolution = resolution or contract["defaults"]["resolution"]
    if preset not in {p["id"] for p in contract["presets"]}:
        raise ValueError("所选模型不支持此生成模式")
    if resolution not in contract["geometry"]["resolutions"]:
        raise ValueError("所选模型不支持此分辨率")
    bounds = contract["duration"]
    # Bound Host audio decoding even when the provider supports unbounded segments.
    maximum = min(600, bounds["maximum_seconds"] or 600)
    if not bounds["minimum_seconds"] <= duration <= maximum:
        raise ValueError(
            f"音频时长须在 {bounds['minimum_seconds']:g} 至 {maximum:g} 秒之间"
        )
    return {"model": model.id, "preset": preset, "resolution": resolution}
