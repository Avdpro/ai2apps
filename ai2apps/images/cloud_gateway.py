# SPDX-License-Identifier: BUSL-1.1
# See LICENSES/AI2APPS-CLOUD-CONNECTOR-BSL-1.1.md.
"""Image-owner Cloud/BYOK transport and image option validation."""
from __future__ import annotations
import base64
import binascii
import json
import re
import uuid
from typing import Any
import httpx
from fastapi import HTTPException, Response
from ai2apps.model_manager import ModelManagerStore
from ai2apps.cloud_gateway import AI2APPS_CLOUD_MODEL_PREFIX, _managed_model_id
from ai2apps.fusion.provider_errors import redacted_provider_error as _redacted_error

_IMAGE_DATA_URL = re.compile(
    r"^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\s]+)$"
)
def _decode_image_data_url(value: Any, label: str) -> tuple[bytes, str, str]:
    match = _IMAGE_DATA_URL.fullmatch(str(value or ""))
    if match is None:
        raise HTTPException(status_code=400, detail=f"{label} must be a PNG, JPEG, or WebP Data URL")
    try:
        data = base64.b64decode("".join(match.group(2).split()), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"{label} contains invalid base64") from exc
    extension = "jpg" if match.group(1) == "image/jpeg" else match.group(1).split("/", 1)[1]
    return data, match.group(1), extension


def _local_image_url(provider: dict[str, Any], edit: bool) -> str:
    root = provider["base_url"].rstrip("/")
    return f"{root}/images/{'edits' if edit else 'generations'}"


async def request_cloud_image(
    payload: dict[str, Any],
    *,
    edit: bool,
    base_path: Any,
    cloud_client: Any | None = None,
    cloud_headers: dict[str, str] | None = None,
    model_manager: ModelManagerStore | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    """Generate or edit one image through the selected local/account route."""

    model = str(payload.get("model") or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="Image model is required")
    store = model_manager or ModelManagerStore(base_path)
    provider = store.resolve_cloud_model(model)
    managed_model = _managed_model_id(model)
    if provider is None and managed_model is not None:
        provider_id = managed_model.split("/", 1)[0]
        local_provider = next(
            (item for item in store.list_cloud() if item["id"] == provider_id), None
        )
        if model.startswith(AI2APPS_CLOUD_MODEL_PREFIX) or local_provider is None or not local_provider["configured"]:
            if cloud_client is None:
                raise HTTPException(status_code=503, detail="AI2Apps Cloud client is not ready")
            if payload.get('background') is not None:
                catalog = await cloud_client.request('GET', '/v1/ai/models', headers=cloud_headers)
                try:
                    catalog.raise_for_status()
                    selected = next((m for m in catalog.json().get('items', []) if m.get('id') == managed_model), {})
                    from ai2apps.images.background import validate_background
                    validate_background(payload['background'], payload.get('outputFormat','png'), selected.get('imageOptions',{}).get('background') or [])
                except ValueError as error:
                    raise HTTPException(status_code=400, detail=str(error)) from error
                finally:
                    await catalog.aclose()
            cloud_body = {
                key: value
                for key, value in payload.items()
                if key
                in {
                    "prompt",
                    "size",
                    "quality",
                    "outputFormat",
                    "outputCompression",
                    "n",
                    "imageDataUrls",
                    "maskDataUrl",
                    "background",
                }
            }
            if cloud_body.get('background') is None:
                cloud_body.pop('background', None)
            cloud_body["model"] = managed_model
            # Generation schemas reject edit-only fields even when model_dump
            # supplied an empty default. Both Studio and Mini-Chat use this
            # adapter; keep image/mask inputs exclusively on the edits route.
            if not edit:
                cloud_body.pop("imageDataUrls", None)
                cloud_body.pop("maskDataUrl", None)
            request_headers = dict(cloud_headers or {})
            request_headers["Idempotency-Key"] = str(
                payload.get("idempotencyKey") or f"local-image-{uuid.uuid4()}"
            )
            try:
                upstream = await cloud_client.request(
                    "POST",
                    f"/v1/ai/images/{'edits' if edit else 'generations'}",
                    json=cloud_body,
                    headers=request_headers,
                )
            except httpx.TimeoutException as exc:
                raise HTTPException(status_code=504, detail="AI2Apps Cloud timed out") from exc
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail="AI2Apps Cloud is unavailable") from exc
            try:
                if upstream.status_code >= 400:
                    try:
                        error_payload = upstream.json()
                    except ValueError:
                        error_payload = {}
                    error = (
                        error_payload.get("error", {})
                        if isinstance(error_payload, dict)
                        else {}
                    )
                    raise HTTPException(
                        status_code=upstream.status_code,
                        detail={
                            "code": str(
                                error.get("code")
                                or "AI2APPS_CLOUD_IMAGE_REQUEST_FAILED"
                            ),
                            "message": str(
                                error.get("message")
                                or "AI2Apps Cloud image request failed"
                            )[:1000],
                            "retryable": bool(error.get("retryable", False)),
                        },
                    )
                result = upstream.json()
                if not isinstance(result, dict) or not isinstance(result.get("image"), dict):
                    raise HTTPException(status_code=502, detail="AI2Apps Cloud returned an invalid image response")
                return result
            finally:
                await upstream.aclose()
    if provider is None:
        raise HTTPException(status_code=404, detail="Image model is not enabled")
    if provider.get("protocol") != "openai":
        raise HTTPException(status_code=400, detail="Selected provider does not support the image API")

    model_id = str(provider["model_id"])
    from ai2apps.images.byok_capabilities import validate_request, model_name
    try:
        options = validate_request(model_id, payload, edit=edit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    common = {
        "model": model_id,
        "prompt": str(payload.get("prompt") or ""),
        "size": str(payload.get("size") or "1024x1024"),
        "quality": str(payload.get("quality") or options["quality"][0]),
        "n": 1,
    }
    output_format = str(payload.get("outputFormat") or "png")
    normalized_model_id = model_name(model_id)
    is_gpt_image = normalized_model_id.startswith("gpt-image-") or normalized_model_id == "chatgpt-image-latest"
    if is_gpt_image:
        common["output_format"] = output_format
        if payload.get('background') is not None:
            common['background'] = payload['background']
        if payload.get("outputCompression") is not None:
            common["output_compression"] = payload["outputCompression"]
    else:
        # DALL-E endpoints still use the legacy response_format switch. GPT Image
        # models return b64_json without it and reject the parameter entirely.
        common["response_format"] = "b64_json"
    if normalized_model_id == "dall-e-2":
        common.pop("quality", None)
    headers = {"Authorization": f"Bearer {provider['api_key']}"}
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=15.0, read=3600.0, write=120.0, pool=30.0),
        transport=transport,
    )
    try:
        if edit:
            values = payload.get("imageDataUrls")
            maximum = 1 if normalized_model_id == 'dall-e-2' else 4
            if not isinstance(values, list) or not 1 <= len(values) <= maximum:
                raise HTTPException(status_code=400, detail=f"imageDataUrls must contain 1 to {maximum} images")
            files = []
            for index, value in enumerate(values):
                data, media_type, extension = _decode_image_data_url(value, f"imageDataUrls[{index}]")
                files.append(("image" if normalized_model_id == "dall-e-2" else "image[]", (f"image-{index + 1}.{extension}", data, media_type)))
            if payload.get("maskDataUrl") is not None:
                data, media_type, extension = _decode_image_data_url(payload["maskDataUrl"], "maskDataUrl")
                files.append(("mask", (f"mask.{extension}", data, media_type)))
            request = client.build_request(
                "POST", _local_image_url(provider, True), headers=headers, data=common, files=files
            )
        else:
            request = client.build_request(
                "POST", _local_image_url(provider, False), headers={**headers, "Content-Type": "application/json"}, json=common
            )
        upstream = await client.send(request)
        if upstream.status_code >= 400:
            detail = _redacted_error(upstream, provider["api_key"])
            raise HTTPException(status_code=upstream.status_code, detail=detail)
        result = upstream.json()
        images = result.get("data") if isinstance(result, dict) else None
        image = images[0] if isinstance(images, list) and images else None
        if not isinstance(image, dict):
            raise HTTPException(status_code=502, detail="Image provider returned no image")
        value = image.get("b64_json")
        data_url = (
            f"data:image/{'jpeg' if output_format == 'jpeg' else output_format};base64,{value}"
            if value
            else image.get("url")
        )
        if not data_url:
            raise HTTPException(status_code=502, detail="Image provider returned an invalid image")
        return {
            "image": {
                "dataUrl": data_url,
                "size": common["size"],
                "quality": common.get("quality", "standard"),
                "format": output_format,
            },
            "usage": result.get("usage"),
            "provider": "local",
            "model": model,
        }
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Image provider timed out") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Image provider is unavailable") from exc
    finally:
        await client.aclose()


async def proxy_cloud_image_request(payload: dict[str, Any], **kwargs: Any) -> Response:
    result = await request_cloud_image(payload, **kwargs)
    return Response(content=json.dumps(result), media_type="application/json")


