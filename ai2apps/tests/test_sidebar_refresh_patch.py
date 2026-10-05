import importlib.util
from pathlib import Path

import pytest


def patch_module():
    path = Path(__file__).resolve().parents[2] / 'apps/ai2apps-acefox/scripts/apply-sidebar-refresh.py'
    spec = importlib.util.spec_from_file_location('sidebar_refresh_patch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_toolbar_refresh_reload_marker_and_normal_document_identity():
    source = '''function documentURL(value) {
    url.searchParams.delete("ai2apps_context_revision");
}
async function refreshContext({ force = false } = {}) {
  selectionLabel.hidden = true;
  await sendContext();
}
'''
    module = patch_module()
    patched = module.transform(source)
    assert 'if (force)' in patched
    assert 'refreshURL.searchParams.set("ai2apps_sidebar_refresh", "1")' in patched
    assert 'url.searchParams.delete("ai2apps_sidebar_refresh")' in patched
    assert 'miniEntry.fixupAndLoadURIString(refreshURL.href' in patched
    assert module.transform(patched) == patched


def test_unknown_packaged_sidebar_source_fails_closed():
    with pytest.raises(ValueError, match='anchor mismatch'):
        patch_module().transform('unrecognized upstream Sidebar')


def test_menu_patch_is_idempotent_and_keeps_native_clear_private():
    module = patch_module()
    source = '''let sidebarStrings = {
};
  refreshButton.title = sidebarStrings.refresh;
    .addEventListener("click", () => refreshContext({ force: true }));
'''
    patched = module.transform_menu(source)
    assert '"click", openSidebarActions' in patched
    assert 'aria-haspopup' in patched
    assert 'deleteDataFromSite' in patched
    assert 'CLEAR_COOKIES_AND_SITE_DATA' in patched
    assert module.transform_menu(patched) == patched
    with pytest.raises(ValueError, match='anchor mismatch'):
        module.transform_menu('unrecognized source')
