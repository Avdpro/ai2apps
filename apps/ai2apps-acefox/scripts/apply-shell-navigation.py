#!/usr/bin/env python3
"""Apply explicit Shell startup navigation semantics to the packaged browser."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
import zipfile
from pathlib import Path


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one source anchor, found {count}")
    return source.replace(old, new, 1)


def transform(source: str) -> str:
    source = replace_once(source, "  let activeConnection = null;", r'''  let shellNavigationEpoch = null;
  const readShellNavigation = async () => {
    try {
      const value = await IOUtils.readJSON(
        PathUtils.join(PathUtils.parent(descriptorPath), "shell-navigation.json")
      );
      if (value.version === 1 && value.instance_id === instanceID &&
          typeof value.epoch === "string" && value.epoch.length > 0 && value.epoch.length <= 64 &&
          ["helper-start", "menu-restart"].includes(value.reason)) {
        return value;
      }
    } catch {}
    return null;
  };
  let activeConnection = null;''', "navigation epoch")
    source = replace_once(source,
        "      const principal = Services.scriptSecurityManager.createContentPrincipal(\n        Services.io.newURI(connection.shellURL),",
        r'''      const navigation = await readShellNavigation();
      const returnHome = shellNavigationEpoch === null ||
        (navigation && navigation.epoch !== shellNavigationEpoch);
      shellNavigationEpoch = navigation?.epoch || shellNavigationEpoch || "legacy";
      const shellEntryURL = new URL(connection.shellURL);
      shellEntryURL.hash = "ai2apps-shell-start=" + (returnHome ? "home" : "resume");
      connection.shellURL = shellEntryURL.href;
      const principal = Services.scriptSecurityManager.createContentPrincipal(
        Services.io.newURI(connection.shellURL),''', "entry navigation")
    source = replace_once(source,
        "    monitorBusy = true;\n    try {\n      const descriptor = await IOUtils.readJSON(descriptorPath);",
        r'''    monitorBusy = true;
    try {
      const navigation = await readShellNavigation();
      if (navigation?.reason === "helper-start" &&
          navigation.epoch !== shellNavigationEpoch) {
        void openLocalShell();
        return;
      }
      const descriptor = await IOUtils.readJSON(descriptorPath);''', "Helper restart detection")
    return source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("destination", type=Path, nargs="?")
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if args.archive:
        if args.source or args.destination:
            parser.error("--archive cannot be combined with source/destination")
        resource = "chrome/browser/content/browser/ai2apps/shell.mjs"
        with zipfile.ZipFile(args.archive) as archive:
            source = archive.read(resource).decode("utf-8")
        transformed = transform(source)
        with tempfile.TemporaryDirectory(prefix="ai2apps-navigation-") as directory:
            target = Path(directory) / resource
            target.parent.mkdir(parents=True)
            target.write_text(transformed, encoding="utf-8")
            subprocess.run(["/usr/bin/zip", "-q", "-X", str(args.archive.resolve()), resource],
                           cwd=directory, check=True)
    else:
        if not args.source or not args.destination:
            parser.error("source and destination are required")
        args.destination.write_text(transform(args.source.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
