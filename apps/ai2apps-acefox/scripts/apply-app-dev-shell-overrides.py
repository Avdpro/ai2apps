#!/usr/bin/env python3
"""Apply App-Dev-only native Shell behavior to an AceFox shell.mjs source."""

from __future__ import annotations

import argparse
from pathlib import Path


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one source anchor, found {count}")
    return source.replace(old, new, 1)


def transform(source: str) -> str:
    source = replace_once(
        source,
        "const SHELL_BROWSER_WINDOW_POLL_MS = 500;\n",
        "const SHELL_BROWSER_WINDOW_POLL_MS = 500;\n"
        "const SCREEN_RECORDING_WINDOW_POLL_MS = 250;\n",
        "poll interval",
    )
    source = replace_once(
        source,
        '''  const helperStatusPath = PathUtils.join(
    libraryDirectory,
    "Application Support",
    "AI2Apps",
    "instances",
    instanceID,
    "run",
    "helper.json"
  );
''',
        '''  const helperStatusPath = PathUtils.join(
    libraryDirectory,
    "Application Support",
    "AI2Apps",
    "instances",
    instanceID,
    "run",
    "helper.json"
  );
  const screenRecordingWindowCommandPath = PathUtils.join(
    PathUtils.parent(descriptorPath),
    "screen-recording-window.json"
  );
''',
        "command path",
    )
    source = replace_once(
        source,
        "  let shellBrowserRequestBusy = false;\n",
        "  let shellBrowserRequestBusy = false;\n"
        "  let screenRecordingWindowBusy = false;\n",
        "busy state",
    )
    source = replace_once(
        source,
        '''  retryButton.addEventListener("click", openLocalShell);
''',
        '''  const prepareScreenRecordingWindow = async () => {
    if (
      instanceID !== "app-dev" ||
      screenRecordingWindowBusy ||
      !(await IOUtils.exists(screenRecordingWindowCommandPath))
    ) {
      return;
    }
    screenRecordingWindowBusy = true;
    try {
      const command = await IOUtils.readJSON(screenRecordingWindowCommandPath);
      await IOUtils.remove(screenRecordingWindowCommandPath, {
        ignoreAbsent: true,
      });
      if (
        command?.version !== 1 ||
        command?.instance_id !== "app-dev" ||
        command?.command !== "prepare-screen-recording"
      ) {
        console.error("Rejected invalid App-Dev screen recording command");
        return;
      }
      const baseWindow = window.docShell.treeOwner
        .QueryInterface(Ci.nsIInterfaceRequestor)
        .getInterface(Ci.nsIAppWindow)
        .QueryInterface(Ci.nsIBaseWindow);
      const screenScale = window.devicePixelRatio || 1;
      baseWindow.setPositionAndSize(
        0,
        0,
        Math.round(1600 * screenScale),
        Math.round(900 * screenScale),
        false
      );
      focusAI2AppsWindow(window);
    } catch (error) {
      console.error("Could not prepare App-Dev screen recording window", error);
      await IOUtils.remove(screenRecordingWindowCommandPath, {
        ignoreAbsent: true,
      });
    } finally {
      screenRecordingWindowBusy = false;
    }
  };

  retryButton.addEventListener("click", openLocalShell);
''',
        "screen recording handler",
    )
    source = replace_once(
        source,
        '''  const shellBrowserWindowTimer = setInterval(
    pollShellBrowserWindow,
    SHELL_BROWSER_WINDOW_POLL_MS
  );
''',
        '''  const shellBrowserWindowTimer = setInterval(
    pollShellBrowserWindow,
    SHELL_BROWSER_WINDOW_POLL_MS
  );
  const screenRecordingWindowTimer = setInterval(
    prepareScreenRecordingWindow,
    SCREEN_RECORDING_WINDOW_POLL_MS
  );
''',
        "screen recording timer",
    )
    source = replace_once(
        source,
        '''  window.addEventListener(
    "unload",
    () => clearInterval(shellBrowserWindowTimer),
    { once: true }
  );
''',
        '''  window.addEventListener(
    "unload",
    () => clearInterval(shellBrowserWindowTimer),
    { once: true }
  );
  window.addEventListener(
    "unload",
    () => clearInterval(screenRecordingWindowTimer),
    { once: true }
  );
''',
        "screen recording timer cleanup",
    )
    return source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    transformed = transform(args.source.read_text(encoding="utf-8"))
    args.destination.write_text(transformed, encoding="utf-8")


if __name__ == "__main__":
    main()
