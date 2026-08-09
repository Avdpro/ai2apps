#!/usr/bin/env python3
"""Run one real multi-turn Qwen3.6 cache-engine conversation."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path
from typing import Any


CONVERSATIONS = {
    "coding": [
        "帮我写一个单文件网页：页面中间有一个按钮，点击后开始放礼花。先说明实现结构，然后给出第一版完整 HTML。",
        "继续改进：礼花用 Canvas 粒子实现，加入重力、阻力、随机颜色和多次爆炸；按钮也要支持键盘操作和 reduced-motion。请给出修改后的完整代码。",
        "现在从性能角度审查这份实现：处理 Retina 缩放、窗口 resize、粒子数量上限和对象复用，避免长时间运行越来越慢。直接给出关键修改。",
        "最后整理成可交付版本：给出完整 HTML，并列出至少六项手工测试，包括移动端、键盘、窗口缩放和连续运行五分钟。",
    ],
    "humanities_social": [
        "比较工业革命在英国率先发生的主要解释。请区分制度、能源、殖民贸易、工资水平与科学文化因素，不要只给单一原因。",
        "继续讨论：从非欧洲中心主义角度批评上一轮框架，说明印度、中国和大西洋奴隶贸易在这个叙事中应该放在什么位置。",
        "把双方观点组织成一场学术辩论：给出正方、反方各三条核心论点，并为每条论点写出对方最强的反驳。",
        "最后写一个平衡的综合结论，明确哪些是较强证据、哪些仍有争议，并提出三个可以继续研究的历史问题。",
    ],
    "medical_health": [
        "请用患者能理解的语言解释家庭血压测量为什么会波动，包括姿势、袖带、时间、运动和焦虑的影响。不要做个体诊断。",
        "假设一个人早晨读数较高、晚上较低，而且左右手偶尔不同。请给出规范复测流程、记录表应该包含什么，以及哪些情况需要尽快咨询医生。",
        "继续完善：区分测量误差、白大衣效应、隐匿性高血压和真实的日内变化，并解释医生通常如何结合家庭记录与动态血压监测。",
        "把前面的内容整理成一页患者说明书：包含准备步骤、测量步骤、七天记录方法、常见错误和明确的安全提示。",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("store", type=Path)
    parser.add_argument("--scope", choices=tuple(CONVERSATIONS), required=True)
    parser.add_argument(
        "--initial-scope",
        default=None,
        help="Initial physical scope; defaults to --scope.",
    )
    parser.add_argument("--backend", choices=("flesh", "arena", "tiered"), required=True)
    parser.add_argument("--mode", choices=("off", "auto"), required=True)
    parser.add_argument(
        "--boost",
        choices=("natural", "turbo", "blast", "tail3", "head3"),
        default="natural",
    )
    parser.add_argument("--turn-tokens", type=int, default=256)
    parser.add_argument("--turns", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--experts", type=int, default=96)
    parser.add_argument("--tail", type=int, default=24)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--include-content",
        action="store_true",
        help="Include generated text/token IDs for deterministic replay artifacts.",
    )
    parser.add_argument(
        "--rotate-session",
        action="store_true",
        help="Use a fresh adaptive-L1 session for every conversation turn.",
    )
    return parser.parse_args()


def token_hash(tokens: list[int]) -> str:
    payload = json.dumps(tokens, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


async def run(args: argparse.Namespace) -> None:
    from omlx.patches.qwen3_6_flesh.scope_policy import (
        configure_qwen36_scope_policy,
    )

    configure_qwen36_scope_policy(
        args.profile,
        args.initial_scope or args.scope,
        args.store,
        args.experts,
        backend=args.backend,
        arena_tail_slots=args.tail,
    )
    if args.backend == "flesh":
        from omlx.engine.qwen36_flesh import Qwen36FleshEngine as Engine
    elif args.backend == "arena":
        from omlx.engine.qwen36_arena import Qwen36ArenaEngine as Engine
    else:
        from omlx.engine.qwen36_tiered import Qwen36TieredEngine as Engine

    engine = Engine(str(args.model))
    messages: list[dict[str, str]] = []
    turns: list[dict[str, Any]] = []
    session_id = f"conversation-{args.scope}"
    try:
        await engine.start()
        user_messages = CONVERSATIONS[args.scope][: args.turns]
        for index, user_text in enumerate(user_messages, start=1):
            request_session_id = (
                f"{session_id}-turn-{index}" if args.rotate_session else session_id
            )
            messages.append({"role": "user", "content": user_text})
            prompt = engine._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
            started = time.perf_counter()
            output = await engine.generate(
                prompt,
                max_tokens=args.turn_tokens,
                temperature=0.0,
                top_p=1.0,
                skip_cache_store=True,
                flesh_session_id=request_session_id,
                flesh_l1_mode=args.mode,
                flesh_boost_mode=args.boost,
            )
            finished = time.perf_counter()
            decode_seconds = finished - output.first_token_at
            tokens = output.tokens or engine._tokenizer.encode(
                output.text, add_special_tokens=False
            )
            turn = {
                    "turn": index,
                    "prompt_tokens": output.prompt_tokens,
                    "completion_tokens": output.completion_tokens,
                    "ttft_seconds": output.first_token_at - started,
                    "decode_seconds_after_first_token": decode_seconds,
                    "decode_tps": (output.completion_tokens - 1) / decode_seconds,
                    "text_sha256": hashlib.sha256(output.text.encode()).hexdigest(),
                    "token_sha256": token_hash(list(tokens)),
            }
            if args.include_content:
                turn["text"] = output.text
                turn["token_ids"] = list(tokens)
            turns.append(turn)
            messages.append({"role": "assistant", "content": output.text})

        stats = engine.get_stats().get("flesh", {})
        total_decode_tokens = sum(turn["completion_tokens"] - 1 for turn in turns)
        total_decode_seconds = sum(
            turn["decode_seconds_after_first_token"] for turn in turns
        )
        report = {
            "scope": args.scope,
            "initial_scope": args.initial_scope or args.scope,
            "backend": args.backend,
            "mode": args.mode,
            "boost": args.boost,
            "turn_tokens": args.turn_tokens,
            "user_messages": user_messages,
            "turns": turns,
            "overall_decode_tps": total_decode_tokens / total_decode_seconds,
            "late_two_turn_decode_tps": sum(
                turn["completion_tokens"] - 1 for turn in turns[-2:]
            )
            / sum(turn["decode_seconds_after_first_token"] for turn in turns[-2:]),
            "adaptive_l1": stats.get("adaptive_l1"),
            "engine_boost": stats.get("engine_boost"),
            "selector": stats.get("selector"),
            "last_selection": stats.get("last_selection"),
            "backend_cache": stats.get(args.backend),
            "expert_store": stats.get("expert_store"),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
