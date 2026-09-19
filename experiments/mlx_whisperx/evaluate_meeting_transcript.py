"""Evaluate meeting WER and speaker-attributed WER from AMI word annotations."""

from __future__ import annotations

import argparse
import itertools
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .benchmark import edit_distance, normalize_units


@dataclass(frozen=True)
class SpeakerWord:
    word: str
    start: float
    end: float
    speaker: str | None


def load_ami_words(directory: Path, meeting: str) -> list[SpeakerWord]:
    words: list[SpeakerWord] = []
    for path in sorted(directory.glob(f"{meeting}.*.words.xml")):
        speaker = path.name.split(".")[-3]
        for item in ET.parse(path).getroot():
            if item.tag != "w" or item.get("punc") == "true":
                continue
            start = item.get("starttime")
            end = item.get("endtime")
            if start is None or end is None or not (item.text or "").strip():
                continue
            for token in normalize_units(item.text or "", "en-US"):
                words.append(SpeakerWord(token, float(start), float(end), speaker))
    return sorted(words, key=lambda item: (item.start, item.end, item.speaker or ""))


def load_hypothesis_words(value: dict) -> list[SpeakerWord]:
    words: list[SpeakerWord] = []
    for segment in value.get("segments", []):
        segment_speaker = segment.get("speaker")
        for item in segment.get("words", []):
            start = item.get("start")
            end = item.get("end")
            if start is None or end is None:
                continue
            for token in normalize_units(str(item.get("word", "")), "en-US"):
                words.append(
                    SpeakerWord(
                        token,
                        float(start),
                        float(end),
                        str(item.get("speaker") or segment_speaker)
                        if item.get("speaker") or segment_speaker
                        else None,
                    )
                )
    return sorted(words, key=lambda item: (item.start, item.end, item.speaker or ""))


def lexical_alignment(
    reference: list[str], hypothesis: list[str]
) -> tuple[int, list[tuple[int, int]]]:
    rows, columns = len(reference) + 1, len(hypothesis) + 1
    costs = np.empty((rows, columns), dtype=np.int32)
    costs[:, 0] = np.arange(rows)
    costs[0, :] = np.arange(columns)
    for i in range(1, rows):
        for j in range(1, columns):
            substitution = costs[i - 1, j - 1] + (
                reference[i - 1] != hypothesis[j - 1]
            )
            costs[i, j] = min(substitution, costs[i - 1, j] + 1, costs[i, j - 1] + 1)
    matches: list[tuple[int, int]] = []
    i, j = len(reference), len(hypothesis)
    while i or j:
        if i and j:
            penalty = reference[i - 1] != hypothesis[j - 1]
            if costs[i, j] == costs[i - 1, j - 1] + penalty:
                if not penalty:
                    matches.append((i - 1, j - 1))
                i -= 1
                j -= 1
                continue
        if i and costs[i, j] == costs[i - 1, j] + 1:
            i -= 1
        else:
            j -= 1
    matches.reverse()
    return int(costs[-1, -1]), matches


def speaker_attributed_metrics(
    reference: list[SpeakerWord], hypothesis: list[SpeakerWord]
) -> dict[str, object]:
    ref_tokens = [item.word for item in reference]
    hyp_tokens = [item.word for item in hypothesis]
    edits, matches = lexical_alignment(ref_tokens, hyp_tokens)
    ref_speakers = sorted({item.speaker for item in reference if item.speaker})
    hyp_speakers = sorted({item.speaker for item in hypothesis if item.speaker})
    reference_by_speaker = {
        speaker: [item.word for item in reference if item.speaker == speaker]
        for speaker in ref_speakers
    }
    hypothesis_by_speaker = {
        speaker: [item.word for item in hypothesis if item.speaker == speaker]
        for speaker in hyp_speakers
    }
    slot_count = max(len(ref_speakers), len(hyp_speakers))
    padded_references: list[str | None] = ref_speakers + [None] * (
        slot_count - len(ref_speakers)
    )
    padded_hypotheses: list[str | None] = hyp_speakers + [None] * (
        slot_count - len(hyp_speakers)
    )
    best_attributed_edits: int | None = None
    best_mapping: dict[str, str] = {}
    for permutation in itertools.permutations(padded_references):
        attributed_edits = 0
        mapping: dict[str, str] = {}
        for hypothesis_speaker, reference_speaker in zip(
            padded_hypotheses, permutation, strict=True
        ):
            if hypothesis_speaker is None:
                attributed_edits += len(reference_by_speaker[reference_speaker])
            elif reference_speaker is None:
                attributed_edits += len(hypothesis_by_speaker[hypothesis_speaker])
            else:
                mapping[hypothesis_speaker] = reference_speaker
                attributed_edits += edit_distance(
                    reference_by_speaker[reference_speaker],
                    hypothesis_by_speaker[hypothesis_speaker],
                )
        if best_attributed_edits is None or attributed_edits < best_attributed_edits:
            best_attributed_edits = attributed_edits
            best_mapping = mapping
    speaker_errors = sum(
        best_mapping.get(hypothesis[hyp_index].speaker)
        != reference[ref_index].speaker
        for ref_index, hyp_index in matches
    )
    denominator = len(ref_tokens)
    return {
        "reference_words": denominator,
        "hypothesis_words_with_timestamps": len(hyp_tokens),
        "lexical_edits": edits,
        "wer": edits / denominator,
        "lexically_correct_words": len(matches),
        "speaker_errors_on_correct_words": speaker_errors,
        "speaker_accuracy_on_correct_words": (
            (len(matches) - speaker_errors) / len(matches) if matches else 0.0
        ),
        "speaker_attributed_wer": (
            best_attributed_edits / denominator if denominator else 0.0
        ),
        "speaker_attributed_method": "cpWER",
        "speaker_mapping": best_mapping,
    }


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--result", required=True, type=Path)
    value.add_argument("--words", required=True, type=Path)
    value.add_argument("--meeting", required=True)
    value.add_argument("--output", required=True, type=Path)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    result = json.loads(args.result.read_text(encoding="utf-8"))
    reference = load_ami_words(args.words, args.meeting)
    hypothesis = load_hypothesis_words(result)
    reference_text = [item.word for item in reference]
    hypothesis_text = normalize_units(str(result.get("text", "")), "en-US")
    metrics = speaker_attributed_metrics(reference, hypothesis)
    metrics["full_text_wer"] = edit_distance(reference_text, hypothesis_text) / len(
        reference_text
    )
    output = {
        "schema": "ai2apps.detailed-transcription-meeting-eval/v1",
        "meeting": args.meeting,
        "result": str(args.result),
        "metrics": metrics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
