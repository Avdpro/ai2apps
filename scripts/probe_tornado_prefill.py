#!/usr/bin/env python3
"""Time-boxed replay of the local WebUI tornado conversation Prefill."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


TORNADO_SESSION = "ses_de4971036ec042d996bc247c7148de04"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--model", default="CachedMOE-DSV4F")
    parser.add_argument("--seconds", type=float, default=240.0)
    parser.add_argument("--poll-seconds", type=float, default=10.0)
    parser.add_argument(
        "--boost", choices=("natural", "turbo", "blast"), default="natural"
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _messages(database: Path) -> list[dict[str, Any]]:
    uri = f"file:{database.expanduser()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            """
            SELECT m.sequence, m.role, m.metadata_json, mp.content_json
            FROM messages AS m
            JOIN message_parts AS mp ON mp.message_id = m.id
            WHERE m.session_id = ? AND m.sequence <= 3
              AND mp.kind = 'chat_ui_content'
            ORDER BY m.sequence, mp.position
            """,
            (TORNADO_SESSION,),
        ).fetchall()
    messages = []
    for _sequence, role, metadata_raw, content_raw in rows:
        content = json.loads(content_raw).get("content", "")
        item: dict[str, Any] = {"role": role, "content": content}
        if role == "assistant":
            metadata = json.loads(metadata_raw)
            reasoning = metadata.get("reasoning_content") or metadata.get("_thinking")
            if reasoning:
                item["reasoning_content"] = reasoning
        messages.append(item)
    if [item["role"] for item in messages] != ["user", "assistant", "user"]:
        raise RuntimeError("unexpected tornado conversation shape")
    return messages


def _headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _diagnostics(args: argparse.Namespace) -> dict[str, Any]:
    query = urllib.parse.urlencode({"model": args.model})
    request = urllib.request.Request(
        f"{args.endpoint.rstrip('/')}/v1/ai2apps/diagnostics/prefill?{query}",
        headers=_headers(args.api_key),
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def _sample(started: float, payload: dict[str, Any]) -> dict[str, Any]:
    cache_moe = payload.get("cache_moe") or {}
    store = cache_moe.get("expert_store") or {}
    adaptive = cache_moe.get("adaptive_l1") or {}
    prefill_l1 = cache_moe.get("prefill_adaptive_l1") or {}
    return {
        "elapsed_seconds": time.perf_counter() - started,
        "process_physical_bytes": payload.get("process_physical_bytes"),
        "experts_loaded": store.get("experts_loaded"),
        "transient_experts_loaded": store.get("transient_experts_loaded"),
        "bytes_loaded": store.get("bytes_loaded"),
        "load_seconds": store.get("load_seconds"),
        "prefetch_requests": store.get("prefetch_requests"),
        "prefetch_hits": store.get("prefetch_hits"),
        "prefetch_bytes": store.get("prefetch_bytes"),
        "prefetch_read_seconds": store.get("prefetch_read_seconds"),
        "prefetch_wait_seconds": store.get("prefetch_wait_seconds"),
        "lossy_routes_replaced": store.get("lossy_routes_replaced"),
        "lossy_l3_misses_before": store.get("lossy_l3_misses_before"),
        "lossy_l3_misses_after": store.get("lossy_l3_misses_after"),
        "lossy_l3_misses_avoided": store.get("lossy_l3_misses_avoided"),
        "route_telemetry_records": store.get("route_telemetry_records"),
        "route_telemetry_drains": store.get("route_telemetry_drains"),
        "l1_patch_calls": store.get("l1_patch_calls"),
        "l1_patch_slots": store.get("l1_patch_slots"),
        "l1_patch_seconds": store.get("l1_patch_seconds"),
        "prefill_l1": prefill_l1,
        "adaptive_l1": adaptive,
    }


def main() -> None:
    args = _args()
    messages = _messages(args.database)
    session_id = f"tornado-prefill-probe-{uuid.uuid4().hex}"
    payload = {
        "model": args.model,
        "messages": messages,
        "stream": True,
        "temperature": 0.0,
        "max_tokens": 1,
        "ai2apps_session_id": session_id,
        "ai2apps_l1_mode": "auto",
        "ai2apps_engine_boost": args.boost,
        "ai2apps_kv_policy": "session",
    }
    curl_args = [
        "curl",
        "--no-buffer",
        "--silent",
        "--show-error",
        "--request",
        "POST",
        f"{args.endpoint.rstrip('/')}/v1/chat/completions",
        "--header",
        "Content-Type: application/json",
    ]
    if args.api_key:
        curl_args += ["--header", f"Authorization: Bearer {args.api_key}"]
    curl_args += ["--data-binary", "@-"]
    process = subprocess.Popen(
        curl_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdin is not None
    process.stdin.write(json.dumps(payload, ensure_ascii=False))
    process.stdin.close()

    started = time.perf_counter()
    samples: list[dict[str, Any]] = []
    deadline = started + args.seconds
    while process.poll() is None and time.perf_counter() < deadline:
        time.sleep(min(args.poll_seconds, max(0.0, deadline - time.perf_counter())))
        try:
            samples.append(_sample(started, _diagnostics(args)))
        except Exception as exc:
            samples.append(
                {"elapsed_seconds": time.perf_counter() - started, "error": str(exc)}
            )

    timed_out = process.poll() is None
    if timed_out:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    try:
        samples.append(_sample(started, _diagnostics(args)))
    except Exception as exc:
        samples.append({"elapsed_seconds": time.perf_counter() - started, "error": str(exc)})
    stderr = process.stderr.read() if process.stderr is not None else ""
    result = {
        "source_session_id": TORNADO_SESSION,
        "probe_session_id": session_id,
        "message_roles": [item["role"] for item in messages],
        "message_characters": [len(item.get("content", "")) for item in messages],
        "reasoning_characters": [len(item.get("reasoning_content", "")) for item in messages],
        "configured_seconds": args.seconds,
        "boost": args.boost,
        "elapsed_seconds": time.perf_counter() - started,
        "timed_out": timed_out,
        "curl_returncode": process.returncode,
        "curl_stderr": stderr,
        "samples": samples,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
