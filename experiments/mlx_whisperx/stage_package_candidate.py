"""Stage a self-contained ACPF source tree without models or test data."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

RUNTIME_MODULES = (
    "__init__.py",
    "aligners.py",
    "assignment.py",
    "audio.py",
    "backends.py",
    "ctc.py",
    "pipeline.py",
    "schema.py",
    "service.py",
    "vad.py",
)


def stage(destination: Path) -> Path:
    source = Path(__file__).resolve().parent
    candidate = source / "package_candidate"
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    shutil.copytree(candidate, destination)
    module_root = destination / "src" / "mlx_whisperx"
    module_root.mkdir(parents=True)
    for name in RUNTIME_MODULES:
        shutil.copy2(source / name, module_root / name)
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    stage(args.destination.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
