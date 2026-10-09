"""Package bounds, cancellation and signed NPZ checkpoint admission."""

import asyncio
import importlib.util
import json
import threading
from pathlib import Path

import pytest
import yaml

from ai2apps.checkpoints import checkpoint_is_complete, model_checkpoint_is_complete
from ai2apps.model_providers import ModelProviderContractError, validate_package_models
from ai2apps.model_worker.protocol import (
    ModelWorkerCheckpoint,
    ModelWorkerContext,
    ModelWorkerError,
    ModelWorkerRequest,
)

ROOT = Path(__file__).resolve().parents[1]


def package(slug):
    root = ROOT / f"packages/ai2apps-model-{slug}-mlx"
    manifest = yaml.safe_load((root / "service.yaml").read_text())
    models = validate_package_models(
        manifest["id"],
        manifest["models"],
        runtime_mode="managed_process",
        protocol="ai2apps-model-worker/v1",
    )
    spec = importlib.util.spec_from_file_location(
        "test_audio_adapter_" + slug, root / "src/worker_adapter.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return root, manifest, models, module


@pytest.mark.parametrize("slug", ["ace-step", "stable-audio"])
def test_model_contract_and_task_limits(slug, tmp_path):
    root, manifest, models, module = package(slug)
    model = models[0]
    assert model["endpoints"]["audio_generate"] == "/v1/audio/generations"
    assert model["model_type"] == "audio_generation"
    assert manifest["permissions"]["network"]["outbound"] is False
    context = ModelWorkerContext(manifest["id"], root, tmp_path, models)
    adapter = module.AudioAdapter(context)

    async def run():
        base = dict(
            model=model["upstream_id"], task="music", prompt="Piano", duration=10
        )
        with pytest.raises(ModelWorkerError) as error:
            await adapter.invoke(
                ModelWorkerRequest(
                    "audio_generate", base, "missing", output_root=tmp_path
                )
            )
        assert error.value.code == "checkpoint_not_ready"
        for change in (
            {"task": "sound_effects"},
            {"duration": 121},
            {"duration": float("nan")},
            {"output_path": "/tmp/untrusted"},
        ):
            with pytest.raises(ModelWorkerError) as error:
                await adapter.invoke(
                    ModelWorkerRequest(
                        "audio_generate", base | change, "invalid", output_root=tmp_path
                    )
                )
            assert error.value.status_code == 400

    asyncio.run(run())
    bad = dict(
        manifest["models"][0], metadata={"audio_generation": {"schema": "invalid"}}
    )
    with pytest.raises(ModelProviderContractError):
        validate_package_models(
            manifest["id"],
            [bad],
            runtime_mode="managed_process",
            protocol="ai2apps-model-worker/v1",
        )


@pytest.mark.parametrize("slug", ["ace-step", "stable-audio"])
def test_cancel_joins_native_work_and_allows_next_request(slug, tmp_path):
    root, manifest, models, module = package(slug)
    m = models[0]
    context = ModelWorkerContext(
        manifest["id"],
        root,
        tmp_path,
        models,
        (
            ModelWorkerCheckpoint(
                m["id"],
                m["upstream_id"],
                "huggingface",
                "test/model",
                "a" * 40,
                tmp_path,
                {},
            ),
        ),
    )
    started = threading.Event()
    exited = threading.Event()

    def engine(checkpoint, config, payload, output, check, report):
        started.set()
        try:
            while not exited.wait(0.002):
                check()
        finally:
            exited.set()

    async def run():
        adapter = module.AudioAdapter(context, engine=engine)
        await adapter.start()
        request = ModelWorkerRequest(
            "audio_generate",
            dict(model=m["id"], task="music", prompt="Piano", duration=10),
            "cancel",
            output_root=tmp_path,
        )
        job = asyncio.create_task(adapter.invoke(request))
        assert await asyncio.to_thread(started.wait, 2)
        job.cancel()
        with pytest.raises(asyncio.CancelledError):
            await job
        assert exited.is_set() and not adapter.tokens
        adapter.engine = lambda checkpoint, config, payload, output, check, report: (
            output.write_bytes(b"RIFF-test")
        )
        assert (await adapter.invoke(request)).path.read_bytes() == b"RIFF-test"
        await adapter.stop()

    asyncio.run(run())


def test_npz_requires_verified_distribution_and_audio_generation_type(tmp_path):
    root = tmp_path / "snapshot"
    (root / "MLX").mkdir(parents=True)
    weight = root / "MLX/model.npz"
    weight.write_bytes(b"npz-placeholder")
    weight.chmod(0o444)
    model = {
        "model_type": "audio_generation",
        "weights": {"distribution_id": "dist_audio_test"},
    }
    assert not checkpoint_is_complete(root)
    assert not model_checkpoint_is_complete(root, model)
    meta = root / ".ai2apps"
    meta.mkdir()
    (meta / "distribution.json").write_text(
        json.dumps(
            {
                "format": "ai2apps-checkpoint-distribution",
                "version": 1,
                "distributionId": "dist_audio_test",
                "manifestDigest": "sha256:" + "a" * 64,
            }
        )
    )
    info = weight.stat()
    (meta / "verification.json").write_text(
        json.dumps(
            {
                "format": "ai2apps-checkpoint-verification",
                "version": 1,
                "manifestDigest": "sha256:" + "a" * 64,
                "files": {
                    "MLX/model.npz": {
                        "device": info.st_dev,
                        "inode": info.st_ino,
                        "size": info.st_size,
                        "mtimeNs": info.st_mtime_ns,
                    }
                },
            }
        )
    )
    assert model_checkpoint_is_complete(root, model)
    assert not model_checkpoint_is_complete(root, dict(model, model_type="audio_tts"))
    weight.chmod(0o644)
    weight.write_bytes(b"tampered")
    weight.chmod(0o444)
    assert not model_checkpoint_is_complete(root, model)
