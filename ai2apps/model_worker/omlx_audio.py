# SPDX-License-Identifier: Apache-2.0
"""Reusable oMLX STT/TTS lifecycle adapters for isolated Model Packages."""

from __future__ import annotations

import asyncio
import io
import wave
from collections.abc import Mapping
from typing import Any

from .protocol import (
    ModelWorkerCheckpoint,
    ModelWorkerContext,
    ModelWorkerError,
    ModelWorkerRequest,
    ModelWorkerResponse,
)


def _error(message: str, *, code: str = "invalid_request_error", status: int = 400):
    raise ModelWorkerError(message, code=code, status_code=status)


def _boolean(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    _error("Boolean request parameter is invalid")


class OmlxAudioAdapterBase:
    def __init__(self, context: ModelWorkerContext) -> None:
        self.context = context
        self._engine: Any | None = None
        self._engine_key: tuple[Any, ...] | None = None
        self._lifecycle_lock = asyncio.Lock()

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        async with self._lifecycle_lock:
            await self._stop_engine()

    async def _stop_engine(self) -> None:
        engine, self._engine = self._engine, None
        self._engine_key = None
        if engine is not None:
            stop = getattr(engine, "stop", None)
            if callable(stop):
                result = stop()
                if hasattr(result, "__await__"):
                    await result

    async def create_engine(
        self,
        checkpoint: ModelWorkerCheckpoint,
        runtime_options: Mapping[str, Any] | None = None,
    ) -> Any:
        raise NotImplementedError

    def model_declaration(self, model_id: str) -> Mapping[str, Any]:
        for model in self.context.models:
            if model_id in {model.get("id"), model.get("upstream_id")}:
                return model
        _error(f"Unsupported model: {model_id}")

    def audio_feature(
        self, model_id: str, section: str, feature: str
    ) -> Mapping[str, Any]:
        model = self.model_declaration(model_id)
        capabilities = model.get("audio_capabilities")
        if not isinstance(capabilities, Mapping):
            return {"mode": "unsupported"}
        section_value = capabilities.get(section)
        if not isinstance(section_value, Mapping):
            return {"mode": "unsupported"}
        feature_value = section_value.get(feature)
        return (
            feature_value
            if isinstance(feature_value, Mapping)
            else {"mode": "unsupported"}
        )

    def require_feature(
        self,
        model_id: str,
        section: str,
        feature: str,
        *,
        requested: bool,
    ) -> Mapping[str, Any]:
        declaration = self.audio_feature(model_id, section, feature)
        if requested and declaration.get("mode", "unsupported") == "unsupported":
            _error(
                f"The selected model does not support {feature.replace('_', ' ')}",
                code="unsupported_feature",
            )
        return declaration

    async def engine_for(
        self,
        model_id: str,
        runtime_options: Mapping[str, Any] | None = None,
    ) -> tuple[Any, ModelWorkerCheckpoint]:
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None:
            _error(f"Unsupported model: {model_id}")
        if checkpoint.path is None:
            _error(
                f"Checkpoint is not installed: {checkpoint.repo_id}@{checkpoint.revision}",
                code="model_unavailable",
                status=503,
            )
        options = dict(runtime_options or {})
        key = (checkpoint.model_id, tuple(sorted(options.items())))
        async with self._lifecycle_lock:
            if self._engine is not None and self._engine_key == key:
                return self._engine, checkpoint
            await self._stop_engine()
            try:
                engine = await self.create_engine(checkpoint, options)
                start = getattr(engine, "start", None)
                if callable(start):
                    result = start()
                    if hasattr(result, "__await__"):
                        await result
            except ModelWorkerError:
                raise
            except Exception as exc:
                raise ModelWorkerError(
                    f"Unable to load {checkpoint.repo_id}: {exc}",
                    code="model_load_failed",
                    status_code=503,
                ) from exc
            self._engine = engine
            self._engine_key = key
            return engine, checkpoint


class OmlxSTTAdapter(OmlxAudioAdapterBase):
    async def create_engine(self, checkpoint, runtime_options=None):
        from omlx.engine.stt import STTEngine

        return STTEngine(str(checkpoint.path), **dict(runtime_options or {}))

    async def invoke(self, request: ModelWorkerRequest):
        if request.operation != "audio_transcription":
            _error(f"Unsupported operation: {request.operation}")
        body = dict(request.payload)
        model = body.get("model")
        if not isinstance(model, str) or not model:
            _error("model is required")
        for request_field, feature in (
            ("diarization", "diarization"),
            ("speaker_recognition", "speaker_recognition"),
            ("speech_rate_analysis", "speech_rate"),
            ("emotion_recognition", "emotion"),
        ):
            value = body.get(request_field)
            requested = (
                bool(value.get("enabled", True))
                if isinstance(value, Mapping)
                else _boolean(value)
            )
            self.require_feature(
                model, "stt", feature, requested=requested
            )
        if _boolean(body.get("stream")):
            _error(
                "This Package does not implement streaming transcription",
                code="unsupported_feature",
            )
        response_format = str(body.get("response_format") or "json")
        if response_format not in {"json", "verbose_json"}:
            _error("Only JSON transcription responses are supported")
        runtime_options = body.pop("_ai2apps_model_settings", {})
        if not isinstance(runtime_options, dict):
            _error("Internal model settings are invalid")
        engine, checkpoint = await self.engine_for(model, runtime_options)
        audio = request.part("file")
        try:
            result = await engine.transcribe(
                str(audio.path),
                language=body.get("language") or None,
                prompt=body.get("prompt") or None,
                max_tokens=(int(body["max_tokens"]) if body.get("max_tokens") else None),
                word_timestamps=_boolean(body.get("word_timestamps")),
            )
        except ModelWorkerError:
            raise
        except Exception as exc:
            raise ModelWorkerError(
                f"Transcription failed: {exc}",
                code="transcription_failed",
                status_code=500,
            ) from exc
        output = dict(result)
        output.setdefault("text", "")
        output["features"] = {
            "timestamps": {
                "requested": "word" if _boolean(body.get("word_timestamps")) else "segment",
                "effective": "word" if _boolean(body.get("word_timestamps")) else "segment",
                "status": "native",
                "provider": self.context.service_id,
                "revision": checkpoint.revision,
            }
        }
        return output


class OmlxTTSAdapter(OmlxAudioAdapterBase):
    def dependency_checkpoint_paths(
        self, checkpoint: ModelWorkerCheckpoint
    ) -> dict[str, str]:
        """Resolve only the helper checkpoints declared by the selected model."""
        declaration = self.model_declaration(checkpoint.model_id)
        metadata = declaration.get("metadata", {})
        required_ids = (
            metadata.get("required_model_ids", ())
            if isinstance(metadata, Mapping)
            else ()
        )
        dependency_checkpoints: dict[str, str] = {}
        for required_id in required_ids:
            required = self.context.checkpoint_for(str(required_id))
            if required is None or required.path is None:
                _error(
                    f"Required checkpoint is not installed: {required_id}",
                    code="model_unavailable",
                    status=503,
                )
            dependency_checkpoints[required.repo_id] = str(required.path)
        return dependency_checkpoints

    async def create_engine(self, checkpoint, runtime_options=None):
        from omlx.engine.tts import TTSEngine

        return TTSEngine(
            str(checkpoint.path),
            dependency_checkpoints=self.dependency_checkpoint_paths(checkpoint),
            **dict(runtime_options or {}),
        )

    async def invoke(self, request: ModelWorkerRequest):
        if request.operation != "audio_speech":
            _error(f"Unsupported operation: {request.operation}")
        body = dict(request.payload)
        model = body.get("model")
        text = body.get("input")
        dialogue = body.get("dialogue")
        if not isinstance(model, str) or not model:
            _error("model is required")
        synthesis_text: str | list[str]
        synthesis_voice: str | list[str] | None
        if dialogue is not None:
            self.require_feature(model, "tts", "multi_speaker", requested=True)
            if not isinstance(dialogue, list) or not 1 <= len(dialogue) <= 32:
                _error("dialogue must contain between 1 and 32 turns")
            synthesis_text = []
            synthesis_voice = []
            for index, turn in enumerate(dialogue):
                if not isinstance(turn, Mapping):
                    _error(f"dialogue[{index}] must be an object")
                turn_text = turn.get("text")
                turn_voice = turn.get("voice")
                if not isinstance(turn_text, str) or not turn_text.strip():
                    _error(f"dialogue[{index}].text must not be empty")
                if not isinstance(turn_voice, str) or not turn_voice:
                    _error(f"dialogue[{index}].voice is required")
                synthesis_text.append(turn_text.strip())
                synthesis_voice.append(turn_voice)
        else:
            if not isinstance(text, str) or not text.strip():
                _error("input must not be empty")
            synthesis_text = text.strip()
            synthesis_voice = None
        role = body.get("role")
        if role is not None and not isinstance(role, Mapping):
            _error("role must be an object")
        if isinstance(role, Mapping):
            if role.get("voice_profile_id"):
                body.setdefault("voice_profile_id", role["voice_profile_id"])
            if role.get("voice") and not body.get("voice"):
                body["voice"] = role["voice"]
        if body.get("voice_profile_id"):
            self.require_feature(
                model, "tts", "voice_profiles", requested=True
            )
        reference = body.get("reference")
        if reference is not None:
            if not isinstance(reference, Mapping):
                _error("reference must be an object")
            if any(reference.get(name) for name in ("audio_part", "transcript")):
                self.require_feature(
                    model, "tts", "voice_profiles", requested=True
                )
        if _boolean(body.get("stream")):
            _error(
                "This Package does not implement streaming synthesis",
                code="unsupported_feature",
            )
        if str(body.get("response_format") or "wav") != "wav":
            _error(
                "The initial Package audio protocol supports WAV output only",
                code="unsupported_audio_format",
                status=415,
            )
        if body.get("ref_audio") is not None:
            _error(
                "Reference audio must use an authorized request part",
                code="unsupported_feature",
            )
        reference_part = (request.parts or {}).get("reference_audio")
        reference_text = body.get("ref_text")
        if reference_part is not None:
            voice_profile_feature = self.require_feature(
                model, "tts", "voice_profiles", requested=True
            )
            transcript_required = (
                voice_profile_feature.get("reference_transcript") == "required"
            )
            if transcript_required and (
                not isinstance(reference_text, str) or not reference_text.strip()
            ):
                _error("ref_text is required with reference audio")
        try:
            speed = float(body.get("speed", 1.0))
        except (TypeError, ValueError) as exc:
            raise ModelWorkerError("speed is invalid") from exc
        if not 0.5 <= speed <= 2.0:
            _error("speed must be between 0.5 and 2.0")
        self.require_feature(
            model, "tts", "speed", requested=speed != 1.0
        )
        voice = body.get("voice")
        if dialogue is not None:
            voice = synthesis_voice
        named_voices = self.audio_feature(model, "tts", "named_voices")
        declared_voices = named_voices.get("voices", [])
        if voice:
            self.require_feature(
                model, "tts", "named_voices", requested=True
            )
            requested_voices = voice if isinstance(voice, list) else [voice]
            if isinstance(declared_voices, list) and any(
                item not in declared_voices for item in requested_voices
            ):
                _error(
                    f"Voice is not available for the selected model: {voice}",
                    code="invalid_voice",
                )
        style = body.get("style")
        if style is not None and not isinstance(style, Mapping):
            _error("style must be an object")
        style = dict(style or {})
        emotion = style.get("emotion") or body.get("emotion")
        instructions = style.get("instructions") or body.get("instructions")
        if emotion and str(emotion).lower() != "neutral":
            emotion_feature = self.require_feature(
                model, "tts", "emotion", requested=True
            )
            allowed = emotion_feature.get("values", [])
            if isinstance(allowed, list) and allowed and emotion not in allowed:
                _error(
                    f"Emotion is not available for the selected model: {emotion}",
                    code="unsupported_feature",
                )
            emotion_instruction = f"Speak with a {emotion} emotion."
            instructions = " ".join(
                part.strip()
                for part in (instructions, emotion_instruction)
                if isinstance(part, str) and part.strip()
            )
        if instructions:
            self.require_feature(
                model, "tts", "instructions", requested=True
            )
        elif self.audio_feature(model, "tts", "instructions").get("required"):
            _error(
                "The selected VoiceDesign model requires instructions describing the voice",
                code="invalid_request_error",
            )
        runtime_options = body.pop("_ai2apps_model_settings", {})
        if not isinstance(runtime_options, dict):
            _error("Internal model settings are invalid")
        engine, checkpoint = await self.engine_for(model, runtime_options)
        try:
            content = await engine.synthesize(
                synthesis_text,
                voice=voice or None,
                language=body.get("language") or None,
                speed=speed,
                instructions=instructions or None,
                ref_audio=(str(reference_part.path) if reference_part is not None else None),
                ref_text=(
                    reference_text.strip()
                    if isinstance(reference_text, str) and reference_text.strip()
                    else None
                ),
                temperature=body.get("temperature"),
                top_k=body.get("top_k"),
                top_p=body.get("top_p"),
                repetition_penalty=body.get("repetition_penalty"),
                max_tokens=body.get("max_tokens"),
            )
        except ModelWorkerError:
            raise
        except Exception as exc:
            raise ModelWorkerError(
                f"Speech synthesis failed: {exc}",
                code="synthesis_failed",
                status_code=500,
            ) from exc
        try:
            with wave.open(io.BytesIO(content), "rb") as audio:
                sample_rate = audio.getframerate()
                channels = audio.getnchannels()
                sample_width = audio.getsampwidth()
        except (EOFError, wave.Error) as exc:
            raise ModelWorkerError(
                "TTS backend returned invalid WAV audio",
                code="synthesis_failed",
                status_code=500,
            ) from exc
        headers = {
            "X-AI2Apps-Audio-Sample-Rate": str(sample_rate),
            "X-AI2Apps-Audio-Channels": str(channels),
            "X-AI2Apps-Audio-Sample-Width": str(sample_width),
            "X-AI2Apps-Audio-Checkpoint-Revision": checkpoint.revision,
        }
        if voice:
            headers["X-AI2Apps-Feature-Named-Voice"] = str(
                named_voices.get("mode", "native")
            )
        if emotion:
            headers["X-AI2Apps-Feature-Emotion"] = str(
                self.audio_feature(model, "tts", "emotion").get("mode", "native")
            )
        if instructions:
            headers["X-AI2Apps-Feature-Instructions"] = str(
                self.audio_feature(model, "tts", "instructions").get("mode", "native")
            )
        return ModelWorkerResponse(
            content,
            media_type="audio/wav",
            headers=headers,
        )
