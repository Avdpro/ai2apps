from pathlib import Path

import pytest

from ai2apps.extensions.sandbox_document import inline_sandbox_assets


def test_verified_assets_are_inlined_and_defer_runs_after_body():
    reads = []
    def read(path):
        reads.append(path)
        return {'web/ui.js': 'document.getElementById("app").textContent="ready";',
                'web/ui.css': 'body{color:red}'}[path]
    html = inline_sandbox_assets('<!doctype html><head><link rel="stylesheet" href="ui.css?v=1">'
        '<script defer src="ui.js?v=1"></script></head><body><main id="app"></main></body>', 'web/index.html', read)
    assert reads == ['web/ui.css', 'web/ui.js']
    assert html.index('<main') < html.index('document.getElementById') < html.index('</body>')
    assert 'src=' not in html and '<style>body{color:red}</style>' in html


@pytest.mark.parametrize('url', ['../secret.js', '%2e%2e/secret.js', '/secret.js',
    'https://example.org/a.js', '//example.org/a.js', 'a%5cb.js'])
def test_assets_cannot_escape_verified_package(url):
    with pytest.raises(ValueError):
        inline_sandbox_assets(f'<script src="{url}"></script>', 'web/index.html', lambda _: pytest.fail('must not read'))


@pytest.mark.parametrize('code', ['</script><img src=x>', 'x' * (4 * 1024 * 1024)])
def test_asset_markup_injection_and_size_fail_closed(code):
    with pytest.raises(ValueError):
        inline_sandbox_assets('<script src="ui.js"></script>', 'web/index.html', lambda _: code)


def test_all_suite_forms_use_verified_resource_delivery_and_host_only_io():
    root = Path(__file__).resolve().parents[1] / 'packages/ai2apps-media-voice-studio-suite'
    for name in ('transcription', 'separation', 'audio-voice-replacement', 'video-subtitles', 'video-voice-replacement'):
        resource = f'web/{name}.html'
        html = inline_sandbox_assets((root / resource).read_text(), resource, lambda path: (root / path).read_text())
        assert 'ai2apps:studio-connect' in html
        assert html.index('<main') < html.index('const workflows')
    script = (root / 'web/mini-app.js').read_text()
    assert 'localStorage.' not in script
    assert 'await fetch(' not in script
