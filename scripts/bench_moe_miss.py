#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Interleaved DeepSeek-V4 cache-miss benchmark.

Loads the folded expert bank once, warms every (mode, prompt length) pair, then
runs a balanced baseline/CPU/GPU order and reports per-metric medians. With
``--ssd-store``, misses perform real expert-major reads and Metal
materialization while routed computation still uses the folded resident bank.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterator


MODES = ("baseline", "cpu", "gpu")
BALANCED_ORDERS = (
    ("baseline", "cpu", "gpu"),
    ("gpu", "baseline", "cpu"),
    ("cpu", "gpu", "baseline"),
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--pp", type=int, nargs="+", default=[1024, 4096])
    parser.add_argument("--gen", type=int, default=64)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--ssd-store", type=Path)
    parser.add_argument("--ssd-no-cache", action="store_true")
    parser.add_argument(
        "--miss-profile", choices=("requested", "historical"), default="requested"
    )
    parser.add_argument("--compare-overlap", action="store_true")
    parser.add_argument("--compare-defer", action="store_true")
    return parser.parse_args()


def _walk(value: Any, module_type: type, seen: set[int]) -> Iterator[Any]:
    identity = id(value)
    if identity in seen:
        return
    seen.add(identity)
    if isinstance(value, module_type):
        yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child, module_type, seen)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _walk(child, module_type, seen)


def _set_mode(
    moes: list[Any],
    backbones: list[Any],
    dsv4: Any,
    mode: str,
    loader: Any = None,
    miss_profile: str = "requested",
) -> None:
    runtime_mode = "" if mode == "baseline" else mode
    if runtime_mode.startswith("gpu-overlap"):
        runtime_mode = "gpu"
    for moe in moes:
        moe.benchmark_miss_mode = runtime_mode
        moe.benchmark_miss_loader = (
            (lambda ids, layer=moe.layer_idx: loader(layer, ids))
            if loader is not None and runtime_mode
            else None
        )
        moe.benchmark_miss_decode_only = loader is not None
        moe.benchmark_miss_profile = miss_profile
        moe.benchmark_miss_overlap_io = mode.startswith("gpu-overlap")
    for backbone in backbones:
        backbone.benchmark_force_layer_eval = mode.endswith("-sync")
    dsv4._BENCH_MISS_EVENT = 0
    dsv4._BENCH_SCORE_EVENT = 0


class _RealSSDLoader:
    def __init__(self, directory: Path, no_cache: bool) -> None:
        from omlx.cache.moe_expert_store import ExpertMajorStore

        self.stores = {
            layer: ExpertMajorStore(directory / f"layer-{layer:03d}.moe")
            for layer in range(43)
        }
        if no_cache:
            for store in self.stores.values():
                store.set_no_cache()
        self.staging = next(iter(self.stores.values())).allocate_staging()
        self.reset()

    def reset(self) -> None:
        self.experts = 0
        self.bytes = 0
        self.seconds = 0.0

    def __call__(self, layer: int, expert_ids: list[int]) -> None:
        import mlx.core as mx

        store = self.stores[layer]
        started = time.perf_counter()
        for expert_id in expert_ids:
            record = store.read_into(expert_id, self.staging)
            mx.eval(*store.mlx_tensor_views(record, copy_record=True).values())
        self.seconds += time.perf_counter() - started
        self.experts += len(expert_ids)
        self.bytes += len(expert_ids) * store.record_bytes

    def close(self) -> None:
        for store in self.stores.values():
            store.close()


def _median(runs: list[dict], key: str) -> float:
    return statistics.median(run[key] for run in runs)


async def _main(args: argparse.Namespace) -> None:
    if args.repeat < 1:
        raise ValueError("--repeat must be at least 1")
    if args.repeat > len(BALANCED_ORDERS):
        raise ValueError(f"--repeat must be at most {len(BALANCED_ORDERS)}")
    if args.compare_overlap and args.compare_defer:
        raise ValueError("choose only one of --compare-overlap/--compare-defer")
    if not os.environ.get("OMLX_DEEPSEEK_V4_BENCH_EXPERT_SLOTS"):
        raise ValueError("set OMLX_DEEPSEEK_V4_BENCH_EXPERT_SLOTS explicitly")
    os.environ.pop("OMLX_DEEPSEEK_V4_BENCH_MISS_MODE", None)

    import mlx.core as mx
    from omlx.admin.benchmark import _generate_prompt, _run_single_test
    from omlx.engine.batched import BatchedEngine

    model_path = str(args.model.expanduser().resolve())
    print(f"Loading {model_path} …", flush=True)
    started = time.perf_counter()
    engine = BatchedEngine(model_path)
    await engine.start()
    import mlx_lm.models.deepseek_v4 as dsv4

    mx.clear_cache()
    print(f"Loaded in {time.perf_counter() - started:.1f}s", flush=True)

    moes = list(_walk(engine._model, dsv4.DeepseekV4MoE, set()))
    backbones = list(_walk(engine._model, dsv4.DeepseekV4Model, set()))
    if not moes:
        raise RuntimeError("no DeepseekV4MoE modules found")
    if not backbones:
        raise RuntimeError("no DeepseekV4Model backbone found")
    print(f"Found {len(moes)} MoE layers", flush=True)
    ssd_loader = (
        _RealSSDLoader(args.ssd_store.expanduser().resolve(), args.ssd_no_cache)
        if args.ssd_store
        else None
    )

    pp_lengths = sorted(set(args.pp))
    prompts = {
        pp: _generate_prompt(engine.tokenizer, pp) for pp in pp_lengths
    }
    results: dict[tuple[str, int], list[dict]] = defaultdict(list)
    if args.compare_defer:
        modes = ("baseline", "gpu-overlap-sync", "gpu-overlap-defer")
    elif args.compare_overlap:
        modes = ("baseline", "gpu", "gpu-overlap")
    else:
        modes = MODES
    balanced_orders = (
        (modes[0], modes[1], modes[2]),
        (modes[2], modes[0], modes[1]),
        (modes[1], modes[2], modes[0]),
    )

    for pp in pp_lengths:
        for mode in modes:
            _set_mode(moes, backbones, dsv4, mode, ssd_loader, args.miss_profile)
            print(f"Warmup mode={mode} pp={pp} …", flush=True)
            await _run_single_test(engine, prompts[pp], args.gen, pp)

        for round_idx, order in enumerate(balanced_orders[: args.repeat], 1):
            for mode in order:
                _set_mode(
                    moes,
                    backbones,
                    dsv4,
                    mode,
                    ssd_loader,
                    args.miss_profile,
                )
                if ssd_loader is not None:
                    ssd_loader.reset()
                print(
                    f"Measure round={round_idx}/{args.repeat} mode={mode} "
                    f"pp={pp} …",
                    end="",
                    flush=True,
                )
                result = await _run_single_test(
                    engine, prompts[pp], args.gen, pp
                )
                results[(mode, pp)].append(result)
                if ssd_loader is not None and mode != "baseline":
                    result["ssd_experts"] = ssd_loader.experts
                    result["ssd_ms"] = ssd_loader.seconds * 1000
                    result["ssd_gib"] = ssd_loader.bytes / 1024**3
                print(
                    f" ttft={result['ttft_ms']:.0f}ms"
                    f" pp={result['processing_tps']:.0f}/s"
                    f" decode={result['gen_tps']:.1f}/s",
                    f" ssd={ssd_loader.experts}exp/{ssd_loader.seconds * 1000:.0f}ms"
                    if ssd_loader is not None and mode != "baseline"
                    else "",
                    flush=True,
                )

    print("\nMedian results")
    print("| Mode | Prompt | TTFT | Prefill TPS | Prefill loss | Decode TPS | Decode loss |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for pp in pp_lengths:
        base_pp = _median(results[("baseline", pp)], "processing_tps")
        base_decode = _median(results[("baseline", pp)], "gen_tps")
        for mode in modes:
            runs = results[(mode, pp)]
            ttft = _median(runs, "ttft_ms")
            prefill = _median(runs, "processing_tps")
            decode = _median(runs, "gen_tps")
            pp_loss = 100 * (1 - prefill / base_pp)
            decode_loss = 100 * (1 - decode / base_decode)
            print(
                f"| {mode} | {pp:,} | {ttft:,.0f} ms | {prefill:.0f} | "
                f"{pp_loss:.1f}% | {decode:.1f} | {decode_loss:.1f}% |"
            )

    if ssd_loader is not None:
        ssd_loader.close()
    await engine.stop()


if __name__ == "__main__":
    asyncio.run(_main(_args()))
