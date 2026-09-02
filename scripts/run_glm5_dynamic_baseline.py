#!/usr/bin/env python3
"""Run the exact configurable-slot GLM-5.3 Flash dynamic-cache baseline."""

from __future__ import annotations

import argparse
import os
import resource
import time
from pathlib import Path


def _scope_ids(path: Path, scope: str, capacity: int) -> dict[int, tuple[int, ...]]:
    import json

    payload = json.loads(path.read_text())
    selected = payload["scopes"][scope]
    result = {}
    for raw_layer, stats in selected["layer_stats"].items():
        phase = stats["phases"]["decode"]
        counts = phase["counts_by_expert"]
        mass = phase["mass_by_expert"]
        count_total = max(sum(counts), 1)
        mass_total = max(sum(mass), 1e-12)
        ranking = sorted(
            range(len(counts)),
            key=lambda expert: (
                -(
                    0.75 * counts[expert] / count_total
                    + 0.25 * mass[expert] / mass_total
                )
            ),
        )
        result[int(raw_layer)] = tuple(ranking[:capacity])
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint")
    parser.add_argument("expert_store")
    parser.add_argument("--prompt", default="用一句话解释什么是混合专家模型。")
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument(
        "--prompt-chars",
        type=int,
        help="Use only the first N characters from --prompt-file.",
    )
    parser.add_argument("--prompt-prefix", default="")
    parser.add_argument("--max-tokens", type=int, default=16)
    parser.add_argument("--io-workers", type=int, default=4)
    parser.add_argument("--slots", type=int, default=80)
    parser.add_argument(
        "--hot-slots",
        type=int,
        default=0,
        help="Persistent fixed-shape L0 slots in addition to --slots L1 slots.",
    )
    parser.add_argument(
        "--l1-promotions-per-layer",
        type=int,
        default=0,
        help="Promote this many repeatedly-hit L0 experts per layer and token.",
    )
    parser.add_argument("--weighted-sum", action="store_true")
    parser.add_argument("--nosync-probe", action="store_true")
    parser.add_argument(
        "--mtp-probe",
        action="store_true",
        help="Load layer 45 and run one native MTP prefill/seed probe.",
    )
    parser.add_argument(
        "--mtp-force-reject-probe",
        action="store_true",
        help="Force one rejected verifier token and compare rollback with replay.",
    )
    parser.add_argument("--mtp-probe-tokens", type=int, default=6)
    parser.add_argument("--mtp-draft-block-size", type=int, default=3)
    parser.add_argument(
        "--boost-mode",
        choices=("natural", "turbo", "blast", "tail3", "head3"),
        default="natural",
        help="Lossy Prefill and Decode policy; natural remains exact.",
    )
    parser.add_argument("--scope-profile", type=Path)
    parser.add_argument("--scope", default="coding")
    parser.add_argument(
        "--scope-prefill-adapt",
        action="store_true",
        help="Seed L1 from Scope, then let exact prompt routes adapt it during prefill.",
    )
    args = parser.parse_args()

    checkpoint = Path(args.checkpoint).expanduser().resolve()
    store = Path(args.expert_store).expanduser().resolve()
    os.environ["OMLX_GLM5_DYNAMIC_STORE"] = str(store)
    if args.hot_slots < 0 or args.slots + args.hot_slots > 96:
        parser.error("--slots + --hot-slots must be in [8, 96]")
    os.environ["OMLX_GLM5_DYNAMIC_SLOTS"] = str(args.slots + args.hot_slots)
    os.environ["OMLX_GLM5_TAIL_SLOTS"] = str(args.hot_slots)
    # This is the text TPS baseline; preserve its explicitly requested slots.
    os.environ["OMLX_GLM5_VISION_L1_RESERVE_SLOTS"] = "0"
    os.environ["OMLX_GLM5_L1_PROMOTIONS_PER_LAYER"] = str(args.l1_promotions_per_layer)
    os.environ["OMLX_GLM5_DYNAMIC_IO_WORKERS"] = str(args.io_workers)
    os.environ["OMLX_GLM5_WEIGHTED_SUM"] = "1" if args.weighted_sum else "0"
    os.environ["OMLX_GLM5_NOSYNC_PROBE"] = "1" if args.nosync_probe else "0"
    os.environ["OMLX_GLM5_BOOST_MODE"] = args.boost_mode
    if args.mtp_probe:
        os.environ["OMLX_GLM5_MTP_ENABLED"] = "1"
    os.environ["OMLX_GLM5_PREFILL_RETAIN_L1"] = (
        "1" if args.scope_profile is not None and not args.scope_prefill_adapt else "0"
    )

    import mlx.core as mx
    from mlx_vlm.generate import generate_step
    from mlx_vlm.utils import load_model
    from transformers import AutoTokenizer

    from omlx.patches.glm5_next_cache.runtime import (
        get_glm5_dynamic_cache,
        glm5_dynamic_safetensors_on_load,
    )
    from omlx.utils.model_loading import maybe_apply_pre_load_patches

    tokenizer = AutoTokenizer.from_pretrained(checkpoint)
    prompt_body = (
        args.prompt_file.expanduser().read_text()
        if args.prompt_file is not None
        else args.prompt
    )
    if args.prompt_chars is not None:
        if args.prompt_file is None or args.prompt_chars <= 0:
            raise ValueError("--prompt-chars requires --prompt-file and N > 0")
        prompt_body = prompt_body[: args.prompt_chars]
    prompt = args.prompt_prefix + prompt_body
    rendered = tokenizer.apply_chat_template(
        [{"role": "user", "content": prompt}],
        tokenize=False,
        add_generation_prompt=True,
    )
    input_ids = mx.array([tokenizer.encode(rendered)], dtype=mx.int32)

    maybe_apply_pre_load_patches(str(checkpoint), for_vlm=True)
    try:
        from mlx_vlm.models.glm5_next import language as _glm5_language  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("GLM5 compatibility modules could not be installed") from exc

    load_started = time.perf_counter()
    with glm5_dynamic_safetensors_on_load(checkpoint):
        model = load_model(checkpoint, lazy=False, strict=True)
    load_seconds = time.perf_counter() - load_started

    dynamic = get_glm5_dynamic_cache(str(store))
    scope_warm_seconds = 0.0
    if args.scope_profile is not None:
        scope_ids = _scope_ids(
            args.scope_profile.expanduser().resolve(), args.scope, dynamic.capacity
        )
        warm_started = time.perf_counter()
        for layer, ids in sorted(scope_ids.items()):
            block = model.language_model.model.layers[layer].mlp
            lookup = dynamic.resolve(layer, ids, block.switch_mlp)
            block.dynamic_lookup_values = lookup
        scope_warm_seconds = time.perf_counter() - warm_started

    generated: list[int] = []
    cache_at_first_token = None
    generation_started = time.perf_counter()
    first_token_seconds = None
    for token, _ in generate_step(
        input_ids,
        model,
        pixel_values=None,
        mask=None,
        max_tokens=args.max_tokens,
        temperature=0.0,
    ):
        if isinstance(token, mx.array):
            mx.eval(token)
        if first_token_seconds is None:
            first_token_seconds = time.perf_counter() - generation_started
            cache_at_first_token = dynamic.stats().copy()
        generated.append(
            int(token.item()) if isinstance(token, mx.array) else int(token)
        )
    generation_seconds = time.perf_counter() - generation_started

    mtp_probe = None
    mtp = getattr(model.language_model, "mtp", None)
    if args.mtp_probe:
        if mtp is None:
            raise RuntimeError("--mtp-probe requested but layer 45 was not loaded")
        probe_started = time.perf_counter()
        target_cache = model.language_model.make_cache()
        target = model.language_model(
            input_ids,
            cache=target_cache,
            return_hidden=True,
            return_shared_kv=True,
        )
        bonus = mx.argmax(target.logits[:, -1, :], axis=-1)
        mx.eval(target.logits, target.hidden_states[-1], bonus)
        target_phase_peak_gib = mx.get_peak_memory() / 2**30
        dynamic.release_prefill_workspaces()
        mx.reset_peak_memory()
        from omlx.speculative.vlm_mtp import (
            VLMMTPDrafter,
            run_vlm_mtp_decode,
        )

        drafter = VLMMTPDrafter(mtp, "mtp", "integrated-layer-45")
        mtp_decode_started = time.perf_counter()
        mtp_tokens = list(
            run_vlm_mtp_decode(
                target_language_model=model.language_model,
                drafter=drafter,
                prompt_cache=target_cache,
                hidden=target.hidden_states[-1],
                shared_kv_states=target.shared_kv_states or {},
                first_bonus=bonus,
                max_tokens=args.mtp_probe_tokens,
                sampler=lambda logits: mx.argmax(logits, axis=-1),
                prompt_tokens=input_ids,
                draft_block_size=args.mtp_draft_block_size,
                token_dtype=input_ids.dtype,
            )
        )
        mtp_decode_seconds = time.perf_counter() - mtp_decode_started
        rollback_max_abs = None
        rollback_state_max_abs = None
        rollback_conv_max_abs = None
        rollback_token_match = None
        if args.mtp_force_reject_probe:
            rollback_cache = model.language_model.make_cache()
            model.language_model(input_ids, cache=rollback_cache, skip_logits=True)
            wrong = (bonus.astype(mx.int32) + 1) % model.language_model.args.vocab_size
            verify_input = mx.stack((bonus, wrong), axis=1)
            _, _, gdn_states = model.language_model.speculative_verify_hidden(
                verify_input, rollback_cache
            )
            model.language_model.rollback_speculative_cache(
                rollback_cache, gdn_states, accepted=0, block_size=2
            )
            probe_token = (bonus.astype(mx.int32) + 2) % model.language_model.args.vocab_size

            reference_cache = model.language_model.make_cache()
            model.language_model(input_ids, cache=reference_cache, skip_logits=True)
            model.language_model(bonus[:, None], cache=reference_cache, skip_logits=True)
            state_diffs = []
            conv_diffs = []
            for rolled_cache, ref_cache in zip(rollback_cache, reference_cache):
                if hasattr(rolled_cache, "cache"):
                    conv_diffs.append(
                        mx.max(
                            mx.abs(
                                rolled_cache[0].astype(mx.float32)
                                - ref_cache[0].astype(mx.float32)
                            )
                        )
                    )
                    state_diffs.append(
                        mx.max(
                            mx.abs(
                                rolled_cache[1].astype(mx.float32)
                                - ref_cache[1].astype(mx.float32)
                            )
                        )
                    )
            rollback_state_max_abs = float(mx.max(mx.stack(state_diffs)).item())
            rollback_conv_max_abs = float(mx.max(mx.stack(conv_diffs)).item())
            rolled = model.language_model(probe_token[:, None], cache=rollback_cache).logits
            reference = model.language_model(
                probe_token[:, None], cache=reference_cache
            ).logits
            diff = mx.max(mx.abs(rolled.astype(mx.float32) - reference.astype(mx.float32)))
            mx.eval(diff)
            rollback_max_abs = float(diff.item())
            rollback_token_match = bool(
                int(mx.argmax(rolled[:, -1, :], axis=-1).item())
                == int(mx.argmax(reference[:, -1, :], axis=-1).item())
            )
        mtp_probe = {
            "seconds": round(time.perf_counter() - probe_started, 3),
            "tokens": [int(value) for value in mtp_tokens],
            "decode_seconds": round(mtp_decode_seconds, 3),
            "decode_tps": round(
                max(0, len(mtp_tokens) - 1) / max(mtp_decode_seconds, 1e-9), 3
            ),
            "accepted_drafts": list(getattr(mtp, "accept_lens", [])),
            "draft_lengths": list(getattr(mtp, "draft_lens", [])),
            "forced_reject_max_abs": rollback_max_abs,
            "forced_reject_state_max_abs": rollback_state_max_abs,
            "forced_reject_conv_max_abs": rollback_conv_max_abs,
            "forced_reject_token_match": rollback_token_match,
            "layer_45_resident": sum(
                expert >= 0 for expert in dynamic.policy.state(45).expert_ids
            ),
            "target_phase_peak_gib": round(target_phase_peak_gib, 3),
            "mtp_phase_peak_gib": round(mx.get_peak_memory() / 2**30, 3),
        }

    print(tokenizer.decode(generated, skip_special_tokens=False))
    final_cache = dynamic.stats()
    boost_stats = {
        key: 0
        for key in (
            "routes_replaced",
            "misses_before",
            "misses_after",
            "prefill_routes_replaced",
            "prefill_misses_before",
            "prefill_misses_after",
            "decode_routes_replaced",
            "decode_misses_before",
            "decode_misses_after",
        )
    }
    for decoder in model.language_model.model.layers:
        counters = getattr(decoder.mlp, "boost_stats", None)
        if counters is None:
            continue
        for key in boost_stats:
            boost_stats[key] += int(counters[key])
    boost_stats["misses_avoided"] = (
        boost_stats["misses_before"] - boost_stats["misses_after"]
    )
    decode_seconds = max(
        0.0,
        generation_seconds - (first_token_seconds or generation_seconds),
    )
    prefill_cache = cache_at_first_token or final_cache
    counter_keys = (
        "calls",
        "hit_calls",
        "miss_calls",
        "prefill_calls",
        "experts_loaded",
        "bytes_loaded",
        "read_seconds",
        "materialize_seconds",
        "patch_seconds",
        "ssd_to_ready_seconds",
        "sync_seconds",
        "direct_load_calls",
        "direct_load_bytes",
    )
    decode_cache = {key: final_cache[key] - prefill_cache[key] for key in counter_keys}
    print(
        {
            "load_seconds": round(load_seconds, 3),
            "scope_warm_seconds": round(scope_warm_seconds, 3),
            "l1_slots": args.slots,
            "hot_slots": args.hot_slots,
            "l1_promotions_per_layer": args.l1_promotions_per_layer,
            "boost_mode": args.boost_mode,
            "prompt_tokens": int(input_ids.size),
            "generated_tokens": len(generated),
            "ttft_seconds": round(first_token_seconds or 0.0, 3),
            "prefill_effective_tps": round(
                int(input_ids.size) / max(1e-9, first_token_seconds or 0.0),
                3,
            ),
            "generation_seconds": round(generation_seconds, 3),
            "decode_seconds": round(decode_seconds, 3),
            "decode_tps": round(
                max(0, len(generated) - 1) / max(1e-9, decode_seconds),
                3,
            ),
            "active_gib": round(mx.get_active_memory() / 2**30, 3),
            "peak_gib": round(mx.get_peak_memory() / 2**30, 3),
            "rss_peak_gib": round(
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**30,
                3,
            ),
            "cache_prefill": prefill_cache,
            "cache_decode": decode_cache,
            "cache_total": final_cache,
            "engine_boost": boost_stats,
            "mtp_probe": mtp_probe,
        }
    )


if __name__ == "__main__":
    main()
