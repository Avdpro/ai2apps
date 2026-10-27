"""Fixed development builders must never accept a frozen source export."""
import subprocess
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[2] / 'apps/ai2apps-acefox/scripts/development-source-contract.sh'


def check(root, source, product='com.ai2apps.desktop.dev', instance='dev'):
    return subprocess.run(
        ['zsh', '-c', 'source "$1"; validate_fixed_development_source "$2" "$3" "$4" "$5"',
         'contract-test', str(GUARD), str(root), str(source), product, instance],
        text=True, capture_output=True,
    )


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / 'checkout'
    (root / 'ai2apps').mkdir(parents=True)
    (root / 'ai2apps/__init__.py').touch()
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    return root


@pytest.mark.parametrize('product,instance', [
    ('com.ai2apps.desktop.dev', 'dev'),
    ('com.ai2apps.desktop.appdev', 'app-dev'),
])
def test_fixed_identity_accepts_live_checkout(checkout, product, instance):
    assert check(checkout, checkout, product, instance).returncode == 0


def test_rejects_other_checkout_and_missing_root(checkout, tmp_path):
    other = tmp_path / 'build2262'
    (other / 'ai2apps').mkdir(parents=True)
    (other / 'ai2apps/__init__.py').touch()
    subprocess.run(['git', 'init', '-q', str(other)], check=True)
    assert check(checkout, other).returncode == 64
    assert check(checkout, '').returncode == 64


def test_rejects_export_even_when_it_owns_builder_path(tmp_path):
    export = tmp_path / 'source-baseline'
    (export / 'ai2apps').mkdir(parents=True)
    (export / 'ai2apps/__init__.py').touch()
    assert check(export, export).returncode == 64


def test_production_and_test_contract_unchanged(tmp_path):
    for product, instance in [('com.ai2apps.desktop', 'default'),
                              ('com.ai2apps.desktop.test', 'test')]:
        assert check(tmp_path, '', product, instance).returncode == 0
