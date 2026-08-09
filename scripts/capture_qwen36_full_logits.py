#!/usr/bin/env python3
"""Capture unchanged full-resident Qwen logits at the real sampler boundary."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument(
        "reference",
        type=Path,
        help="benchmark JSON providing generation.completion_tokens",
    )
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    import mlx.core as mx

    from omlx.engine.batched import BatchedEngine

    payload = json.loads(args.reference.read_text())
    max_tokens = int(payload["generation"]["completion_tokens"])
    engine = BatchedEngine(args.model)
    try:
        await engine.start()
        scheduler = engine._engine.engine.scheduler
        original_build = scheduler._build_sampler_and_processors
        captured: list[np.ndarray] = []

        def capture_build(sampling_params, request=None):
            sampler, processors = original_build(sampling_params, request)

            def capture_sampler(logits):
                current = logits.astype(mx.float32)
                mx.eval(current)
                captured.append(np.asarray(current))
                return sampler(logits)

            return capture_sampler, processors

        scheduler._build_sampler_and_processors = capture_build
        try:
            output = await engine.generate(
                args.prompt,
                max_tokens=max_tokens,
                temperature=0.0,
                top_p=1.0,
                skip_cache_store=True,
            )
        finally:
            scheduler._build_sampler_and_processors = original_build
        arrays = {
            f"step_{index:04d}": logits
            for index, logits in enumerate(captured)
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        np.savez(args.output, **arrays)
        print(
            json.dumps(
                {
                    "steps": len(arrays),
                    "completion_tokens": output.completion_tokens,
                    "output": str(args.output),
                }
            )
        )
    finally:
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
