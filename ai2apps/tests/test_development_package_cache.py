import os
import shutil
from pathlib import Path

import pytest

from ai2apps.extensions.development import DevelopmentPackageLoader
from ai2apps.extensions.models import ExtensionError


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
