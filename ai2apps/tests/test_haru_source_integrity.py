"""Pinned model provenance and installed-resource checks; no inference."""
import hashlib
import json
from importlib import resources
from pathlib import Path
import tomllib

from ai2apps.model_worker.haru_duplex import UPSTREAM_COMMIT, CHECKPOINT_REVISION
from ai2apps.model_worker.haru_mlx.prompt import card_templates


def test_pinned_model_source_and_checkpoint_contract():
    root = resources.files('ai2apps.model_worker.haru_mlx')
    manifest = json.loads((root / 'UPSTREAM.json').read_text())
    assert manifest['commit'] == UPSTREAM_COMMIT
    assert manifest['checkpoint']['revision'] == CHECKPOINT_REVISION
    assert manifest['license'] == 'Apache-2.0'
    assert manifest['files']
    for item in manifest['files']:
        assert hashlib.sha256((root / item['path']).read_bytes()).hexdigest() == item['integrated_sha256']
        if item['path'] != 'prompt.py':
            assert item['upstream_sha256'] == item['integrated_sha256']
    assert (root / 'LICENSE').is_file() and (root / 'THIRD_PARTY_NOTICES.md').is_file()
    assert 'zh' in card_templates()['templates']


def test_distribution_includes_model_templates_and_notices():
    project = tomllib.loads((Path(__file__).resolve().parents[2] / 'pyproject.toml').read_text())
    patterns = project['tool']['setuptools']['package-data']['ai2apps.model_worker.haru_mlx']
    assert {'LICENSE', 'THIRD_PARTY_NOTICES.md', 'UPSTREAM.json', 'assets/*.json', 'assets/**/*.json'} <= set(patterns)
    assert 'haru-duplex' in project['project']['optional-dependencies']
