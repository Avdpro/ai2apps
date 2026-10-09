# SPDX-License-Identifier: Apache-2.0
"""System-owned runtime for isolated AI2Apps Model Packages."""

from importlib import import_module
from .protocol import (
    ModelWorkerAdapter,
    ModelWorkerArtifact,
    ModelWorkerCheckpoint,
    ModelWorkerContext,
    ModelWorkerError,
    ModelWorkerPart,
    ModelWorkerRequest,
    ModelWorkerResponse,
    ModelWorkerStream,
)

__all__ = [
    "ModelWorkerAdapter",
    "ModelWorkerArtifact",
    "ModelWorkerCheckpoint",
    "ModelWorkerContext",
    "ModelWorkerError",
    "ModelWorkerPart",
    "ModelWorkerRequest",
    "ModelWorkerResponse",
    "ModelWorkerStream",
    "OmlxChatAdapter",
    "OmlxAudioAdapterBase",
    "OmlxSTTAdapter",
    "OmlxTTSAdapter",
]


def __getattr__(name: str):
    # CUDA/other runtimes need the protocol without importing oMLX dependencies.
    modules = {
        "OmlxChatAdapter": ".omlx_chat",
        "OmlxAudioAdapterBase": ".omlx_audio",
        "OmlxSTTAdapter": ".omlx_audio",
        "OmlxTTSAdapter": ".omlx_audio",
    }
    module = modules.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module, __name__), name)
    globals()[name] = value
    return value
