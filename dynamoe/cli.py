"""Public DynaMoe command-line entry point.

The server implementation intentionally remains in :mod:`omlx` so upstream
runtime patches stay reviewable.  This module is the stable product boundary.
"""

from __future__ import annotations

import os
import sys


def _apply_environment_compatibility() -> None:
    """Map public DYNAMOE_* controls onto the embedded runtime variables."""
    for name, value in tuple(os.environ.items()):
        if not name.startswith("DYNAMOE_") or name == "DYNAMOE_PRODUCT":
            continue
        runtime_name = "OMLX_" + name.removeprefix("DYNAMOE_")
        os.environ.setdefault(runtime_name, value)


def main() -> None:
    """Run the DynaMoe CLI backed by the embedded oMLX runtime."""
    os.environ["DYNAMOE_PRODUCT"] = "1"
    _apply_environment_compatibility()
    try:
        from omlx.cli import main as runtime_main

        runtime_main()
    except ModuleNotFoundError as exc:
        if exc.name == "huggingface_hub" or (
            exc.name and exc.name.startswith("huggingface_hub.")
        ):
            print(
                "DynaMoe cannot start because huggingface-hub is missing.\n"
                "Install the complete package with:\n"
                "  pip install -U dynamoe\n"
                "or repair this source environment with:\n"
                "  pip install 'huggingface-hub>=1.19.0'",
                file=sys.stderr,
            )
            raise SystemExit(2) from exc
        raise


if __name__ == "__main__":
    main()
