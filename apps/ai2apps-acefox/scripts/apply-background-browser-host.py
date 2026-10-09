#!/usr/bin/env python3
"""Keep native BiDi/Profile lifecycle independent of the Local HTML Shell."""
from __future__ import annotations
import argparse
import subprocess
import tempfile
import zipfile
from pathlib import Path

def replace(source, old, new):
    if source.count(old) != 1:
        raise SystemExit('Native background host source anchor changed: ' + old[:80])
    return source.replace(old, new, 1)

def transform(source):
    source = replace(source, '  let activeConnection = null;', r'''  let backgroundHost = Services.env.get("AI2APPS_BACKGROUND_HOST") === "1";
  let hostHidden = backgroundHost;
  const nativeBaseWindow = window.docShell.treeOwner
    .QueryInterface(Ci.nsIInterfaceRequestor).getInterface(Ci.nsIAppWindow)
    .QueryInterface(Ci.nsIBaseWindow);
  const showHostShell = async () => {
    backgroundHost = false;
    hostHidden = false;
    nativeBaseWindow.visibility = true;
    await openLocalShell();
    focusAI2AppsWindow(window);
  };
  // Closing the UI unloads its HTML. The remaining privileged chrome host
  // owns only protected native protocol bootstrap and Profile lifecycle.
  window.addEventListener("close", event => {
    event.preventDefault();
    hostHidden = true;
    navigationGuardCleanup?.();
    navigationGuardCleanup = null;
    contentBrowser.fixupAndLoadURIString("about:blank", {
      triggeringPrincipal: Services.scriptSecurityManager.getSystemPrincipal(),
    });
    nativeBaseWindow.visibility = false;
  });
  if (backgroundHost) nativeBaseWindow.visibility = false;
  let activeConnection = null;''')
    source = replace(source, '        focusAI2AppsWindow(window);\n        await completeShellBrowserRequest(request, "focused");',
        '        await showHostShell();\n        await completeShellBrowserRequest(request, "focused");')
    source = replace(source, '      contentBrowser.hidden = false;\n      contentBrowser.fixupAndLoadURIString(connection.shellURL, {',
        '      if (!backgroundHost && !hostHidden) {\n      contentBrowser.hidden = false;\n      contentBrowser.fixupAndLoadURIString(connection.shellURL, {')
    source = replace(source, '      activeConnection = connection;', '      }\n      activeConnection = connection;')
    # A Launcher activation requests showing the UI through an instance-private
    # file. No HTML page or browser context is consulted to run a task.
    source = replace(source, '    monitorBusy = true;\n    try {', r'''    monitorBusy = true;
    try {
      const showPath = PathUtils.join(PathUtils.parent(descriptorPath), "shell-foreground-request.json");
      try {
        const foreground = await IOUtils.readJSON(showPath);
        if (foreground.instance_id === instanceID) {
          await IOUtils.remove(showPath);
          void showHostShell();
        }
      } catch {}''')
    source = replace(source, '      } else if (request.action == "bind") {\n        await completeShellBrowserRequest(request, "bound");', r'''      } else if (request.action == "bind") {
        const identity = managedIdentity(request.profile_key);
        let target = browserWindowForProfile(request.profile_key, identity.userContextId);
        if (!target) {
          // Native lifecycle bootstrap only. No Local HTML is loaded here;
          // all DOM actions and timing remain owned by Local's BiDi SDK.
          target = BrowserWindowTracker.openWindow({
            openerWindow: window,
            args: browserWindowArguments(identity.userContextId, null),
          });
          target.__ai2appsProfileKey = request.profile_key;
          bindManagedProfileTabs(target, identity.userContextId);
          applyProfileName(target, request.profile_name);
          aceFoxBrowserWindows.set(request.profile_key, target);
          await new Promise(resolve => {
            if (target.document.readyState == "complete") resolve();
            else target.addEventListener("load", resolve, { once: true });
          });
          const base = target.docShell.treeOwner
            .QueryInterface(Ci.nsIInterfaceRequestor).getInterface(Ci.nsIAppWindow)
            .QueryInterface(Ci.nsIBaseWindow);
          base.visibility = false;
          // Explicit BiDi activation for human assistance restores the window.
          target.addEventListener("focus", () => { base.visibility = true; });
        }
        await completeShellBrowserRequest(request, "bound");''')
    return source

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    args=parser.parse_args()
    resource='chrome/browser/content/browser/ai2apps/shell.mjs'
    with zipfile.ZipFile(args.archive) as archive:
        output=transform(archive.read(resource).decode())
    with tempfile.TemporaryDirectory(prefix='ai2apps-native-host-') as directory:
        path=Path(directory)/resource
        path.parent.mkdir(parents=True)
        path.write_text(output)
        subprocess.run(['/usr/bin/zip','-q','-X',str(args.archive.resolve()),resource],cwd=directory,check=True)
if __name__ == '__main__': main()
