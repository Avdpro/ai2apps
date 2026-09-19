"""HTTP API for the standalone Detailed Transcription development Package."""

# ruff: noqa: B008 -- FastAPI uses File/Form objects as dependency declarations.

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from .service import (
    DetailedTranscriptionConfig,
    DetailedTranscriptionError,
    DetailedTranscriptionService,
    ModelReference,
    capabilities,
)


def _boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise DetailedTranscriptionError(f"Invalid boolean value: {value}")


def create_app(config: DetailedTranscriptionConfig) -> FastAPI:
    app = FastAPI(title="AI2Apps Detailed Transcription", version="0.1.1")
    service = DetailedTranscriptionService(config)

    @app.get("/v1/audio/transcriptions/detailed/capabilities")
    async def get_capabilities():
        return capabilities()

    @app.post("/v1/audio/transcriptions/detailed")
    async def detailed_transcription(
        file: UploadFile = File(...),
        profile: str = Form("quality"),
        language: str | None = Form(None),
        prompt: str | None = Form(None),
        timestamps: str = Form("word"),
        diarization: str = Form("true"),
        speech_rate_analysis: str = Form("false"),
        emotion_recognition: str = Form("false"),
        speaker_recognition: str = Form("false"),
        unsupported_policy: str = Form("reject"),
        vad: str = Form("meeting-energy"),
    ):
        suffix = Path(file.filename or "audio.wav").suffix or ".wav"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="detailed-transcription-", suffix=suffix, delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                while chunk := await file.read(1024 * 1024):
                    temporary.write(chunk)
            return await service.transcribe(
                temporary_path,
                profile=profile,
                language=language,
                prompt=prompt,
                timestamps=timestamps,
                diarization=_boolean(diarization),
                speech_rate_analysis=_boolean(speech_rate_analysis),
                emotion_recognition=_boolean(emotion_recognition),
                speaker_recognition=_boolean(speaker_recognition),
                unsupported_policy=unsupported_policy,
                vad=vad,
            )
        except DetailedTranscriptionError as error:
            raise HTTPException(
                status_code=400,
                detail={"code": error.code, "message": str(error)},
            ) from error
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    return app


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--host", default="127.0.0.1")
    value.add_argument("--port", type=int, default=8765)
    value.add_argument("--compact-asr", required=True)
    value.add_argument("--compact-asr-revision", required=True)
    value.add_argument("--quality-asr", required=True)
    value.add_argument("--quality-asr-revision", required=True)
    value.add_argument("--aligner", required=True)
    value.add_argument("--aligner-revision", required=True)
    value.add_argument("--diarizer", required=True)
    value.add_argument("--diarizer-revision", required=True)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    config = DetailedTranscriptionConfig(
        compact_asr=ModelReference(args.compact_asr, args.compact_asr_revision),
        quality_asr=ModelReference(args.quality_asr, args.quality_asr_revision),
        aligner=ModelReference(args.aligner, args.aligner_revision),
        diarizer=ModelReference(args.diarizer, args.diarizer_revision),
    )
    uvicorn.run(
        create_app(config),
        host=args.host,
        port=args.port,
        log_level=os.environ.get("AI2APPS_LOG_LEVEL", "info").lower(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
