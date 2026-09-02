"""Narrow adapter from Model Share text manifests to the Local Model Worker."""

from __future__ import annotations

import io
import json
import math
import wave
from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from ai2apps.identity import RequestPrincipal
from ai2apps.model_invocation import ModelInvocationContext, ModelInvocationService

from .manifests import AudioTTSRequestManifest, ComputeRequestManifest, MultimodalRequestManifest
from .provider import (
    InferenceUsage,
    ModelShareProviderError,
    ProviderInferenceExecution,
)


def supports_text_conversation(model: object) -> bool:
    """Keep the Pilot on reviewed conversational Package endpoints only."""

    return bool(
        getattr(model, "checkpoint_ready", False)
        and getattr(model, "model_type", None) in {"llm", "vlm"}
        and "chat_completions" in getattr(model, "endpoints", {})
    )


def supports_audio_tts(model: object) -> bool:
    return bool(
        getattr(model, "checkpoint_ready", False)
        and getattr(model, "model_type", None) == "audio_tts"
        and "audio_speech" in getattr(model, "endpoints", {})
    )


class OmlxTextExecution(ProviderInferenceExecution):
    def __init__(self, response: StreamingResponse) -> None:
        self.response = response
        self._used = False
        self._complete = False
        self._input_tokens: int | None = None
        self._output_tokens: int | None = None
        self._finish_reason = "stop"

    async def deltas(self) -> AsyncIterator[str]:
        if self._used:
            raise ModelShareProviderError("MODEL_STREAM_REUSED", "Worker stream can only be consumed once.", status_code=500)
        self._used = True
        buffer = bytearray()
        async for chunk in self.response.body_iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            buffer.extend(chunk)
            while b"\n\n" in buffer:
                raw, _, remaining = buffer.partition(b"\n\n")
                buffer = bytearray(remaining)
                for delta in self._parse_event(raw):
                    yield delta
        if buffer.strip():
            raise ModelShareProviderError("MODEL_STREAM_INVALID", "Worker ended with a partial SSE event.", status_code=502)
        if self._input_tokens is None or self._output_tokens is None:
            raise ModelShareProviderError("MODEL_USAGE_MISSING", "Worker did not return final token usage.", status_code=502)
        self._complete = True

    def _parse_event(self, raw: bytes) -> list[str]:
        data_lines = [line[6:] for line in raw.splitlines() if line.startswith(b"data: ")]
        if len(data_lines) != 1:
            raise ModelShareProviderError("MODEL_STREAM_INVALID", "Worker SSE event is invalid.", status_code=502)
        if data_lines[0] == b"[DONE]":
            return []
        try:
            value = json.loads(data_lines[0])
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ModelShareProviderError("MODEL_STREAM_INVALID", "Worker SSE JSON is invalid.", status_code=502) from error
        if not isinstance(value, dict):
            raise ModelShareProviderError("MODEL_STREAM_INVALID", "Worker SSE payload is invalid.", status_code=502)
        usage = value.get("usage")
        if usage is not None:
            if not isinstance(usage, dict):
                raise ModelShareProviderError("MODEL_USAGE_INVALID", "Worker usage is invalid.", status_code=502)
            self._input_tokens = usage.get("prompt_tokens")
            self._output_tokens = usage.get("completion_tokens")
        output: list[str] = []
        choices = value.get("choices", [])
        if not isinstance(choices, list):
            raise ModelShareProviderError("MODEL_STREAM_INVALID", "Worker choices are invalid.", status_code=502)
        for choice in choices:
            if not isinstance(choice, dict):
                raise ModelShareProviderError("MODEL_STREAM_INVALID", "Worker choice is invalid.", status_code=502)
            finish_reason = choice.get("finish_reason")
            if isinstance(finish_reason, str) and finish_reason:
                self._finish_reason = finish_reason
            delta = choice.get("delta", {})
            content = delta.get("content") if isinstance(delta, dict) else None
            if content is not None:
                if not isinstance(content, str):
                    raise ModelShareProviderError("MODEL_OUTPUT_INVALID", "Worker returned non-text content.", status_code=502)
                output.append(content)
        return output

    async def usage(self) -> InferenceUsage:
        if not self._complete or not isinstance(self._input_tokens, int) or not isinstance(self._output_tokens, int):
            raise ModelShareProviderError("MODEL_USAGE_MISSING", "Worker usage is not available.", status_code=502)
        return InferenceUsage(self._input_tokens, self._output_tokens, self._finish_reason)


class OmlxTextInferenceHandler:
    """Allows exactly one reviewed model/revision/runtime and no Tool fields."""

    def __init__(
        self, *, invocations: ModelInvocationService, principal: RequestPrincipal,
        model_id: str, model_revision: str, runtime: str,
    ) -> None:
        self.invocations = invocations
        self.principal = principal
        self.model_id = model_id
        self.model_revision = model_revision
        self.runtime = runtime

    async def __call__(self, manifest: ComputeRequestManifest) -> OmlxTextExecution:
        value = manifest.value
        expected = {"id": self.model_id, "revision": self.model_revision, "runtime": self.runtime}
        if value["model"] != expected:
            raise ModelShareProviderError("MODEL_NOT_OFFERED", "Requested model does not match the reviewed Provider Offer.", status_code=403)
        model = self.invocations.model(self.model_id)
        # A reviewed VLM Package is also safe for the Pilot's text-only
        # manifest: no image, attachment, URL, or arbitrary file field can
        # cross this adapter. Keep all non-conversational model types blocked.
        if model is None or not supports_text_conversation(model):
            raise ModelShareProviderError("MODEL_NOT_READY", "Reviewed text model is not ready.", status_code=503, retryable=True)
        weights = dict(model.weights or {})
        if weights.get("revision") != self.model_revision:
            raise ModelShareProviderError("MODEL_REVISION_MISMATCH", "Local checkpoint revision does not match the Contract.", status_code=409)
        messages = []
        if value["systemPrompt"] is not None:
            messages.append({"role": "system", "content": value["systemPrompt"]})
        messages.append({"role": "user", "content": value["prompt"]})
        context = ModelInvocationContext.from_principal(
            self.principal, session_id=f"peer:{value['requestId']}",
            consumer_app_id="ai2apps.model-sharing",
        )
        response = await self.invocations.invoke_background_json(
            self.model_id, "chat_completions",
            {
                "messages": messages,
                "temperature": value["parameters"]["temperature"],
                "max_tokens": value["parameters"]["maxTokens"],
                "stream": True,
                "stream_options": {"include_usage": True},
            },
            request_id=value["requestId"], context=context,
        )
        if not isinstance(response, StreamingResponse) or response.status_code != 200:
            raise ModelShareProviderError("MODEL_INVOCATION_FAILED", "Local Model Worker rejected the job.", status_code=502)
        return OmlxTextExecution(response)


class OmlxAudioTtsExecution:
    def __init__(self, audio: bytes, *, input_units: int) -> None:
        if len(audio) > 67_108_864:
            raise ModelShareProviderError(
                "MODEL_OUTPUT_LIMIT_EXCEEDED", "TTS output exceeds 64 MiB.",
                status_code=413,
            )
        try:
            with wave.open(io.BytesIO(audio), "rb") as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
        except (EOFError, wave.Error) as error:
            raise ModelShareProviderError(
                "MODEL_AUDIO_INVALID", "Worker returned an invalid WAV artifact.",
                status_code=502,
            ) from error
        if rate <= 0 or frames <= 0:
            raise ModelShareProviderError(
                "MODEL_AUDIO_INVALID", "Worker returned an empty WAV artifact.",
                status_code=502,
            )
        self.audio = audio
        self.input_units = input_units
        self.output_units = max(1, math.ceil(frames * 1000 / rate))
        self.artifact = audio
        self.content_type = "audio/wav"
        self.actual_usage = {"outputDurationMs": self.output_units}


class OmlxAudioTtsInferenceHandler:
    """Invoke one reviewed named-voice TTS model without reference audio."""

    def __init__(
        self, *, invocations: ModelInvocationService, principal: RequestPrincipal,
        model_id: str, model_revision: str, runtime: str,
    ) -> None:
        self.invocations = invocations
        self.principal = principal
        self.model_id = model_id
        self.model_revision = model_revision
        self.runtime = runtime

    async def __call__(
        self, manifest: AudioTTSRequestManifest | MultimodalRequestManifest,
        request_payload: dict | None = None,
    ) -> OmlxAudioTtsExecution:
        value = manifest.value
        multimodal = isinstance(manifest, MultimodalRequestManifest)
        expected = {"id": self.model_id, "revision": self.model_revision, "runtime": self.runtime}
        actual_model = ({"id": value["modelId"], "revision": value["modelRevision"],
                         "runtime": value["runtime"]} if multimodal else value["model"])
        if actual_model != expected:
            raise ModelShareProviderError(
                "MODEL_NOT_OFFERED", "Requested TTS model does not match the reviewed Offer.",
                status_code=403,
            )
        if multimodal:
            if value["calculatorType"] != "tts_v1" or not isinstance(request_payload, dict):
                raise ModelShareProviderError(
                    "COMPUTE_PRICING_INVALID", "TTS pricing payload is invalid.",
                    status_code=422,
                )
            required = {"text", "voice", "language", "instructions", "speedBps", "customSampleUsed", "quality"}
            if set(request_payload) != required:
                raise ModelShareProviderError(
                    "MODEL_REQUEST_INVALID", "TTS request payload fields are invalid.",
                    status_code=422,
                )
            if request_payload["customSampleUsed"] is not False:
                raise ModelShareProviderError(
                    "MODEL_CUSTOM_SAMPLE_UNSUPPORTED",
                    "This reviewed TTS Provider does not accept custom voice samples.",
                    status_code=422,
                )
            text = request_payload["text"]
            voice = request_payload["voice"]
            language = request_payload["language"]
            instructions = request_payload["instructions"]
            speed_bps = request_payload["speedBps"]
            if (not isinstance(text, str) or not text or len(text) > 100_000
                    or not isinstance(voice, str) or not voice
                    or language is not None and not isinstance(language, str)
                    or instructions is not None and not isinstance(instructions, str)
                    or isinstance(speed_bps, bool) or not isinstance(speed_bps, int)
                    or not 5_000 <= speed_bps <= 20_000
                    or request_payload["quality"] not in {"low", "mid", "high"}):
                raise ModelShareProviderError(
                    "MODEL_REQUEST_INVALID", "TTS request payload is invalid.",
                    status_code=422,
                )
            speed = speed_bps / 10_000
        else:
            text = value["text"]
            voice = value["voice"]
            language = value["language"]
            instructions = value["instructions"]
            speed = value["speed"]
        model = self.invocations.model(self.model_id)
        if model is None or not supports_audio_tts(model):
            raise ModelShareProviderError(
                "MODEL_NOT_READY", "Reviewed TTS model is not ready.",
                status_code=503, retryable=True,
            )
        if dict(model.weights or {}).get("revision") != self.model_revision:
            raise ModelShareProviderError(
                "MODEL_REVISION_MISMATCH", "Local TTS revision does not match the Contract.",
                status_code=409,
            )
        named = dict(model.audio_capabilities or {}).get("tts", {}).get("named_voices", {})
        voices = named.get("voices", []) if isinstance(named, dict) else []
        if voice not in voices:
            raise ModelShareProviderError(
                "MODEL_VOICE_INVALID", "Requested voice is not in the reviewed Package capabilities.",
                status_code=422,
            )
        context = ModelInvocationContext.from_principal(
            self.principal, session_id=f"peer:{value['requestId']}",
            consumer_app_id="ai2apps.model-sharing",
        )
        response = await self.invocations.invoke_background_json(
            self.model_id, "audio_speech",
            {
                "input": text, "voice": voice,
                "language": language, "instructions": instructions,
                "speed": speed, "response_format": "wav", "stream": False,
            },
            request_id=value["requestId"], context=context,
        )
        if response.status_code != 200 or not response.headers.get("content-type", "").lower().startswith(("audio/wav", "audio/x-wav")):
            raise ModelShareProviderError(
                "MODEL_INVOCATION_FAILED", "Local TTS Worker rejected the job.",
                status_code=502,
            )
        return OmlxAudioTtsExecution(bytes(response.body), input_units=len(text))
