#!/usr/bin/env python3
"""Install the Qwen3.5 package into an isolated runtime and run one request."""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

import httpx

from ai2apps.config import PlatformConfig
from ai2apps.model_providers import list_package_models
from ai2apps.packages import TrustStatus
from ai2apps.platform_runtime import PlatformRuntime


async def smoke(artifact: Path, publisher_path: Path, repository: str) -> dict:
    publisher = json.loads(publisher_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="ai2apps-qwen35-smoke-") as temporary:
        runtime = PlatformRuntime(PlatformConfig.from_base_path(Path(temporary)))
        runtime.start()
        assert runtime.package_repository is not None
        assert runtime.package_manager is not None
        runtime.package_repository.upsert_publisher(
            publisher_key=publisher["publisher_key"],
            display_name=publisher["display_name"],
            key_id=publisher["key_id"],
            public_key=publisher["public_key"],
            trust_status=TrustStatus.TRUSTED,
            source="user",
        )
        try:
            try:
                installed = await runtime.package_manager.install(
                    artifact,
                    approve_audit_review=True,
                )
            except Exception as exc:
                logs = runtime.package_repository.logs("ai2apps.qwen35", limit=200)
                raise RuntimeError(
                    f"Package activation failed: {exc}\n"
                    + "\n".join(f"[{item['stream']}] {item['message']}" for item in logs)
                ) from exc
            catalog = list_package_models(runtime)
            selected = next(item for item in catalog if item.upstream_id == repository)
            async with httpx.AsyncClient(timeout=180, trust_env=False) as client:
                try:
                    response = await client.post(
                        selected.endpoint + "/v1/chat/completions",
                        json={
                            "model": repository,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": "Reply with exactly two words: package works",
                                }
                            ],
                            "max_tokens": 16,
                            "temperature": 0,
                        },
                    )
                except Exception as exc:
                    await asyncio.sleep(0.25)
                    logs = runtime.package_repository.logs("ai2apps.qwen35", limit=200)
                    raise RuntimeError(
                        f"Provider connection failed: {exc}\n"
                        + "\n".join(
                            f"[{item['stream']}] {item['message']}" for item in logs
                        )
                    ) from exc
                if response.is_error:
                    await asyncio.sleep(0.25)
                    logs = runtime.package_repository.logs("ai2apps.qwen35", limit=200)
                    raise RuntimeError(
                        f"Provider returned HTTP {response.status_code}: {response.text}\n"
                        + "\n".join(
                            f"[{item['stream']}] {item['message']}" for item in logs
                        )
                    )
                result = response.json()
            return {
                "service": installed.service_key,
                "digest": installed.package_digest,
                "catalog_models": [item.id for item in catalog],
                "selected_model": selected.id,
                "response": result["choices"][0]["message"]["content"],
                "usage": result.get("usage"),
            }
        finally:
            await runtime.package_manager.shutdown()
            runtime.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "artifact",
        type=Path,
        nargs="?",
        default=Path("packages/qwen35-provider/dist/ai2apps.qwen35-0.1.0.ai2service"),
    )
    parser.add_argument("--publisher", type=Path)
    parser.add_argument(
        "--repository",
        default="mlx-community/Qwen3.5-0.8B-4bit",
    )
    args = parser.parse_args()
    publisher = args.publisher or args.artifact.with_suffix(
        args.artifact.suffix + ".publisher.json"
    )
    print(
        json.dumps(
            asyncio.run(smoke(args.artifact.resolve(), publisher.resolve(), args.repository)),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
