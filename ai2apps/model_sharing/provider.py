"""Provider-side Model Share v1 authorization and streaming execution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Protocol

from ai2apps.identity import RequestPrincipal
from ai2apps.peer.broker import PeerBrokerClient, PeerBrokerError
from ai2apps.peer.grants import PeerGrantError, verify_peer_grant
from ai2apps.peer.identity import PeerProtocol, b64url_encode
from ai2apps.peer.repository import PeerSessionRepository

from .cloud import ComputeCloudClient
from .commitments import ComputeCommitmentSigner
from .manifests import (
    AudioTTSRequestManifest,
    AudioTTSResultManifest,
    ComputeRequestManifest,
    ComputeResultManifest,
    MultimodalRequestManifest,
    MultimodalResultManifest,
)
from .pricing import CALCULATOR_CONTRACTS, validate_actual_usage
from .protocol import InferenceRequest
from .repository import ModelShareRepository

if TYPE_CHECKING:
    from ai2apps.peer.core import PeerTransportCore


class ModelShareProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class InferenceUsage:
    input_tokens: int
    output_tokens: int
    finish_reason: str


class ProviderInferenceExecution(Protocol):
    def deltas(self) -> AsyncIterator[str]: ...
    async def usage(self) -> InferenceUsage: ...


InferenceHandler = Callable[[ComputeRequestManifest], Awaitable[ProviderInferenceExecution]]
SignerFactory = Callable[[RequestPrincipal], Awaitable[ComputeCommitmentSigner]]


def _sse(event: str, data: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, separators=(',', ':'))}\n\n".encode()


class ModelShareProviderService:
    """Authenticates before Worker dispatch and commits a result before payload release."""

    def __init__(
        self, *, broker: PeerBrokerClient, peer_sessions: PeerSessionRepository,
        jobs: ModelShareRepository, compute: ComputeCloudClient,
        signer_factory: SignerFactory, inference_handler: InferenceHandler,
        peer_core: PeerTransportCore | None = None,
    ) -> None:
        self.broker = broker
        self.peer_sessions = peer_sessions
        self.jobs = jobs
        self.compute = compute
        self.signer_factory = signer_factory
        self.inference_handler = inference_handler
        self.peer_core = peer_core

    async def accept_pending_sessions(self, principal: RequestPrincipal) -> list[str]:
        accepted: list[str] = []
        for session in await self.broker.list_sessions(principal, status="pending"):
            if session.protocol is PeerProtocol.MODEL_SHARE_V1 and session.peer_endpoint.user_id != principal.actor_user_id:
                active = await self.broker.accept_session(principal, session.session_id)
                if active.status == "active":
                    if self.peer_core is not None:
                        with suppress(OSError, PeerBrokerError):
                            await self.peer_core.publish_direct_candidate(principal, active, self.broker)
                    accepted.append(active.session_id)
        return accepted

    async def inference(self, *, principal: RequestPrincipal, bearer_grant: str, request: InferenceRequest) -> AsyncIterator[bytes]:
        record = self.peer_sessions.get(request.session_id)
        if record is None or record.owner_user_id != principal.actor_user_id:
            raise ModelShareProviderError("PEER_SESSION_NOT_FOUND", "Peer Session was not found.", status_code=404)
        session = record.session
        if session.protocol is not PeerProtocol.MODEL_SHARE_V1 or session.status != "active" or session.purpose_id != request.contract_id:
            raise ModelShareProviderError("PEER_SESSION_INVALID", "Peer Session cannot authorize this job.", status_code=403)
        if session.expires_at <= datetime.now(UTC):
            raise ModelShareProviderError("PEER_SESSION_EXPIRED", "Peer Session expired.", status_code=401)
        try:
            grant = verify_peer_grant(
                bearer_grant, await self.broker.jwks(), session=session,
                # The inbound bearer belongs to the remote Buyer. The
                # Provider's own holder-bound Grant is never sent by Buyer.
                holder_user_id=session.peer_endpoint.user_id,
                holder_device_id=session.peer_endpoint.device_id,
            )
        except PeerGrantError as error:
            raise ModelShareProviderError("PEER_GRANT_INVALID", str(error), status_code=401) from error
        if not self.peer_sessions.consume_grant_jti(
            jti=grant.claims["jti"], session_id=session.session_id,
            expires_at=datetime.fromtimestamp(grant.claims["exp"], UTC),
        ):
            raise ModelShareProviderError("PEER_GRANT_REPLAYED", "Peer Grant was already consumed.", status_code=409)
        contract = await self.compute.get_contract(request.contract_id)
        manifest = request.request_manifest.value
        multimodal = isinstance(request.request_manifest, MultimodalRequestManifest)
        model = ({"id": manifest["modelId"], "revision": manifest["modelRevision"],
                  "runtime": manifest["runtime"]} if multimodal else manifest["model"])
        expected_contract = {
            "id": request.contract_id,
            "providerUserId": principal.actor_user_id,
            "buyerUserId": session.peer_endpoint.user_id,
            "requestDigest": request.request_digest,
            "modelId": model["id"],
            "modelRevision": model["revision"],
            "runtime": model["runtime"],
            "assetCode": "PROMO_POINTS",
            "status": "held",
        }
        if multimodal:
            calculator = manifest["calculatorType"]
            expected_modality, input_unit, output_unit = CALCULATOR_CONTRACTS[calculator]
            expected_units = (input_unit, output_unit)
        else:
            calculator = None
            expected_modality = "audio_tts" if isinstance(request.request_manifest, AudioTTSRequestManifest) else "text"
            expected_units = (("unicode_scalar", "audio_millisecond")
                              if expected_modality == "audio_tts" else ("token", "token"))
        if (contract.get("modality", "text") != expected_modality
                or contract.get("inputUnit", "token") != expected_units[0]
                or contract.get("outputUnit", "token") != expected_units[1]
                or multimodal and contract.get("calculatorType") != calculator
                or any(contract.get(name) != value for name, value in expected_contract.items())):
            raise ModelShareProviderError("COMPUTE_CONTRACT_MISMATCH", "Compute Contract does not authorize this input.", status_code=403)
        if multimodal:
            pricing_input = contract.get("pricingInput")
            bounded_usage = contract.get("boundedUsage")
            if not isinstance(pricing_input, dict) or not isinstance(bounded_usage, dict):
                raise ModelShareProviderError(
                    "COMPUTE_CONTRACT_MISMATCH",
                    "Compute Contract omitted its frozen pricing bounds.", status_code=403,
                )
            if calculator == "tts_v1":
                payload = request.request_payload or {}
                bound_input = {
                    "unicodeScalarCount": len(payload.get("text", "")) if isinstance(payload.get("text"), str) else -1,
                    "speedBps": payload.get("speedBps"),
                    "customSampleUsed": payload.get("customSampleUsed"),
                    "quality": payload.get("quality"),
                }
                if pricing_input != bound_input or not isinstance(bounded_usage.get("maximumDurationMs"), int):
                    raise ModelShareProviderError(
                        "COMPUTE_PRICING_INVALID",
                        "TTS payload does not match the frozen pricing input.", status_code=422,
                    )
        _, created = self.jobs.begin(
            contract_id=request.contract_id, session_id=request.session_id,
            owner_user_id=principal.actor_user_id, role="provider",
            request_digest=request.request_digest,
            calculator_type=calculator,
            maximum_charge_minor=contract.get("maximumChargeMinor") if multimodal else None,
        )
        if not created:
            raise ModelShareProviderError("COMPUTE_RESULT_UNKNOWN", "This Contract was already dispatched.", status_code=409)
        signer = await self.signer_factory(principal)
        acceptance = signer.sign(kind="input_acceptance", contract_id=request.contract_id, digest=request.request_digest)
        running = await self.compute.input_acceptance(request.contract_id, acceptance.api_payload())
        if running.get("status") != "running":
            raise ModelShareProviderError("COMPUTE_INPUT_NOT_ACCEPTED", "Cloud did not authorize Worker execution.", status_code=409)
        self.jobs.set_status(request.contract_id, "running")
        execution = await self.inference_handler(
            request.request_manifest, request.request_payload
        ) if multimodal else await self.inference_handler(request.request_manifest)

        if multimodal:
            return self._multimodal_stream(
                request=request, session=session, signer=signer,
                execution=execution, calculator_type=calculator,
                bounded_usage=contract["boundedUsage"],
            )

        if isinstance(request.request_manifest, AudioTTSRequestManifest):
            return self._audio_stream(
                request=request, session=session, signer=signer,
                execution=execution,
            )

        async def stream() -> AsyncIterator[bytes]:
            sequence = 0
            terminal = False
            yield _sse("job.accepted", {
                "protocolVersion": 1, "contractId": request.contract_id,
                "requestDigest": request.request_digest, "sequence": sequence,
            })
            sequence += 1
            text_parts: list[str] = []
            text_bytes = 0
            try:
                async for delta in execution.deltas():
                    if not isinstance(delta, str):
                        raise ModelShareProviderError("MODEL_OUTPUT_INVALID", "Worker returned a non-text delta.", status_code=502)
                    text_bytes += len(delta.encode("utf-8"))
                    if text_bytes > min(session.transport_policy.max_bytes, 4_000_000):
                        raise ModelShareProviderError("MODEL_OUTPUT_LIMIT_EXCEEDED", "Worker output exceeded the Contract limit.", status_code=413)
                    text_parts.append(delta)
                    yield _sse("output.delta", {"contractId": request.contract_id, "sequence": sequence, "text": delta})
                    sequence += 1
                usage = await execution.usage()
                if usage.input_tokens < 0 or usage.output_tokens < 0:
                    raise ModelShareProviderError("MODEL_USAGE_INVALID", "Worker usage is invalid.", status_code=502)
                result = ComputeResultManifest.create(
                    contract_id=request.contract_id, request_digest=request.request_digest,
                    text="".join(text_parts), finish_reason=usage.finish_reason,
                )
                commitment = signer.sign(kind="result_content", contract_id=request.contract_id, digest=result.digest)
                payload = commitment.api_payload() | {"inputTokens": usage.input_tokens, "outputTokens": usage.output_tokens}
                committed = await self.compute.result_commitment(request.contract_id, payload)
                if committed.get("status") != "result_committed":
                    raise ModelShareProviderError("COMPUTE_RESULT_NOT_COMMITTED", "Cloud did not accept the Result commitment.", status_code=409)
                self.jobs.set_status(
                    request.contract_id, "result_committed", result_digest=result.digest,
                    input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                )
                yield _sse("result.committed", {
                    "contractId": request.contract_id, "sequence": sequence,
                    "resultDigest": result.digest, "inputTokens": usage.input_tokens,
                    "outputTokens": usage.output_tokens,
                })
                sequence += 1
                yield _sse("result.payload", {"contractId": request.contract_id, "sequence": sequence, "resultManifest": result.value})
                sequence += 1
                self.jobs.set_status(request.contract_id, "completed")
                terminal = True
                yield _sse("job.completed", {"contractId": request.contract_id, "sequence": sequence})
            except BaseException:
                if not terminal:
                    self.jobs.set_status(request.contract_id, "result_unknown")
                raise

        return stream()

    def _audio_stream(self, *, request, session, signer, execution) -> AsyncIterator[bytes]:
        async def stream() -> AsyncIterator[bytes]:
            sequence = 0
            terminal = False
            yield _sse("job.accepted", {
                "protocolVersion": 2, "contractId": request.contract_id,
                "requestDigest": request.request_digest, "sequence": sequence,
            })
            sequence += 1
            try:
                audio = getattr(execution, "audio", None)
                input_units = getattr(execution, "input_units", None)
                output_units = getattr(execution, "output_units", None)
                if not isinstance(audio, bytes) or not audio:
                    raise ModelShareProviderError(
                        "MODEL_AUDIO_INVALID", "Worker returned no WAV artifact.",
                        status_code=502,
                    )
                if len(audio) > min(session.transport_policy.max_bytes, 67_108_864):
                    raise ModelShareProviderError(
                        "MODEL_OUTPUT_LIMIT_EXCEEDED", "WAV artifact exceeded the Contract limit.",
                        status_code=413,
                    )
                if any(isinstance(value, bool) or not isinstance(value, int) or value < 1
                       for value in (input_units, output_units)):
                    raise ModelShareProviderError(
                        "MODEL_USAGE_INVALID", "TTS metered usage is invalid.",
                        status_code=502,
                    )
                for offset in range(0, len(audio), 262_144):
                    chunk = audio[offset:offset + 262_144]
                    yield _sse("output.audio.chunk", {
                        "contractId": request.contract_id, "sequence": sequence,
                        "artifactId": "audio-0", "offset": offset,
                        "bytes": b64url_encode(chunk),
                        "final": offset + len(chunk) == len(audio),
                    })
                    sequence += 1
                result = AudioTTSResultManifest.create(
                    contract_id=request.contract_id,
                    request_digest=request.request_digest,
                    size_bytes=len(audio),
                    content_digest=hashlib.sha256(audio).hexdigest(),
                    input_units=input_units,
                    output_units=output_units,
                )
                commitment = signer.sign(
                    kind="result_content", contract_id=request.contract_id,
                    digest=result.digest,
                )
                committed = await self.compute.result_commitment(
                    request.contract_id,
                    commitment.api_payload() | {
                        "inputUnits": input_units, "outputUnits": output_units,
                    },
                )
                if committed.get("status") != "result_committed":
                    raise ModelShareProviderError(
                        "COMPUTE_RESULT_NOT_COMMITTED",
                        "Cloud did not accept the TTS Result commitment.",
                        status_code=409,
                    )
                self.jobs.set_status(
                    request.contract_id, "result_committed",
                    result_digest=result.digest,
                    input_tokens=input_units, output_tokens=output_units,
                )
                yield _sse("result.committed", {
                    "contractId": request.contract_id, "sequence": sequence,
                    "resultDigest": result.digest,
                    "inputUnit": "unicode_scalar", "inputUnits": input_units,
                    "outputUnit": "audio_millisecond", "outputUnits": output_units,
                })
                sequence += 1
                yield _sse("result.payload", {
                    "contractId": request.contract_id, "sequence": sequence,
                    "resultManifest": result.value,
                })
                sequence += 1
                self.jobs.set_status(request.contract_id, "completed")
                terminal = True
                yield _sse("job.completed", {
                    "contractId": request.contract_id, "sequence": sequence,
                })
            except BaseException:
                if not terminal:
                    self.jobs.set_status(request.contract_id, "result_unknown")
                raise

        return stream()

    def _multimodal_stream(
        self, *, request, session, signer, execution, calculator_type: str,
        bounded_usage: dict,
    ) -> AsyncIterator[bytes]:
        async def stream() -> AsyncIterator[bytes]:
            sequence = 0
            terminal = False
            yield _sse("job.accepted", {
                "protocolVersion": 3, "contractId": request.contract_id,
                "requestDigest": request.request_digest,
                "calculatorType": calculator_type, "sequence": sequence,
            })
            sequence += 1
            try:
                artifact = getattr(execution, "artifact", None)
                content_type = getattr(execution, "content_type", None)
                actual_usage = validate_actual_usage(
                    calculator_type, getattr(execution, "actual_usage", None),
                )
                if (calculator_type == "tts_v1"
                        and actual_usage["outputDurationMs"] > bounded_usage["maximumDurationMs"]):
                    raise ModelShareProviderError(
                        "COMPUTE_PRICING_INVALID",
                        "Final TTS duration exceeds the frozen quote bound.",
                        status_code=422,
                    )
                if not isinstance(artifact, bytes) or not artifact:
                    raise ModelShareProviderError(
                        "MODEL_ARTIFACT_INVALID", "Worker returned no final artifact.",
                        status_code=502,
                    )
                if (not isinstance(content_type, str) or not content_type
                        or len(artifact) > session.transport_policy.max_bytes):
                    raise ModelShareProviderError(
                        "MODEL_OUTPUT_LIMIT_EXCEEDED",
                        "Final artifact exceeds the Contract transport limit.",
                        status_code=413,
                    )
                for offset in range(0, len(artifact), 262_144):
                    chunk = artifact[offset:offset + 262_144]
                    yield _sse("output.artifact.chunk", {
                        "contractId": request.contract_id, "sequence": sequence,
                        "artifactId": "artifact-0", "offset": offset,
                        "bytes": b64url_encode(chunk),
                        "final": offset + len(chunk) == len(artifact),
                    })
                    sequence += 1
                result = MultimodalResultManifest.create(
                    contract_id=request.contract_id,
                    calculator_type=calculator_type,
                    actual_usage=actual_usage,
                    artifacts=[{
                        "sha256": hashlib.sha256(artifact).hexdigest(),
                        "contentType": content_type,
                        "byteSize": str(len(artifact)),
                    }],
                )
                commitment = signer.sign(
                    kind="result_content", contract_id=request.contract_id,
                    digest=result.digest,
                )
                committed = await self.compute.result_commitment(
                    request.contract_id,
                    commitment.api_payload() | {
                        "actualUsage": actual_usage,
                        "resultManifest": result.value,
                    },
                )
                if committed.get("status") != "result_committed":
                    raise ModelShareProviderError(
                        "COMPUTE_RESULT_NOT_COMMITTED",
                        "Cloud did not accept the multimodal Result commitment.",
                        status_code=409,
                    )
                self.jobs.set_status(
                    request.contract_id, "result_committed",
                    result_digest=result.digest,
                    actual_usage=actual_usage,
                    charged_minor=committed.get("chargedMinor"),
                    released_minor=(str(int(bounded_charge) - int(committed["chargedMinor"]))
                                    if (bounded_charge := committed.get("maximumChargeMinor"))
                                    and committed.get("chargedMinor") else None),
                )
                yield _sse("result.committed", {
                    "contractId": request.contract_id, "sequence": sequence,
                    "resultDigest": result.digest, "actualUsage": actual_usage,
                })
                sequence += 1
                yield _sse("result.payload", {
                    "contractId": request.contract_id, "sequence": sequence,
                    "resultManifest": result.value,
                })
                sequence += 1
                self.jobs.set_status(request.contract_id, "completed")
                terminal = True
                yield _sse("job.completed", {
                    "contractId": request.contract_id, "sequence": sequence,
                })
            except BaseException:
                if not terminal:
                    self.jobs.set_status(request.contract_id, "result_unknown")
                raise

        return stream()
