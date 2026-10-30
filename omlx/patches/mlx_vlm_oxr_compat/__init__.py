# SPDX-License-Identifier: MIT
"""OXR support backported from mlx-vlm 8826b112, without changing its global pin.

Only model_type=oxr activates this module. Native upstream modules take priority
because the vendor path is appended. Errors propagate rather than falling back
to a text-only processor for an image request.
"""
from pathlib import Path
import importlib

_APPLIED = False

def apply_mlx_vlm_oxr_compat_patch() -> bool:
    global _APPLIED
    if _APPLIED:
        return False
    import mlx_vlm.models as models
    vendor = str(Path(__file__).resolve().parent / "vendor/mlx_vlm/models")
    if vendor not in models.__path__:
        models.__path__.append(vendor)
    importlib.import_module("mlx_vlm.models.oxr")
    from mlx_vlm import prompt_utils
    prompt_utils.MODEL_CONFIG.setdefault(
        "oxr", prompt_utils.MessageFormat.LIST_WITH_IMAGE_FIRST
    )
    _APPLIED = True
    return True
