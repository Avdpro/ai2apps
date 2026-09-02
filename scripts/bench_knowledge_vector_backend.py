#!/usr/bin/env python3
"""Run the reproducible AI2Apps LanceDB Knowledge backend spike."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import statistics
import tempfile
import time
from pathlib import Path

from ai2apps.knowledge.backends.lancedb import LanceDBVectorBackend
from ai2apps.knowledge.backends.protocol import (
    VectorBackendError,
    VectorRecord,
    VectorSearchRequest,
)


def _vector(key: str, dimension: int) -> tuple[float, ...]:
    values: list[float] = []
    counter = 0
    while len(values) < dimension:
        digest = hashlib.sha256(f"{key}:{counter}".encode()).digest()
        values.extend((byte - 127.5) / 127.5 for byte in digest)
        counter += 1
    selected = values[:dimension]
    norm = math.sqrt(sum(value * value for value in selected)) or 1.0
    return tuple(value / norm for value in selected)


def _records(count: int, dimension: int) -> tuple[VectorRecord, ...]:
    return tuple(
        VectorRecord(
            chunk_id=f"chunk-{index:09d}",
            item_id=f"item-{index:09d}",
            installation_id="installation-a" if index % 10 else "installation-b",
            owner_user_id=f"user-{index % 4}",
            visibility="installation" if index % 3 == 0 else "private",
            bucket_ids=(f"bucket-{index % 8}",),
            text=f"Synthetic knowledge chunk {index}",
            vector=_vector(f"chunk-{index:09d}", dimension),
        )
        for index in range(count)
    )


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = min(len(ordered) - 1, math.ceil(len(ordered) * percentile) - 1)
    return ordered[position]


def run_spike(
    root: Path,
    *,
    count: int,
    dimension: int,
    query_count: int,
    batch_size: int,
) -> dict:
    started = time.perf_counter()
    try:
        version = importlib.metadata.version("lancedb")
    except importlib.metadata.PackageNotFoundError:
        version = None
    result = {
        "schema": "ai2apps.knowledge-vector-spike/v1",
        "backend": "lancedb",
        "backend_version": version,
        "platform": {
            "system": platform.system().lower(),
            "machine": platform.machine().lower(),
            "python": platform.python_version(),
        },
        "parameters": {
            "chunks": count,
            "dimension": dimension,
            "queries": query_count,
            "batch_size": batch_size,
        },
    }
    if version is None:
        result.update(
            status="unavailable",
            error="LanceDB is not installed in this isolated spike environment",
        )
        return result

    backend = LanceDBVectorBackend(
        root,
        generation="spike_active",
        dimension=dimension,
    )
    records = _records(count, dimension)
    build_started = time.perf_counter()
    try:
        for offset in range(0, len(records), batch_size):
            backend.upsert(records[offset : offset + batch_size])
        build_seconds = time.perf_counter() - build_started
        latencies = []
        visible_ids: list[str] = []
        for index in range(query_count):
            query_started = time.perf_counter()
            hits = backend.search(
                VectorSearchRequest(
                    vector=records[(index * 17) % len(records)].vector,
                    installation_id="installation-a",
                    actor_user_id="user-1",
                    bucket_ids=(f"bucket-{index % 8}",),
                    limit=20,
                )
            )
            latencies.append((time.perf_counter() - query_started) * 1000)
            visible_ids.extend(hit.item_id for hit in hits)
        delete_ids = tuple(record.item_id for record in records[: min(100, count)])
        delete_started = time.perf_counter()
        backend.delete_items(delete_ids)
        delete_seconds = time.perf_counter() - delete_started
        restarted = LanceDBVectorBackend(
            root,
            generation="spike_active",
            dimension=dimension,
        )
        result.update(
            status="passed",
            metrics={
                "build_seconds": build_seconds,
                "chunks_per_second": count / build_seconds if build_seconds else 0.0,
                "query_p50_ms": statistics.median(latencies) if latencies else 0.0,
                "query_p95_ms": _percentile(latencies, 0.95),
                "delete_seconds": delete_seconds,
                "count_after_delete": restarted.count(),
                "returned_candidates": len(visible_ids),
                "elapsed_seconds": time.perf_counter() - started,
            },
        )
    except (VectorBackendError, ValueError) as error:
        result.update(status="failed", error=str(error))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--chunks", type=int, default=10_000)
    parser.add_argument("--dimension", type=int, default=384)
    parser.add_argument("--queries", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=1_000)
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero when LanceDB is absent or the spike fails.",
    )
    arguments = parser.parse_args()
    if arguments.chunks < 1 or arguments.dimension < 1 or arguments.queries < 1:
        parser.error("chunks, dimension and queries must be positive")
    if arguments.root is None:
        with tempfile.TemporaryDirectory(prefix="ai2apps-lancedb-spike-") as value:
            result = run_spike(
                Path(value),
                count=arguments.chunks,
                dimension=arguments.dimension,
                query_count=arguments.queries,
                batch_size=arguments.batch_size,
            )
    else:
        result = run_spike(
            arguments.root,
            count=arguments.chunks,
            dimension=arguments.dimension,
            query_count=arguments.queries,
            batch_size=arguments.batch_size,
        )
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(payload, encoding="utf-8")
    return int(arguments.require_ready and result["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
