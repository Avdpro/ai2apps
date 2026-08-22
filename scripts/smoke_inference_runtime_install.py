#!/usr/bin/env python3
"""Install a development Runtime + Model dependency pair and start its Worker."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from ai2apps.config import PlatformConfig
from ai2apps.packages import TrustStatus
from ai2apps.platform_runtime import PlatformRuntime


async def smoke(base_path: Path, runtime_archive: Path, model_archive: Path) -> dict:
    os.environ["AI2APPS_ALLOW_DEVELOPMENT_RUNTIME"] = "1"
    runtime = PlatformRuntime(PlatformConfig.from_base_path(base_path))
    runtime.start()
    assert runtime.package_manager is not None
    assert runtime.package_repository is not None
    manager = runtime.package_manager
    sidecar = json.loads(
        runtime_archive.with_suffix(runtime_archive.suffix + ".publisher.json").read_text(
            encoding="utf-8"
        )
    )
    runtime.package_repository.upsert_publisher(
        publisher_key=sidecar["publisher_key"],
        display_name=sidecar["display_name"],
        key_id=sidecar["key_id"],
        public_key=sidecar["public_key"],
        trust_status=TrustStatus.TRUSTED,
        source="user",
    )
    try:
        installed = await manager.install(
            model_archive,
            dependency_archives=(runtime_archive,),
            approve_audit_review=True,
        )
        provider = runtime.package_repository.active("ai2apps.runtime.omlx")
        assert provider is not None
        model = runtime.package_repository.active(installed.service_key)
        assert model is not None
        locks = runtime.package_repository.locks(model.package_digest)
        resolved = manager.inference_runtime_resolver.resolve(model)
        service = runtime.services.get_service(model.service_key)
        instance = runtime.services.get_instance_for_service(service.id)
        return {
            "runtime": {
                "service": provider.service_key,
                "version": provider.package_version,
                "digest": provider.package_digest,
                "root": str(resolved.root),
                "python": str(resolved.python),
            },
            "model": {
                "service": model.service_key,
                "version": model.package_version,
                "digest": model.package_digest,
                "status": instance.status.value,
                "endpoint": instance.endpoint,
            },
            "locks": [
                {
                    "dependency": item.dependency_key,
                    "version": item.dependency_version,
                    "digest": item.dependency_digest,
                }
                for item in locks
            ],
        }
    finally:
        await manager.runtime.shutdown()
        runtime.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()
    report = asyncio.run(
        smoke(
            args.base_path.resolve(),
            args.runtime.resolve(strict=True),
            args.model.resolve(strict=True),
        )
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
