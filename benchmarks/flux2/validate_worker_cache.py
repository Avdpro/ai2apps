#!/usr/bin/env python3
"""Exercise the product adapter's first-build and restart cache paths."""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=("4b", "9b"), default="4b")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--adapter-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--edit-output", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()

    # The Spark benchmark environment contains the Runtime dependencies but not
    # the AI2Apps Host. Only these import-time symbols are needed for direct
    # adapter loading.
    worker = ModuleType("ai2apps.model_worker")
    worker.ModelWorkerError = RuntimeError
    worker.ModelWorkerRequest = object
    ai2apps = ModuleType("ai2apps")
    ai2apps.model_worker = worker
    sys.modules.setdefault("ai2apps", ai2apps)
    sys.modules.setdefault("ai2apps.model_worker", worker)
    sys.path.insert(0, str(args.adapter_dir))
    from worker_adapter import Flux2KleinAdapter

    args.data_root.mkdir(parents=True, exist_ok=True)
    context = SimpleNamespace(data_root=args.data_root)
    first_adapter = Flux2KleinAdapter(context)
    started = time.perf_counter()
    pipeline = first_adapter._load_pipeline(
        args.model, args.source, revision=args.revision, bits=8, edit=False
    )
    first_load = time.perf_counter() - started
    result = pipeline.generate_image(
        seed=20260825,
        prompt="A red paper boat on a still lake at sunrise",
        num_inference_steps=4,
        width=1024,
        height=1024,
        guidance=1.0,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output, overwrite=True)
    first_stats = pipeline.ai2apps_optimization_stats()
    asyncio.run(first_adapter.stop())

    second_adapter = Flux2KleinAdapter(context)
    started = time.perf_counter()
    second_adapter._load_pipeline(
        args.model, args.source, revision=args.revision, bits=8, edit=False
    )
    second_load = time.perf_counter() - started
    cache_target = second_adapter._cache_target(
        args.source, args.revision, args.model, 8
    )
    asyncio.run(second_adapter.stop())

    edit_adapter = Flux2KleinAdapter(context)
    started = time.perf_counter()
    edit_pipeline = edit_adapter._load_pipeline(
        args.model, args.source, revision=args.revision, bits=8, edit=True
    )
    edit_load = time.perf_counter() - started
    edit_result = edit_pipeline.generate_image(
        seed=20260826,
        prompt="Turn the paper boat cobalt blue and add light morning mist",
        image_paths=[args.output],
        num_inference_steps=4,
        width=1024,
        height=1024,
        guidance=1.0,
        use_kv_cache=True,
    )
    args.edit_output.parent.mkdir(parents=True, exist_ok=True)
    edit_result.save(args.edit_output, overwrite=True)
    report = {
        "model": args.model,
        "first_load_and_materialize_seconds": first_load,
        "restart_cached_load_seconds": second_load,
        "edit_cached_load_seconds": edit_load,
        "cache_target": str(cache_target),
        "cache_complete": cache_target.is_dir(),
        "cache_bytes": sum(
            path.stat().st_size for path in cache_target.rglob("*") if path.is_file()
        ),
        "generation_seconds": float(result.generation_time),
        "edit_generation_seconds": float(edit_result.generation_time),
        "optimization_stats": first_stats,
        "edit_optimization_stats": edit_pipeline.ai2apps_optimization_stats(),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
