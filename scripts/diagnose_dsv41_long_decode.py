#!/usr/bin/env python3
"""Run a forced DeepSeek V4.1 Decode and sample its bounded live state.

The fixed token deliberately prevents EOS so the test can reach a requested
completion length.  ``--runtime-native-dir`` lets a source checkout reuse the
signed Direct-L1 extension from an installed Runtime without copying it.
"""

from __future__ import annotations

import argparse
import importlib
import json
import resource
import sys
import time
import types
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


def _install_runtime_native_package(path: Path) -> None:
    importlib.import_module("omlx.custom_kernels")

    source = SOURCE_ROOT / "omlx/custom_kernels/glm_moe_dsa"
    package_name = "omlx.custom_kernels.glm_moe_dsa"
    package = types.ModuleType(package_name)
    package.__package__ = package_name
    package.__path__ = [str(path.resolve()), str(source)]
    sys.modules[package_name] = package


def _snapshot(model, token: int, started: float) -> dict[str, object]:
    import mlx.core as mx

    return {
        "token": token,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "active_bytes": int(mx.get_active_memory()),
        "cache_bytes": int(mx.get_cache_memory()),
        "peak_bytes": int(mx.get_peak_memory()),
        "process_peak_rss_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "banks": len(model.banks),
        "pending_outputs": sum(len(bank.pending) for bank in model.banks.values()),
        "all_hit_layers": int(model.stats.get("all_hit_steps", 0)),
        "route_requests": int(model.stats.get("route_requests", 0)),
        "misses": int(model.stats.get("misses", 0)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--tokens", type=int, default=12_000)
    parser.add_argument("--sample-every", type=int, default=256)
    parser.add_argument("--max-context", type=int, default=16_384)
    parser.add_argument("--runtime-native-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.runtime_native_dir:
        _install_runtime_native_package(args.runtime_native_dir)

    import mlx.core as mx

    from omlx.patches.deepseek_v41.engine import DeepseekV41Engine

    if args.tokens < 1 or args.tokens + 128 >= args.max_context:
        parser.error("tokens must leave room for the prompt inside max-context")

    engine = DeepseekV41Engine(args.checkpoint, max_context=args.max_context)
    records: list[dict[str, object]] = []
    started = time.monotonic()
    fixed_token: int | None = None

    def write_report(status: str, error: str | None = None) -> None:
        if not args.output:
            return
        report = {
            "status": status,
            "error": error,
            "checkpoint": str(args.checkpoint.resolve()),
            "tokens": args.tokens,
            "sample_every": args.sample_every,
            "max_context": args.max_context,
            "fixed_token": fixed_token,
            "mlx_version": getattr(mx, "__version__", None),
            "resource_count_api": "unavailable in MLX 0.32.0 Python API",
            "records": records,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + ".tmp")
        temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        temporary.replace(args.output)

    try:
        engine._start_sync()
        prompt_ids, _ = engine._prepare_sync(
            [{"role": "user", "content": "Count upward carefully and do not stop."}],
            None,
            1,
            {"thinking_mode": "thinking"},
        )
        fixed_ids = engine._tokenizer.encode(" the").ids
        if not fixed_ids:
            raise RuntimeError("tokenizer did not encode the fixed Decode token")
        fixed_token = int(fixed_ids[-1])
        mx.reset_peak_memory()
        records.append(_snapshot(engine._model, 0, started))
        print(json.dumps(records[-1]), flush=True)
        write_report("running")

        for index in range(args.tokens):
            engine._decode_sync(fixed_token, len(prompt_ids) + index)
            completed = index + 1
            if completed % args.sample_every == 0 or completed == args.tokens:
                records.append(_snapshot(engine._model, completed, started))
                print(json.dumps(records[-1]), flush=True)
                write_report("running")

        # A second request proves reset/reuse after the long sequence.
        second_ids, _ = engine._prepare_sync(
            [{"role": "user", "content": "Reply briefly."}],
            None,
            2,
            {"thinking_mode": "chat"},
        )
        for index in range(8):
            engine._decode_sync(fixed_token, len(second_ids) + index)
        final = _snapshot(engine._model, args.tokens + 8, started)
        final["second_request_completed"] = True
        records.append(final)
        print(json.dumps(final), flush=True)
        write_report("completed")
    except BaseException as exc:
        write_report("failed", f"{type(exc).__name__}: {exc}")
        raise
    finally:
        if engine._model is not None:
            engine._model.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
