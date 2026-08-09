#!/usr/bin/env python3
"""Run the exact Qwen3.6 scope x engine x adaptive-L1 benchmark matrix."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ENGINES = ("flesh", "arena", "tiered")
MODES = ("off", "auto")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("store", type=Path)
    parser.add_argument("prompts", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--experts", type=int, default=96)
    parser.add_argument("--tail", type=int, default=24)
    parser.add_argument("--max-promotions", type=int, default=40)
    parser.add_argument("--full-resident-oracle", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def load_inputs(args: argparse.Namespace) -> tuple[list[str], dict[str, str]]:
    profile = json.loads(args.profile.read_text())
    scopes = sorted(profile["phases"]["decode"])
    prompt_data = json.loads(args.prompts.read_text())["scopes"]
    missing = [scope for scope in scopes if not prompt_data.get(scope)]
    if missing:
        raise ValueError(f"missing benchmark prompts for scopes: {missing}")
    return scopes, {scope: prompt_data[scope][0] for scope in scopes}


def result_path(root: Path, scope: str, engine: str, mode: str) -> Path:
    return root / "runs" / f"{scope}--{engine}--{mode}.json"


def oracle_path(root: Path, scope: str) -> Path:
    return root / "runs" / f"{scope}--full-resident.json"


def valid_result(path: Path, max_tokens: int) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
        return int(data["generation"]["completion_tokens"]) > 0 and (
            int(data["generation"]["completion_tokens"]) <= max_tokens
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def run_one(
    args: argparse.Namespace,
    scope: str,
    prompt: str,
    engine: str,
    mode: str,
) -> dict[str, Any]:
    output = result_path(args.output, scope, engine, mode)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not args.force and valid_result(output, args.max_tokens):
        return json.loads(output.read_text())

    env = os.environ.copy()
    env.update(
        {
            "OMLX_QWEN36_ADAPTIVE_L1": "1" if mode == "auto" else "0",
            "OMLX_QWEN36_ADAPTIVE_L1_EARLY": "64",
            "OMLX_QWEN36_ADAPTIVE_L1_INTERVAL": "256",
            "OMLX_QWEN36_ADAPTIVE_L1_MAX_PROMOTIONS": str(
                args.max_promotions
            ),
            "OMLX_QWEN36_TIERED_TOKEN_TXN": "0",
        }
    )
    command = [
        sys.executable,
        str(Path(__file__).with_name("check_qwen36_flesh_load.py")),
        str(args.model),
        str(args.profile),
        str(args.store),
        "--backend",
        engine,
        "--scope",
        scope,
        "--experts",
        str(args.experts),
        "--arena-tail-slots",
        str(args.tail),
        "--prompt",
        prompt,
        "--chat-template",
        "--max-tokens",
        str(args.max_tokens),
        "--output",
        str(output),
        "--omit-text",
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        env=env,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"benchmark failed for {scope}/{engine}/{mode}:\n"
            f"{completed.stdout}\n{completed.stderr}"
        )
    data = json.loads(output.read_text())
    tps = data["generation"]["derived_decode_tokens_per_second"]
    print(
        f"done {scope:20s} {engine:7s} {mode:4s} "
        f"tps={tps:.3f} wall={time.perf_counter() - started:.1f}s",
        flush=True,
    )
    return data


def run_oracle(
    args: argparse.Namespace, scope: str, prompt: str
) -> dict[str, Any]:
    output = oracle_path(args.output, scope)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not args.force and valid_result(output, args.max_tokens):
        return json.loads(output.read_text())
    env = os.environ.copy()
    env["OMLX_QWEN36_ADAPTIVE_L1"] = "0"
    command = [
        sys.executable,
        str(Path(__file__).with_name("check_qwen36_flesh_load.py")),
        str(args.model),
        str(args.profile),
        str(args.store),
        "--full-resident",
        "--prompt",
        prompt,
        "--chat-template",
        "--max-tokens",
        str(args.max_tokens),
        "--output",
        str(output),
        "--omit-text",
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        env=env,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"oracle failed for {scope}:\n{completed.stdout}\n{completed.stderr}"
        )
    data = json.loads(output.read_text())
    tps = data["generation"]["derived_decode_tokens_per_second"]
    print(
        f"done {scope:20s} {'oracle':7s} {'full':4s} "
        f"tps={tps:.3f} wall={time.perf_counter() - started:.1f}s",
        flush=True,
    )
    return data


def summarize(
    args: argparse.Namespace,
    scopes: list[str],
    prompts: dict[str, str],
) -> dict[str, Any]:
    rows = []
    for scope in scopes:
        oracle_hash = None
        if args.full_resident_oracle:
            oracle = json.loads(oracle_path(args.output, scope).read_text())
            oracle_hash = str(oracle["generation"]["text_sha256"])
        scope_hashes: dict[str, str] = {}
        for engine in ENGINES:
            off = json.loads(result_path(args.output, scope, engine, "off").read_text())
            auto = json.loads(
                result_path(args.output, scope, engine, "auto").read_text()
            )
            off_gen = off["generation"]
            auto_gen = auto["generation"]
            off_tps = float(off_gen["derived_decode_tokens_per_second"])
            auto_tps = float(auto_gen["derived_decode_tokens_per_second"])
            off_hash = str(off_gen["text_sha256"])
            auto_hash = str(auto_gen["text_sha256"])
            scope_hashes[f"{engine}_off"] = off_hash
            scope_hashes[f"{engine}_auto"] = auto_hash
            adaptive = auto_gen.get("adaptive_l1", {})
            rows.append(
                {
                    "scope": scope,
                    "engine": engine,
                    "off_tps": off_tps,
                    "auto_tps": auto_tps,
                    "auto_change_percent": (auto_tps / off_tps - 1.0) * 100.0,
                    "completion_tokens": int(off_gen["completion_tokens"]),
                    "off_auto_hash_equal": off_hash == auto_hash,
                    "off_hash": off_hash,
                    "auto_hash": auto_hash,
                    "auto_triggers": int(adaptive.get("triggers", 0)),
                    "auto_update_seconds": float(
                        adaptive.get("bank", {}).get("seconds", 0.0)
                    ),
                    "off_store": off_gen.get("expert_store", {}),
                    "auto_store": auto_gen.get("expert_store", {}),
                }
            )
        rows_for_scope = [row for row in rows if row["scope"] == scope]
        exact = all(row["off_auto_hash_equal"] for row in rows_for_scope)
        cross_engine = len(set(scope_hashes.values())) == 1
        for row in rows_for_scope:
            row["scope_all_exact"] = exact and cross_engine
            row["cross_engine_hash_equal"] = cross_engine
            row["full_resident_hash_equal"] = (
                oracle_hash is None or row["off_hash"] == oracle_hash
            )
            row["scope_all_exact"] = (
                row["scope_all_exact"] and row["full_resident_hash_equal"]
            )

    return {
        "model": str(args.model),
        "profile": str(args.profile),
        "store": str(args.store),
        "max_tokens": args.max_tokens,
        "experts": args.experts,
        "tail": args.tail,
        "max_promotions": args.max_promotions,
        "scopes": scopes,
        "prompts": prompts,
        "rows": rows,
        "correctness": {
            "off_auto_pairs": len(rows),
            "off_auto_exact": sum(row["off_auto_hash_equal"] for row in rows),
            "scope_cross_engine_exact": sum(
                all(
                    row["cross_engine_hash_equal"]
                    for row in rows
                    if row["scope"] == scope
                )
                for scope in scopes
            ),
            "full_resident_pairs": len(rows) if args.full_resident_oracle else 0,
            "full_resident_exact": (
                sum(row["full_resident_hash_equal"] for row in rows)
                if args.full_resident_oracle
                else 0
            ),
        },
    }


def main() -> None:
    args = parse_args()
    scopes, prompts = load_inputs(args)
    args.output.mkdir(parents=True, exist_ok=True)
    total = len(scopes) * len(ENGINES) * len(MODES)
    completed = 0
    for scope in scopes:
        for engine in ENGINES:
            for mode in MODES:
                run_one(args, scope, prompts[scope], engine, mode)
                completed += 1
                print(f"progress {completed}/{total}", flush=True)
        if args.full_resident_oracle:
            run_oracle(args, scope, prompts[scope])
    summary = summarize(args, scopes, prompts)
    summary_path = args.output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"summary {summary_path}", flush=True)


if __name__ == "__main__":
    main()
