#!/usr/bin/env python3
"""Install a development Runtime + Model dependency pair and start its Worker."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ai2apps.checkpoint_acquisition import CheckpointAcquisitionService
from ai2apps.checkpoint_distribution import CheckpointCache
from ai2apps.checkpoint_registry import CheckpointRegistryClient
from ai2apps.config import PlatformConfig
from ai2apps.model_providers import installed_model_preparation_recipes
from ai2apps.packages import TrustStatus
from ai2apps.packages.contract_v1 import verify_signed_package
from ai2apps.packages.registry import RegistryPackageManager
from ai2apps.packages.supervisor import ManagedServiceSupervisor
from ai2apps.platform_runtime import PlatformRuntime


def _publisher_public_key(value: str) -> str:
    if "-----BEGIN PUBLIC KEY-----" in value:
        return value
    raw = base64.b64decode(value, validate=True)
    return Ed25519PublicKey.from_public_bytes(raw).public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def _smoke_detailed_audio(
    endpoint: str,
    headers: dict[str, str],
    model: str,
    audio_path: Path,
    language: str,
) -> dict:
    boundary = "ai2apps-detailed-" + uuid.uuid4().hex
    media_type = mimetypes.guess_type(audio_path.name)[0] or "audio/wav"
    fields = (
        ("model", model),
        ("language", language),
        ("timestamps", "word"),
        ("diarization", "false"),
    )
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    chunks.append(
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"{audio_path.name}\"\r\nContent-Type: {media_type}\r\n\r\n"
        ).encode()
    )
    chunks.extend((audio_path.read_bytes(), b"\r\n", f"--{boundary}--\r\n".encode()))
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/v1/audio/transcriptions/detailed",
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Detailed transcription smoke failed ({error.code}): {detail}"
        ) from error


def _smoke_audio_process(
    endpoint: str,
    headers: dict[str, str],
    model: str,
    audio_path: Path,
    profile: str,
    output_path: Path,
) -> dict:
    boundary = "ai2apps-audio-process-" + uuid.uuid4().hex
    media_type = mimetypes.guess_type(audio_path.name)[0] or "audio/wav"
    chunks: list[bytes] = []
    for name, value in (
        ("model", model),
        ("task", "source_separation"),
        ("profile", profile),
    ):
        chunks.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    chunks.append(
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"{audio_path.name}\"\r\nContent-Type: {media_type}\r\n\r\n"
        ).encode()
    )
    chunks.extend((audio_path.read_bytes(), b"\r\n", f"--{boundary}--\r\n".encode()))
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/v1/audio/process",
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            content = response.read()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(content)
            return {
                "status": response.status,
                "media_type": response.headers.get_content_type(),
                "bytes": len(content),
                "output": str(output_path),
            }
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Audio processing smoke failed ({error.code}): {detail}"
        ) from error


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


def _smoke_long_audio_limit(endpoint: str, headers: dict[str, str]) -> dict:
    """Exercise installed Worker transport without downloading model weights."""
    import io
    import wave
    import httpx
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(48000)
        for _ in range(1369):
            wav.writeframesraw(b"\x00" * 96000)
    audio = output.getvalue()
    response = httpx.post(endpoint.rstrip("/") + "/v1/audio/process",
        headers=headers, timeout=120,
        data={"model": "ai2apps.model.demucs-mlx/default", "profile": "vocals_instrumental"},
        files={"file": ("episode.wav", audio, "audio/wav")})
    if response.status_code == 200:
        import zipfile
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = archive.namelist()
            if archive.testzip() is not None or not any(name.endswith(".wav") for name in names):
                raise RuntimeError("Long audio returned an invalid separation archive")
        return {"bytes": len(audio), "seconds": 1369, "transportAccepted": True,
                "inferenceSucceeded": True, "artifactBytes": len(response.content), "files": names}
    body = response.json()
    code = body.get("error", {}).get("code")
    if response.status_code != 503 or code != "model_unavailable":
        raise RuntimeError(f"Long audio did not reach checkpoint gate: {response.status_code} {body}")
    return {"bytes": len(audio), "seconds": 1369, "adapter_error": code,
            "transportAccepted": True}


async def _prepare_checkpoint_distributions(runtime, model_ids: set[str]) -> list[dict]:
    registry_packages = runtime.registry_packages
    registry_root = registry_packages.root.parent
    acquisition = CheckpointAcquisitionService(
        registry=CheckpointRegistryClient(
            cloud=registry_packages.cloud,
            root=registry_root,
            repository_fingerprint=registry_packages.repository_fingerprint,
        ),
        cache=CheckpointCache(registry_root / "checkpoint-cache-v1"),
    )
    recipes = {
        item["id"]: item for item in installed_model_preparation_recipes(runtime)
    }
    report = []
    for model_id in sorted(model_ids):
        recipe = recipes.get(model_id)
        if recipe is None or not recipe.get("distribution_id"):
            raise RuntimeError(f"No checkpoint distribution recipe for {model_id}")
        acquired = await acquisition.acquire(recipe["distribution_id"])
        snapshot = await asyncio.to_thread(
            acquisition.materialize_worker_snapshot,
            acquired,
            ManagedServiceSupervisor._huggingface_hub_cache(),
        )
        report.append(
            {
                "model": model_id,
                "distribution": recipe["distribution_id"],
                "cache_hit": acquired.cache_hit,
                "source_bytes": acquired.source_bytes,
                "snapshot": str(snapshot),
            }
        )
    return report


async def smoke(
    base_path: Path,
    runtime_archive: Path,
    model_archive: Path,
    *,
    multipart_limit: bool = False,
    long_audio_limit: bool = False,
    runtime_envelope: Path | None = None,
    model_envelope: Path | None = None,
    publisher_public_key: str | None = None,
    model_publisher_public_key: str | None = None,
    detailed_audio: tuple[tuple[str, Path, str], ...] = (),
    process_audio: tuple[tuple[str, Path, str, Path], ...] = (),
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

        def verified_bundle(artifact: Path, envelope_path: Path, public_key: str):
            envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
            inspected = verify_signed_package(
                artifact, envelope, public_key
            )
            return registry._service_bundle(inspected, envelope), envelope

        runtime_bundle, runtime_signature = verified_bundle(
            runtime_archive, runtime_envelope, publisher_public_key
        )
        model_key = model_publisher_public_key or publisher_public_key
        model_bundle, model_signature = verified_bundle(model_archive, model_envelope, model_key)
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
        runtime.package_repository.upsert_publisher(
            publisher_key=model_bundle.manifest.publisher_key,
            display_name="AI2Apps",
            key_id=model_signature["payload"]["publisherKeyId"],
            public_key=model_key,
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
        checkpoint_report = []
        if process_audio:
            checkpoint_report = await _prepare_checkpoint_distributions(
                runtime, {item[0] for item in process_audio}
            )
            await manager.restart(installed.service_key)
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
            "checkpoints": checkpoint_report,
        }
        if multipart_limit:
            headers = manager.supervisor.internal_headers(model.service_key)
            if headers is None:
                raise RuntimeError("Installed Model Worker has no internal authentication headers")
            report["multipart"] = await asyncio.to_thread(
                _smoke_multipart_limit, instance.endpoint, headers
            )
        if long_audio_limit:
            headers = manager.supervisor.internal_headers(model.service_key)
            if headers is None:
                raise RuntimeError("Installed Model Worker has no authentication headers")
            report["long_audio"] = await asyncio.to_thread(
                _smoke_long_audio_limit, instance.endpoint, headers)
        if detailed_audio:
            headers = manager.supervisor.internal_headers(model.service_key)
            if headers is None:
                raise RuntimeError("Installed Model Worker has no internal authentication headers")
            report["detailed_audio"] = []
            for model_id, audio_path, language in detailed_audio:
                value = await asyncio.to_thread(
                    _smoke_detailed_audio,
                    instance.endpoint,
                    headers,
                    model_id,
                    audio_path,
                    language,
                )
                report["detailed_audio"].append(
                    {
                        "model": model_id,
                        "audio": str(audio_path),
                        "language": language,
                        "result": value,
                    }
                )
        if process_audio:
            headers = manager.supervisor.internal_headers(model.service_key)
            if headers is None:
                raise RuntimeError("Installed Model Worker has no internal authentication headers")
            report["process_audio"] = []
            for model_id, audio_path, profile, output_path in process_audio:
                value = await asyncio.to_thread(
                    _smoke_audio_process,
                    instance.endpoint,
                    headers,
                    model_id,
                    audio_path,
                    profile,
                    output_path,
                )
                report["process_audio"].append(
                    {
                        "model": model_id,
                        "audio": str(audio_path),
                        "profile": profile,
                        "result": value,
                    }
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
    parser.add_argument("--long-audio-limit", action="store_true")
    parser.add_argument("--runtime-envelope", type=Path)
    parser.add_argument("--model-envelope", type=Path)
    parser.add_argument(
        "--detailed-audio",
        action="append",
        nargs=3,
        metavar=("MODEL_ID", "AUDIO_PATH", "LANGUAGE"),
        default=[],
    )
    parser.add_argument(
        "--process-audio",
        action="append",
        nargs=4,
        metavar=("MODEL_ID", "AUDIO_PATH", "PROFILE", "OUTPUT_PATH"),
        default=[],
    )
    parser.add_argument(
        "--publisher-sidecar",
        type=Path,
        help="JSON sidecar containing the public_key PEM (never a private key)",
    )
    parser.add_argument("--model-publisher-sidecar", type=Path,
                        help="Optional distinct public key for the model envelope")
    args = parser.parse_args()
    publisher_public_key = None
    if args.publisher_sidecar is not None:
        publisher_public_key = _publisher_public_key(
            json.loads(
                args.publisher_sidecar.resolve(strict=True).read_text(encoding="utf-8")
            )["public_key"]
        )
    report = asyncio.run(
        smoke(
            args.base_path.resolve(),
            args.runtime.resolve(strict=True),
            args.model.resolve(strict=True),
            multipart_limit=args.multipart_limit,
            long_audio_limit=args.long_audio_limit,
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
            model_publisher_public_key=(None if args.model_publisher_sidecar is None else _publisher_public_key(json.loads(args.model_publisher_sidecar.read_text())["public_key"])),
            detailed_audio=tuple(
                (model_id, Path(audio_path).resolve(strict=True), language)
                for model_id, audio_path, language in args.detailed_audio
            ),
            process_audio=tuple(
                (
                    model_id,
                    Path(audio_path).resolve(strict=True),
                    profile,
                    Path(output_path).resolve(),
                )
                for model_id, audio_path, profile, output_path in args.process_audio
            ),
        )
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
