"""Authenticated Local management projection for Model Share Provider."""

from __future__ import annotations

import json
import math

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import PrincipalProvider
from ai2apps.http_security import enforce_same_origin_cookie_request
from ai2apps.identity import RequestPrincipal
from ai2apps.model_sharing.buyer import ModelShareBuyerError, ModelShareBuyerService
from ai2apps.model_sharing.cloud import ComputeCloudClient, ComputeCloudError
from ai2apps.model_sharing.repository import ModelShareRepository
from ai2apps.model_sharing.requester import (
    AudioTTSRequestConfiguration,
    ComputeRequestConfiguration,
    MultimodalRequestConfiguration,
    ModelShareRequesterService,
)
from ai2apps.peer.identity import PeerProtocol
from ai2apps.remote import RemoteAccessError


class ProviderDevicePreferenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


class ProviderModelSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str = Field(alias="modelId", min_length=1, max_length=200)
    enabled: bool


class ProviderModelPreferencesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str = Field(alias="modelId", min_length=1, max_length=200)
    max_concurrency: int = Field(alias="maxConcurrency", ge=1, le=32)
    estimated_tokens_per_second: int = Field(
        alias="estimatedTokensPerSecond", ge=1, le=1_000_000
    )


def create_model_share_router(
    runtime_provider: PlatformRuntimeProvider, principal_provider: PrincipalProvider,
) -> APIRouter:
    router = APIRouter(prefix="/model-share", tags=["platform-model-share"])

    def failure(error) -> JSONResponse:
        return JSONResponse(
            status_code=getattr(error, "status_code", 500),
            content={"error": {"code": getattr(error, "code", "MODEL_SHARE_FAILED"),
                               "message": str(error), "retryable": getattr(error, "retryable", False)}},
            headers={"Cache-Control": "no-store"},
        )

    @router.get("/provider")
    async def provider_status(
        _principal: RequestPrincipal = Depends(principal_provider),
    ) -> dict[str, object]:
        runtime = runtime_provider()
        controller = None if runtime is None else getattr(runtime, "model_share_controller", None)
        if controller is None:
            return {
                "enabled": False,
                "running": False,
                "offerId": None,
                "lastError": None if runtime is None else getattr(runtime, "model_share_provider_error", None),
            }
        return controller.status()

    @router.post("/provider/activate")
    async def activate_provider(
        request: Request,
        _principal: RequestPrincipal = Depends(principal_provider),
    ):
        runtime = runtime_provider()
        controller = None if runtime is None else getattr(runtime, "model_share_controller", None)
        browser_session = (
            None if runtime is None else runtime.cloud_browser_session_from_cookies(request.cookies)
        )
        if controller is None:
            return failure(ModelShareBuyerError(
                "MODEL_SHARE_PROVIDER_DISABLED",
                "Restart this isolated Local with Provider configuration enabled.",
                status_code=409,
            ))
        if not browser_session:
            return failure(ModelShareBuyerError(
                "CLOUD_BROWSER_SESSION_REQUIRED",
                "Sign in to AI2Apps Cloud in this browser before activating Provider.",
                status_code=409,
            ))
        enforce_same_origin_cookie_request(request)
        browser_cloud = runtime.cloud_for_browser(browser_session)
        controller.bind_compute(ComputeCloudClient(browser_cloud))
        controller.bind_remote_cloud(browser_cloud)
        try:
            if controller.status().get("enabled"):
                await controller.ensure_transport_ready()
            return await controller.refresh_rate_cards()
        except (ComputeCloudError, RemoteAccessError, ValueError) as error:
            return failure(error)

    def mutable_provider(request: Request):
        runtime = runtime_provider()
        controller = None if runtime is None else getattr(runtime, "model_share_controller", None)
        if controller is None:
            return None, failure(ModelShareBuyerError(
                "MODEL_SHARE_PROVIDER_UNAVAILABLE",
                "Compute sharing is unavailable until this Device is bound to AI2Apps Cloud.",
                status_code=409,
            ))
        browser_session = runtime.cloud_browser_session_from_cookies(request.cookies)
        if not browser_session:
            return None, failure(ModelShareBuyerError(
                "CLOUD_BROWSER_SESSION_REQUIRED",
                "Sign in to AI2Apps Cloud before changing Compute sharing.",
                status_code=409,
            ))
        enforce_same_origin_cookie_request(request)
        browser_cloud = runtime.cloud_for_browser(browser_session)
        controller.bind_compute(ComputeCloudClient(browser_cloud))
        controller.bind_remote_cloud(browser_cloud)
        return controller, None

    @router.post("/provider/device-preference")
    async def set_provider_device_preference(
        value: ProviderDevicePreferenceRequest,
        request: Request,
        _principal: RequestPrincipal = Depends(principal_provider),
    ):
        controller, error = mutable_provider(request)
        if error is not None:
            return error
        try:
            return await controller.set_device_enabled(value.enabled)
        except (ValueError, RemoteAccessError) as exc:
            return failure(ModelShareBuyerError(
                getattr(exc, "code", "MODEL_SHARE_PREFERENCE_INVALID"),
                str(exc), status_code=getattr(exc, "status_code", 409)
            ))

    @router.post("/provider/model-selection")
    async def set_provider_model_selection(
        value: ProviderModelSelectionRequest,
        request: Request,
        _principal: RequestPrincipal = Depends(principal_provider),
    ):
        controller, error = mutable_provider(request)
        if error is not None:
            return error
        try:
            return await controller.set_model_enabled(value.model_id, value.enabled)
        except ValueError as exc:
            return failure(ModelShareBuyerError(
                "MODEL_SHARE_PREFERENCE_INVALID", str(exc), status_code=409
            ))

    @router.post("/provider/model-preferences")
    async def set_provider_model_preferences(
        value: ProviderModelPreferencesRequest,
        request: Request,
        _principal: RequestPrincipal = Depends(principal_provider),
    ):
        controller, error = mutable_provider(request)
        if error is not None:
            return error
        try:
            return await controller.save_model_preferences(
                value.model_id,
                max_concurrency=value.max_concurrency,
                estimated_tokens_per_second=value.estimated_tokens_per_second,
            )
        except ValueError as exc:
            return failure(ModelShareBuyerError(
                "MODEL_SHARE_PREFERENCE_INVALID", str(exc), status_code=422
            ))

    @router.post("/peer/register")
    async def register_peer_key(
        principal: RequestPrincipal = Depends(principal_provider),
    ) -> dict[str, object]:
        runtime = runtime_provider()
        core = None if runtime is None else getattr(runtime, "peer_transport", None)
        if core is None:
            return {"ready": False, "error": "peer_transport_unavailable"}
        registered = await core.broker_for(principal).ensure_registered(
            principal, PeerProtocol.MODEL_SHARE_V1
        )
        return {
            "ready": True,
            "keyId": registered["keyId"],
            "keyEpoch": registered["keyEpoch"],
            "deviceAccessEpoch": registered["deviceAccessEpoch"],
        }

    @router.post("/inference")
    async def inference(
        request: Request,
        principal: RequestPrincipal = Depends(principal_provider),
    ):
        runtime = runtime_provider()
        if runtime is None or any(getattr(runtime, name, None) is None for name in ("peer_transport", "cloud", "database")):
            return failure(ModelShareBuyerError("MODEL_SHARE_NOT_READY", "Model Share Buyer is not ready.", status_code=503, retryable=True))
        raw = await request.body()
        if len(raw) > 1_000_000:
            return failure(ModelShareBuyerError("MODEL_SHARE_REQUEST_TOO_LARGE", "Model Share request is too large.", status_code=413))
        try:
            value = json.loads(raw)
            allowed = {"modelId", "modelRevision", "runtime", "expectedRateCardVersion", "maximumAmountMinor",
                       "estimatedInputTokens", "maximumOutputTokens", "prompt", "systemPrompt", "temperature"}
            if not isinstance(value, dict) or set(value) != allowed:
                raise ValueError("Model Share request fields are invalid")
            if not isinstance(value["prompt"], str) or not value["prompt"] or len(value["prompt"]) > 262_144:
                raise ValueError("Model Share prompt is invalid")
            if value["systemPrompt"] is not None and (not isinstance(value["systemPrompt"], str) or len(value["systemPrompt"]) > 65_536):
                raise ValueError("Model Share system prompt is invalid")
            for field in ("modelId", "modelRevision", "runtime", "expectedRateCardVersion", "maximumAmountMinor"):
                if not isinstance(value[field], str):
                    raise ValueError(f"{field} must be a string")
            for field in ("estimatedInputTokens", "maximumOutputTokens"):
                if isinstance(value[field], bool) or not isinstance(value[field], int):
                    raise ValueError(f"{field} must be an integer")
            temperature = value["temperature"]
            if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not math.isfinite(temperature):
                raise ValueError("temperature must be a finite number")
            config = ComputeRequestConfiguration(
                model_id=value["modelId"], model_revision=value["modelRevision"],
                runtime=value["runtime"], expected_rate_card_version=value["expectedRateCardVersion"],
                maximum_amount_minor=value["maximumAmountMinor"],
                estimated_input_tokens=value["estimatedInputTokens"],
                maximum_output_tokens=value["maximumOutputTokens"],
            )
            broker = runtime.peer_transport.broker_for(principal)
            browser_session_resolver = getattr(
                runtime, "cloud_browser_session_from_cookies", None
            )
            browser_session = (
                browser_session_resolver(request.cookies)
                if browser_session_resolver is not None
                else None
            )
            if not browser_session:
                raise ModelShareBuyerError(
                    "CLOUD_BROWSER_SESSION_REQUIRED",
                    "Sign in to AI2Apps Cloud in this browser before requesting shared compute.",
                    status_code=409,
                )
            enforce_same_origin_cookie_request(request)
            cloud = runtime.cloud_for_browser(browser_session)
            compute = ComputeCloudClient(cloud)
            requester = ModelShareRequesterService(
                broker=broker, compute=compute, jobs=ModelShareRepository(runtime.database),
                peer_core=runtime.peer_transport,
            )
            buyer = ModelShareBuyerService(requester=requester, compute=compute)
            signer = await runtime.model_share_signer_for(principal)
            manifest, session = await buyer.prepare(
                principal=principal, signer=signer, config=config, prompt=value["prompt"],
                system_prompt=value["systemPrompt"], temperature=temperature,
            )
        except (ComputeCloudError, ModelShareBuyerError) as error:
            return failure(error)
        except (KeyError, TypeError, ValueError) as error:
            return failure(ModelShareBuyerError("MODEL_SHARE_REQUEST_INVALID", str(error), status_code=400))

        async def events():
            try:
                async for event in buyer.stream(
                    principal=principal, signer=signer, manifest=manifest, session=session,
                ):
                    yield f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False, separators=(',', ':'))}\n\n"
            except Exception as error:
                payload = {"code": getattr(error, "code", "MODEL_SHARE_STREAM_FAILED"),
                           "message": str(error), "retryable": getattr(error, "retryable", False)}
                yield f"event: error\ndata: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"

        return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})

    @router.post("/tts")
    async def synthesize_tts(
        request: Request,
        principal: RequestPrincipal = Depends(principal_provider),
    ):
        runtime = runtime_provider()
        if runtime is None or any(
            getattr(runtime, name, None) is None
            for name in ("peer_transport", "cloud", "database")
        ):
            return failure(ModelShareBuyerError(
                "MODEL_SHARE_NOT_READY", "TTS Model Share Buyer is not ready.",
                status_code=503, retryable=True,
            ))
        raw = await request.body()
        if len(raw) > 1_000_000:
            return failure(ModelShareBuyerError(
                "MODEL_SHARE_REQUEST_TOO_LARGE", "TTS request is too large.",
                status_code=413,
            ))
        try:
            value = json.loads(raw)
            legacy_allowed = {
                "modelId", "modelRevision", "runtime",
                "expectedRateCardVersion", "maximumAmountMinor",
                "maximumAudioMilliseconds", "text", "voice", "language",
                "instructions", "speed",
            }
            quoted_allowed = {
                "modelId", "modelRevision", "runtime", "buyerMaximumMinor",
                "text", "voice", "language", "instructions", "speed",
                "quality", "customSampleUsed", "priorityTier",
            }
            if not isinstance(value, dict) or frozenset(value) not in {
                frozenset(legacy_allowed), frozenset(quoted_allowed),
                frozenset(quoted_allowed | {"rateCardId"}),
            }:
                raise ValueError("TTS Model Share request fields are invalid")
            quoted = "quality" in value
            for field in (
                "modelId", "modelRevision", "runtime", "text", "voice",
            ):
                if not isinstance(value[field], str):
                    raise ValueError(f"{field} must be a string")
            if not value["text"] or len(value["text"]) > 100_000:
                raise ValueError("TTS text is invalid")
            if value["language"] is not None and not isinstance(value["language"], str):
                raise ValueError("language must be a string or null")
            if value["instructions"] is not None and not isinstance(value["instructions"], str):
                raise ValueError("instructions must be a string or null")
            speed = value["speed"]
            if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not math.isfinite(speed):
                raise ValueError("speed must be a finite number")
            if quoted:
                if not isinstance(value["buyerMaximumMinor"], str):
                    raise ValueError("buyerMaximumMinor must be a string")
                if value["quality"] not in {"low", "mid", "high"}:
                    raise ValueError("quality is invalid")
                if not isinstance(value["customSampleUsed"], bool):
                    raise ValueError("customSampleUsed must be a boolean")
                speed_bps = round(speed * 10_000)
                config = MultimodalRequestConfiguration(
                    model_id=value["modelId"], model_revision=value["modelRevision"],
                    runtime=value["runtime"], calculator_type="tts_v1",
                    buyer_maximum_minor=value["buyerMaximumMinor"],
                    pricing_input={
                        "unicodeScalarCount": len(value["text"]),
                        "speedBps": speed_bps,
                        "customSampleUsed": value["customSampleUsed"],
                        "quality": value["quality"],
                    },
                    priority_tier=value["priorityTier"],
                    rate_card_id=value.get("rateCardId"),
                )
                request_payload = {
                    "text": value["text"], "voice": value["voice"],
                    "language": value["language"],
                    "instructions": value["instructions"],
                    "speedBps": speed_bps,
                    "customSampleUsed": value["customSampleUsed"],
                    "quality": value["quality"],
                }
            else:
                for field in ("expectedRateCardVersion", "maximumAmountMinor"):
                    if not isinstance(value[field], str):
                        raise ValueError(f"{field} must be a string")
            config = AudioTTSRequestConfiguration(
                    model_id=value["modelId"], model_revision=value["modelRevision"],
                    runtime=value["runtime"],
                    expected_rate_card_version=value["expectedRateCardVersion"],
                    maximum_amount_minor=value["maximumAmountMinor"],
                    maximum_audio_milliseconds=value["maximumAudioMilliseconds"],
                ) if not quoted else config
            browser_session = runtime.cloud_browser_session_from_cookies(request.cookies)
            if not browser_session:
                raise ModelShareBuyerError(
                    "CLOUD_BROWSER_SESSION_REQUIRED",
                    "Sign in to AI2Apps Cloud before requesting shared TTS.",
                    status_code=409,
                )
            enforce_same_origin_cookie_request(request)
            compute = ComputeCloudClient(runtime.cloud_for_browser(browser_session))
            requester = ModelShareRequesterService(
                broker=runtime.peer_transport.broker_for(principal),
                compute=compute, jobs=ModelShareRepository(runtime.database),
                peer_core=runtime.peer_transport,
            )
            buyer = ModelShareBuyerService(requester=requester, compute=compute)
            signer = await runtime.model_share_signer_for(principal)
            if quoted:
                manifest, quote, session = await buyer.prepare_multimodal(
                    principal=principal, signer=signer, config=config,
                    request_payload=request_payload,
                )
                audio, actual_usage = await buyer.fetch_multimodal(
                    principal=principal, signer=signer, manifest=manifest,
                    request_payload=request_payload, session=session,
                    maximum_charge_minor=quote["maximumChargeMinor"],
                )
                response_headers = {
                    "Cache-Control": "no-store",
                    "X-AI2Apps-Calculator-Type": "tts_v1",
                    "X-AI2Apps-Quote-Id": quote["id"],
                    "X-AI2Apps-Maximum-Charge-Minor": quote["maximumChargeMinor"],
                    "X-AI2Apps-Output-Duration-Ms": str(actual_usage["outputDurationMs"]),
                }
            else:
                manifest, session = await buyer.prepare_audio_tts(
                    principal=principal, signer=signer, config=config,
                    text=value["text"], voice=value["voice"],
                    language=value["language"], instructions=value["instructions"],
                    speed=speed,
                )
                audio = await buyer.synthesize_audio_tts(
                    principal=principal, signer=signer,
                    manifest=manifest, session=session,
                )
                response_headers = {"Cache-Control": "no-store"}
            return Response(
                content=audio, media_type="audio/wav",
                headers=response_headers,
            )
        except (ComputeCloudError, ModelShareBuyerError) as error:
            return failure(error)
        except (KeyError, TypeError, ValueError) as error:
            return failure(ModelShareBuyerError(
                "MODEL_SHARE_REQUEST_INVALID", str(error), status_code=400,
            ))

    return router
