"""No network/publishing: exercise the actual job-level routing expressions."""
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def jobs(filename):
    return yaml.safe_load((ROOT / '.github/workflows' / filename).read_text())['jobs']


def enabled(job, tag, prerelease=False):
    expression = job['if'].removeprefix('${{').removesuffix('}}').strip()
    expression = expression.replace('&&', ' and ').replace('||', ' or ').replace('!', ' not ')
    github = SimpleNamespace(ref_name=tag, event=SimpleNamespace(
        release=SimpleNamespace(tag_name=tag, prerelease=prerelease)))
    return eval(expression, {'__builtins__': {}}, {
        'github': github,
        'startsWith': lambda a, b: a.lower().startswith(b.lower()),
        'contains': lambda a, b: b.lower() in a.lower(),
    })


@pytest.mark.parametrize('tag', [
    'v0.1.8-build2264', 'v0.1.9-build2265', 'v1.0.0-build1',
    'v0.1.8-BUILD2264', 'package-runtime-omlx-v1.8.12',
    'package-mini-app-v0.1.0',
])
@pytest.mark.parametrize('prerelease', [False, True])
def test_desktop_and_package_releases_skip_all_publish_jobs(tag, prerelease):
    for filename in ('publish-pypi.yml', 'update-formula.yml'):
        for job in jobs(filename).values():
            assert not enabled(job, tag, prerelease), (filename, tag)


@pytest.mark.parametrize('tag', ['v0.1.8', 'v1.2.3', 'v1.2.3rc1'])
def test_python_releases_keep_existing_route(tag):
    for job in jobs('publish-pypi.yml').values():
        assert enabled(job, tag)
    assert enabled(jobs('update-formula.yml')['update-formula'], tag)


def test_homebrew_preserves_prerelease_and_dev_restrictions():
    job = jobs('update-formula.yml')['update-formula']
    assert not enabled(job, 'v1.2.3', True)
    assert not enabled(job, 'v1.2.3dev1')
    assert enabled(job, 'v1.2.3rc1', True)


def test_pypi_version_and_dependency_gates_remain():
    workflow = jobs('publish-pypi.yml')
    for name in ('build-wheels', 'build-sdist'):
        assert any(s.get('name') == 'Verify release tag matches package version'
                   for s in workflow[name]['steps'])
    for name in ('publish', 'attach-to-release'):
        assert workflow[name]['needs'] == ['build-wheels', 'build-sdist']
