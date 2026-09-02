#!/usr/bin/env python3
"""Install EchoMimic and its Runtime into an isolated Host, then invoke it."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import httpx

from ai2apps.config import PlatformConfig
from ai2apps.model_providers import list_package_models
from ai2apps.packages import TrustStatus
from ai2apps.platform_runtime import PlatformRuntime


async def smoke(args: argparse.Namespace) -> dict:
    if args.hf_hub_cache is not None:
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
        installed = await runtime.package_manager.install(
            args.model_package,
            dependency_archives=(args.runtime_package,),
            approve_audit_review=True,
        )
        await runtime.package_manager.start(installed.service_key)
        model = next(
            item for item in list_package_models(runtime)
            if item.id == "ai2apps.model.echomimic-v3-mlx/default"
        )
        request_started = time.perf_counter()
        async with httpx.AsyncClient(timeout=args.timeout, trust_env=False) as client:
            with args.image.open("rb") as image, args.audio.open("rb") as audio:
                response = await client.post(
                    model.endpoint + "/v1/videos/generations",
                    data={
                        "model": model.upstream_id,
                        "prompt": args.prompt,
                        "width": str(args.width),
                        "height": str(args.height),
                        "preset": args.preset,
                        "long": "true" if args.long else "false",
                    },
                    files={
                        "image": (args.image.name, image, "image/png"),
                        "audio": (args.audio.name, audio, "audio/wav"),
                    },
                    headers=dict(model.internal_headers or {}),
                )
        request_seconds = time.perf_counter() - request_started
        if response.is_error:
            logs = runtime.package_repository.logs(installed.service_key, limit=300)
            detail = "\n".join(f"[{item['stream']}] {item['message']}" for item in logs)
            raise RuntimeError(
                f"EchoMimic Worker returned HTTP {response.status_code}: {response.text}\n{detail}"
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(response.content)
        return {
            "service": installed.service_key,
            "package_version": installed.package_version,
            "package_digest": installed.package_digest,
            "runtime_lock": [
                {"service": lock.dependency_key, "version": lock.dependency_version,
                 "digest": lock.dependency_digest}
                for lock in runtime.package_repository.locks(installed.package_digest)
            ],
            "http_status": response.status_code,
            "content_type": response.headers.get("content-type"),
            "response_bytes": len(response.content),
            "request_seconds": request_seconds,
            "total_seconds": time.perf_counter() - started,
            "output": str(args.output),
        }
    finally:
        await runtime.package_manager.shutdown()
        runtime.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", required=True, type=Path)
    parser.add_argument("--runtime-package", required=True, type=Path)
    parser.add_argument("--model-package", required=True, type=Path)
    parser.add_argument("--publisher", required=True, type=Path)
    parser.add_argument(
        "--hf-hub-cache", type=Path,
        help="Hugging Face hub containing the package's exact pinned snapshot",
    )
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--prompt", default="A person is speaking naturally.")
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--preset", choices=("exact", "fast"), default="exact")
    parser.add_argument("--long", action="store_true")
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()
    report = asyncio.run(smoke(args))
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
