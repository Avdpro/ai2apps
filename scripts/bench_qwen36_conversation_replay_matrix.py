#!/usr/bin/env python3
"""Build fixed conversation references and run forced-token Off/Auto replay."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


SCOPES = ("coding", "humanities_social", "medical_health")
ENGINES = ("flesh", "arena", "tiered")
MODES = ("off", "auto")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("store", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--turn-tokens", type=int, default=256)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def run_checked(command: list[str], env: dict[str, str]) -> None:
    result = subprocess.run(command, env=env, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"failed: {' '.join(command)}\n{result.stdout}\n{result.stderr}")


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    reference_worker = root / "scripts/bench_qwen36_conversation_once.py"
    replay_worker = root / "scripts/bench_qwen36_conversation_replay_once.py"
    args.output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "OMLX_QWEN36_ADAPTIVE_L1": "1",
            "OMLX_QWEN36_ADAPTIVE_L1_EARLY": "64",
            "OMLX_QWEN36_ADAPTIVE_L1_INTERVAL": "256",
            "OMLX_QWEN36_ADAPTIVE_L1_MAX_PROMOTIONS": "40",
            "OMLX_QWEN36_TIERED_TOKEN_TXN": "0",
        }
    )
    for scope in SCOPES:
        reference = args.output / "references" / f"{scope}.json"
        if args.force or not reference.exists():
            reference.parent.mkdir(parents=True, exist_ok=True)
            run_checked(
                [
                    sys.executable,
                    str(reference_worker),
                    str(args.model),
                    str(args.profile),
                    str(args.store),
                    "--scope", scope,
                    "--backend", "flesh",
                    "--mode", "off",
                    "--turn-tokens", str(args.turn_tokens),
                    "--include-content",
                    "--output", str(reference),
                ],
                env,
            )
        for engine in ENGINES:
            for mode in MODES:
                output = args.output / "runs" / f"{scope}--{engine}--{mode}.json"
                if output.exists() and not args.force:
                    continue
                output.parent.mkdir(parents=True, exist_ok=True)
                run_checked(
                    [
                        sys.executable,
                        str(replay_worker),
                        str(args.model),
                        str(args.profile),
                        str(args.store),
                        str(reference),
                        "--backend", engine,
                        "--mode", mode,
                        "--output", str(output),
                    ],
                    env,
                )
                data = json.loads(output.read_text())
                print(
                    f"done {scope:20s} {engine:7s} {mode:4s} "
                    f"overall={data['overall_decode_tps']:.3f} "
                    f"late={data['late_two_turn_decode_tps']:.3f}",
                    flush=True,
                )

    rows = []
    for scope in SCOPES:
        for engine in ENGINES:
            prefix = args.output / "runs" / f"{scope}--{engine}"
            off = json.loads(Path(f"{prefix}--off.json").read_text())
            auto = json.loads(Path(f"{prefix}--auto.json").read_text())
            rows.append(
                {
                    "scope": scope,
                    "engine": engine,
                    "off_overall_tps": off["overall_decode_tps"],
                    "auto_overall_tps": auto["overall_decode_tps"],
                    "overall_change_percent": (auto["overall_decode_tps"] / off["overall_decode_tps"] - 1) * 100,
                    "off_late_tps": off["late_two_turn_decode_tps"],
                    "auto_late_tps": auto["late_two_turn_decode_tps"],
                    "late_change_percent": (auto["late_two_turn_decode_tps"] / off["late_two_turn_decode_tps"] - 1) * 100,
                    "auto_adaptive_l1": auto["adaptive_l1"],
                }
            )
    summary = {"method": "fixed Off/Flesh reference tokens", "rows": rows}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
