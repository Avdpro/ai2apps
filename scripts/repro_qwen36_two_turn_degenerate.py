#!/usr/bin/env python3
"""Reproduce the Qwen3.6 two-turn `!` degeneration without WebUI/Fusion.

The script talks directly to the configured Qwen Cache-MoE engine.  It can
either continue from the first answer generated in this process or rebuild the
second-turn history from a captured AI2Apps platform database.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import resource
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_MODEL = Path(
    "/Users/avdpropang/.omlx/models/mlx-community/Qwen3.6-35B-A3B-4bit"
)
DEFAULT_DEEPSEEK_MODEL = Path(
    "/Users/avdpropang/.omlx/models/deepseek-ai/DeepSeek-V4-Flash"
)
DEFAULT_SCENE_DB = Path(
    "output/qwen36-two-turn-repro-20260812T085415Z/scene/"
    "ai2apps-platform.sqlite3"
)
DEFAULT_SCENE_SESSION = "ses_cbdbc87b26e24661be31b897d3c43174"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument(
        "--co-resident-deepseek",
        type=Path,
        nargs="?",
        const=DEFAULT_DEEPSEEK_MODEL,
        metavar="MODEL",
        help=(
            "Load (but never infer with) DeepSeek V4 before the Qwen turns, "
            "matching the failing Fusion process memory state."
        ),
    )
    parser.add_argument("--scene-db", type=Path, default=DEFAULT_SCENE_DB)
    parser.add_argument("--scene-session", default=DEFAULT_SCENE_SESSION)
    parser.add_argument(
        "--history-source",
        choices=("generated", "captured"),
        default="generated",
        help=(
            "Build turn 2 from the freshly generated turn 1, or from the exact "
            "turn-1 answer saved from the failing WebUI session. Turn 1 is "
            "always generated and reported."
        ),
    )
    parser.add_argument("--l1-mode", choices=("auto", "off"), default="auto")
    parser.add_argument(
        "--adaptive-l1-runtime",
        choices=("on", "off"),
        default="off",
        help="Control the process-level Qwen adaptive-L1 runtime switch.",
    )
    parser.add_argument(
        "--queue-l1-after-turn1",
        action="store_true",
        help=(
            "Queue a manual L1 optimization after turn 1 has ended. It is "
            "then committed at the first safe Decode boundary of turn 2."
        ),
    )
    parser.add_argument(
        "--session-mode",
        choices=("same", "rotate"),
        default="same",
        help="Reuse one Cache-MoE session across turns or rotate before turn 2.",
    )
    parser.add_argument(
        "--kv-policy", choices=("strict", "session"), default="session"
    )
    parser.add_argument(
        "--store-cache",
        action="store_true",
        help="Commit completed turn KV so cross-turn continuity can be measured.",
    )
    parser.add_argument(
        "--prefix-cache-dir",
        type=Path,
        help="Enable the paged prefix cache at this directory.",
    )
    parser.add_argument("--cache-block-size", type=int, default=256)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--top-k", type=int, default=0)
    parser.add_argument("--repetition-penalty", type=float, default=1.0)
    parser.add_argument(
        "--seed",
        type=int,
        help="Seed MLX sampling so intermittent failures can be replayed.",
    )
    parser.add_argument(
        "--repeat-stop",
        type=int,
        default=96,
        help="Abort after this many identical consecutive token IDs (0 disables).",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--quiet", action="store_true", help="Write the report without printing it."
    )
    return parser.parse_args()


def _memory() -> dict[str, float]:
    import mlx.core as mx

    gib = 1024**3
    mx.synchronize()
    return {
        "mlx_active_gb": mx.get_active_memory() / gib,
        "mlx_peak_gb": mx.get_peak_memory() / gib,
        "mlx_cache_gb": mx.get_cache_memory() / gib,
        "process_peak_rss_gb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        / gib,
    }


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _longest_run(values: list[Any]) -> tuple[Any | None, int]:
    best_value: Any | None = None
    best_count = 0
    prior: Any | None = None
    count = 0
    for value in values:
        if value == prior:
            count += 1
        else:
            prior = value
            count = 1
        if count > best_count:
            best_value = value
            best_count = count
    return best_value, best_count


def _captured_messages(
    database: Path, session_id: str
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            """
            SELECT m.sequence, m.role, m.metadata_json, p.content_json
            FROM messages m
            JOIN message_parts p ON p.message_id = m.id
            WHERE m.session_id = ? AND p.position = 0
            ORDER BY m.sequence
            """,
            (session_id,),
        ).fetchall()
    finally:
        connection.close()
    if len(rows) < 3:
        raise RuntimeError(f"captured session {session_id} has fewer than 3 messages")

    first_user = json.loads(rows[0][3])["content"]
    first_metadata = json.loads(rows[1][2])
    first_part = json.loads(rows[1][3])["content"]
    second_user = json.loads(rows[2][3])["content"]
    reasoning = str(first_metadata.get("reasoning_content") or "")
    visible = first_part
    if reasoning and visible.startswith(reasoning):
        visible = visible[len(reasoning) :].lstrip()
    return (
        {"role": "user", "content": first_user},
        {
            "role": "assistant",
            "content": visible,
            "reasoning_content": reasoning,
        },
        {"role": "user", "content": second_user},
    )


def _assistant_message(text: str) -> dict[str, str]:
    from omlx.api.thinking import extract_thinking

    reasoning, visible = extract_thinking(text)
    message = {"role": "assistant", "content": visible or text}
    if reasoning:
        message["reasoning_content"] = reasoning
    return message


def _configure_engine(
    model: Path,
    prefix_cache_dir: Path | None = None,
    cache_block_size: int = 256,
):
    manifest_path = model / "ai2apps-model.json"
    manifest = json.loads(manifest_path.read_text())
    scope = manifest["scope"]
    engine_id = manifest["engine"]["id"]
    resident = {"lean": 80, "compact": 96, "optimal": 120, "auto": 120}[
        manifest.get("memory_tier", "auto")
    ]
    backend = {
        "qwen3.6-flesh": "flesh",
        "qwen3.6-arena": "arena",
        "qwen3.6-tiered": "tiered",
    }[engine_id]
    from omlx.patches.qwen3_6_flesh.scope_policy import (
        configure_qwen36_scope_policy,
    )

    configure_qwen36_scope_policy(
        scope["profile"],
        scope["default"],
        manifest["expert_store"],
        resident,
        backend=backend,
        arena_tail_slots=int(manifest.get("arena_tail_slots", 24)),
    )
    if backend == "flesh":
        from omlx.engine.qwen36_flesh import Qwen36FleshEngine as Engine
    elif backend == "arena":
        from omlx.engine.qwen36_arena import Qwen36ArenaEngine as Engine
    else:
        from omlx.engine.qwen36_tiered import Qwen36TieredEngine as Engine
    scheduler_config = None
    if prefix_cache_dir is not None:
        from omlx.scheduler import SchedulerConfig

        prefix_cache_dir.mkdir(parents=True, exist_ok=True)
        scheduler_config = SchedulerConfig(
            max_num_seqs=1,
            completion_batch_size=1,
            paged_cache_block_size=cache_block_size,
            paged_ssd_cache_dir=str(prefix_cache_dir),
            model_name=model.name,
            model_path=str(model),
        )
    return (
        Engine(str(model), scheduler_config=scheduler_config),
        manifest,
        backend,
        resident,
    )


def _configure_deepseek_engine(model: Path):
    from omlx.engine.flesh import DeepseekV4FleshEngine
    from omlx.patches.deepseek_v4.scope_policy import configure_scope_policy
    from omlx.scheduler import SchedulerConfig

    manifest = json.loads((model / "ai2apps-model.json").read_text())
    resident = {"lean": 20, "compact": 40, "optimal": 60, "auto": 60}[
        manifest.get("memory_tier", "auto")
    ]
    configure_scope_policy(
        manifest["scope"]["profile"],
        manifest["scope"]["default"],
        manifest["expert_store"],
        resident,
    )
    config = SchedulerConfig(
        max_num_seqs=1,
        completion_batch_size=1,
        model_name=model.name,
        model_path=str(model),
    )
    return DeepseekV4FleshEngine(str(model), scheduler_config=config), resident


async def _generate_turn(
    engine: Any,
    messages: list[dict[str, str]],
    *,
    args: argparse.Namespace,
    session_id: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    last = None
    final_text = ""
    final_tokens: list[int] = []
    repeated_abort = False
    async for output in engine.stream_chat(
        messages,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        repetition_penalty=args.repetition_penalty,
        skip_cache_store=not args.store_cache,
        flesh_session_id=session_id,
        flesh_l1_mode=args.l1_mode,
        flesh_prefill_boost_mode="natural",
        flesh_decode_boost_mode="natural",
        flesh_kv_policy=args.kv_policy,
        # The direct BatchedEngine path consumes this generic name. Keep the
        # flesh-prefixed setting above as well to mirror the WebUI request.
        kv_cache_policy=args.kv_policy,
        chat_template_kwargs={"preserve_thinking": True},
    ):
        last = output
        final_text = str(output.text or "")
        final_tokens = list(output.tokens or ())
        _, run = _longest_run(final_tokens)
        if args.repeat_stop and run >= args.repeat_stop:
            repeated_abort = True
            break
    if last is None:
        raise RuntimeError("Qwen produced no output")
    if not final_tokens:
        final_tokens = list(
            engine._tokenizer.encode(final_text, add_special_tokens=False)
        )
    run_token, run_length = _longest_run(final_tokens)
    characters = list(final_text)
    run_character, run_character_length = _longest_run(characters)
    counts = Counter(final_tokens)
    return {
        "wall_seconds": time.perf_counter() - started,
        "prompt_tokens": int(getattr(last, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(last, "completion_tokens", 0) or 0),
        "cached_tokens": int(getattr(last, "cached_tokens", 0) or 0),
        "finish_reason": str(getattr(last, "finish_reason", "") or ""),
        "repeat_guard_aborted": repeated_abort,
        "text": final_text,
        "text_sha256": _sha256_text(final_text),
        "token_ids": final_tokens,
        "unique_token_ids": len(counts),
        "most_common_token": list(counts.most_common(1)[0]) if counts else None,
        "longest_token_run": {"token_id": run_token, "count": run_length},
        "longest_character_run": {
            "character": run_character,
            "count": run_character_length,
        },
        "degenerate": bool(
            run_length >= 32
            or (run_character_length >= 64 and run_character in {"!", "！"})
        ),
    }


async def run(args: argparse.Namespace) -> None:
    import mlx.core as mx

    model = args.model.expanduser().resolve()
    captured_first_user, captured_first_assistant, captured_second_user = (
        _captured_messages(args.scene_db, args.scene_session)
    )
    os.environ["OMLX_QWEN36_ADAPTIVE_L1"] = (
        "1" if args.adaptive_l1_runtime == "on" else "0"
    )
    engine, manifest, backend, resident = _configure_engine(
        model, args.prefix_cache_dir, args.cache_block_size
    )
    deepseek_engine = None
    deepseek_model = None
    deepseek_resident = None
    base_session = f"qwen36-two-turn-repro-{int(time.time())}"
    if args.seed is not None:
        mx.random.seed(args.seed)
    mx.reset_peak_memory()
    load_started = time.perf_counter()
    try:
        await engine.start()
        if args.co_resident_deepseek is not None:
            deepseek_model = args.co_resident_deepseek.expanduser().resolve()
            deepseek_engine, deepseek_resident = _configure_deepseek_engine(
                deepseek_model
            )
            await deepseek_engine.start()
        load_seconds = time.perf_counter() - load_started
        after_load = _memory()
        turn1_messages = [captured_first_user]
        turn1 = await _generate_turn(
            engine, turn1_messages, args=args, session_id=base_session
        )
        stats_after_turn1 = engine.get_stats().get("flesh", {})
        l1_queue_result = None
        if args.queue_l1_after_turn1:
            l1_queue_result = engine.request_l1_optimization(base_session)
        stats_after_l1_queue = engine.get_stats().get("flesh", {})
        history_assistant = (
            captured_first_assistant
            if args.history_source == "captured"
            else _assistant_message(turn1["text"])
        )
        turn2_session = (
            base_session if args.session_mode == "same" else f"{base_session}-turn2"
        )
        turn2_messages = [
            captured_first_user,
            history_assistant,
            captured_second_user,
        ]
        turn2 = await _generate_turn(
            engine, turn2_messages, args=args, session_id=turn2_session
        )
        report = {
            "format": "ai2apps-qwen36-two-turn-repro",
            "version": 1,
            "webui_used": False,
            "fusion_used": False,
            "reviewer_used": False,
            "co_resident_deepseek_loaded_only": deepseek_engine is not None,
            "co_resident_deepseek_model": (
                str(deepseek_model) if deepseek_model is not None else None
            ),
            "co_resident_deepseek_resident_experts": deepseek_resident,
            "model": str(model),
            "engine_id": manifest["engine"]["id"],
            "backend": backend,
            "resident_experts": resident,
            "scene_database": str(args.scene_db),
            "scene_session": args.scene_session,
            "history_source": args.history_source,
            "l1_mode": args.l1_mode,
            "adaptive_l1_runtime": args.adaptive_l1_runtime,
            "queue_l1_after_turn1": args.queue_l1_after_turn1,
            "l1_queue_result": l1_queue_result,
            "session_mode": args.session_mode,
            "kv_policy": args.kv_policy,
            "store_cache": args.store_cache,
            "prefix_cache_dir": (
                str(args.prefix_cache_dir) if args.prefix_cache_dir else None
            ),
            "cache_block_size": args.cache_block_size,
            "seed": args.seed,
            "sampling": {
                "max_tokens": args.max_tokens,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "top_k": args.top_k,
                "repetition_penalty": args.repetition_penalty,
            },
            "load_seconds": load_seconds,
            "memory_after_load": after_load,
            "turn1_input": turn1_messages,
            "turn1": turn1,
            "engine_stats_after_turn1": stats_after_turn1,
            "engine_stats_after_l1_queue": stats_after_l1_queue,
            "turn2_input": turn2_messages,
            "turn2": turn2,
            "memory_after_turn2": _memory(),
            "engine_stats": engine.get_stats().get("flesh", {}),
            "cache_stats": str(engine.get_cache_stats()),
            "prefix_cache_enabled": engine.prefix_cache_enabled,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        if not args.quiet:
            print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        if deepseek_engine is not None:
            await deepseek_engine.stop()
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
