#!/usr/bin/env python3
"""Validate EchoMimic through the durable public video-task service."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import time
from pathlib import Path

from ai2apps.config import PlatformConfig
from ai2apps.packages import TrustStatus
from ai2apps.platform_runtime import PlatformRuntime


async def smoke(args: argparse.Namespace) -> dict:
    os.environ["HF_HUB_CACHE"] = str(args.hf_hub_cache.resolve())
    publisher = json.loads(args.publisher.read_text(encoding="utf-8"))
    runtime = PlatformRuntime(PlatformConfig.from_base_path(args.base_path))
    runtime.start()
    assert runtime.package_repository is not None and runtime.package_manager is not None
    runtime.package_repository.upsert_publisher(
        publisher_key=publisher["publisher_key"],
        display_name=publisher["display_name"],
        key_id=publisher["key_id"],
        public_key=publisher["public_key"],
        trust_status=TrustStatus.TRUSTED,
        source="user",
    )
    started = time.perf_counter()
    try:
        await runtime.start_background_tasks(retention_interval_seconds=3600)
        installed = await runtime.package_manager.install(
            args.model_package,
            dependency_archives=(args.runtime_package,),
            approve_audit_review=True,
        )
        await runtime.package_manager.start(installed.service_key)
        assert runtime.video_tasks is not None
        payload = {
            "model": "ai2apps.model.echomimic-v3-mlx/default",
            "content": [
                {"type": "text", "role": "prompt", "text": args.prompt},
                {
                    "type": "image_url",
                    "role": "reference_image",
                    "image_url": {"url": "multipart://image"},
                },
                {
                    "type": "audio_url",
                    "role": "driving_audio",
                    "audio_url": {"url": "multipart://audio"},
                },
            ],
            "resolution": "512x512",
            "ratio": "1:1",
            "duration": "auto",
            "framespersecond": 25,
            "preset": args.preset,
            "seed": 43,
            "generate_audio": True,
            "output_format": "mp4",
            "metadata": {"acceptance": "echomimic-async-video-v1"},
        }
        created = await runtime.video_tasks.create(
            payload,
            actor_id="local-acceptance",
            idempotency_key=args.idempotency_key,
            uploads={
                "image": (args.image.name, args.image.read_bytes(), "image/png"),
                "audio": (args.audio.name, args.audio.read_bytes(), "audio/wav"),
            },
        )
        deadline = time.monotonic() + args.timeout
        last_progress = None
        while True:
            task = runtime.video_tasks.get(created["id"], actor_id="local-acceptance")
            if task["progress"] != last_progress:
                print(json.dumps({"id": task["id"], "status": task["status"], "progress": task["progress"]}), flush=True)
                last_progress = task["progress"]
            if task["status"] in {"succeeded", "failed", "cancelled"}:
                break
            if time.monotonic() >= deadline:
                await runtime.video_tasks.cancel(task["id"], actor_id="local-acceptance")
                raise TimeoutError("Video task timed out")
            await asyncio.sleep(0.5)
        if task["status"] != "succeeded":
            raise RuntimeError(json.dumps(task, indent=2))
        video = task["result"]["video"]
        artifact = runtime.workspace.get_artifact(
            video["download_url"].split("/")[4], video["artifact_id"]
        )
        source = runtime.workspace.artifact_path(artifact)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, args.output)
        return {
            "task": task,
            "package_digest": installed.package_digest,
            "runtime_lock": [
                {
                    "service": lock.dependency_key,
                    "version": lock.dependency_version,
                    "digest": lock.dependency_digest,
                }
                for lock in runtime.package_repository.locks(installed.package_digest)
            ],
            "bytes": args.output.stat().st_size,
            "total_seconds": time.perf_counter() - started,
            "output": str(args.output),
        }
    finally:
        await runtime.stop_background_tasks()
        runtime.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", required=True, type=Path)
    parser.add_argument("--runtime-package", required=True, type=Path)
    parser.add_argument("--model-package", required=True, type=Path)
    parser.add_argument("--publisher", required=True, type=Path)
    parser.add_argument("--hf-hub-cache", required=True, type=Path)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--prompt", default="A person is speaking naturally.")
    parser.add_argument("--preset", choices=("exact", "fast"), default="fast")
    parser.add_argument("--idempotency-key", default="echomimic-async-acceptance-v1")
    parser.add_argument("--timeout", type=float, default=1800.0)
    args = parser.parse_args()
    report = asyncio.run(smoke(args))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
