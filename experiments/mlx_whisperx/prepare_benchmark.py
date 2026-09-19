"""Download only the public audio files named by a benchmark manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmark import file_sha256


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--manifest", required=True, type=Path)
    value.add_argument("--output", required=True, type=Path)
    return value


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    dataset = str(manifest["dataset"])
    revision = str(manifest["revision"])
    cases = manifest.get("cases")
    transcript = manifest.get("transcript")
    if isinstance(cases, list) and cases:
        files = [str(case["audio"]) for case in cases]
    elif isinstance(transcript, dict):
        audio_directory = str(transcript["audio_directory"])
        suffix = str(transcript.get("audio_suffix", ".wav"))
        files = [str(transcript["path"]), f"{audio_directory}/*{suffix}"]
    else:
        raise ValueError("Benchmark manifest must contain cases or transcript")

    from huggingface_hub import snapshot_download

    root = Path(
        snapshot_download(
            repo_id=dataset,
            repo_type="dataset",
            revision=revision,
            local_dir=args.output,
            allow_patterns=files,
        )
    )
    if isinstance(cases, list) and cases:
        for case in cases:
            path = root / str(case["audio"])
            expected = str(case["audio_sha256"])
            if file_sha256(path) != expected:
                raise ValueError(f"Audio SHA-256 mismatch: {case['id']}")
    else:
        transcript_path = root / str(transcript["path"])
        if file_sha256(transcript_path) != str(transcript["sha256"]):
            raise ValueError("Transcript SHA-256 mismatch")
        expected_cases = int(manifest["expected_cases"])
        audio_directory = root / str(transcript["audio_directory"])
        suffix = str(transcript.get("audio_suffix", ".wav"))
        downloaded_cases = len(list(audio_directory.glob(f"*{suffix}")))
        if downloaded_cases != expected_cases:
            raise ValueError(
                f"Expected {expected_cases} audio files, found {downloaded_cases}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
