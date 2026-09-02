"""Model Share v1 request and strictly ordered SSE application protocol."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ai2apps.peer.identity import b64url_decode

from .manifests import (
    AudioTTSRequestManifest,
    AudioTTSResultManifest,
    ComputeRequestManifest,
    ComputeResultManifest,
    MultimodalRequestManifest,
    MultimodalResultManifest,
    request_payload_digest,
)
from .pricing import validate_actual_usage


class ModelShareProtocolError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    session_id: str
    contract_id: str
    request_digest: str
    request_manifest: ComputeRequestManifest | AudioTTSRequestManifest | MultimodalRequestManifest
    request_payload: dict[str, Any] | None = None

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> InferenceRequest:
        if not isinstance(value, Mapping) or set(value) != {
            "protocolVersion", "sessionId", "contractId", "requestDigest", "requestManifest", "stream"
        } and set(value) != {
            "protocolVersion", "sessionId", "contractId", "requestDigest", "requestManifest", "requestPayload", "stream"
        }:
            raise ModelShareProtocolError("Inference request fields are invalid")
        protocol_version = value.get("protocolVersion")
        if protocol_version not in {1, 2, 3} or value.get("stream") is not True:
            raise ModelShareProtocolError("Only streaming Model Share protocol v1, v2, or v3 is supported")
        try:
            manifest = (
                ComputeRequestManifest.parse(value.get("requestManifest"))
                if protocol_version == 1 else
                AudioTTSRequestManifest.parse(value.get("requestManifest"))
                if protocol_version == 2 else
                MultimodalRequestManifest.parse(value.get("requestManifest"))
            )
        except (TypeError, ValueError) as error:
            raise ModelShareProtocolError(str(error)) from error
        digest = value.get("requestDigest")
        contract_id = value.get("contractId")
        session_id = value.get("sessionId")
        if digest != manifest.digest:
            raise ModelShareProtocolError("Request digest does not match the Manifest")
        if not isinstance(contract_id, str) or not isinstance(session_id, str):
            raise ModelShareProtocolError("Inference identity is invalid")
        try:
            if str(UUID(contract_id)) != contract_id or str(UUID(session_id)) != session_id:
                raise ValueError
        except ValueError as error:
            raise ModelShareProtocolError("Inference identity must use canonical UUIDs") from error
        request_payload = value.get("requestPayload")
        if protocol_version == 3:
            if not isinstance(request_payload, Mapping):
                raise ModelShareProtocolError("Multimodal request payload is missing")
            request_payload = dict(request_payload)
            if request_payload_digest(request_payload) != manifest.value["requestPayloadDigest"]:
                raise ModelShareProtocolError("Request payload does not match its signed digest")
            if manifest.value["contractId"] != contract_id:
                raise ModelShareProtocolError("Request manifest does not bind this Contract")
        elif request_payload is not None:
            raise ModelShareProtocolError("Legacy inference cannot carry requestPayload")
        return cls(session_id, contract_id, digest, manifest, request_payload)

    def payload(self) -> bytes:
        protocol_version = (3 if isinstance(self.request_manifest, MultimodalRequestManifest)
                            else 2 if isinstance(self.request_manifest, AudioTTSRequestManifest) else 1)
        value = {
            "protocolVersion": protocol_version,
            "sessionId": self.session_id,
            "contractId": self.contract_id,
            "requestDigest": self.request_digest,
            "requestManifest": self.request_manifest.value,
            "stream": True,
        }
        if protocol_version == 3:
            if self.request_payload is None:
                raise ModelShareProtocolError("Multimodal request payload is missing")
            value["requestPayload"] = self.request_payload
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ModelShareEvent:
    event: str
    data: dict[str, Any]


class SseEventDecoder:
    """Incremental SSE decoder enforcing the frozen event order and sequence."""

    def __init__(self, *, contract_id: str, request_digest: str) -> None:
        self.contract_id = contract_id
        self.request_digest = request_digest
        self._buffer = bytearray()
        self._next_sequence = 0
        self._state = "accepted"
        self.result_digest: str | None = None
        self.result_manifest: ComputeResultManifest | None = None

    def feed(self, chunk: bytes) -> list[ModelShareEvent]:
        self._buffer.extend(chunk)
        events: list[ModelShareEvent] = []
        while b"\n\n" in self._buffer:
            raw, _, remaining = self._buffer.partition(b"\n\n")
            self._buffer = bytearray(remaining)
            if raw:
                events.append(self._parse(raw))
        return events

    def finish(self) -> None:
        if self._buffer:
            raise ModelShareProtocolError("SSE stream ended with a partial event")
        if self._state != "done" or self.result_manifest is None:
            raise ModelShareProtocolError("SSE stream ended before a verified result")

    def _parse(self, raw: bytes) -> ModelShareEvent:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ModelShareProtocolError("SSE event is not UTF-8") from error
        lines = text.split("\n")
        if len(lines) != 2 or not lines[0].startswith("event: ") or not lines[1].startswith("data: "):
            raise ModelShareProtocolError("SSE event framing is invalid")
        event = lines[0][7:]
        allowed = {
            "accepted": {"job.accepted"},
            "streaming": {"output.delta", "result.committed"},
            "committed": {"result.payload"},
            "payload": {"job.completed"},
            "done": set(),
        }[self._state]
        if event not in allowed:
            raise ModelShareProtocolError("SSE event order is invalid")
        try:
            data = json.loads(lines[1][6:])
        except json.JSONDecodeError as error:
            raise ModelShareProtocolError("SSE event data is invalid JSON") from error
        if not isinstance(data, dict) or data.get("contractId") != self.contract_id or data.get("sequence") != self._next_sequence:
            raise ModelShareProtocolError("SSE event identity or sequence is invalid")
        if event == "job.accepted" and (data.get("protocolVersion") != 1 or data.get("requestDigest") != self.request_digest):
            raise ModelShareProtocolError("Job acceptance binding is invalid")
        if event == "job.accepted":
            self._state = "streaming"
        if event == "output.delta" and not isinstance(data.get("text"), str):
            raise ModelShareProtocolError("Output delta is invalid")
        if event == "result.committed":
            digest = data.get("resultDigest")
            if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ModelShareProtocolError("Result commitment is invalid")
            if any(isinstance(data.get(name), bool) or not isinstance(data.get(name), int) or data[name] < 0 for name in ("inputTokens", "outputTokens")):
                raise ModelShareProtocolError("Result usage is invalid")
            self.result_digest = digest
            self._state = "committed"
        if event == "result.payload":
            try:
                manifest = ComputeResultManifest.parse(data.get("resultManifest"))
            except (TypeError, ValueError) as error:
                raise ModelShareProtocolError(str(error)) from error
            if manifest.value["contractId"] != self.contract_id or manifest.value["requestDigest"] != self.request_digest or manifest.digest != self.result_digest:
                raise ModelShareProtocolError("Result payload does not match its commitment")
            self.result_manifest = manifest
            self._state = "payload"
        if event == "job.completed":
            self._state = "done"
        self._next_sequence += 1
        return ModelShareEvent(event, data)


class AudioTtsSseEventDecoder:
    """Verify ordered v2 audio chunks, artifact digest, and metered usage."""

    def __init__(self, *, contract_id: str, request_digest: str) -> None:
        self.contract_id = contract_id
        self.request_digest = request_digest
        self._buffer = bytearray()
        self._audio = bytearray()
        self._next_sequence = 0
        self._state = "accepted"
        self._final_chunk = False
        self.result_digest: str | None = None
        self._committed_usage: tuple[int, int] | None = None
        self.result_manifest: AudioTTSResultManifest | None = None

    @property
    def audio(self) -> bytes:
        return bytes(self._audio)

    def feed(self, chunk: bytes) -> list[ModelShareEvent]:
        self._buffer.extend(chunk)
        events: list[ModelShareEvent] = []
        while b"\n\n" in self._buffer:
            raw, _, remaining = self._buffer.partition(b"\n\n")
            self._buffer = bytearray(remaining)
            if raw:
                events.append(self._parse(raw))
        return events

    def finish(self) -> None:
        if self._buffer or self._state != "done" or self.result_manifest is None:
            raise ModelShareProtocolError("Audio stream ended before a verified result")

    def _parse(self, raw: bytes) -> ModelShareEvent:
        try:
            lines = raw.decode("utf-8").split("\n")
        except UnicodeDecodeError as error:
            raise ModelShareProtocolError("SSE event is not UTF-8") from error
        if len(lines) != 2 or not lines[0].startswith("event: ") or not lines[1].startswith("data: "):
            raise ModelShareProtocolError("SSE event framing is invalid")
        event = lines[0][7:]
        allowed = {
            "accepted": {"job.accepted"},
            "audio": {"output.audio.chunk", "result.committed"},
            "committed": {"result.payload"},
            "payload": {"job.completed"},
            "done": set(),
        }[self._state]
        if event not in allowed:
            raise ModelShareProtocolError("Audio SSE event order is invalid")
        try:
            data = json.loads(lines[1][6:])
        except json.JSONDecodeError as error:
            raise ModelShareProtocolError("SSE event data is invalid JSON") from error
        if not isinstance(data, dict) or data.get("contractId") != self.contract_id or data.get("sequence") != self._next_sequence:
            raise ModelShareProtocolError("SSE event identity or sequence is invalid")
        if event == "job.accepted":
            if data.get("protocolVersion") != 2 or data.get("requestDigest") != self.request_digest:
                raise ModelShareProtocolError("Job acceptance binding is invalid")
            self._state = "audio"
        elif event == "output.audio.chunk":
            if self._final_chunk or data.get("artifactId") != "audio-0" or data.get("offset") != len(self._audio):
                raise ModelShareProtocolError("Audio chunk identity or offset is invalid")
            try:
                decoded = b64url_decode(data.get("bytes"))
            except (TypeError, ValueError) as error:
                raise ModelShareProtocolError("Audio chunk encoding is invalid") from error
            if not decoded or len(decoded) > 262_144 or len(self._audio) + len(decoded) > 67_108_864:
                raise ModelShareProtocolError("Audio chunk exceeds the protocol limit")
            self._audio.extend(decoded)
            if not isinstance(data.get("final"), bool):
                raise ModelShareProtocolError("Audio chunk final marker is invalid")
            self._final_chunk = data["final"]
        elif event == "result.committed":
            if not self._final_chunk:
                raise ModelShareProtocolError("Audio result was committed before its final chunk")
            digest = data.get("resultDigest")
            if (not isinstance(digest, str) or len(digest) != 64
                    or any(character not in "0123456789abcdef" for character in digest)):
                raise ModelShareProtocolError("Result commitment is invalid")
            if data.get("inputUnit") != "unicode_scalar" or data.get("outputUnit") != "audio_millisecond":
                raise ModelShareProtocolError("Audio result usage units are invalid")
            if any(isinstance(data.get(name), bool) or not isinstance(data.get(name), int) or data[name] < 1 for name in ("inputUnits", "outputUnits")):
                raise ModelShareProtocolError("Audio result usage is invalid")
            self.result_digest = digest
            self._committed_usage = (data["inputUnits"], data["outputUnits"])
            self._state = "committed"
        elif event == "result.payload":
            try:
                manifest = AudioTTSResultManifest.parse(data.get("resultManifest"))
            except (TypeError, ValueError) as error:
                raise ModelShareProtocolError(str(error)) from error
            part = manifest.value["parts"][0]
            usage = manifest.value["usage"]
            if (manifest.value["contractId"] != self.contract_id
                    or manifest.value["requestDigest"] != self.request_digest
                    or manifest.digest != self.result_digest
                    or (usage["inputUnits"], usage["outputUnits"]) != self._committed_usage
                    or part["sizeBytes"] != len(self._audio)
                    or part["contentDigest"] != hashlib.sha256(self._audio).hexdigest()):
                raise ModelShareProtocolError("Audio Result does not match its commitment or bytes")
            self.result_manifest = manifest
            self._state = "payload"
        elif event == "job.completed":
            self._state = "done"
        self._next_sequence += 1
        return ModelShareEvent(event, data)


class MultimodalArtifactSseEventDecoder:
    """Verify v3 artifact bytes, actual usage, and signed result manifest."""

    def __init__(self, *, contract_id: str, request_digest: str,
                 calculator_type: str, maximum_bytes: int = 268_435_456) -> None:
        self.contract_id = contract_id
        self.request_digest = request_digest
        self.calculator_type = calculator_type
        self.maximum_bytes = maximum_bytes
        self._buffer = bytearray()
        self._artifact = bytearray()
        self._next_sequence = 0
        self._state = "accepted"
        self._final_chunk = False
        self.result_digest: str | None = None
        self.actual_usage: dict[str, Any] | None = None
        self.result_manifest: MultimodalResultManifest | None = None

    @property
    def artifact(self) -> bytes:
        return bytes(self._artifact)

    def feed(self, chunk: bytes) -> list[ModelShareEvent]:
        self._buffer.extend(chunk)
        events = []
        while b"\n\n" in self._buffer:
            raw, _, remaining = self._buffer.partition(b"\n\n")
            self._buffer = bytearray(remaining)
            if raw:
                events.append(self._parse(raw))
        return events

    def finish(self) -> None:
        if self._buffer or self._state != "done" or self.result_manifest is None:
            raise ModelShareProtocolError("Multimodal stream ended before a verified result")

    def _parse(self, raw: bytes) -> ModelShareEvent:
        try:
            lines = raw.decode("utf-8").split("\n")
            data = json.loads(lines[1][6:])
        except (UnicodeDecodeError, json.JSONDecodeError, IndexError) as error:
            raise ModelShareProtocolError("Multimodal SSE event is invalid") from error
        if len(lines) != 2 or not lines[0].startswith("event: ") or not lines[1].startswith("data: "):
            raise ModelShareProtocolError("Multimodal SSE framing is invalid")
        event = lines[0][7:]
        allowed = {"accepted": {"job.accepted"}, "artifact": {"output.artifact.chunk", "result.committed"},
                   "committed": {"result.payload"}, "payload": {"job.completed"}, "done": set()}[self._state]
        if event not in allowed or not isinstance(data, dict) or data.get("contractId") != self.contract_id or data.get("sequence") != self._next_sequence:
            raise ModelShareProtocolError("Multimodal SSE order or identity is invalid")
        if event == "job.accepted":
            if data.get("protocolVersion") != 3 or data.get("requestDigest") != self.request_digest or data.get("calculatorType") != self.calculator_type:
                raise ModelShareProtocolError("Multimodal job binding is invalid")
            self._state = "artifact"
        elif event == "output.artifact.chunk":
            if self._final_chunk or data.get("artifactId") != "artifact-0" or data.get("offset") != len(self._artifact):
                raise ModelShareProtocolError("Artifact chunk identity or offset is invalid")
            try:
                decoded = b64url_decode(data.get("bytes"))
            except (TypeError, ValueError) as error:
                raise ModelShareProtocolError("Artifact chunk encoding is invalid") from error
            if not decoded or len(decoded) > 262_144 or len(self._artifact) + len(decoded) > self.maximum_bytes:
                raise ModelShareProtocolError("Artifact chunk exceeds the protocol limit")
            self._artifact.extend(decoded)
            if not isinstance(data.get("final"), bool):
                raise ModelShareProtocolError("Artifact final marker is invalid")
            self._final_chunk = data["final"]
        elif event == "result.committed":
            if not self._final_chunk:
                raise ModelShareProtocolError("Result was committed before the final artifact chunk")
            digest = data.get("resultDigest")
            if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise ModelShareProtocolError("Result commitment is invalid")
            try:
                self.actual_usage = validate_actual_usage(self.calculator_type, data.get("actualUsage"))
            except ValueError as error:
                raise ModelShareProtocolError(str(error)) from error
            self.result_digest = digest
            self._state = "committed"
        elif event == "result.payload":
            try:
                manifest = MultimodalResultManifest.parse(data.get("resultManifest"))
            except (TypeError, ValueError) as error:
                raise ModelShareProtocolError(str(error)) from error
            artifact = manifest.value["artifacts"][0]
            if (manifest.value["contractId"] != self.contract_id
                    or manifest.value["calculatorType"] != self.calculator_type
                    or manifest.value["actualUsage"] != self.actual_usage
                    or manifest.digest != self.result_digest
                    or artifact["byteSize"] != str(len(self._artifact))
                    or artifact["sha256"] != hashlib.sha256(self._artifact).hexdigest()):
                raise ModelShareProtocolError("Result manifest does not match its commitment or artifact")
            self.result_manifest = manifest
            self._state = "payload"
        elif event == "job.completed":
            self._state = "done"
        self._next_sequence += 1
        return ModelShareEvent(event, data)
