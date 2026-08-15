#!/usr/bin/env python3
"""Exercise a real Fusion model across one append-only multi-turn session."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import requests

from omlx.settings import GlobalSettings


BASE_URL = "http://127.0.0.1:8000"


def _headers() -> dict[str, str]:
    api_key = GlobalSettings.load().auth.api_key or ""
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _fusion_model(headers: dict[str, str]) -> str:
    response = requests.get(f"{BASE_URL}/v1/models", headers=headers, timeout=15)
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
    models = [str(item["id"]) for item in response.json().get("data", [])]
    for model in models:
        if model.lower() == "fusion-1":
            return model
    for model in models:
        if "fusion" in model.lower():
            return model
    raise RuntimeError(f"no Fusion model found; available={models}")


def _run_turn(
    *,
    headers: dict[str, str],
    model: str,
    session_id: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "stream_options": {"include_usage": True},
        "max_tokens": int(os.getenv("FUSION_TEST_MAX_TOKENS", "64")),
        "thinking_budget": 0,
        "chat_template_kwargs": {"enable_thinking": False},
        "temperature": 0.0,
        "ai2apps_session_id": session_id,
        "ai2apps_kv_policy": "session",
        "ai2apps_stream_mode": "final",
        "ai2apps_fusion_gate_policy": os.getenv(
            "FUSION_TEST_GATE_POLICY", "always"
        ),
    }
    started = time.monotonic()
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers={**headers, "Content-Type": "application/json"},
        json=payload,
        stream=True,
        timeout=(15, 900),
    )
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
    events: list[dict[str, Any]] = []
    answer_parts: list[str] = []
    usage: dict[str, Any] = {}
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line or not raw_line.startswith("data: "):
            continue
        data = raw_line[6:]
        if data == "[DONE]":
            break
        chunk = json.loads(data)
        if "error" in chunk:
            raise RuntimeError(chunk["error"])
        if chunk.get("usage"):
            usage = dict(chunk["usage"])
        for choice in chunk.get("choices", []):
            delta = choice.get("delta") or {}
            if delta.get("content"):
                answer_parts.append(str(delta["content"]))
            if delta.get("ai2apps"):
                events.append(dict(delta["ai2apps"]))

    review_progress = [
        event.get("metadata") or {}
        for event in events
        if event.get("phase") == "review_progress"
    ]
    review_results = [
        event.get("metadata") or {}
        for event in events
        if event.get("phase") == "review_result"
    ]
    review_errors = [
        event.get("metadata") or {}
        for event in events
        if event.get("phase") == "review_error"
    ]
    prompt_snapshots = [
        item.get("prompt_messages")
        for item in review_progress
        if item.get("prompt_messages")
    ]
    reviewer_prefill = [
        item
        for item in review_progress
        if item.get("stage") == "prefill" and item.get("total")
    ]
    reviewer_generation = [
        item for item in review_progress if item.get("stage") == "generating"
    ]
    prompt_details = usage.get("prompt_tokens_details") or {}
    return {
        "answer": "".join(answer_parts).strip(),
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "generator": {
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "cached_tokens": int(prompt_details.get("cached_tokens") or 0),
            "prompt_eval_seconds": usage.get("prompt_eval_duration"),
            "generation_seconds": usage.get("generation_duration"),
            "generation_tps": usage.get("generation_tokens_per_second"),
        },
        "reviewer": {
            "action": review_results[-1].get("action") if review_results else None,
            "duration_seconds": (
                review_results[-1].get("duration_seconds")
                if review_results
                else None
            ),
            "output_tokens": (
                review_results[-1].get("tokens") if review_results else None
            ),
            "error": review_errors[-1] if review_errors else None,
            "output": (
                review_results[-1].get("output") if review_results else None
            ),
            "decision_retry": any(
                item.get("stage") == "decision_retry" for item in review_progress
            ),
            "prompt_message_count": (
                len(prompt_snapshots[-1]) if prompt_snapshots else None
            ),
            "prompt_roles": (
                [message.get("role") for message in prompt_snapshots[-1]]
                if prompt_snapshots
                else []
            ),
            "prefill_processed": max(
                (int(item.get("processed") or 0) for item in reviewer_prefill),
                default=0,
            ),
            "prefill_total": max(
                (int(item.get("total") or 0) for item in reviewer_prefill),
                default=0,
            ),
            "reported_prompt_tokens": max(
                (int(item.get("prompt_tokens") or 0) for item in reviewer_generation),
                default=0,
            ),
        },
        "phases": list(dict.fromkeys(event.get("phase") for event in events)),
    }


def main() -> None:
    headers = _headers()
    model = _fusion_model(headers)
    session_id = f"fusion-live-{uuid.uuid4().hex[:12]}"
    prompts = [
        "记住暗号 ORCHID-731。只回复：已记住。",
        "刚才的暗号是什么？只回复暗号。",
        "计算 17×23，只回复数字。",
        "把第一轮暗号和上一轮计算结果用“暗号|结果”的格式回复。",
    ]
    if os.getenv("FUSION_TEST_QUICK"):
        prompts = prompts[:2]
    messages: list[dict[str, str]] = []
    turns: list[dict[str, Any]] = []
    for index, prompt in enumerate(prompts, start=1):
        messages.append({"role": "user", "content": prompt})
        result = _run_turn(
            headers=headers,
            model=model,
            session_id=session_id,
            messages=messages,
        )
        turns.append({"turn": index, "prompt": prompt, **result})
        messages.append({"role": "assistant", "content": result["answer"]})
        print(json.dumps(turns[-1], ensure_ascii=False), flush=True)
        turn_delay = float(os.getenv("FUSION_TEST_TURN_DELAY", "0"))
        if turn_delay > 0 and index < len(prompts):
            time.sleep(turn_delay)

    generator_hits = [turn["generator"]["cached_tokens"] for turn in turns]
    reviewer_messages = [turn["reviewer"]["prompt_message_count"] for turn in turns]
    summary = {
        "model": model,
        "session_id": session_id,
        "generator_cached_tokens": generator_hits,
        "reviewer_prompt_message_counts": reviewer_messages,
        "all_reviews_passed": all(
            str(turn["reviewer"]["action"]).upper() == "PASS" for turn in turns
        ),
        "semantic_checks": {
            "turn_2_codeword": len(turns) < 2
            or "ORCHID-731" in turns[1]["answer"],
            "turn_3_product": len(turns) < 3 or "391" in turns[2]["answer"],
            "turn_4_combined": len(turns) < 4
            or (
                "ORCHID-731" in turns[3]["answer"]
                and "391" in turns[3]["answer"]
            ),
        },
    }
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
