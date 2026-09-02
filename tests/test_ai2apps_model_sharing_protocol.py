import hashlib
import io
import json
import wave
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.model_sharing.buyer import ModelShareBuyerService
from ai2apps.model_sharing.controller import ModelShareProviderConfiguration
from ai2apps.model_sharing.manifests import (
    AudioTTSRequestManifest,
    AudioTTSResultManifest,
    ComputeRequestManifest,
    ComputeResultManifest,
    MultimodalRequestManifest,
    MultimodalResultManifest,
    canonical_json,
)
from ai2apps.model_sharing.manager import _request_model_id
from ai2apps.model_sharing.protocol import (
    AudioTtsSseEventDecoder,
    ModelShareProtocolError,
    SseEventDecoder,
    InferenceRequest,
    MultimodalArtifactSseEventDecoder,
)
from ai2apps.model_sharing.requester import ComputeRequestConfiguration
from ai2apps.model_sharing.runtime_adapter import (
    OmlxAudioTtsExecution,
    supports_audio_tts,
    supports_text_conversation,
)
from ai2apps.peer.broker import PeerBrokerClient
from ai2apps.peer.identity import b64url_encode


def _event(name, data):
    return f"event: {name}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n".encode()


def test_request_digest_is_stable_across_mapping_order():
    manifest = ComputeRequestManifest.create(
        request_id=str(uuid4()), requester_id=str(uuid4()), model_id="fixed-model",
        revision="a" * 40, runtime="omlx", maximum_amount_minor="10",
        prompt="hello", system_prompt=None, temperature=0, max_tokens=256,
    )
    reordered = dict(reversed(list(manifest.value.items())))
    assert ComputeRequestManifest.parse(reordered).digest == manifest.digest


def test_multimodal_request_uses_fixed_compute_digest_domain_and_binds_payload():
    request_id, contract_id, quote_id = (str(uuid4()) for _ in range(3))
    payload = {
        "text": "你好", "voice": "serena", "language": "zh",
        "instructions": None, "speedBps": 10_000,
        "customSampleUsed": False, "quality": "mid",
    }
    manifest = MultimodalRequestManifest.create(
        request_id=request_id, contract_id=contract_id, quote_id=quote_id,
        calculator_type="tts_v1", model_id="local/tts",
        model_revision="a" * 40, runtime="omlx", request_payload=payload,
    )
    expected = hashlib.sha256(
        b"ai2apps.compute.request.v1\0" + canonical_json(manifest.value)
    ).hexdigest()
    assert manifest.digest == expected

    request = InferenceRequest(
        session_id=str(uuid4()), contract_id=contract_id,
        request_digest=manifest.digest, request_manifest=manifest,
        request_payload=payload,
    )
    assert _request_model_id(request) == "local/tts"
    assert InferenceRequest.parse(json.loads(request.payload())).request_payload == payload
    broken = json.loads(request.payload())
    broken["requestPayload"]["text"] = "different"
    with pytest.raises(ModelShareProtocolError, match="signed digest"):
        InferenceRequest.parse(broken)


def test_multimodal_tts_stream_verifies_actual_usage_and_artifact():
    contract_id = str(uuid4())
    request_digest = "a" * 64
    audio = b"RIFF-final-audio"
    usage = {"outputDurationMs": 4280}
    result = MultimodalResultManifest.create(
        contract_id=contract_id, calculator_type="tts_v1",
        actual_usage=usage,
        artifacts=[{
            "sha256": hashlib.sha256(audio).hexdigest(),
            "contentType": "audio/wav", "byteSize": str(len(audio)),
        }],
    )
    stream = b"".join((
        _event("job.accepted", {"protocolVersion": 3, "contractId": contract_id,
                                "requestDigest": request_digest, "calculatorType": "tts_v1", "sequence": 0}),
        _event("output.artifact.chunk", {"contractId": contract_id, "sequence": 1,
                                         "artifactId": "artifact-0", "offset": 0,
                                         "bytes": b64url_encode(audio), "final": True}),
        _event("result.committed", {"contractId": contract_id, "sequence": 2,
                                    "resultDigest": result.digest, "actualUsage": usage}),
        _event("result.payload", {"contractId": contract_id, "sequence": 3,
                                  "resultManifest": result.value}),
        _event("job.completed", {"contractId": contract_id, "sequence": 4}),
    ))
    decoder = MultimodalArtifactSseEventDecoder(
        contract_id=contract_id, request_digest=request_digest,
        calculator_type="tts_v1",
    )
    decoder.feed(stream)
    decoder.finish()
    assert decoder.artifact == audio
    assert decoder.actual_usage == usage


def test_sse_accepts_many_deltas_then_verifies_full_result():
    contract_id = str(uuid4())
    request_digest = "1" * 64
    result = ComputeResultManifest.create(
        contract_id=contract_id, request_digest=request_digest, text="hello", finish_reason="stop"
    )
    stream = b"".join((
        _event("job.accepted", {"protocolVersion": 1, "contractId": contract_id, "requestDigest": request_digest, "sequence": 0}),
        _event("output.delta", {"contractId": contract_id, "sequence": 1, "text": "he"}),
        _event("output.delta", {"contractId": contract_id, "sequence": 2, "text": "llo"}),
        _event("result.committed", {"contractId": contract_id, "sequence": 3, "resultDigest": result.digest, "inputTokens": 1, "outputTokens": 2}),
        _event("result.payload", {"contractId": contract_id, "sequence": 4, "resultManifest": result.value}),
        _event("job.completed", {"contractId": contract_id, "sequence": 5}),
    ))
    decoder = SseEventDecoder(contract_id=contract_id, request_digest=request_digest)
    events = decoder.feed(stream[:31]) + decoder.feed(stream[31:])
    decoder.finish()
    assert [event.event for event in events].count("output.delta") == 2
    assert decoder.result_digest == result.digest


def test_sse_rejects_payload_before_commitment():
    contract_id = str(uuid4())
    decoder = SseEventDecoder(contract_id=contract_id, request_digest="2" * 64)
    decoder.feed(_event("job.accepted", {
        "protocolVersion": 1, "contractId": contract_id, "requestDigest": "2" * 64, "sequence": 0,
    }))
    with pytest.raises(ModelShareProtocolError):
        decoder.feed(_event("result.payload", {"contractId": contract_id, "sequence": 1, "resultManifest": {}}))


def test_provider_configuration_is_opt_in_and_strict(monkeypatch):
    monkeypatch.delenv("AI2APPS_MODEL_SHARE_PROVIDER_ENABLED", raising=False)
    assert ModelShareProviderConfiguration.from_environment().enabled is False

    monkeypatch.setenv("AI2APPS_MODEL_SHARE_PROVIDER_ENABLED", "1")
    monkeypatch.setenv("AI2APPS_MODEL_SHARE_RATE_CARD_ID", str(uuid4()))
    monkeypatch.setenv("AI2APPS_MODEL_SHARE_RATE_CARD_VERSION", "pilot-v1")
    monkeypatch.setenv("AI2APPS_MODEL_SHARE_MODEL_ID", "local/model")
    monkeypatch.setenv("AI2APPS_MODEL_SHARE_MODEL_REVISION", "a" * 40)
    config = ModelShareProviderConfiguration.from_environment()
    assert config.enabled is True
    assert config.runtime == "omlx"


def test_text_pilot_accepts_reviewed_llm_and_vlm_conversation_endpoints_only():
    def model(model_type, *, ready=True, endpoints=None):
        return SimpleNamespace(
            model_type=model_type,
            checkpoint_ready=ready,
            endpoints={"chat_completions": "/v1/chat/completions"} if endpoints is None else endpoints,
        )

    assert supports_text_conversation(model("llm")) is True
    assert supports_text_conversation(model("vlm")) is True
    assert supports_text_conversation(model("audio_tts")) is False
    assert supports_text_conversation(model("vlm", ready=False)) is False
    assert supports_text_conversation(model("vlm", endpoints={"images": "/v1/images"})) is False


def test_audio_tts_accepts_only_ready_reviewed_speech_endpoint():
    def model(model_type, *, ready=True, endpoints=None):
        return SimpleNamespace(
            model_type=model_type, checkpoint_ready=ready,
            endpoints={"audio_speech": "/v1/audio/speech"} if endpoints is None else endpoints,
        )

    assert supports_audio_tts(model("audio_tts")) is True
    assert supports_audio_tts(model("llm")) is False
    assert supports_audio_tts(model("audio_tts", ready=False)) is False
    assert supports_audio_tts(model("audio_tts", endpoints={"chat_completions": "/v1/chat/completions"})) is False


def test_audio_tts_stream_verifies_ordered_bytes_digest_and_usage():
    request = AudioTTSRequestManifest.create(
        request_id=str(uuid4()), requester_id=str(uuid4()), model_id="local/tts",
        revision="b" * 40, runtime="omlx", maximum_amount_minor="10",
        text="你好", voice="serena", language="zh", speed=1.0,
    )
    contract_id = str(uuid4())
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(b"\0\0" * 1_600)
    audio = buffer.getvalue()
    result = AudioTTSResultManifest.create(
        contract_id=contract_id, request_digest=request.digest,
        size_bytes=len(audio), content_digest=hashlib.sha256(audio).hexdigest(),
        input_units=2, output_units=100,
    )
    stream = b"".join((
        _event("job.accepted", {"protocolVersion": 2, "contractId": contract_id,
                                "requestDigest": request.digest, "sequence": 0}),
        _event("output.audio.chunk", {"contractId": contract_id, "sequence": 1,
                                      "artifactId": "audio-0", "offset": 0,
                                      "bytes": b64url_encode(audio), "final": True}),
        _event("result.committed", {"contractId": contract_id, "sequence": 2,
                                    "resultDigest": result.digest,
                                    "inputUnit": "unicode_scalar", "inputUnits": 2,
                                    "outputUnit": "audio_millisecond", "outputUnits": 100}),
        _event("result.payload", {"contractId": contract_id, "sequence": 3,
                                  "resultManifest": result.value}),
        _event("job.completed", {"contractId": contract_id, "sequence": 4}),
    ))
    decoder = AudioTtsSseEventDecoder(
        contract_id=contract_id, request_digest=request.digest,
    )
    decoder.feed(stream)
    decoder.finish()
    assert decoder.audio == audio

    broken = AudioTtsSseEventDecoder(
        contract_id=contract_id, request_digest=request.digest,
    )
    broken.feed(_event("job.accepted", {"protocolVersion": 2, "contractId": contract_id,
                                        "requestDigest": request.digest, "sequence": 0}))
    with pytest.raises(ModelShareProtocolError, match="offset"):
        broken.feed(_event("output.audio.chunk", {"contractId": contract_id, "sequence": 1,
                                                   "artifactId": "audio-0", "offset": 1,
                                                   "bytes": b64url_encode(audio), "final": True}))

    mismatched_usage = AudioTtsSseEventDecoder(
        contract_id=contract_id, request_digest=request.digest,
    )
    mismatched_usage.feed(b"".join((
        _event("job.accepted", {"protocolVersion": 2, "contractId": contract_id,
                                "requestDigest": request.digest, "sequence": 0}),
        _event("output.audio.chunk", {"contractId": contract_id, "sequence": 1,
                                      "artifactId": "audio-0", "offset": 0,
                                      "bytes": b64url_encode(audio), "final": True}),
        _event("result.committed", {"contractId": contract_id, "sequence": 2,
                                    "resultDigest": result.digest,
                                    "inputUnit": "unicode_scalar", "inputUnits": 3,
                                    "outputUnit": "audio_millisecond", "outputUnits": 100}),
    )))
    with pytest.raises(ModelShareProtocolError, match="commitment or bytes"):
        mismatched_usage.feed(_event("result.payload", {
            "contractId": contract_id, "sequence": 3, "resultManifest": result.value,
        }))


def test_audio_tts_request_rejects_surrogate_code_points():
    with pytest.raises(ValueError, match="Unicode scalar"):
        AudioTTSRequestManifest.create(
            request_id=str(uuid4()), requester_id=str(uuid4()), model_id="local/tts",
            revision="b" * 40, runtime="omlx", maximum_amount_minor="10",
            text="bad\ud800text", voice="serena",
        )


def test_audio_tts_execution_derives_duration_from_wav_not_buyer_input():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24_000)
        wav.writeframes(b"\0\0" * 12_000)

    execution = OmlxAudioTtsExecution(buffer.getvalue(), input_units=7)

    assert execution.input_units == 7
    assert execution.output_units == 500


def test_compute_request_configuration_rejects_ambiguous_numeric_values():
    valid = {
        "model_id": "local/model",
        "model_revision": "a" * 40,
        "runtime": "omlx",
        "expected_rate_card_version": "pilot-v1",
        "maximum_amount_minor": "10",
        "estimated_input_tokens": 2,
        "maximum_output_tokens": 64,
    }
    assert ComputeRequestConfiguration(**valid).maximum_amount_minor == "10"

    for changes in (
        {"maximum_amount_minor": "01"},
        {"maximum_amount_minor": "0"},
        {"estimated_input_tokens": True},
        {"estimated_input_tokens": -1},
        {"maximum_output_tokens": 0},
        {"priority_tier": "rush"},
    ):
        with pytest.raises(ValueError):
            ComputeRequestConfiguration(**(valid | changes))


@pytest.mark.asyncio
async def test_peer_session_list_consumes_cloud_items_envelope():
    client = object.__new__(PeerBrokerClient)
    session_payload = {"sessionId": str(uuid4())}

    async def request(*_args, **_kwargs):
        return {"items": [session_payload]}

    async def consume(item, _principal):
        return item

    client._request = request
    client._consume_session = consume

    assert await client.list_sessions(object()) == [session_payload]


@pytest.mark.asyncio
async def test_buyer_waits_for_session_until_contract_expiry():
    now = datetime.now(UTC)
    request_expiry = now + timedelta(seconds=5)
    contract_expiry = now + timedelta(minutes=5)
    contract_id = str(uuid4())

    class Requester:
        async def create_request(self, **_kwargs):
            return "manifest", {
                "id": str(uuid4()), "contractId": contract_id, "status": "pending",
                "expiresAt": request_expiry.isoformat(),
            }

        async def open_session(self, **_kwargs):
            return SimpleNamespace(session_id=str(uuid4()))

    class Compute:
        async def get_contract(self, value):
            assert value == contract_id
            return {"id": value, "status": "held", "expiresAt": contract_expiry.isoformat()}

    buyer = ModelShareBuyerService(requester=Requester(), compute=Compute())
    captured = {}

    async def wait_session(_principal, session, expires_at):
        captured["expiresAt"] = expires_at
        return session

    buyer._wait_session = wait_session
    principal = RequestPrincipal(
        actor_user_id=str(uuid4()), installation_id=str(uuid4()),
        organization_id=str(uuid4()), billing_account_id=str(uuid4()),
        role=MemberRole.CORE, membership_epoch=1,
    )
    _, session = await buyer.prepare(
        principal=principal, signer=object(), config=object(), prompt="hello",
        system_prompt=None, temperature=0,
    )

    assert session.session_id
    assert captured["expiresAt"] == contract_expiry


@pytest.mark.asyncio
async def test_buyer_closes_peer_session_after_stream_completion():
    session_id = str(uuid4())

    class Broker:
        def __init__(self):
            self.closed = []

        async def close_session(self, principal, value):
            self.closed.append((principal, value))

    class Requester:
        def __init__(self):
            self.broker = Broker()

        async def stream(self, **_kwargs):
            yield SimpleNamespace(event="job.completed", data={})

    requester = Requester()
    buyer = ModelShareBuyerService(requester=requester, compute=object())
    principal = object()
    events = [
        event
        async for event in buyer.stream(
            principal=principal,
            signer=object(),
            manifest=object(),
            session=SimpleNamespace(session_id=session_id),
        )
    ]

    assert [event.event for event in events] == ["job.completed"]
    assert requester.broker.closed == [(principal, session_id)]
