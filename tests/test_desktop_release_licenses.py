from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_desktop_release_carries_and_checks_repository_license_notices():
    scripts = ROOT / 'apps/ai2apps-acefox/scripts'
    builder = (scripts / 'build-release-app.sh').read_text()
    verifier = (scripts / 'verify-release-app.sh').read_text()
    for name in ['LICENSE', 'LICENSE-POLICY.md', 'NOTICE', 'TRADEMARKS.md',
                 'LICENSES/AI2APPS-CLOUD-CONNECTOR-BSL-1.1.md']:
        assert (ROOT / name).stat().st_size > 0
        assert name in builder
        assert name in verifier
    assert 'Contents/Resources/Licenses' in builder
    assert 'Contents/Resources/Licenses' in verifier
    assert 'missing release license' in builder
    assert 'missing release license' in verifier
