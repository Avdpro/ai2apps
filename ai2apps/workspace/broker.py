"""Narrow host export broker abstraction with atomic replacement."""

from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Protocol


class HostExportBroker(Protocol):
    def export(self, source: Path, destination_directory: Path, name: str) -> Path: ...


class LocalHostExportBroker:
    """Trusted built-in broker; callers must resolve authority before invoking it."""

    def export(self, source: Path, destination_directory: Path, name: str) -> Path:
        directory = destination_directory.resolve(strict=True)
        if not directory.is_dir():
            raise NotADirectoryError(str(directory))
        if Path(name).name != name or name in {"", ".", ".."}:
            raise ValueError("Export name must be a single safe filename")
        destination = directory / name
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{name}.", suffix=".ai2apps-export", dir=directory
        )
        try:
            with os.fdopen(descriptor, "wb") as output, source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_name, destination)
        except BaseException:
            with suppress(FileNotFoundError):
                os.unlink(temporary_name)
            raise
        return destination
