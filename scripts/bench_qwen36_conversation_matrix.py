#!/usr/bin/env python3
"""Orchestrate the Qwen3.6 multi-turn Off/Auto matrix."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
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


def path_for(root: Path, scope: str, engine: str, mode: str) -> Path:
    return root / "runs" / f"{scope}--{engine}--{mode}.json"


def main() -> None:
    args = parse_args()
    worker = Path(__file__).with_name("bench_qwen36_conversation_once.py")
    args.output.mkdir(parents=True, exist_ok=True)
    for scope in SCOPES:
        for engine in ENGINES:
            # Alternate order across engines to reduce thermal/order bias.
            modes = MODES if ENGINES.index(engine) % 2 == 0 else tuple(reversed(MODES))
            for mode in modes:
                output = path_for(args.output, scope, engine, mode)
                if output.exists() and not args.force:
                    continue
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
                command = [
                    sys.executable,
                    str(worker),
                    str(args.model),
                    str(args.profile),
                    str(args.store),
                    "--scope",
                    scope,
                    "--backend",
                    engine,
                    "--mode",
                    mode,
                    "--turn-tokens",
                    str(args.turn_tokens),
                    "--output",
                    str(output),
                ]
                started = time.perf_counter()
                completed = subprocess.run(
                    command,
                    cwd=Path(__file__).resolve().parents[1],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if completed.returncode:
                    raise RuntimeError(
                        f"failed {scope}/{engine}/{mode}:\n"
                        f"{completed.stdout}\n{completed.stderr}"
                    )
                data = json.loads(output.read_text())
                print(
                    f"done {scope:20s} {engine:7s} {mode:4s} "
                    f"overall={data['overall_decode_tps']:.3f} "
                    f"late={data['late_two_turn_decode_tps']:.3f} "
                    f"wall={time.perf_counter() - started:.1f}s",
                    flush=True,
                )

    rows = []
    for scope in SCOPES:
        for engine in ENGINES:
            off = json.loads(path_for(args.output, scope, engine, "off").read_text())
            auto = json.loads(path_for(args.output, scope, engine, "auto").read_text())
            exact_turns = [
                left["token_sha256"] == right["token_sha256"]
                for left, right in zip(off["turns"], auto["turns"], strict=True)
            ]
            rows.append(
                {
                    "scope": scope,
                    "engine": engine,
                    "off_overall_tps": off["overall_decode_tps"],
                    "auto_overall_tps": auto["overall_decode_tps"],
                    "overall_change_percent": (
                        auto["overall_decode_tps"] / off["overall_decode_tps"] - 1
                    )
                    * 100,
                    "off_late_tps": off["late_two_turn_decode_tps"],
                    "auto_late_tps": auto["late_two_turn_decode_tps"],
                    "late_change_percent": (
                        auto["late_two_turn_decode_tps"]
                        / off["late_two_turn_decode_tps"]
                        - 1
                    )
                    * 100,
                    "exact_turns": exact_turns,
                    "all_turns_exact": all(exact_turns),
                    "auto_adaptive_l1": auto.get("adaptive_l1"),
                }
            )
    summary = {
        "turn_tokens": args.turn_tokens,
        "turns_per_conversation": 4,
        "rows": rows,
        "correctness": {
            "pairs": len(rows),
            "exact_pairs": sum(row["all_turns_exact"] for row in rows),
            "exact_turns": sum(sum(row["exact_turns"]) for row in rows),
            "total_turns": len(rows) * 4,
        },
    }
    summary_path = args.output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"summary {summary_path}", flush=True)


if __name__ == "__main__":
    main()
