import os
import json
import shutil
from pathlib import Path

import pytest

from ai2apps.extensions.development import DevelopmentPackageLoader
from ai2apps.extensions.models import ExtensionError
from test_app_interactions import runtime


@pytest.fixture
def loader(tmp_path):
    (tmp_path / 'ai2apps').mkdir()
    (tmp_path / 'ai2apps' / '__init__.py').touch()
    packages = tmp_path / 'packages'
    packages.mkdir()
    source = Path(__file__).resolve().parents[2] / 'packages' / 'ai2apps-search-all'
    shutil.copytree(source, packages / 'search')
    return DevelopmentPackageLoader(tmp_path)


def test_unchanged_packages_skip_manifest_validation_without_sharing_mutable_data(loader, monkeypatch):
    import ai2apps.extensions.development as module
    original = module.validate_manifest
    calls = []
    def validate(value):
        calls.append(True)
        return original(value)
    monkeypatch.setattr(module, 'validate_manifest', validate)
    first = loader.discover()[0]
    first.manifest['name'] = 'tampered in memory'
    second = loader.discover()[0]
    assert len(calls) == 1
    assert second.manifest['name'] != first.manifest['name']


def test_metadata_change_is_revalidated_even_with_restored_mtime(loader):
    loader.discover()
    path = loader.packages_root / 'search' / 'ai2apps.json'
    info = path.stat()
    path.write_text('invalid')
    os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
    with pytest.raises(ExtensionError):
        loader.discover()


def test_cached_package_still_rejects_new_symlinks(loader, tmp_path):
    loader.discover()
    outside = tmp_path / 'outside.js'
    outside.write_text('secret')
    (loader.packages_root / 'search' / 'web' / 'linked.js').symlink_to(outside)
    with pytest.raises(ExtensionError, match='links are forbidden'):
        loader.discover()


def test_file_additions_removals_and_package_removal_invalidate_cache(loader):
    first = loader.discover()[0]
    path = loader.packages_root / 'search' / 'web' / 'extra.js'
    path.write_text('/* new */')
    assert 'web/extra.js' in loader.discover()[0].files
    assert 'web/extra.js' not in first.files
    path.unlink()
    assert 'web/extra.js' not in loader.discover()[0].files
    shutil.rmtree(loader.packages_root / 'search')
    assert loader.discover() == ()
    assert not loader._validated


def test_capability_catalog_uses_builder_component_projection_and_rejects_unknown_identity(loader):
    package=loader.discover()[0]
    assert package.manifest['mini_apps'][0]['id']=='ai2apps.search-all'
    path=loader.packages_root/'search'/'ai2apps.json'
    manifest=json.loads(path.read_text())
    manifest['capabilityCatalog']['entries'][0]['identity']='example.undeclared'
    path.write_text(json.dumps(manifest))
    assert loader.discover(isolate_invalid=True)==()
    assert 'Capability identity' in loader.errors['search']
    assert not loader._validated


def test_isolation_keeps_valid_packages_and_clears_diagnostic_after_repair(loader):
    bad=loader.packages_root/'broken';bad.mkdir()
    (bad/'app.yaml').write_text('schema: ai2apps.app/v1')
    (bad/'ai2apps.json').write_text('invalid')
    assert len(loader.discover(isolate_invalid=True))==1
    assert set(loader.errors)=={'broken'}
    shutil.rmtree(bad)
    assert len(loader.discover(isolate_invalid=True))==1
    assert loader.errors=={}


def test_invalid_source_package_cannot_block_system_apps_or_reuse_stale_definition(loader,runtime):
    manager=runtime.extension_manager
    manager._development_loader=loader
    package=manager.refresh_development_packages()[0]
    assert manager.launch_app(package.package_id)[0].id
    # A rejected live source must not silently reactivate an older stored copy.
    with runtime.database.transaction(write=True) as db:
        old=dict(db.execute('SELECT * FROM app_definitions WHERE package_id=? AND status=?',(package.package_id,'enabled')).fetchone())
        old.update(id='app_'+'f'*32,status='disabled',package_version='0.0.1+fixture',effective_digest='sha256:'+'0'*64,upstream_digest='sha256:'+'0'*64)
        manifest=json.loads(old['manifest_json']);manifest.pop('development');old['manifest_json']=json.dumps(manifest)
        db.execute('INSERT INTO app_definitions('+','.join(old)+') VALUES('+','.join('?' for _ in old)+')',tuple(old.values()))
    path=loader.packages_root/'search'/'ai2apps.json';original=path.read_text()
    path.write_text('invalid')
    for app in ('ai2apps.settings','ai2apps.account'):
        assert manager.launch_app(app)[0].id
    assert manager._active_app_definition(package.package_id) is None
    assert loader.errors
    path.write_text(original)
    assert manager.launch_app(package.package_id)[0].id
    assert not loader.errors
