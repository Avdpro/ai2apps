"""Run bracketing 64/72 staged-read overlap measurements."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path("artifacts/dsv41-ssd-staged-overlap-20260917")
SOURCE = ROOT / "source"
CASES = (
    ("baseline-before", (0, 0, 0, 0)),
    ("fixed64", (12, 20, 16, 16)),
    ("fixed72", (12, 20, 20, 20)),
    ("optimized72", (13, 23, 18, 18)),
    ("baseline-after", (0, 0, 0, 0)),
)


def summary(events):
    compute = sum(event["compute_end"] - event["begin"] for event in events)
    wall = sum(event["end"] - event["begin"] for event in events)
    stage = {}
    for index in range(4):
        reads = [read for event in events for read in event["reads"] if read["stage"] == index]
        stage[str(index)] = {
            "reads": sum(read["count"] for read in reads),
            "seconds": sum(read["end"] - read["begin"] for read in reads),
            "completed_before_forward_end": sum(
                read["end"] <= event["compute_end"]
                for event in events
                for read in event["reads"]
                if read["stage"] == index
            ),
            "tokens": len(reads),
        }
    return {
        "compute_s": compute,
        "total_s": wall,
        "wait_after_compute_s": wall - compute,
        "aux_gb": sum(read["bytes"] for event in events for read in event["reads"]) / 1e9,
        "stages": stage,
    }


def main():
    ROOT.mkdir(exist_ok=True)
    if SOURCE.exists():
        shutil.rmtree(SOURCE)
    for subdir in ("dsv41_mlx", "dsv41_reference"):
        shutil.copytree(
            Path("experiments") / subdir,
            SOURCE / "experiments" / subdir,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    (SOURCE / "artifacts").symlink_to(Path("artifacts").resolve(), target_is_directory=True)
    shutil.copy2(
        "experiments/dsv41_analysis/ssd_overlap/staged_entry.py",
        SOURCE / "experiments/dsv41_mlx/staged_overlap_entry.py",
    )
    (ROOT / "source-hashes.json").write_text(
        json.dumps(
            {
                str(path.relative_to(SOURCE)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in SOURCE.rglob("*.py")
            },
            indent=2,
        )
    )

    rows = []
    reference = None
    for name, counts in CASES:
        output = ROOT / name
        command = [
            sys.executable,
            str(SOURCE / "experiments/dsv41_mlx/staged_overlap_entry.py"),
            "--prompt-json",
            "artifacts/dsv41-l1-shape-20260915/dataset/coding-en-train-18.json",
            "--decode",
            "64",
            "--prefill-slots",
            "64",
            "--logits-mode",
            "hash",
            "--expert-no-cache",
            "--output",
            str(output),
        ]
        environment = dict(
            os.environ,
            STAGED_COUNTS=json.dumps(counts),
            STAGED_OUTPUT=str(output),
        )
        with output.with_suffix(".log").open("w") as log:
            subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT, check=True)
        manifest = json.loads((output / "manifest.json").read_text())
        assert manifest["status"] == "complete"
        assert manifest["sampled_physical_footprint_peak_bytes"] < 65e9
        signature = [manifest[key] for key in ("input_ids", "generated_ids", "logits_sha256", "cache_stats")]
        if reference is None:
            reference = signature
        else:
            assert signature == reference, name
        trace = json.loads((output / "staged-overlap.json").read_text())
        assert len(trace["events"]) == 64
        row = {
            "name": name,
            "counts": counts,
            "tps": 64 / sum(manifest["step_seconds"][1:]),
            "peak_gb": manifest["sampled_physical_footprint_peak_bytes"] / 1e9,
            "expert_read_gb": manifest["expert_total_read_bytes"] / 1e9,
            **summary(trace["events"]),
        }
        rows.append(row)
        (ROOT / "results.json").write_text(json.dumps(rows, indent=2))
        print(json.dumps(row), flush=True)
    (ROOT / "complete.json").write_text(
        json.dumps(
            {
                "runs": len(rows),
                "exact_logits_routes_and_cache": True,
                "strict_no_cache": True,
                "all_under_65gb": True,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
