# SPDX-License-Identifier: Apache-2.0
"""System Model Worker Host protocol, isolation, and Package contract tests."""

from __future__ import annotations

import io
import json
import sys
import wave
from pathlib import Path

from fastapi.testclient import TestClient

from ai2apps.model_worker.server import create_app
from ai2apps.packages.archive import ServicePackageArchive
from ai2apps.packages.supervisor import ManagedServiceSupervisor


def _manifest() -> dict:
    return {
        "schema": "ai2apps.service/v1",
        "id": "example.worker",
        "name": "Example Worker",
        "version": "1.0.0",
        "publisher": {"id": "example.publisher"},
        "runtime": {
            "mode": "process",
            "protocol": "ai2apps-model-worker/v1",
            "adapter": "src/adapter.py:create_adapter",
        },
        "models": [
            {
                "id": "example.worker/chat",
                "display_name": "Example Chat",
                "model_type": "llm",
                "upstream_id": "example-checkpoint",
            }
        ],
        "capabilities": [],
        "requires": {"services": []},
        "permissions": {"network": {"outbound": False}},
        "compatibility": {},
        "health": {"path": "/health"},
        "restart": {},
        "tools": [],
    }


def _worker_files(tmp_path: Path) -> tuple[Path, Path]:
    package = tmp_path / "package"
    data = tmp_path / "data"
    (package / "src").mkdir(parents=True)
    data.mkdir()
    (package / "src" / "adapter.py").write_text(
        """
from ai2apps.model_worker import ModelWorkerError, ModelWorkerStream

class Adapter:
    def __init__(self, context):
        self.context = context
        self.started = False
    async def start(self):
        self.started = True
    async def stop(self):
        self.started = False
    async def invoke(self, request):
        if request.payload.get("fail"):
            raise ModelWorkerError("checkpoint missing", code="model_unavailable", status_code=503)
        if request.payload.get("stream"):
            async def chunks():
                yield b'data: {"ok":true}\\n\\n'
                yield b'data: [DONE]\\n\\n'
            return ModelWorkerStream(chunks())
        if request.parts:
            part = request.part("file")
            return {
                "operation": request.operation,
                "model": request.payload.get("model"),
                "part": {
                    "filename": part.filename,
                    "media_type": part.media_type,
                    "size": part.size,
                    "sha256": part.sha256,
                    "path": str(part.path),
                    "exists": part.path.is_file(),
                },
            }
        return {
            "operation": request.operation,
            "model": request.payload.get("model"),
            "service": self.context.service_id,
            "started": self.started,
        }

def create_adapter(context):
    return Adapter(context)
""",
        encoding="utf-8",
    )
    return package, data


def test_model_worker_manifest_has_system_owned_startup():
    parsed = ServicePackageArchive._manifest(_manifest())

    assert parsed.protocol == "ai2apps-model-worker/v1"
    assert parsed.command == ()
    assert parsed.raw["runtime"]["adapter"] == "src/adapter.py:create_adapter"


def test_supervisor_builds_isolated_system_launcher(tmp_path):
    package, data = _worker_files(tmp_path)
    command, config_path = ManagedServiceSupervisor._model_worker_command(
        package, data, _manifest(), 9123
    )

    assert command[1] == "-I"
    assert command[2].endswith("/ai2apps/model_worker/launcher.py")
    assert command[-2:] == ("--port", "9123")
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    assert config["adapter_path"] == str(package / "src" / "adapter.py")
    assert config["models"][0]["id"] == "example.worker/chat"


def test_supervisor_accepts_trusted_framework_import_root(tmp_path, monkeypatch):
    framework_site = tmp_path / "framework" / "site-packages"
    framework_site.mkdir(parents=True)
    monkeypatch.setenv(
        "AI2APPS_TRUSTED_FRAMEWORK_SITE_PACKAGES", str(framework_site)
    )
    monkeypatch.setattr(sys, "path", [*sys.path, str(framework_site)])

    assert (
        ManagedServiceSupervisor._trusted_framework_site_packages()
        == framework_site.resolve()
    )


def test_supervisor_rejects_framework_path_outside_host_imports(
    tmp_path, monkeypatch
):
    framework_site = tmp_path / "untrusted" / "site-packages"
    framework_site.mkdir(parents=True)
    monkeypatch.setenv(
        "AI2APPS_TRUSTED_FRAMEWORK_SITE_PACKAGES", str(framework_site)
    )

    from ai2apps.packages.models import PackageError
    import pytest

    with pytest.raises(PackageError, match="not a Host import root"):
        ManagedServiceSupervisor._trusted_framework_site_packages()


def test_packaged_entrypoint_declares_trusted_framework_layer():
    entrypoint = (
        Path(__file__).parents[1]
        / "apps"
        / "ai2apps-acefox"
        / "scripts"
        / "runtime-entrypoint.sh"
    ).read_text(encoding="utf-8")

    assert 'AI2APPS_TRUSTED_FRAMEWORK_SITE_PACKAGES="$MLX_SITE"' in entrypoint


def test_host_resolves_exact_pinned_snapshot_for_worker(tmp_path):
    revision = "a" * 40
    manifest = _manifest()
    manifest["models"][0]["weights"] = {
        "provider": "huggingface",
        "repo_id": "example/checkpoint",
        "revision": revision,
        "preparation": {"recipe": "native"},
    }
    hub = tmp_path / "hub"
    repo = hub / "models--example--checkpoint"
    snapshot = repo / "snapshots" / revision
    snapshot.mkdir(parents=True)
    (snapshot / "config.yaml").write_text("model: ct-transformer\n")
    (snapshot / "model.safetensors").write_bytes(b"weights")

    checkpoints, roots = ManagedServiceSupervisor._model_worker_checkpoints(
        manifest, hub
    )

    assert roots == (repo,)
    assert checkpoints[0]["path"] == str(snapshot)
    assert checkpoints[0]["revision"] == revision


def test_host_resolves_exact_pinned_onnx_snapshot_for_worker(tmp_path):
    revision = "b" * 40
    manifest = _manifest()
    manifest["models"][0]["weights"] = {
        "provider": "huggingface",
        "repo_id": "example/punctuation",
        "revision": revision,
        "preparation": {"recipe": "native"},
    }
    hub = tmp_path / "hub"
    repo = hub / "models--example--punctuation"
    snapshot = repo / "snapshots" / revision
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}")
    (snapshot / "model.int8.onnx").write_bytes(b"onnx")

    checkpoints, roots = ManagedServiceSupervisor._model_worker_checkpoints(
        manifest, hub
    )

    assert roots == (repo,)
    assert checkpoints[0]["path"] == str(snapshot)


def test_host_rejects_snapshot_symlink_that_escapes_repository(tmp_path):
    revision = "a" * 40
    manifest = _manifest()
    manifest["models"][0]["weights"] = {
        "provider": "huggingface",
        "repo_id": "example/checkpoint",
        "revision": revision,
    }
    hub = tmp_path / "hub"
    snapshot = hub / "models--example--checkpoint" / "snapshots" / revision
    snapshot.parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "config.json").write_text("{}")
    (outside / "model.safetensors").write_bytes(b"weights")
    snapshot.symlink_to(outside, target_is_directory=True)

    from ai2apps.packages.models import PackageError
    import pytest

    with pytest.raises(PackageError, match="escapes"):
        ManagedServiceSupervisor._model_worker_checkpoints(manifest, hub)


def test_host_treats_incomplete_snapshot_as_not_downloaded(tmp_path):
    revision = "a" * 40
    manifest = _manifest()
    manifest["models"][0]["weights"] = {
        "provider": "huggingface",
        "repo_id": "example/checkpoint",
        "revision": revision,
    }
    hub = tmp_path / "hub"
    snapshot = hub / "models--example--checkpoint" / "snapshots" / revision
    snapshot.mkdir(parents=True)
    (snapshot / "config.json").write_text("{}")

    checkpoints, roots = ManagedServiceSupervisor._model_worker_checkpoints(
        manifest, hub
    )

    assert checkpoints[0]["path"] is None
    assert roots == ()


def test_model_worker_auth_lifecycle_json_and_stream(tmp_path):
    package, data = _worker_files(tmp_path)
    _, config_path = ManagedServiceSupervisor._model_worker_command(
        package, data, _manifest(), 9123
    )
    app = create_app(config_path, token="worker-secret")

    with TestClient(app) as client:
        assert client.get("/health").status_code == 401
        headers = {"Authorization": "Bearer worker-secret"}
        health = client.get("/health", headers=headers)
        assert health.json()["protocol"] == "ai2apps-model-worker/v1"

        response = client.post(
            "/v1/chat/completions",
            headers=headers,
            json={"model": "example-checkpoint", "messages": []},
        )
        assert response.json() == {
            "operation": "chat_completions",
            "model": "example-checkpoint",
            "service": "example.worker",
            "started": True,
        }

        failed = client.post(
            "/v1/chat/completions",
            headers=headers,
            json={"model": "missing", "fail": True},
        )
        assert failed.status_code == 503
        assert failed.json()["error"]["code"] == "model_unavailable"

        streamed = client.post(
            "/v1/chat/completions",
            headers=headers,
            json={"model": "example-checkpoint", "stream": True},
        )
        assert streamed.headers["content-type"].startswith("text/event-stream")
        assert streamed.content.endswith(b"data: [DONE]\n\n")


def _wav_bytes(*, seconds: float = 0.05, sample_rate: int = 16_000) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(b"\x00\x00" * int(seconds * sample_rate))
    return output.getvalue()


def test_model_worker_materializes_and_cleans_multipart_parts(tmp_path):
    package, data = _worker_files(tmp_path)
    _, config_path = ManagedServiceSupervisor._model_worker_command(
        package, data, _manifest(), 9123
    )
    app = create_app(config_path, token="worker-secret")
    audio = _wav_bytes()

    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/transcriptions",
            headers={"Authorization": "Bearer worker-secret"},
            data={"model": "example-checkpoint", "language": "zh"},
            files={"file": ("speech.wav", audio, "audio/wav")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["operation"] == "audio_transcription"
    assert body["model"] == "example-checkpoint"
    assert body["part"]["filename"] == "speech.wav"
    assert body["part"]["media_type"] == "audio/wav"
    assert body["part"]["size"] == len(audio)
    assert body["part"]["exists"] is True
    assert Path(body["part"]["path"]).suffix == ".wav"
    assert not Path(body["part"]["path"]).exists()


def test_model_worker_rejects_non_wav_package_audio(tmp_path):
    package, data = _worker_files(tmp_path)
    _, config_path = ManagedServiceSupervisor._model_worker_command(
        package, data, _manifest(), 9123
    )
    app = create_app(config_path, token="worker-secret")

    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/transcriptions",
            headers={"Authorization": "Bearer worker-secret"},
            data={"model": "example-checkpoint"},
            files={"file": ("speech.mp3", b"not-an-mp3", "audio/mpeg")},
        )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_audio_format"
    assert not any((data / "requests").iterdir())
