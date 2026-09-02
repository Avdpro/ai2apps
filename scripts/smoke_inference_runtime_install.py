#!/usr/bin/env python3
"""Install a development Runtime + Model dependency pair and start its Worker."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from ai2apps.config import PlatformConfig
from ai2apps.packages import TrustStatus
from ai2apps.packages.contract_v1 import verify_signed_package
from ai2apps.packages.registry import RegistryPackageManager
from ai2apps.platform_runtime import PlatformRuntime


def _smoke_multipart_limit(endpoint: str, headers: dict[str, str]) -> dict:
    boundary = "ai2apps-ref2va-" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in (
        ("model", "ai2apps.model.minimax-h3/ref2va-4bit"),
        ("prompt", "transport smoke"),
    ):
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    for index in range(12):
        chunks.append(
            (
                f"--{boundary}\r\nContent-Disposition: form-data; "
                f"name=\"reference_{index:02d}_image\"; filename=\"ref-{index}.png\"\r\n"
                "Content-Type: image/png\r\n\r\n"
            ).encode()
        )
        chunks.extend((b"not-decoded-before-checkpoint-gate", b"\r\n"))
    chunks.append(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/v1/videos/generations",
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", **headers},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as error:
        response = json.loads(error.read())
        code = response.get("error", {}).get("code")
        if error.code != 503 or code != "model_unavailable":
            raise RuntimeError(
                f"Twelve-part request was rejected before the adapter: {error.code} {response}"
            ) from error
        return {"parts": 12, "adapter_error": code, "status": error.code}
    raise RuntimeError("Transport smoke unexpectedly started inference without a checkpoint")


async def smoke(
    base_path: Path,
    runtime_archive: Path,
    model_archive: Path,
    *,
    multipart_limit: bool = False,
    runtime_envelope: Path | None = None,
    model_envelope: Path | None = None,
    publisher_public_key: str | None = None,
) -> dict:
    os.environ["AI2APPS_ALLOW_DEVELOPMENT_RUNTIME"] = "1"
    runtime = PlatformRuntime(PlatformConfig.from_base_path(base_path))
    runtime.start()
    assert runtime.package_manager is not None
    assert runtime.package_repository is not None
    manager = runtime.package_manager
    cloud_contract = runtime_envelope is not None or model_envelope is not None
    if cloud_contract:
        if runtime_envelope is None or model_envelope is None or not publisher_public_key:
            raise ValueError(
                "Cloud Contract smoke requires both envelopes and the publisher public key"
            )
        registry = RegistryPackageManager(
            cloud=None,
            root=base_path / "packages",
            secrets=None,
            extension_manager=None,
            service_manager=manager,
        )

        def verified_bundle(artifact: Path, envelope_path: Path):
            envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
            inspected = verify_signed_package(
                artifact, envelope, publisher_public_key
            )
            return registry._service_bundle(inspected, envelope), envelope

        runtime_bundle, runtime_signature = verified_bundle(
            runtime_archive, runtime_envelope
        )
        model_bundle, model_signature = verified_bundle(model_archive, model_envelope)
        publisher_key = runtime_bundle.manifest.publisher_key
        runtime.package_repository.upsert_publisher(
            publisher_key=publisher_key,
            display_name="AI2Apps",
            key_id=runtime_signature["payload"]["publisherKeyId"],
            public_key=publisher_public_key,
            trust_status=TrustStatus.TRUSTED,
            source="organization",
            metadata={"trust": "ai2apps-cloud-registry-v1"},
        )
    else:
        sidecar = json.loads(
            runtime_archive.with_suffix(
                runtime_archive.suffix + ".publisher.json"
            ).read_text(encoding="utf-8")
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
        if cloud_contract:
            await manager.install_verified_package(
                runtime_bundle,
                {
                    **runtime_signature["signature"],
                    "trust": "ai2apps-cloud-registry-v1",
                },
                approve_audit_review=True,
            )
            await manager.runtime.shutdown()
            runtime.stop()
            runtime = PlatformRuntime(PlatformConfig.from_base_path(base_path))
            runtime.start()
            await runtime.start_background_tasks()
            assert runtime.package_manager is not None
            assert runtime.package_repository is not None
            manager = runtime.package_manager
            installed = await manager.install_verified_package(
                model_bundle,
                {
                    **model_signature["signature"],
                    "trust": "ai2apps-cloud-registry-v1",
                },
                approve_audit_review=True,
            )
        else:
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
        report = {
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
        if multipart_limit:
            headers = manager.supervisor.internal_headers(model.service_key)
            if headers is None:
                raise RuntimeError("Installed Model Worker has no internal authentication headers")
            report["multipart"] = await asyncio.to_thread(
                _smoke_multipart_limit, instance.endpoint, headers
            )
        return report
    finally:
        await runtime.stop_background_tasks()
        runtime.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--multipart-limit", action="store_true")
    parser.add_argument("--runtime-envelope", type=Path)
    parser.add_argument("--model-envelope", type=Path)
    parser.add_argument(
        "--publisher-sidecar",
        type=Path,
        help="JSON sidecar containing the public_key PEM (never a private key)",
    )
    args = parser.parse_args()
    publisher_public_key = None
    if args.publisher_sidecar is not None:
        publisher_public_key = json.loads(
            args.publisher_sidecar.resolve(strict=True).read_text(encoding="utf-8")
        )["public_key"]
    report = asyncio.run(
        smoke(
            args.base_path.resolve(),
            args.runtime.resolve(strict=True),
            args.model.resolve(strict=True),
            multipart_limit=args.multipart_limit,
            runtime_envelope=(
                None
                if args.runtime_envelope is None
                else args.runtime_envelope.resolve(strict=True)
            ),
            model_envelope=(
                None
                if args.model_envelope is None
                else args.model_envelope.resolve(strict=True)
            ),
            publisher_public_key=publisher_public_key,
        )
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
