#!/usr/bin/env python3
"""Run the AI2Apps local-to-Cloud acceptance checks without exposing secrets."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import uuid
from pathlib import Path
from typing import Any

import httpx


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--settings", type=Path, default=Path.home() / ".omlx/settings.json")
    parser.add_argument("--charged", action="store_true", help="Run billed text/image checks")
    parser.add_argument("--cancel", action="store_true", help="Run a live cancellation check")
    parser.add_argument("--image-edit", action="store_true", help="Also edit the generated image")
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/ai2apps-cloud-acceptance"))
    return parser.parse_args()


def _api_key(settings_path: Path) -> str:
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    value = str((settings.get("auth") or {}).get("api_key") or "")
    if not value:
        raise RuntimeError("Local API key is not configured")
    return value


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        values = payload.get("items", payload.get("models", []))
        if isinstance(values, list):
            return [item for item in values if isinstance(item, dict)]
    return []


def _choose_models(models: list[dict[str, Any]]) -> tuple[str, str | None]:
    image = next(
        (
            str(item.get("id"))
            for item in models
            if "image" in str(item.get("id", "")).lower()
            and "image" in str(item.get("displayName", "")).lower()
        ),
        None,
    )
    text_models = [
        str(item.get("id"))
        for item in models
        if item.get("id") and str(item.get("id")) != image
    ]
    preferred = next(
        (
            model
            for token in ("flash", "terra", "sonnet")
            for model in text_models
            if token in model.lower()
        ),
        text_models[0] if text_models else None,
    )
    if not preferred:
        raise RuntimeError("Cloud model catalog contains no text model")
    return preferred, image


def _error(response: httpx.Response) -> RuntimeError:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    detail = payload.get("detail") if isinstance(payload, dict) else None
    error = payload.get("error") if isinstance(payload, dict) else None
    value = error or (detail if isinstance(detail, dict) else {})
    code = value.get("code") if isinstance(value, dict) else None
    message = value.get("message") if isinstance(value, dict) else detail
    return RuntimeError(f"{code or response.status_code}: {message or 'request failed'}")


async def _json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    **kwargs: Any,
) -> dict[str, Any]:
    response = await client.request(method, path, **kwargs)
    if response.status_code >= 400:
        raise _error(response)
    if response.status_code == 204:
        return {}
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} returned a non-object response")
    return payload


async def _chat_stream(
    client: httpx.AsyncClient,
    model: str,
    idempotency_key: str,
    *,
    cancel: bool = False,
) -> dict[str, Any]:
    prompt = "Reply with exactly: AI2Apps cloud accepted"
    max_tokens = 64
    if cancel:
        prompt = (
            "Write a detailed 1500-item numbered checklist. Each item must be "
            "a complete sentence and must not be abbreviated."
        )
        max_tokens = 4096
    body = {
        "model": f"cloud/ai2apps/{model}",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        "ai2apps_idempotency_key": idempotency_key,
    }
    text = ""
    lifecycle: list[dict[str, Any]] = []
    async with client.stream("POST", "/v1/chat/completions", json=body) as response:
        if response.status_code >= 400:
            await response.aread()
            raise _error(response)
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            value = line[6:].strip()
            if value == "[DONE]":
                break
            chunk = json.loads(value)
            delta = ((chunk.get("choices") or [{}])[0].get("delta") or {})
            text += str(delta.get("content") or "")
            cloud = delta.get("ai2apps_cloud")
            if isinstance(cloud, dict):
                lifecycle.append(cloud)
                if cancel and cloud.get("phase") == "created" and cloud.get("requestId"):
                    cancel_response = await client.post(
                        f"/v1/platform/cloud/ai/requests/{cloud['requestId']}/cancel"
                    )
                    if cancel_response.status_code < 400:
                        lifecycle.append({"phase": "cancel_requested"})
                        break
                    cancel_error = _error(cancel_response)
                    if "AI_REQUEST_NOT_RUNNING" not in str(cancel_error):
                        raise cancel_error
                    # Fast models can finish between response.created and the
                    # cancellation request. Keep consuming the stream and
                    # verify the already-terminal request instead of treating
                    # this legitimate race as a cancellation failure.
                    lifecycle.append({"phase": "cancel_raced_with_completion"})
    request_id = next(
        (str(item["requestId"]) for item in lifecycle if item.get("requestId")),
        "",
    )
    return {"text": text, "lifecycle": lifecycle, "request_id": request_id}


async def _image(
    client: httpx.AsyncClient,
    model: str,
    output_dir: Path,
    *,
    source: str | None = None,
) -> dict[str, Any]:
    editing = source is not None
    key = f"accept-image-{uuid.uuid4()}"
    payload: dict[str, Any] = {
        "model": f"cloud/ai2apps/{model}",
        "prompt": "A small blue paper boat on a white background",
        "size": "1024x1024",
        "quality": "low",
        "outputFormat": "png",
        "n": 1,
        "idempotencyKey": key,
    }
    if editing:
        payload["prompt"] = "Keep the paper boat and add one small red star"
        payload["imageDataUrls"] = [source]
    result = await _json(
        client,
        "POST",
        f"/v1/images/{'edits' if editing else 'generations'}",
        json=payload,
    )
    image = result.get("image") or {}
    data_url = str(image.get("dataUrl") or "")
    if "," not in data_url:
        raise RuntimeError("Image response contains no Data URL")
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / ("edited.png" if editing else "generated.png")
    target.write_bytes(base64.b64decode(data_url.split(",", 1)[1], validate=True))
    return {
        "request_id": result.get("requestId"),
        "charged": result.get("charged") or (result.get("points") or {}).get("charged"),
        "released": result.get("released") or result.get("pointsReleased"),
        "balance": result.get("balance"),
        "pricing_version": result.get("pricingVersion"),
        "artifact": str(target),
        "data_url": data_url,
    }


async def main() -> int:
    args = _arguments()
    headers = {"Authorization": f"Bearer {_api_key(args.settings)}"}
    report: dict[str, Any] = {}
    async with httpx.AsyncClient(
        base_url=args.base_url,
        headers=headers,
        timeout=httpx.Timeout(3600),
        trust_env=False,
    ) as client:
        me = await _json(client, "GET", "/v1/platform/cloud/auth/me")
        before = await _json(client, "GET", "/v1/platform/cloud/points")
        catalog = await _json(client, "GET", "/v1/platform/cloud/ai/models")
        models = _items(catalog)
        text_model, image_model = _choose_models(models)
        report.update(
            {
                "account": {
                    "id": (me.get("user") or {}).get("id"),
                    "email": (me.get("user") or {}).get("email"),
                },
                "points_before": before,
                "model_count": len(models),
                "text_model": text_model,
                "image_model": image_model,
            }
        )
        if args.charged:
            text = await _chat_stream(
                client, text_model, f"accept-text-{uuid.uuid4()}"
            )
            if not any(item.get("phase") == "completed" for item in text["lifecycle"]):
                raise RuntimeError("Text stream did not reach response.completed")
            if not text["request_id"] or not text["text"]:
                raise RuntimeError("Text stream did not expose requestId and output")
            state = await _json(
                client,
                "GET",
                f"/v1/platform/cloud/ai/requests/{text['request_id']}",
            )
            report["text"] = {
                "request_id": text["request_id"],
                "characters": len(text["text"]),
                "terminal_phase": text["lifecycle"][-1].get("phase"),
                "charged": text["lifecycle"][-1].get("charged")
                or (text["lifecycle"][-1].get("points") or {}).get("charged"),
                "released": text["lifecycle"][-1].get("pointsReleased"),
                "balance": text["lifecycle"][-1].get("balance"),
                "request_status": state.get("status"),
            }
            if args.cancel:
                cancelled = await _chat_stream(
                    client,
                    text_model,
                    f"accept-cancel-{uuid.uuid4()}",
                    cancel=True,
                )
                await asyncio.sleep(1)
                state = await _json(
                    client,
                    "GET",
                    f"/v1/platform/cloud/ai/requests/{cancelled['request_id']}",
                )
                report["cancel"] = {
                    "request_id": cancelled["request_id"],
                    "status": state.get("status"),
                    "reserved": (state.get("points") or {}).get("reserved"),
                    "charged": (state.get("points") or {}).get("charged"),
                }
            if image_model:
                generated = await _image(client, image_model, args.output_dir)
                report["image_generation"] = {
                    key: value for key, value in generated.items() if key != "data_url"
                }
                if args.image_edit:
                    edited = await _image(
                        client,
                        image_model,
                        args.output_dir,
                        source=generated["data_url"],
                    )
                    report["image_edit"] = {
                        key: value for key, value in edited.items() if key != "data_url"
                    }
            report["points_after"] = await _json(
                client, "GET", "/v1/platform/cloud/points"
            )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
