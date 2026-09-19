"""ACPF candidate adapter for the isolated Detailed Transcription pipeline."""

from __future__ import annotations

from typing import Any

from mlx_whisperx.service import (
    DetailedTranscriptionConfig,
    DetailedTranscriptionService,
    ModelReference,
)

from ai2apps.model_worker import ModelWorkerError

ALIGNER_ID = "ai2apps.model.detailed-transcription-mlx/forced-aligner"
DIARIZER_ID = "ai2apps.model.detailed-transcription-mlx/diarizer"


def _enabled(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    if isinstance(value, dict):
        return bool(value.get("enabled", True))
    raise ModelWorkerError("Boolean feature value is invalid", code="invalid_request")


class DetailedTranscriptionAdapter:
    def __init__(self, context) -> None:
        self.context = context
        self._services: dict[str, DetailedTranscriptionService] = {}

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        self._services.clear()

    def _checkpoint(self, model_id: str):
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                f"Required checkpoint is not installed: {model_id}",
                code="model_unavailable",
                status_code=503,
            )
        return checkpoint

    def _service(self, model_id: str) -> tuple[DetailedTranscriptionService, str]:
        declaration = next(
            (
                item
                for item in self.context.models
                if model_id in {item.get("id"), item.get("upstream_id")}
                and not item.get("metadata", {}).get("internal")
            ),
            None,
        )
        if declaration is None:
            raise ModelWorkerError("Unsupported detailed transcription model")
        profile = str(declaration.get("metadata", {}).get("profile"))
        asr = self._checkpoint(str(declaration["id"]))
        aligner = self._checkpoint(ALIGNER_ID)
        diarizer = self._checkpoint(DIARIZER_ID)
        key = str(declaration["id"])
        service = self._services.get(key)
        if service is None:
            selected = ModelReference(str(asr.path), asr.revision)
            service = DetailedTranscriptionService(
                DetailedTranscriptionConfig(
                    compact_asr=selected,
                    quality_asr=selected,
                    aligner=ModelReference(str(aligner.path), aligner.revision),
                    diarizer=ModelReference(str(diarizer.path), diarizer.revision),
                )
            )
            self._services[key] = service
        return service, profile

    async def invoke(self, request):
        if request.operation != "audio_detailed_transcription":
            raise ModelWorkerError(f"Unsupported operation: {request.operation}")
        body = dict(request.payload)
        model = body.get("model")
        if not isinstance(model, str) or not model:
            raise ModelWorkerError("model is required", code="invalid_request")
        service, profile = self._service(model)
        return await service.transcribe(
            request.part("file").path,
            profile=profile,
            language=body.get("language") or None,
            prompt=body.get("prompt") or None,
            timestamps=str(body.get("timestamps") or "word"),
            diarization=_enabled(body.get("diarization"), default=True),
            speech_rate_analysis=_enabled(body.get("speech_rate_analysis")),
            emotion_recognition=_enabled(body.get("emotion_recognition")),
            speaker_recognition=_enabled(body.get("speaker_recognition")),
            unsupported_policy=str(body.get("unsupported_policy") or "reject"),
            vad=str(body.get("vad") or "meeting-energy"),
        )


def create_adapter(context):
    return DetailedTranscriptionAdapter(context)
