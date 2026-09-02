"""Public, Grant-authenticated ingress for Model Share v1 text jobs."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.model_sharing.protocol import InferenceRequest, ModelShareProtocolError
from ai2apps.model_sharing.provider import ModelShareProviderError


def create_model_share_peer_ingress_router(runtime_provider: PlatformRuntimeProvider) -> APIRouter:
    router = APIRouter(prefix="/v1/model-share/peer/v1", tags=["model-share-peer"])

    def error_response(error: ModelShareProviderError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"error": {"code": error.code, "message": str(error), "retryable": error.retryable}},
            headers={"Cache-Control": "no-store"},
        )

    @router.post("/inference")
    async def inference(request: Request):
        runtime = runtime_provider()
        provider = None if runtime is None else getattr(runtime, "model_share_provider", None)
        principal = None if runtime is None else getattr(runtime, "model_share_provider_principal", None)
        if provider is None or principal is None:
            return error_response(ModelShareProviderError("MODEL_SHARE_NOT_READY", "Model Share Provider is not enabled.", status_code=503, retryable=True))
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer ") or not 1 <= len(authorization[7:]) <= 8192:
            return error_response(ModelShareProviderError("PEER_GRANT_REQUIRED", "A Peer Grant is required.", status_code=401))
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > 2_100_000:
                return error_response(ModelShareProviderError("MODEL_SHARE_REQUEST_TOO_LARGE", "Inference request exceeds the text Pilot limit.", status_code=413))
        try:
            value: Any = json.loads(content)
            parsed = InferenceRequest.parse(value)
            body = await provider.inference(principal=principal, bearer_grant=authorization[7:], request=parsed)
        except (UnicodeDecodeError, json.JSONDecodeError, ModelShareProtocolError) as error:
            return error_response(ModelShareProviderError("MODEL_SHARE_REQUEST_INVALID", str(error)))
        except ModelShareProviderError as error:
            return error_response(error)
        return StreamingResponse(body, media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    return router
