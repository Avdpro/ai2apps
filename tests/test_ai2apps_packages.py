# SPDX-License-Identifier: Apache-2.0
"""M8 Service lifecycle, package integrity, trust, audit, and transactions."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
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
from ai2apps.identity import RequestPrincipal
from ai2apps.model_providers import list_package_models, proxy_package_json
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
    mode="process",
    dependencies=(),
    source: str | None = None,
    endpoint: str | None = None,
    variants: list[dict] | None = None,
    models: list[dict] | None = None,
    model_worker: bool = False,
):
    runtime = {
        "mode": mode,
        "protocol": "internal-asgi" if mode == "embedded" else "http-json",
    }
    if model_worker:
        runtime["protocol"] = "ai2apps-model-worker/v1"
        runtime["adapter"] = "src/adapter.py:create_adapter"
    elif mode == "embedded":
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
    if source is None and mode == "embedded":
        source = f"""
async def echo(arguments, context):
    return {{"value": arguments["value"], "version": "{version}"}}

def create():
    return {{"tools": {{"{service_key}.echo": echo}}}}
"""
    elif source is None and model_worker:
        source = """
class Adapter:
    def __init__(self, context): self.context = context
    async def invoke(self, request):
        return {"object": "chat.completion", "model": request.payload.get("model"), "choices": []}
def create_adapter(context): return Adapter(context)
"""
    elif source is None:
        source = f"""
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({{"status": "ok"}}).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        size = int(self.headers.get("content-length", "0"))
        value = json.loads(self.rfile.read(size) or b"{{}}")
        body = json.dumps({{"value": value.get("value"), "version": "{version}"}}).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(body)
    def log_message(self, *args): pass
HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
"""
    immutable = {
        "service.yaml": yaml.safe_dump(manifest, sort_keys=True).encode(),
        "META/sbom.spdx.json": json.dumps(sbom, sort_keys=True).encode(),
        (
            "src/adapter.py"
            if model_worker
            else "src/echo.py"
            if mode == "embedded"
            else "src/server.py"
        ): source.encode(),
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
        "src/server.py",
    }

    unsafe = tmp_path / "unsafe.ai2service"
    with zipfile.ZipFile(unsafe, "w") as value:
        value.writestr("../escape.py", "bad")
    with pytest.raises(PackageError) as error:
        ServicePackageArchive.inspect(unsafe)
    assert error.value.code == "unsafe_archive_path"


@pytest.mark.parametrize(
    "endpoint",
    (
        "https://example.com:443",
        "http://example.com:9000",
        "http://127.0.0.1:9000?redirect=https://example.com",
        "http://user:pass@127.0.0.1:9000",
        "http://127.0.0.1",
    ),
)
def test_installed_external_service_endpoint_is_loopback_only(tmp_path, endpoint):
    private = Ed25519PrivateKey.generate()
    archive, _ = _build_package(
        tmp_path,
        private,
        service_key="example.external-denied",
        mode="external",
        endpoint=endpoint,
    )

    with pytest.raises(PackageError) as error:
        ServicePackageArchive.inspect(archive)

    assert error.value.code == "external_endpoint_not_local"


def test_managed_service_cannot_redirect_host_calls_to_remote_endpoint(tmp_path):
    private = Ed25519PrivateKey.generate()
    archive, _ = _build_package(
        tmp_path,
        private,
        service_key="example.managed-redirect",
        mode="process",
    )
    with zipfile.ZipFile(archive, "r") as source:
        files = {name: source.read(name) for name in source.namelist()}
    manifest = yaml.safe_load(files["service.yaml"])
    manifest["runtime"]["endpoint"] = "https://collector.example:443"
    files["service.yaml"] = yaml.safe_dump(manifest, sort_keys=True).encode()
    with zipfile.ZipFile(archive, "w") as target:
        for name, content in files.items():
            target.writestr(name, content)

    with pytest.raises(PackageError) as error:
        ServicePackageArchive.inspect(archive)

    assert error.value.code == "managed_endpoint_not_local"


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
        mode="embedded",
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
async def test_signature_trust_gate_precedes_in_process_runtime_denial(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    marker = tmp_path / "executed"
    source = f"""
from pathlib import Path
Path({str(marker)!r}).write_text("executed")
def create():
    return {{"tools": {{}}}}
"""
    archive, _ = _build_package(tmp_path, private, mode="embedded", source=source)

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

    with pytest.raises(PackageError) as rejected:
        await runtime.package_manager.install(archive, approve_audit_review=True)
    assert rejected.value.code == "third_party_in_process_denied"
    assert not marker.exists()
    assert runtime.package_repository.installed() == ()


@pytest.mark.asyncio
async def test_embedded_alias_is_denied_without_executing_package_code(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    marker = tmp_path / "host-process-executed"
    archive, _ = _build_package(
        tmp_path,
        private,
        mode="embedded",
        source=f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n",
    )

    with pytest.raises(PackageError) as denied:
        await runtime.package_manager.install(archive, approve_audit_review=True)

    assert denied.value.code == "third_party_in_process_denied"
    assert not marker.exists()


@pytest.mark.asyncio
async def test_registry_verified_service_cannot_bypass_in_process_denial(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    archive, _ = _build_package(tmp_path, private, mode="embedded")
    inspected = ServicePackageArchive.inspect(archive)

    with pytest.raises(PackageError) as denied:
        await runtime.package_manager.install_verified_package(
            inspected,
            {"trust": "ai2apps-cloud-registry-v1"},
            approve_audit_review=True,
        )

    assert denied.value.code == "third_party_in_process_denied"
    assert runtime.package_repository.installed() == ()


@pytest.mark.asyncio
async def test_registry_verified_service_stores_active_dependency_locks(
    tmp_path, monkeypatch
):
    runtime = _runtime(tmp_path)
    async def no_runtime_start(_package):
        return None

    monkeypatch.setattr(runtime.package_manager.runtime, "start", no_runtime_start)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    dependency, dependency_digest = _build_package(
        tmp_path, private, service_key="example.registry-base", version="1.2.0"
    )
    await runtime.package_manager.install(
        dependency, approve_audit_review=True
    )
    root, root_digest = _build_package(
        tmp_path,
        private,
        service_key="example.registry-consumer",
        dependencies=(("example.registry-base", ">=1,<2", False),),
    )
    inspected = ServicePackageArchive.inspect(root)

    installed = await runtime.package_manager.install_verified_package(
        inspected,
        {"trust": "test-registry"},
        approve_audit_review=True,
    )

    assert installed.package_digest == root_digest
    locks = runtime.package_repository.locks(root_digest)
    assert [(item.dependency_key, item.dependency_digest) for item in locks] == [
        ("example.registry-base", dependency_digest)
    ]


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
async def test_provider_activation_and_dependent_relock_are_atomic(
    tmp_path, monkeypatch
):
    runtime = _runtime(tmp_path)

    async def no_start_or_stop(_package):
        return None

    monkeypatch.setattr(runtime.package_manager.runtime, "start", no_start_or_stop)
    monkeypatch.setattr(runtime.package_manager.runtime, "stop", no_start_or_stop)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    provider_v1, provider_v1_digest = _build_package(
        tmp_path, private, service_key="example.provider", version="1.0.0"
    )
    consumer, consumer_digest = _build_package(
        tmp_path,
        private,
        service_key="example.consumer-atomic",
        dependencies=(("example.provider", ">=1,<2", False),),
    )
    await runtime.package_manager.install(
        consumer,
        dependency_archives=(provider_v1,),
        approve_audit_review=True,
    )
    provider_v2, provider_v2_digest = _build_package(
        tmp_path, private, service_key="example.provider", version="1.1.0"
    )
    inspected = ServicePackageArchive.inspect(provider_v2)
    store, _created = runtime.package_manager._store(inspected)
    runtime.package_repository.record_install(
        inspected,
        store_path=str(store),
        verification={"signature": {}, "audit": {}},
    )

    runtime.package_repository.activate_with_relocked_dependents(
        "example.provider",
        provider_v2_digest,
        (consumer_digest,),
    )

    assert runtime.package_repository.active("example.provider").package_digest == (
        provider_v2_digest
    )
    assert runtime.package_repository.get_by_digest(provider_v1_digest).status.value == (
        "retained"
    )
    locks = runtime.package_repository.locks(consumer_digest)
    assert [(item.dependency_version, item.dependency_digest) for item in locks] == [
        ("1.1.0", provider_v2_digest)
    ]


@pytest.mark.asyncio
async def test_managed_process_health_tools_logs_and_lifecycle(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(
        runtime.package_manager.supervisor,
        "_sandbox_command",
        lambda command, *args, **kwargs: command,
    )
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
        tmp_path,
        private,
        service_key="example.managed",
        mode="process",
        source=server,
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
async def test_system_model_worker_package_install_route_and_auth(tmp_path, monkeypatch):
    runtime = _runtime(tmp_path)
    monkeypatch.setattr(
        runtime.package_manager.supervisor,
        "_sandbox_command",
        lambda command, *args, **kwargs: command,
    )
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    archive, _ = _build_package(
        tmp_path,
        private,
        service_key="example.worker",
        mode="process",
        model_worker=True,
        models=[
            {
                "id": "example.worker/chat",
                "display_name": "Worker Chat",
                "model_type": "llm",
                "upstream_id": "example-checkpoint",
            }
        ],
    )

    await runtime.package_manager.install(archive, approve_audit_review=True)
    model = list_package_models(runtime)[0]
    assert model.internal_headers is not None
    assert model.internal_headers["Authorization"].startswith("Bearer ")

    response = await proxy_package_json(
        model,
        "chat_completions",
        {"model": model.id, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    assert json.loads(response.body)["model"] == "example-checkpoint"
    await runtime.package_manager.shutdown()


@pytest.mark.asyncio
async def test_failed_first_activation_can_retry_same_package_digest(
    tmp_path, monkeypatch
):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    archive, _ = _build_package(
        tmp_path,
        private,
        service_key="example.retry",
        mode="process",
    )
    attempts = 0

    async def start_once_ready(_package):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PackageError("service_start_failed", "first start failed")

    monkeypatch.setattr(runtime.package_manager.runtime, "start", start_once_ready)

    with pytest.raises(PackageError, match="first start failed"):
        await runtime.package_manager.install(archive, approve_audit_review=True)
    assert runtime.package_repository.installed("example.retry") == ()

    installed = await runtime.package_manager.install(
        archive, approve_audit_review=True
    )

    assert attempts == 2
    assert installed.status.value == "active"
    assert runtime.package_repository.active("example.retry") is not None
    await runtime.package_manager.shutdown()


@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS sandbox integration")
@pytest.mark.asyncio
async def test_system_model_worker_runs_inside_macos_package_sandbox(tmp_path):
    runtime = _runtime(tmp_path)
    private = Ed25519PrivateKey.generate()
    _publisher(runtime, private)
    archive, _ = _build_package(
        tmp_path,
        private,
        service_key="example.sandboxed-worker",
        mode="process",
        model_worker=True,
        models=[
            {
                "id": "example.sandboxed-worker/chat",
                "display_name": "Sandboxed Worker Chat",
                "model_type": "llm",
                "upstream_id": "sandboxed-checkpoint",
            }
        ],
    )

    try:
        await runtime.package_manager.install(archive, approve_audit_review=True)
    except PackageError as exc:
        logs = runtime.package_repository.logs("example.sandboxed-worker")
        pytest.fail(f"sandboxed Model Worker failed: {exc}; logs={logs}")
    model = list_package_models(runtime)[0]
    response = await proxy_package_json(
        model,
        "chat_completions",
        {"model": model.id, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    assert json.loads(response.body)["model"] == "sandboxed-checkpoint"
    await runtime.package_manager.shutdown()


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
    source = Path(package.store_path) / "src" / "server.py"
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
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=RequestPrincipal.legacy_local))
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


def test_service_package_rejects_os_below_declared_minimum(tmp_path):
    from ai2apps.packages import CompatibilityContext

    runtime = _runtime(tmp_path)
    current = runtime.package_manager.compatibility
    runtime.package_manager.compatibility = CompatibilityContext(
        os_name="darwin",
        architecture="arm64",
        python_version=current.python_version,
        os_version="15.6.1",
    )
    package = type(
        "Package",
        (),
        {"manifest": type("Manifest", (), {"raw": {"requires": {}}})()},
    )()

    with pytest.raises(PackageError) as error:
        runtime.package_manager._check_requirements(
            {"os": ["macos"], "minimum_os_version": "26.2"}, package
        )
    assert error.value.code == "os_version_too_old"
    assert error.value.details == {"current": "15.6.1", "minimum": "26.2"}


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
