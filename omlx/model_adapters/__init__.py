# SPDX-License-Identifier: Apache-2.0
"""Installable model-adapter API.

Third-party distributions register an adapter through the
``omlx.model_adapters`` Python entry-point group.
"""

from .base import ModelAdapter, ModelAdapterContext
from .packages import (
    ModelAdapterPackageError,
    ModelAdapterPackageManager,
    configure_model_adapter_packages,
)
from .registry import (
    ENTRY_POINT_GROUP,
    ModelAdapterRegistrationError,
    ModelAdapterRegistry,
    adapter_context,
    get_model_adapter_registry,
)

__all__ = [
    "ENTRY_POINT_GROUP",
    "ModelAdapter",
    "ModelAdapterContext",
    "ModelAdapterRegistrationError",
    "ModelAdapterRegistry",
    "ModelAdapterPackageError",
    "ModelAdapterPackageManager",
    "adapter_context",
    "configure_model_adapter_packages",
    "get_model_adapter_registry",
]
