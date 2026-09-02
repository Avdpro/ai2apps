# SPDX-License-Identifier: Apache-2.0
"""System Model Worker Host protocol, isolation, and Package contract tests."""

from __future__ import annotations

import io
import json
import sys
import wave
from pathlib import Path

from fastapi.testclient import TestClient

from ai2apps.checkpoint_paths import checkpoint_distribution_cache_key
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
from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError, ModelWorkerStream

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
        if request.payload.get("artifact"):
            await request.progress({"phase": "encode", "current": 1, "total": 1})
            output = request.output_root / "avatar.mp4"
            output.write_bytes(b"fake-mp4")
            return ModelWorkerArtifact(output, "video/mp4", "avatar.mp4")
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
    async def cancel(self, request_id):
        self.cancelled = request_id

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

    assert 'AI2APPS_TRUSTED_FRAMEWORK_SITE_PACKAGES="$FRAMEWORK_SITE"' in entrypoint


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


def test_host_prefers_prepared_cache_moe_checkpoint_for_worker(tmp_path):
    revision = "c" * 40
    manifest = _manifest()
    manifest["models"][0]["weights"] = {
        "provider": "huggingface",
        "repo_id": "example/checkpoint",
        "revision": revision,
        "distribution_id": "dist_example_v1",
        "preparation": {"recipe": "ai2apps/cache-moe/v1"},
    }
    hub = tmp_path / "hub"
    distribution = (
        hub
        / "models--example--checkpoint"
        / "distributions"
        / checkpoint_distribution_cache_key("dist_example_v1")
    )
    distribution.mkdir(parents=True)
    (distribution / "config.json").write_text("{}")
    (distribution / "model.safetensors").write_bytes(b"weights")
    model_root = tmp_path / "models"
    prepared = model_root / "example" / "checkpoint"
    prepared.mkdir(parents=True)
    (prepared / "config.json").write_text("{}")
    (prepared / "model.safetensors").write_bytes(b"weights")
    (prepared / "ai2apps-model.json").write_text("{}")

    checkpoints, roots = ManagedServiceSupervisor._model_worker_checkpoints(
        manifest, hub, model_root
    )

    assert checkpoints[0]["path"] == str(prepared)
    assert model_root.resolve() in roots
    assert (hub / "models--example--checkpoint").resolve() in roots


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


def test_model_worker_status_and_drain_gate_new_requests(tmp_path):
    package, data = _worker_files(tmp_path)
    _, config_path = ManagedServiceSupervisor._model_worker_command(
        package, data, _manifest(), 9123
    )
    app = create_app(config_path, token="worker-secret")
    headers = {"Authorization": "Bearer worker-secret"}

    with TestClient(app) as client:
        status = client.get("/v1/status", headers=headers)
        drained = client.post("/v1/control/drain", headers=headers)
        after = client.get("/v1/status", headers=headers)
        rejected = client.post(
            "/v1/chat/completions",
            headers=headers,
            json={"model": "example-checkpoint", "messages": []},
        )

    assert status.json() == {
        "status": "ready",
        "protocol": "ai2apps-model-worker/v1",
        "service": "example.worker",
        "accepting_requests": True,
        "active_requests": 0,
        "queued_requests": 0,
    }
    assert drained.json() == {"status": "draining"}
    assert after.json()["accepting_requests"] is False
    assert rejected.status_code == 503
    assert rejected.json()["detail"] == "Model Worker is draining"


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


def test_model_worker_accepts_twelve_ordered_reference_parts(tmp_path):
    package, data = _worker_files(tmp_path)
    _, config_path = ManagedServiceSupervisor._model_worker_command(
        package, data, _manifest(), 9123
    )
    app = create_app(config_path, token="worker-secret")
    files = {"file": ("reference-00.png", b"image-00", "image/png")}
    files.update({
        f"reference_{index:02d}_image": (
            f"reference-{index:02d}.png", f"image-{index:02d}".encode(), "image/png"
        )
        for index in range(1, 12)
    })

    with TestClient(app) as client:
        accepted = client.post(
            "/v1/videos/generations",
            headers={"Authorization": "Bearer worker-secret"},
            data={"model": "example-checkpoint"},
            files=files,
        )
        rejected = client.post(
            "/v1/videos/generations",
            headers={"Authorization": "Bearer worker-secret"},
            data={"model": "example-checkpoint"},
            files={**files, "reference_12_image": ("reference-12.png", b"image-12", "image/png")},
        )

    assert accepted.status_code == 200
    assert rejected.status_code == 400
    assert "files" in str(rejected.json()).lower()


def test_model_worker_streams_controlled_artifact_and_records_progress(tmp_path):
    package, data = _worker_files(tmp_path)
    _, config_path = ManagedServiceSupervisor._model_worker_command(
        package, data, _manifest(), 9123
    )
    app = create_app(config_path, token="worker-secret")
    headers = {
        "Authorization": "Bearer worker-secret",
        "X-Request-Id": "video-request-1",
    }

    with TestClient(app) as client:
        response = client.post(
            "/v1/videos/generations", headers=headers,
            json={"model": "example-checkpoint", "artifact": True},
        )
        status = client.get("/v1/requests/video-request-1", headers=headers)

    assert response.status_code == 200
    assert response.content == b"fake-mp4"
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.headers["content-disposition"] == 'attachment; filename="avatar.mp4"'
    assert status.json()["status"] == "succeeded"
    assert status.json()["progress"] == {"phase": "encode", "current": 1, "total": 1}
    assert not any((data / "requests").iterdir())


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
