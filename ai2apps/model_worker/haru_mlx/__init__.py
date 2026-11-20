"""Haru on Apple silicon: the MLX implementation of the full-duplex spoken dialogue model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .config import HaruConfig
from .frames import DuplexConfig, Frame

__version__ = "0.1.0"
__all__ = ["DuplexConfig", "DuplexSession", "Frame", "HaruConfig", "HaruModel", "load_model"]

if TYPE_CHECKING:
    from .models import HaruModel, load_model
    from .session import DuplexSession

# Everything that needs MLX is loaded on first use, so the pure-Python
# modules (config, sampling, audio, weights, server, ...) work without it.
_LAZY = {
    "HaruModel": "models",
    "load_model": "models",
    "DuplexSession": "session",
}


def __getattr__(name: str):
    if name in _LAZY:
        from importlib import import_module

        return getattr(import_module(f".{_LAZY[name]}", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
