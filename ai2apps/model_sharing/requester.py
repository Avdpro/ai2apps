"""Buyer-side Compute request, Peer Session, stream verification, and receipt."""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from ai2apps.identity import RequestPrincipal
from ai2apps.peer.broker import PeerBrokerClient
from ai2apps.peer.core import PeerTransportCore
from ai2apps.peer.identity import PeerProtocol
from ai2apps.peer.transports.base import PeerStreamingTransport

from .cloud import ComputeCloudClient, ComputeCloudError
from .commitments import ComputeCommitmentSigner
from .manifests import AudioTTSRequestManifest, ComputeRequestManifest, MultimodalRequestManifest
from .pricing import CALCULATOR_CONTRACTS, MultimodalComputeQuote, validate_pricing_input
from .protocol import (
    AudioTtsSseEventDecoder,
    InferenceRequest,
    ModelShareEvent,
    MultimodalArtifactSseEventDecoder,
    SseEventDecoder,
)
from .repository import ModelShareRepository


@dataclass(frozen=True, slots=True)
class ComputeRequestConfiguration:
    model_id: str
    model_revision: str
    runtime: str
    expected_rate_card_version: str
    maximum_amount_minor: str
    estimated_input_tokens: int
    maximum_output_tokens: int
    priority_tier: str = "standard"

    def __post_init__(self) -> None:
        for name, value, maximum in (
            ("model_id", self.model_id, 200),
            ("model_revision", self.model_revision, 160),
            ("runtime", self.runtime, 120),
            ("expected_rate_card_version", self.expected_rate_card_version, 128),
        ):
            if not isinstance(value, str) or not value or len(value) > maximum:
                raise ValueError(f"{name} is invalid")
        if not isinstance(self.maximum_amount_minor, str) or not re.fullmatch(r"[1-9][0-9]{0,17}", self.maximum_amount_minor):
            raise ValueError("maximum_amount_minor must be a positive base-10 integer string")
        if isinstance(self.estimated_input_tokens, bool) or not isinstance(self.estimated_input_tokens, int) or self.estimated_input_tokens < 0:
            raise ValueError("estimated_input_tokens must be a non-negative integer")
        if isinstance(self.maximum_output_tokens, bool) or not isinstance(self.maximum_output_tokens, int) or not 1 <= self.maximum_output_tokens <= 65_536:
            raise ValueError("maximum_output_tokens is invalid")
        if self.priority_tier not in {"standard", "priority"}:
            raise ValueError("priority_tier is invalid")


@dataclass(frozen=True, slots=True)
class AudioTTSRequestConfiguration:
    model_id: str
    model_revision: str
    runtime: str
    expected_rate_card_version: str
    maximum_amount_minor: str
    maximum_audio_milliseconds: int
    priority_tier: str = "standard"

    def __post_init__(self) -> None:
        for name, value, maximum in (
            ("model_id", self.model_id, 200),
            ("model_revision", self.model_revision, 160),
            ("runtime", self.runtime, 120),
            ("expected_rate_card_version", self.expected_rate_card_version, 128),
        ):
            if not isinstance(value, str) or not value or len(value) > maximum:
                raise ValueError(f"{name} is invalid")
        if not isinstance(self.maximum_amount_minor, str) or not re.fullmatch(r"[1-9][0-9]{0,17}", self.maximum_amount_minor):
            raise ValueError("maximum_amount_minor must be a positive base-10 integer string")
        if (isinstance(self.maximum_audio_milliseconds, bool)
                or not isinstance(self.maximum_audio_milliseconds, int)
                or not 1 <= self.maximum_audio_milliseconds <= 86_400_000):
            raise ValueError("maximum_audio_milliseconds is invalid")
        if self.priority_tier not in {"standard", "priority"}:
            raise ValueError("priority_tier is invalid")


@dataclass(frozen=True, slots=True)
class MultimodalRequestConfiguration:
    model_id: str
    model_revision: str
    runtime: str
    calculator_type: str
    buyer_maximum_minor: str
    pricing_input: dict[str, Any]
    priority_tier: str = "standard"
    rate_card_id: str | None = None

    def __post_init__(self) -> None:
        for name, value, maximum in (
            ("model_id", self.model_id, 200),
            ("model_revision", self.model_revision, 160),
            ("runtime", self.runtime, 120),
        ):
            if not isinstance(value, str) or not value or len(value) > maximum:
                raise ValueError(f"{name} is invalid")
        if not isinstance(self.buyer_maximum_minor, str) or not re.fullmatch(r"[1-9][0-9]{0,17}", self.buyer_maximum_minor):
            raise ValueError("buyer_maximum_minor must be a positive base-10 integer string")
        if self.priority_tier not in {"standard", "plus_20", "plus_50", "double"}:
            raise ValueError("priority_tier is invalid")
        validate_pricing_input(self.calculator_type, self.pricing_input)


class ModelShareRequesterService:
    def __init__(
        self, *, broker: PeerBrokerClient, compute: ComputeCloudClient,
        jobs: ModelShareRepository, peer_core: PeerTransportCore | None = None,
    ) -> None:
        self.broker = broker
        self.compute = compute
        self.jobs = jobs
        self.peer_core = peer_core

    async def create_request(
        self, *, principal: RequestPrincipal, signer: ComputeCommitmentSigner,
        config: ComputeRequestConfiguration, prompt: str,
        system_prompt: str | None, temperature: int | float,
    ) -> tuple[ComputeRequestManifest, dict]:
        request_id = str(uuid.uuid4())
        contract_id = str(uuid.uuid4())
        manifest = ComputeRequestManifest.create(
            request_id=request_id, requester_id=principal.actor_user_id,
            model_id=config.model_id, revision=config.model_revision,
            runtime=config.runtime, maximum_amount_minor=config.maximum_amount_minor,
            prompt=prompt, system_prompt=system_prompt, temperature=temperature,
            max_tokens=config.maximum_output_tokens,
        )
        commitment = signer.sign(kind="request_content", contract_id=contract_id, digest=manifest.digest)
        idempotency_key = f"model-share-request:{request_id}"
        payload = {
            "requestId": request_id, "contractId": contract_id,
            "billingAccountId": principal.billing_account_id,
            "requesterInstallationId": principal.installation_id,
            "assetCode": "PROMO_POINTS", "modelId": config.model_id,
            "modelRevision": config.model_revision, "runtime": config.runtime,
            "priorityTier": config.priority_tier, "floatingPrice": False,
            "expectedRateCardVersion": config.expected_rate_card_version,
            "estimatedInputTokens": config.estimated_input_tokens,
            "maximumOutputTokens": config.maximum_output_tokens,
            "buyerMaximumMinor": config.maximum_amount_minor,
            "requestCommitment": commitment.api_payload(),
        }
        response = await self.compute.request(
            "POST", "/v1/compute/requests", json=payload,
            headers={"Idempotency-Key": idempotency_key},
        )
        if response.get("id") != request_id or response.get("contractId") != contract_id or response.get("requestDigest") != manifest.digest:
            raise ValueError("Cloud Compute Request response does not match the local commitment")
        return manifest, response

    async def create_audio_tts_request(
        self, *, principal: RequestPrincipal, signer: ComputeCommitmentSigner,
        config: AudioTTSRequestConfiguration, text: str, voice: str,
        language: str | None, instructions: str | None, speed: int | float,
    ) -> tuple[AudioTTSRequestManifest, dict]:
        request_id = str(uuid.uuid4())
        contract_id = str(uuid.uuid4())
        manifest = AudioTTSRequestManifest.create(
            request_id=request_id, requester_id=principal.actor_user_id,
            model_id=config.model_id, revision=config.model_revision,
            runtime=config.runtime, maximum_amount_minor=config.maximum_amount_minor,
            text=text, voice=voice, language=language,
            instructions=instructions, speed=speed,
        )
        commitment = signer.sign(
            kind="request_content", contract_id=contract_id,
            digest=manifest.digest,
        )
        payload = {
            "requestId": request_id, "contractId": contract_id,
            "billingAccountId": principal.billing_account_id,
            "requesterInstallationId": principal.installation_id,
            "assetCode": "PROMO_POINTS", "modelId": config.model_id,
            "modelRevision": config.model_revision, "runtime": config.runtime,
            "modality": "audio_tts", "inputUnit": "unicode_scalar",
            "outputUnit": "audio_millisecond",
            "priorityTier": config.priority_tier, "floatingPrice": False,
            "expectedRateCardVersion": config.expected_rate_card_version,
            "estimatedInputUnits": len(text),
            "maximumOutputUnits": config.maximum_audio_milliseconds,
            "buyerMaximumMinor": config.maximum_amount_minor,
            "requestCommitment": commitment.api_payload(),
        }
        response = await self.compute.request(
            "POST", "/v1/compute/requests", json=payload,
            headers={"Idempotency-Key": f"model-share-tts:{request_id}"},
        )
        if (response.get("id") != request_id
                or response.get("contractId") != contract_id
                or response.get("requestDigest") != manifest.digest):
            raise ValueError("Cloud TTS Request response does not match the local commitment")
        return manifest, response

    async def create_multimodal_request(
        self, *, principal: RequestPrincipal, signer: ComputeCommitmentSigner,
        config: MultimodalRequestConfiguration,
        request_payload: dict[str, Any], _retry_quote: bool = True,
    ) -> tuple[MultimodalRequestManifest, MultimodalComputeQuote, dict]:
        request_id = str(uuid.uuid4())
        contract_id = str(uuid.uuid4())
        quote = await self.compute.create_quote(
            model_id=config.model_id, model_revision=config.model_revision,
            runtime=config.runtime, calculator_type=config.calculator_type,
            pricing_input=config.pricing_input,
            buyer_maximum_minor=config.buyer_maximum_minor,
            priority_tier=config.priority_tier, rate_card_id=config.rate_card_id,
            idempotency_key=f"model-share-quote:{request_id}",
        )
        manifest = MultimodalRequestManifest.create(
            request_id=request_id, contract_id=contract_id, quote_id=quote.id,
            calculator_type=config.calculator_type, model_id=config.model_id,
            model_revision=config.model_revision, runtime=config.runtime,
            request_payload=request_payload,
        )
        commitment = signer.sign(
            kind="request_content", contract_id=contract_id,
            digest=manifest.digest,
        )
        modality, input_unit, output_unit = CALCULATOR_CONTRACTS[config.calculator_type]
        payload = {
            "requestId": request_id, "contractId": contract_id,
            "billingAccountId": principal.billing_account_id,
            "requesterInstallationId": principal.installation_id,
            "assetCode": "PROMO_POINTS", "modelId": config.model_id,
            "modelRevision": config.model_revision, "runtime": config.runtime,
            "modality": modality, "inputUnit": input_unit, "outputUnit": output_unit,
            "priorityTier": config.priority_tier, "floatingPrice": False,
            "buyerMaximumMinor": config.buyer_maximum_minor,
            "quoteId": quote.id, "requestManifest": manifest.value,
            "requestCommitment": commitment.api_payload(),
        }
        try:
            response = await self.compute.request(
                "POST", "/v1/compute/requests", json=payload,
                headers={"Idempotency-Key": f"model-share-request:{request_id}"},
            )
        except ComputeCloudError as error:
            if _retry_quote and error.code == "COMPUTE_QUOTE_NOT_USABLE":
                return await self.create_multimodal_request(
                    principal=principal, signer=signer, config=config,
                    request_payload=request_payload, _retry_quote=False,
                )
            raise
        if (response.get("id") != request_id
                or response.get("contractId") != contract_id
                or response.get("requestDigest") != manifest.digest):
            raise ValueError("Cloud multimodal Request response does not match the local commitment")
        return manifest, quote, response

    async def open_session(
        self, *, principal: RequestPrincipal, contract: dict,
    ):
        if contract.get("status") != "held" or contract.get("buyerUserId") != principal.actor_user_id:
            raise ValueError("Compute Contract is not held for this buyer")
        return await self.broker.create_session(
            principal=principal, protocol=PeerProtocol.MODEL_SHARE_V1,
            peer_user_id=contract["providerUserId"], purpose_id=contract["id"],
            idempotency_key=f"model-share-session:{contract['id']}",
            requested_transports=("direct_quic", "relay_https"),
        )

    async def stream(
        self, *, principal: RequestPrincipal, signer: ComputeCommitmentSigner,
        manifest: ComputeRequestManifest, session, transport: PeerStreamingTransport | None = None,
    ) -> AsyncIterator[ModelShareEvent]:
        if session.status != "active":
            raise ValueError("Model Share Peer Session is not active")
        grant = self.broker.grant_for(session.session_id)
        if grant is None:
            grant = await self.broker.refresh_grant(principal, session.session_id)
        if transport is None:
            if self.peer_core is None:
                raise ValueError("Model Share transport is not configured")
            transport = await self.peer_core.transport_for(
                principal=principal, session=session, grant=grant,
            )
        request = InferenceRequest(
            session_id=session.session_id, contract_id=session.purpose_id,
            request_digest=manifest.digest, request_manifest=manifest,
        )
        self.jobs.begin(
            contract_id=session.purpose_id, session_id=session.session_id,
            owner_user_id=principal.actor_user_id, role="buyer", request_digest=manifest.digest,
        )
        response = await transport.post_stream(
            path="/v1/model-share/peer/v1/inference", grant=grant.compact,
            payload=request.payload(), max_response_bytes=session.transport_policy.max_bytes,
        )
        decoder = SseEventDecoder(contract_id=session.purpose_id, request_digest=manifest.digest)
        try:
            async for chunk in response.body:
                for event in decoder.feed(chunk):
                    yield event
            decoder.finish()
            assert decoder.result_manifest is not None and decoder.result_digest is not None
            receipt = signer.sign(kind="delivery_receipt", contract_id=session.purpose_id, digest=decoder.result_digest)
            settled = await self.compute.delivery_receipt(session.purpose_id, receipt.api_payload())
            if settled.get("status") != "settled_pending":
                raise ValueError("Cloud did not settle the verified delivery receipt")
            self.jobs.set_status(session.purpose_id, "completed", result_digest=decoder.result_digest)
        except BaseException:
            self.jobs.set_status(session.purpose_id, "result_unknown")
            raise

    async def fetch_audio(
        self, *, principal: RequestPrincipal, signer: ComputeCommitmentSigner,
        manifest: AudioTTSRequestManifest, session,
        transport: PeerStreamingTransport | None = None,
    ) -> bytes:
        if session.status != "active":
            raise ValueError("Model Share Peer Session is not active")
        grant = self.broker.grant_for(session.session_id)
        if grant is None:
            grant = await self.broker.refresh_grant(principal, session.session_id)
        if transport is None:
            if self.peer_core is None:
                raise ValueError("Model Share transport is not configured")
            transport = await self.peer_core.transport_for(
                principal=principal, session=session, grant=grant,
            )
        request = InferenceRequest(
            session_id=session.session_id, contract_id=session.purpose_id,
            request_digest=manifest.digest, request_manifest=manifest,
        )
        self.jobs.begin(
            contract_id=session.purpose_id, session_id=session.session_id,
            owner_user_id=principal.actor_user_id, role="buyer",
            request_digest=manifest.digest,
        )
        response = await transport.post_stream(
            path="/v1/model-share/peer/v1/inference", grant=grant.compact,
            payload=request.payload(),
            max_response_bytes=session.transport_policy.max_bytes,
        )
        decoder = AudioTtsSseEventDecoder(
            contract_id=session.purpose_id, request_digest=manifest.digest,
        )
        try:
            async for chunk in response.body:
                decoder.feed(chunk)
            decoder.finish()
            assert decoder.result_digest is not None
            receipt = signer.sign(
                kind="delivery_receipt", contract_id=session.purpose_id,
                digest=decoder.result_digest,
            )
            settled = await self.compute.delivery_receipt(
                session.purpose_id, receipt.api_payload(),
            )
            if settled.get("status") != "settled_pending":
                raise ValueError("Cloud did not settle the verified TTS delivery receipt")
            self.jobs.set_status(
                session.purpose_id, "completed",
                result_digest=decoder.result_digest,
            )
            return decoder.audio
        except BaseException:
            self.jobs.set_status(session.purpose_id, "result_unknown")
            raise

    async def fetch_multimodal_artifact(
        self, *, principal: RequestPrincipal, signer: ComputeCommitmentSigner,
        manifest: MultimodalRequestManifest, request_payload: dict[str, Any],
        session, maximum_charge_minor: str | None = None,
        transport: PeerStreamingTransport | None = None,
    ) -> tuple[bytes, dict[str, Any]]:
        if session.status != "active":
            raise ValueError("Model Share Peer Session is not active")
        grant = self.broker.grant_for(session.session_id)
        if grant is None:
            grant = await self.broker.refresh_grant(principal, session.session_id)
        if transport is None:
            if self.peer_core is None:
                raise ValueError("Model Share transport is not configured")
            transport = await self.peer_core.transport_for(
                principal=principal, session=session, grant=grant,
            )
        request = InferenceRequest(
            session_id=session.session_id, contract_id=session.purpose_id,
            request_digest=manifest.digest, request_manifest=manifest,
            request_payload=request_payload,
        )
        self.jobs.begin(
            contract_id=session.purpose_id, session_id=session.session_id,
            owner_user_id=principal.actor_user_id, role="buyer",
            request_digest=manifest.digest,
            calculator_type=manifest.value["calculatorType"],
            maximum_charge_minor=maximum_charge_minor,
        )
        response = await transport.post_stream(
            path="/v1/model-share/peer/v1/inference", grant=grant.compact,
            payload=request.payload(), max_response_bytes=session.transport_policy.max_bytes,
        )
        decoder = MultimodalArtifactSseEventDecoder(
            contract_id=session.purpose_id, request_digest=manifest.digest,
            calculator_type=manifest.value["calculatorType"],
            maximum_bytes=session.transport_policy.max_bytes,
        )
        try:
            async for chunk in response.body:
                decoder.feed(chunk)
            decoder.finish()
            assert decoder.result_digest is not None and decoder.actual_usage is not None
            receipt = signer.sign(
                kind="delivery_receipt", contract_id=session.purpose_id,
                digest=decoder.result_digest,
            )
            settled = await self.compute.delivery_receipt(
                session.purpose_id, receipt.api_payload(),
            )
            if settled.get("status") != "settled_pending":
                raise ValueError("Cloud did not settle the verified multimodal delivery receipt")
            self.jobs.set_status(
                session.purpose_id, "completed", result_digest=decoder.result_digest,
                actual_usage=decoder.actual_usage,
                charged_minor=settled.get("chargedMinor"),
                released_minor=(str(int(maximum_charge_minor) - int(settled["chargedMinor"]))
                                if maximum_charge_minor and settled.get("chargedMinor") else None),
            )
            return decoder.artifact, decoder.actual_usage
        except BaseException:
            self.jobs.set_status(session.purpose_id, "result_unknown")
            raise
