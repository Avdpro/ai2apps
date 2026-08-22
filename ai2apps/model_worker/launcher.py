# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402, I001
"""Isolated launcher whose import path is controlled by AI2Apps, not a Package."""

from __future__ import annotations

import os
import sys
from pathlib import Path


# ``python -I`` removes cwd/PYTHONPATH. Add only the trusted distribution root;
# the Package adapter is loaded later by its verified absolute file path.
_PLATFORM_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PLATFORM_ROOT))

# Packaged AI2Apps keeps large, shared framework dependencies in a separate
# immutable layer. ``python -I`` deliberately ignores PYTHONPATH, so the Host
# passes this already-validated, sandbox-readable path through a private
# AI2Apps variable instead of allowing a Package to influence imports.
if configured_framework_site := os.environ.get(
    "AI2APPS_TRUSTED_FRAMEWORK_SITE_PACKAGES"
):
    # The Host already resolved and validated this directory before generating
    # both the child environment and the Sandbox profile. Resolving it again
    # here would require metadata access to every ancestor (including
    # ``/Users``), which the intentionally narrow profile does not grant.
    framework_site = Path(configured_framework_site)
    if not framework_site.is_absolute():
        raise RuntimeError("AI2Apps trusted framework site-packages must be absolute")
    sys.path.insert(1, str(framework_site))

from ai2apps.model_worker.server import main


if __name__ == "__main__":
    main()
