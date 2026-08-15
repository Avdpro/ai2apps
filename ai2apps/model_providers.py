"""Installable Service-backed model provider contracts and routing helpers.

Model weights deliberately remain outside the Package archive.  An installed
Service owns its runtime and may advertise one or more OpenAI-compatible model
IDs through ``service.yaml``.  The platform keeps model selection and default
role routing independent from the provider implementation.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse

from ai2apps.services import ServiceInstanceStatus, ServiceStatus

MODEL_TYPES = frozenset(
    {
        "llm",
        "vlm",
        "image_generation",
        "audio_stt",
        "audio_tts",
        "audio_processing",
        "video_generation",
    }
)

DEFAULT_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "llm": ("work", "conversation"),
    "vlm": ("work", "conversation", "image_recognition"),
    "image_generation": ("image_generation",),
    "audio_stt": ("speech_recognition",),
    "audio_tts": ("speech_generation",),
    "audio_processing": ("audio_processing",),
    "video_generation": ("video_generation",),
}

DEFAULT_PATHS = {
    "chat_completions": "/v1/chat/completions",
    "responses": "/v1/responses",
    "image_generation": "/v1/images/generations",
    "image_edit": "/v1/images/edits",
    "audio_transcription": "/v1/audio/transcriptions",
    "audio_speech": "/v1/audio/speech",
    "audio_process": "/v1/audio/process",
    "video_generation": "/v1/videos/generations",
}

_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
_CAPABILITY = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")


class ModelProviderContractError(ValueError):
    pass


def validate_package_models(
    service_key: str,
    models: Any,
    *,
    runtime_mode: str,
    protocol: str,
) -> tuple[dict[str, Any], ...]:
    """Validate and normalize the ``service.yaml.models`` declaration."""

    if models is None:
        return ()
    if not isinstance(models, list) or len(models) > 128:
        raise ModelProviderContractError("models must be an array of at most 128 entries")
    if models and runtime_mode in {"embedded", "in_process"}:
        raise ModelProviderContractError(
            "Model providers must use a managed_process or external HTTP runtime"
        )
    if models and protocol not in {"openai-compatible", "http-json"}:
        raise ModelProviderContractError(
            "Model providers require openai-compatible or http-json protocol"
        )

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    prefix = service_key + "/"
    for index, raw in enumerate(models):
        if not isinstance(raw, dict):
            raise ModelProviderContractError(f"models[{index}] must be an object")
        model_id = raw.get("id")
        if (
            not isinstance(model_id, str)
            or not _MODEL_ID.fullmatch(model_id)
            or not model_id.startswith(prefix)
        ):
            raise ModelProviderContractError(
                f"models[{index}].id must start with {prefix!r}"
            )
        if model_id in seen:
            raise ModelProviderContractError(f"Duplicate model id: {model_id}")
        seen.add(model_id)
        model_type = raw.get("model_type", raw.get("type"))
        if model_type not in MODEL_TYPES:
            raise ModelProviderContractError(
                f"models[{index}].model_type is unsupported: {model_type!r}"
            )
        display_name = raw.get("display_name", raw.get("name", model_id))
        if not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 160:
            raise ModelProviderContractError(f"models[{index}].display_name is invalid")
        upstream_id = raw.get("upstream_id", model_id)
        if not isinstance(upstream_id, str) or not upstream_id or len(upstream_id) > 512:
            raise ModelProviderContractError(f"models[{index}].upstream_id is invalid")
        capabilities = raw.get("capabilities", DEFAULT_CAPABILITIES[model_type])
        if (
            not isinstance(capabilities, (list, tuple))
            or not capabilities
            or not all(isinstance(value, str) and _CAPABILITY.fullmatch(value) for value in capabilities)
        ):
            raise ModelProviderContractError(f"models[{index}].capabilities is invalid")
        paths = raw.get("endpoints", raw.get("paths", {}))
        if not isinstance(paths, dict) or set(paths) - set(DEFAULT_PATHS):
            raise ModelProviderContractError(f"models[{index}].endpoints is invalid")
        normalized_paths = dict(DEFAULT_PATHS)
        for operation, path in paths.items():
            if (
                not isinstance(path, str)
                or not path.startswith("/")
                or "//" in path
                or ".." in path.split("/")
                or len(path) > 240
            ):
                raise ModelProviderContractError(
                    f"models[{index}].endpoints.{operation} is invalid"
                )
            normalized_paths[operation] = path
        context_window = raw.get("context_window")
        if context_window is not None and (
            not isinstance(context_window, int)
            or isinstance(context_window, bool)
            or context_window <= 0
        ):
            raise ModelProviderContractError(f"models[{index}].context_window is invalid")
        normalized.append(
            {
                "id": model_id,
                "display_name": display_name.strip(),
                "model_type": model_type,
                "upstream_id": upstream_id,
                "capabilities": sorted(set(capabilities)),
                "endpoints": normalized_paths,
                "context_window": context_window,
                "metadata": raw.get("metadata", {}) if isinstance(raw.get("metadata", {}), dict) else {},
            }
        )
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class PackageModel:
    id: str
    display_name: str
    model_type: str
    upstream_id: str
    capabilities: tuple[str, ...]
    endpoints: Mapping[str, str]
    context_window: int | None
    metadata: Mapping[str, Any]
    service_key: str
    provider_key: str
    endpoint: str

    def public_catalog_entry(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "model_path": f"package://{self.service_key}/{self.id}",
            "loaded": True,
            "is_loading": False,
            "estimated_size": 0,
            "estimated_size_formatted": "0 B",
            "actual_size": 0,
            "actual_size_formatted": None,
            "pinned": False,
            "is_default": False,
            "is_hidden": False,
            "is_favorite": False,
            "is_helper": False,
            "engine_type": "package",
            "model_type": self.model_type,
            "config_model_type": "package_provider",
            "capabilities": list(self.capabilities),
            "cache_moe": False,
            "source_type": "package",
            "source_repo_id": None,
            "virtual": True,
            "owned_by": self.service_key,
            "model_context_length": self.context_window,
            "max_context_window": self.context_window,
            "package_service": self.service_key,
        }


def list_package_models(runtime: Any | None) -> tuple[PackageModel, ...]:
    if runtime is None or getattr(runtime, "services", None) is None:
        return ()
    result: list[PackageModel] = []
    for service in runtime.services.list_services():
        if service.source != "installed" or service.status is not ServiceStatus.ENABLED:
            continue
        try:
            instance = runtime.services.get_instance_for_service(service.id)
        except Exception:
            continue
        if instance.status not in {
            ServiceInstanceStatus.RUNNING,
            ServiceInstanceStatus.DEGRADED,
        } or not instance.endpoint:
            continue
        for raw in service.config.get("models", []):
            result.append(
                PackageModel(
                    id=raw["id"],
                    display_name=raw["display_name"],
                    model_type=raw["model_type"],
                    upstream_id=raw["upstream_id"],
                    capabilities=tuple(raw["capabilities"]),
                    endpoints=dict(raw["endpoints"]),
                    context_window=raw.get("context_window"),
                    metadata=dict(raw.get("metadata", {})),
                    service_key=service.service_key,
                    provider_key=instance.provider_key,
                    endpoint=instance.endpoint.rstrip("/"),
                )
            )
    return tuple(sorted(result, key=lambda item: item.id))


def resolve_package_model(runtime: Any | None, model_id: str) -> PackageModel | None:
    return next((model for model in list_package_models(runtime) if model.id == model_id), None)


def _response_headers(response: httpx.Response) -> dict[str, str]:
    accepted = {"content-type", "content-disposition", "cache-control", "x-request-id"}
    return {key: value for key, value in response.headers.items() if key.lower() in accepted}


async def proxy_package_json(
    model: PackageModel,
    operation: str,
    payload: Mapping[str, Any],
) -> Response:
    path = model.endpoints.get(operation)
    if not path:
        raise HTTPException(status_code=400, detail=f"Model does not support {operation}")
    body = dict(payload)
    body["model"] = model.upstream_id
    # Provider endpoints are platform-managed loopback addresses. Inheriting
    # HTTP_PROXY/HTTPS_PROXY can send these private calls to a system proxy,
    # producing synthetic 502/503 responses that never reach the Service.
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(300.0, connect=15.0), trust_env=False
    )
    request = client.build_request("POST", model.endpoint + path, json=body)
    try:
        response = await client.send(request, stream=bool(body.get("stream")))
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"Model provider request failed: {exc}") from exc
    if body.get("stream"):
        async def chunks():
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        return StreamingResponse(
            chunks(),
            status_code=response.status_code,
            media_type=response.headers.get("content-type"),
            headers=_response_headers(response),
        )
    content = await response.aread()
    headers = _response_headers(response)
    status = response.status_code
    await response.aclose()
    await client.aclose()
    return Response(content=content, status_code=status, headers=headers)


async def proxy_package_multipart(
    model: PackageModel,
    operation: str,
    *,
    data: Mapping[str, Any],
    files: Mapping[str, tuple[str, bytes, str]],
) -> Response:
    path = model.endpoints.get(operation)
    if not path:
        raise HTTPException(status_code=400, detail=f"Model does not support {operation}")
    fields = {key: str(value) for key, value in data.items() if value is not None}
    fields["model"] = model.upstream_id
    stream = fields.get("stream", "").lower() == "true"
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(300.0, connect=15.0), trust_env=False
    )
    request = client.build_request(
        "POST", model.endpoint + path, data=fields, files=files
    )
    try:
        response = await client.send(request, stream=stream)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=502, detail=f"Model provider request failed: {exc}") from exc
    if stream:
        async def chunks():
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        return StreamingResponse(
            chunks(),
            status_code=response.status_code,
            media_type=response.headers.get("content-type"),
            headers=_response_headers(response),
        )
    content = await response.aread()
    status = response.status_code
    headers = _response_headers(response)
    await response.aclose()
    await client.aclose()
    return Response(
        content=content,
        status_code=status,
        headers=headers,
    )
