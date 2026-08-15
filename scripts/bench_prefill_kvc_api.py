#!/usr/bin/env python3
"""Two-turn Strict/Continuous Prefill benchmark through the OpenAI API."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--prompt", default="请详细分析缓存式 MoE 推理的性能瓶颈。")
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--follow-up", default="请基于上一轮结论给出三项优先优化。")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument(
        "--second-max-tokens",
        type=int,
        help="Override max_tokens for turn two (useful for Prefill-only probes).",
    )
    parser.add_argument(
        "--policies",
        nargs="+",
        choices=("strict", "session", "persistent"),
        default=("strict", "session"),
    )
    parser.add_argument("--settle-seconds", type=float, default=0.0)
    parser.add_argument(
        "--l1-mode",
        choices=("auto", "off"),
        default="off",
        help="Adaptive L1 request mode (default: off for stable cache A/Bs).",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _diagnostics(args: argparse.Namespace) -> dict[str, Any] | None:
    query = urllib.parse.urlencode({"model": args.model})
    request = urllib.request.Request(
        f"{args.endpoint.rstrip('/')}/v1/ai2apps/diagnostics/prefill?{query}",
        headers=_headers(args.api_key),
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except Exception as exc:  # Benchmark remains useful against older servers.
        return {"unavailable": str(exc)}


def _stream_turn(
    args: argparse.Namespace,
    *,
    session_id: str,
    policy: str,
    messages: list[dict[str, Any]],
    max_tokens: int | None = None,
) -> dict[str, Any]:
    payload = {
        "model": args.model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": 0.0,
        "max_tokens": max_tokens if max_tokens is not None else args.max_tokens,
        "ai2apps_session_id": session_id,
        "ai2apps_l1_mode": args.l1_mode,
        "ai2apps_engine_boost": "natural",
        "ai2apps_kv_policy": policy,
    }
    request = urllib.request.Request(
        f"{args.endpoint.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=_headers(args.api_key),
        method="POST",
    )
    started = time.perf_counter()
    first_token_at: float | None = None
    content: list[str] = []
    reasoning: list[str] = []
    usage: dict[str, Any] = {}
    finish_reason: str | None = None
    with urllib.request.urlopen(request, timeout=60 * 60) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            chunk = json.loads(data)
            if chunk.get("usage"):
                usage = chunk["usage"]
            choices = chunk.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}
            reasoning_piece = delta.get("reasoning_content") or ""
            content_piece = delta.get("content") or ""
            if (reasoning_piece or content_piece) and first_token_at is None:
                first_token_at = time.perf_counter()
            if reasoning_piece:
                reasoning.append(reasoning_piece)
            if content_piece:
                content.append(content_piece)
            finish_reason = choice.get("finish_reason") or finish_reason
    finished = time.perf_counter()
    text = "".join(content)
    reasoning_text = "".join(reasoning)
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    cached_tokens = int(
        (usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
    )
    uncached_tokens = max(0, prompt_tokens - cached_tokens)
    ttft = first_token_at - started if first_token_at is not None else None
    return {
        "prompt_tokens": prompt_tokens,
        "cached_tokens": cached_tokens,
        "uncached_tokens": uncached_tokens,
        "cache_hit_percent": cached_tokens / prompt_tokens * 100.0
        if prompt_tokens
        else 0.0,
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "reported_prefill_tps": usage.get("prompt_tokens_per_second"),
        "ttft_seconds": ttft,
        "wall_seconds": finished - started,
        "finish_reason": finish_reason,
        "text": text,
        "reasoning_content": reasoning_text,
        "output_sha256": hashlib.sha256(
            (reasoning_text + "\0" + text).encode("utf-8")
        ).hexdigest(),
        "diagnostics": _diagnostics(args),
    }


def main() -> None:
    args = _args()
    prompt = (
        args.prompt_file.expanduser().read_text(encoding="utf-8")
        if args.prompt_file
        else args.prompt
    )
    results: dict[str, Any] = {
        "model": args.model,
        "endpoint": args.endpoint,
        "max_tokens": args.max_tokens,
        "policies": {},
    }
    for policy in args.policies:
        session_id = f"prefill-kvc-{policy}-{uuid.uuid4().hex}"
        first_messages = [{"role": "user", "content": prompt}]
        first = _stream_turn(
            args,
            session_id=session_id,
            policy=policy,
            messages=first_messages,
        )
        if args.settle_seconds > 0:
            time.sleep(args.settle_seconds)
        assistant: dict[str, Any] = {
            "role": "assistant",
            "content": first.pop("text"),
        }
        reasoning = first.pop("reasoning_content")
        if reasoning:
            assistant["reasoning_content"] = reasoning
        second_messages = [
            *first_messages,
            assistant,
            {"role": "user", "content": args.follow_up},
        ]
        second = _stream_turn(
            args,
            session_id=session_id,
            policy=policy,
            messages=second_messages,
            max_tokens=args.second_max_tokens,
        )
        second.pop("text")
        second.pop("reasoning_content")
        results["policies"][policy] = {"turn1": first, "turn2": second}

    rendered = json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
