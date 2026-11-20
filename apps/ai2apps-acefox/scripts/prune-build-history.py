#!/usr/bin/env python3
"""Keep three local build versions; unrelated files and symlinks are untouched."""
import argparse
import re
import shutil
from pathlib import Path


def prune(directory, kind):
    if not directory.is_dir() or directory.is_symlink():
        return
    candidates = []
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_dir():
            continue
        if kind == "archive":
            dates = re.findall(r"20\d{6}(?:-\d{6})?", path.name)
            if not path.name.startswith("AI2Apps-") or path.suffix != ".app" or not dates:
                continue
            key = (max(dates), path.name)
        else:
            match = re.fullmatch(r"AI2Apps-.+-build(\d+)", path.name)
            if not match:
                continue
            key = (int(match[1]), path.name)
        candidates.append((key, path))
    for _, path in sorted(candidates, reverse=True)[3:]:
        print(f"Removing old {kind}: {path}", flush=True)
        shutil.rmtree(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("archive", "releases"))
    args = parser.parse_args()
    prune(Path(__file__).resolve().parent.parent / ".build" / args.kind, args.kind)
