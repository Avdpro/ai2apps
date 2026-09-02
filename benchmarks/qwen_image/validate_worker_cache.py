#!/usr/bin/env python3
"""Exercise Qwen Image adapter materialization and native-cache reload."""

import argparse
import json
import time
from pathlib import Path
from types import SimpleNamespace

import mlx.core as mx

from worker_adapter import QwenImageAdapter, _derived_checkpoint_complete


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--kind", choices=("generation", "edit"), default="generation")
    parser.add_argument("--quantize", type=int, choices=(4, 8), default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    upstream = (
        "Qwen/Qwen-Image-Edit-2511"
        if args.kind == "edit"
        else "Qwen/Qwen-Image-2512"
    )
    context = SimpleNamespace(data_root=args.cache_root)
    adapter = QwenImageAdapter(context)
    started = time.perf_counter()
    pipeline = adapter._load_pipeline(
        args.kind,
        upstream,
        args.model_path.resolve(),
        revision="benchmark",
        bits=args.quantize,
    )
    materialize_seconds = time.perf_counter() - started
    target = adapter._cache_target(
        args.model_path.resolve(), "benchmark", args.kind, args.quantize
    )
    target_bytes = sum(path.stat().st_size for path in target.rglob("*") if path.is_file())
    assert _derived_checkpoint_complete(target, args.quantize)
    pipeline = None
    mx.clear_cache()

    fresh = QwenImageAdapter(context)
    started = time.perf_counter()
    fresh._load_pipeline(
        args.kind,
        upstream,
        args.model_path.resolve(),
        revision="benchmark",
        bits=args.quantize,
    )
    reload_seconds = time.perf_counter() - started
    report = {
        "model": upstream,
        "kind": args.kind,
        "quantization": f"q{args.quantize}",
        "source": str(args.model_path.resolve()),
        "derived": str(target),
        "derived_bytes": target_bytes,
        "materialize_and_reload_seconds": materialize_seconds,
        "fresh_native_reload_seconds": reload_seconds,
        "active_memory_bytes": mx.get_active_memory(),
        "peak_memory_bytes": mx.get_peak_memory(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
