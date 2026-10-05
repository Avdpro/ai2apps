#!/usr/bin/env python3
"""Make the native Sidebar toolbar refresh reload its current Mini-Entry."""
import argparse
import subprocess
import tempfile
import zipfile
from pathlib import Path

RESOURCE = "chrome/browser/content/browser/ai2apps/sidebar.mjs"

def transform(source):
    old = "  selectionLabel.hidden = true;\n  await sendContext();"
    new = """  selectionLabel.hidden = true;
  if (force) {
    deliveredContextKeys.set(selectedMiniEntry, contextKey());
    const refreshURL = new URL(miniEntryURL(++contextNavigationRevision));
    refreshURL.searchParams.set("ai2apps_sidebar_refresh", "1");
    miniEntry.fixupAndLoadURIString(refreshURL.href, {
      triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal(),
    });
    return;
  }
  await sendContext();"""
    if "ai2apps_sidebar_refresh" in source:
        return source
    if source.count(old) != 1:
        raise ValueError("Sidebar refresh source anchor mismatch")
    source = source.replace(old,new,1)
    # A refresh marker must not make ordinary sendContext reload this document again.
    old = '    url.searchParams.delete("ai2apps_context_revision");'
    if source.count(old) != 1:
        raise ValueError("Sidebar document URL source anchor mismatch")
    return source.replace(old, old+'\n    url.searchParams.delete("ai2apps_sidebar_refresh");',1)

def transform_menu(source):
    if 'function openSidebarActions(' in source:
        return source
    old = '.addEventListener("click", () => refreshContext({ force: true }));'
    if source.count(old) != 1:
        raise ValueError("Sidebar menu source anchor mismatch")
    source = source.replace(old, '.addEventListener("click", openSidebarActions);', 1)
    old = '  refreshButton.title = sidebarStrings.refresh;'
    if source.count(old) != 1:
        raise ValueError("Sidebar menu locale anchor mismatch")
    source = source.replace(old, '\n'.join([
        '  refreshButton.title = sidebarStrings.menu;',
        '  refreshButton.textContent = "⋯";',
        '  refreshButton.setAttribute("aria-label", sidebarStrings.menu);',
        '  refreshButton.setAttribute("aria-haspopup", "menu");',
    ]), 1)
    defaults = '  menu: "Panel menu",\n  deleteData: "Delete site data",\n  deleteDataConfirm: "Delete cookies, storage and caches for {domain}? This will sign you out.",\n  deleteDataSuccess: "Site data for {domain} has been deleted.",\n  deleteDataFailed: "Some site data could not be deleted. Please retry.",\n'
    source = source.replace('let sidebarStrings = {\n', 'let sidebarStrings = {\n' + defaults, 1)
    asset = Path(__file__).resolve().parents[3] / "ai2apps/browser/sidebar_menu.js"
    return source + "\n" + asset.read_text()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--archive",type=Path,required=True)
    args=parser.parse_args()
    with zipfile.ZipFile(args.archive) as archive:
        source=archive.read(RESOURCE).decode()
    with tempfile.TemporaryDirectory() as directory:
        target=Path(directory)/RESOURCE
        target.parent.mkdir(parents=True)
        target.write_text(transform_menu(transform(source)))
        subprocess.run(["/usr/bin/zip","-q","-X",str(args.archive.resolve()),RESOURCE],cwd=directory,check=True)

if __name__=="__main__":
    main()
