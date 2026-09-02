"""Default-model image generation exposed through the Tool Gateway."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import uuid
from collections.abc import Callable
from typing import Any

from ai2apps.cloud_gateway import request_cloud_image
from ai2apps.model_manager import ModelManagerStore
from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceRegistry,
    ServiceRepository,
    ServiceRuntimeMode,
    ToolCallContext,
    ToolProviderError,
)
from ai2apps.workspace import WorkspaceRepository

_DATA_URL = re.compile(r"^data:(image/(?:png|jpeg|webp));base64,(.+)$", re.DOTALL)


def _default_image_model(store: ModelManagerStore) -> str:
    configured = store.resolve_default_model("image_generation")
    if configured:
        return configured
    for model in store.enabled_cloud_models():
        text = f"{model.get('id', '')} {model.get('name', '')}".lower()
        if any(token in text for token in ("gpt-image", "dall-e", "imagen", "flux")):
            return str(model["gateway_id"])
    # The managed route still validates account/session/catalog server-side.
    return "cloud/ai2apps/openai/gpt-image-2"


def install_image_service(
    *,
    base_path,
    cloud_client,
    workspace: WorkspaceRepository,
    repository: ServiceRepository,
    registry: ServiceRegistry,
    runtime_provider: Callable[[], Any | None] | None = None,
) -> None:
    service = repository.ensure_service(
        service_key="ai2apps.images",
        package_id="ai2apps.images",
        package_version="1.0.0",
        display_name="AI2Apps Images",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
        capabilities=("image.generate", "artifact.create"),
    )
    instance = repository.ensure_instance(
        service_id=service.id,
        provider_key="builtin:images",
        status=ServiceInstanceStatus.RUNNING,
        endpoint="/v1/images/generations",
        health={"status": "ok"},
    )
    repository.ensure_tool(
        service_id=service.id,
        qualified_name="image.generate",
        display_name="Generate image",
        description=(
            "Generate one image from a text prompt using the user's default image "
            "generation model, and return a durable Session artifact."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "minLength": 1, "maxLength": 32000},
                "size": {
                    "type": "string",
                    "enum": ["1024x1024", "1536x1024", "1024x1536"],
                    "default": "1024x1024",
                },
                "quality": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "auto"],
                    "default": "auto",
                },
                "format": {
                    "type": "string",
                    "enum": ["png", "jpeg", "webp"],
                    "default": "png",
                },
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        effects=("network", "billing", "workspace.write", "artifact.create"),
        required_capabilities=("image.generate", "workspace.write", "artifact.create"),
        timeout_ms=300_000,
    )

    async def generate(arguments: dict[str, Any], context: ToolCallContext):
        if context.session_id is None:
            raise ToolProviderError("Image generation requires a Session")
        runtime = runtime_provider() if runtime_provider is not None else None
        model_manager = (
            getattr(runtime, "model_manager", None)
            if runtime is not None
            else None
        ) or ModelManagerStore(base_path)
        model = _default_image_model(model_manager)
        request_fingerprint = hashlib.sha256(
            json.dumps(arguments, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        await context.report_progress("Generating image", progress=0.15)
        request_payload = {
                "model": model,
                "prompt": arguments["prompt"],
                "size": arguments.get("size", "1024x1024"),
                "quality": arguments.get("quality", "auto"),
                "outputFormat": arguments.get("format", "png"),
                "n": 1,
                "idempotencyKey": (
                    f"agent-image-{context.invocation_id or context.trace_id or uuid.uuid4()}-"
                    f"{request_fingerprint}"
                ),
            }
        invocations = (
            None if runtime is None else getattr(runtime, "model_invocations", None)
        )
        package_model = None if invocations is None else invocations.model(model)
        if package_model is not None:
            scheduling_context = (
                invocations.context_for_actor(
                    context.actor_user_id,
                    session_id=context.session_id,
                    consumer_app_id=context.caller_id,
                )
                if context.actor_user_id is not None
                and hasattr(invocations, "context_for_actor")
                else None
            )
            response = await invocations.invoke_foreground_json(
                package_model.id,
                "image_generation",
                request_payload,
                **(
                    {"context": scheduling_context}
                    if scheduling_context is not None
                    else {}
                ),
            )
            if response.status_code >= 400:
                raise ToolProviderError(
                    f"Image provider failed with HTTP {response.status_code}"
                )
            try:
                result = json.loads(bytes(response.body))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ToolProviderError("Image provider returned invalid JSON") from exc
            if not isinstance(result, dict):
                raise ToolProviderError("Image provider response must be an object")
            data = result.get("data")
            first = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else {}
            if not result.get("image") and first.get("b64_json"):
                output_format = arguments.get("format", "png")
                mime = "image/jpeg" if output_format == "jpeg" else f"image/{output_format}"
                result["image"] = {
                    "dataUrl": f"data:{mime};base64,{first['b64_json']}",
                    "size": arguments.get("size", "1024x1024"),
                    "quality": arguments.get("quality", "auto"),
                    "format": output_format,
                }
        else:
            result = await request_cloud_image(
                request_payload,
                edit=False,
                base_path=base_path,
                cloud_client=cloud_client,
                model_manager=model_manager,
            )
        image = result.get("image") if isinstance(result, dict) else None
        match = _DATA_URL.fullmatch(str((image or {}).get("dataUrl") or ""))
        if match is None:
            raise ToolProviderError("Image provider did not return a storable image")
        try:
            data = base64.b64decode(match.group(2), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ToolProviderError("Image provider returned invalid image data") from exc
        extension = "jpg" if match.group(1) == "image/jpeg" else match.group(1).split("/", 1)[1]
        filename = f"generated-{uuid.uuid4().hex[:12]}.{extension}"
        path = f"generated-images/{filename}"
        workspace.write(
            context.session_id,
            path,
            base64.b64encode(data).decode("ascii"),
            encoding="base64",
        )
        artifact = workspace.create_artifact(
            context.session_id,
            path,
            filename,
            run_id=(
                context.trace_id
                if context.trace_id and context.trace_id.startswith("run_")
                else None
            ),
            media_type=match.group(1),
            metadata={
                "generator": "ai2apps.images",
                "model": model,
                "size": (image or {}).get("size"),
                "quality": (image or {}).get("quality"),
            },
        )
        await context.report_progress("Image artifact ready", progress=1.0)
        cloud_settlement = {
            key: result.get(key)
            for key in (
                "requestId",
                "model",
                "status",
                "usage",
                "points",
                "pointsReleased",
                "balance",
                "pricingVersion",
                "usageEstimated",
            )
            if result.get(key) is not None
        }
        cloud_settlement["phase"] = "completed"
        return {
            "model": model,
            "ai2apps_cloud": [cloud_settlement],
            "artifact": {
                "id": artifact.id,
                "uri": artifact.uri,
                "name": artifact.name,
                "media_type": artifact.media_type,
                "size_bytes": artifact.size_bytes,
                "download_url": (
                    f"/v1/platform/sessions/{context.session_id}/artifacts/"
                    f"{artifact.id}/download"
                ),
            },
        }

    registry.bind_tool(
        "image.generate", provider_key=instance.provider_key, handler=generate
    )
