from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import json

import pytest

from ai2apps.packages.contract_v1 import build_package, create_signature_envelope, generate_publisher_key
from ai2apps.packages.registry import RegistryError, RegistryPackageManager
from ai2apps.packages.test_candidates import import_candidate, require_test_instance


@pytest.fixture
def candidate(tmp_path, monkeypatch):
    monkeypatch.setenv('AI2APPS_INSTANCE_ID', 'test')
    monkeypatch.setenv('AI2APPS_SUPERVISED', 'helper')
    source = Path(__file__).resolve().parents[1] / 'packages/ai2apps-media-voice-studio-suite'
    archive = tmp_path / 'candidate.ai2app'
    inspected = build_package(source, archive, include_mini_app_catalog=False)
    private, public, fingerprint = generate_publisher_key()
    envelope = create_signature_envelope(inspected, private, publisher_id='publisher', publisher_key_id='key')
    archive.with_suffix('.ai2app.envelope.json').write_text(json.dumps(envelope))
    registry = RegistryPackageManager(cloud=None, root=tmp_path, secrets=None, extension_manager=None, service_manager=None)
    registry.trusted_snapshot = AsyncMock(return_value={'version': 1, 'releases': [{
        'packageId': 'ai2apps/existing', 'status': 'published', 'publisher': {'id': 'publisher', 'key': {
            'id': 'key', 'publicKeyPem': public, 'fingerprintSha256': fingerprint}}}]})
    extensions = SimpleNamespace(_audit=AsyncMock(return_value={'decision': 'review'}),
        install_verified_bundle=AsyncMock(return_value=SimpleNamespace(status=SimpleNamespace(value='active'))))
    runtime = SimpleNamespace(config=SimpleNamespace(paths=SimpleNamespace(
        base_path=Path.home() / 'Library/Application Support/AI2Apps/instances/test/data')),
        registry_packages=registry, extension_manager=extensions)
    return runtime, archive, inspected.sha256


@pytest.mark.parametrize('instance', ['default', 'dev', 'app-dev', ''])
def test_rejects_other_instances(candidate, monkeypatch, instance):
    runtime, _, _ = candidate
    monkeypatch.setenv('AI2APPS_INSTANCE_ID', instance)
    with pytest.raises(RegistryError, match='isolated Test'):
        require_test_instance(runtime)


def test_rejects_wrong_data_path(candidate, tmp_path):
    runtime, _, _ = candidate
    runtime.config.paths.base_path = tmp_path
    with pytest.raises(RegistryError):
        require_test_instance(runtime)


@pytest.mark.asyncio
async def test_review_does_not_install(candidate):
    runtime, archive, digest = candidate
    result = await import_candidate(runtime, str(archive))
    assert result['sha256'] == digest
    assert result['published'] is False and result['installed'] is False
    runtime.extension_manager.install_verified_bundle.assert_not_called()


@pytest.mark.asyncio
async def test_explicit_digest_approval_installs_with_test_provenance(candidate):
    runtime, archive, digest = candidate
    result = await import_candidate(runtime, str(archive), expected_digest=digest)
    assert result['installed'] and not result['published']
    call = runtime.extension_manager.install_verified_bundle.call_args
    assert call.args[1]['trust'] == 'test-only-publisher-signed-candidate'
    assert call.kwargs['approve_review'] is True
    assert not runtime.registry_packages.state_path.exists()


@pytest.mark.asyncio
async def test_rejects_changed_approval(candidate):
    runtime, archive, _ = candidate
    with pytest.raises(RegistryError, match='changed since review'):
        await import_candidate(runtime, str(archive), expected_digest='0' * 64)
    runtime.extension_manager.install_verified_bundle.assert_not_called()


@pytest.mark.asyncio
async def test_rejects_unbound_publisher(candidate):
    runtime, archive, _ = candidate
    runtime.registry_packages.trusted_snapshot.return_value['releases'] = []
    with pytest.raises(RegistryError, match='Publisher key'):
        await import_candidate(runtime, str(archive))


@pytest.mark.asyncio
async def test_rejects_tampered_bytes(candidate):
    runtime, archive, digest = candidate
    archive.write_bytes(archive.read_bytes() + b'tampered')
    with pytest.raises(Exception, match='digest or size'):
        await import_candidate(runtime, str(archive), expected_digest=digest)
    runtime.extension_manager.install_verified_bundle.assert_not_called()


@pytest.mark.asyncio
async def test_audit_rejection_cannot_install(candidate):
    from ai2apps.extensions import ExtensionError
    runtime, archive, digest = candidate
    runtime.extension_manager._audit.side_effect = ExtensionError('audit_rejected', 'Rejected')
    with pytest.raises(ExtensionError):
        await import_candidate(runtime, str(archive), expected_digest=digest)
    runtime.extension_manager.install_verified_bundle.assert_not_called()


@pytest.mark.asyncio
async def test_rejects_revoked_key(candidate):
    runtime, archive, _ = candidate
    runtime.registry_packages.trusted_snapshot.return_value['releases'][0]['publisher']['key']['status'] = 'revoked'
    with pytest.raises(RegistryError, match='Publisher key'):
        await import_candidate(runtime, str(archive))
