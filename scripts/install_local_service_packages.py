#!/usr/bin/env python3
"""Trust one local publisher and install a root Service Package offline."""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import urllib.request
import uuid
from pathlib import Path
from urllib.error import HTTPError

from ai2apps.config import PlatformConfig
from ai2apps.packages.models import TrustStatus
from ai2apps.platform_runtime import PlatformRuntime


def _smoke_chat(endpoint: str, headers: dict[str, str], model: str, prompt: str) -> dict:
    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 32,
            "temperature": 0,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        value = json.load(response)
    return {
        "model": value.get("model"),
        "text": value["choices"][0]["message"]["content"],
        "usage": value.get("usage"),
    }


def _smoke_audio(
    endpoint: str, headers: dict[str, str], model: str, audio_path: Path
) -> dict:
    boundary = "ai2apps-" + uuid.uuid4().hex
    media_type = mimetypes.guess_type(audio_path.name)[0] or "audio/wav"
    fields = (("model", model), ("response_format", "verbose_json"))
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
        endpoint.rstrip("/") + "/v1/audio/transcriptions",
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Audio smoke request failed ({error.code}): {detail}") from error


async def _install(args: argparse.Namespace) -> dict:
    runtime = PlatformRuntime(PlatformConfig.from_base_path(args.base_path))
    status = runtime.start()
    if status.status != "ready" or runtime.package_repository is None:
        runtime.stop()
        raise RuntimeError("AI2Apps platform database is not ready")
    try:
        publisher = json.loads(args.publisher_json.read_text(encoding="utf-8"))
        trusted = runtime.package_repository.upsert_publisher(
            publisher_key=str(publisher["publisher_key"]),
            display_name=str(publisher["display_name"]),
            key_id=str(publisher["key_id"]),
            public_key=str(publisher["public_key"]),
            trust_status=TrustStatus.TRUSTED,
            source="user",
            metadata={"ephemeral": bool(publisher.get("ephemeral", False))},
        )
        assert runtime.package_manager is not None
        installed = await runtime.package_manager.install(
            args.archive,
            dependency_archives=tuple(args.dependency),
            approve_audit_review=args.approve_audit_review,
        )
        result = {
            "database": status.filename,
            "publisher": trusted.publisher_key,
            "service_key": installed.service_key,
            "version": installed.package_version,
            "digest": installed.package_digest,
            "status": installed.status.value,
            "installed": [
                {
                    "service_key": item.service_key,
                    "version": item.package_version,
                    "digest": item.package_digest,
                    "status": item.status.value,
                }
                for item in runtime.package_repository.installed()
            ],
        }
        if args.smoke_model:
            supervisor = runtime.package_manager.supervisor
            managed = supervisor._live.get(installed.service_key)
            if managed is None:
                await supervisor.start(installed)
                managed = supervisor._live.get(installed.service_key)
            headers = supervisor.internal_headers(installed.service_key)
            if managed is None or headers is None:
                raise RuntimeError("Installed Model Worker is not live")
            result["smoke_chat"] = await asyncio.to_thread(
                _smoke_chat,
                managed.endpoint,
                headers,
                args.smoke_model,
                args.smoke_prompt,
            )
        if args.smoke_audio:
            supervisor = runtime.package_manager.supervisor
            managed = supervisor._live.get(installed.service_key)
            if managed is None:
                await supervisor.start(installed)
                managed = supervisor._live.get(installed.service_key)
            headers = supervisor.internal_headers(installed.service_key)
            if managed is None or headers is None:
                raise RuntimeError("Installed audio Model Worker is not live")
            result["smoke_audio"] = await asyncio.to_thread(
                _smoke_audio,
                managed.endpoint,
                headers,
                args.smoke_audio_model,
                args.smoke_audio,
            )
        return result
    finally:
        if runtime.package_manager is not None:
            await runtime.package_manager.shutdown()
        runtime.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--dependency", action="append", default=[], type=Path)
    parser.add_argument("--publisher-json", required=True, type=Path)
    parser.add_argument("--base-path", required=True, type=Path)
    parser.add_argument("--approve-audit-review", action="store_true")
    parser.add_argument("--smoke-model")
    parser.add_argument("--smoke-prompt", default="Reply with exactly: Spark OK")
    parser.add_argument("--smoke-audio", type=Path)
    parser.add_argument(
        "--smoke-audio-model",
        default="ai2apps.model.qwen3-asr-0.6b-cuda/qwen3-asr-0.6b",
    )
    args = parser.parse_args()
    args.archive = args.archive.resolve(strict=True)
    args.dependency = [path.resolve(strict=True) for path in args.dependency]
    args.publisher_json = args.publisher_json.resolve(strict=True)
    if args.smoke_audio:
        args.smoke_audio = args.smoke_audio.resolve(strict=True)
    print(json.dumps(asyncio.run(_install(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
