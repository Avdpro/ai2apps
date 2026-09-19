"""Command line entry point for the isolated MLX-WhisperX experiment."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .aligners import MLXCTCAligner, MLXQwen3ForcedAligner
from .backends import MLXQwen3ASRBackend, MLXSortformerDiarizer, MLXWhisperBackend
from .pipeline import MLXWhisperXPipeline, PipelineConfig
from .vad import EnergyVAD, FullAudioVAD, MeetingEnergyVAD


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("audio", type=Path)
    value.add_argument(
        "--model", required=True, help="Local MLX STT checkpoint path or HF id"
    )
    value.add_argument("--revision", help="Immutable checkpoint revision")
    value.add_argument(
        "--backend", choices=("whisper", "qwen3-asr"), default="whisper"
    )
    value.add_argument("--language")
    value.add_argument("--prompt")
    value.add_argument("--transcription-chunk-seconds", type=float, default=30.0)
    value.add_argument(
        "--vad",
        choices=("energy", "meeting-energy", "sortformer", "none"),
        default="energy",
    )
    value.add_argument("--diarization-model")
    value.add_argument("--diarization-revision")
    value.add_argument(
        "--diarization-window-seconds",
        type=float,
        default=120.0,
        help="Bound Sortformer context; speaker IDs are window-local on long audio",
    )
    value.add_argument(
        "--diarization-speaker-identity",
        choices=("global-streaming", "window-local"),
        default="global-streaming",
        help="Keep global Sortformer slots through its streaming speaker cache",
    )
    value.add_argument("--diarization-streaming-chunk-seconds", type=float, default=5.0)
    value.add_argument("--diarization-threshold", type=float, default=0.20)
    value.add_argument(
        "--diarization-speaker-bridge-gap-seconds", type=float, default=0.12
    )
    value.add_argument("--alignment-model")
    value.add_argument("--alignment-revision")
    value.add_argument(
        "--alignment-backend",
        choices=("wav2vec2-ctc", "qwen3-forced-aligner"),
        default="wav2vec2-ctc",
    )
    value.add_argument("--alignment-min-word-score", type=float, default=0.0)
    value.add_argument("--alignment-window-seconds", type=float, default=30.0)
    value.add_argument(
        "--alignment-unknown-characters",
        choices=("skip", "reject"),
        default="skip",
        help="Skip and report out-of-vocabulary characters, or reject the run",
    )
    value.add_argument(
        "--alignment-fallback", choices=("reject", "native"), default="reject"
    )
    value.add_argument("--no-word-timestamps", action="store_true")
    value.add_argument("--output", type=Path)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    backend_class = (
        MLXQwen3ASRBackend if args.backend == "qwen3-asr" else MLXWhisperBackend
    )
    transcriber = backend_class(args.model, revision=args.revision)
    diarizer = (
        MLXSortformerDiarizer(
            args.diarization_model,
            revision=args.diarization_revision,
            window_seconds=args.diarization_window_seconds,
            speaker_identity=args.diarization_speaker_identity.replace("-", "_"),
            streaming_chunk_seconds=args.diarization_streaming_chunk_seconds,
            threshold=args.diarization_threshold,
            speaker_bridge_gap_seconds=(
                args.diarization_speaker_bridge_gap_seconds
            ),
        )
        if args.diarization_model
        else None
    )
    if args.vad == "sortformer":
        if diarizer is None:
            parser().error("--vad sortformer requires --diarization-model")
        vad = diarizer
    elif args.vad == "meeting-energy":
        vad = MeetingEnergyVAD()
    elif args.vad == "energy":
        vad = EnergyVAD()
    else:
        vad = FullAudioVAD()
    if args.alignment_model and args.alignment_backend == "qwen3-forced-aligner":
        aligner = MLXQwen3ForcedAligner(
            args.alignment_model,
            revision=args.alignment_revision,
            max_window_seconds=args.alignment_window_seconds,
        )
    elif args.alignment_model:
        aligner = MLXCTCAligner(
            args.alignment_model,
            revision=args.alignment_revision,
            min_word_score=args.alignment_min_word_score,
            max_window_seconds=args.alignment_window_seconds,
            unknown_character_policy=args.alignment_unknown_characters,
        )
    else:
        aligner = None
    result = MLXWhisperXPipeline(
        transcriber, vad=vad, aligner=aligner, diarizer=diarizer
    ).run(
        args.audio,
        config=PipelineConfig(
            language=args.language,
            prompt=args.prompt,
            word_timestamps=not args.no_word_timestamps,
            alignment_fallback=args.alignment_fallback,
            max_transcription_chunk_seconds=args.transcription_chunk_seconds,
        ),
    )
    rendered = json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
