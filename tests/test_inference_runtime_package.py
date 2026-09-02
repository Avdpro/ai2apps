from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from ai2apps.packages.archive import MAX_PACKAGE_BYTES, ServicePackageArchive
from ai2apps.packages.inference_runtime import (
    NATIVE_RUNTIME_PROTOCOL,
    RUNTIME_PROTOCOL,
    InferenceRuntimeInstaller,
    InferenceRuntimeResolver,
)
from ai2apps.packages.manager import ServicePackageManager, _detect_local_accelerator
from ai2apps.packages.models import PackageError, PackageStatus
from ai2apps.packages.resolver import ServiceDependencyResolver
from ai2apps.packages.supervisor import ManagedServiceSupervisor

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SOURCE = ROOT / "packages" / "ai2apps-runtime-omlx"
KNOWLEDGE_RUNTIME_SOURCE = ROOT / "packages" / "ai2apps-runtime-knowledge-rag"
MODEL_SOURCES = (
    ROOT / "packages" / "omlx-model-qwen38",
    ROOT / "packages" / "omlx-model-qwen36-cached-moe",
    ROOT / "packages" / "omlx-model-deepseek-v4-flash",
    ROOT / "packages" / "omlx-model-deepseek-v4-flash-2bit",
)


def manifest(path: Path) -> dict:
    return yaml.safe_load((path / "service.yaml").read_text(encoding="utf-8"))


def test_runtime_provider_and_model_dependencies_are_explicit() -> None:
    runtime = ServicePackageArchive._manifest(manifest(RUNTIME_SOURCE))
    assert runtime.protocol == RUNTIME_PROTOCOL
    assert runtime.raw["runtime"]["role"] == "inference_provider"
    assert runtime.command == ()
    assert "model-worker-v1" in runtime.capabilities

    for source in MODEL_SOURCES:
        parsed = ServicePackageArchive._manifest(manifest(source))
        expected_version = (
            "0.3.3"
            if source.name == "omlx-model-deepseek-v4-flash-2bit"
            else "0.3.2"
        )
        assert parsed.version == expected_version
        assert parsed.raw["runtime"]["provider"] == "ai2apps.runtime.omlx"
        requirement = parsed.raw["requires"]["services"][0]
        assert requirement["id"] == "ai2apps.runtime.omlx"
        assert requirement["optional"] is False
        assert {"mlx", "model-worker-v1"}.issubset(requirement["capabilities"])
        pyproject = (source / "pyproject.toml").read_text(encoding="utf-8")
        project_section = pyproject.partition("[project.optional-dependencies]")[0]
        assert "mlx==" not in project_section
        outer = json.loads((source / "ai2apps.json").read_text(encoding="utf-8"))
        expected_runtime = (
            ">=1.5.4 <2.0.0"
            if source.name == "omlx-model-deepseek-v4-flash-2bit"
            else ">=1.0.1 <2.0.0"
        )
        assert outer["dependencies"] == [
            {
                "packageId": "ai2apps/runtime-omlx",
                "version": expected_runtime,
                "optional": False,
            }
        ]


def test_knowledge_runtime_and_workers_use_generic_locked_provider_contract() -> None:
    runtime = ServicePackageArchive._manifest(manifest(KNOWLEDGE_RUNTIME_SOURCE))
    assert runtime.protocol == NATIVE_RUNTIME_PROTOCOL
    assert runtime.raw["runtime"]["role"] == "knowledge_backend_provider"
    assert runtime.command == ()
    assert {"knowledge-runtime-v1", "lancedb", "mlx-embeddings"}.issubset(
        runtime.capabilities
    )

    for source in (
        ROOT / "packages" / "ai2apps-service-knowledge-lancedb",
        ROOT / "packages" / "ai2apps-model-multilingual-e5-small",
    ):
        worker = ServicePackageArchive._manifest(manifest(source))
        assert worker.raw["runtime"]["provider"] == "ai2apps.runtime.knowledge-rag"
        assert worker.command[0] == "{runtime_python}"
        requirement = worker.raw["requires"]["services"][0]
        assert requirement["id"] == "ai2apps.runtime.knowledge-rag"
        assert requirement["optional"] is False
        assert "knowledge-runtime-v1" in requirement["capabilities"]

    embedding = ServicePackageArchive._manifest(
        manifest(ROOT / "packages" / "ai2apps-model-multilingual-e5-small")
    )
    assert embedding.protocol == "http-json"


def test_only_inference_runtime_packages_receive_the_large_archive_limit() -> None:
    entry = SimpleNamespace(file_size=MAX_PACKAGE_BYTES + 1)
    runtime = ServicePackageArchive._manifest(manifest(RUNTIME_SOURCE))
    model = ServicePackageArchive._manifest(
        manifest(ROOT / "packages" / "omlx-model-qwen38")
    )

    ServicePackageArchive._enforce_size_limit({"runtime": entry}, runtime)
    with pytest.raises(PackageError) as error:
        ServicePackageArchive._enforce_size_limit({"model": entry}, model)

    assert error.value.code == "package_size_limit"


def test_package_manager_detects_cuda_for_variant_selection(monkeypatch) -> None:
    monkeypatch.setattr("ai2apps.packages.manager.platform.system", lambda: "Linux")
    monkeypatch.setattr("ai2apps.packages.manager.platform.machine", lambda: "aarch64")
    monkeypatch.setattr(
        "ai2apps.packages.manager.Path.exists",
        lambda path: str(path) == "/dev/nvidiactl",
    )

    assert _detect_local_accelerator() == "cuda"


def test_dependency_solver_filters_runtime_capabilities() -> None:
    class Repository:
        @staticmethod
        def installed():
            return ()

        @staticmethod
        def active(_key):
            return None

    runtime_manifest = ServicePackageArchive._manifest(manifest(RUNTIME_SOURCE))
    model_manifest = ServicePackageArchive._manifest(
        manifest(ROOT / "packages" / "omlx-model-qwen38")
    )
    runtime = SimpleNamespace(
        digest="sha256:runtime",
        manifest=runtime_manifest,
    )
    model = SimpleNamespace(digest="sha256:model", manifest=model_manifest)

    # The resolver intentionally uses the concrete inspected type to
    # distinguish archives from installed records. Exercise its capability
    # logic through lightweight subclasses with the required attributes.
    from ai2apps.packages.models import InspectedServicePackage

    def inspected(value, digest):
        return InspectedServicePackage(
            archive_path=Path("/tmp/fake.ai2service"),
            digest=digest,
            manifest=value,
            files=(),
            sbom={},
            publisher_attestation={},
            signature={},
            bundled_attestations=(),
            total_size_bytes=0,
        )

    plan = ServiceDependencyResolver(Repository()).resolve(
        inspected(model.manifest, model.digest),
        (inspected(runtime.manifest, runtime.digest),),
    )
    assert [item.manifest.service_key for item in plan.packages] == [
        "ai2apps.runtime.omlx",
        "ai2apps.model.qwen38",
    ]
    assert plan.locks[0].dependency_key == "ai2apps.runtime.omlx"

    incompatible_raw = manifest(RUNTIME_SOURCE)
    incompatible_raw["capabilities"] = ["mlx", "model-worker-v1"]
    incompatible = ServicePackageArchive._manifest(incompatible_raw)
    with pytest.raises(PackageError, match="lacks required capabilities") as error:
        ServiceDependencyResolver(Repository()).resolve(
            inspected(model.manifest, model.digest),
            (inspected(incompatible, "sha256:incompatible"),),
        )
    assert error.value.code == "dependency_capability_missing"


def test_runtime_resolver_uses_locked_immutable_payload(tmp_path: Path) -> None:
    packages_root = tmp_path / "packages"
    store = tmp_path / "store"
    store.joinpath("META").mkdir(parents=True)
    provider_manifest = manifest(RUNTIME_SOURCE)
    provider = SimpleNamespace(
        service_key="ai2apps.runtime.omlx",
        package_version=provider_manifest["version"],
        package_digest="sha256:abc123",
        status=PackageStatus.ACTIVE,
        manifest=provider_manifest,
        store_path=str(store),
    )
    model_manifest = manifest(ROOT / "packages" / "omlx-model-qwen38")
    model = SimpleNamespace(
        package_digest="sha256:model",
        manifest=model_manifest,
    )

    class Repository:
        @staticmethod
        def locks(_digest):
            return (
                SimpleNamespace(
                    dependency_key="ai2apps.runtime.omlx",
                    dependency_digest="sha256:abc123",
                    optional=False,
                ),
            )

        @staticmethod
        def active(key):
            return provider if key == "ai2apps.runtime.omlx" else None

    resolver = InferenceRuntimeResolver(Repository(), packages_root)
    root = resolver.installation_root(provider)
    python = root / "Python/cpython-3.11/bin/python3.11"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    python.chmod(0o755)
    (root / "Python/framework-mlx-base/lib/python3.11/site-packages").mkdir(
        parents=True
    )
    launcher = root / "app/ai2apps/model_worker/launcher.py"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("", encoding="utf-8")
    descriptor = {
        "schema": "ai2apps.inference-runtime/v1",
        "service_id": "ai2apps.runtime.omlx",
        "version": provider_manifest["version"],
        "protocol": "ai2apps-model-worker/v1",
        "python": "Python/cpython-3.11/bin/python3.11",
        "python_home": "Python/cpython-3.11",
        "framework_site_packages": "Python/framework-mlx-base/lib/python3.11/site-packages",
        "launcher": "app/ai2apps/model_worker/launcher.py",
    }
    (store / "META/runtime-manifest.json").write_text(json.dumps(descriptor))

    resolved = resolver.resolve(model)
    assert resolved.python == python
    assert resolved.launcher == launcher
    package_root = tmp_path / "model"
    package_root.mkdir()
    adapter = package_root / "adapter.py"
    adapter.write_text("", encoding="utf-8")
    data_root = tmp_path / "data"
    data_root.mkdir()
    command, _ = ManagedServiceSupervisor._model_worker_command(
        package_root,
        data_root,
        {
            "id": "ai2apps.model.test",
            "runtime": {"adapter": "adapter.py:create_adapter"},
            "models": [],
        },
        12345,
        inference_runtime=resolved,
    )
    assert Path(command[0]) == python
    assert Path(command[2]) == launcher


def test_model_runtime_provider_cannot_be_optional() -> None:
    value = manifest(ROOT / "packages" / "omlx-model-qwen38")
    value["requires"]["services"][0]["optional"] = True
    parsed = ServicePackageArchive._manifest(value)
    model = SimpleNamespace(package_digest="sha256:model", manifest=parsed.raw)
    with pytest.raises(PackageError) as error:
        InferenceRuntimeResolver._provider_requirement(model)
    assert error.value.code == "runtime_dependency_missing"


def test_runtime_command_timeout_reports_install_stage(monkeypatch) -> None:
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(("tool",), 12)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(PackageError) as error:
        InferenceRuntimeInstaller._run(
            "/usr/bin/tool", stage="test verification", timeout_seconds=12
        )
    assert error.value.code == "runtime_payload_verification_timeout"
    assert error.value.details == {
        "stage": "test verification",
        "timeout_seconds": 12,
    }


def _linux_runtime_package(tmp_path: Path, archive_bytes: bytes, digest: str | None = None):
    store = tmp_path / "store"
    store.joinpath("META").mkdir(parents=True)
    payload = store / "runtime.tar.gz"
    payload.write_bytes(archive_bytes)
    descriptor = {
        "schema": "ai2apps.inference-runtime/v1",
        "service_id": "ai2apps.runtime.cuda-torch",
        "version": "0.1.0",
        "protocol": "ai2apps-model-worker/v1",
        "python": "bin/python",
        "python_home": ".",
        "framework_site_packages": "site-packages",
        "launcher": "ai2apps/model_worker/launcher.py",
        "payload": {
            "type": "tar.gz",
            "path": "runtime.tar.gz",
            "root": "Runtime",
            "sha256": digest or hashlib.sha256(archive_bytes).hexdigest(),
            "max_unpacked_bytes": 1024 * 1024,
        },
    }
    store.joinpath("META/runtime-manifest.json").write_text(json.dumps(descriptor))
    return SimpleNamespace(
        service_key="ai2apps.runtime.cuda-torch",
        package_version="0.1.0",
        package_digest="sha256:abc123",
        store_path=str(store),
        manifest={"runtime": {"descriptor": "META/runtime-manifest.json"}},
    )


def _runtime_tar(*, unsafe_name: str | None = None) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name, content, mode in (
            ("Runtime/bin/python", b"#!/bin/sh\n", 0o755),
            ("Runtime/site-packages/marker", b"ok\n", 0o644),
            ("Runtime/ai2apps/model_worker/launcher.py", b"pass\n", 0o644),
        ):
            item = tarfile.TarInfo(name)
            item.size = len(content)
            item.mode = mode
            archive.addfile(item, io.BytesIO(content))
        if unsafe_name is not None:
            item = tarfile.TarInfo(unsafe_name)
            item.size = 1
            archive.addfile(item, io.BytesIO(b"x"))
    return stream.getvalue()


def test_linux_runtime_tar_payload_is_verified_and_materialized(
    tmp_path: Path, monkeypatch
) -> None:
    archive_bytes = _runtime_tar()
    package = _linux_runtime_package(tmp_path, archive_bytes)
    resolver = InferenceRuntimeResolver(SimpleNamespace(), tmp_path / "packages")
    monkeypatch.setattr("ai2apps.packages.inference_runtime.platform.system", lambda: "Linux")

    root = InferenceRuntimeInstaller(resolver).materialize(package)

    assert root.joinpath("bin/python").read_text() == "#!/bin/sh\n"
    assert root.joinpath("bin/python").stat().st_mode & 0o111
    assert root.stat().st_mode & 0o222 == 0


@pytest.mark.parametrize(
    ("archive_bytes", "digest", "code"),
    (
        (_runtime_tar(unsafe_name="../escape"), None, "runtime_payload_escape"),
        (_runtime_tar(), "0" * 64, "runtime_payload_digest_mismatch"),
    ),
)
def test_linux_runtime_tar_rejects_untrusted_payloads(
    tmp_path: Path, monkeypatch, archive_bytes: bytes, digest: str | None, code: str
) -> None:
    package = _linux_runtime_package(tmp_path, archive_bytes, digest)
    resolver = InferenceRuntimeResolver(SimpleNamespace(), tmp_path / "packages")
    monkeypatch.setattr("ai2apps.packages.inference_runtime.platform.system", lambda: "Linux")

    with pytest.raises(PackageError) as error:
        InferenceRuntimeInstaller(resolver).materialize(package)

    assert error.value.code == code


def test_model_workers_do_not_receive_the_generic_four_gib_address_limit(
    monkeypatch,
) -> None:
    calls = []
    monkeypatch.setattr("ai2apps.packages.supervisor.platform.system", lambda: "Linux")
    monkeypatch.setattr(
        "ai2apps.packages.supervisor.resource.setrlimit",
        lambda kind, value: calls.append((kind, value)),
    )

    ManagedServiceSupervisor._limit_resources(model_worker=True)
    assert all(kind != __import__("resource").RLIMIT_AS for kind, _ in calls)

    calls.clear()
    ManagedServiceSupervisor._limit_resources(model_worker=False)
    assert any(kind == __import__("resource").RLIMIT_AS for kind, _ in calls)


def test_linux_model_worker_sandbox_keeps_host_loopback_transport(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("ai2apps.packages.supervisor.platform.system", lambda: "Linux")
    monkeypatch.setattr("ai2apps.packages.supervisor.shutil.which", lambda _: "/usr/bin/bwrap")
    package = tmp_path / "package"
    data = tmp_path / "data"
    temporary = tmp_path / "temporary"
    for path in (package, data, temporary):
        path.mkdir()
    supervisor = object.__new__(ManagedServiceSupervisor)

    command = supervisor._sandbox_command(
        ("/bin/true",),
        package,
        data,
        temporary,
        network=False,
        host_loopback_transport=True,
    )

    assert "--unshare-net" not in command


def test_linux_cuda_model_worker_uses_docker_sandbox(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("ai2apps.packages.supervisor.platform.system", lambda: "Linux")
    monkeypatch.setattr("ai2apps.packages.supervisor.shutil.which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr(
        "ai2apps.packages.supervisor.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0),
    )
    package = tmp_path / "package"
    data = tmp_path / "data"
    temporary = tmp_path / "temporary"
    for path in (package, data, temporary):
        path.mkdir()
    supervisor = object.__new__(ManagedServiceSupervisor)

    command = supervisor._sandbox_command(
        ("/runtime/python", "--port", "18765"),
        package,
        data,
        temporary,
        network=False,
        cuda=True,
        host_loopback_transport=True,
        port=18765,
        unix_socket=data / "model-worker.sock",
    )

    assert command[:3] == ("/usr/bin/docker", "run", "--rm")
    assert "none" in command
    assert "--publish" not in command
    assert "--gpus" in command
    assert command[-2:] == ("--uds", str(data / "model-worker.sock"))


def test_staged_runtime_activation_moves_locks_before_local_services_start() -> None:
    manifest_value = manifest(RUNTIME_SOURCE)
    pending = SimpleNamespace(
        service_key="ai2apps.runtime.omlx",
        package_version="1.3.0",
        package_digest="sha256:new",
        status=PackageStatus.INSTALLED,
        manifest=manifest_value,
    )
    prior = SimpleNamespace(
        service_key="ai2apps.runtime.omlx",
        package_version="1.1.1",
        package_digest="sha256:old",
        status=PackageStatus.ACTIVE,
        manifest=manifest_value,
    )
    calls = []

    class Packages:
        @staticmethod
        def installed():
            return (prior, pending)

        @staticmethod
        def active(_key):
            return prior

        @staticmethod
        def activate_with_relocked_dependents(key, digest, dependents):
            calls.append((key, digest, dependents))

        @staticmethod
        def get_by_digest(_digest):
            return pending

    fake_manager = SimpleNamespace(
        packages=Packages(),
        _validate_installed=lambda package: calls.append(("validate", package.package_digest)),
        _compatible_runtime_dependents=lambda _package: ("sha256:model",),
        _declare=lambda package: calls.append(("declare", package.package_digest)),
    )

    activated = ServicePackageManager._activate_staged_inference_runtimes(
        fake_manager
    )

    assert activated == ((pending, prior, ("sha256:model",)),)
    assert calls == [
        ("validate", "sha256:new"),
        ("ai2apps.runtime.omlx", "sha256:new", ("sha256:model",)),
        ("declare", "sha256:new"),
    ]


def test_developer_id_runtime_uses_gatekeeper_without_xcode(
    tmp_path: Path, monkeypatch
) -> None:
    installer = InferenceRuntimeInstaller(SimpleNamespace())
    commands = []

    def run(*command, stage, timeout_seconds=300.0):
        commands.append((command, stage, timeout_seconds))
        return SimpleNamespace(stderr="TeamIdentifier=84XL5V265N")

    monkeypatch.setattr(installer, "_run", run)
    monkeypatch.setattr(installer, "_copy_directory", lambda *_args: None)
    monkeypatch.setattr("ai2apps.packages.inference_runtime.platform.system", lambda: "Darwin")
    source = tmp_path / "Runtime.dmg"
    source.write_bytes(b"test")
    installer._copy_dmg(
        source,
        tmp_path / "installed",
        {
            "distribution": {
                "signing": "developer-id",
                "team_id": "84XL5V265N",
            },
            "payload": {"root": "."},
        },
    )
    binaries = [command[0][0] for command in commands]
    assert "/usr/bin/xcrun" not in binaries
    assert not any(
        command[0][0] == "/usr/bin/codesign" and str(source) in command[0]
        for command in commands
    )
    assert any(
        command[0][:6]
        == (
            "/usr/sbin/spctl",
            "--assess",
            "--type",
            "open",
            "--context",
            "context:primary-signature",
        )
        for command in commands
    )
