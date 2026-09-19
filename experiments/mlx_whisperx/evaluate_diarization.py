"""Evaluate global Sortformer speaker slots against AMI NXT annotations."""

from __future__ import annotations

import argparse
import itertools
import json
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path

import numpy as np

from .assignment import speaker_for
from .backends import MLXSortformerDiarizer
from .benchmark import file_sha256, normalize_units
from .evaluate_meeting_transcript import (
    SpeakerWord,
    load_ami_words,
    speaker_attributed_metrics,
)
from .schema import DiarizationSpan


def load_ami_segments(paths: Iterable[Path]) -> list[DiarizationSpan]:
    spans: list[DiarizationSpan] = []
    for path in paths:
        speaker = path.name.split(".")[-3]
        root = ET.parse(path).getroot()
        for item in root.findall("segment"):
            start = item.get("transcriber_start")
            end = item.get("transcriber_end")
            if start is None or end is None or float(end) <= float(start):
                continue
            spans.append(DiarizationSpan(float(start), float(end), speaker))
    return sorted(spans, key=lambda item: (item.start, item.end, item.speaker))


def _activity(
    spans: list[DiarizationSpan], speakers: list[str], duration: float, frame: float
) -> np.ndarray:
    result = np.zeros((int(np.ceil(duration / frame)), len(speakers)), dtype=bool)
    speaker_index = {speaker: index for index, speaker in enumerate(speakers)}
    for span in spans:
        first = max(0, int(np.floor(span.start / frame)))
        last = min(len(result), int(np.ceil(span.end / frame)))
        result[first:last, speaker_index[span.speaker]] = True
    return result


def diarization_error_rate(
    reference: list[DiarizationSpan],
    hypothesis: list[DiarizationSpan],
    *,
    duration: float,
    frame: float = 0.01,
    collar: float = 0.25,
    skip_overlap: bool = False,
) -> dict[str, object]:
    reference_speakers = sorted({span.speaker for span in reference})
    hypothesis_speakers = sorted({span.speaker for span in hypothesis})
    ref = _activity(reference, reference_speakers, duration, frame)
    hyp = _activity(hypothesis, hypothesis_speakers, duration, frame)
    scored = np.ones(len(ref), dtype=bool)
    collar_frames = int(round(collar / frame))
    if collar_frames:
        for span in reference:
            for boundary in (span.start, span.end):
                center = int(round(boundary / frame))
                scored[max(0, center - collar_frames) : center + collar_frames + 1] = (
                    False
                )
    if skip_overlap:
        scored &= ref.sum(axis=1) <= 1

    size = max(len(reference_speakers), len(hypothesis_speakers))
    best_mapping: tuple[int, ...] = tuple(range(size))
    best_correct = -1
    padded_ref = np.pad(ref, ((0, 0), (0, size - ref.shape[1])))
    padded_hyp = np.pad(hyp, ((0, 0), (0, size - hyp.shape[1])))
    for permutation in itertools.permutations(range(size)):
        correct = int(
            np.logical_and(padded_ref[scored], padded_hyp[scored][:, permutation]).sum()
        )
        if correct > best_correct:
            best_correct = correct
            best_mapping = permutation
    mapped_hyp = padded_hyp[:, best_mapping]
    ref_count = padded_ref.sum(axis=1)
    hyp_count = mapped_hyp.sum(axis=1)
    correct = np.logical_and(padded_ref, mapped_hyp).sum(axis=1)
    miss = np.maximum(ref_count - hyp_count, 0)[scored].sum()
    false_alarm = np.maximum(hyp_count - ref_count, 0)[scored].sum()
    confusion = (np.minimum(ref_count, hyp_count) - correct)[scored].sum()
    denominator = ref_count[scored].sum()
    mapping = {
        hypothesis_speakers[index]: reference_speakers[target]
        for target, index in enumerate(best_mapping[: len(reference_speakers)])
        if index < len(hypothesis_speakers)
    }
    return {
        "der": float((miss + false_alarm + confusion) / denominator),
        "miss": float(miss / denominator),
        "false_alarm": float(false_alarm / denominator),
        "confusion": float(confusion / denominator),
        "collar_seconds": collar,
        "skip_overlap": skip_overlap,
        "scored_reference_speaker_seconds": float(denominator * frame),
        "mapping": mapping,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--audio", required=True, type=Path)
    value.add_argument("--annotations", required=True, type=Path)
    value.add_argument("--meeting", required=True)
    value.add_argument("--model", required=True)
    value.add_argument("--revision")
    value.add_argument("--chunk-seconds", type=float, default=5.0)
    value.add_argument("--threshold", type=float, default=0.20)
    value.add_argument("--speaker-bridge-gap-seconds", type=float, default=0.12)
    value.add_argument(
        "--bridge-gaps",
        default="",
        help="Comma-separated same-speaker gap sizes to evaluate without rerunning MLX",
    )
    value.add_argument("--output", required=True, type=Path)
    value.add_argument("--transcript-result", type=Path)
    value.add_argument("--word-annotations", type=Path)
    return value


def transcript_speaker_metrics(
    result: dict, reference: list[SpeakerWord], diarization: list[DiarizationSpan]
) -> dict[str, object]:
    words: list[SpeakerWord] = []
    for segment in result.get("segments", []):
        for item in segment.get("words", []):
            start = item.get("start")
            end = item.get("end")
            if start is None or end is None:
                continue
            speaker = speaker_for(float(start), float(end), diarization)
            for token in normalize_units(str(item.get("word", "")), "en-US"):
                words.append(SpeakerWord(token, float(start), float(end), speaker))
    words.sort(key=lambda item: (item.start, item.end, item.speaker or ""))
    return speaker_attributed_metrics(reference, words)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    from .audio import read_audio

    audio = read_audio(args.audio)
    paths = sorted(args.annotations.glob(f"{args.meeting}.*.segments.xml"))
    if not paths:
        raise ValueError(f"No AMI annotations found for {args.meeting}")
    reference = load_ami_segments(paths)
    diarizer = MLXSortformerDiarizer(
        args.model,
        revision=args.revision,
        speaker_identity="global_streaming",
        streaming_chunk_seconds=args.chunk_seconds,
        threshold=args.threshold,
        speaker_bridge_gap_seconds=args.speaker_bridge_gap_seconds,
    )
    started = time.perf_counter()
    hypothesis = diarizer.diarize(args.audio)
    elapsed = time.perf_counter() - started
    bridge_gaps = [
        float(value) for value in args.bridge_gaps.split(",") if value.strip()
    ]
    transcript_result = (
        json.loads(args.transcript_result.read_text(encoding="utf-8"))
        if args.transcript_result
        else None
    )
    if (transcript_result is None) != (args.word_annotations is None):
        raise ValueError(
            "--transcript-result and --word-annotations must be provided together"
        )
    word_reference = (
        load_ami_words(args.word_annotations, args.meeting)
        if args.word_annotations
        else None
    )
    result = {
        "schema": "ai2apps.mlx-whisperx-diarization-eval/v1",
        "dataset": "AMI Meeting Corpus",
        "license": "CC-BY-4.0",
        "meeting": args.meeting,
        "audio_sha256": file_sha256(args.audio),
        "duration_seconds": audio.duration,
        "model": args.model,
        "revision": args.revision,
        "speaker_identity": "global_streaming",
        "chunk_seconds": args.chunk_seconds,
        "threshold": args.threshold,
        "speaker_bridge_gap_seconds": args.speaker_bridge_gap_seconds,
        "inference_seconds": elapsed,
        "rtf": elapsed / audio.duration,
        "reference_speakers": sorted({span.speaker for span in reference}),
        "hypothesis_speakers": sorted({span.speaker for span in hypothesis}),
        "metrics": {
            "standard": diarization_error_rate(
                reference, hypothesis, duration=audio.duration
            ),
            "no_overlap": diarization_error_rate(
                reference,
                hypothesis,
                duration=audio.duration,
                skip_overlap=True,
            ),
        },
        "same_speaker_bridge_sweep": {
            f"{gap:g}": {
                "standard": diarization_error_rate(
                    reference,
                    diarizer._merge_same_speaker(hypothesis, merge_gap=gap),
                    duration=audio.duration,
                ),
                "no_overlap": diarization_error_rate(
                    reference,
                    diarizer._merge_same_speaker(hypothesis, merge_gap=gap),
                    duration=audio.duration,
                    skip_overlap=True,
                ),
            }
            for gap in bridge_gaps
        },
        "transcript_speaker_metrics": (
            transcript_speaker_metrics(
                transcript_result, word_reference, hypothesis
            )
            if transcript_result is not None and word_reference is not None
            else None
        ),
        "transcript_speaker_bridge_sweep": (
            {
                f"{gap:g}": transcript_speaker_metrics(
                    transcript_result,
                    word_reference,
                    diarizer._merge_same_speaker(hypothesis, merge_gap=gap),
                )
                for gap in bridge_gaps
            }
            if transcript_result is not None and word_reference is not None
            else {}
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
