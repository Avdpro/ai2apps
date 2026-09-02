"""Atomic denoising checkpoints for exact crash recovery."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx

from .safetensors_io import SelectiveSafeTensorReader
from .schedulers import FlowUniPCScheduler


@dataclass(frozen=True, slots=True)
class RestoredDenoiseState:
    """One validated latent and the next scheduler step to execute."""

    sample: mx.array
    next_step: int


class DenoiseCheckpointStore:
    """Save and restore a single atomic, request-bound Safetensors checkpoint."""

    _SCHEMA = "echomimic-mlx-denoise-v1"

    def __init__(self, path: str | Path, fingerprint: str) -> None:
        self.path = Path(path).expanduser().resolve()
        if not fingerprint:
            raise ValueError("checkpoint fingerprint must not be empty")
        self.fingerprint = fingerprint

    def save(self, sample: mx.array, scheduler: FlowUniPCScheduler) -> None:
        metadata = {
            "schema": self._SCHEMA,
            "fingerprint": self.fingerprint,
            **scheduler.state_metadata(),
        }
        tensors = {"sample": sample, **scheduler.state_tensors()}
        mx.eval(*tensors.values())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp.safetensors")
        try:
            mx.save_safetensors(temporary, tensors, metadata=metadata)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def restore(self, scheduler: FlowUniPCScheduler) -> RestoredDenoiseState | None:
        if not self.path.exists():
            return None
        reader = SelectiveSafeTensorReader(self.path)
        metadata = reader.metadata
        if metadata.get("schema") != self._SCHEMA:
            raise ValueError("unsupported denoise checkpoint schema")
        if metadata.get("fingerprint") != self.fingerprint:
            raise ValueError("denoise checkpoint belongs to a different request")
        tensors = reader.read_many(tuple(sorted(reader.names)))
        try:
            sample = tensors.pop("sample")
        except KeyError as error:
            raise ValueError("denoise checkpoint is missing the latent sample") from error
        scheduler.restore_state(tensors, metadata)
        assert scheduler.step_index is not None
        return RestoredDenoiseState(sample, scheduler.step_index)

    def clear(self) -> None:
        """Remove the completed job checkpoint, if one exists."""

        self.path.unlink(missing_ok=True)
