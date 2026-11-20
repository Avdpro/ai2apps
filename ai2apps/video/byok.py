"""Direct, user-keyed video generation providers for Video Studio.

This catalog is deliberately separate from AI2Apps Cloud model routing.  Keys
stay in the instance's SecretBackend and never enter a task or API response.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from ai2apps.model_providers import PackageModel

PROVIDERS = {
    "minimax": {
        "name": "MiniMax H3 API",
        "model": "MiniMax-H3",
        "id": "byok/minimax/MiniMax-H3",
        "origin": "https://api.minimax.io",
        "models": (
            {"name": "MiniMax H3", "model": "MiniMax-H3", "tiers": ("768P", "2K")},
            {"name": "MiniMax H3 Highspeed", "model": "MiniMax-H3-Highspeed", "tiers": ("480P", "768P")},
            {"name": "MiniMax H3 Lite", "model": "MiniMax-H3-Lite", "tiers": ("480P", "768P")},
            {"name": "MiniMax H3 Max", "model": "MiniMax-H3-Max", "tiers": ("480P", "768P"), "minimum": 5},
        ),
        "resolutions": ("1366x768", "768x1366"),
        "default_resolution": "1366x768",
        "minimum": 4,
        "maximum": 15,
    },
    "volcengine": {
        "name": "火山引擎 Seedance 2.5 API",
        "model": "doubao-seedance-2-5-260628",
        "id": "byok/volcengine/doubao-seedance-2-5-260628",
        "models": (
            {"name": "Seedance 2.5", "model": "doubao-seedance-2-5-260628",
             "resolutions": ("854x480", "480x854", "1280x720", "720x1280",
                             "1920x1080", "1080x1920", "3840x2160", "2160x3840")},
            {"name": "Seedance 2.5 Flash", "model": "doubao-seedance-2-5-flash-261115",
             "resolutions": ("854x480", "480x854", "1280x720", "720x1280")},
        ),
        "origin": "https://ark.cn-beijing.volces.com",
        "resolutions": ("1280x720", "720x1280"),
        "default_resolution": "1280x720",
        "minimum": 4,
        "maximum": 30,
    },
}
MAX_OUTPUT_BYTES = 2 * 1024 * 1024 * 1024
MAX_MINIMAX_BODY_BYTES = 64 * 1024 * 1024
MINIMAX_TIER_RESOLUTIONS = {
    "480P": ("854x480", "480x854"),
    "768P": ("1366x768", "768x1366"),
    "2K": ("2048x1152", "1152x2048"),
}

# Official Seedance 2.5 output geometry, indexed by tier and ratio. MiniMax's
# API specifies tiers rather than guaranteed pixel dimensions; do not invent
# corresponding pixel presets for its other aspect ratios.
SEEDANCE_GEOMETRY = {
    '480p': {'16:9': '854x480', '4:3': '752x560', '1:1': '640x640', '3:4': '560x752', '9:16': '480x854', '21:9': '992x432'},
    '720p': {'16:9': '1280x720', '4:3': '1112x834', '1:1': '960x960', '3:4': '834x1112', '9:16': '720x1280', '21:9': '1470x630'},
    '1080p': {'16:9': '1920x1080', '4:3': '1664x1248', '1:1': '1440x1440', '3:4': '1248x1664', '9:16': '1080x1920', '21:9': '2206x946'},
    '4k': {'16:9': '3840x2160', '4:3': '3326x2494', '1:1': '2880x2880', '3:4': '2494x3326', '9:16': '2160x3840', '21:9': '4398x1886'},
}
SEEDANCE_RESOLUTIONS = {value: (tier, ratio) for tier, ratios in SEEDANCE_GEOMETRY.items() for ratio, value in ratios.items()}


def provider_for_model(model_id: str) -> str | None:
    return next((provider for provider, spec in PROVIDERS.items()
                 if any(f"byok/{provider}/{item['model']}" == model_id
                        for item in spec.get("models", ({"model": spec["model"]},)))), None)


def _secret_key(provider: str, actor_id: str) -> str:
    if actor_id.startswith("ai2apps-user:"):
        actor_id = actor_id[len("ai2apps-user:"):]
    actor = hashlib.sha256(actor_id.encode("utf-8")).hexdigest()[:32]
    return f"video-byok-{provider}-{actor}-api-key"


def configured(runtime: Any, provider: str, actor_id: str) -> bool:
    try:
        return bool(runtime.model_manager.secret_backend.load(_secret_key(provider, actor_id)))
    except Exception:
        return False


def credential(runtime: Any, provider: str, actor_id: str) -> str:
    from ai2apps.video.tasks import VideoGenerationError

    try:
        value = runtime.model_manager.secret_backend.load(_secret_key(provider, actor_id))
    except Exception:
        value = ""
    if not value:
        raise VideoGenerationError("byok_key_missing", "Configure this provider's API key in Video Studio", status_code=503)
    return value


def set_credential(runtime: Any, provider: str, actor_id: str, api_key: str) -> None:
    if provider not in PROVIDERS:
        raise ValueError("Unknown video API provider")
    key = api_key.strip()
    if not key or len(key) > 4096 or any(char.isspace() for char in key):
        raise ValueError("API key must be a non-empty token without spaces")
    runtime.model_manager.secret_backend.store(_secret_key(provider, actor_id), key)
    if getattr(runtime, "cloud", None) is not None and getattr(runtime, "config", None) is not None:
        from ai2apps.credential_import import service, account_id, origin
        service(runtime).mark_owner({"actor_id": actor_id, "user_id": account_id(actor_id),
                                     "cloud_origin": origin(runtime.cloud.base_url)}, "video:" + provider)


def clear_credential(runtime: Any, provider: str, actor_id: str) -> None:
    if provider not in PROVIDERS:
        raise ValueError("Unknown video API provider")
    runtime.model_manager.secret_backend.delete(_secret_key(provider, actor_id))


def catalog_model(runtime: Any, provider: str, actor_id: str, model_id: str | None = None) -> PackageModel:
    spec = PROVIDERS[provider]
    variants = spec.get("models", ({"name": spec["name"], "model": spec["model"]},))
    selected = next((item for item in variants
                     if f"byok/{provider}/{item['model']}" == (model_id or spec["id"])), None)
    if selected is None:
        raise ValueError("Unknown video API model")
    resolutions = (tuple(value for tier in selected["tiers"] for value in MINIMAX_TIER_RESOLUTIONS[tier])
                   if provider == "minimax" else selected.get("resolutions", spec["resolutions"]))
    if provider == 'volcengine':
        tiers = ('480p', '720p') if 'flash' in selected['model'] else tuple(SEEDANCE_GEOMETRY)
        resolutions = tuple(value for tier in tiers for value in SEEDANCE_GEOMETRY[tier].values())
    combinations = [{"id": "text_to_video", "required": [{"type": "text", "role": "prompt", "min": 1, "max": 1}], "optional": []}]
    if provider == "minimax":
        prompt = {"type": "text", "role": "prompt", "min": 1, "max": 1}
        combinations.extend([
            {"id": "image_to_video", "required": [prompt], "optional": [
                {"type": "image_url", "role": "first_frame", "min": 0, "max": 1},
                {"type": "image_url", "role": "last_frame", "min": 0, "max": 1}]},
            {"id": "reference_to_video", "required": [prompt], "optional": [
                {"type": "image_url", "role": "reference_image", "min": 0, "max": 9},
                {"type": "video_url", "role": "reference_video", "min": 0, "max": 3},
                {"type": "audio_url", "role": "reference_audio", "min": 0, "max": 3}]},
        ])
    if provider == "volcengine":
        prompt = {"type": "text", "role": "prompt", "min": 1, "max": 1}
        combinations.extend([
            {"id": "image_to_video", "required": [prompt,
                {"type": "image_url", "role": "first_frame", "min": 1, "max": 1}],
             "optional": [{"type": "image_url", "role": "last_frame", "min": 0, "max": 1}]},
            {"id": "reference_to_video", "required": [prompt], "optional": [
                {"type": "image_url", "role": "reference_image", "min": 0, "max": 9},
                {"type": "video_url", "role": "reference_video", "min": 0, "max": 3},
                {"type": "audio_url", "role": "reference_audio", "min": 0, "max": 3}]},
        ])
    caps = {
        "schema": "ai2apps.video-capabilities/v1",
        "operations": ["video_generation"],
        "content_combinations": combinations,
        "geometry": {"resolutions": list(resolutions),
                     "ratios": ["21:9", "16:9", "4:3", "1:1", "3:4", "9:16"], "framespersecond": [24]},
        "duration": {"mode": "requested", "minimum_seconds": selected.get("minimum", spec["minimum"]),
                     "maximum_seconds": spec["maximum"]},
        "media_limits": {"reference_duration_seconds": 30 if provider == "volcengine" else 15},
        "presets": [{"id": "standard", "display_name": "Standard"}],
        "defaults": {"resolution": ("1366x768" if provider == "minimax" else spec["default_resolution"]), "ratio": "16:9", "framespersecond": 24,
                     "preset": "standard", "seed": 42, "output_format": "mp4"},
    }
    return PackageModel(
        id=f"byok/{provider}/{selected['model']}", display_name=f"火山引擎 {selected['name']} API" if provider == "volcengine" else selected["name"],
        model_type="video_generation", upstream_id=selected["model"],
        capabilities=("video_generation", "text_to_video", "image_to_video", "reference_to_video"), endpoints={},
        context_window=None, metadata={"source": "byok", "provider": provider,
            "resolutionOptions": [
                {"value": value, "label": f"{SEEDANCE_RESOLUTIONS[value][0]} · {value} · {SEEDANCE_RESOLUTIONS[value][1]}"}
                for value in resolutions
            ] if provider == 'volcengine' else [
                {"value": MINIMAX_TIER_RESOLUTIONS[tier][0], "label": tier} for tier in selected['tiers']
            ],
            "resolutionSemantics": "tier-and-ratio" if provider == 'minimax' else "documented-pixels",
        },
        audio_capabilities=None, video_capabilities=caps, image_capabilities=None,
        service_key=f"byok.{provider}", provider_key=provider, endpoint=None,
        checkpoint_ready=configured(runtime, provider, actor_id),
    )


def catalog(runtime: Any, actor_id: str) -> list[PackageModel]:
    return [catalog_model(runtime, provider, actor_id, f"byok/{provider}/{item['model']}")
            for provider, spec in PROVIDERS.items()
            for item in spec.get("models", ({"model": spec["model"]},))]


def _request_body(provider: str, model: PackageModel, request: dict[str, Any],
                  media_content: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    duration = request.get("duration")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or int(duration) != duration:
        raise ValueError("API video duration must be a whole number of seconds")
    ratio = request.get("ratio")
    if ratio not in model.video_capabilities["geometry"]["ratios"]:
        raise ValueError("API video ratio is not supported by this model")
    prompt = str(request["prompt"])
    if provider == "minimax" and len(prompt) > 7000:
        raise ValueError("MiniMax H3 prompt must be at most 7000 characters")
    content = [{"type": "text", "text": prompt}, *(media_content or [])]
    if provider == "minimax":
        resolution = request.get("resolution") or model.video_capabilities["defaults"]["resolution"]
        if resolution not in model.video_capabilities["geometry"]["resolutions"]:
            raise ValueError("resolution is not supported by this model")
        tier = next(tier for tier, values in MINIMAX_TIER_RESOLUTIONS.items() if resolution in values)
        if not model.video_capabilities["duration"]["minimum_seconds"] <= duration <= 15:
            raise ValueError("duration is not supported by this model")
        roles = {item.get("role") for item in media_content or []}
        if roles & {"first_frame", "last_frame"} and roles & {"reference_image", "reference_video", "reference_audio"}:
            raise ValueError("first/last frames cannot be mixed with reference media")
        return {"model": model.upstream_id, "content": content, "duration": int(duration),
                "resolution": tier, "ratio": "adaptive" if roles & {"first_frame", "last_frame"} else ratio,
                "generate_audio": True}
    resolution = request.get("resolution") or model.video_capabilities["defaults"]["resolution"]
    if resolution not in model.video_capabilities["geometry"]["resolutions"]:
        raise ValueError("resolution is not supported by this model")
    tier, geometry_ratio = SEEDANCE_RESOLUTIONS[resolution]
    if ratio != geometry_ratio:
        raise ValueError('Selected Seedance dimensions and aspect ratio disagree')
    roles = {item.get("role") for item in media_content or []}
    if roles & {"first_frame", "last_frame"}:
        if "first_frame" not in roles:
            raise ValueError("Seedance requires a first frame when using keyframes")
        if roles & {"reference_image", "reference_video", "reference_audio"}:
            raise ValueError("first/last frames cannot be mixed with reference media")
    body = {"model": model.upstream_id, "content": content, "duration": int(duration),
            "resolution": tier,
            "ratio": "adaptive" if roles & {"first_frame", "last_frame"} else ratio,
            "generate_audio": True}
    if roles & {"reference_image", "reference_video", "reference_audio"}:
        task_type = request.get("omni_reference_task_type", "reference")
        if task_type not in {"reference", "edit", "extend"}:
            raise ValueError("Seedance task type must be reference, edit, or extend")
        if task_type in {"edit", "extend"}:
            if "reference_video" not in roles:
                raise ValueError("Seedance editing and extension require a reference video")
            body["ratio"] = "adaptive"
            if task_type == "edit":
                body["duration"] = -1
        body["omni_reference_task_type"] = task_type
    elif request.get("omni_reference_task_type") is not None:
        raise ValueError("Seedance task type requires reference media")
    return body


def _minimax_media_content(request: dict[str, Any], manifest: list[dict[str, Any]],
                           task_root: Path, provider: str = "minimax") -> list[dict[str, Any]]:
    """Read private frozen inputs only; never create a public media URL."""
    from ai2apps.video.tasks import VideoGenerationError

    roles = {"first_frame": ("image_url", "first_frame"),
             "last_frame": ("image_url", "last_frame")}
    for item in request.get("reference_parts", []):
        if isinstance(item, dict) and item.get("kind") in {"image", "video", "audio"}:
            kind = item["kind"]
            roles[item["part_name"]] = (f"{kind}_url", f"reference_{kind}")
    allowed_types = {
        "image_url": {"image/png", "image/jpeg", "image/webp"},
        "video_url": {"video/mp4", "video/quicktime"},
        "audio_url": {"audio/wav", "audio/mpeg"},
    }
    size_limits = {"image_url": 30, "video_url": 50, "audio_url": 15}
    content = []
    root = task_root.resolve()
    for item in manifest:
        part_name = item.get("part_name")
        if part_name not in roles:
            raise VideoGenerationError("unsupported_content", "Unsupported MiniMax media role")
        item_type, role = roles[part_name]
        media_type = str(item.get("media_type") or "")
        if media_type not in allowed_types[item_type]:
            raise VideoGenerationError("unsupported_media_type", f"MiniMax does not support {media_type}")
        path = (root / str(item.get("path") or "")).resolve()
        if root not in path.parents or not path.is_file():
            raise VideoGenerationError("input_unavailable", "Frozen media input is unavailable")
        if item_type != "video_url" and path.stat().st_size > size_limits[item_type] * 1024 * 1024:
            raise VideoGenerationError("input_too_large", "Media exceeds MiniMax's per-file limit", status_code=413)
        if provider == "minimax" and path.stat().st_size > size_limits[item_type] * 1024 * 1024:
            raise VideoGenerationError("input_too_large", "Media exceeds MiniMax's per-file limit", status_code=413)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != item.get("sha256"):
            raise VideoGenerationError("input_changed", "Frozen media input changed")
        if provider == "volcengine" and item_type == "video_url":
            url = item.get("source_url")
            if url is None:
                url = f"local-video://{part_name}"
            else:
                parsed = urlparse(url) if isinstance(url, str) else None
                if not parsed or parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                    raise VideoGenerationError("unsupported_content", "Seedance reference video URL must be public HTTPS")
        else:
            url = f"data:{media_type};base64,{base64.b64encode(data).decode('ascii')}"
        content.append({"type": item_type, item_type: {"url": url}, "role": role})
    return content


def _error(response: httpx.Response, key: str) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get("error") if isinstance(payload, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    return str(message or f"Provider returned HTTP {response.status_code}").replace(key, "[redacted]")[:300]


async def generate(
    runtime: Any, model: PackageModel, request: dict[str, Any], output: Path,
    *, actor_id: str, cancelled: Any, progress: Any,
    manifest: list[dict[str, Any]] | None = None, task_root: Path | None = None,
    task_id: str | None = None,
) -> None:
    """Submit and poll the vendor directly; never use AI2Apps Cloud fallback."""
    from ai2apps.video.tasks import VideoGenerationError, _public_address

    provider = provider_for_model(model.id)
    if provider is None:
        raise VideoGenerationError("model_not_found", "Unknown BYOK model")
    spec = PROVIDERS[provider]
    key = credential(runtime, provider, actor_id)
    try:
        if manifest and task_root is None:
            raise VideoGenerationError("input_unavailable", "Frozen media directory is unavailable")
        media_content = (await asyncio.to_thread(_minimax_media_content, request, manifest, task_root, provider)
                         if manifest else [])
        if provider == "volcengine":
            from ai2apps.video.temporary_input import issue
            parts = {item["part_name"]: item for item in manifest or []}
            for item in media_content:
                if item["type"] == "video_url" and item["video_url"]["url"].startswith("local-video://"):
                    if task_id is None or task_root is None:
                        raise VideoGenerationError("input_unavailable", "Video task identity is unavailable")
                    part_name = item["video_url"]["url"].removeprefix("local-video://")
                    item["video_url"]["url"] = issue(runtime, task_id, task_root, parts[part_name])
        body = _request_body(provider, model, request, media_content)
        if len(json.dumps(body, ensure_ascii=False).encode("utf-8")) > MAX_MINIMAX_BODY_BYTES:
            raise VideoGenerationError("request_too_large", "Provider request exceeds 64 MiB; use smaller media", status_code=413)
    except (KeyError, ValueError) as exc:
        raise VideoGenerationError("unsupported_parameter", str(exc)) from exc
    origin = spec["origin"]
    create_path = "/v2/video_generation" if provider == "minimax" else "/api/v3/contents/generations/tasks"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60, trust_env=False, follow_redirects=False) as client:
        try:
            if cancelled():
                raise VideoGenerationError("generation_cancelled", "Video generation cancelled")
            response = await client.post(origin + create_path, headers=headers, json=body)
            if response.status_code >= 400:
                raise VideoGenerationError("provider_request_failed", _error(response, key), status_code=502)
            created = response.json()
            if not isinstance(created, dict):
                raise VideoGenerationError("provider_response_invalid", "Provider returned an invalid response", status_code=502)
            base_resp = created.get("base_resp") if isinstance(created, dict) else None
            if isinstance(base_resp, dict) and base_resp.get("status_code") not in {None, 0}:
                raise VideoGenerationError(
                    "provider_request_failed",
                    str(base_resp.get("status_msg") or "Provider rejected video task").replace(key, "[redacted]")[:300],
                    status_code=502,
                )
            remote_id = created.get("task_id") if provider == "minimax" else created.get("id")
            if not isinstance(remote_id, str) or not remote_id:
                raise VideoGenerationError("provider_response_invalid", "Provider did not return a task ID", status_code=502)
            progress({"phase": "provider_generate", "current": 0, "total": 1})
            for _ in range(180):  # Up to 30 minutes; provider gives no reliable percent.
                if cancelled():
                    raise VideoGenerationError("generation_cancelled", "Video generation cancelled")
                await asyncio.sleep(10)
                query_path = (f"/v2/query/video_generation/{remote_id}" if provider == "minimax"
                              else f"/api/v3/contents/generations/tasks/{remote_id}")
                response = await client.get(origin + query_path, headers=headers)
                if response.status_code >= 400:
                    raise VideoGenerationError("provider_query_failed", _error(response, key), status_code=502)
                data = response.json()
                if not isinstance(data, dict):
                    raise VideoGenerationError("provider_response_invalid", "Provider returned an invalid task", status_code=502)
                task = data.get("task", {}) if provider == "minimax" else data
                if not isinstance(task, dict):
                    raise VideoGenerationError("provider_response_invalid", "Provider returned an invalid task", status_code=502)
                status = task.get("status")
                if status in {"failed", "cancelled"}:
                    raise VideoGenerationError("provider_generation_failed", "Provider video task failed", status_code=502)
                if status == "succeeded":
                    content = task.get("content") or {}
                    video_url = content.get("url") if provider == "minimax" else content.get("video_url")
                    if not isinstance(video_url, str):
                        raise VideoGenerationError("provider_response_invalid", "Provider returned no video URL", status_code=502)
                    break
            else:
                raise VideoGenerationError("provider_timeout", "Provider video task timed out", status_code=504)
            progress({"phase": "download", "current": 0, "total": 1})
            current = video_url
            for _ in range(6):
                parsed = urlparse(current)
                if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
                    raise VideoGenerationError("unsafe_output_url", "Provider output URL must be public HTTPS")
                _public_address(parsed.hostname, parsed.port or 443)
                async with client.stream("GET", current) as stream:
                    if stream.is_redirect:
                        location = stream.headers.get("location")
                        if not location:
                            raise VideoGenerationError("provider_download_failed", "Output redirect has no location")
                        current = urljoin(current, location)
                        continue
                    if stream.status_code != 200:
                        raise VideoGenerationError("provider_download_failed", f"Output download returned HTTP {stream.status_code}")
                    count = 0
                    with output.open("wb") as handle:
                        async for chunk in stream.aiter_bytes():
                            if cancelled():
                                raise VideoGenerationError("generation_cancelled", "Video generation cancelled")
                            count += len(chunk)
                            if count > MAX_OUTPUT_BYTES:
                                raise VideoGenerationError("provider_output_too_large", "Video exceeds 2 GiB")
                            handle.write(chunk)
                    if count == 0:
                        raise VideoGenerationError("provider_response_invalid", "Provider returned an empty video")
                    return
            raise VideoGenerationError("provider_download_failed", "Output redirected too many times")
        except httpx.HTTPError as exc:
            raise VideoGenerationError("provider_unavailable", "Video provider is unavailable", status_code=502) from exc
