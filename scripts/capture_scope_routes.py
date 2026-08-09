#!/usr/bin/env python3
"""Capture compact real Decode Top6 routes for cache-policy simulation."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from bench_scope_once import _load_encoder
from bench_scope_review import _ReviewCollector, _install, _restore


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("sample_id")
    parser.add_argument("--runtime-scope")
    parser.add_argument("--gen", type=int, default=128)
    parser.add_argument("--interval", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> dict:
    from omlx.admin.benchmark import _run_single_test
    from omlx.engine.batched import BatchedEngine

    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite route trace: {output}")
    dataset = json.loads(args.dataset.expanduser().read_text())
    samples = {sample["id"]: sample for sample in dataset["samples"]}
    sample = samples[args.sample_id]
    expected_scope = args.runtime_scope or sample["scope"]
    if os.environ.get("OMLX_DEEPSEEK_V4_SCOPE_NAME") != expected_scope:
        raise ValueError("configured runtime Scope does not match trace request")

    model_path = args.model.expanduser().resolve()
    encode_messages = _load_encoder(model_path)
    prompt = encode_messages(list(sample["messages"]), thinking_mode="chat")
    engine = BatchedEngine(str(model_path))
    await engine.start()
    collector = _ReviewCollector(args.interval)
    core = engine._engine.engine
    loop = asyncio.get_running_loop()
    originals = None
    try:
        prompt_ids = engine.tokenizer.encode(prompt, add_special_tokens=False)
        originals = await loop.run_in_executor(
            core._mlx_executor, _install, engine._model, collector
        )
        result = await _run_single_test(engine, prompt_ids, args.gen, len(prompt_ids))
    finally:
        if originals is not None:
            await loop.run_in_executor(core._mlx_executor, _restore, originals)
        await engine.stop()

    if collector.decode_steps != args.gen or len(collector.trace) != args.gen:
        raise RuntimeError(
            f"incomplete trace: steps={collector.decode_steps} rows={len(collector.trace)}"
        )
    payload = {
        "version": 1,
        "sample_id": args.sample_id,
        "scope": expected_scope,
        "language": sample["language"],
        "prompt_tokens": len(prompt_ids),
        "decode_tokens": args.gen,
        "review_interval": args.interval,
        "decode_tokens_per_second": result["gen_tps"],
        "review": collector.summary(),
        "routes": collector.trace,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as target:
        target.write(json.dumps(payload, separators=(",", ":")) + "\n")
    print(json.dumps({key: payload[key] for key in payload if key != "routes"}))
    return payload


def main() -> None:
    asyncio.run(_run(_args()))


if __name__ == "__main__":
    main()
