# SPDX-License-Identifier: Apache-2.0
"""M8 Service lifecycle, package integrity, trust, audit, and transactions."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx
import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI

from ai2apps.api.router import create_ai2apps_router
from ai2apps.capabilities import GrantScope
from ai2apps.chat import ChatRepository
from ai2apps.config import PlatformConfig
from ai2apps.packages import (
    PackageError,
    PackageFile,
    ServicePackageArchive,
    TrustStatus,
    package_digest,
)
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceRuntimeMode,
    ServiceStatus,
    ToolCallContext,
)


def _runtime(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / "data"))
    runtime.start()
    assert runtime.package_manager is not None
    assert runtime.package_repository is not None
    return runtime


def _publisher(
    runtime, private_key, key="example.publisher", status=TrustStatus.TRUSTED
):
    public = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return runtime.package_repository.upsert_publisher(
        publisher_key=key,
        display_name="Example Publisher",
        key_id=f"{key}:main",
        public_key=base64.b64encode(public).decode(),
        trust_status=status,
    )


def _build_package(
    directory: Path,
    private_key: Ed25519PrivateKey,
    *,
    service_key="example.echo",
    version="1.0.0",
    publisher="example.publisher",
    mode="embedded",
    dependencies=(),
    source: str | None = None,
    endpoint: str | None = None,
    variants: list[dict] | None = None,
    models: list[dict] | None = None,
):
    runtime = {
        "mode": mode,
        "protocol": "internal-asgi" if mode == "embedded" else "http-json",
    }
    if mode == "embedded":
        runtime["entrypoint"] = "echo:create"
    elif mode == "process":
        runtime["command"] = [
            "{python}",
            "{package}/src/server.py",
            "{port}",
        ]
    else:
        runtime["endpoint"] = endpoint
    manifest = {
        "schema": "ai2apps.service/v1",
        "id": service_key,
        "name": f"{service_key} {version}",
        "version": version,
        "publisher": {"id": publisher},
        "runtime": runtime,
        "capabilities": [f"{service_key}.echo@1"],
        "requires": {
            "services": [
                {"id": key, "version": spec, "optional": optional}
                for key, spec, optional in dependencies
            ],
            "python": ">=3.11,<3.14",
        },
        "permissions": {"network": {"outbound": False}},
        "compatibility": {
            "os": ["macos", "linux"],
            "architectures": [os.uname().machine.lower()],
        },
        "health": {"path": "/health", "startup_timeout_seconds": 10},
        "restart": {"max_attempts": 2, "base_delay_seconds": 0.01},
        "tools": [
            {
                "name": f"{service_key}.echo",
                "display_name": "Echo",
                "path": "/echo",
                "input_schema": {
                    "type": "object",
                    "properties": {"value": {}},
                    "required": ["value"],
                    "additionalProperties": False,
                },
                "output_schema": {
                    "type": "object",
                    "properties": {"value": {}, "version": {"type": "string"}},
                    "required": ["value", "version"],
                },
            }
        ],
    }
    if variants is not None:
        manifest["variants"] = variants
    if models is not None:
        manifest["models"] = models
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{service_key}-{version}",
        "dataLicense": "CC0-1.0",
        "packages": [],
    }
    if source is None:
        source = f"""
async def echo(arguments, context):
    return {{"value": arguments["value"], "version": "{version}"}}

def create():
    return {{"tools": {{"{service_key}.echo": echo}}}}
"""
    immutable = {
        "service.yaml": yaml.safe_dump(manifest, sort_keys=True).encode(),
        "META/sbom.spdx.json": json.dumps(sbom, sort_keys=True).encode(),
        "src/echo.py" if mode == "embedded" else "src/server.py": source.encode(),
    }
    files = tuple(
        PackageFile(
            path,
            f"sha256:{hashlib.sha256(content).hexdigest()}",
            len(content),
        )
        for path, content in immutable.items()
    )
    digest = package_digest(manifest, files)
    index = {
        "files": [
            {
                "path": item.path,
                "sha256": item.content_hash,
                "size": item.size_bytes,
            }
            for item in files
        ]
    }
    publisher_attestation = {
        "publisher_id": publisher,
        "key_id": f"{publisher}:main",
        "algorithm": "ed25519",
        "package_digest": digest,
    }
    signature = {
        "algorithm": "ed25519",
        "key_id": f"{publisher}:main",
        "signature": base64.b64encode(
            private_key.sign(digest.encode("ascii"))
        ).decode(),
    }
    path = directory / f"{service_key}-{version}.ai2service"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in immutable.items():
            archive.writestr(name, content)
        archive.writestr("META/files.json", json.dumps(index, sort_keys=True))
        archive.writestr(
            "attestations/publisher.json",
            json.dumps(publisher_attestation, sort_keys=True),
        )
        archive.writestr(
            "signatures/publisher.sig", json.dumps(signature, sort_keys=True)
        )
    return path, digest


def test_archive_digest_hash_sbom_and_traversal_are_fail_closed(tmp_path):
    private = Ed25519PrivateKey.generate()
    archive, digest = _build_package(tmp_path, private)
    inspected = ServicePackageArchive.inspect(archive)
    assert inspected.digest == digest
    assert inspected.sbom["spdxVersion"] == "SPDX-2.3"
    assert {item.path for item in inspected.files} == {
        "service.yaml",
        "META/sbom.spdx.json",
        "src/echo.py",
    }

    unsafe = tmp_path / "unsafe.ai2service"
    with zipfile.ZipFile(unsafe, "w") as value:
        value.writestr("../escape.py", "bad")
    with pytest.raises(PackageError) as error:
        ServicePackageArchive.inspect(unsafe)
    assert error.value.code == "unsafe_archive_path"


def test_archive_validates_installable_model_provider_contract(tmp_path):
    private = Ed25519PrivateKey.generate()
    valid, _ = _build_package(
        tmp_path,
        private,
        service_key="example.media",
        mode="external",
        endpoint="http://127.0.0.1:9000",
        models=[
            {
                "id": "example.media/image-v1",
                "display_name": "Example Image",
                "model_type": "image_generation",
                "upstream_id": "image-checkpoint",
            }
        ],
    )
    inspected = ServicePackageArchive.inspect(valid)
    assert inspected.manifest.models[0]["model_type"] == "image_generation"

    invalid, _ = _build_package(
        tmp_path,
        private,
        service_key="example.embedded-model",
        models=[
            {
                "id": "example.embedded-model/chat-v1",
                "model_type": "llm",
            }
        ],
    )
    with pytest.raises(PackageError) as error:
        ServicePackageArchive.inspect(invalid)
    assert error.value.code == "invalid_models"


@pytest.mark.asyncio
async def test_signature_trust_and_audit_gate_precede_embedded_execution(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    marker = tmp_path / "executed"
    source = f"""
from pathlib import Path
Path({str(marker)!r}).write_text("executed")
def create():
    return {{"tools": {{}}}}
"""
    archive, _ = _build_package(tmp_path, private, source=source)

    with pytest.raises(PackageError) as unknown:
        await runtime.package_manager.install(archive, approve_audit_review=True)
    assert unknown.value.code == "publisher_unknown"
    assert not marker.exists()

    _publisher(runtime, private, status=TrustStatus.UNTRUSTED)
    with pytest.raises(PackageError) as untrusted:
        await runtime.package_manager.install(archive, approve_audit_review=True)
    assert untrusted.value.code == "publisher_untrusted"
    assert not marker.exists()

    _publisher(runtime, private, status=TrustStatus.TRUSTED)

    async def reject(_request):
        return {
            "decision": "reject",
            "risk": "high",
            "model": "audit-model",
            "evidence": {"finding": "test rejection"},
        }

    runtime.bind_service_package_auditor(reject)
    with pytest.raises(PackageError) as rejected:
        await runtime.package_manager.install(archive)
    assert rejected.value.code == "audit_rejected"
    assert not marker.exists()
    assert runtime.package_repository.installed() == ()


@pytest.mark.asyncio
async def test_embedded_install_upgrade_failed_upgrade_and_rollback(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    first_archive, first_digest = _build_package(tmp_path, private, version="1.0.0")
    first = await runtime.package_manager.install(
        first_archive, approve_audit_review=True
    )
    assert first.status.value == "active"
    service = runtime.services.get_service("example.echo")
    assert service.runtime_mode is ServiceRuntimeMode.IN_PROCESS
    assert service.package_digest == first_digest
    assert Path(first.store_path).stat().st_mode & 0o222 == 0
    result = await runtime.tools.execute(
        "example.echo.echo",
        {"value": "one"},
        context=ToolCallContext(caller_id="test"),
    )
    assert result.output == {"value": "one", "version": "1.0.0"}

    broken_source = "raise RuntimeError('must roll back before activation')"
    broken_archive, broken_digest = _build_package(
        tmp_path, private, version="1.5.0", source=broken_source
    )
    with pytest.raises(RuntimeError, match="must roll back"):
        await runtime.package_manager.install(broken_archive, approve_audit_review=True)
    assert (
        runtime.package_repository.active("example.echo").package_digest == first_digest
    )
    assert (
        runtime.package_repository.get_by_digest(broken_digest).status.value
        == "uninstalled"
    )
    assert (
        await runtime.tools.execute(
            "example.echo.echo",
            {"value": "safe"},
            context=ToolCallContext(caller_id="test"),
        )
    ).output["version"] == "1.0.0"

    second_archive, second_digest = _build_package(tmp_path, private, version="2.0.0")
    await runtime.package_manager.install(second_archive, approve_audit_review=True)
    assert (
        runtime.package_repository.active("example.echo").package_digest
        == second_digest
    )
    assert (
        await runtime.tools.execute(
            "example.echo.echo",
            {"value": "two"},
            context=ToolCallContext(caller_id="test"),
        )
    ).output["version"] == "2.0.0"

    rolled_back = await runtime.package_manager.rollback("example.echo")
    assert rolled_back.package_digest == first_digest
    assert (
        await runtime.tools.execute(
            "example.echo.echo",
            {"value": "back"},
            context=ToolCallContext(caller_id="test"),
        )
    ).output["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_dependencies_lock_order_and_prevent_disable_uninstall(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    dependency, dependency_digest = _build_package(
        tmp_path, private, service_key="example.base", version="1.2.0"
    )
    root, root_digest = _build_package(
        tmp_path,
        private,
        service_key="example.consumer",
        dependencies=(("example.base", ">=1,<2", False),),
    )
    installed = await runtime.package_manager.install(
        root,
        dependency_archives=(dependency,),
        approve_audit_review=True,
    )
    assert installed.package_digest == root_digest
    assert (
        runtime.package_repository.active("example.base").package_digest
        == dependency_digest
    )
    locks = runtime.package_repository.locks(root_digest)
    assert [(item.dependency_key, item.dependency_digest) for item in locks] == [
        ("example.base", dependency_digest)
    ]
    base_service = runtime.services.get_service("example.base")
    with pytest.raises(PackageError) as disable:
        await runtime.package_manager.disable("example.base", base_service.revision)
    assert disable.value.code == "service_has_dependents"
    with pytest.raises(PackageError) as uninstall:
        await runtime.package_manager.uninstall("example.base")
    assert uninstall.value.code == "service_has_dependents"


@pytest.mark.asyncio
async def test_managed_process_health_tools_logs_and_lifecycle(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    server = """
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body=json.dumps({"status":"ok"}).encode()
        self.send_response(200); self.send_header("Content-Type","application/json")
        self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        size=int(self.headers.get("Content-Length","0"))
        value=json.loads(self.rfile.read(size))
        body=json.dumps({"value":value["value"],"version":"managed"}).encode()
        self.send_response(200); self.send_header("Content-Type","application/json")
        self.end_headers(); self.wfile.write(body)
        print(json.dumps({"level":"info","message":"echo handled","path":self.path}),flush=True)
    def log_message(self, *args): pass
HTTPServer(("127.0.0.1",int(sys.argv[1])),Handler).serve_forever()
"""
    archive, _ = _build_package(
        tmp_path, private, service_key="example.managed", mode="process", source=server
    )
    package = await runtime.package_manager.install(archive, approve_audit_review=True)
    assert package.runtime_mode is ServiceRuntimeMode.MANAGED_PROCESS
    result = await runtime.tools.execute(
        "example.managed.echo",
        {"value": 7},
        context=ToolCallContext(caller_id="test"),
    )
    assert result.output == {"value": 7, "version": "managed"}
    for _ in range(100):
        logs = runtime.package_repository.logs("example.managed")
        if any(item["message"] == "echo handled" for item in logs):
            break
        await __import__("asyncio").sleep(0.01)
    assert any(item["message"] == "echo handled" for item in logs)

    await runtime.package_manager.stop("example.managed")
    managed_service = runtime.services.get_service("example.managed")
    assert (
        runtime.services.get_instance_for_service(managed_service.id).status
        is not ServiceInstanceStatus.RUNNING
    )
    await runtime.package_manager.start("example.managed")
    assert (
        runtime.services.get_instance_for_service(managed_service.id).status
        is ServiceInstanceStatus.RUNNING
    )

    service = runtime.services.get_service("example.managed")
    disabled = await runtime.package_manager.disable(
        "example.managed", service.revision
    )
    assert disabled.status is ServiceStatus.DISABLED
    enabled = await runtime.package_manager.enable("example.managed", disabled.revision)
    assert enabled.status is ServiceStatus.ENABLED
    await runtime.package_manager.restart("example.managed")
    await runtime.package_manager.uninstall("example.managed")
    assert runtime.package_repository.active("example.managed") is None


@pytest.mark.asyncio
async def test_external_service_health_and_lifecycle(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            value = json.loads(self.rfile.read(size))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                json.dumps({"value": value["value"], "version": "external"}).encode()
            )

        def log_message(self, *_args):
            pass

    try:
        server = HTTPServer(("127.0.0.1", 0), Handler)
    except PermissionError:
        pytest.skip("test runner forbids binding a loopback listener")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    try:
        archive, _ = _build_package(
            tmp_path,
            private,
            service_key="example.external",
            mode="external",
            endpoint=f"http://127.0.0.1:{server.server_port}",
        )
        package = await runtime.package_manager.install(
            archive, approve_audit_review=True
        )
        assert package.runtime_mode is ServiceRuntimeMode.EXTERNAL
        result = await runtime.tools.execute(
            "example.external.echo",
            {"value": "remote"},
            context=ToolCallContext(caller_id="test"),
        )
        assert result.output == {"value": "remote", "version": "external"}
    finally:
        server.shutdown()
        thread.join()


@pytest.mark.asyncio
async def test_package_upgrade_invalidates_digest_bound_grant(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    first, first_digest = _build_package(tmp_path, private, version="1.0.0")
    await runtime.package_manager.install(first, approve_audit_review=True)
    session = (
        ChatRepository(runtime.database, runtime.events)
        .create_thread(title="Digest grant")[0]
        .session.id
    )
    run = runtime.agents.create_run(
        session_id=session, agent_key="ai2apps.diagnostic-agent", input={}
    )[0]
    lease = runtime.capabilities.create_lease(
        run_id=run.id,
        scope=GrantScope.RUN,
        capabilities=("example.use",),
        tool_pattern="example.echo.echo",
        issued_by="user",
        evidence={"test": True},
    )
    assert lease.tool_service_digest == first_digest
    assert runtime.capabilities.active_leases_for_run(run.id, "example.echo.echo") == (
        lease,
    )

    second, second_digest = _build_package(tmp_path, private, version="2.0.0")
    await runtime.package_manager.install(second, approve_audit_review=True)
    assert second_digest != first_digest
    assert runtime.capabilities.active_leases_for_run(run.id, "example.echo.echo") == ()


@pytest.mark.asyncio
async def test_tampered_installed_source_cannot_restart(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    archive, _ = _build_package(tmp_path, private)
    package = await runtime.package_manager.install(archive, approve_audit_review=True)
    source = Path(package.store_path) / "src" / "echo.py"
    source.chmod(0o644)
    source.write_text("def create(): return {'tools': {}}", encoding="utf-8")
    with pytest.raises(PackageError) as error:
        await runtime.package_manager.restart("example.echo")
    assert error.value.code == "installed_package_tampered"


def test_dependency_cycle_is_rejected_before_mutation(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    first, _ = _build_package(
        tmp_path,
        private,
        service_key="example.cycle-a",
        dependencies=(("example.cycle-b", ">=1", False),),
    )
    second, _ = _build_package(
        tmp_path,
        private,
        service_key="example.cycle-b",
        dependencies=(("example.cycle-a", ">=1", False),),
    )
    with pytest.raises(PackageError) as error:
        runtime.package_manager.plan(first, (second,))
    assert error.value.code == "dependency_cycle"
    assert runtime.package_repository.installed() == ()


@pytest.mark.asyncio
async def test_package_management_api_inspect_audit_install_and_detail(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    archive, digest = _build_package(tmp_path, private)
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        publisher = await client.put(
            "/v1/platform/publishers/example.publisher",
            json={
                "display_name": "Example",
                "key_id": "example.publisher:main",
                "public_key": base64.b64encode(public).decode(),
                "trust_status": "trusted",
            },
        )
        inspected = await client.post(
            "/v1/platform/service-packages/inspect",
            json={"archive_path": str(archive)},
        )
        audited = await client.post(
            "/v1/platform/service-packages/audit",
            json={"archive_path": str(archive)},
        )
        installed = await client.post(
            "/v1/platform/service-packages/install",
            json={
                "archive_path": str(archive),
                "approve_audit_review": True,
            },
        )
        detail = await client.get(
            "/v1/platform/service-packages/" + digest.removeprefix("sha256:")
        )
    assert publisher.status_code == 200
    assert inspected.json()["digest"] == digest
    assert audited.json()["signature"]["signature"] == "valid"
    assert installed.json()["status"] == "active"
    assert detail.json()["digest"] == digest
    assert detail.json()["attestations"][0]["decision"] == "review"


def test_signed_accelerator_variant_selection_is_deterministic(tmp_path):
    from ai2apps.packages import CompatibilityContext

    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    archive, _ = _build_package(
        tmp_path,
        private,
        variants=[
            {
                "id": "rocm",
                "priority": 10,
                "compatibility": {"accelerators": ["rocm"]},
            },
            {
                "id": "cuda-fast",
                "priority": 20,
                "compatibility": {"accelerators": ["cuda"]},
            },
            {
                "id": "cuda-portable",
                "priority": 10,
                "compatibility": {"accelerators": ["cuda"]},
            },
        ],
    )
    current = runtime.package_manager.compatibility
    runtime.package_manager.compatibility = CompatibilityContext(
        current.os_name,
        current.architecture,
        current.python_version,
        accelerator="cuda",
    )
    inspected = runtime.package_manager.inspect(archive)
    assert runtime.package_manager._select_variant(inspected) == "cuda-fast"


@pytest.mark.asyncio
async def test_upgrade_cannot_break_unchanged_active_dependent(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    base_v1, first_digest = _build_package(
        tmp_path, private, service_key="example.base", version="1.0.0"
    )
    consumer, _ = _build_package(
        tmp_path,
        private,
        service_key="example.consumer",
        dependencies=(("example.base", ">=1,<2", False),),
    )
    await runtime.package_manager.install(
        consumer,
        dependency_archives=(base_v1,),
        approve_audit_review=True,
    )
    base_v2, _ = _build_package(
        tmp_path, private, service_key="example.base", version="2.0.0"
    )
    with pytest.raises(PackageError) as error:
        await runtime.package_manager.install(base_v2, approve_audit_review=True)
    assert error.value.code == "dependent_version_conflict"
    assert (
        runtime.package_repository.active("example.base").package_digest == first_digest
    )
