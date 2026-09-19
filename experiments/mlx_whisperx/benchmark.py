"""Run a small, reproducible English WER / Chinese CER benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import unicodedata
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .audio import read_audio
from .backends import (
    MLXQwen3ASRBackend,
    MLXSortformerDiarizer,
    MLXWhisperBackend,
)
from .pipeline import MLXWhisperXPipeline, PipelineConfig
from .vad import EnergyVAD, FullAudioVAD


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_units(text: str, language: str) -> list[str]:
    """Return dependency-free scoring units for the two priority languages."""

    normalized = unicodedata.normalize("NFKC", text).casefold()
    language_code = language.lower().split("-", 1)[0]
    if language_code == "zh":
        return [
            character
            for character in normalized
            if unicodedata.category(character)[0] in {"L", "N"}
        ]
    if language_code == "en":
        rendered: list[str] = []
        for character in normalized:
            category = unicodedata.category(character)
            if category[0] in {"L", "N"} or character == "'":
                rendered.append(character)
            else:
                rendered.append(" ")
        return "".join(rendered).split()
    raise ValueError(f"Unsupported benchmark language: {language}")


def edit_distance(reference: Sequence[str], hypothesis: Sequence[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for reference_index, reference_unit in enumerate(reference, start=1):
        current = [reference_index]
        for hypothesis_index, hypothesis_unit in enumerate(hypothesis, start=1):
            current.append(
                min(
                    previous[hypothesis_index] + 1,
                    current[hypothesis_index - 1] + 1,
                    previous[hypothesis_index - 1]
                    + (reference_unit != hypothesis_unit),
                )
            )
        previous = current
    return previous[-1]


def load_cases(manifest: dict[str, Any], audio_root: Path) -> list[dict[str, Any]]:
    cases = manifest.get("cases")
    if isinstance(cases, list) and cases:
        return cases
    transcript = manifest.get("transcript")
    if not isinstance(transcript, dict):
        raise ValueError("Benchmark manifest must contain cases or transcript")
    transcript_path = (audio_root / str(transcript["path"])).resolve(strict=True)
    expected_sha256 = str(transcript["sha256"])
    if file_sha256(transcript_path) != expected_sha256:
        raise ValueError("Transcript SHA-256 mismatch")
    language = str(manifest["language"])
    audio_directory = str(transcript["audio_directory"])
    suffix = str(transcript.get("audio_suffix", ".wav"))
    loaded: list[dict[str, Any]] = []
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        identifier, reference = line.split(maxsplit=1)
        loaded.append(
            {
                "id": identifier,
                "language": language,
                "audio": f"{audio_directory}/{identifier}{suffix}",
                "reference": reference,
            }
        )
    expected_cases = manifest.get("expected_cases")
    if expected_cases is not None and len(loaded) != int(expected_cases):
        raise ValueError(
            f"Expected {expected_cases} transcript cases, found {len(loaded)}"
        )
    return loaded


def render_result(
    *,
    manifest: dict[str, Any],
    args: argparse.Namespace,
    cases: list[dict[str, Any]],
    results: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    total_audio_seconds = sum(item["duration_seconds"] for item in results)
    total_inference_seconds = sum(item["inference_seconds"] for item in results)
    total_edits = sum(item["edits"] for item in results)
    total_reference_units = sum(item["reference_units"] for item in results)
    language_set = sorted({str(case["language"]) for case in cases})
    metric = "cer" if all(value.startswith("zh") for value in language_set) else "wer"
    return {
        "schema": "ai2apps.mlx-whisperx-benchmark/v1",
        "status": status,
        "dataset": manifest.get("dataset"),
        "dataset_revision": manifest.get("revision"),
        "model": args.model,
        "model_revision": args.revision,
        "backend": args.backend,
        "prompt": args.prompt,
        "vad": args.vad,
        "diarization_model": args.diarization_model,
        "languages": language_set,
        "metric": metric,
        "summary": {
            "cases": len(results),
            "expected_cases": len(cases),
            "audio_seconds": total_audio_seconds,
            "inference_seconds": total_inference_seconds,
            "rtf": (
                total_inference_seconds / total_audio_seconds
                if total_audio_seconds
                else 0.0
            ),
            "edits": total_edits,
            "reference_units": total_reference_units,
            "error_rate": (
                total_edits / total_reference_units
                if total_reference_units
                else 0.0
            ),
        },
        "cases": results,
    }


def write_result(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--manifest", required=True, type=Path)
    value.add_argument("--audio-root", required=True, type=Path)
    value.add_argument("--model", required=True)
    value.add_argument("--revision")
    value.add_argument(
        "--backend", choices=("whisper", "qwen3-asr"), default="whisper"
    )
    value.add_argument("--prompt")
    value.add_argument(
        "--vad", choices=("sortformer", "energy", "none"), default="sortformer"
    )
    value.add_argument("--diarization-model")
    value.add_argument("--diarization-revision")
    value.add_argument("--checkpoint-every", type=int, default=10)
    value.add_argument("--resume", action="store_true")
    value.add_argument("--output", required=True, type=Path)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.checkpoint_every <= 0:
        parser().error("--checkpoint-every must be positive")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    cases = load_cases(manifest, args.audio_root)

    backend_class = (
        MLXQwen3ASRBackend if args.backend == "qwen3-asr" else MLXWhisperBackend
    )
    backend = backend_class(args.model, revision=args.revision)
    diarizer = (
        MLXSortformerDiarizer(
            args.diarization_model,
            revision=args.diarization_revision,
        )
        if args.vad == "sortformer" and args.diarization_model
        else None
    )
    if args.vad == "sortformer" and diarizer is None:
        parser().error("--vad sortformer requires --diarization-model")
    if args.vad == "sortformer":
        vad = diarizer
    elif args.vad == "energy":
        vad = EnergyVAD()
    else:
        vad = FullAudioVAD()
    pipeline = MLXWhisperXPipeline(
        backend,
        vad=vad,
        diarizer=diarizer,
    )
    results: list[dict[str, Any]] = []
    if args.resume and args.output.is_file():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        if previous.get("dataset_revision") != manifest.get("revision"):
            raise ValueError("Cannot resume a different dataset revision")
        previous_backend = previous.get("backend", "whisper")
        if (
            previous.get("model") != args.model
            or previous.get("vad") != args.vad
            or previous_backend != args.backend
            or previous.get("prompt") != args.prompt
        ):
            raise ValueError("Cannot resume with a different model or VAD")
        results = list(previous.get("cases", []))
    completed = {str(item["id"]) for item in results}

    for case in cases:
        if str(case["id"]) in completed:
            continue
        language = str(case["language"])
        audio_path = (args.audio_root / str(case["audio"])).resolve(strict=True)
        expected_sha256 = case.get("audio_sha256")
        if expected_sha256 and file_sha256(audio_path) != expected_sha256:
            raise ValueError(f"Audio SHA-256 mismatch: {case['id']}")
        reference = str(case["reference"])
        duration = read_audio(audio_path).duration
        started = time.perf_counter()
        output = pipeline.run(
            audio_path,
            config=PipelineConfig(
                language=language,
                prompt=(
                    args.prompt
                    if args.prompt is not None
                    else (
                        "以下内容使用简体中文。"
                        if args.backend == "whisper" and language.startswith("zh")
                        else None
                    )
                ),
                word_timestamps=False,
            ),
        )
        elapsed = time.perf_counter() - started
        hypothesis = output.text
        reference_units = normalize_units(reference, language)
        if not reference_units:
            raise ValueError(f"Benchmark reference has no scoring units: {case['id']}")
        hypothesis_units = normalize_units(hypothesis, language)
        edits = edit_distance(reference_units, hypothesis_units)
        results.append(
            {
                "id": str(case["id"]),
                "language": language,
                "audio": str(case["audio"]),
                "duration_seconds": duration,
                "inference_seconds": elapsed,
                "rtf": elapsed / duration,
                "reference": reference,
                "hypothesis": hypothesis,
                "edits": edits,
                "reference_units": len(reference_units),
                "error_rate": edits / len(reference_units),
            }
        )
        if len(results) % args.checkpoint_every == 0:
            write_result(
                args.output,
                render_result(
                    manifest=manifest,
                    args=args,
                    cases=cases,
                    results=results,
                    status="in_progress",
                ),
            )

    write_result(
        args.output,
        render_result(
            manifest=manifest,
            args=args,
            cases=cases,
            results=results,
            status="complete",
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
