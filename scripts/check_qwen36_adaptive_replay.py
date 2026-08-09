#!/usr/bin/env python3
"""Forced-token logits parity around a Qwen3.6 adaptive-L1 commit."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("profile")
    parser.add_argument("store")
    parser.add_argument("tokens", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--scope", default="coding")
    parser.add_argument("--experts", type=int, default=96)
    parser.add_argument("--tail", type=int, default=24)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--capture-from", type=int, default=60)
    parser.add_argument("--capture-to", type=int, default=96)
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    import mlx.core as mx
    from mlx_lm.models.cache import make_prompt_cache

    from omlx.engine.qwen36_tiered import Qwen36TieredEngine
    from omlx.patches.qwen3_6_flesh.scope_policy import (
        configure_qwen36_scope_policy,
    )

    configure_qwen36_scope_policy(
        args.profile,
        args.scope,
        args.store,
        args.experts,
        backend="tiered",
        arena_tail_slots=args.tail,
    )
    payload = json.loads(args.tokens.read_text())
    forced = [int(value) for value in payload["generation"]["token_ids"]]
    reference = np.load(args.reference) if args.reference else None
    engine = Qwen36TieredEngine(args.model)
    try:
        await engine.start()
        from omlx.patches.qwen3_6_flesh.model_patch import (
            set_qwen36_parity_observer,
        )

        trace_step = -1
        trace: dict[
            int, list[tuple[int, object, object, object, object, object, object]]
        ] = {}

        def observe(block, x, inds, _scores, routed, output):
            if args.capture_from <= trace_step <= args.capture_to:
                l1_map = mx.array(
                    block.scope_expert_to_slot_values, dtype=mx.int32
                )[inds]
                tail_values = getattr(block, "scope_tail_to_slot_values", None)
                tail_map = (
                    mx.array(tail_values, dtype=mx.int32)[inds]
                    if tail_values is not None
                    else mx.full(inds.shape, -1, dtype=mx.int32)
                )
                isolated_routes = []
                flat_l1 = l1_map.reshape(-1)
                flat_tail = tail_map.reshape(-1)
                for position in range(inds.size):
                    l1_slot = mx.maximum(flat_l1[position], 0).reshape(1, 1, 1)
                    tail_slot = mx.maximum(flat_tail[position], 0).reshape(1, 1, 1)
                    l1_route = block.switch_mlp(x, l1_slot).reshape(-1)
                    tail_route = block.tail_switch_mlp(x, tail_slot).reshape(-1)
                    isolated_routes.append(
                        mx.where(flat_l1[position] >= 0, l1_route, tail_route)
                    )
                isolated = mx.stack(isolated_routes)
                trace.setdefault(trace_step, []).append(
                    (
                        block.scope_layer,
                        x,
                        inds,
                        l1_map,
                        tail_map,
                        isolated,
                        routed,
                        output,
                    )
                )

        set_qwen36_parity_observer(observe)
        prompt = engine._tokenizer.apply_chat_template(
            [{"role": "user", "content": args.prompt}],
            tokenize=False,
            add_generation_prompt=True,
        )
        prompt_ids = engine._tokenizer.encode(prompt, add_special_tokens=False)
        await engine._qwen_adaptive.prepare(
            {"flesh_session_id": "parity", "flesh_l1_mode": "auto"}
        )
        cache = make_prompt_cache(engine._model)
        trace_step = 0
        logits = engine._model(mx.array([prompt_ids]), cache=cache)[:, -1, :]
        captures: dict[str, np.ndarray] = {}
        comparisons = []
        for index, token in enumerate(forced):
            if args.capture_from <= index <= args.capture_to:
                current_logits = logits.astype(mx.float32)
                layer_trace = trace.get(index, [])
                trace_arrays = [
                    array
                    for _, x, inds, l1_map, tail_map, isolated, routed, output in layer_trace
                    for array in (x, inds, l1_map, tail_map, isolated, routed, output)
                ]
                mx.eval(current_logits, *trace_arrays)
                current = np.asarray(current_logits)
                key = f"step_{index:04d}"
                captures[key] = current
                for (
                    layer,
                    x,
                    inds,
                    l1_map,
                    tail_map,
                    isolated,
                    routed,
                    output,
                ) in layer_trace:
                    prefix = f"{key}_layer_{layer:02d}"
                    captures[f"{prefix}_input"] = np.asarray(x.astype(mx.float32))
                    captures[f"{prefix}_inds"] = np.asarray(inds)
                    captures[f"{prefix}_l1"] = np.asarray(l1_map)
                    captures[f"{prefix}_tail"] = np.asarray(tail_map)
                    captures[f"{prefix}_isolated"] = np.asarray(
                        isolated.astype(mx.float32)
                    )
                    captures[f"{prefix}_routed"] = np.asarray(
                        routed.astype(mx.float32)
                    )
                    captures[f"{prefix}_output"] = np.asarray(
                        output.astype(mx.float32)
                    )
                if reference is not None:
                    expected = reference[key]
                    delta = np.abs(current - expected)
                    actual_top = np.argsort(current[0])[-10:][::-1]
                    expected_top = np.argsort(expected[0])[-10:][::-1]
                    comparisons.append(
                        {
                            "step": index,
                            "max_abs": float(delta.max()),
                            "mean_abs": float(delta.mean()),
                            "argmax_equal": bool(actual_top[0] == expected_top[0]),
                            "top10_ordered_equal": bool(
                                np.array_equal(actual_top, expected_top)
                            ),
                            "top10_overlap": int(
                                len(set(actual_top.tolist()) & set(expected_top.tolist()))
                            ),
                        }
                    )
                    if delta.max() > 0:
                        layer_diffs = []
                        for layer, *_ in layer_trace:
                            prefix = f"{key}_layer_{layer:02d}"
                            actual_inds = captures[f"{prefix}_inds"]
                            expected_inds = reference[f"{prefix}_inds"]
                            actual_l1 = captures[f"{prefix}_l1"]
                            expected_l1 = reference[f"{prefix}_l1"]
                            actual_tail = captures[f"{prefix}_tail"]
                            expected_tail = reference[f"{prefix}_tail"]
                            isolated_delta = np.abs(
                                captures[f"{prefix}_isolated"]
                                - reference[f"{prefix}_isolated"]
                            )
                            input_delta = np.abs(
                                captures[f"{prefix}_input"]
                                - reference[f"{prefix}_input"]
                            )
                            routed_delta = np.abs(
                                captures[f"{prefix}_routed"]
                                - reference[f"{prefix}_routed"]
                            )
                            output_delta = np.abs(
                                captures[f"{prefix}_output"]
                                - reference[f"{prefix}_output"]
                            )
                            layer_diffs.append(
                                {
                                    "layer": layer,
                                    "inds_equal": bool(
                                        np.array_equal(actual_inds, expected_inds)
                                    ),
                                    "expert_ids": actual_inds.reshape(-1).tolist(),
                                    "reference_l1_slots": expected_l1.reshape(
                                        -1
                                    ).tolist(),
                                    "adaptive_l1_slots": actual_l1.reshape(-1).tolist(),
                                    "reference_tail_slots": expected_tail.reshape(
                                        -1
                                    ).tolist(),
                                    "adaptive_tail_slots": actual_tail.reshape(
                                        -1
                                    ).tolist(),
                                    "isolated_route_max_abs": isolated_delta.max(
                                        axis=1
                                    ).tolist(),
                                    "input_max_abs": float(input_delta.max()),
                                    "routed_max_abs": float(routed_delta.max()),
                                    "output_max_abs": float(output_delta.max()),
                                }
                            )
                        comparisons[-1]["first_layer_difference"] = next(
                            (
                                item
                                for item in layer_diffs
                                if not item["inds_equal"]
                                or item["input_max_abs"] > 0
                                or item["routed_max_abs"] > 0
                                or item["output_max_abs"] > 0
                            ),
                            None,
                        )
            engine._qwen_adaptive.between_step(
                SimpleNamespace(outputs=[SimpleNamespace(completion_tokens=index + 1)])
            )
            trace_step = index + 1
            logits = engine._model(
                mx.array([[token]], dtype=mx.int32), cache=cache
            )[:, -1, :]
        if reference is None:
            np.savez(args.output, **captures)
            result = {"captured": len(captures), "output": str(args.output)}
        else:
            result = {
                "comparisons": comparisons,
                "first_nonzero": next(
                    (item for item in comparisons if item["max_abs"] > 0), None
                ),
                "first_argmax_mismatch": next(
                    (item for item in comparisons if not item["argmax_equal"]), None
                ),
                "adaptive": engine._qwen_adaptive.stats(),
            }
            args.output.write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
    finally:
        try:
            set_qwen36_parity_observer(None)
        except UnboundLocalError:
            pass
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
